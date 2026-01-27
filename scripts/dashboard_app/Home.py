#!/usr/bin/env python3
"""
Bitcoin Lab Dashboard - Home
==============================
Main dashboard showing current market status and signals.
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="Bitcoin Lab Dashboard",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CONSTANTS
# =============================================================================

DATA_DIR = PROJECT_ROOT / "data" / "brk" / "daily"
GLASSNODE_DIR = PROJECT_ROOT / "data" / "glassnode" / "daily"
SIGNALS_FILE = PROJECT_ROOT / "data" / "signals" / "dashboard_context.json"

COLORS = {
    'green': '#22c55e',
    'red': '#ef4444',
    'orange': '#f59e0b',
    'blue': '#3b82f6',
    'purple': '#a855f7',
    'muted': '#9ca3af'
}

# =============================================================================
# DATA LOADING
# =============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
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


@st.cache_data(ttl=300)
def load_dashboard_data():
    """Load all metrics needed for dashboard."""
    metrics = {}

    # Core metrics
    metric_names = [
        'price', 'mvrv', 'mvrv_sth', 'mvrv_lth', 'mvrv_z',
        'sopr', 'sopr_sth', 'sopr_lth',
        'nupl', 'nupl_sth', 'nupl_lth',
        'supply_in_profit', 'supply_in_loss',
        'realized_price', 'realized_price_sth', 'realized_price_lth',
        'puell_multiple', 'liveliness'
    ]

    for name in metric_names:
        series = load_metric(name)
        if not series.empty:
            metrics[name] = series

    # Combine into DataFrame
    if metrics:
        df = pd.DataFrame(metrics)
        df = df.dropna(subset=['price'])
        return df

    return pd.DataFrame()


@st.cache_data(ttl=60)
def load_signals():
    """Load pre-computed signals from JSON."""
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE) as f:
            return json.load(f)
    return {}


def get_current_values(df: pd.DataFrame) -> dict:
    """Get the most recent values for all metrics."""
    if df.empty:
        return {}

    latest = df.iloc[-1].to_dict()
    latest['date'] = df.index[-1]

    # Add price changes
    if 'price' in df.columns:
        latest['price_24h_change'] = (df['price'].iloc[-1] / df['price'].iloc[-2] - 1) * 100 if len(df) > 1 else 0
        latest['price_7d_change'] = (df['price'].iloc[-1] / df['price'].iloc[-7] - 1) * 100 if len(df) > 7 else 0
        latest['price_30d_change'] = (df['price'].iloc[-1] / df['price'].iloc[-30] - 1) * 100 if len(df) > 30 else 0

    return latest


# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_header(current: dict):
    """Render dashboard header with price and key metrics."""
    st.title("₿ Bitcoin Lab Dashboard")

    if not current:
        st.warning("No data available. Run data sync first.")
        return

    # Price header
    col1, col2, col3, col4, col5 = st.columns(5)

    price = current.get('price', 0)
    price_24h = current.get('price_24h_change', 0)

    with col1:
        st.metric(
            "BTC Price",
            f"${price:,.0f}",
            f"{price_24h:+.1f}% (24h)",
            delta_color="normal" if price_24h >= 0 else "inverse"
        )

    with col2:
        mvrv = current.get('mvrv', 0)
        mvrv_color = "normal" if mvrv < 2.5 else "inverse"
        st.metric("MVRV", f"{mvrv:.2f}", delta_color="off")

    with col3:
        nupl = current.get('nupl', 0)
        st.metric("NUPL", f"{nupl:.2f}", delta_color="off")

    with col4:
        sopr = current.get('sopr', 0)
        st.metric("SOPR", f"{sopr:.3f}", delta_color="off")

    with col5:
        data_date = current.get('date')
        if data_date:
            st.metric("Data Date", data_date.strftime("%Y-%m-%d"))


def render_signal_card(title: str, status: str, value: float, threshold: str, description: str):
    """Render a signal indicator card."""
    if status == "BULLISH":
        color = COLORS['green']
        icon = "🟢"
    elif status == "BEARISH":
        color = COLORS['red']
        icon = "🔴"
    else:
        color = COLORS['orange']
        icon = "🟡"

    st.markdown(f"""
    <div style="background: #1e293b; padding: 16px; border-radius: 8px; border-left: 4px solid {color}; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="font-size: 0.8em; color: #9ca3af; text-transform: uppercase;">{title}</div>
                <div style="font-size: 1.4em; font-weight: 600;">{icon} {status}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 1.2em; font-weight: 600;">{value:.3f}</div>
                <div style="font-size: 0.75em; color: #9ca3af;">{threshold}</div>
            </div>
        </div>
        <div style="font-size: 0.8em; color: #9ca3af; margin-top: 8px;">{description}</div>
    </div>
    """, unsafe_allow_html=True)


def render_pillar(title: str, metrics: list, current: dict):
    """Render a pillar section with its metrics."""
    st.subheader(title)

    for metric in metrics:
        name = metric['name']
        display = metric.get('display', name)
        value = current.get(name, 0)

        if value is None or (isinstance(value, float) and np.isnan(value)):
            value = 0

        # Determine status based on thresholds
        bullish = metric.get('bullish', None)
        bearish = metric.get('bearish', None)

        if bullish and bearish:
            if isinstance(bullish, str) and bullish.startswith('<'):
                threshold_val = float(bullish[1:])
                if value < threshold_val:
                    status = "BULLISH"
                elif value > float(bearish[1:]) if bearish.startswith('>') else float(bearish):
                    status = "BEARISH"
                else:
                    status = "NEUTRAL"
            elif isinstance(bullish, str) and bullish.startswith('>'):
                threshold_val = float(bullish[1:])
                if value > threshold_val:
                    status = "BULLISH"
                else:
                    status = "NEUTRAL"
            else:
                status = "NEUTRAL"
        else:
            status = "NEUTRAL"

        threshold_str = f"Bull: {bullish}, Bear: {bearish}" if bullish else ""
        description = metric.get('description', '')

        render_signal_card(display, status, value, threshold_str, description)


def render_six_pillars(current: dict):
    """Render the 6 pillars of on-chain analysis."""

    # Define pillars and their metrics
    pillars = {
        "1. Valuation": [
            {'name': 'mvrv', 'display': 'MVRV Ratio', 'bullish': '<1.0', 'bearish': '>3.0',
             'description': 'Market Value to Realized Value - measures if BTC is over/undervalued'},
            {'name': 'mvrv_sth', 'display': 'STH-MVRV', 'bullish': '<1.0', 'bearish': '>1.5',
             'description': 'Short-term holder MVRV - STH underwater signals capitulation'},
        ],
        "2. Profitability": [
            {'name': 'nupl', 'display': 'NUPL', 'bullish': '<0.25', 'bearish': '>0.75',
             'description': 'Net Unrealized Profit/Loss - market sentiment indicator'},
            {'name': 'sopr', 'display': 'SOPR', 'bullish': '<1.0', 'bearish': '>1.05',
             'description': 'Spent Output Profit Ratio - are holders selling at profit or loss?'},
        ],
        "3. Spending Behavior": [
            {'name': 'sopr_sth', 'display': 'STH-SOPR', 'bullish': '<1.0', 'bearish': '>1.02',
             'description': 'Short-term holder SOPR - STH capitulation signals'},
            {'name': 'sopr_lth', 'display': 'LTH-SOPR', 'bullish': '<1.0', 'bearish': '>1.5',
             'description': 'Long-term holder SOPR - LTH distribution signals'},
        ],
    }

    col1, col2, col3 = st.columns(3)

    columns = [col1, col2, col3]
    for i, (pillar_name, metrics) in enumerate(pillars.items()):
        with columns[i]:
            render_pillar(pillar_name, metrics, current)


def render_price_chart(df: pd.DataFrame):
    """Render interactive price chart."""
    st.subheader("📈 Price Chart")

    if 'price' not in df.columns:
        st.warning("No price data available")
        return

    # Time range selector
    range_options = {
        '1M': 30,
        '3M': 90,
        '6M': 180,
        '1Y': 365,
        '2Y': 730,
        'All': len(df)
    }

    selected_range = st.radio("Time Range", list(range_options.keys()), horizontal=True, index=3)
    days = range_options[selected_range]

    chart_df = df[['price']].iloc[-days:].copy()
    chart_df.columns = ['Price']

    st.line_chart(chart_df, use_container_width=True)


def render_mvrv_chart(df: pd.DataFrame):
    """Render MVRV chart with zones."""
    st.subheader("📊 MVRV Ratio")

    if 'mvrv' not in df.columns:
        st.warning("No MVRV data available")
        return

    chart_df = df[['mvrv']].iloc[-365:].copy()
    chart_df.columns = ['MVRV']

    st.line_chart(chart_df, use_container_width=True)

    # Zone legend
    st.markdown("""
    **MVRV Zones:**
    🟢 < 1.0 (Undervalued) |
    🟡 1.0-2.5 (Fair Value) |
    🔴 > 2.5 (Overvalued)
    """)


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Load data
    with st.spinner("Loading data..."):
        df = load_dashboard_data()
        signals = load_signals()

    if df.empty:
        st.error("No data available. Please run data sync first:")
        st.code("python run.py brk-sync")
        return

    current = get_current_values(df)

    # Render header
    render_header(current)

    st.markdown("---")

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📊 Signals", "📈 Charts", "📋 Data"])

    with tab1:
        render_six_pillars(current)

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            render_price_chart(df)
        with col2:
            render_mvrv_chart(df)

    with tab3:
        st.subheader("Latest Values")

        # Show recent data as table
        display_df = df.tail(30).copy()
        display_df = display_df.round(4)
        st.dataframe(display_df, use_container_width=True)

        # Data freshness
        st.subheader("Data Freshness")
        latest_date = df.index[-1]
        days_old = (datetime.now(latest_date.tzinfo) - latest_date).days

        if days_old == 0:
            st.success(f"✅ Data is current ({latest_date.strftime('%Y-%m-%d')})")
        elif days_old <= 1:
            st.info(f"📅 Data is {days_old} day old ({latest_date.strftime('%Y-%m-%d')})")
        else:
            st.warning(f"⚠️ Data is {days_old} days old ({latest_date.strftime('%Y-%m-%d')}). Run sync to update.")


if __name__ == "__main__":
    main()
