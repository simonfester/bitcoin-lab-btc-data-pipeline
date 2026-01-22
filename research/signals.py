#!/usr/bin/env python3
"""
Signal Generator - Calculates and saves trading signals to parquet files.
=========================================================================

This script is the single source of truth for signal calculation.
Both the dashboard and backtesting framework read from these files.

Usage:
    python signals.py              # Generate all signals
    python signals.py --watch      # Auto-refresh every 5 minutes
    
Output files (in data/signals/):
    - checkmate.parquet           # Checkmate framework composite score
    - entry_signals.parquet       # Entry signal triggers
    - exit_signals.parquet        # Exit signal triggers
    - valuation_zones.parquet     # Price zone classifications
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sys
import time

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "brk" / "daily"
SIGNALS_DIR = PROJECT_ROOT / "data" / "signals"
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# DATA LOADING
# =============================================================================

def load_metric(name: str) -> pd.DataFrame:
    """Load metric from parquet, normalize to time/value columns."""
    path = DATA_DIR / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame(columns=['time', 'value'])
    
    df = pd.read_parquet(path)
    
    # Normalize time column
    time_col = None
    if 'time' in df.columns:
        time_col = 'time'
    elif 'date' in df.columns:
        time_col = 'date'
    elif isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        time_col = df.columns[0]
    
    if time_col and time_col != 'time':
        df = df.rename(columns={time_col: 'time'})
    
    if 'time' not in df.columns:
        return pd.DataFrame(columns=['time', 'value'])
    
    # Normalize value column
    if 'value' not in df.columns:
        for col in df.columns:
            if col != 'time' and pd.api.types.is_numeric_dtype(df[col]):
                df = df.rename(columns={col: 'value'})
                break
    
    if 'value' not in df.columns:
        return pd.DataFrame(columns=['time', 'value'])
    
    df['time'] = pd.to_datetime(df['time'])
    if df['time'].dt.tz is not None:
        df['time'] = df['time'].dt.tz_localize(None)
    
    return df[['time', 'value']].sort_values('time').reset_index(drop=True)


def load_all_metrics() -> dict:
    """Load all metrics needed for signal generation."""
    metrics = [
        # Price
        'price',
        # MVRV family
        'mvrv', 'mvrv_sth', 'mvrv_lth',
        # SOPR family
        'sopr', 'sopr_sth', 'sopr_lth', 'sopr_adjusted',
        # NUPL family
        'nupl', 'nupl_sth', 'nupl_lth',
        # Cost basis levels
        'realized_price', 'true_market_mean_price', 'realized_price_sth', 'vaulted_price',
        # Checkmate additions
        'puell_multiple', 'sell_side_risk',
        # Supply
        'supply_lth', 'supply_sth', 'supply_total', 'supply_in_profit',
        # Other
        'realized_loss', 'realized_profit',
    ]
    
    data = {}
    for m in metrics:
        data[m] = load_metric(m)
    return data

# =============================================================================
# CHECKMATE COMPOSITE SIGNAL (James Check Framework)
# =============================================================================

def calculate_checkmate_signal(data: dict) -> pd.DataFrame:
    """
    Calculate the Checkmate composite signal time series.
    
    8-metric framework:
    - MVRV, STH-MVRV (valuation)
    - SOPR, STH-SOPR, LTH-SOPR (spending behavior)
    - NUPL (unrealized P&L)
    - Puell Multiple (miner stress)
    - Sell-side Risk (market structure)
    
    Returns DataFrame with columns:
        time, composite, zone, position_size,
        mvrv, sth_mvrv, sopr, sth_sopr, lth_sopr, nupl, puell, sell_side_risk
    """
    # Get price as base timeline
    price_df = data.get('price', pd.DataFrame())
    if price_df.empty:
        return pd.DataFrame()
    
    # Create result DataFrame
    result = price_df[['time']].copy()
    result = result.set_index('time')
    
    # Add all component metrics
    components = {
        'mvrv': 'mvrv',
        'sth_mvrv': 'mvrv_sth',
        'sopr': 'sopr',
        'sth_sopr': 'sopr_sth',
        'lth_sopr': 'sopr_lth',
        'nupl': 'nupl',
        'puell': 'puell_multiple',
        'sell_side_risk': 'sell_side_risk',
    }
    
    for col_name, metric_name in components.items():
        df = data.get(metric_name, pd.DataFrame())
        if not df.empty:
            df = df.set_index('time')
            result[col_name] = df['value']
    
    result = result.reset_index()
    
    # Calculate individual scores for each row
    def calc_row_score(row):
        scores = []
        weights = []
        
        # MVRV: < 1 = accumulate (-1), > 3 = distribute (+1), center at 2
        if pd.notna(row.get('mvrv')):
            score = np.clip((row['mvrv'] - 2) / 2, -1, 1)
            scores.append(score)
            weights.append(1.5)
        
        # STH-MVRV: < 1 = STH underwater, > 1.3 = STH profit (key signal)
        if pd.notna(row.get('sth_mvrv')):
            score = np.clip((row['sth_mvrv'] - 1) / 0.5, -1, 1)
            scores.append(score)
            weights.append(2.0)  # Highest weight
        
        # SOPR: < 1 = loss, > 1.05 = profit taking
        if pd.notna(row.get('sopr')):
            score = np.clip((row['sopr'] - 1) / 0.1, -1, 1)
            scores.append(score)
            weights.append(1.0)
        
        # STH-SOPR: < 1 = STH capitulating, > 1.02 = STH profit
        if pd.notna(row.get('sth_sopr')):
            score = np.clip((row['sth_sopr'] - 1) / 0.05, -1, 1)
            scores.append(score)
            weights.append(1.5)
        
        # LTH-SOPR: > 1.5 = LTH distribution
        if pd.notna(row.get('lth_sopr')):
            score = np.clip((row['lth_sopr'] - 1) / 0.5, -1, 1)
            scores.append(score)
            weights.append(1.0)
        
        # NUPL: < 0 = underwater, > 0.75 = euphoria
        if pd.notna(row.get('nupl')):
            score = np.clip((row['nupl'] - 0.4) / 0.4, -1, 1)
            scores.append(score)
            weights.append(1.2)
        
        # Puell: < 0.5 = miner stress, > 1.5 = miner euphoria
        if pd.notna(row.get('puell')):
            score = np.clip((row['puell'] - 1) / 1, -1, 1)
            scores.append(score)
            weights.append(1.0)
        
        # Sell-side Risk: low = calm, high = volatility
        if pd.notna(row.get('sell_side_risk')):
            score = np.clip((row['sell_side_risk'] - 0.1) / 0.3, -1, 1)
            scores.append(score)
            weights.append(0.5)
        
        if not scores:
            return pd.Series({'composite': np.nan, 'zone': 'UNKNOWN', 'position_size': 1.0})
        
        # Weighted average
        composite = np.average(scores, weights=weights)
        composite = np.clip(composite, -1, 1)
        
        # Determine zone
        if composite <= -0.5:
            zone, position_size = 'STRONG_ACCUMULATE', 1.5
        elif composite <= -0.2:
            zone, position_size = 'ACCUMULATE', 1.25
        elif composite <= 0.2:
            zone, position_size = 'NEUTRAL', 1.0
        elif composite <= 0.5:
            zone, position_size = 'DISTRIBUTE', 0.5
        else:
            zone, position_size = 'STRONG_DISTRIBUTE', 0.25
        
        return pd.Series({'composite': composite, 'zone': zone, 'position_size': position_size})
    
    # Apply to each row
    score_cols = result.apply(calc_row_score, axis=1)
    result = pd.concat([result, score_cols], axis=1)
    
    return result


# =============================================================================
# VALUATION ZONES
# =============================================================================

def calculate_valuation_zones(data: dict) -> pd.DataFrame:
    """
    Calculate price valuation zones over time.
    
    Zones based on price relative to cost basis levels:
    - EXTREME_BEAR: Price < Realized Price (2x position)
    - UNDERVALUED: RP < Price < True Market Mean (1.5x)
    - FAIR_VALUE: TMM < Price < STH Cost Basis (1x)
    - OVERVALUED: STH < Price < Vaulted Price (0.5x)
    - EXTREME_BULL: Price > Vaulted Price (0.25x)
    """
    price_df = data.get('price', pd.DataFrame())
    if price_df.empty:
        return pd.DataFrame()
    
    result = price_df.copy()
    result.columns = ['time', 'price']
    result = result.set_index('time')
    
    # Add cost basis levels
    for col, metric in [
        ('realized_price', 'realized_price'),
        ('true_market_mean', 'true_market_mean_price'),
        ('sth_cost_basis', 'realized_price_sth'),
        ('vaulted_price', 'vaulted_price'),
    ]:
        df = data.get(metric, pd.DataFrame())
        if not df.empty:
            df = df.set_index('time')
            result[col] = df['value']
    
    result = result.reset_index()
    
    def get_zone(row):
        price = row['price']
        rp = row.get('realized_price')
        tmm = row.get('true_market_mean')
        sth = row.get('sth_cost_basis')
        vp = row.get('vaulted_price')
        
        if pd.isna(price) or pd.isna(rp):
            return pd.Series({'zone': 'UNKNOWN', 'position_mult': 1.0})
        
        if price < rp:
            return pd.Series({'zone': 'EXTREME_BEAR', 'position_mult': 2.0})
        elif pd.notna(tmm) and price < tmm:
            return pd.Series({'zone': 'UNDERVALUED', 'position_mult': 1.5})
        elif pd.notna(sth) and price < sth:
            return pd.Series({'zone': 'FAIR_VALUE', 'position_mult': 1.0})
        elif pd.notna(vp) and price < vp:
            return pd.Series({'zone': 'OVERVALUED', 'position_mult': 0.5})
        else:
            return pd.Series({'zone': 'EXTREME_BULL', 'position_mult': 0.25})
    
    zone_cols = result.apply(get_zone, axis=1)
    result = pd.concat([result, zone_cols], axis=1)
    
    return result


# =============================================================================
# ENTRY/EXIT SIGNALS
# =============================================================================

def calculate_entry_signals(data: dict) -> pd.DataFrame:
    """
    Calculate entry signal triggers over time.
    
    STRAT-002/004 Entry Conditions:
    - SOPR < 1 (market selling at loss)
    - STH-SOPR < 1 (short-term holders capitulating)
    - Realized Loss Z-score > 0.5 (elevated loss-taking)
    """
    price_df = data.get('price', pd.DataFrame())
    if price_df.empty:
        return pd.DataFrame()
    
    result = price_df[['time']].copy()
    result = result.set_index('time')
    
    # Add metrics
    for col, metric in [
        ('sopr', 'sopr'),
        ('sth_sopr', 'sopr_sth'),
        ('realized_loss', 'realized_loss'),
    ]:
        df = data.get(metric, pd.DataFrame())
        if not df.empty:
            df = df.set_index('time')
            result[col] = df['value']
    
    result = result.reset_index()
    
    # Calculate z-score for realized loss (365d rolling)
    if 'realized_loss' in result.columns:
        result['realized_loss_z'] = (
            (result['realized_loss'] - result['realized_loss'].rolling(365, min_periods=30).mean()) /
            result['realized_loss'].rolling(365, min_periods=30).std()
        )
    
    # Calculate signal triggers
    result['sig_sopr'] = result['sopr'] < 1.0 if 'sopr' in result.columns else False
    result['sig_sth_sopr'] = result['sth_sopr'] < 1.0 if 'sth_sopr' in result.columns else False
    result['sig_realized_loss_z'] = result['realized_loss_z'] > 0.5 if 'realized_loss_z' in result.columns else False
    
    # Combined entry signal (all conditions met)
    result['entry_signal'] = (
        result['sig_sopr'] & 
        result['sig_sth_sopr'] & 
        result['sig_realized_loss_z']
    )
    
    # Entry score (0-3 based on how many signals active)
    result['entry_score'] = (
        result['sig_sopr'].astype(int) + 
        result['sig_sth_sopr'].astype(int) + 
        result['sig_realized_loss_z'].astype(int)
    )
    
    return result


def calculate_exit_signals(data: dict) -> pd.DataFrame:
    """
    Calculate exit signal triggers over time.
    
    Distribution Exit Conditions:
    - LTH-SOPR > 1.5 (long-term holders taking profits)
    - MVRV-Z > 2.5 (market historically expensive)
    - NUPL > 0.75 (extreme unrealized profit)
    """
    price_df = data.get('price', pd.DataFrame())
    if price_df.empty:
        return pd.DataFrame()
    
    result = price_df[['time']].copy()
    result = result.set_index('time')
    
    # Add metrics
    for col, metric in [
        ('lth_sopr', 'sopr_lth'),
        ('mvrv', 'mvrv'),
        ('nupl', 'nupl'),
    ]:
        df = data.get(metric, pd.DataFrame())
        if not df.empty:
            df = df.set_index('time')
            result[col] = df['value']
    
    result = result.reset_index()
    
    # Calculate MVRV-Z (4-year rolling z-score)
    if 'mvrv' in result.columns:
        result['mvrv_z'] = (
            (result['mvrv'] - result['mvrv'].rolling(1460, min_periods=365).mean()) /
            result['mvrv'].rolling(1460, min_periods=365).std()
        )
    
    # Calculate signal triggers
    result['sig_lth_sopr'] = result['lth_sopr'] > 1.5 if 'lth_sopr' in result.columns else False
    result['sig_mvrv_z'] = result['mvrv_z'] > 2.5 if 'mvrv_z' in result.columns else False
    result['sig_nupl'] = result['nupl'] > 0.75 if 'nupl' in result.columns else False
    
    # Combined exit signal (2+ conditions met)
    result['exit_signal'] = (
        (result['sig_lth_sopr'].astype(int) + 
         result['sig_mvrv_z'].astype(int) + 
         result['sig_nupl'].astype(int)) >= 2
    )
    
    # Exit score (0-3)
    result['exit_score'] = (
        result['sig_lth_sopr'].astype(int) + 
        result['sig_mvrv_z'].astype(int) + 
        result['sig_nupl'].astype(int)
    )
    
    return result


# =============================================================================
# MAIN
# =============================================================================

def generate_all_signals():
    """Generate all signals and save to parquet files."""
    print("=" * 60)
    print("Signal Generator")
    print("=" * 60)
    print(f"Data source: {DATA_DIR}")
    print(f"Output: {SIGNALS_DIR}")
    print()
    
    # Load data
    print("Loading metrics...")
    data = load_all_metrics()
    loaded = sum(1 for df in data.values() if not df.empty)
    print(f"  Loaded {loaded}/{len(data)} metrics")
    print()
    
    # Generate signals
    signals = {}
    
    print("Generating Checkmate composite...")
    signals['checkmate'] = calculate_checkmate_signal(data)
    if not signals['checkmate'].empty:
        latest = signals['checkmate'].iloc[-1]
        print(f"  Latest: {latest['composite']:.3f} ({latest['zone']}) → {latest['position_size']}x")
    
    print("Generating valuation zones...")
    signals['valuation'] = calculate_valuation_zones(data)
    if not signals['valuation'].empty:
        latest = signals['valuation'].iloc[-1]
        print(f"  Latest: {latest['zone']} ({latest['position_mult']}x)")
    
    print("Generating entry signals...")
    signals['entry'] = calculate_entry_signals(data)
    if not signals['entry'].empty:
        latest = signals['entry'].iloc[-1]
        print(f"  Latest: score={latest['entry_score']}/3, triggered={latest['entry_signal']}")
    
    print("Generating exit signals...")
    signals['exit'] = calculate_exit_signals(data)
    if not signals['exit'].empty:
        latest = signals['exit'].iloc[-1]
        print(f"  Latest: score={latest['exit_score']}/3, triggered={latest['exit_signal']}")
    
    print()
    
    # Save to parquet
    print("Saving signals...")
    for name, df in signals.items():
        if df.empty:
            print(f"  ✗ {name}: empty")
            continue
        
        path = SIGNALS_DIR / f"{name}.parquet"
        df.to_parquet(path, index=False)
        
        # Get date range
        if 'time' in df.columns:
            start = df['time'].min().strftime('%Y-%m-%d')
            end = df['time'].max().strftime('%Y-%m-%d')
            print(f"  ✓ {name}: {len(df)} rows ({start} to {end})")
        else:
            print(f"  ✓ {name}: {len(df)} rows")
    
    print()
    print("=" * 60)
    print("Done!")
    print("=" * 60)
    
    return signals


def main():
    if '--watch' in sys.argv:
        print("Watch mode: regenerating every 5 minutes...")
        while True:
            generate_all_signals()
            print(f"\nNext update in 5 minutes... (Ctrl+C to stop)\n")
            time.sleep(300)
    else:
        generate_all_signals()


if __name__ == "__main__":
    main()
