#!/usr/bin/env python3
"""
All Runs - Browse and compare all backtest runs from the database.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="All Runs",
    page_icon="📋",
    layout="wide"
)


def get_database():
    """Get database connection."""
    try:
        from src.backtest_db import BacktestDB
        return BacktestDB()
    except Exception as e:
        st.error(f"Database not available: {e}")
        return None


def main():
    st.title("📋 All Backtest Runs")

    db = get_database()
    if not db:
        return

    # Get stats
    stats = db.get_stats()
    strategies = db.get_strategies()

    # Stats bar
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Runs", stats['total_runs'])
    with col2:
        st.metric("Strategies", stats['total_strategies'])
    with col3:
        if stats['last_run']:
            last_run = stats['last_run'][:16]
            st.metric("Last Run", last_run)

    st.markdown("---")

    # Filters
    st.subheader("Filters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        strategy_options = ["All"] + [s['strategy_id'] for s in strategies]
        selected_strategy = st.selectbox("Strategy", strategy_options)

    with col2:
        min_sharpe = st.number_input("Min Sharpe", value=0.0, step=0.1)

    with col3:
        min_return = st.number_input("Min Return %", value=-100.0, step=10.0)

    with col4:
        max_dd = st.number_input("Max Drawdown %", value=0.0, step=5.0,
                                  help="Enter as negative (e.g., -30)")

    # Query runs
    filter_strategy = None if selected_strategy == "All" else selected_strategy
    runs = db.get_runs(
        strategy_id=filter_strategy,
        min_sharpe=min_sharpe if min_sharpe > 0 else None,
        min_return=min_return if min_return > -100 else None,
        max_dd=max_dd if max_dd < 0 else None,
        limit=500
    )

    st.markdown("---")

    if not runs:
        st.info("No runs match the current filters.")
        return

    st.subheader(f"Results ({len(runs)} runs)")

    # Convert to DataFrame for display
    df = pd.DataFrame(runs)

    # Select and format columns
    display_cols = ['run_id', 'strategy_id', 'return_pct', 'sharpe', 'sortino',
                    'max_dd', 'win_rate', 'num_trades', 'run_date']

    display_df = df[display_cols].copy()

    # Format columns
    display_df['return_pct'] = display_df['return_pct'].apply(
        lambda x: f"{x:+.1f}%" if pd.notna(x) else "N/A"
    )
    display_df['sharpe'] = display_df['sharpe'].apply(
        lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
    )
    display_df['sortino'] = display_df['sortino'].apply(
        lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
    )
    display_df['max_dd'] = display_df['max_dd'].apply(
        lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A"
    )
    display_df['win_rate'] = display_df['win_rate'].apply(
        lambda x: f"{x:.0f}%" if pd.notna(x) else "N/A"
    )
    display_df['run_date'] = display_df['run_date'].apply(
        lambda x: x[:16] if x else "N/A"
    )

    # Rename columns for display
    display_df.columns = ['Run ID', 'Strategy', 'Return', 'Sharpe', 'Sortino',
                          'Max DD', 'Win Rate', 'Trades', 'Date']

    # Show table
    st.dataframe(display_df, use_container_width=True, height=500)

    # Run details expander
    st.markdown("---")
    st.subheader("Run Details")

    run_ids = [r['run_id'] for r in runs]
    selected_run = st.selectbox("Select run to view details", run_ids)

    if selected_run:
        run_details = db.get_run_details(selected_run)

        if run_details:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Parameters Used:**")
                params = run_details.get('parameters', {})
                if params:
                    st.json(params)
                else:
                    st.info("No parameters recorded")

            with col2:
                st.markdown("**Test Period:**")
                test_period = run_details.get('test_period', {})
                st.write(f"Start: {test_period.get('start', 'N/A')}")
                st.write(f"End: {test_period.get('end', 'N/A')}")
                st.write(f"Days: {test_period.get('days', 'N/A')}")

            # Equity curve
            if 'equity_curve' in run_details.get('test', {}):
                st.markdown("**Equity Curve:**")
                equity = run_details['test']['equity_curve']
                if equity:
                    equity_df = pd.DataFrame({'Equity': equity})
                    st.line_chart(equity_df)

            # Trades
            trades = run_details.get('test', {}).get('trades', [])
            if trades:
                st.markdown(f"**Trade Log ({len(trades)} trades):**")
                trades_df = pd.DataFrame(trades)
                st.dataframe(trades_df, use_container_width=True)
        else:
            st.warning("Could not load run details. JSON file may be missing.")

    # Strategy summary
    st.markdown("---")
    st.subheader("Strategy Summary")

    summary_data = []
    for s in strategies:
        summary_data.append({
            'Strategy': s['strategy_id'],
            'Runs': s['run_count'],
            'Best Return': f"{s['best_return']:+.1f}%" if s['best_return'] else "N/A",
            'Best Sharpe': f"{s['best_sharpe']:.2f}" if s['best_sharpe'] else "N/A",
            'Last Run': s['last_run'][:16] if s['last_run'] else "N/A"
        })

    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True)


if __name__ == "__main__":
    main()
