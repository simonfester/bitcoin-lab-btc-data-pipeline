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
OUTPUT_PATH = PROJECT_ROOT / "dashboard.html"

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

def generate_price_card(ctx: dict, live_price: float = None) -> str:
    """Generate price levels card."""
    pc = ctx['price_context']
    price = live_price or pc.get('price')
    levels = pc.get('levels', {})
    zone = pc.get('zone', 'UNKNOWN')
    zone_color = pc.get('zone_color', '#6b7280')
    
    # Price level rows
    level_rows = ""
    level_order = [
        ('vaulted_price', 'Vaulted Price', '#a855f7'),
        ('sth_realized_price', 'STH Realized', '#fbbf24'),
        ('true_market_mean', 'True Market Mean', '#22c55e'),
        ('realized_price', 'Realized Price', '#ef4444'),
    ]
    
    for key, label, color in level_order:
        val = levels.get(key)
        if val:
            indicator = "◄" if price and abs(price - val) / val < 0.05 else ""
            level_rows += metric_row(label, f"{format_price(val)} {indicator}", color)
    
    return f'''
        <div class="card">
            <h3>📊 Price Levels</h3>
            <div style="text-align:center; margin:16px 0;">
                <div style="font-size:2.5em; font-weight:bold;">{format_price(price)}</div>
                <div style="margin-top:8px;">
                    {zone_badge(zone, zone_color)}
                </div>
            </div>
            <div style="margin-top:16px;">
                {level_rows}
            </div>
        </div>
    '''


