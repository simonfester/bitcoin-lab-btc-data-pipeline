#!/usr/bin/env python3
"""
Professional Backtest of James Check Entry/Exit Framework
==========================================================
Tests Buy The Dip entry signal with multiple exit strategies.

Usage:
    python backtest_framework.py              # Full backtest
    python backtest_framework.py --quick      # Quick test (2020+)
    python backtest_framework.py --plot       # Generate equity curves
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_loader import load_data

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "brk" / "daily"
GLASSNODE_DIR = PROJECT_ROOT / "data" / "glassnode" / "daily"
OUTPUT_DIR = PROJECT_ROOT / "data" / "results"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Backtest parameters
INITIAL_CAPITAL = 10000
COMMISSION = 0.001  # 0.1%
SLIPPAGE = 0.001    # 0.1%

# Walk-forward split
TRAIN_END = '2022-12-31'  # Train on 2009-2022
TEST_START = '2023-01-01'  # Test on 2023-2026 (out-of-sample)

# =============================================================================
# DATA LOADING
# =============================================================================

def load_metric(name: str, source: str = "brk") -> pd.DataFrame:
    """Load metric from parquet file."""
    if source == "brk":
        path = DATA_DIR / f"{name}.parquet"
    elif source == "glassnode":
        path = GLASSNODE_DIR / f"{name}.parquet"
    else:
        return pd.DataFrame()

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_parquet(path)

    # Normalize
    if 'time' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.columns = ['time'] + list(df.columns[1:])

    if 'value' not in df.columns:
        for col in df.columns:
            if col != 'time' and pd.api.types.is_numeric_dtype(df[col]):
                df = df.rename(columns={col: 'value'})
                break

    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time').reset_index(drop=True)

    return df[['time', 'value']] if 'value' in df.columns else pd.DataFrame()


def load_all_data() -> pd.DataFrame:
    """Load and merge all required metrics into single DataFrame."""
    print("Loading historical data...")

    # Core metrics
    metrics_to_load = [
        ('price', 'brk'),
        ('mvrv', 'brk'),
        ('mvrv_sth', 'brk'),
        ('mvrv_lth', 'brk'),
        ('sopr', 'brk'),
        ('sopr_sth', 'brk'),
        ('sopr_lth', 'brk'),
        ('realized_profit', 'brk'),
        ('realized_loss', 'brk'),
        ('puell_multiple', 'brk'),
        ('price_200d_sma', 'brk'),
        ('funding_rate', 'glassnode'),
        ('liquidations_long', 'glassnode'),
        ('liquidations_short', 'glassnode'),
    ]

    # Start with price
    df = load_metric('price', 'brk')
    if df.empty:
        raise ValueError("Price data not found!")

    df = df.rename(columns={'value': 'price'})

    # Merge all metrics
    for metric, source in metrics_to_load[1:]:
        metric_df = load_metric(metric, source)
        if not metric_df.empty:
            metric_df = metric_df.rename(columns={'value': metric})
            df = df.merge(metric_df, on='time', how='left')
            print(f"  ✓ {metric}")
        else:
            df[metric] = np.nan
            print(f"  ✗ {metric} (missing)")

    print(f"\nLoaded {len(df)} days from {df['time'].min()} to {df['time'].max()}")

    return df


# =============================================================================
# SIGNAL CALCULATIONS
# =============================================================================

def calculate_zscore(series: pd.Series, window: int = 365) -> pd.Series:
    """Calculate rolling Z-score."""
    mean = series.rolling(window, min_periods=30).mean()
    std = series.rolling(window, min_periods=30).std()
    return (series - mean) / std


def calculate_buy_the_dip_signal(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Buy The Dip entry signal (5 conditions)."""
    df = df.copy()

    # Condition 1: STH-MVRV < 1.0
    df['btd_sth_mvrv'] = df['mvrv_sth'] < 1.0

    # Condition 2: STH-SOPR < 1.0
    df['btd_sth_sopr'] = df['sopr_sth'] < 1.0

    # Condition 3: RP/L Ratio < 1.0
    df['rplr'] = df['realized_profit'] / df['realized_loss']
    df['btd_rplr'] = df['rplr'] < 1.0

    # Condition 4: Funding Rate <= 0
    df['btd_funding'] = df['funding_rate'] <= 0.0

    # Condition 5: Long Liq > Short Liq
    df['liq_ratio'] = df['liquidations_long'] / df['liquidations_short']
    df['btd_liq'] = df['liq_ratio'] > 1.0

    # Count conditions met
    df['btd_count'] = (
        df['btd_sth_mvrv'].fillna(False).astype(int) +
        df['btd_sth_sopr'].fillna(False).astype(int) +
        df['btd_rplr'].fillna(False).astype(int) +
        df['btd_funding'].fillna(False).astype(int) +
        df['btd_liq'].fillna(False).astype(int)
    )

    # Entry signal: 4+ conditions (STRONG DIP or better)
    df['entry_signal'] = df['btd_count'] >= 4

    return df


