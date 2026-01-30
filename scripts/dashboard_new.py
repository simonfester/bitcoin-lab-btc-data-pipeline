#!/usr/bin/env python3
"""
Bitcoin Trading Dashboard - Display Only
=========================================
Reads pre-computed signals from data/signals/ and renders HTML dashboard.

Usage:
    python dashboard.py              # Generate dashboard
    python dashboard.py --watch      # Auto-refresh every 60 seconds
    python dashboard.py --no-open    # Generate without opening browser

Prerequisites:
    Run calculate.py first to generate signal data.
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import webbrowser
import sys
import time
import requests

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
SIGNALS_DIR = PROJECT_ROOT / "data" / "signals"
DASHBOARDS_DIR = PROJECT_ROOT / "dashboards"
OUTPUT_PATH = DASHBOARDS_DIR / "dashboard.html"

# Ensure dashboards directory exists
DASHBOARDS_DIR.mkdir(exist_ok=True)

# Live price API (only external call dashboard makes)
COINBASE_API = "https://api.coinbase.com/v2/prices/BTC-USD/spot"

# =============================================================================
# DATA LOADING
# =============================================================================

def load_dashboard_context(resolution: str = "daily") -> dict:
    """Load pre-computed dashboard context from JSON."""
    suffix = "_hourly" if resolution == "hourly" else ""
    context_path = SIGNALS_DIR / f"dashboard_context{suffix}.json"
    if not context_path.exists():
        raise FileNotFoundError(
            f"Dashboard context not found: {context_path}\n"
            f"Run 'python calculate.py{' --resolution hourly' if resolution == 'hourly' else ''}' first."
        )

    with open(context_path, 'r') as f:
        return json.load(f)


def get_live_price() -> tuple:
    """Fetch live BTC price from Coinbase (optional)."""
    try:
        response = requests.get(COINBASE_API, timeout=5)
        if response.status_code == 200:
            data = response.json()
            price = float(data['data']['amount'])
            return price, datetime.now()
    except Exception:
        pass
    return None, None


# =============================================================================
# HTML GENERATION HELPERS
# =============================================================================

def format_number(val, decimals=2, prefix="", suffix=""):
    """Format number for display."""
    if val is None:
        return "N/A"
    # Handle string values from JSON
    if isinstance(val, str):
        try:
            val = float(val)
        except ValueError:
            return val
    if abs(val) >= 1_000_000_000:
        return f"{prefix}{val/1_000_000_000:.2f}B{suffix}"
    if abs(val) >= 1_000_000:
        return f"{prefix}{val/1_000_000:.2f}M{suffix}"
    if abs(val) >= 1_000:
        return f"{prefix}{val/1_000:.2f}K{suffix}"
    return f"{prefix}{val:.{decimals}f}{suffix}"


def format_btc_supply(val):
    """Format BTC supply value (stored in satoshis) as human-readable BTC."""
    if val is None:
        return "N/A"
    if isinstance(val, str):
        try:
            val = float(val)
        except ValueError:
            return val
    # Convert from satoshis to BTC
    btc = val / 1e8
    if btc >= 1_000_000:
        return f"{btc/1_000_000:.2f}M BTC"
    if btc >= 1_000:
        return f"{btc/1_000:.1f}K BTC"
    return f"{btc:.0f} BTC"


def format_price(val):
    """Format price with dollar sign and commas."""
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
    if isinstance(val, str):
        try:
            val = float(val)
        except ValueError:
            return val
    return f"{val:.1f}%"


def signal_badge(triggered: bool, label: str) -> str:
    """Generate HTML for signal badge."""
    color = "#22c55e" if triggered else "#6b7280"
    icon = "✓" if triggered else "○"
    return f'<span style="color:{color}; font-weight:bold;">{icon} {label}</span>'


def zone_badge(zone: str, color: str) -> str:
    """Generate HTML for zone badge."""
    return f'<span style="background:{color}; color:white; padding:2px 8px; border-radius:4px; font-weight:bold;">{zone}</span>'


def progress_bar(value: float, max_val: float = 100, color: str = "#3b82f6", height: int = 8) -> str:
    """Generate HTML for progress bar."""
    pct = min(100, max(0, (value / max_val) * 100)) if max_val else 0
    return f'''
        <div style="background:#1f2937; border-radius:4px; height:{height}px; width:100%; overflow:hidden;">
            <div style="background:{color}; height:100%; width:{pct}%; transition:width 0.3s;"></div>
        </div>
    '''


def metric_row(label: str, value, color: str = "#fff") -> str:
    """Generate HTML for metric row."""
    return f'''
        <div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #374151;">
            <span style="color:#9ca3af;">{label}</span>
            <span style="color:{color}; font-weight:500;">{value}</span>
        </div>
    '''


# =============================================================================
# CARD GENERATORS
# =============================================================================

def _load_price_chart_data() -> dict:
    """Load price + cost basis time series for chart rendering.

    Primary source: Bitcoin Lab hourly (resampled to daily).
    Fallback: BRK daily (if BL unavailable for a metric).
    """
    bl_dir = PROJECT_ROOT / "data" / "bl" / "hourly"
    brk_dir = PROJECT_ROOT / "data" / "brk" / "daily"
    series_map = {
        'price': ('price', '#f7931a'),
        'realized_price': ('Realized Price', '#ef4444'),
        'true_market_mean_price': ('True Mkt Mean', '#22c55e'),
        'realized_price_sth': ('STH Realized', '#fbbf24'),
        'vaulted_price': ('Vaulted Price', '#a855f7'),
    }
    result = {}
    for filename, (label, color) in series_map.items():
        # Try Bitcoin Lab first, fall back to BRK
        bl_path = bl_dir / f"{filename}.parquet"
        brk_path = brk_dir / f"{filename}.parquet"
        path = bl_path if bl_path.exists() else brk_path
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        # Last 2 years of data
        cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=730)
        df = df[df['time'] >= cutoff].copy()
        df = df.sort_values('time')
        # Resample hourly data to daily (last value per day) for chart performance
        if path == bl_path:
            df = df.set_index('time').resample('1D').last().dropna().reset_index()
        # Convert to lightweight-charts format: {time: 'YYYY-MM-DD', value: float}
        records = []
        for _, row in df.iterrows():
            t = row['time']
            v = row['value']
            if pd.notna(v) and v > 0:
                records.append({'time': t.strftime('%Y-%m-%d'), 'value': round(float(v), 2)})
        result[filename] = {'label': label, 'color': color, 'data': records}
    return result


def generate_price_hero(ctx: dict, live_price: float = None) -> str:
    """Generate full-width price hero section with interactive time-series chart."""
    pc = ctx['price_context']
    price = live_price or pc.get('price')
    zone = pc.get('zone', 'UNKNOWN')
    zone_color = pc.get('zone_color', '#6b7280')
    change_24h = pc.get('change_24h')
    change_7d = pc.get('change_7d')

    def change_html(val, label):
        if val is None:
            return f'<div style="color:#6b7280; font-size:0.85em;">{label}: N/A</div>'
        color = '#22c55e' if val >= 0 else '#ef4444'
        arrow = '\u25B2' if val >= 0 else '\u25BC'
        return f'<div style="color:{color}; font-size:1.1em; font-weight:600;">{arrow} {val:+.1f}% <span style="color:#6b7280; font-weight:400; font-size:0.8em;">{label}</span></div>'

    # Load time series data
    chart_data = _load_price_chart_data()
    chart_data_json = json.dumps(chart_data)

    return f'''
        <div class="card" style="margin-bottom:24px; padding:24px 32px;">
            <!-- Top row: Price, changes, zone -->
            <div style="display:flex; align-items:baseline; gap:20px; flex-wrap:wrap; margin-bottom:16px;">
                <div style="font-size:2.8em; font-weight:bold; letter-spacing:-1px;">{format_price(price)}</div>
                <div style="display:flex; gap:14px; align-items:center;">
                    {change_html(change_24h, '24h')}
                    {change_html(change_7d, '7d')}
                </div>
                <div>{zone_badge(zone, zone_color)}</div>
            </div>
            <!-- Chart container -->
            <div id="price-chart" style="width:100%; height:420px;"></div>
            <!-- Legend -->
            <div style="display:flex; gap:20px; margin-top:10px; flex-wrap:wrap;">
                <span style="color:#f7931a; font-size:0.8em; font-weight:600;">\u2501\u2501 Price</span>
                <span style="color:#ef4444; font-size:0.8em; font-weight:600;">\u2501\u2501 Realized</span>
                <span style="color:#22c55e; font-size:0.8em; font-weight:600;">\u2501\u2501 True Mkt Mean</span>
                <span style="color:#fbbf24; font-size:0.8em; font-weight:600;">\u2501\u2501 STH Realized</span>
                <span style="color:#a855f7; font-size:0.8em; font-weight:600;">\u2501\u2501 Vaulted</span>
            </div>
        </div>
        <script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
        <script>
        (function() {{
            var chartData = {chart_data_json};
            var container = document.getElementById('price-chart');
            var chart = LightweightCharts.createChart(container, {{
                layout: {{
                    background: {{ type: 'solid', color: '#1e293b' }},
                    textColor: '#94a3b8',
                    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(51, 65, 85, 0.5)' }},
                    horzLines: {{ color: 'rgba(51, 65, 85, 0.5)' }},
                }},
                rightPriceScale: {{
                    borderColor: '#334155',
                    scaleMargins: {{ top: 0.05, bottom: 0.05 }},
                }},
                timeScale: {{
                    borderColor: '#334155',
                    timeVisible: false,
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {{ color: 'rgba(148, 163, 184, 0.3)', labelBackgroundColor: '#475569' }},
                    horzLine: {{ color: 'rgba(148, 163, 184, 0.3)', labelBackgroundColor: '#475569' }},
                }},
                handleScroll: true,
                handleScale: true,
            }});

            var seriesOrder = ['price', 'realized_price', 'true_market_mean_price', 'realized_price_sth', 'vaulted_price'];
            var lineWidths = {{ 'price': 2, 'realized_price': 1, 'true_market_mean_price': 1, 'realized_price_sth': 1, 'vaulted_price': 1 }};

            seriesOrder.forEach(function(key) {{
                if (!chartData[key]) return;
                var s = chartData[key];
                var series = chart.addLineSeries({{
                    color: s.color,
                    lineWidth: lineWidths[key] || 1,
                    crosshairMarkerVisible: key === 'price',
                    lastValueVisible: key === 'price',
                    priceLineVisible: false,
                    title: key === 'price' ? '' : s.label,
                }});
                series.setData(s.data);
            }});

            chart.timeScale().fitContent();

            // Resize handler
            var ro = new ResizeObserver(function(entries) {{
                var cr = entries[0].contentRect;
                chart.applyOptions({{ width: cr.width, height: cr.height }});
            }});
            ro.observe(container);
        }})();
        </script>
    '''


def _gauge_bar(value: float, min_val: float, max_val: float, colors: list, labels: list, height: int = 8) -> str:
    """Render a horizontal gauge bar with a needle marker. CSS-only, no JS."""
    rng = max_val - min_val
    pos = min(100, max(0, (value - min_val) / rng * 100)) if rng else 0
    gradient = ', '.join(f'{c} {i * 100 // (len(colors) - 1)}%' for i, c in enumerate(colors))
    label_html = ''.join(f'<span>{l}</span>' for l in labels)
    return f'''
        <div style="position:relative; height:{height}px; background:linear-gradient(to right, {gradient}); border-radius:{height // 2}px; margin:4px 0;">
            <div style="position:absolute; left:{pos:.1f}%; top:50%; width:3px; height:{height + 8}px; background:#f1f5f9; border-radius:1.5px; transform:translate(-50%,-50%); box-shadow:0 0 6px rgba(241,245,249,0.4);"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:0.65em; color:#64748b; margin-top:2px; padding:0 2px;">
            {label_html}
        </div>'''


def _stat_cell(value: str, label: str, color: str = '#f1f5f9', sub: str = '') -> str:
    """Render a single stat inside a dark cell."""
    sub_html = f'<div style="color:{color}; font-size:0.7em; font-weight:500; margin-top:2px;">{sub}</div>' if sub else ''
    return f'''
        <div style="text-align:center; padding:12px 8px; background:#0f172a; border-radius:8px; border:1px solid #1e293b;">
            <div style="font-size:1.6em; font-weight:700; color:{color}; letter-spacing:-0.5px;">{value}</div>
            <div style="color:#64748b; font-size:0.7em; font-weight:500; margin-top:4px; text-transform:uppercase; letter-spacing:0.5px;">{label}</div>
            {sub_html}
        </div>'''


def _condition_row(icon: str, color: str, label: str, value_str: str) -> str:
    """Render a single condition row for checklists."""
    return f'''
        <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 10px; border-bottom:1px solid rgba(51,65,85,0.5);">
            <span style="color:{color}; font-weight:500; font-size:0.85em;">{icon} {label}</span>
            <span style="color:#94a3b8; font-size:0.85em; font-family:'SF Mono',Menlo,monospace;">{value_str}</span>
        </div>'''


def generate_valuation_card(ctx: dict) -> str:
    """Generate valuation thermometer card."""
    val = ctx['valuation']
    mvrv = val.get('mvrv')
    mvrv_z = val.get('mvrv_z')
    aviv = val.get('aviv')
    zone = val.get('zone', 'UNKNOWN')
    zone_color = val.get('zone_color', '#6b7280')

    gauge = _gauge_bar(
        mvrv_z if mvrv_z is not None else 0, -1, 4,
        ['#22c55e', '#3b82f6', '#f97316', '#ef4444'],
        ['Deep Value', 'Fair', 'Expensive', 'Euphoria'],
        height=8,
    )

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">Valuation</h3>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-bottom:18px;">
                {_stat_cell(format_number(mvrv_z) if mvrv_z else 'N/A', 'MVRV-Z', zone_color)}
                {_stat_cell(format_number(mvrv) if mvrv else 'N/A', 'MVRV')}
                {_stat_cell(format_number(aviv) if aviv else 'N/A', 'AVIV')}
            </div>
            {gauge}
            <div style="text-align:center; margin-top:14px;">
                {zone_badge(zone, zone_color)}
            </div>
        </div>
    '''


def generate_sopr_card(ctx: dict) -> str:
    """Generate spending behavior card."""
    sopr = ctx['sopr']
    sopr_val = sopr.get('sopr')
    sth_sopr = sopr.get('sopr_sth')
    lth_sopr = sopr.get('sopr_lth')
    sopr_pos = sopr.get('sopr_position', 50)
    sth_state = sopr.get('sth_state', 'UNKNOWN')
    sth_color = sopr.get('sth_state_color', '#6b7280')
    lth_state = sopr.get('lth_state', 'UNKNOWN')
    lth_color = sopr.get('lth_state_color', '#6b7280')
    pl_ratio = sopr.get('realized_pl_ratio')

    sopr_color = '#22c55e' if sopr_val and sopr_val < 1 else '#ef4444' if sopr_val else '#6b7280'
    gauge = _gauge_bar(
        sopr_val if sopr_val is not None else 1.0, 0.9, 1.1,
        ['#22c55e', '#64748b', '#ef4444'],
        ['Loss (0.9)', 'Break-even', 'Profit (1.1)'],
        height=8,
    )

    pl_color = '#fbbf24' if pl_ratio and pl_ratio < 1 else '#22c55e'

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">Spending Behavior</h3>
            <div style="margin-bottom:18px;">
                <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">
                    <span style="color:#64748b; font-size:0.75em; text-transform:uppercase; letter-spacing:0.5px;">SOPR</span>
                    <span style="font-weight:700; font-size:1.1em; color:{sopr_color}; font-family:'SF Mono',Menlo,monospace;">{format_number(sopr_val, 4)}</span>
                </div>
                {gauge}
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:14px;">
                {_stat_cell(format_number(sth_sopr, 3), 'STH-SOPR', sth_color, sth_state)}
                {_stat_cell(format_number(lth_sopr, 3), 'LTH-SOPR', lth_color, lth_state)}
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 12px; background:#0f172a; border-radius:8px; border:1px solid #1e293b;">
                <span style="color:#64748b; font-size:0.75em; text-transform:uppercase; letter-spacing:0.5px;">Realized P/L Ratio</span>
                <span style="color:{pl_color}; font-weight:700; font-family:'SF Mono',Menlo,monospace;">{format_number(pl_ratio, 2)}</span>
            </div>
        </div>
    '''


def generate_profitability_card(ctx: dict) -> str:
    """Generate profitability card with NUPL."""
    prof = ctx['profitability']
    supply = ctx['supply']
    nupl = prof.get('nupl')
    nupl_zone = prof.get('nupl_zone', 'UNKNOWN')
    nupl_color = prof.get('nupl_color', '#6b7280')
    profit_pct = supply.get('profit_percent', 0)
    loss_pct = supply.get('loss_percent', 0)

    gauge = _gauge_bar(
        nupl if nupl is not None else 0, -0.5, 1.0,
        ['#ef4444', '#f97316', '#22c55e', '#3b82f6', '#a855f7'],
        ['Capitulation', 'Hope', 'Optimism', 'Belief', 'Euphoria'],
        height=8,
    )

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">Profitability</h3>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:18px;">
                {_stat_cell(format_number(nupl, 3) if nupl is not None else 'N/A', 'NUPL', nupl_color)}
                {_stat_cell(zone_badge(nupl_zone, nupl_color), 'Emotion')}
            </div>
            <div style="margin-bottom:18px;">
                {gauge}
            </div>
            <div style="padding:12px; background:#0f172a; border-radius:8px; border:1px solid #1e293b;">
                <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                    <span style="color:#22c55e; font-size:0.8em; font-weight:600;">Profit {format_percent(profit_pct)}</span>
                    <span style="color:#ef4444; font-size:0.8em; font-weight:600;">Loss {format_percent(loss_pct)}</span>
                </div>
                <div style="height:8px; background:#ef4444; border-radius:4px; overflow:hidden;">
                    <div style="height:100%; width:{profit_pct}%; background:#22c55e; border-radius:4px;"></div>
                </div>
                <div style="color:#64748b; font-size:0.65em; text-align:center; margin-top:4px;">Supply in Profit vs Loss</div>
            </div>
        </div>
    '''


def generate_supply_card(ctx: dict) -> str:
    """Generate supply dynamics card."""
    supply = ctx['supply']
    lth_pct = supply.get('lth_percent', 0)
    sth_pct = supply.get('sth_percent', 0)
    state = supply.get('supply_state', 'UNKNOWN')
    state_color = supply.get('supply_state_color', '#6b7280')

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">Supply Distribution</h3>
            <div style="padding:12px; background:#0f172a; border-radius:8px; border:1px solid #1e293b; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                    <span style="color:#22c55e; font-size:0.8em; font-weight:600;">LTH {format_percent(lth_pct)}</span>
                    <span style="color:#f97316; font-size:0.8em; font-weight:600;">STH {format_percent(sth_pct)}</span>
                </div>
                <div style="height:8px; background:#f97316; border-radius:4px; overflow:hidden;">
                    <div style="height:100%; width:{lth_pct}%; background:#22c55e; border-radius:4px;"></div>
                </div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:14px;">
                {_stat_cell(format_btc_supply(supply.get('supply_lth')), 'LTH Supply', '#22c55e')}
                {_stat_cell(format_btc_supply(supply.get('supply_sth')), 'STH Supply', '#f97316')}
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 12px; background:#0f172a; border-radius:8px; border:1px solid #1e293b; margin-bottom:14px;">
                <span style="color:#64748b; font-size:0.75em; text-transform:uppercase; letter-spacing:0.5px;">LTH / STH Ratio</span>
                <span style="color:#f1f5f9; font-weight:700; font-family:'SF Mono',Menlo,monospace;">{format_number(supply.get('lth_sth_ratio'), 2)}</span>
            </div>
            <div style="text-align:center;">
                {zone_badge(state, state_color)}
            </div>
        </div>
    '''


def generate_liveliness_card(ctx: dict) -> str:
    """Generate liveliness/activity card."""
    live = ctx['liveliness']
    liveliness = live.get('liveliness')
    vaultedness = live.get('vaultedness')
    state = live.get('activity_state', 'UNKNOWN')
    state_color = live.get('activity_color', '#6b7280')
    live_pct = (liveliness * 100) if liveliness else 0
    vault_pct = (vaultedness * 100) if vaultedness else 0

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">Activity</h3>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:18px;">
                {_stat_cell(format_percent(live_pct), 'Liveliness', '#3b82f6')}
                {_stat_cell(format_percent(vault_pct), 'Vaultedness', '#22c55e')}
            </div>
            <div style="padding:12px; background:#0f172a; border-radius:8px; border:1px solid #1e293b; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                    <span style="color:#3b82f6; font-size:0.8em; font-weight:600;">Spending</span>
                    <span style="color:#22c55e; font-size:0.8em; font-weight:600;">HODLing</span>
                </div>
                <div style="height:8px; background:#22c55e; border-radius:4px; overflow:hidden;">
                    <div style="height:100%; width:{live_pct}%; background:#3b82f6; border-radius:4px;"></div>
                </div>
            </div>
            <div style="text-align:center;">
                {zone_badge(state, state_color)}
            </div>
        </div>
    '''


def generate_miner_card(ctx: dict) -> str:
    """Generate miner health card."""
    miner = ctx['miner']
    puell = miner.get('puell_multiple')
    puell_zone = miner.get('puell_zone', 'UNKNOWN')
    puell_color = miner.get('puell_color', '#6b7280')

    gauge = _gauge_bar(
        puell if puell is not None else 0, 0, 8,
        ['#22c55e', '#64748b', '#f97316', '#ef4444'],
        ['Capitulation', 'Normal', 'Profit-taking', 'Overheated'],
        height=8,
    )

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">Miner Health</h3>
            <div style="margin-bottom:18px;">
                {_stat_cell(format_number(puell, 2) if puell else 'N/A', 'Puell Multiple', puell_color)}
            </div>
            {gauge}
            <div style="text-align:center; margin-top:14px;">
                {zone_badge(puell_zone, puell_color)}
            </div>
        </div>
    '''


def generate_checkmate_card(ctx: dict) -> str:
    """Generate Checkmate composite signal card."""
    cm = ctx['checkmate']
    score = cm.get('score', 0)
    total = cm.get('total', 0)
    signal = cm.get('signal', 'NO SIGNAL')
    signal_color = cm.get('signal_color', '#6b7280')
    conditions = cm.get('conditions', [])

    condition_rows = ""
    for cond in conditions:
        met = cond.get('met')
        icon = "&#10003;" if met else "&#9675;"
        color = "#22c55e" if met else "#475569"
        val = cond.get('value')
        val_str = format_number(val, 4) if val is not None else "N/A"
        condition_rows += _condition_row(icon, color, cond.get('name', ''), val_str)

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">Checkmate Signal</h3>
            <div style="text-align:center; margin-bottom:16px;">
                <div style="font-size:2.8em; font-weight:800; color:{signal_color}; letter-spacing:-1px;">{score}<span style="font-size:0.45em; color:#64748b; font-weight:500;">/{total}</span></div>
                <div style="margin-top:6px;">{zone_badge(signal, signal_color)}</div>
            </div>
            <div style="background:#0f172a; border-radius:8px; border:1px solid #1e293b; overflow:hidden;">
                {condition_rows}
            </div>
        </div>
    '''


def generate_btd_card(ctx: dict) -> str:
    """Generate Buy The Dip checklist card."""
    btd = ctx['buy_the_dip']
    met_count = btd.get('met_count', 0)
    total = btd.get('total', 0)
    signal = btd.get('signal', 'NO DIP')
    signal_color = btd.get('signal_color', '#6b7280')
    conditions = btd.get('conditions', [])

    condition_rows = ""
    for cond in conditions:
        triggered = cond.get('triggered', False)
        icon = "&#10003;" if triggered else "&#9675;"
        color = "#22c55e" if triggered else "#475569"
        val = cond.get('value')
        val_str = format_number(val, 4) if val is not None else "N/A"
        condition_rows += _condition_row(icon, color, cond.get('label', ''), val_str)

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">Buy The Dip</h3>
            <div style="text-align:center; margin-bottom:16px;">
                <div style="font-size:3em; font-weight:800; color:{signal_color}; letter-spacing:-1px;">{met_count}<span style="font-size:0.4em; color:#64748b; font-weight:500;">/{total}</span></div>
                <div style="margin-top:6px;">{zone_badge(signal, signal_color)}</div>
            </div>
            <div style="background:#0f172a; border-radius:8px; border:1px solid #1e293b; overflow:hidden;">
                {condition_rows}
            </div>
            <div style="color:#475569; font-size:0.7em; margin-top:10px; text-align:center;">4+ conditions = strong buy signal</div>
        </div>
    '''


def generate_8_metric_exit_card(ctx: dict) -> str:
    """Generate 8-Metric Cycle Extreme Detector card."""
    exit_8 = ctx.get('exit_8_metric', {})
    met_count = exit_8.get('met_count', 0)
    total = exit_8.get('total', 0)
    signal = exit_8.get('signal', 'UNKNOWN')
    signal_color = exit_8.get('signal_color', '#6b7280')
    recommendation = exit_8.get('recommendation', '')
    conditions = exit_8.get('conditions', [])

    if met_count >= 6:
        title_color = "#ef4444"
    elif met_count >= 4:
        title_color = "#f97316"
    elif met_count >= 2:
        title_color = "#fbbf24"
    else:
        title_color = "#22c55e"

    condition_rows = ""
    for cond in conditions:
        triggered = cond.get('triggered', False)
        icon = "&#10003;" if triggered else "&#9675;"
        color = "#ef4444" if triggered else "#475569"
        z_score = cond.get('z_score')
        z_str = f"{z_score:+.2f}\u03c3" if z_score is not None else "N/A"
        condition_rows += _condition_row(icon, color, cond.get('label', '')[:22], z_str)

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">8-Metric Exit Detector</h3>
            <div style="text-align:center; margin-bottom:16px;">
                <div style="font-size:3em; font-weight:800; color:{title_color}; letter-spacing:-1px;">{met_count}<span style="font-size:0.4em; color:#64748b; font-weight:500;">/{total}</span></div>
                <div style="margin-top:6px;">{zone_badge(signal, signal_color)}</div>
            </div>
            <div style="padding:10px 12px; background:#0f172a; border-radius:8px; border:1px solid #1e293b; margin-bottom:12px; text-align:center;">
                <div style="color:#475569; font-size:0.65em; text-transform:uppercase; letter-spacing:0.5px;">Recommendation</div>
                <div style="color:#f1f5f9; font-weight:600; font-size:0.9em; margin-top:2px;">{recommendation}</div>
            </div>
            <div style="background:#0f172a; border-radius:8px; border:1px solid #1e293b; overflow:hidden; max-height:240px; overflow-y:auto;">
                {condition_rows}
            </div>
            <div style="color:#475569; font-size:0.65em; margin-top:10px; text-align:center;">4/8 = Caution &middot; 6/8 = High Risk</div>
        </div>
    '''


def generate_sth_zones_card(ctx: dict) -> str:
    """Generate STH-MVRV Zones card for local tops."""
    sth_zones = ctx.get('sth_mvrv_zones', {})
    zone = sth_zones.get('zone', 'UNKNOWN')
    zone_color = sth_zones.get('zone_color', '#6b7280')
    current_value = sth_zones.get('current_value')
    z_score = sth_zones.get('z_score')
    interpretation = sth_zones.get('interpretation', '')
    price_levels = sth_zones.get('price_levels', {})
    current_price = sth_zones.get('current_price')

    z_str = f"{z_score:+.2f}\u03c3" if z_score is not None else "N/A"

    price_rows = ""
    if price_levels:
        level_colors = {'warming': '#fbbf24', 'local_top': '#f97316', 'overheated': '#ef4444'}
        for level, lprice in price_levels.items():
            level_name = level.replace('_', ' ').title()
            lc = level_colors.get(level, '#64748b')
            price_rows += f'''
                <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 10px; border-bottom:1px solid rgba(51,65,85,0.5);">
                    <span style="color:{lc}; font-size:0.85em; font-weight:500;">{level_name}</span>
                    <span style="color:#f1f5f9; font-weight:600; font-family:'SF Mono',Menlo,monospace; font-size:0.85em;">{format_price(lprice)}</span>
                </div>'''

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">STH-MVRV Zones</h3>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:14px;">
                {_stat_cell(format_number(current_value, 4) if current_value else 'N/A', 'STH-MVRV', zone_color)}
                {_stat_cell(z_str, 'Z-Score')}
            </div>
            <div style="text-align:center; margin-bottom:14px;">{zone_badge(zone, zone_color)}</div>
            <div style="padding:10px 12px; background:#0f172a; border-radius:8px; border:1px solid #1e293b; margin-bottom:12px; text-align:center;">
                <div style="color:#475569; font-size:0.65em; text-transform:uppercase; letter-spacing:0.5px;">Current Price</div>
                <div style="color:#f1f5f9; font-weight:700; font-size:1.4em; letter-spacing:-0.5px; margin-top:2px;">{format_price(current_price)}</div>
            </div>
            <div style="background:#0f172a; border-radius:8px; border:1px solid #1e293b; overflow:hidden; margin-bottom:12px;">
                <div style="color:#475569; font-size:0.65em; text-transform:uppercase; letter-spacing:0.5px; padding:8px 10px; border-bottom:1px solid rgba(51,65,85,0.5);">Local Top Price Levels</div>
                {price_rows}
            </div>
            <div style="color:#64748b; font-size:0.75em; line-height:1.5;">{interpretation}</div>
        </div>
    '''


def generate_lth_distribution_card(ctx: dict) -> str:
    """Generate LTH Distribution Signal card."""
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

    mvrv_color = "#ef4444" if mvrv_triggered else "#475569"
    sopr_color = "#ef4444" if lth_sopr_triggered else "#475569"
    mvrv_icon = "&#10003;" if mvrv_triggered else "&#9675;"
    sopr_icon = "&#10003;" if lth_sopr_triggered else "&#9675;"

    alert_bg = '#450a0a' if both_triggered else '#0f172a'
    alert_border = '#7f1d1d' if both_triggered else '#1e293b'

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">LTH Distribution</h3>
            <div style="text-align:center; margin-bottom:16px;">
                {zone_badge(signal, signal_color)}
            </div>
            <div style="background:#0f172a; border-radius:8px; border:1px solid #1e293b; overflow:hidden; margin-bottom:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 14px; border-bottom:1px solid rgba(51,65,85,0.5);">
                    <div>
                        <span style="color:{mvrv_color}; font-weight:600; font-size:0.85em;">{mvrv_icon} MVRV</span>
                        <div style="color:#475569; font-size:0.65em; margin-top:2px;">Threshold: {mvrv_threshold}</div>
                    </div>
                    <div style="font-size:1.4em; font-weight:700; color:{mvrv_color}; font-family:'SF Mono',Menlo,monospace;">{format_number(mvrv, 2)}</div>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 14px;">
                    <div>
                        <span style="color:{sopr_color}; font-weight:600; font-size:0.85em;">{sopr_icon} LTH-SOPR</span>
                        <div style="color:#475569; font-size:0.65em; margin-top:2px;">Threshold: {lth_sopr_threshold}</div>
                    </div>
                    <div style="font-size:1.4em; font-weight:700; color:{sopr_color}; font-family:'SF Mono',Menlo,monospace;">{format_number(lth_sopr, 2)}</div>
                </div>
            </div>
            <div style="background:{alert_bg}; padding:12px; border-radius:8px; border:1px solid {alert_border}; text-align:center;">
                <div style="color:#475569; font-size:0.65em; text-transform:uppercase; letter-spacing:0.5px;">Interpretation</div>
                <div style="color:#e2e8f0; font-weight:500; font-size:0.85em; line-height:1.5; margin-top:4px;">{interpretation}</div>
            </div>
            <div style="color:#475569; font-size:0.65em; margin-top:10px; text-align:center;">Both conditions = HODLers distributing</div>
        </div>
    '''


def generate_signals_card(signals: list, title: str, icon: str) -> str:
    """Generate entry or exit signals card."""
    triggered_count = sum(1 for s in signals if s.get('triggered'))
    total = len(signals)
    sig_color = '#22c55e' if triggered_count > 0 else '#475569'

    signal_rows = ""
    for sig in signals:
        triggered = sig.get('triggered', False)
        badge_icon = "&#10003;" if triggered else "&#9675;"
        color = "#22c55e" if triggered else "#475569"
        val = sig.get('value')
        val_str = format_number(val, 4) if val is not None else "N/A"
        desc = sig.get('description', '')
        desc_html = f'<div style="color:#475569; font-size:0.7em; margin-top:1px;">{desc}</div>' if desc else ''
        signal_rows += f'''
            <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 10px; border-bottom:1px solid rgba(51,65,85,0.5);">
                <div>
                    <span style="color:{color}; font-weight:500; font-size:0.85em;">{badge_icon} {sig.get('label', '')}</span>
                    {desc_html}
                </div>
                <span style="color:#94a3b8; font-size:0.85em; font-family:'SF Mono',Menlo,monospace;">{val_str}</span>
            </div>'''

    return f'''
        <div class="card">
            <h3 style="color:#94a3b8; font-size:0.8em; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; border-bottom:1px solid #334155; padding-bottom:10px;">{title}</h3>
            <div style="text-align:center; margin-bottom:16px;">
                <div style="font-size:2em; font-weight:800; color:{sig_color}; letter-spacing:-1px;">{triggered_count}<span style="font-size:0.45em; color:#64748b; font-weight:500;">/{total} triggered</span></div>
            </div>
            <div style="background:#0f172a; border-radius:8px; border:1px solid #1e293b; overflow:hidden;">
                {signal_rows}
            </div>
        </div>
    '''


# =============================================================================
# PILLAR DEFINITIONS
# =============================================================================

PILLARS = [
    {
        "id": "valuation",
        "title": "1. Valuation",
        "icon": "🌡️",
        "metrics": "MVRV, MVRV-Z, AVIV, Price Levels",
        "tells_us": "How expensive is BTC vs historical norms? Uses cost-basis models to assess if market is over/undervalued."
    },
    {
        "id": "profitability",
        "title": "2. Profitability",
        "icon": "💰",
        "metrics": "NUPL, Supply in Profit/Loss, Unrealized P/L",
        "tells_us": "How much paper gains/losses exist? Measures unrealized profit across the holder base — high values signal greed, low signal fear."
    },
    {
        "id": "spending",
        "title": "3. Spending Behavior",
        "icon": "💸",
        "metrics": "SOPR, STH/LTH-SOPR, Realized P/L Ratio",
        "tells_us": "What are holders actually doing? Tracks realized profit/loss when coins move — reveals capitulation and profit-taking."
    },
    {
        "id": "supply",
        "title": "4. Supply Distribution",
        "icon": "📦",
        "metrics": "LTH/STH Supply, Age Bands, Wallet Cohorts",
        "tells_us": "Who holds the coins and for how long? High LTH% = strong hands dominate; rising STH% = new speculative demand."
    },
    {
        "id": "activity",
        "title": "5. Activity",
        "icon": "⚡",
        "metrics": "Liveliness, Vaultedness, Coindays Destroyed",
        "tells_us": "Are coins moving or dormant? High liveliness = active spending; high vaultedness = HODLing conviction."
    },
    {
        "id": "miners",
        "title": "6. Miner Health",
        "icon": "⛏️",
        "metrics": "Puell Multiple, Difficulty, Thermocap",
        "tells_us": "Are miners profitable or under stress? Miner capitulation often marks cycle lows; high Puell = overheated."
    },
]


def generate_pillar_header(pillar: dict, is_daily_fallback: bool = False) -> str:
    """Generate HTML for pillar section header."""
    fallback_badge = ''
    if is_daily_fallback:
        fallback_badge = ' <span style="background:#475569; color:#94a3b8; font-size:0.55em; padding:2px 6px; border-radius:3px; vertical-align:middle; margin-left:6px;">DAILY DATA</span>'
    return f'''
        <div class="pillar-header">
            <div class="pillar-title">{pillar['icon']} {pillar['title']}{fallback_badge}</div>
            <div class="pillar-tells">
                <span class="tells-label">What it tells us:</span> {pillar['tells_us']}
            </div>
            <div class="pillar-metrics">Metrics: {pillar['metrics']}</div>
        </div>
    '''


# =============================================================================
# MAIN HTML GENERATION
# =============================================================================

def generate_pillar_content(ctx: dict, live_price: float = None, hourly_metrics: list = None) -> str:
    """Generate the inner pillar content in a 2-column, 3-row grid.

    Args:
        hourly_metrics: List of metrics available at hourly resolution. When set,
            pillars whose key metrics are NOT in this list get a "DAILY DATA" badge.
    """
    # Determine which pillars fall back to daily data when in hourly mode.
    # Each pillar maps to the key metrics it needs at hourly resolution.
    PILLAR_KEY_METRICS = {
        0: {'price', 'mvrv', 'mvrv_z'},       # Valuation
        1: {'nupl'},                            # Profitability
        2: {'sopr', 'sopr_sth', 'sopr_lth'},   # Spending
        3: {'supply_lth', 'supply_sth'},        # Supply
        4: {'liveliness'},                      # Activity
        5: {'puell_multiple'},                  # Miner
    }

    def is_fallback(pillar_idx: int) -> bool:
        if not hourly_metrics:
            return False
        needed = PILLAR_KEY_METRICS.get(pillar_idx, set())
        return not needed.intersection(set(hourly_metrics))

    return f'''
        <div class="pillar-grid">
            <!-- ROW 1: Valuation + Profitability -->
            <div class="pillar-section">
                {generate_pillar_header(PILLARS[0], is_fallback(0))}
                {generate_valuation_card(ctx)}
            </div>
            <div class="pillar-section">
                {generate_pillar_header(PILLARS[1], is_fallback(1))}
                {generate_profitability_card(ctx)}
            </div>

            <!-- ROW 2: Spending + Supply -->
            <div class="pillar-section">
                {generate_pillar_header(PILLARS[2], is_fallback(2))}
                {generate_sopr_card(ctx)}
            </div>
            <div class="pillar-section">
                {generate_pillar_header(PILLARS[3], is_fallback(3))}
                {generate_supply_card(ctx)}
            </div>

            <!-- ROW 3: Activity + Miner -->
            <div class="pillar-section">
                {generate_pillar_header(PILLARS[4], is_fallback(4))}
                {generate_liveliness_card(ctx)}
            </div>
            <div class="pillar-section">
                {generate_pillar_header(PILLARS[5], is_fallback(5))}
                {generate_miner_card(ctx)}
            </div>
        </div>
    '''


def generate_dashboard_html(ctx: dict, live_price: float = None, hourly_ctx: dict = None) -> str:
    """Generate complete dashboard HTML organized by 6 pillars.

    If hourly_ctx is provided, renders both daily and hourly views
    with a toggle button.
    """
    meta = ctx.get('meta', {})
    calculated_at = meta.get('calculated_at', 'Unknown')
    data_as_of = meta.get('data_as_of', 'Unknown')

    # Parse times for display
    try:
        calc_time = datetime.fromisoformat(calculated_at).strftime("%Y-%m-%d %H:%M")
    except:
        calc_time = calculated_at

    try:
        data_time = datetime.fromisoformat(data_as_of).strftime("%Y-%m-%d")
    except:
        data_time = data_as_of

    # Check data staleness
    stale_badge = ""
    try:
        data_dt = datetime.fromisoformat(data_as_of)
        age_hours = (datetime.now() - data_dt).total_seconds() / 3600
        if age_hours > 48:
            stale_badge = f' | <span style="background:#ef4444; color:white; padding:1px 6px; border-radius:3px; font-size:0.85em;">STALE ({age_hours:.0f}h old)</span>'
        elif age_hours > 24:
            stale_badge = f' | <span style="background:#f97316; color:white; padding:1px 6px; border-radius:3px; font-size:0.85em;">STALE ({age_hours:.0f}h old)</span>'
    except:
        pass

    has_hourly = hourly_ctx is not None

    # Hourly metadata
    hourly_meta_html = ""
    hourly_data_time = ""
    hourly_calc_time = ""
    hourly_metrics_list = []
    if has_hourly:
        h_meta = hourly_ctx.get('meta', {})
        hourly_metrics_list = h_meta.get('hourly_metrics', [])
        try:
            hourly_data_time = datetime.fromisoformat(h_meta.get('data_as_of', '')).strftime("%Y-%m-%d %H:%M")
        except:
            hourly_data_time = h_meta.get('data_as_of', 'Unknown')
        try:
            hourly_calc_time = datetime.fromisoformat(h_meta.get('calculated_at', '')).strftime("%Y-%m-%d %H:%M")
        except:
            hourly_calc_time = h_meta.get('calculated_at', 'Unknown')

    # Toggle button HTML
    toggle_html = ""
    # Hourly staleness check
    hourly_stale_badge = ""
    if has_hourly:
        try:
            h_data_dt = datetime.fromisoformat(hourly_ctx.get('meta', {}).get('data_as_of', ''))
            h_age_hours = (datetime.now() - h_data_dt).total_seconds() / 3600
            if h_age_hours > 48:
                hourly_stale_badge = f' | <span style="background:#ef4444; color:white; padding:1px 6px; border-radius:3px; font-size:0.85em;">STALE ({h_age_hours:.0f}h old)</span>'
            elif h_age_hours > 24:
                hourly_stale_badge = f' | <span style="background:#f97316; color:white; padding:1px 6px; border-radius:3px; font-size:0.85em;">STALE ({h_age_hours:.0f}h old)</span>'
        except:
            pass

    if has_hourly:
        toggle_html = f'''
        <div class="resolution-toggle">
            <button id="btn-daily" class="toggle-btn active" onclick="showResolution('daily')">Daily</button>
            <button id="btn-hourly" class="toggle-btn" onclick="showResolution('hourly')">Hourly</button>
        </div>
        <div id="meta-daily" class="meta">
            Data as of: {data_time} | Calculated: {calc_time}
            {' | Live price enabled' if live_price else ''}{stale_badge}
        </div>
        <div id="meta-hourly" class="meta" style="display:none;">
            Data as of: {hourly_data_time} | Calculated: {hourly_calc_time}
            | H1 metrics: {', '.join(hourly_metrics_list) if hourly_metrics_list else 'none'}
            {' | Live price enabled' if live_price else ''}{hourly_stale_badge}
        </div>
        '''
    else:
        toggle_html = f'''
        <div class="meta">
            Data as of: {data_time} | Calculated: {calc_time}
            {' | Live price enabled' if live_price else ''}{stale_badge}
        </div>
        '''

    # Generate price hero once (shared across daily/hourly)
    price_hero = generate_price_hero(ctx, live_price)

    # Generate both content blocks
    daily_content = generate_pillar_content(ctx, live_price)
    hourly_content = generate_pillar_content(hourly_ctx, live_price, hourly_metrics=hourly_metrics_list) if has_hourly else ""

    # Toggle styles
    toggle_css = '''
        .resolution-toggle {
            display: inline-flex;
            background: #1e293b;
            border-radius: 8px;
            padding: 4px;
            margin-bottom: 12px;
            border: 1px solid #334155;
        }
        .toggle-btn {
            padding: 8px 24px;
            border: none;
            border-radius: 6px;
            font-size: 0.9em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            background: transparent;
            color: #6b7280;
        }
        .toggle-btn.active {
            background: #f59e0b;
            color: #0f172a;
        }
        .toggle-btn:hover:not(.active) {
            color: #f1f5f9;
        }
        .h1-badge {
            display: inline-block;
            background: #2563eb;
            color: white;
            font-size: 0.65em;
            padding: 1px 5px;
            border-radius: 3px;
            vertical-align: middle;
            margin-left: 4px;
            font-weight: 600;
        }
    '''

    # Toggle JS
    toggle_js = '''
    <script>
    function showResolution(res) {
        var daily = document.getElementById('content-daily');
        var hourly = document.getElementById('content-hourly');
        var btnDaily = document.getElementById('btn-daily');
        var btnHourly = document.getElementById('btn-hourly');
        var metaDaily = document.getElementById('meta-daily');
        var metaHourly = document.getElementById('meta-hourly');

        if (res === 'hourly' && hourly) {
            daily.style.display = 'none';
            hourly.style.display = 'block';
            btnDaily.classList.remove('active');
            btnHourly.classList.add('active');
            if (metaDaily) metaDaily.style.display = 'none';
            if (metaHourly) metaHourly.style.display = 'block';
        } else {
            daily.style.display = 'block';
            if (hourly) hourly.style.display = 'none';
            btnDaily.classList.add('active');
            if (btnHourly) btnHourly.classList.remove('active');
            if (metaDaily) metaDaily.style.display = 'block';
            if (metaHourly) metaHourly.style.display = 'none';
        }
    }
    </script>
    ''' if has_hourly else ''

    hourly_block = f'''
        <div id="content-hourly" style="display:none;">
            {hourly_content}
        </div>
    ''' if has_hourly else ''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitcoin Trading Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #f1f5f9;
            min-height: 100vh;
            padding: 24px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 32px;
        }}
        .header h1 {{
            font-size: 2em;
            margin-bottom: 8px;
        }}
        .header .meta {{
            color: #6b7280;
            font-size: 0.85em;
        }}
        .header .nav {{
            margin-top: 12px;
        }}
        .header .nav a {{
            display: inline-block;
            padding: 8px 16px;
            margin: 0 8px;
            background: rgba(245, 158, 11, 0.1);
            color: #f59e0b;
            text-decoration: none;
            border-radius: 6px;
            border: 1px solid rgba(245, 158, 11, 0.3);
            font-size: 0.85em;
            transition: all 0.3s ease;
        }}
        .header .nav a:hover {{
            background: rgba(245, 158, 11, 0.2);
            transform: translateY(-2px);
        }}
        {toggle_css}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}
        .pillar-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }}
        @media (max-width: 1024px) {{
            .pillar-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .pillar-section {{
            display: flex;
            flex-direction: column;
            margin-bottom: 0;
        }}
        .pillar-section .card:last-child {{
            flex: 1;
        }}
        .pillar-header {{
            margin-bottom: 16px;
            padding: 16px 20px;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-left: 4px solid #f59e0b;
            border-radius: 8px;
        }}
        .pillar-title {{
            font-size: 1.4em;
            font-weight: bold;
            color: #f59e0b;
            margin-bottom: 8px;
        }}
        .pillar-tells {{
            color: #e2e8f0;
            font-size: 0.95em;
            margin-bottom: 6px;
            line-height: 1.4;
        }}
        .tells-label {{
            color: #f59e0b;
            font-weight: 600;
        }}
        .pillar-metrics {{
            color: #6b7280;
            font-size: 0.8em;
            font-style: italic;
        }}
        .pillar-section .card {{
            margin-bottom: 12px;
        }}
        .pillar-section .card:last-child {{
            margin-bottom: 0;
        }}
        .card {{
            background: #1e293b;
            border-radius: 10px;
            padding: 22px;
            border: 1px solid #334155;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }}
        .card h3 {{
            margin-bottom: 16px;
            color: #e2e8f0;
            font-size: 1.1em;
        }}
        .signals-section {{
            margin-top: 48px;
            padding-top: 32px;
            border-top: 2px solid #334155;
        }}
        .signals-header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .signals-header h2 {{
            font-size: 1.6em;
            color: #f59e0b;
            margin-bottom: 8px;
        }}
        .signals-header p {{
            color: #9ca3af;
            font-size: 0.9em;
        }}
        .footer {{
            text-align: center;
            margin-top: 32px;
            color: #6b7280;
            font-size: 0.8em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>₿ Bitcoin Trading Dashboard</h1>
        {toggle_html}
        <div class="nav">
            <a href="dashboard_signals.html">🎯 Trading Signals</a>
            <a href="dashboard_backtest.html">📈 Backtest Results</a>
            <a href="dashboard_quality.html">📊 Data Quality</a>
        </div>
    </div>

    <div class="container">
        {price_hero}
        <div id="content-daily">
            {daily_content}
        </div>
        {hourly_block}
    </div>

    <div class="footer">
        <p>James Check Framework — 6 Pillars of On-Chain Analysis | Run <code>python scripts/calculate.py</code> to update</p>
    </div>
    {toggle_js}
</body>
</html>
'''
    return html


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 50)
    print("Bitcoin Trading Dashboard")
    print("=" * 50)
    
    # Check for signals data
    if not SIGNALS_DIR.exists():
        print(f"❌ Signals directory not found: {SIGNALS_DIR}")
        print("Run 'python calculate.py' first to generate signals.")
        return
    
    # Load pre-computed context
    print("\nLoading signals...")
    try:
        ctx = load_dashboard_context("daily")
        print("  ✓ Daily dashboard context loaded")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return

    # Try loading hourly context (optional)
    hourly_ctx = None
    try:
        hourly_ctx = load_dashboard_context("hourly")
        h_metrics = hourly_ctx.get('meta', {}).get('hourly_metrics', [])
        print(f"  ✓ Hourly dashboard context loaded ({len(h_metrics)} h1 metrics)")
    except FileNotFoundError:
        print("  - No hourly context (run: python scripts/calculate.py --resolution hourly)")
    
    # Optionally fetch live price
    live_price = None
    if '--no-live' not in sys.argv:
        print("\nFetching live price...")
        live_price, _ = get_live_price()
        if live_price:
            print(f"  ✓ Live: ${live_price:,.0f}")
        else:
            print("  ✗ Using cached price")
    
    # Generate HTML
    print("\nGenerating dashboard...")
    html = generate_dashboard_html(ctx, live_price, hourly_ctx=hourly_ctx)
    
    # Write to file
    OUTPUT_PATH.write_text(html)
    print(f"  ✓ Saved to {OUTPUT_PATH}")
    
    # Open in browser
    if '--no-open' not in sys.argv:
        webbrowser.open(f'file://{OUTPUT_PATH.absolute()}')
        print("  ✓ Opened in browser")
    
    # Watch mode
    if '--watch' in sys.argv:
        print("\n👀 Watch mode - refreshing every 60s (Ctrl+C to stop)")
        while True:
            time.sleep(60)
            try:
                ctx = load_dashboard_context("daily")
                try:
                    hourly_ctx = load_dashboard_context("hourly")
                except FileNotFoundError:
                    hourly_ctx = None
                live_price, _ = get_live_price() if '--no-live' not in sys.argv else (None, None)
                html = generate_dashboard_html(ctx, live_price, hourly_ctx=hourly_ctx)
                OUTPUT_PATH.write_text(html)
                print(f"  ✓ Refreshed at {datetime.now().strftime('%H:%M:%S')}")
            except KeyboardInterrupt:
                print("\n\nStopped.")
                break
            except Exception as e:
                print(f"  ✗ Error: {e}")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
