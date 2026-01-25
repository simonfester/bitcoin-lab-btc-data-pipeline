#!/usr/bin/env python3
"""
Sync Glassnode Daily Derivatives Data
======================================
Syncs daily derivatives metrics from Glassnode API:
- Funding rates
- Liquidations (long/short)
- Open interest
- Estimated leverage ratio

Usage:
    python scripts/sync_glassnode_daily.py
"""

import sys
from pathlib import Path
import pandas as pd
import requests
from datetime import datetime, timedelta

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.glassnode_downloader import GLASSNODE_API_KEY, GLASSNODE_BASE_URL

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "glassnode" / "daily"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Metrics to sync (daily resolution)
DAILY_METRICS = {
    "funding_rate": "/v1/metrics/derivatives/futures_funding_rate_perpetual",
    "liquidations_long": "/v1/metrics/derivatives/futures_liquidated_volume_long_sum",
    "liquidations_short": "/v1/metrics/derivatives/futures_liquidated_volume_short_sum",
    "open_interest": "/v1/metrics/derivatives/futures_open_interest_sum",
    "estimated_leverage_ratio": "/v1/metrics/derivatives/futures_estimated_leverage_ratio",
}


def fetch_daily_metric(endpoint: str, since: str = None) -> pd.DataFrame:
    """Fetch daily resolution data from Glassnode"""

    params = {
        'a': 'BTC',
        'i': '24h',  # Daily resolution
        'api_key': GLASSNODE_API_KEY
    }

    if since:
        # Convert to timestamp
        since_dt = pd.Timestamp(since)
        params['s'] = int(since_dt.timestamp())

    url = f"{GLASSNODE_BASE_URL}{endpoint}"

    print(f"  Fetching {endpoint}...")
    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        # Handle 400 error for "since after until" (no new data available)
        if response.status_code == 400 and 'since' in response.text.lower():
            print(f"  ✅ Already up to date (no new data)")
            return pd.DataFrame()  # Return empty DataFrame
        print(f"  ❌ Error {response.status_code}: {response.text[:100]}")
        return None

    data = response.json()

    if not data:
        print(f"  ✅ Already up to date (no data returned)")
        return pd.DataFrame()  # Return empty DataFrame instead of None

    # Convert to DataFrame
    df = pd.DataFrame(data)
    df['time'] = pd.to_datetime(df['t'], unit='s', utc=True)
    df = df.rename(columns={'v': 'value'})
    df = df[['time', 'value']]
    df = df.sort_values('time')

    print(f"  ✓ Fetched {len(df):,} rows (last: {df['time'].iloc[-1]})")

    return df


def sync_glassnode_daily():
    """Sync all daily Glassnode metrics"""

    print("=" * 80)
    print("GLASSNODE DAILY SYNC (Derivatives)")
    print("=" * 80)

    if not GLASSNODE_API_KEY or GLASSNODE_API_KEY == "YOUR_GLASSNODE_API_KEY":
        print("⚠️  Glassnode API key not configured")
        print("   Set in src/glassnode_downloader.py or .env")
        print("   Skipping Glassnode sync")
        return

    total_added = 0
    success_count = 0
    error_count = 0

    for metric_name, endpoint in DAILY_METRICS.items():
        print(f"\n📊 {metric_name}:")

        file_path = DATA_DIR / f"{metric_name}.parquet"

        # Check if file exists for incremental update
        since = None
        existing_df = None
        if file_path.exists():
            try:
                existing_df = pd.read_parquet(file_path)
                if len(existing_df) > 0:
                    last_time = existing_df['time'].max()
                    since = (last_time + timedelta(days=1)).strftime("%Y-%m-%d")
                    print(f"  Incremental from: {since}")
            except Exception as e:
                print(f"  ⚠️  Error reading existing file: {e}")
                existing_df = None

        # Fetch data
        df = fetch_daily_metric(endpoint, since=since)

        if df is None:
            print(f"  ❌ Failed to fetch data")
            error_count += 1
            continue

        if len(df) == 0:
            # Empty DataFrame means no new data (already up to date)
            # The message was already printed in fetch_daily_metric
            success_count += 1
            continue

        # Merge with existing
        if existing_df is not None:
            df = pd.concat([existing_df, df])
            df = df.drop_duplicates(subset=['time'], keep='last')
            df = df.sort_values('time')

        # Save
        df.to_parquet(file_path, compression='zstd', index=False)

        rows_added = len(df) - (len(existing_df) if existing_df is not None else 0)
        total_added += rows_added

        print(f"  ✅ Saved: {len(df):,} total rows ({rows_added} new)")
        success_count += 1

    print("\n" + "=" * 80)
    print(f"✅ Sync complete: {success_count}/{len(DAILY_METRICS)} metrics synced")
    if total_added > 0:
        print(f"📈 {total_added} new rows added")
    if error_count > 0:
        print(f"⚠️  {error_count} metrics failed")
    print("=" * 80)


if __name__ == '__main__':
    sync_glassnode_daily()
