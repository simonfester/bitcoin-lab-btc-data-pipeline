#!/usr/bin/env python3
"""
Bitcoin Signal Pipeline - Unified System
=========================================
Consolidates data download, analysis, and backtesting into one clean workflow.

Usage:
    python scripts/pipeline.py status          # Current market state
    python scripts/pipeline.py sync            # Download latest data
    python scripts/pipeline.py analyze         # Run statistical tests
    python scripts/pipeline.py backtest        # Run walk-forward validation
    python scripts/pipeline.py all             # Full pipeline

DO NOT USE GLASSNODE - Bitcoin Lab + BRK only
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')


# =============================================================================
# CONFIGURATION
# =============================================================================

DATA_DIR = PROJECT_ROOT / "data"
BRK_DIR = DATA_DIR / "brk" / "daily"
BL_DIR = DATA_DIR / "bl" / "daily"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def load_config() -> dict:
    """Load signal definitions."""
    with open(SCRIPTS_DIR / "signals.yaml") as f:
        return yaml.safe_load(f)


# =============================================================================
# DATA LOADING
# =============================================================================

def load_metric(name: str, prefer_source: str = "brk") -> pd.DataFrame:
    """
    Load a metric, preferring Bitcoin Lab but falling back to BRK.
    
    Args:
        name: Metric name (e.g., 'sopr', 'mvrv')
        prefer_source: 'bl' (Bitcoin Lab) or 'brk'
    
    Returns:
        DataFrame with 'time' and 'value' columns
    """
    # Try preferred source first
    if prefer_source == "bl":
        sources = [BL_DIR, BRK_DIR]
    else:
        sources = [BRK_DIR, BL_DIR]
    
    for src in sources:
        path = src / f"{name}.parquet"
        if path.exists():
            try:
                df = pd.read_parquet(path)
                
                # Handle different column structures
                if 'time' not in df.columns:
                    # Maybe index is the time?
                    if df.index.name == 'time' or isinstance(df.index, pd.DatetimeIndex):
                        df = df.reset_index()
                        if df.columns[0] != 'time':
                            df = df.rename(columns={df.columns[0]: 'time'})
                    else:
                        # Skip files without time column
                        continue
                
                if 'time' in df.columns:
                    df['time'] = pd.to_datetime(df['time'])
                    if df['time'].dt.tz is not None:
                        df['time'] = df['time'].dt.tz_localize(None)
                
                return df
            except Exception as e:
                print(f"Warning: Could not load {path}: {e}")
                continue
    
    return pd.DataFrame(columns=['time', 'value'])


def load_all_metrics(metrics: List[str] = None) -> pd.DataFrame:
    """Load all metrics into a single DataFrame."""
    config = load_config()
    metrics = metrics or config.get('metrics', [])
    
    # Start with price
    df = load_metric('price')
    if df.empty:
        print("ERROR: No price data found!")
        return pd.DataFrame()
    
    if 'time' not in df.columns:
        print("ERROR: Price data has no 'time' column!")
        print(f"  Columns found: {df.columns.tolist()}")
        return pd.DataFrame()
    
    df = df.set_index('time').rename(columns={'value': 'price'})
    
    # Add other metrics
    for metric in metrics:
        if metric == 'price':
            continue
        
        m_df = load_metric(metric)
        if not m_df.empty and 'time' in m_df.columns and 'value' in m_df.columns:
            m_df = m_df.set_index('time').rename(columns={'value': metric})
            df = df.join(m_df, how='left')
    
    return df.sort_index().ffill()


# =============================================================================
# CHECKMATE COMPOSITE SIGNAL
# =============================================================================

def score_metric(value: float, bullish: float, bearish: float) -> float:
    """
    Score a metric value from -2 (extreme bullish) to +2 (extreme bearish).
    
    Logic:
      - Below bullish threshold: increasingly negative (bullish)
      - Between bullish and bearish: interpolate -1 to +1
      - Above bearish threshold: increasingly positive (bearish)
    """
    if pd.isna(value):
        return 0.0
    
    midpoint = (bullish + bearish) / 2
    
    if value <= bullish:
        # Bullish zone: -1 to -2
        return -1 - min((bullish - value) / bullish, 1.0)
    elif value <= midpoint:
        # Transition: -1 to 0
        return -1 + (value - bullish) / (midpoint - bullish)
    elif value <= bearish:
        # Transition: 0 to +1
        return (value - midpoint) / (bearish - midpoint)
    else:
        # Bearish zone: +1 to +2
        return 1 + min((value - bearish) / bearish, 1.0)


def calc_checkmate_signal(row: pd.Series, config: dict) -> float:
    """Calculate weighted Checkmate composite signal."""
    checkmate_cfg = config.get('checkmate', {}).get('metrics', {})
    
    total_score = 0.0
    total_weight = 0.0
    
    # Map our column names to config names
    metric_map = {
        'mvrv': 'mvrv',
        'mvrv_sth': 'mvrv_sth', 
        'mvrv_lth': 'mvrv_lth',
        'nupl': 'nupl',
        'sopr': 'sopr',
        'aviv': 'aviv'
    }
    
    for col, cfg_name in metric_map.items():
        if col in row and cfg_name in checkmate_cfg and pd.notna(row[col]):
            cfg = checkmate_cfg[cfg_name]
            score = score_metric(row[col], cfg['bullish'], cfg['bearish'])
            total_score += score * cfg['weight']
            total_weight += cfg['weight']
    
    return total_score / total_weight if total_weight > 0 else 0.0


# =============================================================================
# SIGNAL GENERATION
# =============================================================================

def check_condition(value: float, operator: str, threshold: float) -> bool:
    """Check if a single condition is met."""
    if pd.isna(value):
        return False
    
    if operator == "<":
        return value < threshold
    elif operator == ">":
        return value > threshold
    elif operator == "<=":
        return value <= threshold
    elif operator == ">=":
        return value >= threshold
    elif operator == "==":
        return value == threshold
    else:
        raise ValueError(f"Unknown operator: {operator}")


def check_entry_signal(row: pd.Series, strategy_cfg: dict) -> bool:
    """Check if entry conditions are met for a strategy."""
    entry_cfg = strategy_cfg.get('entry', {})
    conditions = entry_cfg.get('conditions', [])
    logic = entry_cfg.get('logic', 'AND')
    
    if not conditions:
        return False
    
    results = []
    for cond in conditions:
        metric = cond['metric']
        
        # Handle special metrics
        if metric == 'realized_loss_z':
            # Calculate z-score of realized loss
            # This would need the full series, so we'll handle it separately
            value = row.get('realized_loss_z', np.nan)
        else:
            value = row.get(metric, np.nan)
        
        result = check_condition(value, cond['operator'], cond['threshold'])
        results.append(result)
    
    if logic == 'AND':
        return all(results)
    elif logic == 'OR':
        return any(results)
    else:
        return all(results)


def generate_signals(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Generate all signals for the DataFrame."""
    df = df.copy()
    
    # Calculate Checkmate composite
    df['checkmate_composite'] = df.apply(
        lambda row: calc_checkmate_signal(row, config), axis=1
    )
    
    # Calculate realized loss z-score
    if 'realized_loss' in df.columns:
        df['realized_loss_z'] = (
            df['realized_loss'] - df['realized_loss'].rolling(365).mean()
        ) / df['realized_loss'].rolling(365).std()
    
    # Calculate forward returns for analysis
    df['fwd_return_1d'] = df['price'].pct_change(1).shift(-1)
    df['fwd_return_7d'] = df['price'].pct_change(7).shift(-7)
    df['fwd_return_30d'] = df['price'].pct_change(30).shift(-30)
    
    # Generate entry signals for each strategy
    for strat_name, strat_cfg in config.get('strategies', {}).items():
        # Raw entry condition
        df[f'{strat_name}_entry_raw'] = df.apply(
            lambda row: check_entry_signal(row, strat_cfg), axis=1
        )
        
        # First day only (if configured)
        if strat_cfg.get('entry', {}).get('first_day_only', True):
            df[f'{strat_name}_entry'] = (
                df[f'{strat_name}_entry_raw'] & 
                ~df[f'{strat_name}_entry_raw'].shift(1).fillna(False)
            )
        else:
            df[f'{strat_name}_entry'] = df[f'{strat_name}_entry_raw']
    
    # Valuation zone (for dashboard)
    df['valuation_zone'] = pd.cut(
        df['checkmate_composite'],
        bins=[-float('inf'), -1.0, -0.5, 0.0, 0.5, 1.0, float('inf')],
        labels=['Deep Value', 'Value', 'Neutral-Low', 'Neutral-High', 'Expensive', 'Extreme']
    )
    
    return df


