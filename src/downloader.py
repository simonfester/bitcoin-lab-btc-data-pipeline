"""
Bitcoin Lab API Data Pipeline
=============================
Downloads, stores, and updates Bitcoin on-chain metrics for backtesting and ML.

Usage:
    python -m src.downloader sync          # Incremental sync (daily use)
    python -m src.downloader backfill      # Full historical backfill
    python -m src.downloader status        # Show sync status
    python -m src.downloader info          # Show API quota info
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

import yaml
import requests
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
for d in [RAW_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "sync.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MetricConfig:
    """Configuration for a single metric."""
    name: str
    endpoint: str
    data_field: str
    priority: str = "medium"
    tier: int = 0
    description: str = ""
    
    @property
    def priority_order(self) -> int:
        return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(self.priority, 2)


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
# API CLIENT
# =============================================================================

class BitcoinLabAPI:
    """Client for Bitcoin Lab API."""
    
    def __init__(self, base_url: str, token: str, rate_limit: int = 60):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Token": token,
            "Accept": "application/json"
        })
    
    def _rate_limit_wait(self):
        """Ensure we don't exceed rate limits."""
        min_interval = 60.0 / self.rate_limit
        elapsed = time.time() - self.last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()
    
    def get_user_info(self) -> dict:
        """Get user/quota information."""
        self._rate_limit_wait()
        resp = self.session.get(f"{self.base_url}/v2/info/user_info")
        if resp.status_code != 200:
            data = resp.json()
            raise ValueError(f"API Error ({resp.status_code}): {data.get('message', 'Unknown error')}")
        return resp.json()
    
    def get_system_info(self) -> dict:
        """Get system/block information."""
        self._rate_limit_wait()
        resp = self.session.get(f"{self.base_url}/v2/info/system_info")
        if resp.status_code != 200:
            data = resp.json()
            raise ValueError(f"API Error ({resp.status_code}): {data.get('message', 'Unknown error')}")
        return resp.json()
    
    def fetch_metric(
        self,
        endpoint: str,
        data_field: str,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        resolution: str = "d1"
    ) -> pd.DataFrame:
        """
        Fetch metric data from API.
        
        Returns DataFrame with columns: [time, value]
        """
        self._rate_limit_wait()
        
        url = f"{self.base_url}/v2/{endpoint}/{data_field}"
        params = {"resolution": resolution, "output_format": "json"}
        
        if from_time:
            params["from_time"] = from_time
        if to_time:
            params["to_time"] = to_time
        
        logger.debug(f"Fetching {url} with params {params}")
        
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        
        data = resp.json()
        
        if data.get("status") != "success":
            raise ValueError(f"API error: {data.get('error', 'Unknown error')}")
        
        # Parse response data
        raw_data = data.get("data", [])
        
        if not raw_data:
            return pd.DataFrame(columns=["time", "value"])
        
        # Handle both single dict and list of dicts
        if isinstance(raw_data, dict):
            raw_data = [raw_data]
        
        df = pd.DataFrame(raw_data)
        
        # Standardize column names
        # API returns the data_field name as column (e.g., 'price', 'mvrv')
        # Rename it to 'value' for consistency
        if "time" not in df.columns and "t" in df.columns:
            df = df.rename(columns={"t": "time"})
        
        # Find the value column - it's whatever isn't 'time'
        value_cols = [c for c in df.columns if c != "time"]
        if value_cols:
            df = df.rename(columns={value_cols[0]: "value"})
        
        # Parse timestamps
        df["time"] = pd.to_datetime(df["time"], utc=True)
        
        # Sort by time
        df = df.sort_values("time").reset_index(drop=True)
        
        return df[["time", "value"]]


# =============================================================================
# STORAGE
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
        
        # Ensure proper types
        df = df.copy()
        df["time"] = pd.to_datetime(df["time"], utc=True)
        
        # Write with compression
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

