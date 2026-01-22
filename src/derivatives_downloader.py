#!/usr/bin/env python3
"""
Free Derivatives Data Downloader
================================
Downloads derivatives data from FREE sources:
- Coinglass (aggregated funding, liquidations, OI)
- Direct exchange APIs (Binance, Bybit, OKX)

This replaces the paid Glassnode derivatives data.

Usage:
    python -m src.derivatives_downloader sync       # Daily sync
    python -m src.derivatives_downloader backfill   # Full backfill
    python -m src.derivatives_downloader status     # Show status
"""

import os
import json
import time
import logging
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests
import pandas as pd

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "derivatives" / "daily"
DATA_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "derivatives_sync.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# API endpoints
COINGLASS_BASE = "https://open-api.coinglass.com/public/v2"
BINANCE_FAPI = "https://fapi.binance.com"
BYBIT_API = "https://api.bybit.com"
OKX_API = "https://www.okx.com"


# =============================================================================
# COINGLASS API (Free tier - no API key needed for public endpoints)
# =============================================================================

class CoinglassClient:
    """Client for Coinglass public API."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; BitcoinDashboard/1.0)'
        })
    
    def _get(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make GET request to Coinglass."""
        url = f"{COINGLASS_BASE}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get('success') or data.get('code') == '0':
                    return data.get('data', data)
            logger.warning(f"Coinglass error: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Coinglass request failed: {e}")
            return None
    
    def get_funding_rates(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get current funding rates across exchanges."""
        # Try the funding rate endpoint
        data = self._get("/funding", params={"symbol": symbol})
        return data
    
    def get_liquidations(self, symbol: str = "BTC", interval: str = "h24") -> Optional[Dict]:
        """Get liquidation data."""
        data = self._get("/liquidation_history", params={
            "symbol": symbol,
            "time_type": interval
        })
        return data
    
    def get_open_interest(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get open interest across exchanges."""
        data = self._get("/open_interest", params={"symbol": symbol})
        return data
    
    def get_long_short_ratio(self, symbol: str = "BTC") -> Optional[Dict]:
        """Get long/short ratio."""
        data = self._get("/long_short", params={"symbol": symbol})
        return data


# =============================================================================
# BINANCE FUTURES API (Free, no auth needed for public endpoints)
# =============================================================================

class BinanceClient:
    """Client for Binance Futures public API."""
    
    def __init__(self):
        self.session = requests.Session()
    
    def _get(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """Make GET request to Binance Futures."""
        url = f"{BINANCE_FAPI}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Binance error: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Binance request failed: {e}")
            return None
    
    def get_funding_rate(self, symbol: str = "BTCUSDT") -> Optional[Dict]:
        """Get current funding rate."""
        data = self._get("/fapi/v1/premiumIndex", params={"symbol": symbol})
        return data
    
    def get_funding_rate_history(
        self, 
        symbol: str = "BTCUSDT",
        limit: int = 100,
        start_time: int = None,
        end_time: int = None
    ) -> Optional[List[Dict]]:
        """Get historical funding rates."""
        params = {"symbol": symbol, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return self._get("/fapi/v1/fundingRate", params=params)
    
    def get_open_interest(self, symbol: str = "BTCUSDT") -> Optional[Dict]:
        """Get current open interest."""
        return self._get("/fapi/v1/openInterest", params={"symbol": symbol})
    
    def get_open_interest_history(
        self,
        symbol: str = "BTCUSDT",
        period: str = "1d",
        limit: int = 30
    ) -> Optional[List[Dict]]:
        """Get historical open interest."""
        return self._get("/futures/data/openInterestHist", params={
            "symbol": symbol,
            "period": period,
            "limit": limit
        })
    
    def get_long_short_ratio(
        self,
        symbol: str = "BTCUSDT",
        period: str = "1d",
        limit: int = 30
    ) -> Optional[List[Dict]]:
        """Get top trader long/short ratio."""
        return self._get("/futures/data/topLongShortAccountRatio", params={
            "symbol": symbol,
            "period": period,
            "limit": limit
        })
    
    def get_taker_volume(
        self,
        symbol: str = "BTCUSDT",
        period: str = "1d",
        limit: int = 30
    ) -> Optional[List[Dict]]:
        """Get taker buy/sell volume."""
        return self._get("/futures/data/takerlongshortRatio", params={
            "symbol": symbol,
            "period": period,
            "limit": limit
        })


# =============================================================================
# BYBIT API (Free, no auth needed for public endpoints)
# =============================================================================

class BybitClient:
    """Client for Bybit public API."""
    
    def __init__(self):
        self.session = requests.Session()
    
    def _get(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """Make GET request to Bybit."""
        url = f"{BYBIT_API}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0:
                    return data.get('result', data)
            logger.warning(f"Bybit error: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Bybit request failed: {e}")
            return None
    
    def get_funding_rate_history(
        self,
        symbol: str = "BTCUSDT",
        category: str = "linear",
        limit: int = 100
    ) -> Optional[Dict]:
        """Get historical funding rates."""
        return self._get("/v5/market/funding/history", params={
            "category": category,
            "symbol": symbol,
            "limit": limit
        })
    
    def get_open_interest(
        self,
        symbol: str = "BTCUSDT",
        category: str = "linear",
        interval: str = "1d",
        limit: int = 30
    ) -> Optional[Dict]:
        """Get historical open interest."""
        return self._get("/v5/market/open-interest", params={
            "category": category,
            "symbol": symbol,
            "intervalTime": interval,
            "limit": limit
        })


# =============================================================================
# AGGREGATED DERIVATIVES DOWNLOADER
# =============================================================================

class DerivativesDownloader:
    """Aggregates derivatives data from multiple free sources."""
    
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize clients
        self.binance = BinanceClient()
        self.bybit = BybitClient()
        self.coinglass = CoinglassClient()
    
    def _save_parquet(self, df: pd.DataFrame, name: str):
        """Save DataFrame to parquet."""
        if df.empty:
            return
        path = self.data_dir / f"{name}.parquet"
        df.to_parquet(path, compression='zstd')
        logger.info(f"Saved {name}: {len(df)} rows")
    
    def _load_parquet(self, name: str) -> pd.DataFrame:
        """Load DataFrame from parquet."""
        path = self.data_dir / f"{name}.parquet"
        if path.exists():
            return pd.read_parquet(path)
        return pd.DataFrame()
    
    def download_funding_rates(self, days: int = 365) -> pd.DataFrame:
        """Download funding rate history from Binance."""
        logger.info("Downloading funding rates from Binance...")
        
        all_data = []
        
        # Binance returns max 1000 records per call, funding every 8h = 3/day
        # So 1000 records ≈ 333 days
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        current_end = end_time
        while current_end > start_time:
            data = self.binance.get_funding_rate_history(
                symbol="BTCUSDT",
                limit=1000,
                end_time=current_end
            )
            
            if not data or len(data) == 0:
                break
            
            all_data.extend(data)
            
            # Move to earlier time
            earliest = min(d['fundingTime'] for d in data)
            current_end = earliest - 1
            
            time.sleep(0.2)  # Rate limit
        
        if not all_data:
            logger.warning("No funding rate data retrieved")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_data)
        df['time'] = pd.to_datetime(df['fundingTime'], unit='ms', utc=True)
        df['value'] = df['fundingRate'].astype(float)
        df = df[['time', 'value']].drop_duplicates(subset=['time'])
        df = df.set_index('time').sort_index()
        
        # Resample to daily (average of 3 daily funding periods)
        df_daily = df.resample('D').mean()
        
        self._save_parquet(df_daily, 'funding_rate')
        return df_daily
    
    def download_open_interest(self, days: int = 30) -> pd.DataFrame:
        """Download open interest history from Binance."""
        logger.info("Downloading open interest from Binance...")
        
        data = self.binance.get_open_interest_history(
            symbol="BTCUSDT",
            period="1d",
            limit=min(days, 30)  # Binance limit
        )
        
        if not data:
            logger.warning("No open interest data retrieved")
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['time'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df['value'] = df['sumOpenInterest'].astype(float)
        df = df[['time', 'value']].set_index('time').sort_index()
        
        self._save_parquet(df, 'open_interest')
        return df
    
    def download_long_short_ratio(self, days: int = 30) -> pd.DataFrame:
        """Download long/short ratio from Binance."""
        logger.info("Downloading long/short ratio from Binance...")
        
        data = self.binance.get_long_short_ratio(
            symbol="BTCUSDT",
            period="1d",
            limit=min(days, 30)
        )
        
        if not data:
            logger.warning("No long/short ratio data retrieved")
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['time'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df['value'] = df['longShortRatio'].astype(float)
        df['long_account'] = df['longAccount'].astype(float)
        df['short_account'] = df['shortAccount'].astype(float)
        df = df[['time', 'value', 'long_account', 'short_account']].set_index('time').sort_index()
        
        self._save_parquet(df, 'long_short_ratio')
        return df
    
    def download_taker_volume(self, days: int = 30) -> pd.DataFrame:
        """Download taker buy/sell volume from Binance."""
        logger.info("Downloading taker volume from Binance...")
        
        data = self.binance.get_taker_volume(
            symbol="BTCUSDT",
            period="1d",
            limit=min(days, 30)
        )
        
        if not data:
            logger.warning("No taker volume data retrieved")
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['time'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df['value'] = df['buySellRatio'].astype(float)  # >1 = more buyers
        df['buy_vol'] = df['buyVol'].astype(float)
        df['sell_vol'] = df['sellVol'].astype(float)
        df = df[['time', 'value', 'buy_vol', 'sell_vol']].set_index('time').sort_index()
        
        self._save_parquet(df, 'taker_volume')
        return df
    
    def get_current_funding(self) -> Dict[str, float]:
        """Get current funding rate from multiple exchanges."""
        results = {}
        
        # Binance
        binance_data = self.binance.get_funding_rate("BTCUSDT")
        if binance_data:
            results['binance'] = float(binance_data.get('lastFundingRate', 0))
        
        # Bybit
        bybit_data = self.bybit.get_funding_rate_history("BTCUSDT", limit=1)
        if bybit_data and bybit_data.get('list'):
            results['bybit'] = float(bybit_data['list'][0].get('fundingRate', 0))
        
        # Calculate average
        if results:
            results['average'] = sum(results.values()) / len(results)
        
        return results
    
    def get_current_oi(self) -> Dict[str, float]:
        """Get current open interest from Binance."""
        data = self.binance.get_open_interest("BTCUSDT")
        if data:
            return {
                'open_interest': float(data.get('openInterest', 0)),
                'time': datetime.now(timezone.utc).isoformat()
            }
        return {}
    
    def download_all(self, days: int = 365) -> Dict[str, pd.DataFrame]:
        """Download all derivatives metrics."""
        results = {}
        
        results['funding_rate'] = self.download_funding_rates(days=days)
        time.sleep(0.5)
        
        results['open_interest'] = self.download_open_interest(days=min(days, 30))
        time.sleep(0.5)
        
        results['long_short_ratio'] = self.download_long_short_ratio(days=min(days, 30))
        time.sleep(0.5)
        
        results['taker_volume'] = self.download_taker_volume(days=min(days, 30))
        
        return results
    
    def get_latest_values(self) -> Dict[str, Any]:
        """Get latest values for all stored metrics."""
        latest = {}
        
        for file_path in self.data_dir.glob("*.parquet"):
            metric_name = file_path.stem
            df = pd.read_parquet(file_path)
            if len(df) > 0:
                latest[metric_name] = {
                    'value': df['value'].iloc[-1],
                    'time': df.index[-1]
                }
        
        return latest
    
    def get_buy_the_dip_status(self) -> Dict[str, Any]:
        """Get derivatives status for Buy-the-Dip signal.
        
        Returns dict compatible with dashboard's get_glassnode_derivatives() format.
        """
        result = {
            'funding_rate': None,
            'funding_rate_negative': False,
            'long_liquidations': None,  # Not available from free APIs
            'short_liquidations': None,  # Not available from free APIs
            'liquidation_ratio': None,
            'long_liq_peak': False,
            'available': False,
            'source': 'binance_free'
        }
        
        # Load funding rate
        funding_df = self._load_parquet('funding_rate')
        if not funding_df.empty:
            latest_funding = funding_df['value'].iloc[-1]
            result['funding_rate'] = latest_funding
            result['funding_rate_negative'] = latest_funding <= 0
            result['available'] = True
        
        # Load long/short ratio (use as proxy for sentiment)
        ls_df = self._load_parquet('long_short_ratio')
        if not ls_df.empty:
            latest_ls = ls_df['value'].iloc[-1]
            result['long_short_ratio'] = latest_ls
            # Ratio < 1 means more shorts than longs (bearish positioning)
        
        # Load taker volume
        taker_df = self._load_parquet('taker_volume')
        if not taker_df.empty:
            latest_taker = taker_df['value'].iloc[-1]
            result['taker_buy_sell_ratio'] = latest_taker
            # Ratio > 1 means more taker buys (bullish)
        
        return result


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Download derivatives data from free sources")
    parser.add_argument("command", choices=["sync", "backfill", "status", "current"],
                       help="Command to run")
    parser.add_argument("--days", type=int, default=365, help="Days of history to fetch")
    
    args = parser.parse_args()
    
    downloader = DerivativesDownloader()
    
    if args.command == "sync":
        logger.info("=" * 50)
        logger.info("SYNCING DERIVATIVES DATA (FREE SOURCES)")
        logger.info("=" * 50)
        
        results = downloader.download_all(days=30)  # Quick sync - last 30 days
        
        logger.info("\nSync complete:")
        for name, df in results.items():
            if not df.empty:
                logger.info(f"  {name}: {len(df)} rows, latest: {df.index[-1]}")
    
    elif args.command == "backfill":
        logger.info("=" * 50)
        logger.info(f"BACKFILLING {args.days} DAYS OF DERIVATIVES DATA")
        logger.info("=" * 50)
        
        results = downloader.download_all(days=args.days)
        
        logger.info("\nBackfill complete:")
        for name, df in results.items():
            if not df.empty:
                logger.info(f"  {name}: {len(df)} rows")
    
    elif args.command == "status":
        logger.info("=" * 50)
        logger.info("DERIVATIVES DATA STATUS")
        logger.info("=" * 50)
        
        latest = downloader.get_latest_values()
        if latest:
            for name, info in latest.items():
                logger.info(f"  {name}: {info['value']:.6f} @ {info['time']}")
        else:
            logger.info("  No cached data. Run 'sync' or 'backfill' first.")
    
    elif args.command == "current":
        logger.info("=" * 50)
        logger.info("CURRENT DERIVATIVES VALUES (LIVE)")
        logger.info("=" * 50)
        
        # Funding rates
        funding = downloader.get_current_funding()
        if funding:
            logger.info("\nFunding Rates:")
            for exchange, rate in funding.items():
                logger.info(f"  {exchange}: {rate:.6f} ({rate*100:.4f}%)")
        
        # Open interest
        oi = downloader.get_current_oi()
        if oi:
            logger.info(f"\nOpen Interest: {oi['open_interest']:,.0f} BTC")
        
        # Buy-the-Dip status
        btd = downloader.get_buy_the_dip_status()
        logger.info(f"\nBuy-the-Dip Status:")
        logger.info(f"  Funding ≤0: {'✓' if btd['funding_rate_negative'] else '✗'} ({btd['funding_rate']:.6f})")


if __name__ == "__main__":
    main()
