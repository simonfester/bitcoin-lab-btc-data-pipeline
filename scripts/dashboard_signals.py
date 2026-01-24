#!/usr/bin/env python3
"""
Bitcoin Trading Signals Dashboard - Actionable Trading Signals
==============================================================
Displays Buy/Sell signals derived from the 6 pillars of on-chain analysis.

Usage:
    python dashboard_signals.py              # Generate signals dashboard
    python dashboard_signals.py --watch      # Auto-refresh every 60 seconds
    python dashboard_signals.py --no-open    # Generate without opening browser

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
OUTPUT_PATH = DASHBOARDS_DIR / "dashboard_signals.html"

# Ensure dashboards directory exists
DASHBOARDS_DIR.mkdir(exist_ok=True)

# Live price API (only external call dashboard makes)
COINBASE_API = "https://api.coinbase.com/v2/prices/BTC-USD/spot"

# =============================================================================
# DATA LOADING
# =============================================================================

def load_dashboard_context() -> dict:
    """Load pre-computed dashboard context from JSON."""
    context_path = SIGNALS_DIR / "dashboard_context.json"
    if not context_path.exists():
        raise FileNotFoundError(
            f"Dashboard context not found: {context_path}\n"
            "Run 'python calculate.py' first to generate signals."
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
    # For very small numbers (e.g., funding rates), use more precision
    if abs(val) < 0.001 and val != 0:
        return f"{prefix}{val:.6f}{suffix}"
    return f"{prefix}{val:.{decimals}f}{suffix}"


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


def zone_badge(text: str, color: str) -> str:
    """Generate a colored zone badge."""
    return f'<span style="display:inline-block; padding:6px 12px; background:{color}; color:white; border-radius:4px; font-weight:bold; font-size:0.85em;">{text}</span>'


# =============================================================================
# SIGNAL CARD GENERATORS
# =============================================================================

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
        icon = "✓" if cond.get('met') else "○"
        color = "#22c55e" if cond.get('met') else "#6b7280"
        val = cond.get('value')
        val_str = format_number(val, 4) if val is not None else "N/A"
        condition_rows += f'''
            <div style="display:flex; justify-content:space-between; padding:4px 0;">
                <span style="color:{color};">{icon} {cond.get('name', '')}</span>
                <span style="color:#9ca3af;">{val_str}</span>
            </div>
        '''

    return f'''
        <div class="card">
            <h3>🎯 Checkmate Signal</h3>

            <div style="text-align:center; margin:16px 0;">
                <div style="font-size:2.5em; font-weight:bold;">{score}/{total}</div>
                <div style="margin-top:8px;">
                    {zone_badge(signal, signal_color)}
                </div>
            </div>

            <div style="margin-top:16px;">
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
        icon = "✓" if triggered else "○"
        color = "#22c55e" if triggered else "#6b7280"
        val = cond.get('value')
        val_str = format_number(val, 4) if val is not None else "N/A"
        condition_rows += f'''
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #374151;">
                <span style="color:{color}; font-weight:500;">{icon} {cond.get('label', '')}</span>
                <span style="color:#9ca3af;">{val_str}</span>
            </div>
        '''

    return f'''
        <div class="card">
            <h3>🛒 Buy The Dip</h3>

            <div style="text-align:center; margin:16px 0;">
                <div style="font-size:3em; font-weight:bold; color:{signal_color};">{met_count}/{total}</div>
                <div style="margin-top:8px;">
                    {zone_badge(signal, signal_color)}
                </div>
            </div>

            <div style="margin-top:16px;">
                {condition_rows}
            </div>

            <p style="color:#6b7280; font-size:0.75em; margin-top:12px; text-align:center;">
                James Check: 4+ conditions = strong buy signal
            </p>
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

    condition_rows = ""
    for cond in conditions:
        triggered = cond.get('triggered', False)
        icon = "✓" if triggered else "○"
        color = "#ef4444" if triggered else "#6b7280"
        z_score = cond.get('z_score')
        z_str = f"{z_score:+.2f}σ" if z_score is not None else "N/A"
        condition_rows += f'''
            <div style="display:flex; justify-content:space-between; padding:4px 0; font-size:0.85em;">
                <span style="color:{color};">{icon} {cond.get('label', '')[:20]}</span>
                <span style="color:#9ca3af;">{z_str}</span>
            </div>
        '''

    # Color intensity based on signal
    if met_count >= 6:
        title_color = "#ef4444"
    elif met_count >= 4:
        title_color = "#f97316"
    elif met_count >= 2:
        title_color = "#fbbf24"
    else:
        title_color = "#22c55e"

    return f'''
        <div class="card">
            <h3>🚨 8-Metric Exit Detector</h3>

            <div style="text-align:center; margin:16px 0;">
                <div style="font-size:3em; font-weight:bold; color:{title_color};">{met_count}/{total}</div>
                <div style="margin-top:8px;">
                    {zone_badge(signal, signal_color)}
                </div>
            </div>

            <div style="background:#1e293b; padding:8px; border-radius:6px; margin:12px 0; text-align:center;">
                <div style="color:#9ca3af; font-size:0.75em;">Recommendation</div>
                <div style="color:#f1f5f9; font-weight:500;">{recommendation}</div>
            </div>

            <div style="margin-top:12px; max-height:240px; overflow-y:auto;">
                {condition_rows}
            </div>

            <p style="color:#6b7280; font-size:0.7em; margin-top:12px; text-align:center;">
                4/8 = Caution | 6/8 = High Risk (James Check Masterclass #19)
            </p>
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

    # Generate price level rows
    price_rows = ""
    if price_levels:
        for level, price in price_levels.items():
            level_name = level.replace('_', ' ').title()
            if level == 'warming':
                level_color = "#fbbf24"
            elif level == 'local_top':
                level_color = "#f97316"
            else:  # overheated
                level_color = "#ef4444"

            price_rows += f'''
                <div style="display:flex; justify-content:space-between; padding:6px; background:#1e293b; border-radius:4px; margin:4px 0;">
                    <span style="color:{level_color};">{level_name}</span>
                    <span style="color:#f1f5f9; font-weight:500;">{format_price(price)}</span>
                </div>
            '''

    z_str = f"{z_score:+.2f}σ" if z_score is not None else "N/A"

    return f'''
        <div class="card">
            <h3>📊 STH-MVRV Zones</h3>

            <div style="text-align:center; margin:16px 0;">
                <div style="font-size:2em; font-weight:bold;">{format_number(current_value, 4)}</div>
                <div style="color:#9ca3af;">STH-MVRV (Z: {z_str})</div>
                <div style="margin-top:8px;">
                    {zone_badge(zone, zone_color)}
                </div>
            </div>

            <div style="background:#1e293b; padding:10px; border-radius:6px; margin:12px 0;">
                <div style="color:#9ca3af; font-size:0.8em; margin-bottom:4px;">Current Price</div>
                <div style="color:#f1f5f9; font-size:1.5em; font-weight:bold;">{format_price(current_price)}</div>
            </div>

            <div style="margin-top:12px;">
                <div style="color:#9ca3af; font-size:0.85em; margin-bottom:8px;">Local Top Price Levels</div>
                {price_rows}
            </div>

            <p style="color:#6b7280; font-size:0.75em; margin-top:12px; line-height:1.4;">
                {interpretation}
            </p>
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

    # Icons and colors
    mvrv_icon = "✓" if mvrv_triggered else "○"
    mvrv_color = "#ef4444" if mvrv_triggered else "#6b7280"

    sopr_icon = "✓" if lth_sopr_triggered else "○"
    sopr_color = "#ef4444" if lth_sopr_triggered else "#6b7280"

    return f'''
        <div class="card">
            <h3>💎 LTH Distribution</h3>

            <div style="text-align:center; margin:16px 0;">
                <div style="margin-top:8px;">
                    {zone_badge(signal, signal_color)}
                </div>
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

            <div style="background:{'#7f1d1d' if both_triggered else '#1e293b'}; padding:10px; border-radius:6px; margin:12px 0; text-align:center;">
                <div style="color:#9ca3af; font-size:0.75em;">Interpretation</div>
                <div style="color:#f1f5f9; font-weight:500; font-size:0.9em; line-height:1.4; margin-top:4px;">
                    {interpretation}
                </div>
            </div>

            <p style="color:#6b7280; font-size:0.7em; margin-top:12px; text-align:center;">
                Both conditions = HODLers distributing (James Check)
            </p>
        </div>
    '''


def generate_signals_card(signals: list, title: str, icon: str) -> str:
    """Generate entry or exit signals card."""
    triggered_count = sum(1 for s in signals if s.get('triggered'))
    total = len(signals)

    signal_rows = ""
    for sig in signals:
        triggered = sig.get('triggered', False)
        badge_icon = "✓" if triggered else "○"
        color = "#22c55e" if triggered else "#6b7280"
        val = sig.get('value')
        val_str = format_number(val, 4) if val is not None else "N/A"
        signal_rows += f'''
            <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid #374151;">
                <div>
                    <span style="color:{color}; font-weight:bold;">{badge_icon} {sig.get('label', '')}</span>
                    <div style="color:#6b7280; font-size:0.75em;">{sig.get('description', '')}</div>
                </div>
                <span style="color:#9ca3af;">{val_str}</span>
            </div>
        '''

    return f'''
        <div class="card">
            <h3>{icon} {title}</h3>
            <div style="text-align:center; margin:12px 0;">
                <span style="font-size:1.5em; font-weight:bold;">{triggered_count}/{total}</span>
                <span style="color:#9ca3af;"> triggered</span>
            </div>
            <div style="margin-top:12px;">
                {signal_rows}
            </div>
        </div>
    '''


# =============================================================================
# DASHBOARD HTML GENERATION
# =============================================================================

def generate_signals_dashboard_html(ctx: dict, live_price: float = None) -> str:
    """Generate complete signals dashboard HTML."""

    # Get timestamps
    data_time = ctx.get('data_timestamp', 'Unknown')
    calc_time = ctx.get('calculation_timestamp', 'Unknown')

    # Get current price
    current_price = ctx.get('price', {}).get('current')
    if live_price:
        current_price = live_price

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitcoin Trading Signals</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #f1f5f9;
            min-height: 100vh;
            padding: 24px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 32px;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 8px;
            color: white;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .header .meta {{
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.9em;
            margin-bottom: 12px;
        }}
        .header .price {{
            font-size: 2em;
            font-weight: bold;
            color: #fbbf24;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .header .nav {{
            margin-top: 16px;
        }}
        .header .nav a {{
            display: inline-block;
            padding: 10px 20px;
            margin: 0 8px;
            background: rgba(255, 255, 255, 0.15);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            font-size: 0.9em;
            transition: all 0.3s ease;
        }}
        .header .nav a:hover {{
            background: rgba(255, 255, 255, 0.25);
            transform: translateY(-2px);
        }}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section-title {{
            font-size: 1.8em;
            margin-bottom: 16px;
            padding: 16px 24px;
            background: rgba(255, 255, 255, 0.1);
            border-left: 4px solid;
            border-radius: 8px;
            backdrop-filter: blur(10px);
        }}
        .section-title.buy {{
            border-color: #22c55e;
            color: #22c55e;
        }}
        .section-title.sell {{
            border-color: #ef4444;
            color: #ef4444;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 24px;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.3);
        }}
        .card h3 {{
            color: #fbbf24;
            margin-bottom: 16px;
            font-size: 1.2em;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.85em;
            border-top: 1px solid rgba(255, 255, 255, 0.2);
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Bitcoin Trading Signals</h1>
        <div class="meta">
            Data as of: {data_time} | Calculated: {calc_time}
            {' | Live price enabled' if live_price else ''}
        </div>
        <div class="price">{format_price(current_price)}</div>
        <div class="nav">
            <a href="dashboard.html">← Back to Dashboard</a>
            <a href="dashboard_quality.html">📊 Data Quality</a>
        </div>
    </div>

    <div class="container">
        <!-- BUY SIGNALS SECTION -->
        <div class="section">
            <div class="section-title buy">🟢 Entry Signals — When to Buy</div>
            <div class="grid">
                {generate_checkmate_card(ctx)}
                {generate_btd_card(ctx)}
                {generate_signals_card(ctx.get('entry_signals', []), 'Additional Entry Signals', '🟢')}
            </div>
        </div>

        <!-- SELL SIGNALS SECTION -->
        <div class="section">
            <div class="section-title sell">🔴 Exit Signals — When to Sell/Reduce</div>
            <div class="grid">
                {generate_8_metric_exit_card(ctx)}
                {generate_sth_zones_card(ctx)}
                {generate_lth_distribution_card(ctx)}
                {generate_signals_card(ctx.get('exit_signals', []), 'Additional Exit Signals', '🔴')}
            </div>
        </div>
    </div>

    <div class="footer">
        <p>James Check Framework Implementation | Combining the 6 Pillars into Actionable Signals</p>
        <p>Run <code>python scripts/calculate.py</code> to update signals</p>
    </div>
</body>
</html>
'''

    return html


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Generate signals dashboard."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate trading signals dashboard')
    parser.add_argument('--watch', action='store_true',
                       help='Auto-refresh every 60 seconds')
    parser.add_argument('--no-open', action='store_true',
                       help='Generate without opening browser')
    parser.add_argument('--live-price', action='store_true',
                       help='Fetch live price from Coinbase')

    args = parser.parse_args()

    while True:
        try:
            print("Loading dashboard context...")
            ctx = load_dashboard_context()

            # Fetch live price if requested
            live_price = None
            if args.live_price:
                print("Fetching live price...")
                live_price, _ = get_live_price()
                if live_price:
                    print(f"  Live price: ${live_price:,.0f}")

            print("Generating signals dashboard...")
            html = generate_signals_dashboard_html(ctx, live_price)

            OUTPUT_PATH.write_text(html)
            print(f"✓ Dashboard saved to: {OUTPUT_PATH}")

            # Open in browser on first run
            if not args.no_open and not args.watch:
                print("Opening in browser...")
                webbrowser.open(OUTPUT_PATH.as_uri())

            if not args.watch:
                break

            print("Refreshing in 60 seconds... (Ctrl+C to stop)")
            time.sleep(60)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            if not args.watch:
                sys.exit(1)
            time.sleep(60)


if __name__ == '__main__':
    main()
