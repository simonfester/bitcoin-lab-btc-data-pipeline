"""
BRK (Bitcoin Research Kit) API Data Pipeline
=============================================
Downloads, stores, and updates Bitcoin on-chain metrics from the FREE BRK API.

This is a parallel implementation to the Bitcoin Lab downloader, using the same
patterns but for the free BRK API.

NOTE: BRK only supports DAILY resolution. For hourly data, use Bitcoin Lab API.

Usage:
    python -m src.brk_downloader sync           # Daily incremental sync
    python -m src.brk_downloader backfill       # Full daily backfill
    python -m src.brk_downloader status         # Show sync status
    python -m src.brk_downloader refresh        # Force refresh all metrics
"""

import os
import json
import time
import logging
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, field, asdict

import requests
from requests.exceptions import ConnectionError, Timeout
import pandas as pd

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"

# BRK data directory (separate from Bitcoin Lab)
BRK_DATA_DIR = DATA_DIR / "brk" / "daily"
BRK_STATE_FILE = CONFIG_DIR / "brk_sync_state.json"

# BRK API settings - CURRENT API at next.bitview.space
# Note: bitcoinresearchkit.org is outdated, next.bitview.space is current
BRK_BASE_URL = "https://next.bitview.space"
BRK_EPOCH = pd.Timestamp('2009-01-08')  # Day 0 in BRK's date index (Bitcoin network start)

# Ensure directories exist
BRK_DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "brk_sync.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# METRIC DEFINITIONS
# =============================================================================

