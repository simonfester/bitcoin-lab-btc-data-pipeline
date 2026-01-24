#!/usr/bin/env python3
"""
Quick script to sync Glassnode hourly derivatives data
======================================================
Temporary solution until glassnode_downloader.py is updated to support resolutions.
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
DATA_DIR = PROJECT_ROOT / "data" / "glassnode" / "hourly"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Metrics to sync (hourly resolution available)
HOURLY_METRICS = {
    "funding_rate": "/v1/metrics/derivatives/futures_funding_rate_perpetual",
    "liquidations_long": "/v1/metrics/derivatives/futures_liquidated_volume_long_sum",
    "liquidations_short": "/v1/metrics/derivatives/futures_liquidated_volume_short_sum",
    "open_interest": "/v1/metrics/derivatives/futures_open_interest_sum",
}


def fetch_hourly_metric(endpoint: str, since: str = None) -> pd.DataFrame:
    """Fetch hourly resolution data from Glassnode"""

    params = {
        'a': 'BTC',
        'i': '1h',  # Hourly resolution
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
        print(f"  ❌ Error {response.status_code}")
        return None

    data = response.json()

    if not data:
        print(f"  ⚠️  No data returned")
        return None

    # Convert to DataFrame
    df = pd.DataFrame(data)
    df['time'] = pd.to_datetime(df['t'], unit='s', utc=True)
    df = df.rename(columns={'v': 'value'})
    df = df.set_index('time')[['value']]
    df = df.sort_index()

    print(f"  ✓ Fetched {len(df):,} rows (last: {df.index[-1]})")

    return df


def sync_glassnode_hourly():
    """Sync all hourly Glassnode metrics"""

    print("=" * 80)
    print("GLASSNODE HOURLY SYNC")
    print("=" * 80)

    total_added = 0

    for metric_name, endpoint in HOURLY_METRICS.items():
        print(f"\n{metric_name}:")

        file_path = DATA_DIR / f"{metric_name}.parquet"

        # Check if file exists for incremental update
        since = None
        if file_path.exists():
            existing = pd.read_parquet(file_path)
            if len(existing) > 0:
                last_time = existing.index.max()
                since = (last_time + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  Incremental from: {since}")

        # Fetch data
        df = fetch_hourly_metric(endpoint, since=since)

        if df is None or len(df) == 0:
            if file_path.exists():
                print(f"  Already up to date")
            else:
                print(f"  No data available")
            continue

        # Merge with existing
        if file_path.exists():
            existing = pd.read_parquet(file_path)
            df = pd.concat([existing, df])
            df = df[~df.index.duplicated(keep='last')]
            df = df.sort_index()

        # Save
        df.to_parquet(file_path, compression='zstd')

        rows_added = len(df) - (len(existing) if file_path.exists() and 'existing' in locals() else 0)
        total_added += rows_added

        print(f"  ✓ Saved: {len(df):,} total rows ({rows_added} new)")

    print("\n" + "=" * 80)
    print(f"Sync complete: {len(HOURLY_METRICS)} metrics, {total_added} rows added")
    print("=" * 80)


if __name__ == '__main__':
    sync_glassnode_hourly()