class SyncEngine:
    """Orchestrates the sync process."""
    
    def __init__(
        self,
        api: BitcoinLabAPI,
        storage: ParquetStorage,
        metrics: list[MetricConfig],
        state_path: Path
    ):
        self.api = api
        self.storage = storage
        self.metrics = sorted(metrics, key=lambda m: m.priority_order)
        self.state_path = state_path
        self.state = SyncState.load(state_path)
    
    def _save_state(self):
        self.state.save(self.state_path)
    
    def sync_metric(
        self,
        metric: MetricConfig,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None
    ) -> tuple[bool, int, Optional[str]]:
        """
        Sync a single metric.
        
        Returns: (success, rows_added, error_message)
        """
        metric_state = self.state.get_metric_state(metric.name)
        
        # Determine start time for incremental sync
        if from_time is None:
            last_ts = self.storage.get_last_timestamp(metric.name)
            if last_ts:
                # Start from day after last data point
                from_time = (last_ts + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                # No existing data - use default start
                from_time = "2015-01-01"
        
        try:
            logger.info(f"Syncing {metric.name} from {from_time}...")
            
            df = self.api.fetch_metric(
                endpoint=metric.endpoint,
                data_field=metric.data_field,
                from_time=from_time,
                to_time=to_time,
                resolution="d1"
            )
            
            if df.empty:
                logger.info(f"  → No new data for {metric.name}")
                metric_state.status = "ok"
                metric_state.last_sync = datetime.now(timezone.utc).isoformat()
                self.state.set_metric_state(metric.name, metric_state)
                return True, 0, None
            
            # Append to storage
            rows_added = self.storage.append(metric.name, df)
            
            # Update state
            metric_state.last_timestamp = df["time"].max().isoformat()
            metric_state.last_sync = datetime.now(timezone.utc).isoformat()
            metric_state.row_count = self.storage.get_row_count(metric.name)
            metric_state.status = "ok"
            metric_state.error = None
            self.state.set_metric_state(metric.name, metric_state)
            
            logger.info(f"  → Added {rows_added} rows (total: {metric_state.row_count})")
            return True, rows_added, None
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"  → Error syncing {metric.name}: {error_msg}")
            
            metric_state.status = "error"
            metric_state.error = error_msg
            metric_state.last_sync = datetime.now(timezone.utc).isoformat()
            self.state.set_metric_state(metric.name, metric_state)
            
            return False, 0, error_msg
    
    def sync_all(
        self,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        max_errors: int = 5
    ) -> dict:
        """
        Sync all metrics.
        
        Returns summary dict.
        """
        logger.info("=" * 60)
        logger.info("Starting sync...")
        logger.info("=" * 60)
        
        results = {
            "started": datetime.now(timezone.utc).isoformat(),
            "metrics_total": len(self.metrics),
            "metrics_success": 0,
            "metrics_failed": 0,
            "rows_added": 0,
            "errors": []
        }
        
        consecutive_errors = 0
        
        for metric in self.metrics:
            success, rows, error = self.sync_metric(metric, from_time, to_time)
            
            if success:
                results["metrics_success"] += 1
                results["rows_added"] += rows
                consecutive_errors = 0
            else:
                results["metrics_failed"] += 1
                results["errors"].append({"metric": metric.name, "error": error})
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
        logger.info(f"Sync complete: {results['metrics_success']}/{results['metrics_total']} metrics, {results['rows_added']} rows added")
        if results["metrics_failed"] > 0:
            logger.warning(f"  {results['metrics_failed']} metrics failed")
        logger.info("=" * 60)
        
        return results
    
    def backfill(self, start_date: str = "2015-01-01") -> dict:
        """Run full historical backfill."""
        logger.info(f"Running backfill from {start_date}...")
        return self.sync_all(from_time=start_date)
    
    def get_status(self) -> dict:
        """Get current sync status."""
        status = {
            "last_sync": self.state.last_sync,
            "metrics": {}
        }
        
        for metric in self.metrics:
            state = self.state.get_metric_state(metric.name)
            status["metrics"][metric.name] = {
                "priority": metric.priority,
                "status": state.status,
                "last_timestamp": state.last_timestamp,
                "row_count": state.row_count,
                "error": state.error
            }
        
        return status


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def load_config() -> tuple[dict, list[MetricConfig]]:
    """Load configuration from YAML."""
    config_path = CONFIG_DIR / "metrics.yaml"
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    metrics = [
        MetricConfig(**m)
        for m in config.get("metrics", [])
    ]
    
    return config, metrics


def create_engine() -> SyncEngine:
    """Create and configure the sync engine."""
    config, metrics = load_config()
    
    # Get API token from environment or use default
    token = os.environ.get(
        config["api"]["token_env"],
        os.environ.get("BITCOIN_LAB_TOKEN", "")
    )
    
    if not token:
        raise ValueError(
            f"API token not found. Set {config['api']['token_env']} environment variable."
        )
    
    api = BitcoinLabAPI(
        base_url=config["api"]["base_url"],
        token=token,
        rate_limit=config["api"].get("rate_limit_per_minute", 60)
    )
    
    storage = ParquetStorage(RAW_DIR)
    state_path = CONFIG_DIR / "sync_state.json"
    
    return SyncEngine(api, storage, metrics, state_path)


def cmd_sync():
    """Run incremental sync."""
    engine = create_engine()
    return engine.sync_all()


def cmd_backfill(start_date: str = "2015-01-01"):
    """Run full backfill."""
    engine = create_engine()
    return engine.backfill(start_date)


def cmd_status():
    """Show sync status."""
    engine = create_engine()
    status = engine.get_status()
    
    print(f"\nLast sync: {status['last_sync'] or 'Never'}\n")
    print(f"{'Metric':<30} {'Priority':<10} {'Status':<8} {'Rows':>8} {'Last Data':<12}")
    print("-" * 80)
    
    for name, info in status["metrics"].items():
        last_ts = info["last_timestamp"][:10] if info["last_timestamp"] else "N/A"
        print(f"{name:<30} {info['priority']:<10} {info['status']:<8} {info['row_count']:>8} {last_ts:<12}")
    
    return status


def cmd_info():
    """Show API info and quota."""
    config, _ = load_config()
    token = os.environ.get(config["api"]["token_env"], "")
    
    api = BitcoinLabAPI(config["api"]["base_url"], token)
    
    try:
        user_info = api.get_user_info()
        system_info = api.get_system_info()
        
        print("\n=== API Status ===")
        print(f"System: {system_info.get('data', {})}")
        print(f"\n=== User Info ===")
        print(f"User: {user_info.get('data', {})}")
        
    except Exception as e:
        print(f"Error fetching API info: {e}")


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    
    commands = {
        "sync": cmd_sync,
        "backfill": cmd_backfill,
        "status": cmd_status,
        "info": cmd_info,
    }
    
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(__doc__)
        print(f"Available commands: {', '.join(commands.keys())}")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    # Handle backfill with optional start date
    if cmd == "backfill" and len(sys.argv) > 2:
        commands[cmd](sys.argv[2])
    else:
        commands[cmd]()
