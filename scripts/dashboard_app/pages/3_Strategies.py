#!/usr/bin/env python3
"""
Strategies - View individual strategy configurations and best results.
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="Strategies",
    page_icon="📈",
    layout="wide"
)

STRATEGIES_DIR = PROJECT_ROOT / "config" / "strategies"


@st.cache_data
def load_strategies():
    """Load all strategy configurations."""
    strategies = {}
    for path in STRATEGIES_DIR.glob("strat*.json"):
        if "_results" not in path.name:
            try:
                with open(path) as f:
                    config = json.load(f)
                    config['_path'] = str(path)
                    strategies[config.get('id', path.stem)] = config
            except Exception as e:
                st.warning(f"Error loading {path.name}: {e}")
    return strategies


@st.cache_data
def load_results(strategy_id: str):
    """Load results for a strategy."""
    # Try sidecar file first
    for path in STRATEGIES_DIR.glob(f"*{strategy_id.lower().replace('-', '')}*_results.json"):
        try:
            with open(path) as f:
                return json.load(f)
        except:
            pass

    # Try database
    try:
        from src.backtest_db import BacktestDB
        db = BacktestDB()
        runs = db.get_runs(strategy_id=strategy_id, limit=1, order_by='sharpe')
        if runs:
            return db.get_run_details(runs[0]['run_id'])
    except:
        pass

    return None


def render_entry_conditions(entry: dict):
    """Render entry conditions."""
    st.markdown("### Entry Conditions")

    conditions = entry.get('conditions', [])
    required = entry.get('required_conditions', len(conditions))
    total = entry.get('total_conditions', len(conditions))

    st.markdown(f"**{required} of {total} conditions required**")

    for cond in conditions:
        metric = cond.get('metric', '')
        operator = cond.get('operator', '')
        threshold = cond.get('threshold', '')
        compare = cond.get('metric_compare', '')
        rationale = cond.get('rationale', '')

        if compare:
            condition_str = f"`{metric}` {operator} `{compare}`"
        else:
            condition_str = f"`{metric}` {operator} `{threshold}`"

        st.markdown(f"- {condition_str}")
        if rationale:
            st.markdown(f"  _{rationale}_")


def render_exit_conditions(exit_cfg: dict):
    """Render exit conditions."""
    st.markdown("### Exit Conditions")

    conditions = exit_cfg.get('conditions', [])
    logic = exit_cfg.get('logic', 'AND')

    st.markdown(f"**Logic: {logic}**")

    for cond in conditions:
        metric = cond.get('metric', '')
        operator = cond.get('operator', '')
        threshold = cond.get('threshold', '')
        compare = cond.get('metric_compare', '')
        rationale = cond.get('rationale', '')

        if compare:
            condition_str = f"`{metric}` {operator} `{compare}`"
        else:
            condition_str = f"`{metric}` {operator} `{threshold}`"

        st.markdown(f"- {condition_str}")
        if rationale:
            st.markdown(f"  _{rationale}_")


def render_performance(results: dict):
    """Render performance metrics."""
    st.markdown("### Performance (Best Run)")

    if not results:
        st.info("No backtest results available. Run a backtest first.")
        return

    test = results.get('test', {})

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        ret = test.get('return_pct', 0)
        st.metric("Return", f"{ret:+.1f}%")

    with col2:
        sharpe = test.get('sharpe', 0)
        st.metric("Sharpe", f"{sharpe:.2f}")

    with col3:
        max_dd = test.get('max_dd', 0)
        st.metric("Max DD", f"{max_dd:.1f}%")

    with col4:
        win_rate = test.get('win_rate', 0)
        st.metric("Win Rate", f"{win_rate:.0f}%")

    # More metrics
    with st.expander("More Metrics"):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Sortino", f"{test.get('sortino', 0):.2f}")
        col2.metric("Calmar", f"{test.get('calmar', 0):.2f}")
        col3.metric("Trades", test.get('num_trades', 0))
        col4.metric("Profit Factor", f"{test.get('profit_factor', 0):.2f}")

    # Equity curve
    if test.get('equity_curve'):
        st.markdown("**Equity Curve:**")
        equity_df = pd.DataFrame({'Equity': test['equity_curve']})
        st.line_chart(equity_df)


def main():
    st.title("📈 Strategy Details")

    strategies = load_strategies()

    if not strategies:
        st.error("No strategies found in config/strategies/")
        return

    # Strategy selector
    strategy_ids = list(strategies.keys())
    selected_id = st.selectbox(
        "Select Strategy",
        strategy_ids,
        format_func=lambda x: f"{x}: {strategies[x].get('name', 'Unknown')}"
    )

    strategy = strategies[selected_id]

    st.markdown("---")

    # Strategy header
    st.header(f"{strategy.get('id', 'Unknown')}")
    st.markdown(f"**{strategy.get('name', 'Unknown')}**")
    st.markdown(f"_{strategy.get('description', '')}_")

    # Status badge
    status = strategy.get('status', 'UNKNOWN')
    if 'VALIDATED' in status or 'READY' in status:
        st.success(f"Status: {status}")
    elif 'TESTING' in status:
        st.warning(f"Status: {status}")
    else:
        st.info(f"Status: {status}")

    # Metadata
    metadata = strategy.get('metadata', {})
    if metadata:
        col1, col2, col3 = st.columns(3)
        col1.markdown(f"**Time Horizon:** {metadata.get('time_horizon', 'N/A')}")
        col2.markdown(f"**Trade Frequency:** {metadata.get('trade_frequency', 'N/A')}")
        col3.markdown(f"**Complexity:** {metadata.get('complexity', 'N/A')}")

    st.markdown("---")

    # Tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Conditions", "📈 Performance", "⚙️ Parameters", "📄 Raw Config"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            entry = strategy.get('entry', {})
            if entry:
                render_entry_conditions(entry)

        with col2:
            exit_cfg = strategy.get('exit', {})
            if exit_cfg:
                render_exit_conditions(exit_cfg)

    with tab2:
        results = load_results(selected_id)
        render_performance(results)

    with tab3:
        st.markdown("### Tunable Parameters")

        params = strategy.get('parameters', {})
        tunable = params.get('tunable', {})

        if tunable:
            for param_name, param_config in tunable.items():
                current = param_config.get('current', 'N/A')
                tested_range = param_config.get('tested_range', [])
                optimal_range = param_config.get('optimal_range', [])
                description = param_config.get('description', '')

                st.markdown(f"**{param_name}**: `{current}`")
                st.markdown(f"  - Tested: {tested_range}")
                st.markdown(f"  - Optimal: {optimal_range}")
                st.markdown(f"  - _{description}_")
        else:
            st.info("No tunable parameters defined")

        st.markdown("### Fixed Parameters")
        fixed = params.get('fixed', {})
        if fixed:
            st.json(fixed)
        else:
            st.info("No fixed parameters defined")

    with tab4:
        st.json(strategy)

    # Research notebooks
    st.markdown("---")
    notebooks = metadata.get('research_notebooks', [])
    if notebooks:
        st.markdown("### Related Research")
        for nb in notebooks:
            st.markdown(f"- `{nb}`")


if __name__ == "__main__":
    main()