# BRK metric name -> standard name mapping
# Format: {standard_name: brk_api_name}
# These map our standard names to BRK's metric IDs
# Use /api/metrics/search/{query} to find available metrics
#
# BRK is FREE and provides current daily data - use as primary source
BRK_METRICS = {
    # === PRICE ===
    'price': 'price_close',  # Main price metric
    'price_200d_sma': 'price_200d_sma',  # Corrected from sma_200
    
    # === SOPR FAMILY ===
    'sopr': 'sopr',
    'sopr_sth': 'sth_sopr',
    'sopr_lth': 'lth_sopr',
    'sopr_adjusted': 'adjusted_sopr',
    
    # === MVRV FAMILY ===
    'mvrv': 'mvrv',
    'mvrv_sth': 'sth_mvrv',
    'mvrv_lth': 'lth_mvrv',
    
    # === NUPL FAMILY ===
    # NOTE: No plain 'nupl' metric, use net_unrealized_pnl instead
    'nupl': 'net_unrealized_pnl',  # Maps to net unrealized P&L
    'nupl_lth': 'lth_nupl',
    'nupl_sth': 'sth_nupl',
    'unrealized_profit': 'unrealized_profit',
    'unrealized_loss': 'unrealized_loss',
    
    # === REALIZED METRICS ===
    'realized_cap': 'realized_cap',
    'realized_price': 'realized_price',
    'realized_price_sth': 'sth_realized_price',
    'realized_price_lth': 'lth_realized_price',
    'realized_profit': 'realized_profit',
    'realized_loss': 'realized_loss',
    'net_realized_pnl': 'net_realized_pnl',
    
    # === SUPPLY METRICS ===
    'supply_lth': 'lth_supply',
    'supply_sth': 'sth_supply',
    'supply_in_profit': 'supply_in_profit',
    'supply_in_loss': 'supply_in_loss',
    'supply_total': 'supply',
    
    # === COST BASIS / PRICING ===
    'true_market_mean_price': 'true_market_mean',
    'market_cap': 'market_cap',
    
    # === COINTIME ECONOMICS ===
    'liveliness': 'liveliness',
    'aviv': 'active_price_ratio',  # AVIV = Active Value to Investor Value = active_price_ratio
    'active_price': 'active_price',
    'vaulted_price': 'vaulted_price',
    'cointime_price': 'cointime_price',
    'investor_cap': 'investor_cap',
    'thermo_cap': 'thermo_cap',  # Corrected from thermocap
    
    # === SELL-SIDE RISK (James Check) ===
    'sell_side_risk': 'sell_side_risk_ratio',
    'sell_side_risk_sth': 'sth_sell_side_risk_ratio',
    'sell_side_risk_lth': 'lth_sell_side_risk_ratio',
    
    # === MINING ===
    'puell_multiple': 'puell_multiple',
    'difficulty': 'difficulty',
    
    # === COINDAYS ===
    'coindays_destroyed': 'coindays_destroyed',
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass 
class MetricState:
    """Sync state for a single metric."""
    last_timestamp: Optional[str] = None
    last_sync: Optional[str] = None
    row_count: int = 0
    status: str = "pending"
    error: Optional[str] = None


@dataclass
class SyncState:
    """Overall sync state."""
    last_sync: Optional[str] = None
    metrics: dict = field(default_factory=dict)
    
    def get_metric_state(self, name: str) -> MetricState:
        if name not in self.metrics:
            self.metrics[name] = asdict(MetricState())
        return MetricState(**self.metrics[name])
    
    def set_metric_state(self, name: str, state: MetricState):
        self.metrics[name] = asdict(state)
    
    @classmethod
    def load(cls, path: Path) -> "SyncState":
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            return cls(
                last_sync=data.get("last_sync"),
                metrics=data.get("metrics", {})
            )
        return cls()
    
    def save(self, path: Path):
        with open(path, "w") as f:
            json.dump({"last_sync": self.last_sync, "metrics": self.metrics}, f, indent=2)


# =============================================================================
# BRK API CLIENT
# =============================================================================

class BRKAPI:
    """Client for BRK (Bitcoin Research Kit) API - FREE, no auth required."""
    
    def __init__(self, base_url: str = BRK_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "bitcoin-lab-pipeline/1.0"
        })
    
    def _request_with_retry(self, url: str, params: dict = None, timeout: int = 30, max_retries: int = 3) -> requests.Response:
        """Make a GET request with retry logic for transient errors."""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=timeout)
            except (ConnectionError, Timeout) as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"  Connection error, retrying in {wait}s: {e}")
                    time.sleep(wait)
                    continue
                raise ValueError(f"Connection failed after {max_retries} attempts: {e}")

            if response.status_code == 200:
                return response

            # 5xx: retry
            if 500 <= response.status_code < 600:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"  Server error {response.status_code}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

            # 429: retry with backoff
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    wait = int(response.headers.get("Retry-After", 30))
                    logger.warning(f"  Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue

            # Non-retryable (4xx except 429) or exhausted retries — return as-is
            return response

        return response

    def list_metrics(self, page: int = 0) -> list:
        """List available metrics from BRK API."""
        url = f"{self.base_url}/api/metrics/list"
        params = {"page": page} if page > 0 else {}

        try:
            response = self._request_with_retry(url, params=params)
            if response.status_code != 200:
                logger.warning(f"Failed to list metrics: HTTP {response.status_code}")
                return []
            data = response.json()
            return data.get('metrics', [])
        except Exception as e:
            logger.warning(f"Failed to list metrics: {e}")
            return []

    def search_metrics(self, query: str, limit: int = 20) -> list:
        """Search for metrics matching a query."""
        url = f"{self.base_url}/api/metrics/search/{query}"
        params = {"limit": limit}

        try:
            response = self._request_with_retry(url, params=params)
            if response.status_code != 200:
                logger.warning(f"Failed to search metrics: HTTP {response.status_code}")
                return []
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to search metrics: {e}")
            return []

    def fetch_metric(self, brk_metric_name: str) -> pd.DataFrame:
        """
        Fetch complete metric data from BRK API.

        NEW API format (next.bitview.space):
        /api/metric/{metric}/dateindex

        Response format (MetricData):
        {"version": N, "total": N, "start": N, "end": N, "data": [...]}

        Day 0 = 2008-01-03 (BRK_EPOCH)

        Returns DataFrame with columns: [time, value]
        """
        url = f"{self.base_url}/api/metric/{brk_metric_name}/dateindex"
        logger.debug(f"Fetching {url}")

        try:
            response = self._request_with_retry(url, timeout=120)
            if response.status_code == 404:
                logger.warning(f"Metric '{brk_metric_name}' not found on BRK API (404)")
                return pd.DataFrame(columns=["time", "value"])
            if response.status_code != 200:
                raise ValueError(
                    f"BRK API error for {brk_metric_name}: HTTP {response.status_code} — "
                    f"{response.text[:200] if response.text else response.reason}"
                )
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"BRK API request failed for {brk_metric_name}: {e}")
        
        data = response.json()
        
        # New API returns MetricData: {"version": N, "total": N, "start": N, "end": N, "data": [...]}
        if 'data' in data:
            values = data['data']
            start_idx = data.get('start', 0)
        else:
            logger.warning(f"Unexpected BRK response format: {list(data.keys())}")
            return pd.DataFrame(columns=["time", "value"])
        
        if not values:
            return pd.DataFrame(columns=["time", "value"])
        
        # Generate dates from BRK epoch
        dates = [BRK_EPOCH + timedelta(days=start_idx + i) for i in range(len(values))]
        
        df = pd.DataFrame({
            'time': pd.DatetimeIndex(dates),
            'value': values
        })
        
        # Remove null values
        df = df.dropna(subset=['value'])
        
        # Ensure time is UTC
        df['time'] = df['time'].dt.tz_localize('UTC')
        
        return df.sort_values('time').reset_index(drop=True)
    
    def fetch_metric_incremental(
        self, 
        brk_metric_name: str, 
        since: datetime
    ) -> pd.DataFrame:
        """
        Fetch metric data since a specific timestamp.
        
        BRK doesn't support time-based queries, so we fetch all and filter.
        This is still fast because BRK is free and fast.
        """
        df = self.fetch_metric(brk_metric_name)
        
        if df.empty:
            return df
        
        # Filter to data after 'since'
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        
        df = df[df['time'] > since]
        
        return df


