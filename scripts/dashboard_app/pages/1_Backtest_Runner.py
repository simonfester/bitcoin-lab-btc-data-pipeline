#!/usr/bin/env python3
"""
Backtest Runner - Run and compare backtests interactively.
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# =============================================================================
# CONFIGURATION
# =============================================================================

STRATEGIES_DIR = PROJECT_ROOT / "config" / "strategies"
DATA_DIR = PROJECT_ROOT / "data" / "brk" / "daily"
GLASSNODE_DIR = PROJECT_ROOT / "data" / "glassnode" / "daily"

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="Backtest Runner",
    page_icon="▶️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stMetric {
        background-color: #1e293b;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid #334155;
    }
    .stMetric label {
        color: #9ca3af !important;
    }
    .success-box {
        background-color: rgba(34, 197, 94, 0.1);
        border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
    }
    .warning-box {
        background-color: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# DATA LOADING
# =============================================================================

@st.cache_data
def load_strategies():
    """Load all strategy configurations."""
    strategies = {}
    for path in STRATEGIES_DIR.glob("strat*.json"):
        if "_results" not in path.name:
            try:
                with open(path) as f:
                    config = json.load(f)
                    config['_path'] = path
                    strategies[config.get('id', path.stem)] = config
            except Exception as e:
                st.warning(f"Error loading {path.name}: {e}")
    return strategies


@st.cache_data
def load_metric(name: str, source: str = "brk") -> pd.Series:
    """Load a metric as time-indexed Series."""
    if source == "brk":
        path = DATA_DIR / f"{name}.parquet"
    elif source == "glassnode":
        path = GLASSNODE_DIR / f"{name}.parquet"
    else:
        return pd.Series(dtype=float)

    if not path.exists():
        return pd.Series(dtype=float)

    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], utc=True)
        df = df.set_index('time')
    return df['value'] if 'value' in df.columns else df.iloc[:, 0]


@st.cache_data
def load_all_data():
    """Load all required metrics."""
    metrics = {
        'price': load_metric('price'),
        'mvrv': load_metric('mvrv'),
        'mvrv_sth': load_metric('mvrv_sth'),
        'mvrv_lth': load_metric('mvrv_lth'),
        'sopr': load_metric('sopr'),
        'sopr_sth': load_metric('sopr_sth'),
        'sopr_lth': load_metric('sopr_lth'),
        'realized_profit': load_metric('realized_profit'),
        'realized_loss': load_metric('realized_loss'),
        'funding': load_metric('funding_rate', 'glassnode'),
        'liq_long': load_metric('liq_long', 'glassnode'),
        'liq_short': load_metric('liq_short', 'glassnode'),
    }

    # Combine into DataFrame
    df = pd.DataFrame(metrics)
    df = df.dropna(subset=['price'])

    # Add derived metrics
    df['price_ma50'] = df['price'].rolling(50).mean()
    df['price_ma200'] = df['price'].rolling(200).mean()

    # Realized P/L ratio
    if 'realized_profit' in df.columns and 'realized_loss' in df.columns:
        df['rpl_ratio'] = df['realized_profit'] / df['realized_loss'].replace(0, np.nan)

    return df


def get_database():
    """Get database connection."""
    try:
        from src.backtest_db import BacktestDB
        return BacktestDB()
    except Exception as e:
        st.warning(f"Database not available: {e}")
        return None


# =============================================================================
# SIGNAL GENERATION
# =============================================================================

def generate_entry_signals(df: pd.DataFrame, params: dict) -> pd.Series:
    """Generate entry signals based on parameters."""
    conditions = []

    # STH-MVRV < threshold
    if 'mvrv_sth' in df.columns:
        conditions.append(df['mvrv_sth'] < params.get('mvrv_sth_threshold', 1.0))

    # STH-SOPR < threshold
    if 'sopr_sth' in df.columns:
        conditions.append(df['sopr_sth'] < params.get('sopr_sth_threshold', 1.0))

    # Realized P/L ratio < threshold
    if 'rpl_ratio' in df.columns:
        conditions.append(df['rpl_ratio'] < params.get('rpl_threshold', 1.0))

    # Funding <= threshold
    if 'funding' in df.columns:
        conditions.append(df['funding'] <= params.get('funding_threshold', 0.0))

    # Long liquidations > Short liquidations
    if 'liq_long' in df.columns and 'liq_short' in df.columns:
        conditions.append(df['liq_long'] > df['liq_short'])

    if not conditions:
        return pd.Series(False, index=df.index)

    # Count conditions met
    conditions_df = pd.concat(conditions, axis=1)
    conditions_met = conditions_df.sum(axis=1)

    min_conditions = params.get('min_conditions', 4)
    return conditions_met >= min_conditions


def generate_exit_signals(df: pd.DataFrame, params: dict) -> pd.Series:
    """Generate exit signals based on parameters."""
    exit_type = params.get('exit_type', 'momentum')

    if exit_type == 'momentum':
        # MVRV > threshold AND price < MA
        mvrv_exit = df['mvrv'] > params.get('mvrv_exit_threshold', 2.0)
        ma_period = params.get('ma_period', 50)
        ma = df['price'].rolling(ma_period).mean()
        price_below_ma = df['price'] < ma
        return mvrv_exit & price_below_ma

    elif exit_type == 'mvrv_only':
        return df['mvrv'] > params.get('mvrv_exit_threshold', 2.5)

    elif exit_type == 'trailing':
        # Simple trailing stop (placeholder)
        return pd.Series(False, index=df.index)

    return pd.Series(False, index=df.index)


# =============================================================================
# BACKTESTING
# =============================================================================

def run_backtest(df: pd.DataFrame, entries: pd.Series, exits: pd.Series, params: dict) -> dict:
    """Run backtest and return results."""
    try:
        import vectorbt as vbt
    except ImportError:
        st.error("VectorBT not installed. Run: pip install vectorbt")
        return None

    position_size = params.get('position_size', 0.2)
    stop_loss = params.get('stop_loss', 0.1)
    init_cash = params.get('init_cash', 100000)

    # Run portfolio simulation
    pf = vbt.Portfolio.from_signals(
        close=df['price'],
        entries=entries,
        exits=exits,
        size=position_size,
        size_type='percent',
        fees=0.001,
        slippage=0.001,
        init_cash=init_cash,
        freq='1D',
        sl_stop=stop_loss if stop_loss > 0 else None
    )

    # Extract stats
    stats = pf.stats()

    # Get trades
    trades = []
    if hasattr(pf, 'trades') and len(pf.trades.records) > 0:
        trades_df = pf.trades.records_readable
        for _, trade in trades_df.iterrows():
            trades.append({
                'entry_date': str(trade.get('Entry Timestamp', '')),
                'exit_date': str(trade.get('Exit Timestamp', '')),
                'return_pct': float(trade.get('Return', 0) * 100),
                'pnl': float(trade.get('PnL', 0))
            })

    # Build results
    results = {
        'return_pct': float(pf.total_return() * 100),
        'sharpe': float(stats.get('Sharpe Ratio', 0)),
        'sortino': float(stats.get('Sortino Ratio', 0)),
        'calmar': float(stats.get('Calmar Ratio', 0)),
        'max_dd': float(pf.max_drawdown() * 100),
        'max_dd_days': int(stats.get('Max Drawdown Duration', pd.Timedelta(0)).days) if pd.notna(stats.get('Max Drawdown Duration')) else 0,
        'win_rate': float(pf.trades.win_rate() * 100) if len(pf.trades.records) > 0 else 0,
        'num_trades': len(pf.trades.records) if hasattr(pf, 'trades') else 0,
        'profit_factor': float(stats.get('Profit Factor', 0)) if pd.notna(stats.get('Profit Factor')) else 0,
        'expectancy': float(stats.get('Expectancy', 0)) if pd.notna(stats.get('Expectancy')) else 0,
        'trades': trades,
        'equity_curve': pf.value().tolist(),
        'equity_dates': [str(d) for d in pf.value().index],
        'benchmark_return': float((df['price'].iloc[-1] / df['price'].iloc[0] - 1) * 100)
    }

    return results


# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_sidebar():
    """Render sidebar with strategy selection and parameters."""
    st.sidebar.title("📈 Backtest Runner")

    strategies = load_strategies()

    if not strategies:
        st.sidebar.error("No strategies found in config/strategies/")
        return None, None

    # Strategy selection
    strategy_ids = list(strategies.keys())
    selected_id = st.sidebar.selectbox(
        "Select Strategy",
        strategy_ids,
        format_func=lambda x: f"{x}: {strategies[x].get('name', 'Unknown')[:30]}"
    )

    strategy = strategies[selected_id]

    st.sidebar.markdown("---")
    st.sidebar.subheader("Entry Parameters")

    # Entry parameters
    params = {}

    params['mvrv_sth_threshold'] = st.sidebar.slider(
        "MVRV STH Threshold",
        min_value=0.5, max_value=2.0, value=1.0, step=0.1,
        help="Enter when STH-MVRV < this value"
    )

    params['sopr_sth_threshold'] = st.sidebar.slider(
        "SOPR STH Threshold",
        min_value=0.5, max_value=1.5, value=1.0, step=0.05,
        help="Enter when STH-SOPR < this value"
    )

    params['rpl_threshold'] = st.sidebar.slider(
        "Realized P/L Ratio Threshold",
        min_value=0.5, max_value=2.0, value=1.0, step=0.1,
        help="Enter when RPL ratio < this value"
    )

    params['funding_threshold'] = st.sidebar.slider(
        "Funding Rate Threshold",
        min_value=-0.05, max_value=0.05, value=0.0, step=0.005,
        format="%.3f",
        help="Enter when funding <= this value"
    )

    params['min_conditions'] = st.sidebar.select_slider(
        "Minimum Conditions Required",
        options=[2, 3, 4, 5],
        value=4,
        help="Number of entry conditions that must be true"
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Exit Parameters")

    params['exit_type'] = st.sidebar.radio(
        "Exit Strategy",
        ['momentum', 'mvrv_only'],
        format_func=lambda x: {
            'momentum': 'Momentum (MVRV + MA)',
            'mvrv_only': 'MVRV Only'
        }[x]
    )

    params['mvrv_exit_threshold'] = st.sidebar.slider(
        "MVRV Exit Threshold",
        min_value=1.5, max_value=4.0, value=2.0, step=0.1,
        help="Exit when MVRV > this value"
    )

    if params['exit_type'] == 'momentum':
        params['ma_period'] = st.sidebar.slider(
            "MA Period (days)",
            min_value=20, max_value=200, value=50, step=10,
            help="Exit when price < this MA"
        )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Position Sizing")

    params['position_size'] = st.sidebar.slider(
        "Position Size",
        min_value=0.1, max_value=1.0, value=0.2, step=0.05,
        format="%.0f%%",
        help="Percentage of portfolio per trade"
    )

    params['stop_loss'] = st.sidebar.slider(
        "Stop Loss",
        min_value=0.0, max_value=0.3, value=0.1, step=0.01,
        format="%.0f%%",
        help="Stop loss below entry (0 = disabled)"
    )

    params['init_cash'] = st.sidebar.number_input(
        "Initial Capital ($)",
        min_value=1000, max_value=10000000, value=100000, step=10000
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Test Period")

    col1, col2 = st.sidebar.columns(2)
    params['test_start'] = col1.date_input(
        "Start",
        value=datetime(2023, 1, 1)
    )
    params['test_end'] = col2.date_input(
        "End",
        value=datetime.now()
    )

    return strategy, params


def render_results(results: dict, params: dict):
    """Render backtest results."""
    st.subheader("📊 Results")

    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        delta_color = "normal" if results['return_pct'] >= 0 else "inverse"
        st.metric("Total Return", f"{results['return_pct']:+.1f}%",
                  delta=f"vs B&H: {results['return_pct'] - results['benchmark_return']:+.1f}%",
                  delta_color=delta_color)

    with col2:
        st.metric("Sharpe Ratio", f"{results['sharpe']:.2f}")

    with col3:
        st.metric("Max Drawdown", f"{results['max_dd']:.1f}%")

    with col4:
        st.metric("Win Rate", f"{results['win_rate']:.0f}%")

    with col5:
        st.metric("Trades", results['num_trades'])

    # Additional metrics
    with st.expander("More Metrics"):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Sortino", f"{results['sortino']:.2f}")
        col2.metric("Calmar", f"{results['calmar']:.2f}")
        col3.metric("Profit Factor", f"{results['profit_factor']:.2f}")
        col4.metric("DD Duration", f"{results['max_dd_days']} days")

    # Equity curve
    st.subheader("📈 Equity Curve")

    if results.get('equity_curve') and results.get('equity_dates'):
        equity_df = pd.DataFrame({
            'date': pd.to_datetime(results['equity_dates']),
            'equity': results['equity_curve']
        }).set_index('date')

        st.line_chart(equity_df)

    # Trade log
    if results.get('trades'):
        st.subheader("📋 Trade Log")

        trades_df = pd.DataFrame(results['trades'])
        trades_df['return_pct'] = trades_df['return_pct'].apply(lambda x: f"{x:+.1f}%")
        trades_df['pnl'] = trades_df['pnl'].apply(lambda x: f"${x:+,.0f}")

        st.dataframe(trades_df, use_container_width=True)

    # Parameters used
    with st.expander("Parameters Used"):
        st.json(params)


def render_comparison():
    """Render comparison of recent runs."""
    db = get_database()
    if not db:
        return

    st.subheader("📊 Recent Runs")

    runs = db.get_runs(limit=10)
    if not runs:
        st.info("No runs in database yet. Run a backtest to see results here.")
        return

    # Convert to DataFrame
    runs_df = pd.DataFrame(runs)
    display_cols = ['run_id', 'strategy_id', 'return_pct', 'sharpe', 'max_dd', 'win_rate', 'num_trades']
    display_df = runs_df[display_cols].copy()

    display_df['return_pct'] = display_df['return_pct'].apply(lambda x: f"{x:+.1f}%" if x else "N/A")
    display_df['sharpe'] = display_df['sharpe'].apply(lambda x: f"{x:.2f}" if x else "N/A")
    display_df['max_dd'] = display_df['max_dd'].apply(lambda x: f"{x:.1f}%" if x else "N/A")
    display_df['win_rate'] = display_df['win_rate'].apply(lambda x: f"{x:.0f}%" if x else "N/A")

    st.dataframe(display_df, use_container_width=True)


# =============================================================================
# MAIN
# =============================================================================

def main():
    strategy, params = render_sidebar()

    if not strategy:
        st.warning("Please select a strategy from the sidebar.")
        return

    # Main content
    st.title(f"🎯 {strategy.get('id', 'Unknown')}")
    st.markdown(f"**{strategy.get('name', 'Unknown Strategy')}**")
    st.markdown(f"_{strategy.get('description', '')}_")

    st.markdown("---")

    # Load data
    with st.spinner("Loading data..."):
        df = load_all_data()

    if df.empty:
        st.error("No data available. Run data sync first.")
        return

    # Filter to test period
    test_start = pd.Timestamp(params['test_start'], tz='UTC')
    test_end = pd.Timestamp(params['test_end'], tz='UTC')
    test_df = df[(df.index >= test_start) & (df.index <= test_end)].copy()

    if len(test_df) < 30:
        st.warning(f"Only {len(test_df)} days of data in test period. Need at least 30.")
        return

    st.info(f"📅 Test period: {test_start.date()} to {test_end.date()} ({len(test_df)} days)")

    # Generate signals preview
    with st.expander("Signal Preview"):
        entries = generate_entry_signals(test_df, params)
        exits = generate_exit_signals(test_df, params)

        entry_count = entries.sum()
        exit_count = exits.sum()

        col1, col2 = st.columns(2)
        col1.metric("Entry Signals", int(entry_count))
        col2.metric("Exit Signals", int(exit_count))

        if entry_count == 0:
            st.warning("No entry signals generated with current parameters.")

    # Run backtest button
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        run_button = st.button("▶️ Run Backtest", type="primary", use_container_width=True)

    if run_button:
        with st.spinner("Running backtest..."):
            entries = generate_entry_signals(test_df, params)
            exits = generate_exit_signals(test_df, params)
            results = run_backtest(test_df, entries, exits, params)

        if results:
            render_results(results, params)

            # Save to database
            db = get_database()
            if db:
                try:
                    run_id = db.save_run(
                        strategy_id=strategy.get('id', 'CUSTOM'),
                        strategy_name=strategy.get('name', 'Custom Run'),
                        results={
                            'test': results,
                            'test_period': {
                                'start': str(test_start.date()),
                                'end': str(test_end.date()),
                                'days': len(test_df)
                            },
                            'position_sizing': {
                                'position_size_pct': params['position_size'] * 100,
                                'stop_loss_pct': params['stop_loss'] * 100
                            }
                        },
                        parameters=params
                    )
                    st.success(f"✅ Saved to database: {run_id}")
                except Exception as e:
                    st.warning(f"Could not save to database: {e}")
        else:
            st.error("Backtest failed. Check the logs.")

    # Show recent runs
    st.markdown("---")
    render_comparison()


if __name__ == "__main__":
    main()
