#!/usr/bin/env python3
"""
Glassnode Derivatives Downloader
================================
Downloads derivatives data (funding rates, liquidations, open interest) from Glassnode.
This complements on-chain data from Bitcoin Lab / BRK APIs.

Note: Your Glassnode API key must be passed as a header, not query parameter.
API Key: 1vQgbCQeHhEaY0YJAxNY90YB25H
"""

import os
import requests
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import logging
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

GLASSNODE_API_KEY = os.environ.get("GLASSNODE_API_KEY", "1vQgbCQeHhEaY0YJAxNY90YB25H")
GLASSNODE_BASE_URL = "https://api.glassnode.com"

# Data directory
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "glassnode" / "daily"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# DERIVATIVES METRICS REGISTRY
# =============================================================================
# These metrics are NOT available from Bitcoin Lab or BRK APIs

DERIVATIVES_METRICS = {
    # Funding Rates
    "funding_rate": {
        "endpoint": "/v1/metrics/derivatives/futures_funding_rate_perpetual",
        "description": "Perpetual futures funding rate (aggregated)",
        "tier": "professional",
        "priority": "critical",  # Key for Buy-the-Dip strategy
    },
    "funding_rate_all": {
        "endpoint": "/v1/metrics/derivatives/futures_funding_rate_perpetual_all",
        "description": "Funding rate by exchange breakdown",
        "tier": "professional",
        "priority": "medium",
    },
    
    # Liquidations
    "liquidations_long": {
        "endpoint": "/v1/metrics/derivatives/futures_liquidated_volume_long_sum",
        "description": "Total long liquidation volume (BTC)",
        "tier": "professional",
        "priority": "critical",
    },
    "liquidations_short": {
        "endpoint": "/v1/metrics/derivatives/futures_liquidated_volume_short_sum",
        "description": "Total short liquidation volume (BTC)",
        "tier": "professional",
        "priority": "critical",
    },
    "liquidations_total": {
        "endpoint": "/v1/metrics/derivatives/futures_liquidated_total_volume_sum",
        "description": "Total liquidation volume (BTC)",
        "tier": "professional",
        "priority": "high",
    },
    "liquidations_long_relative": {
        "endpoint": "/v1/metrics/derivatives/futures_liquidated_volume_long_relative",
        "description": "Long liquidations relative to total",
        "tier": "professional",
        "priority": "medium",
    },
    
    # Open Interest
    "open_interest": {
        "endpoint": "/v1/metrics/derivatives/futures_open_interest_sum",
        "description": "Total futures open interest",
        "tier": "standard",
        "priority": "high",
    },
    "open_interest_perpetual": {
        "endpoint": "/v1/metrics/derivatives/futures_open_interest_perpetual_sum",
        "description": "Perpetual futures open interest",
        "tier": "standard",
        "priority": "high",
    },
    "estimated_leverage_ratio": {
        "endpoint": "/v1/metrics/derivatives/futures_estimated_leverage_ratio",
        "description": "OI / Exchange Reserve",
        "tier": "professional",
        "priority": "high",
    },
    
    # Futures Volume
    "futures_volume": {
        "endpoint": "/v1/metrics/derivatives/futures_volume_daily_sum",
        "description": "Daily futures trading volume",
        "tier": "standard",
        "priority": "medium",
    },
    "futures_volume_perpetual": {
        "endpoint": "/v1/metrics/derivatives/futures_volume_daily_perpetual_sum",
        "description": "Daily perpetual futures volume",
        "tier": "standard",
        "priority": "medium",
    },
    
    # Basis & Term Structure
    "futures_basis_3m": {
        "endpoint": "/v1/metrics/derivatives/futures_annualized_basis_3m",
        "description": "3-month annualized basis",
        "tier": "standard",
        "priority": "medium",
    },
    
    # Options (bonus)
    "options_volume": {
        "endpoint": "/v1/metrics/derivatives/options_volume_daily_sum",
        "description": "Daily options volume",
        "tier": "professional",
        "priority": "low",
    },
    "options_put_call_ratio": {
        "endpoint": "/v1/metrics/derivatives/options_volume_put_call_ratio",
        "description": "Options put/call ratio",
        "tier": "professional",
        "priority": "medium",
    },
    "options_25delta_skew_1m": {
        "endpoint": "/v1/metrics/derivatives/options_25delta_skew_1_month",
        "description": "1-month 25-delta skew",
        "tier": "professional",
        "priority": "medium",
    },
    "atm_iv_1m": {
        "endpoint": "/v1/metrics/derivatives/options_atm_implied_volatility_1_month",
        "description": "1-month ATM implied volatility",
        "tier": "professional",
        "priority": "medium",
    },
}


# =============================================================================
# API CLIENT
# =============================================================================