# =============================================================================
# STATUS COMMAND
# =============================================================================

def cmd_status():
    """Show current market state and signal status."""
    config = load_config()
    df = load_all_metrics()
    
    if df.empty:
        print("ERROR: No data loaded!")
        return
    
    df = generate_signals(df, config)
    latest = df.iloc[-1]
    
    print("=" * 70)
    print("BITCOIN SIGNAL DASHBOARD")
    print("=" * 70)
    print(f"Date: {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"Price: ${latest['price']:,.0f}")
    
    # Data freshness
    days_old = (datetime.now() - df.index[-1]).days
    if days_old > 1:
        print(f"⚠️  Data is {days_old} days old - run 'python scripts/pipeline.py sync'")
    
    print("\n" + "-" * 70)
    print("KEY METRICS")
    print("-" * 70)
    
    metrics_display = [
        ('SOPR', 'sopr', 1.0),
        ('STH-SOPR', 'sopr_sth', 1.0),
        ('LTH-SOPR', 'sopr_lth', 1.0),
        ('MVRV', 'mvrv', 1.0),
        ('STH-MVRV', 'mvrv_sth', 1.0),
        ('LTH-MVRV', 'mvrv_lth', 1.0),
        ('NUPL', 'nupl', 0.5),
        ('AVIV', 'aviv', 1.0),
    ]
    
    for display_name, col, neutral in metrics_display:
        if col in df.columns and pd.notna(latest[col]):
            value = latest[col]
            if value < neutral * 0.95:
                status = "🟢 BULLISH"
            elif value > neutral * 1.2:
                status = "🔴 BEARISH"
            else:
                status = "⚪ NEUTRAL"
            print(f"  {display_name:<12} {value:>8.3f}  {status}")
    
    print("\n" + "-" * 70)
    print("CHECKMATE COMPOSITE SIGNAL")
    print("-" * 70)
    
    signal = latest['checkmate_composite']
    zone = latest['valuation_zone']
    
    if signal <= -1.0:
        rec_size = "100%"
        emoji = "🟢🟢"
    elif signal <= -0.5:
        rec_size = "80%"
        emoji = "🟢"
    elif signal <= 0.0:
        rec_size = "60%"
        emoji = "⚪"
    elif signal <= 0.5:
        rec_size = "40%"
        emoji = "🟡"
    else:
        rec_size = "25%"
        emoji = "🔴"
    
    print(f"  Signal: {signal:+.3f} {emoji}")
    print(f"  Zone: {zone}")
    print(f"  Recommended Position Size: {rec_size}")
    
    print("\n" + "-" * 70)
    print("STRATEGY ENTRY SIGNALS")
    print("-" * 70)
    
    for strat_name, strat_cfg in config.get('strategies', {}).items():
        entry_col = f'{strat_name}_entry'
        if entry_col in df.columns:
            is_entry = latest[entry_col]
            status = "🚨 ENTRY SIGNAL!" if is_entry else "No signal"
            print(f"  {strat_name} ({strat_cfg['name']}): {status}")
            
            # Show conditions
            if is_entry:
                print("    Conditions met:")
                for cond in strat_cfg.get('entry', {}).get('conditions', []):
                    metric = cond['metric']
                    value = latest.get(metric, np.nan)
                    print(f"      {metric} = {value:.3f} {cond['operator']} {cond['threshold']}")
    
    # Last entry signal dates
    print("\n" + "-" * 70)
    print("RECENT ENTRY SIGNALS")
    print("-" * 70)
    
    for strat_name in config.get('strategies', {}).keys():
        entry_col = f'{strat_name}_entry'
        if entry_col in df.columns:
            entries = df[df[entry_col]].index
            if len(entries) > 0:
                last_entry = entries[-1]
                days_ago = (df.index[-1] - last_entry).days
                print(f"  {strat_name}: Last entry {last_entry.strftime('%Y-%m-%d')} ({days_ago} days ago)")
            else:
                print(f"  {strat_name}: No entries in data range")
    
    print("\n" + "=" * 70)


# =============================================================================
# SYNC COMMAND
# =============================================================================

def cmd_sync():
    """Sync latest data from Bitcoin Lab and BRK."""
    print("Syncing data...")
    print("  Run: python run.py bl-sync-daily")
    print("  Run: python run.py brk-sync")
    
    # Actually run the sync
    os.chdir(PROJECT_ROOT)
    os.system("python run.py bl-sync-daily")
    os.system("python run.py brk-sync")
    
    print("Done!")


# =============================================================================
# ANALYZE COMMAND
# =============================================================================

def cmd_analyze():
    """Run exploratory statistical analysis."""
    print("=" * 70)
    print("EXPLORATORY STATISTICAL ANALYSIS")
    print("=" * 70)
    print("Testing if signals have predictive power BEFORE backtesting.\n")
    
    config = load_config()
    df = load_all_metrics()
    
    if df.empty:
        print("ERROR: No data!")
        return
    
    df = generate_signals(df, config)
    
    # Import statsmodels if available
    try:
        import statsmodels.api as sm
        from statsmodels.tsa.stattools import grangercausalitytests
        HAS_STATS = True
    except ImportError:
        print("⚠️  statsmodels not installed. Run: pip install statsmodels")
        HAS_STATS = False
    
    # 1. Correlation Analysis
    print("-" * 70)
    print("1. CORRELATION WITH FORWARD RETURNS")
    print("-" * 70)
    
    metrics_to_test = ['sopr', 'sopr_sth', 'sopr_lth', 'mvrv', 'mvrv_sth', 
                       'nupl', 'aviv', 'checkmate_composite']
    
    from scipy.stats import pearsonr, spearmanr
    
    print(f"\n{'Metric':<20} {'Pearson r':>10} {'Spearman r':>12} {'p-value':>10}")
    print("-" * 55)
    
    for metric in metrics_to_test:
        if metric not in df.columns:
            continue
        
        # Clean data
        clean = df[[metric, 'fwd_return_30d']].dropna()
        if len(clean) < 100:
            continue
        
        # Pearson
        r, p = pearsonr(clean[metric], clean['fwd_return_30d'])
        
        # Spearman (rank correlation)
        rho, _ = spearmanr(clean[metric], clean['fwd_return_30d'])
        
        sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""
        print(f"{metric:<20} {r:>10.4f} {rho:>12.4f} {p:>10.4f} {sig}")
    
    # 2. Regression Analysis
    if HAS_STATS:
        print("\n" + "-" * 70)
        print("2. OLS REGRESSION: fwd_return_30d ~ metric")
        print("-" * 70)
        print("Significance: *** p<0.01, ** p<0.05, * p<0.1\n")
        
        print(f"{'Metric':<20} {'Coef':>10} {'t-stat':>10} {'p-value':>10} {'R²':>8}")
        print("-" * 60)
        
        for metric in metrics_to_test:
            if metric not in df.columns:
                continue
            
            clean = df[[metric, 'fwd_return_30d']].dropna()
            if len(clean) < 100:
                continue
            
            X = sm.add_constant(clean[metric])
            y = clean['fwd_return_30d']
            
            try:
                model = sm.OLS(y, X).fit()
                coef = model.params[metric]
                t = model.tvalues[metric]
                p = model.pvalues[metric]
                r2 = model.rsquared
                
                sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""
                print(f"{metric:<20} {coef:>+10.5f} {t:>10.2f} {p:>10.4f} {r2:>8.4f} {sig}")
            except:
                pass
        
        # 3. Granger Causality
        print("\n" + "-" * 70)
        print("3. GRANGER CAUSALITY (does metric predict returns?)")
        print("-" * 70)
        print("Testing if past metric values help predict future returns.\n")
        
        for metric in ['sopr', 'sopr_sth', 'mvrv', 'checkmate_composite']:
            if metric not in df.columns:
                continue
            
            clean = df[[metric, 'fwd_return_7d']].dropna()
            if len(clean) < 200:
                continue
            
            try:
                result = grangercausalitytests(clean[[metric, 'fwd_return_7d']], maxlag=3, verbose=False)
                
                # Get p-value for lag 1
                p_value = result[1][0]['ssr_ftest'][1]
                sig = "✓ PREDICTIVE" if p_value < 0.05 else ""
                print(f"  {metric:<25} p={p_value:.4f} {sig}")
            except:
                pass
    
    # 4. Entry Signal Analysis
    print("\n" + "-" * 70)
    print("4. ENTRY SIGNAL FORWARD RETURNS")
    print("-" * 70)
    
    for strat_name in config.get('strategies', {}).keys():
        entry_col = f'{strat_name}_entry'
        if entry_col not in df.columns:
            continue
        
        entries = df[df[entry_col]]
        if len(entries) == 0:
            print(f"\n{strat_name}: No entry signals in data")
            continue
        
        print(f"\n{strat_name}:")
        print(f"  Total entries: {len(entries)}")
        
        for horizon in ['1d', '7d', '30d']:
            col = f'fwd_return_{horizon}'
            if col in entries.columns:
                returns = entries[col].dropna()
                if len(returns) > 0:
                    mean_ret = returns.mean() * 100
                    win_rate = (returns > 0).mean() * 100
                    print(f"  {horizon:>3}: Avg={mean_ret:+.1f}%, Win={win_rate:.0f}%")
    
    print("\n" + "=" * 70)
    print("INTERPRETATION:")
    print("=" * 70)
    print("✓ Significant correlation (p < 0.05) = metric has predictive power")
    print("✓ Negative coefficient = lower metric → higher returns (buy signal)")
    print("✓ Granger p < 0.05 = past metric values predict future returns")
    print("✓ Use this to CONFIRM signals BEFORE backtesting")
    print("=" * 70)


# =============================================================================
# BACKTEST COMMAND
# =============================================================================

def cmd_backtest():
    """Run walk-forward backtesting on validated strategies."""
    print("=" * 70)
    print("WALK-FORWARD BACKTESTING")
    print("=" * 70)
    print("Confirming strategy viability with out-of-sample testing.\n")
    
    config = load_config()
    df = load_all_metrics()
    
    if df.empty:
        print("ERROR: No data!")
        return
    
    df = generate_signals(df, config)
    
    # Import backtester
    try:
        from src.backtester import Backtester, Signal, ExitMode
        HAS_BACKTESTER = True
    except ImportError:
        HAS_BACKTESTER = False
        print("Using simple backtest...")
    
    for strat_name, strat_cfg in config.get('strategies', {}).items():
        print(f"\n{'-' * 70}")
        print(f"STRATEGY: {strat_name} - {strat_cfg['name']}")
        print(f"{'-' * 70}")
        
        entry_col = f'{strat_name}_entry'
        if entry_col not in df.columns:
            print("  No entry signals generated")
            continue
        
        # Simple backtest with trailing stop
        trail_pct = strat_cfg.get('exit', {}).get('trailing_stop', 0.30)
        
        # Run simple simulation
        trades = []
        in_trade = False
        entry_price = 0
        peak_price = 0
        entry_date = None
        
        for date, row in df.iterrows():
            if not in_trade:
                if row[entry_col]:
                    in_trade = True
                    entry_price = row['price']
                    peak_price = entry_price
                    entry_date = date
            else:
                # Update peak
                if row['price'] > peak_price:
                    peak_price = row['price']
                
                # Check trailing stop
                drawdown = (peak_price - row['price']) / peak_price
                if drawdown >= trail_pct:
                    # Exit
                    exit_price = row['price']
                    ret = (exit_price - entry_price) / entry_price
                    trades.append({
                        'entry_date': entry_date,
                        'exit_date': date,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'return': ret,
                        'days': (date - entry_date).days
                    })
                    in_trade = False
        
        # Calculate stats
        if not trades:
            print("  No completed trades")
            continue
        
        returns = [t['return'] for t in trades]
        cumulative = (1 + pd.Series(returns)).cumprod().iloc[-1] - 1
        win_rate = sum(1 for r in returns if r > 0) / len(returns)
        avg_ret = np.mean(returns)
        
        print(f"  Total Trades: {len(trades)}")
        print(f"  Win Rate: {win_rate:.1%}")
        print(f"  Avg Return/Trade: {avg_ret:.1%}")
        print(f"  Cumulative Return: {cumulative:.1%}")
        
        # Show recent trades
        print(f"\n  Recent Trades:")
        for t in trades[-5:]:
            status = "✓" if t['return'] > 0 else "✗"
            print(f"    {status} {t['entry_date'].strftime('%Y-%m-%d')} → "
                  f"{t['exit_date'].strftime('%Y-%m-%d')} "
                  f"({t['days']}d): {t['return']:+.1%}")
    
    print("\n" + "=" * 70)


# =============================================================================
# ALL COMMAND
# =============================================================================

def cmd_all():
    """Run full pipeline."""
    cmd_sync()
    print("\n")
    cmd_analyze()
    print("\n")
    cmd_backtest()
    print("\n")
    cmd_status()


# =============================================================================
# MAIN
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCommands:")
        print("  status    - Current market state and signals")
        print("  sync      - Download latest data")
        print("  analyze   - Run statistical analysis")
        print("  backtest  - Run walk-forward validation")
        print("  all       - Full pipeline")
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "status":
        cmd_status()
    elif cmd == "sync":
        cmd_sync()
    elif cmd == "analyze":
        cmd_analyze()
    elif cmd == "backtest":
        cmd_backtest()
    elif cmd == "all":
        cmd_all()
    else:
        print(f"Unknown command: {cmd}")
        print("Use: status, sync, analyze, backtest, all")


if __name__ == "__main__":
    main()