def calculate_exit_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all exit signals."""
    df = df.copy()

    # 1. LTH Distribution (MVRV > 2.0 AND LTH-SOPR > 1.5)
    df['exit_lth_dist'] = (df['mvrv'] > 2.0) & (df['sopr_lth'] > 1.5)

    # 2. 8-Metric Detector (calculate Z-scores)
    df['mvrv_z'] = calculate_zscore(df['mvrv'], 1460)
    df['mvrv_sth_z'] = calculate_zscore(df['mvrv_sth'], 365)
    df['sopr_z'] = calculate_zscore(df['sopr'], 365)
    df['sopr_sth_z'] = calculate_zscore(df['sopr_sth'], 365)
    df['puell_z'] = calculate_zscore(df['puell_multiple'], 365)

    # Mayer Multiple Z
    df['mayer'] = df['price'] / df['price_200d_sma']
    df['mayer_z'] = calculate_zscore(df['mayer'], 365)

    # Funding Z
    df['funding_z'] = calculate_zscore(df['funding_rate'], 365)

    # Count 8-metric triggers
    df['exit_8m_count'] = (
        (df['mvrv_z'] > 1.5).astype(int) +
        (df['mvrv_sth_z'] > 1.25).astype(int) +
        (df['sopr_z'] > 1.5).astype(int) +
        (df['sopr_sth_z'] > 1.0).astype(int) +
        (df['mayer_z'] > 1.0).astype(int) +
        (df['puell_z'] > 1.5).astype(int) +
        (df['funding_z'] > 1.5).astype(int)
    )

    df['exit_8m_caution'] = df['exit_8m_count'] >= 4  # 4/8 metrics
    df['exit_8m_high_risk'] = df['exit_8m_count'] >= 6  # 6/8 metrics

    # 3. STH-MVRV Zones
    df['sth_mvrv_z'] = calculate_zscore(df['mvrv_sth'], 365)
    df['exit_sth_overheated'] = df['sth_mvrv_z'] > 1.5  # Overheated zone
    df['exit_sth_local_top'] = df['sth_mvrv_z'] > 1.0   # Local top zone

    return df


# =============================================================================
# BACKTESTING ENGINE
# =============================================================================

def backtest_strategy(df: pd.DataFrame, entry_signal: str, exit_signal: str,
                      exit_params: dict = None) -> dict:
    """
    Backtest a strategy with given entry/exit signals.

    Args:
        df: DataFrame with signals
        entry_signal: Column name for entry signal
        exit_signal: Column name for exit signal or 'trailing_stop'
        exit_params: Parameters for exit (e.g., {'stop_pct': 0.10})
    """
    df = df.copy()
    exit_params = exit_params or {}

    # Initialize
    position = 0  # 0 = no position, 1 = long
    entry_price = 0
    entry_date = None
    cash = INITIAL_CAPITAL
    shares = 0

    trades = []
    equity = []

    # Track peak for trailing stop
    peak_price = 0

    for idx, row in df.iterrows():
        date = row['time']
        price = row['price']

        if pd.isna(price):
            continue

        # Entry logic
        if position == 0 and row.get(entry_signal, False):
            # Buy
            entry_price = price * (1 + SLIPPAGE)
            shares = (cash * (1 - COMMISSION)) / entry_price
            cash = 0
            position = 1
            entry_date = date
            peak_price = entry_price

        # Exit logic
        elif position == 1:
            should_exit = False
            exit_reason = ''

            # Update peak for trailing stop
            if price > peak_price:
                peak_price = price

            # Check exit conditions
            if exit_signal == 'trailing_stop':
                stop_pct = exit_params.get('stop_pct', 0.10)
                stop_price = peak_price * (1 - stop_pct)
                if price <= stop_price:
                    should_exit = True
                    exit_reason = f'Trailing Stop ({stop_pct:.0%})'

            elif exit_signal in df.columns:
                if row.get(exit_signal, False):
                    should_exit = True
                    exit_reason = exit_signal.replace('exit_', '').replace('_', ' ').title()

            # Execute exit
            if should_exit:
                exit_price = price * (1 - SLIPPAGE)
                cash = shares * exit_price * (1 - COMMISSION)

                pnl = cash - INITIAL_CAPITAL
                ret = (cash / INITIAL_CAPITAL - 1) * 100
                hold_days = (date - entry_date).days

                trades.append({
                    'entry_date': entry_date,
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'shares': shares,
                    'pnl': pnl,
                    'return_pct': ret,
                    'hold_days': hold_days,
                    'exit_reason': exit_reason
                })

                position = 0
                shares = 0

        # Record equity
        if position == 1:
            equity_val = shares * price
        else:
            equity_val = cash

        equity.append({'time': date, 'equity': equity_val})

    # Close any open position at end
    if position == 1:
        exit_price = df.iloc[-1]['price'] * (1 - SLIPPAGE)
        cash = shares * exit_price * (1 - COMMISSION)
        pnl = cash - INITIAL_CAPITAL
        ret = (cash / INITIAL_CAPITAL - 1) * 100
        hold_days = (df.iloc[-1]['time'] - entry_date).days

        trades.append({
            'entry_date': entry_date,
            'exit_date': df.iloc[-1]['time'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'shares': shares,
            'pnl': pnl,
            'return_pct': ret,
            'hold_days': hold_days,
            'exit_reason': 'End of Period'
        })

    return {
        'trades': pd.DataFrame(trades),
        'equity': pd.DataFrame(equity),
        'final_capital': cash if position == 0 else shares * df.iloc[-1]['price']
    }


def calculate_performance_metrics(trades_df: pd.DataFrame, equity_df: pd.DataFrame,
                                   initial_capital: float, start_date, end_date) -> dict:
    """Calculate comprehensive performance metrics."""
    if trades_df.empty:
        return {
            'total_return_pct': 0,
            'num_trades': 0,
            'win_rate': 0,
            'avg_return': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'error': 'No trades executed'
        }

    final_capital = equity_df.iloc[-1]['equity']
    total_return = (final_capital / initial_capital - 1) * 100

    # Time-based metrics
    days = (end_date - start_date).days
    years = days / 365.25
    cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

    # Trade metrics
    num_trades = len(trades_df)
    wins = (trades_df['return_pct'] > 0).sum()
    win_rate = wins / num_trades * 100 if num_trades > 0 else 0

    avg_return = trades_df['return_pct'].mean()
    avg_win = trades_df[trades_df['return_pct'] > 0]['return_pct'].mean()
    avg_loss = trades_df[trades_df['return_pct'] < 0]['return_pct'].mean()

    avg_hold_days = trades_df['hold_days'].mean()

    # Risk metrics
    returns = trades_df['return_pct'].values
    sharpe = (returns.mean() / returns.std() * np.sqrt(252 / avg_hold_days)) if len(returns) > 1 else 0

    # Drawdown
    equity_df['peak'] = equity_df['equity'].cummax()
    equity_df['dd'] = (equity_df['equity'] / equity_df['peak'] - 1) * 100
    max_dd = equity_df['dd'].min()

    return {
        'total_return_pct': total_return,
        'cagr': cagr,
        'num_trades': num_trades,
        'win_rate': win_rate,
        'avg_return': avg_return,
        'avg_win': avg_win if not pd.isna(avg_win) else 0,
        'avg_loss': avg_loss if not pd.isna(avg_loss) else 0,
        'avg_hold_days': avg_hold_days,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_dd,
        'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 and not pd.isna(avg_loss) else 0
    }


# =============================================================================
# MAIN BACKTEST
# =============================================================================

def run_comprehensive_backtest(df: pd.DataFrame, quick: bool = False):
    """Run comprehensive backtest of all entry/exit combinations."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE FRAMEWORK BACKTEST")
    print("=" * 80)

    # Filter date range if quick
    if quick:
        df = df[df['time'] >= '2020-01-01'].copy()
        print(f"\nQuick mode: Testing {len(df)} days from 2020-01-01")

    # Calculate all signals
    print("\nCalculating signals...")
    df = calculate_buy_the_dip_signal(df)
    df = calculate_exit_signals(df)

    # Walk-forward split
    train_df = df[df['time'] <= TRAIN_END].copy()
    test_df = df[df['time'] >= TEST_START].copy()

    print(f"\nTrain period: {train_df['time'].min()} to {train_df['time'].max()} ({len(train_df)} days)")
    print(f"Test period (OOS): {test_df['time'].min()} to {test_df['time'].max()} ({len(test_df)} days)")

    # Test strategies
    strategies = [
        {
            'name': '1. Trailing Stop 10%',
            'exit_signal': 'trailing_stop',
            'exit_params': {'stop_pct': 0.10}
        },
        {
            'name': '2. Trailing Stop 15%',
            'exit_signal': 'trailing_stop',
            'exit_params': {'stop_pct': 0.15}
        },
        {
            'name': '3. LTH Distribution',
            'exit_signal': 'exit_lth_dist',
            'exit_params': {}
        },
        {
            'name': '4. 8-Metric Caution (4/8)',
            'exit_signal': 'exit_8m_caution',
            'exit_params': {}
        },
        {
            'name': '5. 8-Metric High Risk (6/8)',
            'exit_signal': 'exit_8m_high_risk',
            'exit_params': {}
        },
        {
            'name': '6. STH Local Top',
            'exit_signal': 'exit_sth_local_top',
            'exit_params': {}
        },
    ]

    results = []

    print("\n" + "=" * 80)
    print("TESTING STRATEGIES")
    print("=" * 80)

    for strat in strategies:
        print(f"\nTesting: {strat['name']}")

        # Train period
        train_result = backtest_strategy(
            train_df,
            'entry_signal',
            strat['exit_signal'],
            strat['exit_params']
        )

        train_metrics = calculate_performance_metrics(
            train_result['trades'],
            train_result['equity'],
            INITIAL_CAPITAL,
            train_df['time'].min(),
            train_df['time'].max()
        )

        # Test period (out-of-sample)
        test_result = backtest_strategy(
            test_df,
            'entry_signal',
            strat['exit_signal'],
            strat['exit_params']
        )

        test_metrics = calculate_performance_metrics(
            test_result['trades'],
            test_result['equity'],
            INITIAL_CAPITAL,
            test_df['time'].min(),
            test_df['time'].max()
        )

        print(f"  Train: {train_metrics['total_return_pct']:>7.1f}% ({train_metrics['num_trades']} trades)")
        print(f"  Test:  {test_metrics['total_return_pct']:>7.1f}% ({test_metrics['num_trades']} trades)")

        results.append({
            'strategy': strat['name'],
            'train': train_metrics,
            'test': test_metrics,
            'train_trades': train_result['trades'],
            'test_trades': test_result['trades']
        })

    # Buy and hold benchmark
    print(f"\nBenchmark: Buy & Hold")
    bh_train_return = (train_df.iloc[-1]['price'] / train_df.iloc[0]['price'] - 1) * 100
    bh_test_return = (test_df.iloc[-1]['price'] / test_df.iloc[0]['price'] - 1) * 100
    print(f"  Train: {bh_train_return:>7.1f}%")
    print(f"  Test:  {bh_test_return:>7.1f}%")

    results.append({
        'strategy': '7. Buy & Hold (Benchmark)',
        'train': {'total_return_pct': bh_train_return, 'num_trades': 0},
        'test': {'total_return_pct': bh_test_return, 'num_trades': 0}
    })

    return results, df