def generate_valuation_card(ctx: dict) -> str:
    """Generate valuation thermometer card."""
    val = ctx['valuation']
    mvrv = val.get('mvrv')
    mvrv_z = val.get('mvrv_z')
    aviv = val.get('aviv')
    zone = val.get('zone', 'UNKNOWN')
    zone_color = val.get('zone_color', '#6b7280')
    
    # MVRV-Z thermometer position (map -1 to 4 range to 0-100%)
    thermo_pos = 0
    if mvrv_z is not None:
        thermo_pos = min(100, max(0, (mvrv_z + 1) / 5 * 100))
    
    return f'''
        <div class="card" style="grid-column: span 2;">
            <h3>🌡️ Valuation</h3>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:24px;">
                <div>
                    <div style="text-align:center; margin-bottom:16px;">
                        <div style="font-size:2em; font-weight:bold;">{format_number(mvrv_z) if mvrv_z else 'N/A'}</div>
                        <div style="color:#9ca3af;">MVRV-Z Score</div>
                    </div>
                    <div style="position:relative; height:20px; background:linear-gradient(to right, #22c55e 0%, #3b82f6 30%, #f97316 60%, #ef4444 100%); border-radius:10px;">
                        <div style="position:absolute; left:{thermo_pos}%; top:-2px; width:4px; height:24px; background:white; border-radius:2px; transform:translateX(-50%);"></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:0.75em; color:#9ca3af; margin-top:4px;">
                        <span>Deep Value</span>
                        <span>Fair</span>
                        <span>Expensive</span>
                        <span>Euphoria</span>
                    </div>
                </div>
                <div>
                    {metric_row('MVRV', format_number(mvrv))}
                    {metric_row('AVIV', format_number(aviv))}
                    {metric_row('Zone', zone_badge(zone, zone_color))}
                </div>
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
    
    return f'''
        <div class="card">
            <h3>💸 Spending Behavior</h3>
            
            <!-- SOPR Bar -->
            <div style="margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="color:#9ca3af;">SOPR</span>
                    <span style="font-weight:bold;">{format_number(sopr_val, 4)}</span>
                </div>
                <div style="position:relative; height:12px; background:#1f2937; border-radius:6px;">
                    <div style="position:absolute; left:50%; top:0; width:2px; height:100%; background:#6b7280;"></div>
                    <div style="position:absolute; left:{sopr_pos}%; top:50%; width:12px; height:12px; background:{'#22c55e' if sopr_val and sopr_val < 1 else '#ef4444'}; border-radius:50%; transform:translate(-50%, -50%);"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.7em; color:#6b7280;">
                    <span>Loss (0.9)</span>
                    <span>Break-even (1.0)</span>
                    <span>Profit (1.1)</span>
                </div>
            </div>
            
            <!-- STH vs LTH -->
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:16px;">
                <div style="text-align:center; padding:8px; background:#1f2937; border-radius:8px;">
                    <div style="font-size:1.5em; font-weight:bold;">{format_number(sth_sopr, 3)}</div>
                    <div style="color:#9ca3af; font-size:0.8em;">STH-SOPR</div>
                    <div style="color:{sth_color}; font-weight:500; margin-top:4px;">{sth_state}</div>
                </div>
                <div style="text-align:center; padding:8px; background:#1f2937; border-radius:8px;">
                    <div style="font-size:1.5em; font-weight:bold;">{format_number(lth_sopr, 3)}</div>
                    <div style="color:#9ca3af; font-size:0.8em;">LTH-SOPR</div>
                    <div style="color:{lth_color}; font-weight:500; margin-top:4px;">{lth_state}</div>
                </div>
            </div>
            
            <!-- Realized P/L Ratio -->
            <div style="margin-top:16px;">
                {metric_row('Realized P/L Ratio', format_number(pl_ratio, 2), '#fbbf24' if pl_ratio and pl_ratio < 1 else '#22c55e')}
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
    
    # NUPL position (map -0.5 to 1.0 range to 0-100%)
    nupl_pos = 0
    if nupl is not None:
        nupl_pos = min(100, max(0, (nupl + 0.5) / 1.5 * 100))
    
    return f'''
        <div class="card">
            <h3>💰 Profitability</h3>
            
            <!-- NUPL Bar -->
            <div style="margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="color:#9ca3af;">NUPL</span>
                    <span style="font-weight:bold;">{format_number(nupl, 3)}</span>
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
                {zone_badge(nupl_zone, nupl_color)}
            </div>
            
            <!-- Supply in Profit/Loss -->
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
            <h3>📦 Supply Dynamics</h3>
            
            <!-- LTH vs STH Bar -->
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
                {zone_badge(state, state_color)}
            </div>
            
            {metric_row('LTH Supply', format_number(supply.get('supply_lth'), 0))}
            {metric_row('STH Supply', format_number(supply.get('supply_sth'), 0))}
            {metric_row('LTH/STH Ratio', format_number(supply.get('lth_sth_ratio'), 2))}
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
            <h3>⚡ Liveliness</h3>
            
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
                {zone_badge(state, state_color)}
            </div>
            
            <p style="color:#9ca3af; font-size:0.8em; margin-top:12px;">
                High liveliness = active spending. High vaultedness = HODLing behavior.
            </p>
        </div>
    '''


