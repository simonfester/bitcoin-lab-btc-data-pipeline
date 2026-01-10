"""
Signal Screener Module
======================
Screens on-chain metrics for threshold-based signals with predictive power.

Usage:
    from src.screener import SignalScreener
    
    screener = SignalScreener()
    
    # Run full screen
    results = screener.screen(df)
    
    # Get top signals
    screener.top_bullish(results, n=10)
    screener.top_bearish(results, n=10)
    screener.top_win_rate(results, n=10)
    
    # Check current signals
    signals = screener.current_signals(df)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"

# Default metrics to screen
DEFAULT_METRICS = [
    'mvrv', 'mvrv_z', 'mvrv_lth', 'mvrv_sth',
    'nupl', 'nupl_lth', 'nupl_sth',
    'sopr', 'sopr_lth', 'sopr_sth',
    'nvt', 'supply_in_profit_percent', 
    'supply_lth_sth_ratio',
    'liveliness', 'vaultedness', 
    'coindays_destroyed', 'velocity'
]

# Default percentile thresholds to test
DEFAULT_PERCENTILES = [5, 10, 20, 80, 90, 95]

# Forward return periods to test
DEFAULT_FORWARD_DAYS = [7, 14, 30, 60, 90]


# =============================================================================
# REGIME CONFIG (embedded for standalone use)
# =============================================================================

REGIMES_CONFIG = [
    {"name": "2015 Bear Bottom", "type": "bear", "start": "2015-01-01", "end": "2015-10-01"},
    {"name": "2015-2017 Bull Run", "type": "bull", "start": "2015-10-01", "end": "2017-12-17"},
    {"name": "2018 Bear Market", "type": "bear", "start": "2017-12-17", "end": "2018-12-15"},
    {"name": "2019 Recovery", "type": "bull", "start": "2018-12-15", "end": "2019-06-26"},
    {"name": "2019 Correction", "type": "bear", "start": "2019-06-26", "end": "2020-03-13"},
    {"name": "2020-2021 Bull Run", "type": "bull", "start": "2020-03-13", "end": "2021-11-10"},
    {"name": "2022 Bear Market", "type": "bear", "start": "2021-11-10", "end": "2022-11-21"},
    {"name": "2023-2024 Recovery", "type": "bull", "start": "2022-11-21", "end": "2024-03-14"},
    {"name": "2024 Consolidation", "type": "bear", "start": "2024-03-14", "end": "2024-09-01"},
    {"name": "2024-Present Bull", "type": "bull", "start": "2024-09-01", "end": "2026-12-31"},
]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Signal:
    """A single signal definition."""
    metric: str
    direction: str      # "above" or "below"
    threshold: float
    percentile: int
    regime: str         # "bull", "bear", or "all"
    
    @property
    def condition(self) -> str:
        """Human-readable condition."""
        symbol = ">" if self.direction == "above" else "<"
        return f"{self.metric} {symbol} {self.threshold:.3f}"
    
    @property
    def key(self) -> str:
        """Unique identifier."""
        return f"{self.metric}_{self.direction}_{self.percentile}_{self.regime}"


@dataclass
class SignalResult:
    """Results from testing a signal."""
    signal: Signal
    n_signals: int
    avg_return_7d: float
    avg_return_14d: float
    avg_return_30d: float
    avg_return_60d: float
    avg_return_90d: float
    win_rate_30d: float
    median_return_30d: float
    std_return_30d: float
    
    @property
    def sharpe_30d(self) -> float:
        """Simple Sharpe-like ratio for 30d returns."""
        if self.std_return_30d == 0:
            return 0.0
        return self.avg_return_30d / self.std_return_30d


# =============================================================================
# SIGNAL SCREENER CLASS
# =============================================================================

class SignalScreener:
    """
    Screen metrics for threshold-based signals with predictive power.
    """
    
    def __init__(
        self,
        metrics: Optional[List[str]] = None,
        percentiles: Optional[List[int]] = None,
        forward_days: Optional[List[int]] = None,
        min_signals: int = 20
    ):
        """
        Initialize screener.
        
        Args:
            metrics: List of metrics to screen (default: DEFAULT_METRICS)
            percentiles: Percentile thresholds to test (default: [5, 10, 20, 80, 90, 95])
            forward_days: Forward return periods (default: [7, 14, 30, 60, 90])
            min_signals: Minimum signal count to include in results
        """
        self.metrics = metrics or DEFAULT_METRICS
        self.percentiles = percentiles or DEFAULT_PERCENTILES
        self.forward_days = forward_days or DEFAULT_FORWARD_DAYS
        self.min_signals = min_signals
    
    # -------------------------------------------------------------------------
    # DATA PREPARATION
    # -------------------------------------------------------------------------
    
    def _add_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add regime column based on configured periods."""
        if 'regime' in df.columns:
            return df
        
        df = df.copy()
        df['regime'] = 'undefined'
        
        for r in REGIMES_CONFIG:
            start = pd.Timestamp(r["start"], tz="UTC")
            end = pd.Timestamp(r["end"], tz="UTC")
            mask = (df.index >= start) & (df.index < end)
            df.loc[mask, 'regime'] = r["type"]
        
        return df
    
    def _add_forward_returns(self, df: pd.DataFrame, price_col: str = "price") -> pd.DataFrame:
        """Add forward return columns."""
        df = df.copy()
        
        for days in self.forward_days:
            col = f'fwd_{days}d'
            if col not in df.columns:
                df[col] = df[price_col].pct_change(days).shift(-days)
        
        return df
    
    def prepare_data(self, df: pd.DataFrame, price_col: str = "price") -> pd.DataFrame:
        """Prepare DataFrame with regime and forward returns."""
        df = self._add_regime(df)
        df = self._add_forward_returns(df, price_col)
        return df
    
    # -------------------------------------------------------------------------
    # SCREENING
    # -------------------------------------------------------------------------
    
    def _test_signal(
        self,
        df: pd.DataFrame,
        metric: str,
        percentile: int,
        regime: str
    ) -> Optional[SignalResult]:
        """Test a single signal configuration."""
        
        if metric not in df.columns:
            return None
        
        # Determine threshold and direction
        threshold = df[metric].quantile(percentile / 100)
        
        if percentile >= 80:
            direction = "above"
            signal_mask = df[metric] > threshold
        else:
            direction = "below"
            signal_mask = df[metric] < threshold
        
        # Apply regime filter
        if regime != "all":
            signal_mask = signal_mask & (df['regime'] == regime)
        
        n_signals = signal_mask.sum()
        if n_signals < self.min_signals:
            return None
        
        # Calculate returns
        signal_data = df.loc[signal_mask]
        
        returns = {}
        for days in self.forward_days:
            col = f'fwd_{days}d'
            if col in signal_data.columns:
                returns[days] = signal_data[col].dropna()
        
        if 30 not in returns or len(returns[30]) == 0:
            return None
        
        signal = Signal(
            metric=metric,
            direction=direction,
            threshold=threshold,
            percentile=percentile,
            regime=regime
        )
        
        return SignalResult(
            signal=signal,
            n_signals=n_signals,
            avg_return_7d=returns.get(7, pd.Series()).mean() * 100 if 7 in returns else np.nan,
            avg_return_14d=returns.get(14, pd.Series()).mean() * 100 if 14 in returns else np.nan,
            avg_return_30d=returns[30].mean() * 100,
            avg_return_60d=returns.get(60, pd.Series()).mean() * 100 if 60 in returns else np.nan,
            avg_return_90d=returns.get(90, pd.Series()).mean() * 100 if 90 in returns else np.nan,
            win_rate_30d=(returns[30] > 0).mean() * 100,
            median_return_30d=returns[30].median() * 100,
            std_return_30d=returns[30].std() * 100
        )
    
    def screen(
        self,
        df: pd.DataFrame,
        price_col: str = "price",
        regimes: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Run full signal screen.
        
        Args:
            df: DataFrame with metric data
            price_col: Price column name
            regimes: Regimes to test (default: ["bull", "bear"])
            
        Returns:
            DataFrame with all signal results
        """
        df = self.prepare_data(df, price_col)
        regimes = regimes or ["bull", "bear"]
        
        results = []
        
        for metric in self.metrics:
            for percentile in self.percentiles:
                for regime in regimes:
                    result = self._test_signal(df, metric, percentile, regime)
                    if result is not None:
                        results.append({
                            'metric': result.signal.metric,
                            'direction': result.signal.direction,
                            'percentile': result.signal.percentile,
                            'threshold': result.signal.threshold,
                            'regime': result.signal.regime,
                            'condition': result.signal.condition,
                            'n_signals': result.n_signals,
                            'fwd_7d': result.avg_return_7d,
                            'fwd_14d': result.avg_return_14d,
                            'fwd_30d': result.avg_return_30d,
                            'fwd_60d': result.avg_return_60d,
                            'fwd_90d': result.avg_return_90d,
                            'win_rate': result.win_rate_30d,
                            'median_30d': result.median_return_30d,
                            'std_30d': result.std_return_30d,
                            'sharpe_30d': result.sharpe_30d,
                        })
        
        return pd.DataFrame(results)
    
    # -------------------------------------------------------------------------
    # FILTERING & RANKING
    # -------------------------------------------------------------------------
    
    def top_bullish(
        self,
        results: pd.DataFrame,
        n: int = 10,
        min_win_rate: float = 50.0
    ) -> pd.DataFrame:
        """Get top bullish signals (highest positive returns)."""
        filtered = results[
            (results['fwd_30d'] > 0) & 
            (results['win_rate'] >= min_win_rate)
        ]
        return filtered.nlargest(n, 'fwd_30d')
    
    def top_bearish(
        self,
        results: pd.DataFrame,
        n: int = 10,
        max_win_rate: float = 50.0
    ) -> pd.DataFrame:
        """Get top bearish signals (lowest negative returns)."""
        filtered = results[
            (results['fwd_30d'] < 0) & 
            (results['win_rate'] <= max_win_rate)
        ]
        return filtered.nsmallest(n, 'fwd_30d')
    
    def top_win_rate(
        self,
        results: pd.DataFrame,
        n: int = 10,
        min_signals: int = 50
    ) -> pd.DataFrame:
        """Get signals with highest win rate."""
        filtered = results[results['n_signals'] >= min_signals]
        return filtered.nlargest(n, 'win_rate')
    
    def top_sharpe(
        self,
        results: pd.DataFrame,
        n: int = 10,
        min_signals: int = 50
    ) -> pd.DataFrame:
        """Get signals with best risk-adjusted returns."""
        filtered = results[results['n_signals'] >= min_signals]
        return filtered.nlargest(n, 'sharpe_30d')
    
    def filter_regime(
        self,
        results: pd.DataFrame,
        regime: str
    ) -> pd.DataFrame:
        """Filter results by regime."""
        return results[results['regime'] == regime]
    
    # -------------------------------------------------------------------------
    # CURRENT SIGNALS
    # -------------------------------------------------------------------------
    
    def current_signals(
        self,
        df: pd.DataFrame,
        results: Optional[pd.DataFrame] = None,
        top_n: int = 20
    ) -> pd.DataFrame:
        """
        Check which signals are currently active.
        
        Args:
            df: DataFrame with current metric values
            results: Pre-computed screen results (will compute if None)
            top_n: Consider only top N signals by absolute return
            
        Returns:
            DataFrame of currently active signals
        """
        if results is None:
            results = self.screen(df)
        
        # Get current regime
        df = self._add_regime(df)
        current_regime = df['regime'].iloc[-1]
        
        # Filter to current regime
        regime_results = results[results['regime'] == current_regime]
        
        # Get top signals by absolute return
        regime_results = regime_results.copy()
        regime_results['abs_return'] = regime_results['fwd_30d'].abs()
        top_signals = regime_results.nlargest(top_n * 2, 'abs_return')
        
        # Check which are active
        active = []
        latest = df.iloc[-1]
        
        for _, row in top_signals.iterrows():
            metric = row['metric']
            if metric not in df.columns:
                continue
            
            current_val = latest[metric]
            threshold = row['threshold']
            direction = row['direction']
            
            is_active = (
                (direction == "above" and current_val > threshold) or
                (direction == "below" and current_val < threshold)
            )
            
            if is_active:
                active.append({
                    **row.to_dict(),
                    'current_value': current_val,
                    'current_percentile': (df[metric] < current_val).mean() * 100
                })
        
        return pd.DataFrame(active)
    
    # -------------------------------------------------------------------------
    # REPORTING
    # -------------------------------------------------------------------------
    
    def summary(self, results: pd.DataFrame) -> str:
        """Generate text summary of screening results."""
        lines = []
        lines.append("=" * 80)
        lines.append("SIGNAL SCREENER SUMMARY")
        lines.append("=" * 80)
        
        lines.append(f"\nTotal signals tested: {len(results)}")
        lines.append(f"Metrics: {results['metric'].nunique()}")
        lines.append(f"Regimes: {results['regime'].unique().tolist()}")
        
        # Top bullish
        lines.append("\n" + "-" * 40)
        lines.append("TOP BULLISH SIGNALS")
        lines.append("-" * 40)
        bullish = self.top_bullish(results, n=5)
        for _, row in bullish.iterrows():
            lines.append(
                f"  {row['condition']:<35} {row['regime']:<5} "
                f"+{row['fwd_30d']:.1f}% (win {row['win_rate']:.0f}%)"
            )
        
        # Top bearish
        lines.append("\n" + "-" * 40)
        lines.append("TOP BEARISH SIGNALS")
        lines.append("-" * 40)
        bearish = self.top_bearish(results, n=5)
        for _, row in bearish.iterrows():
            lines.append(
                f"  {row['condition']:<35} {row['regime']:<5} "
                f"{row['fwd_30d']:.1f}% (win {row['win_rate']:.0f}%)"
            )
        
        # Highest win rate
        lines.append("\n" + "-" * 40)
        lines.append("HIGHEST WIN RATE")
        lines.append("-" * 40)
        win_rate = self.top_win_rate(results, n=5)
        for _, row in win_rate.iterrows():
            lines.append(
                f"  {row['condition']:<35} {row['regime']:<5} "
                f"{row['win_rate']:.0f}% win ({row['fwd_30d']:+.1f}%)"
            )
        
        return "\n".join(lines)
    
    def print_results(
        self,
        results: pd.DataFrame,
        n: int = 15,
        sort_by: str = 'fwd_30d'
    ):
        """Print formatted results table."""
        sorted_df = results.sort_values(sort_by, key=abs, ascending=False).head(n)
        
        print(f"\n{'Metric':<22} {'Cond':<8} {'Regime':<6} {'N':>5} "
              f"{'30d':>8} {'60d':>8} {'Win%':>6}")
        print("-" * 75)
        
        for _, row in sorted_df.iterrows():
            cond = f"{'>' if row['direction'] == 'above' else '<'}{row['percentile']}th"
            print(
                f"{row['metric']:<22} {cond:<8} {row['regime']:<6} "
                f"{row['n_signals']:>5} {row['fwd_30d']:>+7.1f}% "
                f"{row['fwd_60d']:>+7.1f}% {row['win_rate']:>5.0f}%"
            )
    
    def __repr__(self) -> str:
        return f"SignalScreener(metrics={len(self.metrics)}, percentiles={self.percentiles})"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def load_data(data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Load all metrics from parquet files."""
    data_dir = data_dir or DATA_DIR
    
    dfs = {}
    for f in sorted(data_dir.glob("*.parquet")):
        metric_name = f.stem
        df = pd.read_parquet(f)
        df = df.set_index("time")
        df = df.rename(columns={"value": metric_name})
        dfs[metric_name] = df
    
    combined = pd.concat(dfs.values(), axis=1)
    combined = combined.sort_index()
    
    return combined


def quick_screen(df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Run quick screen with defaults."""
    if df is None:
        df = load_data()
    
    screener = SignalScreener()
    return screener.screen(df)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("Loading data...")
    df = load_data()
    
    if df.empty:
        print(f"No data found in {DATA_DIR}")
        print("Run 'python run.py sync' first to download data.")
        sys.exit(1)
    
    print(f"Loaded {len(df.columns)} metrics, {len(df)} rows")
    
    print("\nRunning signal screen...")
    screener = SignalScreener()
    results = screener.screen(df)
    
    print(screener.summary(results))
    
    # Current signals
    print("\n" + "=" * 80)
    print("CURRENTLY ACTIVE SIGNALS")
    print("=" * 80)
    
    active = screener.current_signals(df, results)
    if len(active) > 0:
        print(f"\n{'Metric':<22} {'Condition':<25} {'Current':>10} {'30d':>8} {'Win%':>6}")
        print("-" * 80)
        for _, row in active.head(10).iterrows():
            print(
                f"{row['metric']:<22} {row['condition']:<25} "
                f"{row['current_value']:>10.3f} {row['fwd_30d']:>+7.1f}% "
                f"{row['win_rate']:>5.0f}%"
            )
    else:
        print("\nNo strong signals currently active.")
