#!/usr/bin/env python3
"""
Bitcoin Lab Dashboard - Home
=============================
Full 6-pillar dashboard matching the HTML design, built in Streamlit.
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import requests
from pathlib import Path
from datetime import datetime
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
    initial_sidebar_state="collapsed"
)

# =============================================================================
# CONSTANTS & STYLING
# =============================================================================

SIGNALS_DIR = PROJECT_ROOT / "data" / "signals"
COINBASE_API = "https://api.coinbase.com/v2/prices/BTC-USD/spot"

# Helper function for rendering HTML (st.html is more reliable than st.markdown)
def render_html(html: str):
    """Render HTML using st.html for better compatibility."""
    # st.html() was added in Streamlit 1.33+ and is more reliable
    if hasattr(st, 'html'):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


# Custom CSS for dark theme matching HTML dashboard
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background: #0f172a;
    }

    /* Headers */
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #f1f5f9 !important;
    }

    /* Pillar header styling */
    .pillar-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-left: 4px solid #f59e0b;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }
    .pillar-title {
        font-size: 1.4em;
        font-weight: bold;
        color: #f59e0b;
        margin-bottom: 8px;
    }
    .pillar-tells {
        color: #e2e8f0;
        font-size: 0.95em;
        margin-bottom: 6px;
    }
    .pillar-metrics {
        color: #6b7280;
        font-size: 0.8em;
        font-style: italic;
    }

    /* Card styling */
    .metric-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #334155;
        margin-bottom: 16px;
    }
    .card-title {
        color: #e2e8f0;
        font-size: 1.1em;
        font-weight: 600;
        margin-bottom: 16px;
    }

    /* Big numbers */
    .big-number {
        font-size: 2.5em;
        font-weight: bold;
        text-align: center;
        color: #f1f5f9;
    }
    .big-label {
        color: #9ca3af;
        text-align: center;
        font-size: 0.9em;
    }

    /* Zone badges */
    .zone-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85em;
    }

    /* Metric rows */
    .metric-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid #374151;
    }
    .metric-label {
        color: #9ca3af;
    }
    .metric-value {
        font-weight: 500;
    }

    /* Progress bars */
    .progress-container {
        background: #1f2937;
        border-radius: 8px;
        height: 16px;
        overflow: hidden;
        position: relative;
    }
    .progress-fill {
        height: 100%;
        transition: width 0.3s;
    }

    /* Thermometer */
    .thermometer {
        position: relative;
        height: 20px;
        border-radius: 10px;
        background: linear-gradient(to right, #22c55e 0%, #3b82f6 30%, #f97316 60%, #ef4444 100%);
    }
    .thermometer-marker {
        position: absolute;
        top: -2px;
        width: 4px;
        height: 24px;
        background: white;
        border-radius: 2px;
        transform: translateX(-50%);
    }

    /* Condition rows */
    .condition-row {
        display: flex;
        justify-content: space-between;
        padding: 6px 0;
        border-bottom: 1px solid #374151;
    }
    .condition-met {
        color: #22c55e;
        font-weight: 500;
    }
    .condition-unmet {
        color: #6b7280;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Sidebar styling */
    .css-1d391kg {
        background: #1e293b;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# DATA LOADING
# =============================================================================

@st.cache_data(ttl=60)
def load_dashboard_context() -> dict:
    """Load pre-computed dashboard context from JSON."""
    context_path = SIGNALS_DIR / "dashboard_context.json"
    if not context_path.exists():
        return {}
    with open(context_path, 'r') as f:
        return json.load(f)


@st.cache_data(ttl=30)
def get_live_price() -> float:
    """Fetch live BTC price from Coinbase."""
    try:
        response = requests.get(COINBASE_API, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['data']['amount'])
    except Exception:
        pass
    return None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_number(val, decimals=2):
    """Format number for display."""
    if val is None:
        return "N/A"
    if isinstance(val, str):
        try:
            val = float(val)
        except ValueError:
            return val
    if abs(val) >= 1_000_000_000:
        return f"{val/1_000_000_000:.2f}B"
    if abs(val) >= 1_000_000:
        return f"{val/1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"{val/1_000:.2f}K"
    return f"{val:.{decimals}f}"


def format_price(val):
    """Format price with dollar sign."""
    if val is None:
        return "N/A"
    if isinstance(val, str):
        try:
            val = float(val)
        except ValueError:
            return val
    return f"${val:,.0f}"


def format_percent(val):
    """Format as percentage."""
    if val is None:
        return "N/A"
    return f"{val:.1f}%"


def zone_badge_html(zone: str, color: str) -> str:
    """Generate HTML for zone badge."""
    return f'<span class="zone-badge" style="background:{color}; color:white;">{zone}</span>'


def render_pillar_header(icon: str, title: str, tells_us: str, metrics: str):
    """Render pillar section header."""
    render_html(f"""
    <div class="pillar-header">
        <div class="pillar-title">{icon} {title}</div>
        <div class="pillar-tells"><span style="color:#f59e0b; font-weight:600;">What it tells us:</span> {tells_us}</div>
        <div class="pillar-metrics">Metrics: {metrics}</div>
    </div>
    """)


# =============================================================================
# CARD RENDERERS
# =============================================================================

def render_price_card(ctx: dict, live_price: float = None):
    """Render price levels card."""
    pc = ctx.get('price_context', {})
    price = live_price or pc.get('price', 0)
    levels = pc.get('levels', {})
    zone = pc.get('zone', 'UNKNOWN')
    zone_color = pc.get('zone_color', '#6b7280')

    render_html(f"""
    <div class="metric-card">
        <div class="card-title">📊 Price Levels</div>
        <div style="text-align:center; margin:16px 0;">
            <div class="big-number">{format_price(price)}</div>
            <div style="margin-top:12px;">{zone_badge_html(zone, zone_color)}</div>
        </div>
        <div style="margin-top:20px;">
            <div class="metric-row">
                <span class="metric-label">Vaulted Price</span>
                <span class="metric-value" style="color:#a855f7;">{format_price(levels.get('vaulted_price'))}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">STH Realized</span>
                <span class="metric-value" style="color:#fbbf24;">{format_price(levels.get('sth_realized_price'))}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">True Market Mean</span>
                <span class="metric-value" style="color:#22c55e;">{format_price(levels.get('true_market_mean'))}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Realized Price</span>
                <span class="metric-value" style="color:#ef4444;">{format_price(levels.get('realized_price'))}</span>
            </div>
        </div>
    </div>
    """)


def render_valuation_card(ctx: dict):
    """Render MVRV-Z valuation thermometer card."""
    val = ctx.get('valuation', {})
    mvrv = val.get('mvrv')
    mvrv_z = val.get('mvrv_z')
    aviv = val.get('aviv')
    zone = val.get('zone', 'UNKNOWN')
    zone_color = val.get('zone_color', '#6b7280')

    # MVRV-Z thermometer position (map -1 to 4 range to 0-100%)
    thermo_pos = 0
    if mvrv_z is not None:
        thermo_pos = min(100, max(0, (mvrv_z + 1) / 5 * 100))

    render_html(f"""
    <div class="metric-card">
        <div class="card-title">🌡️ Valuation</div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:24px;">
            <div>
                <div style="text-align:center; margin-bottom:16px;">
                    <div style="font-size:2em; font-weight:bold; color:#f1f5f9;">{format_number(mvrv_z) if mvrv_z else 'N/A'}</div>
                    <div style="color:#9ca3af;">MVRV-Z Score</div>
                </div>
                <div class="thermometer">
                    <div class="thermometer-marker" style="left:{thermo_pos}%;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.75em; color:#9ca3af; margin-top:4px;">
                    <span>Deep Value</span>
                    <span>Fair</span>
                    <span>Expensive</span>
                    <span>Euphoria</span>
                </div>
            </div>
            <div>
                <div class="metric-row">
                    <span class="metric-label">MVRV</span>
                    <span class="metric-value" style="color:#f1f5f9;">{format_number(mvrv)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">AVIV</span>
                    <span class="metric-value" style="color:#f1f5f9;">{format_number(aviv)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Zone</span>
                    <span>{zone_badge_html(zone, zone_color)}</span>
                </div>
            </div>
        </div>
    </div>
    """)


def render_profitability_card(ctx: dict):
    """Render NUPL profitability card."""
    prof = ctx.get('profitability', {})
    supply = ctx.get('supply', {})

    nupl = prof.get('nupl')
    nupl_zone = prof.get('nupl_zone', 'UNKNOWN')
    nupl_color = prof.get('nupl_color', '#6b7280')

    profit_pct = supply.get('profit_percent', 0)
    loss_pct = supply.get('loss_percent', 0)

    # NUPL position (map -0.5 to 1.0 range to 0-100%)
    nupl_pos = 0
    if nupl is not None:
        nupl_pos = min(100, max(0, (nupl + 0.5) / 1.5 * 100))

    render_html(f"""
    <div class="metric-card">
        <div class="card-title">💰 Profitability</div>

        <div style="margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#9ca3af;">NUPL</span>
                <span style="font-weight:bold; color:#f1f5f9;">{format_number(nupl, 3)}</span>
            </div>
            <div style="position:relative; height:16px; background:linear-gradient(to right, #ef4444 0%, #f97316 25%, #22c55e 50%, #3b82f6 75%, #a855f7 100%); border-radius:8px;">
                <div style="position:absolute; left:{nupl_pos}%; top:50%; width:4px; height:20px; background:white; border-radius:2px; transform:translate(-50%, -50%);"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.65em; color:#6b7280; margin-top:2px;">
                <span>Capitulation</span>
                <span>Hope</span>
                <span>Optimism</span>
                <span>Belief</span>
                <span>Euphoria</span>
            </div>
        </div>

        <div style="text-align:center; margin:12px 0;">
            {zone_badge_html(nupl_zone, nupl_color)}
        </div>

        <div style="margin-top:16px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#22c55e;">Profit {format_percent(profit_pct)}</span>
                <span style="color:#ef4444;">Loss {format_percent(loss_pct)}</span>
            </div>
            <div style="height:12px; background:#ef4444; border-radius:6px; overflow:hidden;">
                <div style="height:100%; width:{profit_pct}%; background:#22c55e;"></div>
            </div>
        </div>
    </div>
    """)


def render_sopr_card(ctx: dict):
    """Render SOPR spending behavior card."""
    sopr = ctx.get('sopr', {})

    sopr_val = sopr.get('sopr')
    sth_sopr = sopr.get('sopr_sth')
    lth_sopr = sopr.get('sopr_lth')
    sopr_pos = sopr.get('sopr_position', 50)
    sth_state = sopr.get('sth_state', 'UNKNOWN')
    sth_color = sopr.get('sth_state_color', '#6b7280')
    lth_state = sopr.get('lth_state', 'UNKNOWN')
    lth_color = sopr.get('lth_state_color', '#6b7280')
    pl_ratio = sopr.get('realized_pl_ratio')

    sopr_color = '#22c55e' if sopr_val and sopr_val < 1 else '#ef4444'
    pl_color = '#fbbf24' if pl_ratio and pl_ratio < 1 else '#22c55e'

    render_html(f"""
    <div class="metric-card">
        <div class="card-title">💸 Spending Behavior</div>

        <div style="margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#9ca3af;">SOPR</span>
                <span style="font-weight:bold; color:#f1f5f9;">{format_number(sopr_val, 4)}</span>
            </div>
            <div style="position:relative; height:12px; background:#1f2937; border-radius:6px;">
                <div style="position:absolute; left:50%; top:0; width:2px; height:100%; background:#6b7280;"></div>
                <div style="position:absolute; left:{sopr_pos}%; top:50%; width:12px; height:12px; background:{sopr_color}; border-radius:50%; transform:translate(-50%, -50%);"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.7em; color:#6b7280;">
                <span>Loss (0.9)</span>
                <span>Break-even (1.0)</span>
                <span>Profit (1.1)</span>
            </div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:16px;">
            <div style="text-align:center; padding:8px; background:#1f2937; border-radius:8px;">
                <div style="font-size:1.5em; font-weight:bold; color:#f1f5f9;">{format_number(sth_sopr, 3)}</div>
                <div style="color:#9ca3af; font-size:0.8em;">STH-SOPR</div>
                <div style="color:{sth_color}; font-weight:500; margin-top:4px;">{sth_state}</div>
            </div>
            <div style="text-align:center; padding:8px; background:#1f2937; border-radius:8px;">
                <div style="font-size:1.5em; font-weight:bold; color:#f1f5f9;">{format_number(lth_sopr, 3)}</div>
                <div style="color:#9ca3af; font-size:0.8em;">LTH-SOPR</div>
                <div style="color:{lth_color}; font-weight:500; margin-top:4px;">{lth_state}</div>
            </div>
        </div>

        <div style="margin-top:16px;">
            <div class="metric-row">
                <span class="metric-label">Realized P/L Ratio</span>
                <span class="metric-value" style="color:{pl_color};">{format_number(pl_ratio, 2)}</span>
            </div>
        </div>
    </div>
    """)


def render_supply_card(ctx: dict):
    """Render supply distribution card."""
    supply = ctx.get('supply', {})

    lth_pct = supply.get('lth_percent', 0)
    sth_pct = supply.get('sth_percent', 0)
    state = supply.get('supply_state', 'UNKNOWN')
    state_color = supply.get('supply_state_color', '#6b7280')

    render_html(f"""
    <div class="metric-card">
        <div class="card-title">📦 Supply Dynamics</div>

        <div style="margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#22c55e;">LTH {format_percent(lth_pct)}</span>
                <span style="color:#f97316;">STH {format_percent(sth_pct)}</span>
            </div>
            <div style="height:16px; background:#f97316; border-radius:8px; overflow:hidden;">
                <div style="height:100%; width:{lth_pct}%; background:#22c55e;"></div>
            </div>
        </div>

        <div style="text-align:center; margin-top:16px;">
            {zone_badge_html(state, state_color)}
        </div>

        <div style="margin-top:16px;">
            <div class="metric-row">
                <span class="metric-label">LTH Supply</span>
                <span class="metric-value" style="color:#f1f5f9;">{format_number(supply.get('supply_lth'), 0)}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">STH Supply</span>
                <span class="metric-value" style="color:#f1f5f9;">{format_number(supply.get('supply_sth'), 0)}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">LTH/STH Ratio</span>
                <span class="metric-value" style="color:#f1f5f9;">{format_number(supply.get('lth_sth_ratio'), 2)}</span>
            </div>
        </div>
    </div>
    """)


def render_liveliness_card(ctx: dict):
    """Render liveliness/activity card."""
    live = ctx.get('liveliness', {})

    liveliness = live.get('liveliness')
    vaultedness = live.get('vaultedness')
    state = live.get('activity_state', 'UNKNOWN')
    state_color = live.get('activity_color', '#6b7280')

    live_pct = (liveliness * 100) if liveliness else 0
    vault_pct = (vaultedness * 100) if vaultedness else 0

    render_html(f"""
    <div class="metric-card">
        <div class="card-title">⚡ Liveliness</div>

        <div style="margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#3b82f6;">Liveliness {format_percent(live_pct)}</span>
                <span style="color:#22c55e;">Vaultedness {format_percent(vault_pct)}</span>
            </div>
            <div style="height:16px; background:#22c55e; border-radius:8px; overflow:hidden;">
                <div style="height:100%; width:{live_pct}%; background:#3b82f6;"></div>
            </div>
        </div>

        <div style="text-align:center; margin-top:16px;">
            {zone_badge_html(state, state_color)}
        </div>

        <p style="color:#9ca3af; font-size:0.8em; margin-top:12px;">
            High liveliness = active spending. High vaultedness = HODLing behavior.
        </p>
    </div>
    """)


def render_miner_card(ctx: dict):
    """Render miner health card."""
    miner = ctx.get('miner', {})

    puell = miner.get('puell_multiple')
    puell_zone = miner.get('puell_zone', 'UNKNOWN')
    puell_color = miner.get('puell_color', '#6b7280')

    # Puell position (map 0-8 range to 0-100%)
    puell_pos = 0
    if puell is not None:
        puell_pos = min(100, max(0, puell / 8 * 100))

    render_html(f"""
    <div class="metric-card">
        <div class="card-title">⛏️ Miner Health</div>

        <div style="text-align:center; margin-bottom:16px;">
            <div style="font-size:2em; font-weight:bold; color:#f1f5f9;">{format_number(puell, 2)}</div>
            <div style="color:#9ca3af;">Puell Multiple</div>
        </div>

        <div style="position:relative; height:16px; background:linear-gradient(to right, #22c55e 0%, #6b7280 30%, #f97316 70%, #ef4444 100%); border-radius:8px;">
            <div style="position:absolute; left:{puell_pos}%; top:50%; width:4px; height:20px; background:white; border-radius:2px; transform:translate(-50%, -50%);"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:0.7em; color:#6b7280; margin-top:4px;">
            <span>Capitulation</span>
            <span>Normal</span>
            <span>Profit-taking</span>
        </div>

        <div style="text-align:center; margin-top:16px;">
            {zone_badge_html(puell_zone, puell_color)}
        </div>
    </div>
    """)


def render_buy_the_dip_card(ctx: dict):
    """Render Buy The Dip checklist card."""
    btd = ctx.get('buy_the_dip', {})

    met_count = btd.get('met_count', 0)
    total = btd.get('total', 0)
    signal = btd.get('signal', 'NO DIP')
    signal_color = btd.get('signal_color', '#6b7280')
    conditions = btd.get('conditions', [])

    condition_rows = ""
    for cond in conditions:
        triggered = cond.get('triggered', False)
        icon = "✓" if triggered else "○"
        color = "#22c55e" if triggered else "#6b7280"
        val = cond.get('value')
        val_str = format_number(val, 4) if val is not None else "N/A"
        condition_rows += f'''
            <div class="condition-row">
                <span class="{"condition-met" if triggered else "condition-unmet"}">{icon} {cond.get('label', '')}</span>
                <span style="color:#9ca3af;">{val_str}</span>
            </div>
        '''

    render_html(f"""
    <div class="metric-card">
        <div class="card-title">🛒 Buy The Dip</div>

        <div style="text-align:center; margin:16px 0;">
            <div style="font-size:3em; font-weight:bold; color:{signal_color};">{met_count}/{total}</div>
            <div style="margin-top:8px;">{zone_badge_html(signal, signal_color)}</div>
        </div>

        <div style="margin-top:16px;">
            {condition_rows}
        </div>

        <p style="color:#6b7280; font-size:0.75em; margin-top:12px; text-align:center;">
            James Check: 4+ conditions = strong buy signal
        </p>
    </div>
    """)


def render_lth_distribution_card(ctx: dict):
    """Render LTH Distribution exit signal card."""
    lth_dist = ctx.get('lth_distribution', {})

    signal = lth_dist.get('signal', 'UNKNOWN')
    signal_color = lth_dist.get('signal_color', '#6b7280')
    interpretation = lth_dist.get('interpretation', '')

    mvrv = lth_dist.get('mvrv')
    mvrv_threshold = lth_dist.get('mvrv_threshold', 2.0)
    mvrv_triggered = lth_dist.get('mvrv_triggered', False)

    lth_sopr = lth_dist.get('lth_sopr')
    lth_sopr_threshold = lth_dist.get('lth_sopr_threshold', 1.5)
    lth_sopr_triggered = lth_dist.get('lth_sopr_triggered', False)

    both_triggered = lth_dist.get('both_triggered', False)

    mvrv_icon = "✓" if mvrv_triggered else "○"
    mvrv_color = "#ef4444" if mvrv_triggered else "#6b7280"
    sopr_icon = "✓" if lth_sopr_triggered else "○"
    sopr_color = "#ef4444" if lth_sopr_triggered else "#6b7280"
    bg_color = "#7f1d1d" if both_triggered else "#1e293b"

    render_html(f"""
    <div class="metric-card">
        <div class="card-title">💎 LTH Distribution</div>

        <div style="text-align:center; margin:16px 0;">
            {zone_badge_html(signal, signal_color)}
        </div>

        <div style="margin-top:16px;">
            <div style="display:flex; justify-content:space-between; padding:12px; background:#1e293b; border-radius:6px; margin:8px 0;">
                <div>
                    <span style="color:{mvrv_color}; font-weight:bold;">{mvrv_icon} MVRV</span>
                    <div style="color:#6b7280; font-size:0.75em;">Threshold: {mvrv_threshold}</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:1.5em; font-weight:bold; color:{mvrv_color};">{format_number(mvrv, 2)}</div>
                </div>
            </div>

            <div style="display:flex; justify-content:space-between; padding:12px; background:#1e293b; border-radius:6px; margin:8px 0;">
                <div>
                    <span style="color:{sopr_color}; font-weight:bold;">{sopr_icon} LTH-SOPR</span>
                    <div style="color:#6b7280; font-size:0.75em;">Threshold: {lth_sopr_threshold}</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:1.5em; font-weight:bold; color:{sopr_color};">{format_number(lth_sopr, 2)}</div>
                </div>
            </div>
        </div>

        <div style="background:{bg_color}; padding:10px; border-radius:6px; margin:12px 0; text-align:center;">
            <div style="color:#9ca3af; font-size:0.75em;">Interpretation</div>
            <div style="color:#f1f5f9; font-weight:500; font-size:0.9em;">{interpretation}</div>
        </div>
    </div>
    """)


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Load data
    ctx = load_dashboard_context()

    if not ctx:
        st.error("No dashboard data found. Run `python scripts/calculate.py` first.")
        st.code("source venv/bin/activate && python scripts/calculate.py", language="bash")
        return

    # Get live price
    live_price = get_live_price()

    # Get metadata
    meta = ctx.get('meta', {})
    calculated_at = meta.get('calculated_at', 'Unknown')
    data_as_of = meta.get('data_as_of', 'Unknown')

    try:
        calc_time = datetime.fromisoformat(calculated_at).strftime("%Y-%m-%d %H:%M")
    except:
        calc_time = calculated_at

    try:
        data_time = datetime.fromisoformat(data_as_of).strftime("%Y-%m-%d")
    except:
        data_time = data_as_of

    # Header
    render_html(f"""
    <div style="text-align:center; margin-bottom:32px;">
        <h1 style="font-size:2em; margin-bottom:8px;">₿ Bitcoin Trading Dashboard</h1>
        <div style="color:#6b7280; font-size:0.85em;">
            Data as of: {data_time} | Calculated: {calc_time} {'| Live price enabled' if live_price else ''}
        </div>
    </div>
    """)

    # PILLAR 1: VALUATION
    render_pillar_header(
        "🌡️", "1. Valuation",
        "How expensive is BTC vs historical norms? Uses cost-basis models to assess if market is over/undervalued.",
        "MVRV, MVRV-Z, AVIV, Price Levels"
    )
    col1, col2 = st.columns(2)
    with col1:
        render_price_card(ctx, live_price)
    with col2:
        render_valuation_card(ctx)

    # PILLAR 2: PROFITABILITY
    render_pillar_header(
        "💰", "2. Profitability",
        "How much paper gains/losses exist? Measures unrealized profit across the holder base — high values signal greed, low signal fear.",
        "NUPL, Supply in Profit/Loss, Unrealized P/L"
    )
    col1, col2 = st.columns(2)
    with col1:
        render_profitability_card(ctx)

    # PILLAR 3: SPENDING BEHAVIOR
    render_pillar_header(
        "💸", "3. Spending Behavior",
        "What are holders actually doing? Tracks realized profit/loss when coins move — reveals capitulation and profit-taking.",
        "SOPR, STH/LTH-SOPR, Realized P/L Ratio"
    )
    col1, col2 = st.columns(2)
    with col1:
        render_sopr_card(ctx)

    # PILLAR 4: SUPPLY DISTRIBUTION
    render_pillar_header(
        "📦", "4. Supply Distribution",
        "Who holds the coins and for how long? High LTH% = strong hands dominate; rising STH% = new speculative demand.",
        "LTH/STH Supply, Age Bands, Wallet Cohorts"
    )
    col1, col2 = st.columns(2)
    with col1:
        render_supply_card(ctx)

    # PILLAR 5: ACTIVITY
    render_pillar_header(
        "⚡", "5. Activity",
        "Are coins moving or dormant? High liveliness = active spending; high vaultedness = HODLing conviction.",
        "Liveliness, Vaultedness, Coindays Destroyed"
    )
    col1, col2 = st.columns(2)
    with col1:
        render_liveliness_card(ctx)

    # PILLAR 6: MINER HEALTH
    render_pillar_header(
        "⛏️", "6. Miner Health",
        "Are miners profitable or under stress? Miner capitulation often marks cycle lows; high Puell = overheated.",
        "Puell Multiple, Difficulty, Thermocap"
    )
    col1, col2 = st.columns(2)
    with col1:
        render_miner_card(ctx)

    # TRADING SIGNALS SECTION
    st.markdown("---")
    render_html("""
    <div style="text-align:center; margin:32px 0 24px 0;">
        <h2 style="font-size:1.6em; color:#f59e0b; margin-bottom:8px;">🎯 Trading Signals</h2>
        <p style="color:#9ca3af; font-size:0.9em;">James Check Framework entry/exit indicators</p>
    </div>
    """)

    col1, col2 = st.columns(2)
    with col1:
        render_buy_the_dip_card(ctx)
    with col2:
        render_lth_distribution_card(ctx)

    # Footer
    render_html("""
    <div style="text-align:center; margin-top:32px; color:#6b7280; font-size:0.8em;">
        <p>James Check Framework — 6 Pillars of On-Chain Analysis</p>
    </div>
    """)


if __name__ == "__main__":
    main()