# =============================================================================
# STORAGE (Same pattern as Bitcoin Lab)
# =============================================================================

class ParquetStorage:
    """Handles reading and writing metric data to Parquet files."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _metric_path(self, metric_name: str) -> Path:
        return self.data_dir / f"{metric_name}.parquet"
    
    def exists(self, metric_name: str) -> bool:
        return self._metric_path(metric_name).exists()
    
    def read(self, metric_name: str) -> pd.DataFrame:
        """Read metric data from Parquet."""
        path = self._metric_path(metric_name)
        if not path.exists():
            return pd.DataFrame(columns=["time", "value"])
        return pd.read_parquet(path)
    
    def write(self, metric_name: str, df: pd.DataFrame):
        """Write metric data to Parquet."""
        if df.empty:
            return
        
        df = df.copy()
        df["time"] = pd.to_datetime(df["time"], utc=True)
        
        path = self._metric_path(metric_name)
        df.to_parquet(path, compression="snappy", index=False)
        logger.debug(f"Wrote {len(df)} rows to {path}")
    
    def append(self, metric_name: str, new_df: pd.DataFrame) -> int:
        """
        Append new data to existing metric, handling deduplication.
        
        Returns number of new rows added.
        """
        if new_df.empty:
            return 0
        
        existing = self.read(metric_name)
        
        if existing.empty:
            self.write(metric_name, new_df)
            return len(new_df)
        
        # Combine and deduplicate by time
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["time"], keep="last")
        combined = combined.sort_values("time").reset_index(drop=True)
        
        new_rows = len(combined) - len(existing)
        
        self.write(metric_name, combined)
        return new_rows
    
    def get_last_timestamp(self, metric_name: str) -> Optional[datetime]:
        """Get the most recent timestamp for a metric."""
        df = self.read(metric_name)
        if df.empty:
            return None
        return df["time"].max().to_pydatetime()
    
    def get_row_count(self, metric_name: str) -> int:
        """Get number of rows for a metric."""
        if not self.exists(metric_name):
            return 0
        return len(self.read(metric_name))


# =============================================================================
# SYNC ENGINE
# =============================================================================

class BRKSyncEngine:
    """Orchestrates the BRK sync process."""
    
    def __init__(
        self,
        api: BRKAPI,
        storage: ParquetStorage,
        metrics: Dict[str, str],
        state_path: Path
    ):
        self.api = api
        self.storage = storage
        self.metrics = metrics  # {standard_name: brk_name}
        self.state_path = state_path
        self.state = SyncState.load(state_path)
    
    def _save_state(self):
        self.state.save(self.state_path)
    
    def sync_metric(
        self,
        standard_name: str,
        brk_name: str,
        force_full: bool = False
    ) -> tuple[bool, int, Optional[str]]:
        """
        Sync a single metric.
        
        Returns: (success, rows_added, error_message)
        """
        metric_state = self.state.get_metric_state(standard_name)
        
        try:
            # Determine if incremental or full sync
            last_ts = self.storage.get_last_timestamp(standard_name)
            
            if last_ts and not force_full:
                logger.info(f"Syncing {standard_name} (incremental from {last_ts.date()})...")
                df = self.api.fetch_metric_incremental(brk_name, last_ts)
            else:
                logger.info(f"Syncing {standard_name} (full download)...")
                df = self.api.fetch_metric(brk_name)
            
            if df.empty:
                logger.info(f"  → No new data for {standard_name}")
                metric_state.status = "ok"
                metric_state.last_sync = datetime.now(timezone.utc).isoformat()
                self.state.set_metric_state(standard_name, metric_state)
                return True, 0, None
            
            # Append to storage
            rows_added = self.storage.append(standard_name, df)
            
            # Update state
            metric_state.last_timestamp = df["time"].max().isoformat()
            metric_state.last_sync = datetime.now(timezone.utc).isoformat()
            metric_state.row_count = self.storage.get_row_count(standard_name)
            metric_state.status = "ok"
            metric_state.error = None
            self.state.set_metric_state(standard_name, metric_state)
            
            logger.info(f"  → Added {rows_added} rows (total: {metric_state.row_count})")
            return True, rows_added, None
            
        except ValueError as e:
            error_msg = str(e)
            # Distinguish between "not found" and other errors
            if "404" in error_msg or "not found" in error_msg.lower():
                logger.warning(f"  → NOT FOUND {standard_name}: metric unavailable on BRK")
                metric_state.status = "not_found"
            elif "Connection failed" in error_msg or "timeout" in error_msg.lower():
                logger.error(f"  → CONNECTION ERROR {standard_name}: {error_msg}")
                metric_state.status = "connection_error"
            else:
                logger.error(f"  → API ERROR {standard_name}: {error_msg}")
                metric_state.status = "error"
            metric_state.error = error_msg
            metric_state.last_sync = datetime.now(timezone.utc).isoformat()
            self.state.set_metric_state(standard_name, metric_state)
            return False, 0, error_msg

        except Exception as e:
            error_msg = str(e)
            logger.error(f"  → UNEXPECTED ERROR syncing {standard_name}: {error_msg}")
            metric_state.status = "error"
            metric_state.error = error_msg
            metric_state.last_sync = datetime.now(timezone.utc).isoformat()
            self.state.set_metric_state(standard_name, metric_state)
            return False, 0, error_msg
    
    def sync_all(self, force_full: bool = False, max_errors: int = 10) -> dict:
        """
        Sync all metrics.
        
        Args:
            force_full: If True, re-download everything (default: incremental)
            max_errors: Stop after this many consecutive errors
        
        Returns summary dict.
        """
        logger.info("=" * 60)
        logger.info(f"Starting BRK sync ({'full' if force_full else 'incremental'})...")
        logger.info(f"Metrics to sync: {len(self.metrics)}")
        logger.info("=" * 60)
        
        results = {
            "started": datetime.now(timezone.utc).isoformat(),
            "source": "brk",
            "mode": "full" if force_full else "incremental",
            "metrics_total": len(self.metrics),
            "metrics_success": 0,
            "metrics_failed": 0,
            "rows_added": 0,
            "errors": []
        }
        
        consecutive_errors = 0
        
        for standard_name, brk_name in self.metrics.items():
            success, rows, error = self.sync_metric(standard_name, brk_name, force_full)
            
            if success:
                results["metrics_success"] += 1
                results["rows_added"] += rows
                consecutive_errors = 0
            else:
                results["metrics_failed"] += 1
                results["errors"].append({"metric": standard_name, "error": error})
                consecutive_errors += 1
                
                if consecutive_errors >= max_errors:
                    logger.error(f"Too many consecutive errors ({max_errors}), stopping.")
                    break
            
            # Save state after each metric
            self._save_state()
        
        # Final state update
        self.state.last_sync = datetime.now(timezone.utc).isoformat()
        self._save_state()
        
        results["completed"] = datetime.now(timezone.utc).isoformat()
        
        logger.info("=" * 60)
        logger.info(f"BRK sync complete: {results['metrics_success']}/{results['metrics_total']} metrics")
        logger.info(f"Total rows added: {results['rows_added']}")
        if results["metrics_failed"] > 0:
            logger.warning(f"  {results['metrics_failed']} metrics failed")
        logger.info("=" * 60)
        
        return results
    
    def backfill(self) -> dict:
        """Run full historical backfill (same as sync with force_full=True)."""
        logger.info("Running BRK full backfill...")
        return self.sync_all(force_full=True)
    
    def get_status(self) -> dict:
        """Get current sync status."""
        status = {
            "source": "brk",
            "resolution": "daily",
            "last_sync": self.state.last_sync,
            "data_dir": str(self.storage.data_dir),
            "metrics": {}
        }
        
        for standard_name in self.metrics.keys():
            state = self.state.get_metric_state(standard_name)
            status["metrics"][standard_name] = {
                "status": state.status,
                "last_timestamp": state.last_timestamp,
                "row_count": state.row_count,
                "error": state.error
            }
        
        return status


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def create_engine() -> BRKSyncEngine:
    """Create and configure the BRK sync engine."""
    api = BRKAPI(BRK_BASE_URL)
    storage = ParquetStorage(BRK_DATA_DIR)
    return BRKSyncEngine(api, storage, BRK_METRICS, BRK_STATE_FILE)


def cmd_sync():
    """Run incremental sync."""
    engine = create_engine()
    return engine.sync_all(force_full=False)


def cmd_backfill():
    """Run full backfill."""
    engine = create_engine()
    return engine.backfill()


def cmd_refresh():
    """Force refresh all metrics (alias for backfill)."""
    return cmd_backfill()


def cmd_discover(query: str = None):
    """Discover available metrics on BRK API."""
    api = BRKAPI(BRK_BASE_URL)
    
    if query:
        print(f"\nSearching for metrics matching '{query}'...\n")
        metrics = api.search_metrics(query, limit=50)
        if metrics:
            for m in metrics:
                print(f"  - {m}")
            print(f"\nFound {len(metrics)} metrics")
        else:
            print("No metrics found")
    else:
        print(f"\nListing all available metrics (page 0)...\n")
        metrics = api.list_metrics(page=0)
        for m in metrics[:50]:  # First 50
            print(f"  - {m}")
        print(f"\n... showing first 50 of {len(metrics)}+ metrics")
        print("Use: python run.py brk-discover <search_term> to search")


def cmd_status():
    """Show sync status."""
    engine = create_engine()
    status = engine.get_status()
    
    print(f"\n{'='*70}")
    print("BRK SYNC STATUS")
    print(f"{'='*70}")
    print(f"Source: {status['source']}")
    print(f"Resolution: {status['resolution']} (BRK only supports daily)")
    print(f"Data directory: {status['data_dir']}")
    print(f"Last sync: {status['last_sync'] or 'Never'}\n")
    
    print(f"{'Metric':<25} {'Status':<8} {'Rows':>10} {'Last Data':<20}")
    print("-" * 70)
    
    ok_count = 0
    error_count = 0
    pending_count = 0
    total_rows = 0
    
    for name, info in sorted(status["metrics"].items()):
        last_ts = info["last_timestamp"][:10] if info["last_timestamp"] else "N/A"
        row_count = info["row_count"]
        total_rows += row_count
        
        status_icon = {
            "ok": "✓",
            "error": "✗",
            "pending": "○"
        }.get(info["status"], "?")
        
        if info["status"] == "ok":
            ok_count += 1
        elif info["status"] == "error":
            error_count += 1
        else:
            pending_count += 1
        
        print(f"{name:<25} {status_icon} {info['status']:<6} {row_count:>10,} {last_ts:<20}")
        
        if info["error"]:
            print(f"  └─ Error: {info['error'][:50]}")
    
    print("-" * 70)
    print(f"Total: {ok_count} ok, {error_count} errors, {pending_count} pending")
    print(f"Total rows: {total_rows:,}")
    print(f"{'='*70}\n")
    
    return status


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BRK (Bitcoin Research Kit) API Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s sync            Incremental sync (only new data)
  %(prog)s backfill        Full historical download
  %(prog)s refresh         Force refresh all metrics
  %(prog)s status          Show sync status
  %(prog)s discover        List available metrics
  %(prog)s discover mvrv   Search for metrics matching 'mvrv'

NOTE: BRK only provides DAILY data. For hourly data, use Bitcoin Lab API.
        """
    )
    
    parser.add_argument(
        "command",
        choices=["sync", "backfill", "refresh", "status", "discover"],
        help="Command to run"
    )
    
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Search query for discover command"
    )
    
    args = parser.parse_args()
    
    if args.command == "sync":
        cmd_sync()
    elif args.command == "backfill":
        cmd_backfill()
    elif args.command == "refresh":
        cmd_refresh()
    elif args.command == "status":
        cmd_status()
    elif args.command == "discover":
        cmd_discover(args.query)


if __name__ == "__main__":
    main()