def print_results_table(results: list):
    """Print formatted results table."""
    print("\n" + "=" * 120)
    print("BACKTEST RESULTS SUMMARY")
    print("=" * 120)
    print(f"\n{'Strategy':<35} {'Train Return':>12} {'Test Return':>12} {'Win Rate':>10} {'Sharpe':>8} {'Max DD':>8} {'Trades':>8}")
    print("-" * 120)

    for r in results:
        name = r['strategy']
        train = r['train']
        test = r['test']

        print(f"{name:<35} "
              f"{train['total_return_pct']:>11.1f}% "
              f"{test['total_return_pct']:>11.1f}% "
              f"{test.get('win_rate', 0):>9.1f}% "
              f"{test.get('sharpe_ratio', 0):>8.2f} "
              f"{test.get('max_drawdown', 0):>7.1f}% "
              f"{test.get('num_trades', 0):>8}")


def main():
    quick = '--quick' in sys.argv

    # Load data
    df = load_all_data()

    # Run backtest
    results, df_with_signals = run_comprehensive_backtest(df, quick=quick)

    # Print results
    print_results_table(results)

    # Save results
    output_file = OUTPUT_DIR / "framework_backtest_results.json"

    # Convert to serializable format
    results_json = []
    for r in results:
        r_copy = r.copy()
        if 'train_trades' in r_copy:
            del r_copy['train_trades']
        if 'test_trades' in r_copy:
            del r_copy['test_trades']
        results_json.append(r_copy)

    with open(output_file, 'w') as f:
        json.dump({
            'results': results_json,
            'backtest_date': datetime.now().isoformat(),
            'initial_capital': INITIAL_CAPITAL,
            'commission': COMMISSION,
            'train_end': TRAIN_END,
            'test_start': TEST_START
        }, f, indent=2, default=str)

    print(f"\n✅ Results saved to: {output_file}")

    # Recommendation
    print("\n" + "=" * 120)
    print("RECOMMENDATION")
    print("=" * 120)

    # Find best OOS performer
    best_strat = max(results[:-1], key=lambda x: x['test']['total_return_pct'])

    print(f"\nBest Out-of-Sample Strategy: {best_strat['strategy']}")
    print(f"  • Test Return: {best_strat['test']['total_return_pct']:.1f}%")
    print(f"  • Win Rate: {best_strat['test'].get('win_rate', 0):.1f}%")
    print(f"  • Sharpe: {best_strat['test'].get('sharpe_ratio', 0):.2f}")
    print(f"  • Max Drawdown: {best_strat['test'].get('max_drawdown', 0):.1f}%")

    if best_strat['test']['total_return_pct'] > results[-1]['test']['total_return_pct']:
        outperformance = best_strat['test']['total_return_pct'] - results[-1]['test']['total_return_pct']
        print(f"\n✅ BEATS Buy & Hold by {outperformance:.1f}% (OOS)")
        print("   → Framework is WORTH paper trading")
    else:
        print(f"\n⚠️ Underperforms Buy & Hold in test period")
        print("   → Consider refinements before paper trading")

    print("\n" + "=" * 120)


if __name__ == "__main__":
    main()
