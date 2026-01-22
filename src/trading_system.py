#!/usr/bin/env python3
"""
Unified Bitcoin Trading System
==============================
Integrates:
- Bitcoin Lab API (primary on-chain data)
- BRK API (backup on-chain data)  
- Glassnode (derivatives data)

Three components:
1. Data Downloading (unified across sources)
2. Exploratory Statistics (test predictive power)
3. Backtesting (confirmation, not discovery)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import warnings
warnings.filterwarnings('ignore')

# Stats imports
from scipy import stats
from scipy.stats import spearmanr, pearsonr, kendalltau
import statsmodels.api as sm
from statsmodels.tsa.stattools import acf, adfuller, grangercausalitytests

# Local imports
from config import (
    PROJECT_ROOT, DATA_DIR, RESULTS_DIR, SIGNALS_DIR,
    DEFAULT_METRICS, BULL_MARKETS, BEAR_MARKETS
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# PATHS
# =============================================================================

BL_DATA = DATA_DIR / "bl" / "daily"
BRK_DATA = DATA_DIR / "brk" / "daily"
GLASSNODE_DATA = DATA_DIR / "glassnode" / "daily"


# =============================================================================
# DATA LOADER (Unified)
# =============================================================================

@dataclass
class MetricSource:
    """Track which source a metric came from."""
    name: str
    source: str  # 'bl', 'brk', 'glassnode'
    data: pd.DataFrame


class UnifiedDataLoader:
    """
    Load data from all sources with automatic fallback:
    1. Bitcoin Lab (primary)
    2. BRK (backup for on-chain)
    3. Glassnode (derivatives only)
    """
    
    def __init__(self):
        self.bl_dir = BL_DATA
        self.brk_dir = BRK_DATA
        self.gn_dir = GLASSNODE_DATA
        self._cache = {}
        
    def load(
        self,
        metric_name: str,
        source: str = "auto",
        start: str = None,
        end: str = None
    ) -> Optional[pd.DataFrame]:
        """
        Load a metric with automatic source selection.
        
        Args:
            metric_name: Name of metric (e.g., 'mvrv', 'funding_rate')
            source: 'auto', 'bl', 'brk', or 'glassnode'
            start: Start date filter
            end: End date filter
            
        Returns:
            DataFrame with DatetimeIndex and 'value' column
        """
        cache_key = f"{metric_name}_{source}_{start}_{end}"
        if cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        df = None
        actual_source = None
        
        if source == "auto":
            # Try sources in order of preference
            df = self._try_load(metric_name, "bl")
            if df is not None:
                actual_source = "bl"
            else:
                df = self._try_load(metric_name, "brk")
                if df is not None:
                    actual_source = "brk"
                else:
                    df = self._try_load(metric_name, "glassnode")
                    if df is not None:
                        actual_source = "glassnode"
        else:
            df = self._try_load(metric_name, source)
            actual_source = source
            
        if df is None:
            logger.warning(f"Could not load metric: {metric_name}")
            return None
            
        # Filter by date range
        if start:
            df = df[df.index >= pd.Timestamp(start, tz='UTC')]
        if end:
            df = df[df.index <= pd.Timestamp(end, tz='UTC')]
        
        self._cache[cache_key] = df
        return df.copy()
    
    def _try_load(self, metric_name: str, source: str) -> Optional[pd.DataFrame]:
        """Try to load from a specific source."""
        
        if source == "bl":
            path = self.bl_dir / f"{metric_name}.parquet"
        elif source == "brk":
            path = self.brk_dir / f"{metric_name}.parquet"
        elif source == "glassnode":
            path = self.gn_dir / f"{metric_name}.parquet"
        else:
            return None
            
        if not path.exists():
            return None
            
        try:
            df = pd.read_parquet(path)
            
            # Standardize column name
            if 'value' not in df.columns:
                # Find the value column
                for col in df.columns:
                    if col != 'time' and not col.startswith('_'):
                        df = df.rename(columns={col: 'value'})
                        break
            
            # Ensure DatetimeIndex with UTC
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'time' in df.columns:
                    df = df.set_index('time')
                    
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC')
                
            return df
            
        except Exception as e:
            logger.error(f"Error loading {metric_name} from {source}: {e}")
            return None
    
    def load_multiple(
        self,
        metrics: List[str],
        start: str = None,
        end: str = None,
        align: bool = True
    ) -> pd.DataFrame:
        """
        Load multiple metrics into a single DataFrame.
        
        Args:
            metrics: List of metric names
            start: Start date
            end: End date  
            align: Align all series to common dates
            
        Returns:
            DataFrame with each metric as a column
        """
        dfs = {}
        
        for metric in metrics:
            df = self.load(metric, start=start, end=end)
            if df is not None:
                dfs[metric] = df['value']
        
        if not dfs:
            return pd.DataFrame()
            
        result = pd.DataFrame(dfs)
        
        if align:
            result = result.dropna(how='any')
            
        return result
    
    def get_available_metrics(self) -> Dict[str, List[str]]:
        """List all available metrics by source."""
        available = {
            'bl': [],
            'brk': [],
            'glassnode': []
        }
        
        for source, dir_path in [
            ('bl', self.bl_dir),
            ('brk', self.brk_dir),
            ('glassnode', self.gn_dir)
        ]:
            if dir_path.exists():
                for f in dir_path.glob("*.parquet"):
                    available[source].append(f.stem)
                    
        return available


# =============================================================================
# EXPLORATORY STATISTICS
# =============================================================================

class ExploratoryStats:
    """
    Test whether signals have predictive power BEFORE backtesting.
    Use backtesting as confirmation, not discovery.
    """
    
    def __init__(self, loader: UnifiedDataLoader = None):
        self.loader = loader or UnifiedDataLoader()
        
    def calculate_forward_returns(
        self,
        prices: pd.Series,
        periods: List[int] = [7, 14, 30, 60, 90]
    ) -> pd.DataFrame:
        """Calculate forward returns for multiple horizons."""
        returns = pd.DataFrame(index=prices.index)
        
        for p in periods:
            returns[f'fwd_{p}d'] = prices.shift(-p) / prices - 1
            
        return returns
    
    def regression_analysis(
        self,
        signal: pd.Series,
        forward_returns: pd.Series,
        controls: pd.DataFrame = None
    ) -> Dict:
        """
        Run regression to test if signal predicts returns.
        
        Args:
            signal: The metric/indicator being tested
            forward_returns: Future returns (dependent variable)
            controls: Control variables (e.g., momentum, volatility)
            
        Returns:
            Dict with coefficient, t-stat, p-value, R²
        """
        # Align data
        df = pd.DataFrame({
            'signal': signal,
            'returns': forward_returns
        }).dropna()
        
        if len(df) < 50:
            return {'error': 'Insufficient data'}
        
        # Build regression
        X = df[['signal']]
        if controls is not None:
            # Add controls
            for col in controls.columns:
                if col in df.index:
                    X[col] = controls.loc[df.index, col]
            X = X.dropna()
            df = df.loc[X.index]
            
        X = sm.add_constant(X)
        y = df['returns']
        
        try:
            model = sm.OLS(y, X).fit(cov_type='HAC', cov_kwds={'maxlags': 5})
            
            return {
                'coefficient': model.params['signal'],
                't_stat': model.tvalues['signal'],
                'p_value': model.pvalues['signal'],
                'r_squared': model.rsquared,
                'adj_r_squared': model.rsquared_adj,
                'n_obs': int(model.nobs),
                'significant_5pct': model.pvalues['signal'] < 0.05,
                'significant_1pct': model.pvalues['signal'] < 0.01,
            }
        except Exception as e:
            return {'error': str(e)}
    
    def correlation_analysis(
        self,
        signal: pd.Series,
        forward_returns: pd.Series
    ) -> Dict:
        """Calculate multiple correlation measures."""
        # Align data
        df = pd.DataFrame({
            'signal': signal,
            'returns': forward_returns
        }).dropna()
        
        if len(df) < 30:
            return {'error': 'Insufficient data'}
        
        return {
            'pearson_r': pearsonr(df['signal'], df['returns'])[0],
            'pearson_p': pearsonr(df['signal'], df['returns'])[1],
            'spearman_r': spearmanr(df['signal'], df['returns'])[0],
            'spearman_p': spearmanr(df['signal'], df['returns'])[1],
            'kendall_tau': kendalltau(df['signal'], df['returns'])[0],
            'kendall_p': kendalltau(df['signal'], df['returns'])[1],
            'n_obs': len(df)
        }
    
    def threshold_analysis(
        self,
        signal: pd.Series,
        forward_returns: pd.Series,
        thresholds: List[float] = None,
        n_quantiles: int = 10
    ) -> pd.DataFrame:
        """
        Test returns at different signal thresholds.
        
        Args:
            signal: The indicator
            forward_returns: Future returns
            thresholds: Specific thresholds to test (or auto from quantiles)
            n_quantiles: Number of quantiles if auto
        """
        df = pd.DataFrame({
            'signal': signal,
            'returns': forward_returns
        }).dropna()
        
        if thresholds is None:
            thresholds = df['signal'].quantile(np.linspace(0.1, 0.9, n_quantiles)).values
        
        results = []
        
        for i, thresh in enumerate(thresholds):
            below = df[df['signal'] < thresh]['returns']
            above = df[df['signal'] >= thresh]['returns']
            
            results.append({
                'threshold': thresh,
                'below_mean': below.mean(),
                'below_std': below.std(),
                'below_count': len(below),
                'above_mean': above.mean(),
                'above_std': above.std(),
                'above_count': len(above),
                'spread': above.mean() - below.mean(),
            })
            
            # T-test for difference in means
            if len(below) > 10 and len(above) > 10:
                t_stat, p_val = stats.ttest_ind(above, below)
                results[-1]['t_stat'] = t_stat
                results[-1]['p_value'] = p_val
        
        return pd.DataFrame(results)
    
    def granger_causality(
        self,
        signal: pd.Series,
        returns: pd.Series,
        max_lag: int = 5
    ) -> Dict:
        """Test if signal Granger-causes returns."""
        df = pd.DataFrame({
            'signal': signal,
            'returns': returns
        }).dropna()
        
        if len(df) < 50:
            return {'error': 'Insufficient data'}
        
        try:
            result = grangercausalitytests(
                df[['returns', 'signal']],
                maxlag=max_lag,
                verbose=False
            )
            
            # Extract p-values for each lag
            p_values = {}
            for lag in range(1, max_lag + 1):
                # Use F-test p-value
                p_values[f'lag_{lag}'] = result[lag][0]['ssr_ftest'][1]
            
            # Signal Granger-causes returns if any lag is significant
            min_p = min(p_values.values())
            
            return {
                'p_values': p_values,
                'min_p_value': min_p,
                'granger_causes': min_p < 0.05,
                'best_lag': min(p_values, key=p_values.get)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def cycle_validation(
        self,
        signal: pd.Series,
        forward_returns: pd.Series,
        cycles: List[Dict] = None
    ) -> pd.DataFrame:
        """
        Test signal effectiveness across different market cycles.
        
        Important: A robust signal should work in at least 60% of cycles.
        """
        if cycles is None:
            cycles = BULL_MARKETS + BEAR_MARKETS
        
        df = pd.DataFrame({
            'signal': signal,
            'returns': forward_returns
        }).dropna()
        
        results = []
        
        for cycle in cycles:
            start = pd.Timestamp(cycle['start'], tz='UTC')
            end = pd.Timestamp(cycle['end'], tz='UTC')
            
            mask = (df.index >= start) & (df.index <= end)
            cycle_data = df[mask]
            
            if len(cycle_data) < 20:
                continue
            
            corr, p_val = spearmanr(cycle_data['signal'], cycle_data['returns'])
            
            results.append({
                'cycle': cycle['name'],
                'start': start,
                'end': end,
                'n_obs': len(cycle_data),
                'correlation': corr,
                'p_value': p_val,
                'significant': p_val < 0.1,
                'correct_sign': corr > 0  # Assuming higher signal = lower future returns for most
            })
        
        result_df = pd.DataFrame(results)
        
        # Add summary
        if len(result_df) > 0:
            result_df.attrs['cycles_significant'] = (result_df['significant'].sum() / len(result_df)) * 100
            result_df.attrs['cycles_correct_sign'] = (result_df['correct_sign'].sum() / len(result_df)) * 100
            
        return result_df
    
    def run_full_analysis(
        self,
        metric_name: str,
        forward_periods: List[int] = [7, 14, 30, 60],
        verbose: bool = True
    ) -> Dict:
        """
        Run complete exploratory analysis on a metric.
        
        Returns a comprehensive report on predictive power.
        """
        # Load data
        signal = self.loader.load(metric_name)
        price = self.loader.load('price')
        
        if signal is None or price is None:
            return {'error': f'Could not load {metric_name} or price data'}
        
        # Calculate forward returns
        fwd_returns = self.calculate_forward_returns(price['value'], forward_periods)
        
        results = {
            'metric': metric_name,
            'date_range': f"{signal.index.min().date()} to {signal.index.max().date()}",
            'n_observations': len(signal),
            'analysis': {}
        }
        
        for period in forward_periods:
            fwd_col = f'fwd_{period}d'
            if fwd_col not in fwd_returns.columns:
                continue
                
            period_results = {
                'forward_days': period,
                'regression': self.regression_analysis(
                    signal['value'], fwd_returns[fwd_col]
                ),
                'correlation': self.correlation_analysis(
                    signal['value'], fwd_returns[fwd_col]
                ),
                'granger': self.granger_causality(
                    signal['value'], fwd_returns[fwd_col]
                ),
            }
            
            # Cycle validation
            cycles = self.cycle_validation(signal['value'], fwd_returns[fwd_col])
            if len(cycles) > 0:
                period_results['cycle_validation'] = {
                    'pct_significant': cycles.attrs.get('cycles_significant', 0),
                    'pct_correct_sign': cycles.attrs.get('cycles_correct_sign', 0),
                    'n_cycles': len(cycles)
                }
            
            results['analysis'][f'{period}d'] = period_results
        
        # Summary
        results['summary'] = self._summarize_results(results)
        
        if verbose:
            self._print_summary(results)
            
        return results
    
    def _summarize_results(self, results: Dict) -> Dict:
        """Summarize analysis results into actionable conclusions."""
        summary = {
            'predictive_power': 'unknown',
            'recommended_horizons': [],
            'warnings': []
        }
        
        significant_horizons = []
        
        for horizon, analysis in results.get('analysis', {}).items():
            reg = analysis.get('regression', {})
            corr = analysis.get('correlation', {})
            
            if reg.get('significant_5pct', False):
                significant_horizons.append(horizon)
            
            # Check for cycle consistency
            cycle_val = analysis.get('cycle_validation', {})
            if cycle_val.get('pct_significant', 0) < 40:
                summary['warnings'].append(f"{horizon}: Low cycle consistency (<40%)")
        
        if len(significant_horizons) >= 2:
            summary['predictive_power'] = 'strong'
        elif len(significant_horizons) >= 1:
            summary['predictive_power'] = 'moderate'
        else:
            summary['predictive_power'] = 'weak'
            
        summary['recommended_horizons'] = significant_horizons
        
        return summary
    
    def _print_summary(self, results: Dict):
        """Print formatted summary."""
        print("\n" + "="*60)
        print(f"EXPLORATORY ANALYSIS: {results['metric']}")
        print("="*60)
        print(f"Date range: {results['date_range']}")
        print(f"Observations: {results['n_observations']}")
        
        for horizon, analysis in results.get('analysis', {}).items():
            print(f"\n--- {horizon} Forward Returns ---")
            
            reg = analysis.get('regression', {})
            if 'error' not in reg:
                print(f"  Regression: coef={reg.get('coefficient', 0):.4f}, "
                      f"t={reg.get('t_stat', 0):.2f}, "
                      f"p={reg.get('p_value', 1):.4f} "
                      f"{'✓' if reg.get('significant_5pct') else '✗'}")
            
            corr = analysis.get('correlation', {})
            if 'error' not in corr:
                print(f"  Spearman: r={corr.get('spearman_r', 0):.3f}, "
                      f"p={corr.get('spearman_p', 1):.4f}")
            
            cycle = analysis.get('cycle_validation', {})
            if cycle:
                print(f"  Cycles: {cycle.get('pct_significant', 0):.0f}% significant, "
                      f"{cycle.get('pct_correct_sign', 0):.0f}% correct sign")
        
        summary = results.get('summary', {})
        print(f"\n>>> PREDICTIVE POWER: {summary.get('predictive_power', 'unknown').upper()}")
        if summary.get('recommended_horizons'):
            print(f">>> Recommended horizons: {', '.join(summary['recommended_horizons'])}")
        if summary.get('warnings'):
            print(f">>> Warnings: {'; '.join(summary['warnings'])}")


# =============================================================================
# CHECKMATE COMPOSITE SCORE
# =============================================================================

class CheckmateFramework:
    """
    James Check's Checkmate Framework implementation.
    
    Three layers:
    1. Investor Profitability (MVRV, NUPL)
    2. Spending Behavior (SOPR, Realized P/L)
    3. Market Structure (LTH Supply, Exchange Flows)
    """
    
    # Metric configurations: (bullish_threshold, bearish_threshold, weight, inverted)
    # inverted=True means lower values are bearish (opposite of normal)
    
    LAYER_1_METRICS = {
        'mvrv': (1.0, 2.4, 0.25, False),
        'mvrv_sth': (1.0, 1.4, 0.15, False),
        'nupl': (0.25, 0.6, 0.20, False),
    }
    
    LAYER_2_METRICS = {
        'sopr': (1.0, 1.05, 0.15, False),
        'sopr_sth': (1.0, 1.02, 0.10, False),
    }
    
    LAYER_3_METRICS = {
        'supply_lth_sth_ratio': (3.0, 5.0, 0.15, False),  # Lower = more STH = riskier
    }
    
    def __init__(self, loader: UnifiedDataLoader = None):
        self.loader = loader or UnifiedDataLoader()
        
    def score_metric(
        self,
        value: float,
        bullish_thresh: float,
        bearish_thresh: float,
        inverted: bool = False
    ) -> float:
        """
        Score a single metric from -1 (bullish) to +1 (bearish).
        
        Args:
            value: Current metric value
            bullish_thresh: Value below which is bullish
            bearish_thresh: Value above which is bearish
            inverted: If True, reverse interpretation
        """
        if inverted:
            bullish_thresh, bearish_thresh = bearish_thresh, bullish_thresh
            
        if value <= bullish_thresh:
            return -1.0  # Bullish
        elif value >= bearish_thresh:
            return 1.0  # Bearish
        else:
            # Linear interpolation between thresholds
            range_size = bearish_thresh - bullish_thresh
            if range_size == 0:
                return 0
            position = (value - bullish_thresh) / range_size
            return (position * 2) - 1  # Scale to [-1, 1]
    
    def calculate_composite(
        self,
        date: pd.Timestamp = None
    ) -> Dict:
        """
        Calculate composite Checkmate score for a date.
        
        Returns:
            Dict with scores by layer and overall composite
        """
        if date is None:
            date = pd.Timestamp.now(tz='UTC').floor('D')
        
        results = {
            'date': date,
            'layer_1': {},
            'layer_2': {},
            'layer_3': {},
            'scores': {},
            'weights': {},
        }
        
        total_weight = 0
        weighted_sum = 0
        
        all_metrics = {
            **self.LAYER_1_METRICS,
            **self.LAYER_2_METRICS,
            **self.LAYER_3_METRICS
        }
        
        for metric_name, (bull, bear, weight, inv) in all_metrics.items():
            df = self.loader.load(metric_name)
            if df is None:
                continue
                
            # Get value for date (or closest prior)
            mask = df.index <= date
            if not mask.any():
                continue
                
            value = df.loc[mask, 'value'].iloc[-1]
            score = self.score_metric(value, bull, bear, inv)
            
            # Categorize by layer
            if metric_name in self.LAYER_1_METRICS:
                results['layer_1'][metric_name] = {'value': value, 'score': score}
            elif metric_name in self.LAYER_2_METRICS:
                results['layer_2'][metric_name] = {'value': value, 'score': score}
            else:
                results['layer_3'][metric_name] = {'value': value, 'score': score}
            
            results['scores'][metric_name] = score
            results['weights'][metric_name] = weight
            
            weighted_sum += score * weight
            total_weight += weight
        
        if total_weight > 0:
            results['composite'] = weighted_sum / total_weight
        else:
            results['composite'] = 0
            
        # Interpret
        composite = results['composite']
        if composite <= -0.5:
            results['signal'] = 'STRONG_ACCUMULATE'
        elif composite <= 0:
            results['signal'] = 'ACCUMULATE'
        elif composite <= 0.5:
            results['signal'] = 'HOLD'
        else:
            results['signal'] = 'DISTRIBUTE'
            
        return results
    
    def calculate_series(
        self,
        start: str = "2015-01-01",
        end: str = None
    ) -> pd.DataFrame:
        """Calculate composite score for a date range."""
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")
            
        dates = pd.date_range(start, end, freq='D', tz='UTC')
        
        records = []
        for date in dates:
            result = self.calculate_composite(date)
            records.append({
                'date': date,
                'composite': result.get('composite', np.nan),
                'signal': result.get('signal', 'UNKNOWN'),
                **result.get('scores', {})
            })
        
        df = pd.DataFrame(records)
        df = df.set_index('date')
        
        return df


# =============================================================================
# BUY THE DIP STRATEGY
# =============================================================================

class BuyTheDipStrategy:
    """
    Implements James Check's "Buy the Dip" conditions.
    
    On-chain conditions (from Bitcoin Lab):
    - STH-MVRV < 1.0 (short-term holders underwater)
    - STH-SOPR < 1.0 (short-term holders selling at loss)
    - Price < STH Realized Price (below cost basis)
    
    Derivatives conditions (from Glassnode):
    - Funding rate ≤ 0 (bearish sentiment in perps)
    - Long/Short liquidation ratio > 2.0 (heavy long liquidations)
    """
    
    def __init__(self, loader: UnifiedDataLoader = None):
        self.loader = loader or UnifiedDataLoader()
        
    def check_conditions(self, date: pd.Timestamp = None) -> Dict:
        """
        Check all Buy-the-Dip conditions for a specific date.
        
        Returns:
            Dict with each condition status and overall signal
        """
        if date is None:
            date = pd.Timestamp.now(tz='UTC').floor('D')
        
        conditions = {}
        
        # === ON-CHAIN CONDITIONS (Bitcoin Lab) ===
        
        # STH-MVRV < 1.0
        mvrv_sth = self._get_value('mvrv_sth', date)
        if mvrv_sth is not None:
            conditions['sth_mvrv'] = {
                'value': mvrv_sth,
                'threshold': 1.0,
                'met': mvrv_sth < 1.0,
                'source': 'on-chain'
            }
        
        # STH-SOPR < 1.0
        sopr_sth = self._get_value('sopr_sth', date)
        if sopr_sth is not None:
            conditions['sth_sopr'] = {
                'value': sopr_sth,
                'threshold': 1.0,
                'met': sopr_sth < 1.0,
                'source': 'on-chain'
            }
        
        # Price < STH Realized Price
        price = self._get_value('price', date)
        sth_rp = self._get_value('realized_price_sth', date)
        if price is not None and sth_rp is not None:
            conditions['price_below_sth_rp'] = {
                'value': price,
                'threshold': sth_rp,
                'met': price < sth_rp,
                'source': 'on-chain'
            }
        
        # NUPL < 0.25 (fear)
        nupl = self._get_value('nupl', date)
        if nupl is not None:
            conditions['nupl_fear'] = {
                'value': nupl,
                'threshold': 0.25,
                'met': nupl < 0.25,
                'source': 'on-chain'
            }
        
        # === DERIVATIVES CONDITIONS (Glassnode) ===
        
        # Funding rate ≤ 0
        funding = self._get_value('funding_rate', date)
        if funding is not None:
            conditions['funding_negative'] = {
                'value': funding,
                'threshold': 0.0,
                'met': funding <= 0,
                'source': 'derivatives'
            }
        
        # Long/Short liquidation ratio > 2.0
        long_liqs = self._get_value('liquidations_long', date)
        short_liqs = self._get_value('liquidations_short', date)
        if long_liqs is not None and short_liqs is not None and short_liqs > 0:
            liq_ratio = long_liqs / short_liqs
            conditions['liquidation_ratio'] = {
                'value': liq_ratio,
                'threshold': 2.0,
                'met': liq_ratio > 2.0,
                'source': 'derivatives'
            }
        
        # === SIGNAL AGGREGATION ===
        
        on_chain_conditions = [c for c in conditions.values() if c['source'] == 'on-chain']
        deriv_conditions = [c for c in conditions.values() if c['source'] == 'derivatives']
        
        on_chain_met = sum(1 for c in on_chain_conditions if c['met'])
        deriv_met = sum(1 for c in deriv_conditions if c['met'])
        
        total_met = on_chain_met + deriv_met
        total_conditions = len(conditions)
        
        # Signal logic
        if total_met >= 4 and on_chain_met >= 2:
            signal = 'STRONG_BUY'
            confidence = 'high'
        elif total_met >= 3 and on_chain_met >= 2:
            signal = 'BUY'
            confidence = 'medium'
        elif total_met >= 2:
            signal = 'WATCH'
            confidence = 'low'
        else:
            signal = 'WAIT'
            confidence = 'none'
        
        return {
            'date': date,
            'conditions': conditions,
            'on_chain_met': on_chain_met,
            'on_chain_total': len(on_chain_conditions),
            'derivatives_met': deriv_met,
            'derivatives_total': len(deriv_conditions),
            'total_met': total_met,
            'total_conditions': total_conditions,
            'signal': signal,
            'confidence': confidence
        }
    
    def _get_value(self, metric: str, date: pd.Timestamp) -> Optional[float]:
        """Get metric value for a date."""
        df = self.loader.load(metric)
        if df is None:
            return None
            
        mask = df.index <= date
        if not mask.any():
            return None
            
        return df.loc[mask, 'value'].iloc[-1]
    
    def generate_signals(
        self,
        start: str = "2020-01-01",
        end: str = None
    ) -> pd.DataFrame:
        """Generate Buy-the-Dip signals for a date range."""
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")
        
        dates = pd.date_range(start, end, freq='D', tz='UTC')
        
        records = []
        for date in dates:
            result = self.check_conditions(date)
            records.append({
                'date': date,
                'signal': result['signal'],
                'confidence': result['confidence'],
                'conditions_met': result['total_met'],
                'on_chain_met': result['on_chain_met'],
                'derivatives_met': result['derivatives_met'],
            })
        
        df = pd.DataFrame(records)
        df = df.set_index('date')
        
        return df
    
    def print_current_status(self):
        """Print current Buy-the-Dip status."""
        result = self.check_conditions()
        
        print("\n" + "="*60)
        print("BUY THE DIP STATUS")
        print("="*60)
        print(f"Date: {result['date'].date()}")
        print(f"\nSignal: {result['signal']} (confidence: {result['confidence']})")
        print(f"Conditions met: {result['total_met']}/{result['total_conditions']}")
        
        print("\n--- On-Chain Conditions ---")
        for name, cond in result['conditions'].items():
            if cond['source'] == 'on-chain':
                status = "✓" if cond['met'] else "✗"
                print(f"  {status} {name}: {cond['value']:.4f} "
                      f"(threshold: {cond['threshold']:.4f})")
        
        print("\n--- Derivatives Conditions ---")
        for name, cond in result['conditions'].items():
            if cond['source'] == 'derivatives':
                status = "✓" if cond['met'] else "✗"
                print(f"  {status} {name}: {cond['value']:.4f} "
                      f"(threshold: {cond['threshold']:.2f})")


# =============================================================================
# MAIN CLI
# =============================================================================

def main():
    """CLI for the unified trading system."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bitcoin Trading System")
    parser.add_argument("command", choices=[
        'status', 'explore', 'checkmate', 'signals', 'list'
    ])
    parser.add_argument("--metric", type=str, help="Metric name for explore")
    parser.add_argument("--start", type=str, default="2020-01-01", help="Start date")
    parser.add_argument("--end", type=str, help="End date")
    
    args = parser.parse_args()
    
    loader = UnifiedDataLoader()
    
    if args.command == 'status':
        btd = BuyTheDipStrategy(loader)
        btd.print_current_status()
        
    elif args.command == 'explore':
        if not args.metric:
            print("Please specify --metric")
            return
        stats = ExploratoryStats(loader)
        stats.run_full_analysis(args.metric)
        
    elif args.command == 'checkmate':
        framework = CheckmateFramework(loader)
        result = framework.calculate_composite()
        print(f"\nCheckmate Composite Score: {result['composite']:.3f}")
        print(f"Signal: {result['signal']}")
        print("\nScores by metric:")
        for metric, score in result['scores'].items():
            print(f"  {metric}: {score:.2f}")
            
    elif args.command == 'signals':
        btd = BuyTheDipStrategy(loader)
        df = btd.generate_signals(start=args.start, end=args.end)
        buy_signals = df[df['signal'].isin(['BUY', 'STRONG_BUY'])]
        print(f"\nBuy signals from {args.start}:")
        print(buy_signals.tail(20))
        
    elif args.command == 'list':
        available = loader.get_available_metrics()
        print("\nAvailable Metrics:")
        for source, metrics in available.items():
            print(f"\n{source.upper()} ({len(metrics)} metrics):")
            for m in sorted(metrics)[:20]:
                print(f"  {m}")
            if len(metrics) > 20:
                print(f"  ... and {len(metrics) - 20} more")


if __name__ == "__main__":
    main()
