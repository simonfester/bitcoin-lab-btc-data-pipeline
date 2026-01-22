"""
Unified Bitcoin On-Chain Data Loader

Supports multiple data sources with automatic fallback:
1. Local cache (parquet files)
2. BRK API (free, open-source) - PREFERRED
3. Bitcoin Lab API (paid, rate-limited)

Usage:
    from src.data_loader import DataLoader, load_data
    
    # Quick load
    df = load_data(['price', 'sopr', 'mvrv_sth'])
    
    # Full control
    loader = DataLoader()
    df = loader.load(['price', 'sopr_sth', 'sopr_lth', 'mvrv'])
    loader.refresh_cache(source='brk')  # Update cache from FREE API
"""

import pandas as pd
import numpy as np
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union, Tuple
import json
import time
import warnings

warnings.filterwarnings('ignore')


class DataLoader:
    """Unified data loader with multi-source support."""
    
    # Metric name mapping between sources
    # Standard name -> {source: api_name}
    METRIC_MAP = {
        # =====================================================================
        # PRICE & MARKET
        # =====================================================================
        'price': {
            'local': 'price',
            'bitcoin_lab': 'market/price_usd_close',
            'brk': 'price_close'
        },
        'price_200d_sma': {
            'local': 'price_200d_sma',
            'bitcoin_lab': 'indicators/price_200d_sma',
            'brk': 'price_200d_sma'
        },
        
        # =====================================================================
        # SOPR FAMILY (Realized P/L)
        # =====================================================================
        'sopr': {
            'local': 'sopr',
            'bitcoin_lab': 'indicators/sopr',
            'brk': 'sopr'
        },
        'sopr_sth': {
            'local': 'sopr_sth',
            'bitcoin_lab': 'indicators/sopr_less_155',
            'brk': 'sth_sopr'
        },
        'sopr_lth': {
            'local': 'sopr_lth',
            'bitcoin_lab': 'indicators/sopr_more_155',
            'brk': 'lth_sopr'
        },
        'sopr_adjusted': {
            'local': 'sopr_adjusted',
            'bitcoin_lab': 'indicators/sopr_adjusted',
            'brk': 'adjusted_sopr'
        },
        
        # =====================================================================
        # MVRV FAMILY (Unrealized P/L)
        # =====================================================================
        'mvrv': {
            'local': 'mvrv',
            'bitcoin_lab': 'indicators/mvrv',
            'brk': 'mvrv'
        },
        'mvrv_sth': {
            'local': 'mvrv_sth',
            'bitcoin_lab': 'indicators/mvrv_less_155',
            'brk': 'sth_mvrv'
        },
        'mvrv_lth': {
            'local': 'mvrv_lth',
            'bitcoin_lab': 'indicators/mvrv_more_155',
            'brk': 'lth_mvrv'
        },
        'mvrv_z': {
            'local': 'mvrv_z',
            'bitcoin_lab': 'indicators/mvrv_z_score',
            'brk': 'mvrv_zscore'
        },
        
        # =====================================================================
        # NUPL FAMILY (Net Unrealized P/L)
        # =====================================================================
        'nupl': {
            'local': 'nupl',
            'bitcoin_lab': 'indicators/net_unrealized_profit_loss',
            'brk': 'net_unrealized_pnl'  # BRK uses different name
        },
        'nupl_lth': {
            'local': 'nupl_lth',
            'bitcoin_lab': 'indicators/nupl_more_155',
            'brk': 'lth_nupl'
        },
        'nupl_sth': {
            'local': 'nupl_sth',
            'bitcoin_lab': 'indicators/nupl_less_155',
            'brk': 'sth_nupl'
        },
        # Additional unrealized metrics
        'unrealized_profit': {
            'local': 'unrealized_profit',
            'bitcoin_lab': 'indicators/unrealized_profit',
            'brk': 'unrealized_profit'
        },
        'unrealized_loss': {
            'local': 'unrealized_loss',
            'bitcoin_lab': 'indicators/unrealized_loss',
            'brk': 'unrealized_loss'
        },
        
        # =====================================================================
        # REALIZED METRICS (Cost Basis)
        # =====================================================================
        'realized_cap': {
            'local': 'realized_cap',
            'bitcoin_lab': 'indicators/realized_cap',
            'brk': 'realized_cap'
        },
        'realized_price': {
            'local': 'realized_price',
            'bitcoin_lab': 'indicators/realized_price',
            'brk': 'realized_price'
        },
        'realized_price_sth': {
            'local': 'realized_price_sth',
            'bitcoin_lab': 'indicators/realized_price_less_155',
            'brk': 'sth_realized_price'
        },
        'realized_price_lth': {
            'local': 'realized_price_lth',
            'bitcoin_lab': 'indicators/realized_price_more_155',
            'brk': 'lth_realized_price'
        },
        'realized_profit': {
            'local': 'realized_profit',
            'bitcoin_lab': 'indicators/realized_profits_sum',
            'brk': 'realized_profit'
        },
        'realized_loss': {
            'local': 'realized_loss',
            'bitcoin_lab': 'indicators/realized_losses_sum',
            'brk': 'realized_loss'
        },
        'net_realized_pnl': {
            'local': 'net_realized_pnl',
            'bitcoin_lab': 'indicators/net_realized_profit_loss',
            'brk': 'net_realized_pnl'
        },
        
        # =====================================================================
        # SELL-SIDE RISK RATIO (James Check - Volatility/Reversal Prediction)
        # Formula: (Realized Profit + Realized Loss) / Realized Cap
        # High = instability, Low = equilibrium
        # =====================================================================
        'sell_side_risk': {
            'local': 'sell_side_risk',
            'bitcoin_lab': 'indicators/sell_side_risk_ratio',  # May not exist
            'brk': 'sell_side_risk_ratio'
        },
        'sell_side_risk_lth': {
            'local': 'sell_side_risk_lth',
            'bitcoin_lab': 'indicators/sell_side_risk_ratio_lth',  # May not exist
            'brk': 'lth_sell_side_risk_ratio'
        },
        'sell_side_risk_sth': {
            'local': 'sell_side_risk_sth',
            'bitcoin_lab': 'indicators/sell_side_risk_ratio_sth',  # May not exist
            'brk': 'sth_sell_side_risk_ratio'
        },
        
        # =====================================================================
        # SUPPLY METRICS
        # =====================================================================
        'supply_lth': {
            'local': 'supply_lth',
            'bitcoin_lab': 'supply/lth_sum',
            'brk': 'lth_supply'
        },
        'supply_sth': {
            'local': 'supply_sth',
            'bitcoin_lab': 'supply/sth_sum',
            'brk': 'sth_supply'
        },
        'supply_in_profit': {
            'local': 'supply_in_profit',
            'bitcoin_lab': 'indicators/supply_profit_relative',
            'brk': 'supply_in_profit'
        },
        'supply_in_loss': {
            'local': 'supply_in_loss',
            'bitcoin_lab': 'indicators/supply_loss_relative',
            'brk': 'supply_in_loss'
        },
        
        # =====================================================================
        # COINTIME ECONOMICS (James Check Framework)
        # =====================================================================
        'aviv': {
            'local': 'aviv',
            'bitcoin_lab': 'indicators/aviv_ratio',
            'brk': 'active_price_ratio'  # AVIV = Active Value / Investor Value
        },
        'active_price': {
            'local': 'active_price',
            'bitcoin_lab': 'indicators/true_market_mean',
            'brk': 'active_price'
        },
        'vaulted_price': {
            'local': 'vaulted_price',
            'bitcoin_lab': 'indicators/vaulted_price',
            'brk': 'vaulted_price'
        },
        'cointime_price': {
            'local': 'cointime_price',
            'bitcoin_lab': 'cointime_statistics/cointime_price',  # May not exist
            'brk': 'cointime_price'
        },
        'liveliness': {
            'local': 'liveliness',
            'bitcoin_lab': 'indicators/liveliness',
            'brk': 'liveliness'
        },
        'coindays_destroyed': {
            'local': 'coindays_destroyed',
            'bitcoin_lab': 'indicators/cdd',
            'brk': 'coindays_destroyed'
        },
        
        # =====================================================================
        # CAPITALIZATION METRICS
        # =====================================================================
        'investor_cap': {
            'local': 'investor_cap',
            'bitcoin_lab': 'indicators/investor_cap',  # May not exist
            'brk': 'investor_cap'
        },
        'thermo_cap': {
            'local': 'thermo_cap',
            'bitcoin_lab': 'indicators/thermo_cap',  # May not exist
            'brk': 'thermo_cap'
        },
        
        # =====================================================================
        # MINING (8-Metric Framework Component)
        # =====================================================================
        'hashrate': {
            'local': 'hashrate',
            'bitcoin_lab': 'mining/hash_rate_mean',
            'brk': 'hashrate'
        },
        'difficulty': {
            'local': 'difficulty',
            'bitcoin_lab': 'mining/difficulty_latest',
            'brk': 'difficulty'
        },
        'puell_multiple': {
            'local': 'puell_multiple',
            'bitcoin_lab': 'indicators/puell_multiple',
            'brk': 'puell_multiple'
        },
        
        # =====================================================================
        # EXCHANGE
        # =====================================================================
        'exchange_balance': {
            'local': 'exchange_balance',
            'bitcoin_lab': 'distribution/balance_exchanges',
            'brk': 'exchange_balance'
        },
        
        # =====================================================================
        # TECHNICAL INDICATORS (8-Metric Framework)
        # =====================================================================
        'mayer_multiple': {
            'local': 'mayer_multiple',
            'bitcoin_lab': 'indicators/mayer_multiple',
            'brk': 'mayer_multiple'  # May not exist - calculate from price/200d_sma
        },
    }
    
    # Aliases for common metric names
    ALIASES = {
        'sth_sopr': 'sopr_sth',
        'lth_sopr': 'sopr_lth',
        'sth_mvrv': 'mvrv_sth',
        'lth_mvrv': 'mvrv_lth',
        'lth_nupl': 'nupl_lth',
        'sth_nupl': 'nupl_sth',
        'true_market_mean': 'active_price',
        'sellside_risk': 'sell_side_risk',
        'sell_side_risk_ratio': 'sell_side_risk',
    }
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        bitcoin_lab_token: Optional[str] = None,
        preferred_source: str = 'auto',
        verbose: bool = True
    ):
        """
        Initialize the data loader.
        
        Args:
            cache_dir: Directory for local cache (default: ~/Documents/bitcoin-lab-btc-data-pipeline/data/cache)
            bitcoin_lab_token: Bitcoin Lab API token (optional)
            preferred_source: 'auto', 'local', 'bitcoin_lab', 'brk'
            verbose: Print status messages
        """
        self.cache_dir = cache_dir or Path.home() / "Documents" / "bitcoin-lab-btc-data-pipeline" / "data" / "cache"
        self.bitcoin_lab_token = bitcoin_lab_token or "ae92658e-373f-4fce-a5b3-1cfc1ffb4da6"
        self.preferred_source = preferred_source
        self.verbose = verbose
        
        # API endpoints
        self.bitcoin_lab_base = "https://api.researchbitcoin.net/v2"
        self.brk_base = "https://next.bitview.space"
        
        # BRK date epoch (day 0 = 2008-01-03)
        self.brk_epoch = pd.Timestamp('2008-01-03')
        
        # Ensure cache dir exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def log(self, msg: str):
        """Print if verbose mode enabled."""
        if self.verbose:
            print(msg)
    
    def _resolve_alias(self, metric: str) -> str:
        """Resolve metric alias to standard name."""
        return self.ALIASES.get(metric, metric)
    
    def load(
        self,
        metrics: Union[str, List[str]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        source: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load one or more metrics into a DataFrame.
        
        Args:
            metrics: Single metric name or list of metric names
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            source: Override preferred source ('local', 'bitcoin_lab', 'brk')
            
        Returns:
            DataFrame with date index and metric columns
        """
        if isinstance(metrics, str):
            metrics = [metrics]
        
        # Resolve aliases
        metrics = [self._resolve_alias(m) for m in metrics]
        
        source = source or self.preferred_source
        
        dfs = []
        for metric in metrics:
            df = self._load_single(metric, start_date, end_date, source)
            if df is not None and not df.empty:
                df = df.rename(columns={'value': metric})
                dfs.append(df)
        
        if not dfs:
            self.log("Warning: No data loaded")
            return pd.DataFrame()
        
        # Merge all metrics
        result = dfs[0]
        for df in dfs[1:]:
            result = result.join(df, how='outer')
        
        # Filter date range
        if start_date:
            result = result[result.index >= pd.Timestamp(start_date)]
        if end_date:
            result = result[result.index <= pd.Timestamp(end_date)]
        
        return result
    
    def _load_single(
        self,
        metric: str,
        start_date: Optional[str],
        end_date: Optional[str],
        source: str
    ) -> Optional[pd.DataFrame]:
        """Load a single metric from the best available source."""
        
        if source == 'auto':
            # Try sources in order: local -> brk -> bitcoin_lab
            sources = ['local', 'brk', 'bitcoin_lab']
        else:
            sources = [source]
        
        for src in sources:
            try:
                if src == 'local':
                    df = self._load_local(metric)
                elif src == 'brk':
                    df = self._load_brk(metric)
                elif src == 'bitcoin_lab':
                    df = self._load_bitcoin_lab(metric)
                else:
                    continue
                
                if df is not None and not df.empty:
                    self.log(f"  ✓ {metric} loaded from {src}")
                    return df
                    
            except Exception as e:
                if self.verbose:
                    self.log(f"  ✗ {metric} failed from {src}: {str(e)[:50]}")
                continue
        
        self.log(f"  ✗ {metric}: No source available")
        return None
    
    def _load_local(self, metric: str) -> Optional[pd.DataFrame]:
        """Load metric from local parquet cache."""
        local_name = self.METRIC_MAP.get(metric, {}).get('local', metric)
        path = self.cache_dir / f"{local_name}.parquet"
        
        if not path.exists():
            return None
        
        df = pd.read_parquet(path)
        
        # Standardize format
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            if hasattr(df['time'].dt, 'tz') and df['time'].dt.tz is not None:
                df['time'] = df['time'].dt.tz_localize(None)
            df = df.set_index('time')
        
        if 'value' not in df.columns and len(df.columns) == 1:
            df = df.rename(columns={df.columns[0]: 'value'})
        
        return df[['value']].sort_index()
    
    def _load_brk(self, metric: str) -> Optional[pd.DataFrame]:
        """Load metric from BRK API (free, no auth)."""
        brk_name = self.METRIC_MAP.get(metric, {}).get('brk', metric)
        
        url = f"{self.brk_base}/api/metric/{brk_name}/dateindex"
        
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if not data.get('data'):
            return None
        
        # Convert BRK format to DataFrame
        values = data['data']
        start_idx = data.get('start', 0)
        
        dates = [self.brk_epoch + timedelta(days=start_idx + i) for i in range(len(values))]
        
        df = pd.DataFrame({
            'value': values
        }, index=pd.DatetimeIndex(dates, name='time'))
        
        # Remove null/None values
        df = df.dropna()
        
        return df
    
    def _load_bitcoin_lab(self, metric: str) -> Optional[pd.DataFrame]:
        """Load metric from Bitcoin Lab API (paid, rate-limited)."""
        bl_name = self.METRIC_MAP.get(metric, {}).get('bitcoin_lab', metric)
        
        url = f"{self.bitcoin_lab_base}/{bl_name}"
        headers = {"Authorization": f"Bearer {self.bitcoin_lab_token}"}
        params = {"a": "BTC", "i": "24h"}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if not data:
            return None
        
        # Convert Bitcoin Lab format to DataFrame
        df = pd.DataFrame(data)
        
        if 't' in df.columns:
            df['time'] = pd.to_datetime(df['t'], unit='s')
            df = df.set_index('time')
            df = df.rename(columns={'v': 'value'})
        elif 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
        
        if 'value' not in df.columns and 'v' in df.columns:
            df = df.rename(columns={'v': 'value'})
        
        return df[['value']].sort_index()
    
    def save_to_cache(self, df: pd.DataFrame, metric: str):
        """Save a DataFrame to local cache."""
        local_name = self.METRIC_MAP.get(metric, {}).get('local', metric)
        path = self.cache_dir / f"{local_name}.parquet"
        
        # Reset index for parquet storage
        df_save = df.reset_index()
        if 'index' in df_save.columns:
            df_save = df_save.rename(columns={'index': 'time'})
        
        df_save.to_parquet(path, index=False)
        self.log(f"  💾 Saved {metric} to cache")
    
    def refresh_cache(self, metrics: Optional[List[str]] = None, source: str = 'brk'):
        """
        Refresh local cache from remote source.
        
        Args:
            metrics: List of metrics to refresh (default: all mapped metrics)
            source: Source to fetch from ('brk' or 'bitcoin_lab')
        """
        if metrics is None:
            metrics = list(self.METRIC_MAP.keys())
        
        self.log(f"Refreshing cache for {len(metrics)} metrics from {source}...")
        
        success, failed = 0, 0
        for metric in metrics:
            try:
                if source == 'brk':
                    df = self._load_brk(metric)
                else:
                    df = self._load_bitcoin_lab(metric)
                
                if df is not None and not df.empty:
                    self.save_to_cache(df, metric)
                    success += 1
                else:
                    failed += 1
                    self.log(f"  ✗ {metric}: No data returned")
                    
            except Exception as e:
                failed += 1
                self.log(f"  ✗ {metric}: {str(e)[:50]}")
        
        self.log(f"\n✅ Refresh complete: {success} success, {failed} failed")
    
    def get_available_metrics(self) -> List[str]:
        """Get list of all mapped metrics."""
        return list(self.METRIC_MAP.keys())
    
    def check_data_freshness(self) -> pd.DataFrame:
        """Check how fresh each cached metric is."""
        results = []
        
        for metric in self.METRIC_MAP.keys():
            local_name = self.METRIC_MAP[metric].get('local', metric)
            path = self.cache_dir / f"{local_name}.parquet"
            
            if path.exists():
                try:
                    df = pd.read_parquet(path)
                    if 'time' in df.columns:
                        latest = pd.to_datetime(df['time']).max()
                    else:
                        latest = df.index.max()
                    
                    age_days = (datetime.now() - latest).days
                    results.append({
                        'metric': metric,
                        'latest_date': latest.date(),
                        'age_days': age_days,
                        'status': '✓' if age_days <= 1 else '⚠' if age_days <= 7 else '✗'
                    })
                except:
                    results.append({
                        'metric': metric,
                        'latest_date': None,
                        'age_days': None,
                        'status': '✗'
                    })
            else:
                results.append({
                    'metric': metric,
                    'latest_date': None,
                    'age_days': None,
                    'status': '✗ (missing)'
                })
        
        return pd.DataFrame(results)


# ============================================================================
# STRATEGY SIGNAL CHECKER
# ============================================================================

class StrategySignalChecker:
    """Check current signals for trading strategies."""
    
    # Checkmate signal configuration
    CHECKMATE_CONFIG = {
        'mvrv': {'weight': 0.30, 'bullish': 1.0, 'bearish': 2.4},
        'mvrv_sth': {'weight': 0.15, 'bullish': 1.0, 'bearish': 1.4},
        'mvrv_lth': {'weight': 0.15, 'bullish': 1.5, 'bearish': 3.5},
        'nupl_lth': {'weight': 0.20, 'bullish': 0.25, 'bearish': 0.6},
        'aviv': {'weight': 0.10, 'bullish': 1.0, 'bearish': 1.5},
    }
    
    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader(verbose=False)
    
    def _score_metric(self, value: float, bullish: float, bearish: float) -> float:
        """Score a metric value on the Checkmate scale."""
        if pd.isna(value):
            return 0
        midpoint = (bullish + bearish) / 2
        if value <= bullish:
            return -1 - (bullish - value) / bullish
        elif value <= midpoint:
            return -1 + (value - bullish) / (midpoint - bullish)
        elif value <= bearish:
            return (value - midpoint) / (bearish - midpoint)
        else:
            return 1 + min((value - bearish) / bearish, 1)
    
    def calc_checkmate_signal(self, row: pd.Series) -> float:
        """Calculate composite Checkmate signal."""
        total_score, total_weight = 0, 0
        for metric, cfg in self.CHECKMATE_CONFIG.items():
            if metric in row and pd.notna(row[metric]):
                score = self._score_metric(row[metric], cfg['bullish'], cfg['bearish'])
                total_score += score * cfg['weight']
                total_weight += cfg['weight']
        return total_score / total_weight if total_weight > 0 else 0
    
    def sizing_stepped_v2(self, signal: float) -> float:
        """STRAT-003 v3 position sizing based on Checkmate signal."""
        if signal <= -1.5:   return 1.00
        elif signal <= -1.0: return 0.90
        elif signal <= -0.5: return 0.75
        elif signal <= 0.0:  return 0.50
        elif signal <= 0.5:  return 0.35
        else:                return 0.20
    
    def check_signals(self, source: str = 'brk') -> Dict:
        """
        Check current strategy signals.
        
        Returns dict with:
            - current_state: Latest metric values
            - strat003: STRAT-003 entry/exit signals
            - checkmate: Checkmate signal and recommended size
        """
        # Load required metrics
        metrics = ['price', 'sopr_sth', 'sopr_lth', 'mvrv', 'mvrv_sth', 'mvrv_lth', 'nupl_lth', 'aviv']
        df = self.loader.load(metrics, source=source)
        
        if df.empty:
            return {'error': 'No data loaded'}
        
        # Get latest row
        latest = df.iloc[-1]
        date = latest.name
        
        # Calculate Checkmate signal
        checkmate = self.calc_checkmate_signal(latest)
        size = self.sizing_stepped_v2(checkmate)
        
        # STRAT-003 signals
        entry_signal = latest.get('sopr_sth', 1) < 1.0
        exit_trigger = (latest.get('mvrv', 0) > 2.5) and (latest.get('sopr_lth', 0) > 1.5)
        
        return {
            'date': date.date() if hasattr(date, 'date') else date,
            'current_state': {
                'price': latest.get('price', None),
                'sopr_sth': latest.get('sopr_sth', None),
                'sopr_lth': latest.get('sopr_lth', None),
                'mvrv': latest.get('mvrv', None),
                'mvrv_sth': latest.get('mvrv_sth', None),
                'mvrv_lth': latest.get('mvrv_lth', None),
            },
            'strat003': {
                'entry_signal': entry_signal,
                'exit_trigger': exit_trigger,
                'description': 'STH-SOPR < 1' if entry_signal else 'No entry signal'
            },
            'checkmate': {
                'signal': checkmate,
                'interpretation': self._interpret_signal(checkmate),
                'recommended_size': size,
            }
        }
    
    def _interpret_signal(self, signal: float) -> str:
        """Interpret Checkmate signal value."""
        if signal <= -1.5: return 'Very Bullish 🟢🟢'
        elif signal <= -1.0: return 'Bullish 🟢'
        elif signal <= -0.5: return 'Slightly Bullish'
        elif signal <= 0.0: return 'Neutral-Bullish'
        elif signal <= 0.5: return 'Neutral-Bearish'
        elif signal <= 1.0: return 'Bearish 🟡'
        else: return 'Very Bearish 🔴'
    
    def print_signals(self, source: str = 'brk'):
        """Print formatted signal report."""
        signals = self.check_signals(source)
        
        if 'error' in signals:
            print(f"Error: {signals['error']}")
            return
        
        print("=" * 60)
        print("CURRENT STRATEGY SIGNALS")
        print("=" * 60)
        print(f"Date: {signals['date']}")
        
        state = signals['current_state']
        print(f"\n📊 Current State:")
        print(f"   Price: ${state['price']:,.0f}" if state['price'] else "   Price: N/A")
        print(f"   STH-SOPR: {state['sopr_sth']:.4f}" if state['sopr_sth'] else "   STH-SOPR: N/A")
        print(f"   LTH-SOPR: {state['sopr_lth']:.4f}" if state['sopr_lth'] else "   LTH-SOPR: N/A")
        print(f"   MVRV: {state['mvrv']:.3f}" if state['mvrv'] else "   MVRV: N/A")
        print(f"   STH-MVRV: {state['mvrv_sth']:.3f}" if state['mvrv_sth'] else "   STH-MVRV: N/A")
        
        strat = signals['strat003']
        print(f"\n📈 STRAT-003:")
        print(f"   Entry Signal: {'🟢 YES' if strat['entry_signal'] else '⚪ No'}")
        print(f"   Exit Trigger: {'🔴 ACTIVE' if strat['exit_trigger'] else '⚪ Not active'}")
        
        cm = signals['checkmate']
        print(f"\n🎯 Checkmate Signal:")
        print(f"   Signal: {cm['signal']:+.2f}")
        print(f"   Interpretation: {cm['interpretation']}")
        print(f"   Recommended Size: {cm['recommended_size']:.0%}")
        
        print("=" * 60)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def load_data(
    metrics: Union[str, List[str]],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    source: str = 'auto'
) -> pd.DataFrame:
    """
    Quick function to load metrics.
    
    Usage:
        df = load_data(['price', 'sopr', 'mvrv'])
        df = load_data('sopr_sth', start_date='2020-01-01')
    """
    loader = DataLoader(verbose=False)
    return loader.load(metrics, start_date, end_date, source)


def check_signals(source: str = 'brk') -> Dict:
    """Quick function to check current strategy signals."""
    checker = StrategySignalChecker()
    return checker.check_signals(source)


def print_signals(source: str = 'brk'):
    """Print current strategy signals."""
    checker = StrategySignalChecker()
    checker.print_signals(source)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Unified Data Loader")
        print("=" * 40)
        print("\nUsage:")
        print("  python data_loader.py status     - Show cache status")
        print("  python data_loader.py refresh    - Refresh cache from BRK")
        print("  python data_loader.py signals    - Check strategy signals")
        print("  python data_loader.py load M1,M2 - Load specific metrics")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        loader = DataLoader()
        print("=" * 60)
        print("DATA CACHE STATUS")
        print("=" * 60)
        freshness = loader.check_data_freshness()
        print(freshness.to_string(index=False))
    
    elif cmd == "refresh":
        loader = DataLoader()
        print("=" * 60)
        print("REFRESHING CACHE FROM BRK (FREE)")
        print("=" * 60)
        loader.refresh_cache(source='brk')
    
    elif cmd == "signals":
        print_signals('brk')
    
    elif cmd == "load":
        if len(sys.argv) < 3:
            print("Usage: python data_loader.py load price,sopr,mvrv")
            sys.exit(1)
        metrics = sys.argv[2].split(',')
        loader = DataLoader()
        df = loader.load(metrics, source='brk')
        print(f"\nLoaded {len(df)} rows")
        print(f"Date range: {df.index.min().date()} to {df.index.max().date()}")
        print(f"\nLatest values:")
        print(df.tail(5).to_string())
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
