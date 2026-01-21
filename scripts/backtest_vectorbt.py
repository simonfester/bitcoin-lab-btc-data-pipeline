#!/usr/bin/env python3
"""
VectorBT Independent Verification of James Check Framework
===========================================================
Independent verification to check for look-ahead bias and bugs.

Usage:
    python backtest_vectorbt.py              # Full verification
    python backtest_vectorbt.py --debug      # Show detailed trades
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import warnings
warnings.filterwarnings('ignore')

# Try to import vectorbt
try:
    import vectorbt as vbt
    print("✓ VectorBT loaded")
except ImportError:
    print("✗ VectorBT not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "vectorbt"])
    import vectorbt as vbt
    print("✓ VectorBT installed and loaded")

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "brk" / "daily"
GLASSNODE_DIR = PROJECT_ROOT / "data" / "glassnode" / "daily"

# Split dates
TRAIN_END = '2022-12-31'
TEST_START = '2023-01-01'

# Costs
FEES = 0.001  # 0.1%
SLIPPAGE = 0.001  # 0.1%

# =============================================================================
# DATA LOADING
# =============================================================================

def load_metric(name: str, source: str = "brk") -> pd.Series:
    """Load metric as time-indexed Series."""
    if source == "brk":
        path = DATA_DIR / f"{name}.parquet"
    elif source == "glassnode":
        path = GLASSNODE_DIR / f"{name}.parquet"
    else:
        return pd.Series(dtype=float)

    if not path.exists():
        return pd.Series(dtype=float)

    df = pd.read_parquet(path)

    # Normalize
    if 'time' not in df.columns and isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        if len(df.columns) == 2:
            df.columns = ['time', 'value']

    if 'value' not in df.columns:
        for col in df.columns:
            if col != 'time' and pd.api.types.is_numeric_dtype(df[col]):
                df['value'] = df[col]
                break

    if 'time' in df.columns and 'value' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        df = df.set_index('time')['value']
        df = df.sort_index()
        return df

    return pd.Series(dtype=float)


def load_all_data() -> pd.DataFrame:
    """Load all metrics into aligned DataFrame."""
    print("\nLoading data...")

    metrics = {
        'price': ('price', 'brk'),
        'mvrv': ('mvrv', 'brk'),
        'mvrv_sth': ('mvrv_sth', 'brk'),
        'mvrv_lth': ('mvrv_lth', 'brk'),
        'sopr': ('sopr', 'brk'),
        'sopr_sth': ('sopr_sth', 'brk'),
        'sopr_lth': ('sopr_lth', 'brk'),
        'realized_profit': ('realized_profit', 'brk'),
        'realized_loss': ('realized_loss', 'brk'),
        'puell': ('puell_multiple', 'brk'),
        'price_200sma': ('price_200d_sma', 'brk'),
        'funding': ('funding_rate', 'glassnode'),
        'liq_long': ('liquidations_long', 'glassnode'),
        'liq_short': ('liquidations_short', 'glassnode'),
    }

    df_dict = {}
    for name, (metric, source) in metrics.items():
        series = load_metric(metric, source)
        if not series.empty:
            df_dict[name] = series
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name} (missing)")

    # Combine all series
    df = pd.DataFrame(df_dict)

    # Forward fill missing values (common in derivatives data)
    df = df.fillna(method='ffill')

    print(f"\nData loaded: {len(df)} days from {df.index[0]} to {df.index[-1]}")

    return df


# =============================================================================
# SIGNAL GENERATION (NO LOOK-AHEAD BIAS)
# =============================================================================

def calculate_rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """Calculate rolling z-score using ONLY past data."""
    mean = series.rolling(window, min_periods=30).mean()
    std = series.rolling(window, min_periods=30).std()
    return (series - mean) / std


def generate_buy_the_dip_entries(df: pd.DataFrame) -> pd.Series:
    """
    Generate Buy The Dip entry signals.
    CRITICAL: Each row only uses data available UP TO that date.
    """
    print("\nGenerating Buy The Dip signals...")

    # Condition 1: STH-MVRV < 1.0
    c1 = df['mvrv_sth'] < 1.0

    # Condition 2: STH-SOPR < 1.0
    c2 = df['sopr_sth'] < 1.0

    # Condition 3: RP/L Ratio < 1.0
    rplr = df['realized_profit'] / df['realized_loss']
    c3 = rplr < 1.0

    # Condition 4: Funding <= 0
    c4 = df['funding'] <= 0.0

    # Condition 5: Long Liq > Short Liq
    liq_ratio = df['liq_long'] / df['liq_short']
    c5 = liq_ratio > 1.0

    # Count conditions
    count = c1.astype(int) + c2.astype(int) + c3.astype(int) + c4.astype(int) + c5.astype(int)

    # Entry when 4+ conditions met
    entries = count >= 4

    print(f"  Generated {entries.sum()} entry signals")

    return entries


def generate_lth_distribution_exits(df: pd.DataFrame) -> pd.Series:
    """Generate LTH Distribution exit signals."""
    print("Generating LTH Distribution exits...")

    exits = (df['mvrv'] > 2.0) & (df['sopr_lth'] > 1.5)

    print(f"  Generated {exits.sum()} exit signals")

    return exits


def generate_8metric_exits(df: pd.DataFrame, threshold: int = 6) -> pd.Series:
    """Generate 8-Metric exit signals (6/8 threshold)."""
    print(f"Generating 8-Metric exits ({threshold}/8)...")

    # Calculate Z-scores using ONLY past data
    mvrv_z = calculate_rolling_zscore(df['mvrv'], 1460)
    mvrv_sth_z = calculate_rolling_zscore(df['mvrv_sth'], 365)
    sopr_z = calculate_rolling_zscore(df['sopr'], 365)
    sopr_sth_z = calculate_rolling_zscore(df['sopr_sth'], 365)
    puell_z = calculate_rolling_zscore(df['puell'], 365)

    # Mayer Multiple
    mayer = df['price'] / df['price_200sma']
    mayer_z = calculate_rolling_zscore(mayer, 365)

    # Funding Z
    funding_z = calculate_rolling_zscore(df['funding'], 365)

    # Count triggers
    count = (
        (mvrv_z > 1.5).astype(int) +
        (mvrv_sth_z > 1.25).astype(int) +
        (sopr_z > 1.5).astype(int) +
        (sopr_sth_z > 1.0).astype(int) +
        (mayer_z > 1.0).astype(int) +
        (puell_z > 1.5).astype(int) +
        (funding_z > 1.5).astype(int)
    )

    exits = count >= threshold

    print(f"  Generated {exits.sum()} exit signals")

    return exits


# =============================================================================
# VECTORBT BACKTESTING
# =============================================================================

def backtest_with_vectorbt(df: pd.DataFrame, entries: pd.Series, exits: pd.Series,
                           name: str = "Strategy") -> dict:
    """
    Run backtest using VectorBT.
    VectorBT handles position sizing, fees, and statistics automatically.
    """
    print(f"\nBacktesting: {name}")

    # Create portfolio with VectorBT
    pf = vbt.Portfolio.from_signals(
        close=df['price'],
        entries=entries,
        exits=exits,
        fees=FEES,
        slippage=SLIPPAGE,
        init_cash=10000,
        freq='1D'
    )

    # Get statistics
    stats = pf.stats()

    # Extract key metrics
    total_return = pf.total_return() * 100
    num_trades = pf.trades.count()
    win_rate = pf.trades.win_rate() * 100 if num_trades > 0 else 0
    sharpe = pf.sharpe_ratio()
    max_dd = pf.max_drawdown() * 100

    print(f"  Total Return: {total_return:.1f}%")
    print(f"  Trades: {num_trades}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Sharpe: {sharpe:.2f}")
    print(f"  Max DD: {max_dd:.1f}%")

    return {
        'name': name,
        'total_return': total_return,
        'num_trades': num_trades,
        'win_rate': win_rate,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'portfolio': pf,
        'stats': stats
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    debug = '--debug' in sys.argv

    print("=" * 80)
    print("VECTORBT INDEPENDENT VERIFICATION")
    print("=" * 80)

    # Load data
    df = load_all_data()

    # Split train/test
    train_df = df[df.index <= TRAIN_END].copy()
    test_df = df[df.index >= TEST_START].copy()

    print(f"\nTrain: {train_df.index[0]} to {train_df.index[-1]} ({len(train_df)} days)")
    print(f"Test:  {test_df.index[0]} to {test_df.index[-1]} ({len(test_df)} days)")

    # Generate signals
    print("\n" + "=" * 80)
    print("SIGNAL GENERATION")
    print("=" * 80)

    # Entry signals
    train_entries = generate_buy_the_dip_entries(train_df)
    test_entries = generate_buy_the_dip_entries(test_df)

    # Exit signals
    strategies = []

    # 1. LTH Distribution
    train_lth_exits = generate_lth_distribution_exits(train_df)
    test_lth_exits = generate_lth_distribution_exits(test_df)

    # 2. 8-Metric High Risk (6/8)
    train_8m_exits = generate_8metric_exits(train_df, threshold=6)
    test_8m_exits = generate_8metric_exits(test_df, threshold=6)

    # 3. 8-Metric Caution (4/8)
    train_4m_exits = generate_8metric_exits(train_df, threshold=4)
    test_4m_exits = generate_8metric_exits(test_df, threshold=4)

    # Run backtests
    print("\n" + "=" * 80)
    print("TRAIN PERIOD BACKTESTS (2009-2022)")
    print("=" * 80)

    train_lth = backtest_with_vectorbt(train_df, train_entries, train_lth_exits,
                                       "LTH Distribution")
    train_8m = backtest_with_vectorbt(train_df, train_entries, train_8m_exits,
                                      "8-Metric High Risk (6/8)")
    train_4m = backtest_with_vectorbt(train_df, train_entries, train_4m_exits,
                                      "8-Metric Caution (4/8)")

    print("\n" + "=" * 80)
    print("TEST PERIOD BACKTESTS (2023-2026) - OUT OF SAMPLE")
    print("=" * 80)

    test_lth = backtest_with_vectorbt(test_df, test_entries, test_lth_exits,
                                      "LTH Distribution")
    test_8m = backtest_with_vectorbt(test_df, test_entries, test_8m_exits,
                                     "8-Metric High Risk (6/8)")
    test_4m = backtest_with_vectorbt(test_df, test_entries, test_4m_exits,
                                     "8-Metric Caution (4/8)")

    # Buy and hold
    print("\nBenchmark: Buy & Hold")
    bh_train = (train_df['price'].iloc[-1] / train_df['price'].iloc[0] - 1) * 100
    bh_test = (test_df['price'].iloc[-1] / test_df['price'].iloc[0] - 1) * 100
    print(f"  Train: {bh_train:.1f}%")
    print(f"  Test:  {bh_test:.1f}%")

    # Results table
    print("\n" + "=" * 80)
    print("RESULTS COMPARISON")
    print("=" * 80)

    print(f"\n{'Strategy':<30} {'Train Return':>12} {'Test Return':>12} {'Win Rate':>10} {'Sharpe':>8} {'Max DD':>8}")
    print("-" * 80)

    results = [
        ("LTH Distribution", train_lth, test_lth),
        ("8-Metric High Risk (6/8)", train_8m, test_8m),
        ("8-Metric Caution (4/8)", train_4m, test_4m),
    ]

    for name, train_r, test_r in results:
        print(f"{name:<30} "
              f"{train_r['total_return']:>11.1f}% "
              f"{test_r['total_return']:>11.1f}% "
              f"{test_r['win_rate']:>9.1f}% "
              f"{test_r['sharpe']:>8.2f} "
              f"{test_r['max_dd']:>7.1f}%")

    print(f"{'Buy & Hold':<30} {bh_train:>11.1f}% {bh_test:>11.1f}% {'':>10} {'':>8} {'':>8}")

    # Comparison with custom backtest
    print("\n" + "=" * 80)
    print("COMPARISON WITH CUSTOM BACKTEST")
    print("=" * 80)

    print("\nCustom Backtest Results (from earlier):")
    print("  LTH Distribution:        +348.7% (15 trades)")
    print("  8-Metric High Risk 6/8:  +473.2% (4 trades)")
    print("  Buy & Hold:              +437.5%")

    print("\nVectorBT Results (OOS 2023-2026):")
    print(f"  LTH Distribution:        {test_lth['total_return']:+.1f}% ({int(test_lth['num_trades'])} trades)")
    print(f"  8-Metric High Risk 6/8:  {test_8m['total_return']:+.1f}% ({int(test_8m['num_trades'])} trades)")
    print(f"  Buy & Hold:              {bh_test:+.1f}%")

    # Check for discrepancies
    print("\n" + "=" * 80)
    print("VERIFICATION STATUS")
    print("=" * 80)

    lth_diff = abs(test_lth['total_return'] - 348.7)
    m8_diff = abs(test_8m['total_return'] - 473.2)
    bh_diff = abs(bh_test - 437.5)

    print(f"\nReturn Differences:")
    print(f"  LTH Distribution: {lth_diff:.1f}% difference")
    print(f"  8-Metric 6/8:     {m8_diff:.1f}% difference")
    print(f"  Buy & Hold:       {bh_diff:.1f}% difference")

    if lth_diff < 20 and m8_diff < 50 and bh_diff < 20:
        print("\n✅ VERIFICATION PASSED")
        print("   Results match within expected variance (fees, slippage, implementation)")
    else:
        print("\n⚠️  LARGE DISCREPANCIES FOUND")
        print("   Investigate for potential look-ahead bias or bugs")

    # Debug mode - show trades
    if debug:
        print("\n" + "=" * 80)
        print("TRADE DETAILS (8-Metric High Risk)")
        print("=" * 80)
        print(test_8m['portfolio'].trades.records_readable)

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
