#!/usr/bin/env python3
"""
Data Quality - Check data freshness and quality.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="Data Quality",
    page_icon="🔍",
    layout="wide"
)

DATA_DIR = PROJECT_ROOT / "data" / "brk" / "daily"
BL_HOURLY_DIR = PROJECT_ROOT / "data" / "bl" / "hourly"
GLASSNODE_DIR = PROJECT_ROOT / "data" / "glassnode" / "daily"


def check_file_freshness(path: Path) -> dict:
    """Check a parquet file's freshness."""
    if not path.exists():
        return {'status': 'missing', 'file': path.name}

    try:
        df = pd.read_parquet(path)

        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'], utc=True)
            latest = df['time'].max()
        elif df.index.name == 'time' or isinstance(df.index, pd.DatetimeIndex):
            latest = df.index.max()
        else:
            return {'status': 'no_time', 'file': path.name, 'rows': len(df)}

        now = datetime.now(latest.tzinfo)
        days_old = (now - latest).days

        return {
            'status': 'ok' if days_old <= 1 else 'stale',
            'file': path.name,
            'latest': latest,
            'days_old': days_old,
            'rows': len(df),
            'nulls': df.isnull().sum().sum()
        }
    except Exception as e:
        return {'status': 'error', 'file': path.name, 'error': str(e)}


def render_source_status(source_name: str, source_dir: Path, expected_metrics: list):
    """Render status for a data source."""
    st.subheader(f"📁 {source_name}")

    if not source_dir.exists():
        st.error(f"Directory not found: {source_dir}")
        return

    # Check each expected metric
    results = []
    for metric in expected_metrics:
        path = source_dir / f"{metric}.parquet"
        result = check_file_freshness(path)
        result['metric'] = metric
        results.append(result)

    # Summary
    ok_count = sum(1 for r in results if r['status'] == 'ok')
    stale_count = sum(1 for r in results if r['status'] == 'stale')
    missing_count = sum(1 for r in results if r['status'] == 'missing')
    error_count = sum(1 for r in results if r['status'] == 'error')

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ Current", ok_count)
    col2.metric("⚠️ Stale", stale_count)
    col3.metric("❌ Missing", missing_count)
    col4.metric("🔴 Error", error_count)

    # Detailed table
    with st.expander("Details"):
        data = []
        for r in results:
            status_icon = {
                'ok': '✅',
                'stale': '⚠️',
                'missing': '❌',
                'error': '🔴',
                'no_time': '❓'
            }.get(r['status'], '❓')

            data.append({
                'Metric': r['metric'],
                'Status': f"{status_icon} {r['status'].upper()}",
                'Latest': r.get('latest', pd.NaT),
                'Days Old': r.get('days_old', ''),
                'Rows': r.get('rows', ''),
                'Nulls': r.get('nulls', '')
            })

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)


def main():
    st.title("🔍 Data Quality")

    st.markdown("""
    Check data freshness across all sources. Run sync commands to update stale data.
    """)

    st.markdown("---")

    # BRK Daily (primary source)
    brk_metrics = [
        'price', 'mvrv', 'mvrv_sth', 'mvrv_lth',
        'sopr', 'sopr_sth', 'sopr_lth',
        'nupl', 'nupl_sth', 'nupl_lth',
        'realized_price', 'realized_profit', 'realized_loss',
        'supply_in_profit', 'supply_in_loss',
        'puell_multiple', 'liveliness'
    ]
    render_source_status("BRK Daily (FREE)", DATA_DIR, brk_metrics)

    st.markdown("---")

    # Bitcoin Lab Hourly
    bl_metrics = ['price', 'sopr', 'sopr_sth', 'sopr_lth', 'realized_loss']
    render_source_status("Bitcoin Lab Hourly (PAID)", BL_HOURLY_DIR, bl_metrics)

    st.markdown("---")

    # Glassnode
    gn_metrics = ['funding_rate', 'liq_long', 'liq_short']
    render_source_status("Glassnode Derivatives (PAID)", GLASSNODE_DIR, gn_metrics)

    st.markdown("---")

    # Sync commands
    st.subheader("🔄 Sync Commands")

    st.markdown("""
    Run these commands to update data:

    ```bash
    # BRK Daily (FREE - run daily)
    python run.py brk-sync

    # Bitcoin Lab Hourly (uses quota)
    python run.py bl-sync-hourly

    # Check quota before syncing
    python run.py quota
    ```
    """)

    # Quick actions
    st.markdown("---")
    st.subheader("Quick Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Refresh Page"):
            st.cache_data.clear()
            st.rerun()

    with col2:
        st.markdown("**Run BRK Sync:**")
        st.code("python run.py brk-sync", language="bash")

    with col3:
        st.markdown("**Check Quota:**")
        st.code("python run.py quota", language="bash")


if __name__ == "__main__":
    main()