class GlassnodeClient:
    """Client for Glassnode API with proper authentication."""
    
    def __init__(self, api_key: str = GLASSNODE_API_KEY):
        self.api_key = api_key
        self.base_url = GLASSNODE_BASE_URL
        self.session = requests.Session()
        self.rate_limit_remaining = 100
        self.rate_limit_reset = None
        
    def _make_request(
        self,
        endpoint: str,
        params: Dict = None,
        max_retries: int = 3
    ) -> Optional[List[Dict]]:
        """Make authenticated request to Glassnode API."""
        
        url = f"{self.base_url}{endpoint}"
        
        # Add API key to params (Glassnode uses query param, not header)
        if params is None:
            params = {}
        params['api_key'] = self.api_key
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                
                # Check rate limits
                if 'X-RateLimit-Remaining' in response.headers:
                    self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
                if 'X-RateLimit-Reset' in response.headers:
                    self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])
                
                if response.status_code == 200:
                    return response.json()
                    
                elif response.status_code == 401:
                    logger.error(f"Authentication failed for {endpoint}. Check API key.")
                    return None
                    
                elif response.status_code == 403:
                    logger.warning(f"Access denied for {endpoint}. May require higher tier.")
                    return None
                    
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = self.rate_limit_reset or 60
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    logger.error(f"API error ({response.status_code}): {endpoint}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout for {endpoint}, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
                
            except Exception as e:
                logger.error(f"Request error for {endpoint}: {e}")
                return None
        
        return None
    
    def fetch_metric(
        self,
        endpoint: str,
        asset: str = "BTC",
        resolution: str = "24h",
        since: Optional[Union[str, datetime]] = None,
        until: Optional[Union[str, datetime]] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch a metric from Glassnode.
        
        Args:
            endpoint: API endpoint path
            asset: Asset symbol (default: BTC)
            resolution: Data resolution (1h, 24h, etc.)
            since: Start date (string or datetime)
            until: End date (string or datetime)
            
        Returns:
            DataFrame with 'time' index and 'value' column
        """
        
        params = {
            'a': asset,
            'i': resolution,
        }
        
        # Convert dates to timestamps
        if since:
            if isinstance(since, str):
                since = pd.Timestamp(since)
            params['s'] = int(since.timestamp())
            
        if until:
            if isinstance(until, str):
                until = pd.Timestamp(until)
            params['u'] = int(until.timestamp())
        
        data = self._make_request(endpoint, params)
        
        if data is None or len(data) == 0:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Handle different response formats
        if 't' in df.columns:
            df['time'] = pd.to_datetime(df['t'], unit='s', utc=True)
            df = df.drop(columns=['t'])
        elif 'timestamp' in df.columns:
            df['time'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
            df = df.drop(columns=['timestamp'])
            
        if 'v' in df.columns:
            df['value'] = df['v']
            df = df.drop(columns=['v'])
        
        # Set time as index
        df = df.set_index('time')
        
        return df


# =============================================================================
# DOWNLOADER
# =============================================================================

class GlassnodeDownloader:
    """Downloads and stores Glassnode derivatives data."""
    
    def __init__(
        self,
        api_key: str = GLASSNODE_API_KEY,
        data_dir: Path = DATA_DIR
    ):
        self.client = GlassnodeClient(api_key)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def download_metric(
        self,
        metric_name: str,
        since: str = "2019-01-01",
        until: Optional[str] = None,
        force: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Download a single metric and save to parquet.
        
        Args:
            metric_name: Key from DERIVATIVES_METRICS
            since: Start date
            until: End date (default: today)
            force: Redownload even if file exists
            
        Returns:
            DataFrame with the metric data
        """
        
        if metric_name not in DERIVATIVES_METRICS:
            logger.error(f"Unknown metric: {metric_name}")
            return None
            
        metric_info = DERIVATIVES_METRICS[metric_name]
        endpoint = metric_info["endpoint"]
        
        # Check if file exists (incremental update)
        file_path = self.data_dir / f"{metric_name}.parquet"
        
        if file_path.exists() and not force:
            # Load existing data and find last date
            existing = pd.read_parquet(file_path)
            if len(existing) > 0:
                last_date = existing.index.max()
                since = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                logger.info(f"Incremental update from {since} for {metric_name}")
        
        # Set default until
        if until is None:
            until = datetime.now().strftime("%Y-%m-%d")
        
        # Skip if we're already up to date
        if pd.Timestamp(since) >= pd.Timestamp(until):
            logger.info(f"{metric_name} already up to date")
            if file_path.exists():
                return pd.read_parquet(file_path)
            return None
        
        logger.info(f"Downloading {metric_name} from {since} to {until}...")
        
        df = self.client.fetch_metric(
            endpoint=endpoint,
            since=since,
            until=until
        )
        
        if df is None or len(df) == 0:
            logger.warning(f"No data returned for {metric_name}")
            if file_path.exists():
                return pd.read_parquet(file_path)
            return None
        
        # Merge with existing data if applicable
        if file_path.exists() and not force:
            existing = pd.read_parquet(file_path)
            df = pd.concat([existing, df])
            df = df[~df.index.duplicated(keep='last')]
            df = df.sort_index()
        
        # Save to parquet
        df.to_parquet(file_path, compression='zstd')
        logger.info(f"Saved {metric_name}: {len(df)} rows")
        
        return df
    
    def download_all(
        self,
        priority: Optional[str] = None,
        since: str = "2019-01-01",
        force: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        Download all derivatives metrics (or filter by priority).
        
        Args:
            priority: Filter by priority level (critical, high, medium, low)
            since: Start date
            force: Force redownload
            
        Returns:
            Dict of metric_name -> DataFrame
        """
        
        results = {}
        
        for name, info in DERIVATIVES_METRICS.items():
            if priority and info["priority"] != priority:
                continue
                
            df = self.download_metric(name, since=since, force=force)
            if df is not None:
                results[name] = df
            
            # Small delay to be nice to API
            time.sleep(0.5)
        
        return results
    
    def download_buy_the_dip_metrics(self, since: str = "2019-01-01") -> Dict[str, pd.DataFrame]:
        """Download metrics specifically needed for Buy-the-Dip strategy."""
        
        critical_metrics = [
            "funding_rate",
            "liquidations_long", 
            "liquidations_short",
            "open_interest",
            "estimated_leverage_ratio"
        ]
        
        results = {}
        for name in critical_metrics:
            df = self.download_metric(name, since=since)
            if df is not None:
                results[name] = df
            time.sleep(0.5)
            
        return results
    
    def load_metric(self, metric_name: str) -> Optional[pd.DataFrame]:
        """Load a metric from local storage."""
        file_path = self.data_dir / f"{metric_name}.parquet"
        if file_path.exists():
            return pd.read_parquet(file_path)
        return None
    
    def get_latest_values(self) -> Dict[str, float]:
        """Get latest values for all stored metrics."""
        latest = {}
        
        for file_path in self.data_dir.glob("*.parquet"):
            metric_name = file_path.stem
            df = pd.read_parquet(file_path)
            if len(df) > 0:
                latest[metric_name] = df['value'].iloc[-1]
                
        return latest


# =============================================================================
# DERIVED METRICS
# =============================================================================

def calculate_liquidation_ratio(
    long_liqs: pd.DataFrame,
    short_liqs: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate Long/Short liquidation ratio.
    
    Ratio > 2.0 indicates heavy long liquidations (potential buy opportunity)
    Ratio < 0.5 indicates heavy short liquidations (caution on longs)
    """
    df = pd.DataFrame({
        'long': long_liqs['value'],
        'short': short_liqs['value']
    })
    
    # Avoid division by zero
    df['short'] = df['short'].replace(0, 0.001)
    df['liquidation_ratio'] = df['long'] / df['short']
    
    return df[['liquidation_ratio']]


def calculate_funding_z_score(
    funding: pd.DataFrame,
    window: int = 30
) -> pd.DataFrame:
    """
    Calculate z-score of funding rate over rolling window.
    
    Z < -1: Significantly negative funding (bearish sentiment)
    Z > 1: Significantly positive funding (euphoria)
    """
    df = funding.copy()
    df['funding_mean'] = df['value'].rolling(window).mean()
    df['funding_std'] = df['value'].rolling(window).std()
    df['funding_z'] = (df['value'] - df['funding_mean']) / df['funding_std']
    
    return df[['funding_z']]


# =============================================================================
# MAIN / CLI
# =============================================================================

def main():
    """CLI for downloading Glassnode derivatives data."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Download Glassnode derivatives data")
    parser.add_argument("--all", action="store_true", help="Download all metrics")
    parser.add_argument("--btd", action="store_true", help="Download Buy-the-Dip metrics only")
    parser.add_argument("--metric", type=str, help="Download specific metric")
    parser.add_argument("--since", type=str, default="2019-01-01", help="Start date")
    parser.add_argument("--force", action="store_true", help="Force redownload")
    parser.add_argument("--list", action="store_true", help="List available metrics")
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable Glassnode Derivatives Metrics:")
        print("=" * 60)
        for name, info in DERIVATIVES_METRICS.items():
            print(f"  {name:<30} [{info['priority']:<8}] {info['description']}")
        return
    
    downloader = GlassnodeDownloader()
    
    if args.all:
        results = downloader.download_all(since=args.since, force=args.force)
        print(f"\nDownloaded {len(results)} metrics")
        
    elif args.btd:
        results = downloader.download_buy_the_dip_metrics(since=args.since)
        print(f"\nDownloaded Buy-the-Dip metrics: {list(results.keys())}")
        
    elif args.metric:
        df = downloader.download_metric(args.metric, since=args.since, force=args.force)
        if df is not None:
            print(f"\n{args.metric}: {len(df)} rows")
            print(df.tail())
    
    else:
        # Default: download critical metrics
        results = downloader.download_all(priority="critical", since=args.since)
        print(f"\nDownloaded critical metrics: {list(results.keys())}")


if __name__ == "__main__":
    main()