def generate_miner_card(ctx: dict) -> str:
    """Generate miner health card."""
    miner = ctx['miner']
    
    puell = miner.get('puell_multiple')
    puell_zone = miner.get('puell_zone', 'UNKNOWN')
    puell_color = miner.get('puell_color', '#6b7280')
    
    # Puell position (map 0-8 range to 0-100%)
    puell_pos = 0
    if puell is not None:
        puell_pos = min(100, max(0, puell / 8 * 100))
    
    return f'''
        <div class="card">
            <h3>⛏️ Miner Health</h3>
            
            <div style="text-align:center; margin-bottom:16px;">
                <div style="font-size:2em; font-weight:bold;">{format_number(puell, 2)}</div>
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


def generate_pillar_header(pillar: dict) -> str:
    """Generate HTML for pillar section header."""
    return f'''
        <div class="pillar-header">
            <div class="pillar-title">{pillar['icon']} {pillar['title']}</div>
            <div class="pillar-tells">
                <span class="tells-label">What it tells us:</span> {pillar['tells_us']}
            </div>
            <div class="pillar-metrics">Metrics: {pillar['metrics']}</div>
        </div>
    '''


# =============================================================================
# MAIN HTML GENERATION
# =============================================================================

def generate_dashboard_html(ctx: dict, live_price: float = None) -> str:
    """Generate complete dashboard HTML organized by 6 pillars."""
    
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
        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}
        .pillar-section {{
            margin-bottom: 40px;
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
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #334155;
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
        <div class="meta">
            Data as of: {data_time} | Calculated: {calc_time}
            {' | Live price enabled' if live_price else ''}
        </div>
        <div class="nav">
            <a href="dashboard_quality.html">📊 Data Quality</a>
        </div>
    </div>
    
    <div class="container">
        <!-- PILLAR 1: VALUATION -->
        <div class="pillar-section">
            {generate_pillar_header(PILLARS[0])}
            <div class="grid">
                {generate_price_card(ctx, live_price)}
                {generate_valuation_card(ctx)}
            </div>
        </div>
        
        <!-- PILLAR 2: PROFITABILITY -->
        <div class="pillar-section">
            {generate_pillar_header(PILLARS[1])}
            <div class="grid">
                {generate_profitability_card(ctx)}
            </div>
        </div>
        
        <!-- PILLAR 3: SPENDING BEHAVIOR -->
        <div class="pillar-section">
            {generate_pillar_header(PILLARS[2])}
            <div class="grid">
                {generate_sopr_card(ctx)}
            </div>
        </div>
        
        <!-- PILLAR 4: SUPPLY DISTRIBUTION -->
        <div class="pillar-section">
            {generate_pillar_header(PILLARS[3])}
            <div class="grid">
                {generate_supply_card(ctx)}
            </div>
        </div>
        
        <!-- PILLAR 5: ACTIVITY -->
        <div class="pillar-section">
            {generate_pillar_header(PILLARS[4])}
            <div class="grid">
                {generate_liveliness_card(ctx)}
            </div>
        </div>
        
        <!-- PILLAR 6: MINER HEALTH -->
        <div class="pillar-section">
            {generate_pillar_header(PILLARS[5])}
            <div class="grid">
                {generate_miner_card(ctx)}
            </div>
        </div>
        
        <!-- SIGNALS SYNTHESIS -->
        <div class="signals-section">
            <div class="signals-header">
                <h2>🎯 Signal Synthesis</h2>
                <p>Combining pillars into actionable signals — the output of the Checkonchain Framework</p>
            </div>

            <!-- Entry Signals Row -->
            <div style="margin-bottom:24px;">
                <h3 style="color:#22c55e; margin-bottom:12px;">🟢 Entry Signals (When to Buy)</h3>
                <div class="grid">
                    {generate_checkmate_card(ctx)}
                    {generate_btd_card(ctx)}
                    {generate_signals_card(ctx.get('entry_signals', []), 'Additional Entry Signals', '🟢')}
                </div>
            </div>

            <!-- Exit Signals Row -->
            <div style="margin-bottom:24px;">
                <h3 style="color:#ef4444; margin-bottom:12px;">🔴 Exit Signals (When to Sell/Reduce)</h3>
                <div class="grid">
                    {generate_8_metric_exit_card(ctx)}
                    {generate_sth_zones_card(ctx)}
                    {generate_lth_distribution_card(ctx)}
                    {generate_signals_card(ctx.get('exit_signals', []), 'Additional Exit Signals', '🔴')}
                </div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        <p>James Check Framework Implementation | Run calculate.py to update signals</p>
    </div>
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
        ctx = load_dashboard_context()
        print("  ✓ Dashboard context loaded")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return
    
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
    html = generate_dashboard_html(ctx, live_price)
    
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
                ctx = load_dashboard_context()
                live_price, _ = get_live_price() if '--no-live' not in sys.argv else (None, None)
                html = generate_dashboard_html(ctx, live_price)
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
