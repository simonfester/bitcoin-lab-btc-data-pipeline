"""
Data Mining Module
==================
Proper statistical analysis for signal discovery following best practices:

1. OLS Regression with p-values (not just correlation)
2. Grid search across thresholds
3. Smoothness analysis (detect overfitting)
4. Cycle-by-cycle validation
5. Single digit metrics rule (max 9 parameters)

Usage:
    from src.miner import DataMiner
    
    miner = DataMiner()
    df = miner.load_data()
    
    # Full report
    miner.print_report(df, regime='bull')
    
    # Individual analyses
    miner.regression_analysis(df, 'mvrv', regime='bull')
    miner.grid_search(df, 'mvrv', direction='below', regime='bull')
    miner.cycle_regression(df, 'mvrv', regime='bull')

Key Rules (from analyst):
- Use statsmodels regression, not just correlation
- Grid search: Sharpe curve must be SMOOTH
- Must work in multiple market cycles
- Keep to single digit metrics (max 9)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

try:
    import statsmodels.api as sm
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

from src.config import BULL_MARKETS, BEAR_MARKETS, RAW_DATA_DIR, RESULTS_DIR, DEFAULT_METRICS


# =============================================================================
# CONFIGURATION
# =============================================================================

REGIMES_CONFIG = []
for r in BULL_MARKETS:
    REGIMES_CONFIG.append({"type": "bull", **r})
for r in BEAR_MARKETS:
    REGIMES_CONFIG.append({"type": "bear", **r})


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RegressionResult:
    """Results from OLS regression."""
    metric: str
    coefficient: float
    std_error: float
    t_stat: float
    p_value: float
    r_squared: float
    n_observations: int
    
    @property
    def significant(self) -> bool:
        """p < 0.05"""
        return self.p_value < 0.05
    
    @property
    def highly_significant(self) -> bool:
        """p < 0.01"""
        return self.p_value < 0.01
    
    @property
    def direction(self) -> str:
        """Signal direction based on coefficient sign."""
        return "above" if self.coefficient > 0 else "below"
    
    def __repr__(self):
        sig = "***" if self.p_value < 0.01 else "**" if self.p_value < 0.05 else "*" if self.p_value < 0.1 else ""
        return f"{self.metric}: coef={self.coefficient:+.5f}, p={self.p_value:.4f}{sig}, R²={self.r_squared:.4f}"


@dataclass
class GridSearchResult:
    """Results from grid search across thresholds."""
    metric: str
    direction: str
    thresholds: List[float]
    sharpes: List[float]
    returns: List[float]
    win_rates: List[float]
    n_trades: List[int]
    
    @property
    def smoothness_score(self) -> float:
        """
        Measure how smooth the Sharpe curve is.
        Lower = smoother = more robust.
        
        Spiky curve = overfit to specific threshold.
        Smooth curve = works across range of thresholds.
        """
        if len(self.sharpes) < 3:
            return float('inf')
        
        diffs = np.diff(self.sharpes)
        mean_abs_sharpe = np.mean(np.abs(self.sharpes))
        
        if mean_abs_sharpe == 0:
            return float('inf')
        
        return np.std(diffs) / mean_abs_sharpe
    
    @property
    def is_smooth(self) -> bool:
        """Smoothness < 0.5 = acceptably smooth."""
        return self.smoothness_score < 0.5
    
    @property
    def best_threshold(self) -> float:
        """Threshold with highest Sharpe."""
        if not self.sharpes:
            return 0.0
        idx = np.argmax(self.sharpes)
        return self.thresholds[idx]
    
    @property
    def best_sharpe(self) -> float:
        """Highest Sharpe in grid."""
        return max(self.sharpes) if self.sharpes else 0.0
    
    @property
    def robust_range(self) -> Tuple[float, float]:
        """
        Range of thresholds with Sharpe within 80% of best.
        Wider range = more robust signal.
        """
        if not self.sharpes or max(self.sharpes) <= 0:
            return (0.0, 0.0)
        
        best = max(self.sharpes)
        threshold_80 = best * 0.8
        
        valid = [t for t, s in zip(self.thresholds, self.sharpes) if s >= threshold_80]
        
        if not valid:
            return (self.best_threshold, self.best_threshold)
        
        return (min(valid), max(valid))
    
    @property
    def robust_range_width(self) -> float:
        """Width of robust range."""
        low, high = self.robust_range
        return high - low


@dataclass
class SignalCandidate:
    """A signal that passed all validation tests."""
    metric: str
    direction: str
    threshold: float
    
    # Regression stats
    coefficient: float
    p_value: float
    r_squared: float
    
    # Grid search stats
    sharpe: float
    smoothness: float
    robust_range: Tuple[float, float]
    
    # Cycle stats
    n_cycles_significant: int
    n_cycles_total: int
    sign_consistency: float
    
    @property
    def name(self) -> str:
        symbol = ">" if self.direction == "above" else "<"
        return f"{self.metric}{symbol}{self.threshold:.3f}"
    
    def to_dict(self) -> dict:
        return {
            'metric': self.metric,
            'direction': self.direction,
            'threshold': self.threshold,
            'coefficient': self.coefficient,
            'p_value': self.p_value,
            'r_squared': self.r_squared,
            'sharpe': self.sharpe,
            'smoothness': self.smoothness,
            'robust_range_low': self.robust_range[0],
            'robust_range_high': self.robust_range[1],
            'n_cycles_significant': self.n_cycles_significant,
            'n_cycles_total': self.n_cycles_total,
            'sign_consistency': self.sign_consistency,
        }


# =============================================================================
# DATA MINER CLASS
# =============================================================================

class DataMiner:
    """
    Statistical data mining with proper regression analysis.
    
    Follows analyst best practices:
    1. OLS regression with p-values
    2. Grid search with smoothness check
    3. Cycle-by-cycle validation
    4. Single digit metrics rule
    """
    
    def __init__(
        self,
        metrics: Optional[List[str]] = None,
        forward_days: int = 30
    ):
        """
        Initialize miner.
        
        Args:
            metrics: List of metrics to analyze (default: all)
            forward_days: Forward return horizon in days
        """
        self.metrics = metrics or DEFAULT_METRICS
        self.forward_days = forward_days
        
        if not HAS_STATSMODELS:
            print("⚠️  statsmodels not installed. Run: pip install statsmodels")
    
    # -------------------------------------------------------------------------
    # DATA LOADING
    # -------------------------------------------------------------------------
    
    def load_data(self, data_dir: Optional[Path] = None) -> pd.DataFrame:
        """Load all metrics from parquet files."""
        data_dir = data_dir or RAW_DATA_DIR
        
        dfs = {}
        for f in sorted(data_dir.glob("*.parquet")):
            metric_name = f.stem
            temp = pd.read_parquet(f)
            temp = temp.set_index("time")
            temp = temp.rename(columns={"value": metric_name})
            dfs[metric_name] = temp
        
        df = pd.concat(dfs.values(), axis=1).sort_index()
        return self._prepare_data(df)
    
    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add regime and forward returns."""
        df = df.copy()
        
        # Add regime column
        df['regime'] = 'undefined'
        for r in REGIMES_CONFIG:
            start = pd.Timestamp(r["start"], tz="UTC")
            end = pd.Timestamp(r["end"], tz="UTC")
            mask = (df.index >= start) & (df.index < end)
            df.loc[mask, 'regime'] = r["type"]
        
        # Add forward returns (Y variable for regression)
        if 'price' in df.columns:
            df['fwd_return'] = df['price'].pct_change(self.forward_days).shift(-self.forward_days)
        
        return df
    
    # -------------------------------------------------------------------------
    # 1. OLS REGRESSION
    # -------------------------------------------------------------------------
    
    def regression_analysis(
        self,
        df: pd.DataFrame,
        metric: str,
        regime: Optional[str] = None
    ) -> Optional[RegressionResult]:
        """
        Run OLS regression: fwd_return ~ metric
        
        Returns proper statistics:
        - Coefficient (direction and magnitude)
        - p-value (is it statistically significant?)
        - R² (how much variance explained?)
        - t-stat (coefficient / std error)
        
        Args:
            df: DataFrame with metric and fwd_return columns
            metric: Metric name to regress
            regime: Optional regime filter ('bull' or 'bear')
        """
        if not HAS_STATSMODELS:
            print("statsmodels required. Run: pip install statsmodels")
            return None
        
        if metric not in df.columns or 'fwd_return' not in df.columns:
            return None
        
        # Filter by regime
        if regime:
            df = df[df['regime'] == regime]
        
        # Prepare data
        data = df[[metric, 'fwd_return']].dropna()
        if len(data) < 50:
            return None
        
        X = sm.add_constant(data[metric])
        y = data['fwd_return']
        
        try:
            model = sm.OLS(y, X).fit()
            
            return RegressionResult(
                metric=metric,
                coefficient=model.params[metric],
                std_error=model.bse[metric],
                t_stat=model.tvalues[metric],
                p_value=model.pvalues[metric],
                r_squared=model.rsquared,
                n_observations=len(data),
            )
        except Exception as e:
            print(f"Regression failed for {metric}: {e}")
            return None
    
    def regression_all_metrics(
        self,
        df: pd.DataFrame,
        regime: Optional[str] = None
    ) -> pd.DataFrame:
        """Run regression for all metrics."""
        results = []
        
        for metric in self.metrics:
            if metric not in df.columns:
                continue
            
            result = self.regression_analysis(df, metric, regime)
            if result:
                results.append({
                    'metric': result.metric,
                    'coefficient': result.coefficient,
                    'std_error': result.std_error,
                    't_stat': result.t_stat,
                    'p_value': result.p_value,
                    'r_squared': result.r_squared,
                    'n_obs': result.n_observations,
                    'significant': result.significant,
                    'direction': result.direction,
                })
        
        return pd.DataFrame(results).sort_values('p_value')
    
    # -------------------------------------------------------------------------
    # 2. GRID SEARCH WITH SMOOTHNESS
    # -------------------------------------------------------------------------
    
    def grid_search(
        self,
        df: pd.DataFrame,
        metric: str,
        direction: str = 'below',
        n_points: int = 20,
        regime: Optional[str] = None
    ) -> GridSearchResult:
        """
        Grid search across threshold values.
        
        Tests thresholds from 5th to 95th percentile.
        Returns Sharpe at each threshold.
        
        Key output: is the Sharpe curve SMOOTH?
        - Smooth = robust signal, works across threshold range
        - Spiky = overfit, only works at specific threshold
        
        Args:
            df: DataFrame with metric and fwd_return
            metric: Metric to test
            direction: 'below' or 'above' threshold
            n_points: Number of threshold points to test
            regime: Optional regime filter
        """
        if metric not in df.columns or 'fwd_return' not in df.columns:
            return GridSearchResult(metric, direction, [], [], [], [], [])
        
        # Filter by regime
        if regime:
            df = df[df['regime'] == regime]
        
        # Generate threshold grid (5th to 95th percentile)
        percentiles = np.linspace(5, 95, n_points)
        thresholds = [df[metric].quantile(p/100) for p in percentiles]
        
        sharpes = []
        returns = []
        win_rates = []
        n_trades = []
        
        for threshold in thresholds:
            # Generate signal
            if direction == 'below':
                signal = df[metric] < threshold
            else:
                signal = df[metric] > threshold
            
            # Get returns when signal is active
            signal_returns = df.loc[signal, 'fwd_return'].dropna()
            
            if len(signal_returns) < 10:
                sharpes.append(0)
                returns.append(0)
                win_rates.append(0)
                n_trades.append(0)
                continue
            
            # Calculate metrics
            mean_ret = signal_returns.mean()
            std_ret = signal_returns.std()
            
            # Annualized Sharpe (assuming monthly rebalancing)
            sharpe = mean_ret / std_ret * np.sqrt(12) if std_ret > 0 else 0
            win_rate = (signal_returns > 0).mean()
            
            sharpes.append(sharpe)
            returns.append(mean_ret * 100)
            win_rates.append(win_rate * 100)
            n_trades.append(len(signal_returns))
        
        return GridSearchResult(
            metric=metric,
            direction=direction,
            thresholds=thresholds,
            sharpes=sharpes,
            returns=returns,
            win_rates=win_rates,
            n_trades=n_trades,
        )
    
    def grid_search_all_metrics(
        self,
        df: pd.DataFrame,
        regime: Optional[str] = None
    ) -> pd.DataFrame:
        """Run grid search for all metrics in both directions."""
        results = []
        
        for metric in self.metrics:
            if metric not in df.columns:
                continue
            
            for direction in ['below', 'above']:
                gs = self.grid_search(df, metric, direction, regime=regime)
                
                if not gs.sharpes or gs.best_sharpe <= 0:
                    continue
                
                results.append({
                    'metric': metric,
                    'direction': direction,
                    'best_threshold': gs.best_threshold,
                    'best_sharpe': gs.best_sharpe,
                    'smoothness': gs.smoothness_score,
                    'is_smooth': gs.is_smooth,
                    'robust_range_low': gs.robust_range[0],
                    'robust_range_high': gs.robust_range[1],
                    'robust_range_width': gs.robust_range_width,
                })
        
        return pd.DataFrame(results).sort_values('best_sharpe', ascending=False)
    
    # -------------------------------------------------------------------------
    # 3. CYCLE-BY-CYCLE VALIDATION
    # -------------------------------------------------------------------------
    
    def cycle_regression(
        self,
        df: pd.DataFrame,
        metric: str,
        regime: str = 'bull'
    ) -> pd.DataFrame:
        """
        Run regression in each market cycle separately.
        
        A robust signal should be significant in MOST cycles,
        not just one or two.
        
        Args:
            df: Full DataFrame (all dates)
            metric: Metric to test
            regime: 'bull' or 'bear'
        """
        cycles = BULL_MARKETS if regime == 'bull' else BEAR_MARKETS
        
        if not HAS_STATSMODELS:
            return pd.DataFrame()
        
        results = []
        for cycle in cycles:
            start = pd.Timestamp(cycle['start'], tz='UTC')
            end = pd.Timestamp(cycle['end'], tz='UTC')
            
            cycle_df = df[(df.index >= start) & (df.index < end)]
            
            data = cycle_df[[metric, 'fwd_return']].dropna()
            if len(data) < 30:
                continue
            
            X = sm.add_constant(data[metric])
            y = data['fwd_return']
            
            try:
                model = sm.OLS(y, X).fit()
                results.append({
                    'cycle': cycle['name'],
                    'start': cycle['start'],
                    'end': cycle['end'],
                    'coefficient': model.params[metric],
                    'p_value': model.pvalues[metric],
                    'r_squared': model.rsquared,
                    'significant': model.pvalues[metric] < 0.1,
                    'n_obs': len(data),
                })
            except:
                pass
        
        return pd.DataFrame(results)
    
    def metric_robustness(
        self,
        df: pd.DataFrame,
        regime: str = 'bull'
    ) -> pd.DataFrame:
        """
        Test each metric's robustness across cycles.
        
        Returns:
        - n_significant: How many cycles is it significant in?
        - sign_consistency: Is the coefficient sign consistent?
        """
        results = []
        
        for metric in self.metrics:
            if metric not in df.columns:
                continue
            
            cycle_results = self.cycle_regression(df, metric, regime)
            
            if cycle_results.empty or len(cycle_results) < 3:
                continue
            
            n_cycles = len(cycle_results)
            n_significant = cycle_results['significant'].sum()
            
            # Check sign consistency
            coefs = cycle_results['coefficient'].values
            dominant_sign = 1 if np.mean(coefs) > 0 else -1
            n_same_sign = sum(1 for c in coefs if np.sign(c) == dominant_sign)
            
            results.append({
                'metric': metric,
                'n_cycles': n_cycles,
                'n_significant': n_significant,
                'pct_significant': n_significant / n_cycles * 100,
                'n_same_sign': n_same_sign,
                'sign_consistency': n_same_sign / n_cycles * 100,
                'avg_coefficient': np.mean(coefs),
                'avg_r_squared': cycle_results['r_squared'].mean(),
            })
        
        return pd.DataFrame(results).sort_values('pct_significant', ascending=False)
    
    # -------------------------------------------------------------------------
    # 4. FIND PASSING SIGNALS
    # -------------------------------------------------------------------------
    
    def find_signals(
        self,
        df: pd.DataFrame,
        regime: str = 'bull',
        min_p_value: float = 0.05,
        min_smoothness: bool = True,
        min_cycle_pct: float = 40,
        min_sign_consistency: float = 60
    ) -> List[SignalCandidate]:
        """
        Find signals that pass all validation tests.
        
        Tests:
        1. Regression significant (p < min_p_value)
        2. Smooth Sharpe curve (smoothness < 0.5)
        3. Works in multiple cycles (pct_significant >= min_cycle_pct)
        4. Consistent sign across cycles (sign_consistency >= min_sign_consistency)
        
        Args:
            df: DataFrame with all data
            regime: 'bull' or 'bear'
            min_p_value: Maximum p-value for significance
            min_smoothness: Require smooth Sharpe curve
            min_cycle_pct: Minimum % of cycles where significant
            min_sign_consistency: Minimum % of cycles with same sign
        
        Returns:
            List of SignalCandidate objects
        """
        # Run all analyses
        reg_results = self.regression_all_metrics(df, regime)
        gs_results = self.grid_search_all_metrics(df, regime)
        cycle_results = self.metric_robustness(df, regime)
        
        candidates = []
        
        for metric in self.metrics:
            # Get regression result
            reg = reg_results[reg_results['metric'] == metric]
            if reg.empty:
                continue
            reg = reg.iloc[0]
            
            # Check regression significance
            if reg['p_value'] > min_p_value:
                continue
            
            # Get direction from coefficient sign
            direction = reg['direction']
            
            # Get grid search result for this metric/direction
            gs = gs_results[(gs_results['metric'] == metric) & (gs_results['direction'] == direction)]
            if gs.empty:
                continue
            gs = gs.iloc[0]
            
            # Check smoothness
            if min_smoothness and not gs['is_smooth']:
                continue
            
            # Get cycle results
            cyc = cycle_results[cycle_results['metric'] == metric]
            if cyc.empty:
                continue
            cyc = cyc.iloc[0]
            
            # Check cycle robustness
            if cyc['pct_significant'] < min_cycle_pct:
                continue
            if cyc['sign_consistency'] < min_sign_consistency:
                continue
            
            # Passed all tests!
            candidates.append(SignalCandidate(
                metric=metric,
                direction=direction,
                threshold=gs['best_threshold'],
                coefficient=reg['coefficient'],
                p_value=reg['p_value'],
                r_squared=reg['r_squared'],
                sharpe=gs['best_sharpe'],
                smoothness=gs['smoothness'],
                robust_range=(gs['robust_range_low'], gs['robust_range_high']),
                n_cycles_significant=int(cyc['n_significant']),
                n_cycles_total=int(cyc['n_cycles']),
                sign_consistency=cyc['sign_consistency'],
            ))
        
        # Sort by Sharpe
        return sorted(candidates, key=lambda x: x.sharpe, reverse=True)
    
    # -------------------------------------------------------------------------
    # 5. CROSS-CORRELATION (Redundancy)
    # -------------------------------------------------------------------------
    
    def find_independent_metrics(
        self,
        df: pd.DataFrame,
        max_corr: float = 0.7,
        max_metrics: int = 9
    ) -> List[str]:
        """
        Find a minimal set of independent (non-redundant) metrics.
        
        Follows the "single digit metrics" rule (max 9).
        
        Args:
            df: DataFrame with metrics
            max_corr: Maximum allowed correlation between metrics
            max_metrics: Maximum number of metrics to select
        """
        available = [m for m in self.metrics if m in df.columns]
        corr_matrix = df[available].corr()
        
        selected = []
        remaining = available.copy()
        
        while remaining and len(selected) < max_metrics:
            # Pick first remaining
            metric = remaining.pop(0)
            selected.append(metric)
            
            # Remove highly correlated metrics
            to_remove = []
            for m in remaining:
                if abs(corr_matrix.loc[metric, m]) > max_corr:
                    to_remove.append(m)
            
            for m in to_remove:
                remaining.remove(m)
        
        return selected
    
    # -------------------------------------------------------------------------
    # REPORTING
    # -------------------------------------------------------------------------
    
    def print_report(self, df: pd.DataFrame, regime: str = 'bull'):
        """Print comprehensive data mining report."""
        
        regime_df = df[df['regime'] == regime] if regime else df
        
        print("=" * 90)
        print("DATA MINING REPORT")
        print("=" * 90)
        print(f"Data: {len(df)} total rows, {len(regime_df)} {regime} market rows")
        print(f"Forward horizon: {self.forward_days} days")
        print(f"Regime: {regime.upper()}")
        
        # 1. Regression
        print("\n" + "─" * 90)
        print("1. OLS REGRESSION: fwd_return ~ metric")
        print("─" * 90)
        print("Significance: *** p<0.01, ** p<0.05, * p<0.1\n")
        
        reg_results = self.regression_all_metrics(df, regime)
        
        if not reg_results.empty:
            print(f"{'Metric':<25} {'Coef':>10} {'t-stat':>8} {'p-value':>10} {'R²':>8} {'Sig':>5}")
            print("-" * 75)
            
            for _, row in reg_results.iterrows():
                sig = "***" if row['p_value'] < 0.01 else "**" if row['p_value'] < 0.05 else "*" if row['p_value'] < 0.1 else ""
                print(f"{row['metric']:<25} {row['coefficient']:>+10.5f} {row['t_stat']:>8.2f} "
                      f"{row['p_value']:>10.4f} {row['r_squared']:>8.4f} {sig:>5}")
        
        # 2. Grid search
        print("\n" + "─" * 90)
        print("2. GRID SEARCH - SHARPE CURVE SMOOTHNESS")
        print("─" * 90)
        print("Smooth curve = robust. Spiky curve = OVERFIT.\n")
        
        gs_results = self.grid_search_all_metrics(df, regime)
        
        if not gs_results.empty:
            print(f"{'Metric':<20} {'Dir':>6} {'Sharpe':>8} {'Smooth':>8} {'OK?':>5} {'Range':>15}")
            print("-" * 70)
            
            for _, row in gs_results.head(20).iterrows():
                ok = "✓" if row['is_smooth'] else "✗"
                range_str = f"{row['robust_range_low']:.2f}-{row['robust_range_high']:.2f}"
                print(f"{row['metric']:<20} {row['direction']:>6} {row['best_sharpe']:>8.2f} "
                      f"{row['smoothness']:>8.2f} {ok:>5} {range_str:>15}")
        
        # 3. Cycle robustness
        print("\n" + "─" * 90)
        print("3. CYCLE-BY-CYCLE VALIDATION")
        print("─" * 90)
        print("Must work in multiple cycles, not just one.\n")
        
        cycle_results = self.metric_robustness(df, regime)
        
        if not cycle_results.empty:
            print(f"{'Metric':<25} {'Sig Cycles':>12} {'Sign Consist':>14} {'Robust?':>10}")
            print("-" * 65)
            
            for _, row in cycle_results.iterrows():
                is_robust = row['pct_significant'] >= 40 and row['sign_consistency'] >= 60
                ok = "✓" if is_robust else ""
                print(f"{row['metric']:<25} {row['n_significant']:.0f}/{row['n_cycles']:.0f} ({row['pct_significant']:.0f}%)   "
                      f"{row['n_same_sign']:.0f}/{row['n_cycles']:.0f} ({row['sign_consistency']:.0f}%)       {ok:>5}")
        
        # 4. Passing signals
        print("\n" + "=" * 90)
        print("SIGNALS PASSING ALL TESTS")
        print("=" * 90)
        
        candidates = self.find_signals(df, regime)
        
        if candidates:
            print(f"\n{'Metric':<20} {'Dir':>6} {'Threshold':>12} {'Sharpe':>8} {'Smooth':>8} {'Cycles':>10}")
            print("-" * 75)
            
            for c in candidates:
                print(f"{c.metric:<20} {c.direction:>6} {c.threshold:>12.3f} {c.sharpe:>8.2f} "
                      f"{c.smoothness:>8.2f} {c.n_cycles_significant}/{c.n_cycles_total}")
            
            print("\n🏆 RECOMMENDED SIGNALS:\n")
            for c in candidates[:8]:  # Single digit rule
                print(f"  {c.name}")
                print(f"    Regression: coef={c.coefficient:+.5f}, p={c.p_value:.4f}")
                print(f"    Grid: Sharpe={c.sharpe:.2f}, smoothness={c.smoothness:.2f}")
                print(f"    Robust range: {c.robust_range[0]:.3f} to {c.robust_range[1]:.3f}")
                print()
        else:
            print("\n⚠️  No signals passed all tests.")
        
        # Rules reminder
        print("─" * 90)
        print("KEY RULES:")
        print("─" * 90)
        print("  1. Use regression p-values, not just correlation")
        print("  2. Sharpe curve MUST be smooth (not spiky)")
        print("  3. Must work in MULTIPLE market cycles")
        print("  4. Keep to SINGLE DIGIT metrics (max 9)")
    
    # -------------------------------------------------------------------------
    # SAVE RESULTS
    # -------------------------------------------------------------------------
    
    def save_signals(
        self,
        candidates: List[SignalCandidate],
        filename: Optional[str] = None
    ) -> Path:
        """Save signal candidates to JSON."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mined_signals_{timestamp}.json"
        
        output_path = RESULTS_DIR / "screens" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'forward_days': self.forward_days,
            'n_signals': len(candidates),
            'signals': [c.to_dict() for c in candidates]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return output_path


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    print("Loading data...")
    miner = DataMiner(forward_days=30)
    df = miner.load_data()
    
    if df.empty:
        print("No data found. Run 'python run.py sync' first.")
        exit(1)
    
    # Run full report
    miner.print_report(df, regime='bull')
    
    # Save passing signals
    candidates = miner.find_signals(df, regime='bull')
    if candidates:
        output_path = miner.save_signals(candidates)
        print(f"\n📁 Signals saved to: {output_path}")
