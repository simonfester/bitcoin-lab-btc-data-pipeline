#!/usr/bin/env python3
"""
Bitcoin Trading Framework - Live Dashboard Generator
=====================================================
Usage:
    python dashboard.py              # Generate dashboard
    python dashboard.py --watch      # Auto-refresh every 60 seconds
    python dashboard.py --no-open    # Generate without opening browser
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import webbrowser
import sys
import time

# =============================================================================
# CONFIGURATION
# =============================================================================

DATA_DIR = Path(__file__).parent.parent / "data" / "daily"
if not DATA_DIR.exists():
    DATA_DIR = Path.home() / "Documents" / "bitcoin-lab-btc-data-pipeline" / "data" / "daily"

OUTPUT_PATH = Path(__file__).parent / "dashboard.html"

# =============================================================================
# ⚡ SIGNAL REGISTRY - ADD NEW SIGNALS HERE ⚡
# =============================================================================

ENTRY_SIGNALS = [
    # STRAT-002/004 Entry Signals (Validated)
    {"id": "sopr", "metric": "sopr", "condition": "lt", "threshold": 1.0,
     "label": "SOPR < 1", "description": "Market selling at loss", "category": "STRAT-002/004"},
    {"id": "sth_sopr", "metric": "sopr_sth", "condition": "lt", "threshold": 1.0,
     "label": "STH-SOPR < 1", "description": "Short-term holders capitulating", "category": "STRAT-002/004"},
    {"id": "realized_loss_z", "metric": "realized_loss", "condition": "gt", "threshold": 0.5,
     "label": "RL Z > 0.5", "description": "Elevated loss-taking", "use_zscore": True, "zscore_lookback": 365, "category": "STRAT-002/004"},
    # ADD NEW ENTRY SIGNALS HERE
]

EXIT_SIGNALS = [
    # Distribution Exit Signals
    {"id": "lth_sopr", "metric": "sopr_lth", "condition": "gt", "threshold": 1.5,
     "label": "LTH-SOPR > 1.5", "description": "Long-term holders taking profits", "category": "Distribution"},
    {"id": "mvrv_z_high", "metric": "mvrv_z", "condition": "gt", "threshold": 2.5,
     "label": "MVRV-Z > 2.5", "description": "Market expensive historically", "category": "Valuation"},
    # ADD NEW EXIT SIGNALS HERE
]

SIGNAL_GROUPS = {
    "strat_002_004_entry": {"name": "STRAT-002/004 Entry", "signals": ["sopr", "sth_sopr", "realized_loss_z"], "type": "entry"},
    "distribution_exit": {"name": "Distribution Exit", "signals": ["lth_sopr", "mvrv_z_high"], "type": "exit"},
}

# =============================================================================
# DATA LOADING
# =============================================================================

def load_metric(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame(columns=['time', 'value'])
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        if hasattr(df['time'].dt, 'tz') and df['time'].dt.tz is not None:
            df['time'] = df['time'].dt.tz_localize(None)
    return df.sort_values('time')

def get_latest(df: pd.DataFrame) -> tuple:
    if df.empty or 'value' not in df.columns:
        return None, None
    row = df.iloc[-1]
    return row['value'], row.get('time', None)

def calculate_z_score(df: pd.DataFrame, lookback: int = 365) -> float:
    if df.empty or len(df) < 10:
        return 0
    lookback = min(lookback, len(df))
    recent = df.tail(lookback)['value']
    latest = df.iloc[-1]['value']
    mean, std = recent.mean(), recent.std()
    return (latest - mean) / std if std and not pd.isna(std) else 0

# =============================================================================
# SIGNAL CALCULATION
# =============================================================================

def evaluate_signal(signal_def: dict, data: dict) -> dict:
    metric_name = signal_def["metric"]
    if metric_name not in data or data[metric_name].empty:
        return {"id": signal_def["id"], "label": signal_def["label"], "value": None,
                "threshold": signal_def["threshold"], "triggered": False}
    
    df = data[metric_name]
    value = calculate_z_score(df, signal_def.get("zscore_lookback", 365)) if signal_def.get("use_zscore") else get_latest(df)[0]
    
    if value is None:
        triggered = False
    elif signal_def["condition"] == "lt":
        triggered = value < signal_def["threshold"]
    elif signal_def["condition"] == "gt":
        triggered = value > signal_def["threshold"]
    else:
        triggered = False
    
    return {"id": signal_def["id"], "label": signal_def["label"], "value": value,
            "threshold": signal_def["threshold"], "triggered": triggered,
            "description": signal_def.get("description", "")}

def calculate_all_signals(data: dict) -> dict:
    results = {"entry": {}, "exit": {}, "groups": {}}
    for sig in ENTRY_SIGNALS:
        results["entry"][sig["id"]] = evaluate_signal(sig, data)
    for sig in EXIT_SIGNALS:
        results["exit"][sig["id"]] = evaluate_signal(sig, data)
    for gid, gdef in SIGNAL_GROUPS.items():
        sigs = [results[gdef["type"]].get(sid) for sid in gdef["signals"]]
        results["groups"][gid] = {"triggered": all(s and s["triggered"] for s in sigs if s)}
    return results

def calculate_context(data: dict) -> dict:
    ctx = {}
    price_val, price_time = get_latest(data.get('price', pd.DataFrame()))
    ctx['price'] = {'value': price_val, 'time': price_time}
    
    mvrv_z_val, _ = get_latest(data.get('mvrv_z', pd.DataFrame()))
    if mvrv_z_val is not None:
        if mvrv_z_val < 0: zone, zc = 'DEEP VALUE', '#22c55e'
        elif mvrv_z_val < 1.5: zone, zc = 'FAIR VALUE', '#3b82f6'
        elif mvrv_z_val < 2.5: zone, zc = 'EXPENSIVE', '#f97316'
        else: zone, zc = 'EUPHORIA', '#ef4444'
    else: zone, zc = 'UNKNOWN', '#6b7280'
    ctx['mvrv_z'] = {'value': mvrv_z_val, 'zone': zone, 'zone_color': zc}
    
    for key in ['mvrv', 'aviv', 'nupl']:
        val, _ = get_latest(data.get(key, pd.DataFrame()))
        ctx[key] = {'value': val}
    
    levels = {}
    for name, metric in [('realized_price', 'realized_price'), ('true_market_mean', 'true_market_mean_price'),
                         ('sth_realized_price', 'realized_price_sth'), ('vaulted_price', 'vaulted_price')]:
        val, _ = get_latest(data.get(metric, pd.DataFrame()))
        levels[name] = val
    ctx['price_levels'] = levels
    
    if price_val and all(levels.get(k) for k in levels):
        if price_val < levels['realized_price']: pz, pc, pm = 'EXTREME BEAR', '#ef4444', 2.0
        elif price_val < levels['true_market_mean']: pz, pc, pm = 'UNDERVALUED', '#f97316', 1.5
        elif price_val < levels['sth_realized_price']: pz, pc, pm = 'FAIR VALUE', '#22c55e', 1.0
        elif price_val < levels['vaulted_price']: pz, pc, pm = 'OVERVALUED', '#fbbf24', 0.5
        else: pz, pc, pm = 'EXTREME BULL', '#a855f7', 0.25
    else: pz, pc, pm = 'UNKNOWN', '#6b7280', 1.0
    ctx['price_zone'] = {'zone': pz, 'color': pc, 'position_mult': pm}
    return ctx

def calculate_confluence(signals: dict, context: dict) -> dict:
    conf = {'buy_signals': [], 'sell_signals': []}
    price, levels = context['price']['value'], context['price_levels']
    
    if levels.get('realized_price') and price:
        if price < levels['realized_price']: conf['buy_signals'].append(('Cost', 'Below RP', '#22c55e'))
    if levels.get('true_market_mean') and price:
        if price < levels['true_market_mean']: conf['buy_signals'].append(('Cost', 'Below TMM', '#22c55e'))
    if levels.get('sth_realized_price') and price:
        if price < levels['sth_realized_price']: conf['buy_signals'].append(('Cost', 'Below STH', '#4ade80'))
        elif price > levels['sth_realized_price'] * 1.3: conf['sell_signals'].append(('Cost', '>30% STH', '#f87171'))
    if levels.get('vaulted_price') and price and price > levels['vaulted_price']:
        conf['sell_signals'].append(('Cost', 'Above Vaulted', '#ef4444'))
    
    mvrv, aviv = context['mvrv']['value'], context['aviv']['value']
    if mvrv is not None:
        if mvrv < 1: conf['buy_signals'].append(('Ratio', 'MVRV < 1', '#22c55e'))
        elif mvrv > 3: conf['sell_signals'].append(('Ratio', 'MVRV > 3', '#ef4444'))
    if aviv is not None:
        if aviv < 1: conf['buy_signals'].append(('Ratio', 'AVIV < 1', '#4ade80'))
    
    for sig in signals['entry'].values():
        if sig['triggered']: conf['buy_signals'].append(('Signal', sig['label'], '#22c55e'))
    
    conf['total_buy'], conf['total_sell'] = len(conf['buy_signals']), len(conf['sell_signals'])
    
    if conf['total_buy'] >= 4: conf['verdict'], conf['verdict_color'] = 'STRONG BUY', '#22c55e'
    elif conf['total_buy'] >= 2 and conf['total_sell'] == 0: conf['verdict'], conf['verdict_color'] = 'BUY', '#4ade80'
    elif conf['total_sell'] >= 3: conf['verdict'], conf['verdict_color'] = 'SELL', '#ef4444'
    elif conf['total_sell'] >= 1: conf['verdict'], conf['verdict_color'] = 'CAUTION', '#fbbf24'
    else: conf['verdict'], conf['verdict_color'] = 'NEUTRAL', '#6b7280'
    return conf

def calculate_sopr_metrics(data: dict) -> dict:
    metrics = {}
    for name, key in [('SOPR', 'sopr'), ('STH-SOPR', 'sopr_sth'), ('LTH-SOPR', 'sopr_lth')]:
        val, _ = get_latest(data.get(key, pd.DataFrame()))
        metrics[key] = {'name': name, 'value': val}
    return metrics

def calculate_supply_metrics(data: dict) -> dict:
    """Calculate supply dynamics metrics."""
    metrics = {}
    
    # LTH/STH Ratio
    ratio_val, _ = get_latest(data.get('supply_lth_sth_ratio', pd.DataFrame()))
    metrics['lth_sth_ratio'] = {'name': 'LTH/STH Ratio', 'value': ratio_val}
    
    # Individual supplies
    lth_val, _ = get_latest(data.get('supply_lth', pd.DataFrame()))
    sth_val, _ = get_latest(data.get('supply_sth', pd.DataFrame()))
    total_val, _ = get_latest(data.get('supply_total', pd.DataFrame()))
    
    metrics['supply_lth'] = {'name': 'LTH Supply', 'value': lth_val}
    metrics['supply_sth'] = {'name': 'STH Supply', 'value': sth_val}
    
    # Calculate percentages
    if lth_val and total_val:
        metrics['lth_pct'] = {'name': 'LTH %', 'value': (lth_val / total_val) * 100}
    else:
        metrics['lth_pct'] = {'name': 'LTH %', 'value': None}
    
    if sth_val and total_val:
        metrics['sth_pct'] = {'name': 'STH %', 'value': (sth_val / total_val) * 100}
    else:
        metrics['sth_pct'] = {'name': 'STH %', 'value': None}
    
    # Supply in profit
    profit_pct, _ = get_latest(data.get('supply_in_profit_percent', pd.DataFrame()))
    metrics['supply_profit_pct'] = {'name': 'Supply in Profit', 'value': profit_pct * 100 if profit_pct else None}
    
    # 30-day change in LTH/STH ratio
    ratio_df = data.get('supply_lth_sth_ratio', pd.DataFrame())
    if not ratio_df.empty and len(ratio_df) >= 30:
        ratio_30d_ago = ratio_df.iloc[-30]['value']
        if ratio_val and ratio_30d_ago:
            metrics['ratio_change_30d'] = {'name': '30d Change', 'value': ((ratio_val - ratio_30d_ago) / ratio_30d_ago) * 100}
        else:
            metrics['ratio_change_30d'] = {'name': '30d Change', 'value': None}
    else:
        metrics['ratio_change_30d'] = {'name': '30d Change', 'value': None}
    
    return metrics

def calculate_signals(context: dict, signals: dict, sopr_metrics: dict, supply_metrics: dict, momentum_metrics: dict) -> dict:
    """Calculate signal (BUY/HOLD/SELL) for each section."""
    section_signals = {}
    
    # Price signal - based on valuation zone
    zone = context['price_zone']['zone']
    if zone in ['EXTREME BEAR', 'UNDERVALUED']:
        section_signals['price'] = ('BUY', '#22c55e')
    elif zone in ['OVERVALUED', 'EXTREME BULL']:
        section_signals['price'] = ('SELL', '#ef4444')
    else:
        section_signals['price'] = ('HOLD', '#fbbf24')
    
    # Valuation signal - same as price
    section_signals['valuation'] = section_signals['price']
    
    # Entry signal
    entry_triggered = signals['groups'].get('strat_002_004_entry', {}).get('triggered', False)
    if entry_triggered:
        section_signals['entry'] = ('BUY', '#22c55e')
    else:
        section_signals['entry'] = ('NO BUY', '#6b7280')
    
    # Exit signal
    exit_count = sum(1 for s in signals['exit'].values() if s.get('triggered', False))
    if exit_count >= 2:
        section_signals['exit'] = ('SELL', '#ef4444')
    elif exit_count >= 1:
        section_signals['exit'] = ('CAUTION', '#fbbf24')
    else:
        section_signals['exit'] = ('NO SELL', '#6b7280')
    
    # Cycle signal - based on MVRV-Z zone
    mvrv_zone = context['mvrv_z']['zone']
    if mvrv_zone == 'DEEP VALUE':
        section_signals['cycle'] = ('BUY', '#22c55e')
    elif mvrv_zone == 'EUPHORIA':
        section_signals['cycle'] = ('SELL', '#ef4444')
    elif mvrv_zone == 'EXPENSIVE':
        section_signals['cycle'] = ('CAUTION', '#fbbf24')
    else:
        section_signals['cycle'] = ('HOLD', '#fbbf24')
    
    # SOPR signal
    sopr_val = sopr_metrics.get('sopr', {}).get('value')
    lth_sopr_val = sopr_metrics.get('sopr_lth', {}).get('value')
    if sopr_val and sopr_val < 0.95:
        section_signals['sopr'] = ('BUY', '#22c55e')
    elif lth_sopr_val and lth_sopr_val > 1.5:
        section_signals['sopr'] = ('CAUTION', '#fbbf24')
    else:
        section_signals['sopr'] = ('HOLD', '#fbbf24')
    
    # Supply signal
    ratio_change = supply_metrics.get('ratio_change_30d', {}).get('value')
    if ratio_change is not None:
        if ratio_change > 2:
            section_signals['supply'] = ('BUY', '#22c55e')
        elif ratio_change < -2:
            section_signals['supply'] = ('SELL', '#ef4444')
        else:
            section_signals['supply'] = ('HOLD', '#fbbf24')
    else:
        section_signals['supply'] = ('HOLD', '#fbbf24')
    
    # Momentum signal
    trend = momentum_metrics.get('trend', 'UNKNOWN')
    if trend in ['STRONG UPTREND', 'UPTREND']:
        section_signals['momentum'] = ('BUY', '#22c55e')
    elif trend in ['STRONG DOWNTREND', 'DOWNTREND']:
        section_signals['momentum'] = ('SELL', '#ef4444')
    else:
        section_signals['momentum'] = ('HOLD', '#fbbf24')
    
    return section_signals

def calculate_momentum_metrics(data: dict) -> dict:
    """Calculate momentum and trend metrics."""
    metrics = {}
    
    price_df = data.get('price', pd.DataFrame())
    if price_df.empty:
        return {'ma_50': None, 'ma_200': None, 'price': None, 'trend': 'UNKNOWN', 'trend_color': '#6b7280'}
    
    price_val, _ = get_latest(price_df)
    metrics['price'] = price_val
    
    # Calculate MAs
    if len(price_df) >= 50:
        metrics['ma_50'] = price_df.tail(50)['value'].mean()
    else:
        metrics['ma_50'] = None
    
    if len(price_df) >= 200:
        metrics['ma_200'] = price_df.tail(200)['value'].mean()
    else:
        metrics['ma_200'] = None
    
    # Determine trend
    if metrics['ma_50'] and metrics['ma_200']:
        if metrics['ma_50'] > metrics['ma_200']:
            if price_val and price_val > metrics['ma_50']:
                metrics['trend'] = 'STRONG UPTREND'
                metrics['trend_color'] = '#22c55e'
            else:
                metrics['trend'] = 'UPTREND'
                metrics['trend_color'] = '#4ade80'
        else:
            if price_val and price_val < metrics['ma_50']:
                metrics['trend'] = 'STRONG DOWNTREND'
                metrics['trend_color'] = '#ef4444'
            else:
                metrics['trend'] = 'DOWNTREND'
                metrics['trend_color'] = '#f87171'
    else:
        metrics['trend'] = 'UNKNOWN'
        metrics['trend_color'] = '#6b7280'
    
    # Price vs MA percentages
    if price_val and metrics['ma_50']:
        metrics['price_vs_ma50'] = ((price_val - metrics['ma_50']) / metrics['ma_50']) * 100
    else:
        metrics['price_vs_ma50'] = None
    
    if price_val and metrics['ma_200']:
        metrics['price_vs_ma200'] = ((price_val - metrics['ma_200']) / metrics['ma_200']) * 100
    else:
        metrics['price_vs_ma200'] = None
    
    # Golden/Death cross status
    if metrics['ma_50'] and metrics['ma_200']:
        metrics['cross_status'] = 'Golden Cross' if metrics['ma_50'] > metrics['ma_200'] else 'Death Cross'
        metrics['cross_color'] = '#22c55e' if metrics['ma_50'] > metrics['ma_200'] else '#ef4444'
    else:
        metrics['cross_status'] = 'N/A'
        metrics['cross_color'] = '#6b7280'
    
    return metrics

# =============================================================================
# HTML GENERATION
# =============================================================================

def generate_signal_rows(signals: dict, signal_type: str) -> str:
    html = ""
    for sig in signals[signal_type].values():
        val_str = f"{sig['value']:.4f}" if sig['value'] is not None else "N/A"
        val_class = "green" if (signal_type == "entry" and sig['triggered']) else ("red" if signal_type == "exit" and sig['triggered'] else "")
        badge_class = "badge-green" if sig['triggered'] else "badge-gray"
        html += f'''
                <div class="metric-row">
                    <span class="metric-label">{sig['label']}</span>
                    <span><span class="metric-value {val_class}">{val_str}</span>
                    <span class="badge {badge_class}">{"✓" if sig['triggered'] else "○"}</span></span>
                </div>'''
    return html

def generate_html(signals: dict, context: dict, sopr_metrics: dict, confluence: dict, data_freshness: str, supply_metrics: dict = None, momentum_metrics: dict = None, section_signals: dict = None) -> str:
    supply_metrics = supply_metrics or {}
    momentum_metrics = momentum_metrics or {}
    section_signals = section_signals or {}
    def fmt(val, d=4): return f"{val:,.{d}f}" if val is not None else 'N/A'
    def fmt_price(val): return f"${val:,.0f}" if val is not None else 'N/A'
    
    ts = context['price']['time']
    ts_str = ts.strftime('%Y-%m-%d') if ts else 'Unknown'
    
    entry_on = signals['groups'].get('strat_002_004_entry', {}).get('triggered', False)
    exit_on = signals['groups'].get('distribution_exit', {}).get('triggered', False)
    
    # Price levels as JSON for JavaScript
    levels_json = {
        'realized_price': context['price_levels'].get('realized_price'),
        'true_market_mean': context['price_levels'].get('true_market_mean'),
        'sth_realized_price': context['price_levels'].get('sth_realized_price'),
        'vaulted_price': context['price_levels'].get('vaulted_price'),
    }
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitcoin Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 24px; }}
        .header h1 {{ font-size: 24px; font-weight: 700; color: #f8fafc; }}
        .header .sub {{ color: #64748b; font-size: 13px; margin-top: 4px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 18px; border: 1px solid #334155; }}
        .card.wide {{ grid-column: span 2; }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid #334155; }}
        .card-title {{ font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
        .card-title.blue {{ color: #60a5fa; }} .card-title.green {{ color: #4ade80; }} .card-title.red {{ color: #f87171; }}
        .card-title.purple {{ color: #c084fc; }} .card-title.orange {{ color: #fb923c; }}
        .big-value {{ font-size: 32px; font-weight: 700; color: #f8fafc; }}
        .price-change {{ font-size: 14px; margin-left: 10px; }}
        .price-change.up {{ color: #4ade80; }}
        .price-change.down {{ color: #f87171; }}
        .metric-row {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #334155; }}
        .metric-row:last-child {{ border-bottom: none; }}
        .metric-label {{ color: #94a3b8; font-size: 13px; }}
        .metric-value {{ font-weight: 600; font-size: 14px; margin-right: 6px; }}
        .metric-value.green {{ color: #4ade80; }} .metric-value.red {{ color: #f87171; }}
        .badge {{ display: inline-block; padding: 3px 7px; border-radius: 5px; font-size: 11px; font-weight: 600; }}
        .badge-green {{ background: #14532d; color: #4ade80; }} .badge-gray {{ background: #374151; color: #9ca3af; }}
        .signal-box {{ padding: 14px; border-radius: 8px; text-align: center; margin-bottom: 14px; }}
        .signal-box.active {{ background: linear-gradient(135deg, #14532d, #166534); border: 2px solid #22c55e; }}
        .signal-box.inactive {{ background: #1e293b; border: 2px solid #475569; }}
        .signal-box.warning {{ background: linear-gradient(135deg, #7f1d1d, #991b1b); border: 2px solid #ef4444; }}
        .signal-text {{ font-size: 16px; font-weight: 700; }}
        .price-row {{ display: flex; align-items: center; gap: 10px; padding: 6px 0; font-size: 12px; }}
        .price-bar {{ flex: 1; height: 6px; background: #334155; border-radius: 3px; overflow: hidden; }}
        .price-bar-fill {{ height: 100%; border-radius: 3px; transition: width 0.3s; }}
        .price-label {{ width: 100px; color: #94a3b8; }}
        .price-value {{ width: 80px; text-align: right; font-weight: 600; }}
        .zone-badge {{ display: inline-block; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 700; }}
        .signal-badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; }}
        .zone-row {{ display: flex; align-items: center; padding: 6px 10px; border-radius: 5px; margin-bottom: 3px; font-size: 12px; }}
        .zone-row.active {{ border: 2px solid currentColor; }}
        .zone-emoji {{ width: 20px; }} .zone-name {{ flex: 1; font-weight: 600; }}
        .zone-range {{ color: #94a3b8; font-size: 11px; margin-right: 10px; }}
        .zone-mult {{ font-weight: 700; width: 40px; text-align: right; }}
        .conf-item {{ display: flex; align-items: center; padding: 4px 0; font-size: 12px; }}
        .conf-dot {{ width: 6px; height: 6px; border-radius: 50%; margin-right: 8px; }}
        .conf-cat {{ color: #64748b; width: 50px; font-size: 10px; }}
        .sopr-bar {{ width: 100%; height: 20px; background: linear-gradient(90deg, #ef4444 0%, #6b7280 50%, #22c55e 100%); border-radius: 4px; position: relative; margin: 6px 0; }}
        .sopr-marker {{ position: absolute; top: -3px; width: 3px; height: 26px; background: #f8fafc; border-radius: 2px; transform: translateX(-50%); }}
        .sopr-center {{ position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background: #f8fafc; opacity: 0.4; }}
        .footer {{ text-align: center; margin-top: 24px; padding-top: 16px; border-top: 1px solid #334155; color: #64748b; font-size: 12px; }}
        .live-dot {{ display: inline-block; width: 8px; height: 8px; background: #22c55e; border-radius: 50%; margin-right: 6px; animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
        .refresh-btn {{ position: fixed; bottom: 20px; right: 20px; background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }}
        @media (max-width: 768px) {{ .card.wide {{ grid-column: span 1; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>₿ Bitcoin Trading Dashboard</h1>
            <div class="sub">On-chain: {ts_str} ({data_freshness}) | <span class="live-dot"></span><span id="live-status">Connecting...</span></div>
        </div>
        
        <div class="grid">
            <!-- PRICE -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title blue">Price</span>
                    <span>
                        <span class="price-change" id="price-change"></span>
                        <span class="signal-badge" id="price-signal" style="background: {section_signals.get('price', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('price', ('HOLD', '#fbbf24'))[1]}; margin-left: 8px;">{section_signals.get('price', ('HOLD', '#fbbf24'))[0]}</span>
                    </span>
                </div>
                <div style="display: flex; align-items: baseline; margin-bottom: 16px;">
                    <div class="big-value" id="live-price">{fmt_price(context['price']['value'])}</div>
                </div>
                <div id="price-levels">'''
    
    price = context['price']['value'] or 1
    for label, key, color in [('Realized Price', 'realized_price', '#22c55e'), ('True Market Mean', 'true_market_mean', '#a855f7'),
                               ('STH Cost Basis', 'sth_realized_price', '#60a5fa'), ('Vaulted Price', 'vaulted_price', '#f97316')]:
        val = context['price_levels'].get(key)
        pct = min(100, (val or 0) / price * 100) if val else 0
        html += f'''
                            <div class="price-row" data-level="{key}">
                                <span class="price-label">{label}</span>
                                <div class="price-bar"><div class="price-bar-fill" style="width: {pct:.0f}%; background: {color};"></div></div>
                                <span class="price-value">{fmt_price(val)}</span>
                            </div>'''
    
    html += f'''
                </div>
            </div>
            
            <!-- VALUATION -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title purple">Valuation</span>
                    <span>
                        <span class="zone-badge" id="zone-badge" style="background: {context['price_zone']['color']}20; color: {context['price_zone']['color']}">{context['price_zone']['zone']}</span>
                        <span class="signal-badge" style="background: {section_signals.get('valuation', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('valuation', ('HOLD', '#fbbf24'))[1]}; margin-left: 8px;">{section_signals.get('valuation', ('HOLD', '#fbbf24'))[0]}</span>
                    </span>
                </div>'''
    
    zones = [('🔴', 'EXTREME BEAR', '< RP', '2x', '#ef4444'), ('🟠', 'UNDERVALUED', 'RP→TMM', '1.5x', '#f97316'),
             ('🟢', 'FAIR VALUE', 'TMM→STH', '1x', '#22c55e'), ('🟡', 'OVERVALUED', '> STH', '0.5x', '#fbbf24'),
             ('🟣', 'EXTREME BULL', '> Vault', '0.25x', '#a855f7')]
    
    for emoji, name, rng, mult, color in zones:
        active = context['price_zone']['zone'] == name
        style = f'background: {color}15;' if active else 'background: #0f172a;'
        html += f'''
                        <div class="zone-row {'active' if active else ''}" data-zone="{name}" style="{style} color: {color};">
                            <span class="zone-emoji">{emoji}</span>
                            <span class="zone-name">{name}</span>
                            <span class="zone-range">{rng}</span>
                            <span class="zone-mult">{mult}</span>
                        </div>'''
    
    html += f'''
                <div style="margin-top: 12px; padding: 10px; background: #0f172a; border-radius: 6px; text-align: center;">
                    <span style="color: #94a3b8; font-size: 11px;">Position Size:</span>
                    <span style="font-size: 20px; font-weight: 700; margin-left: 8px;" id="position-mult">{context['price_zone']['position_mult']}x</span>
                </div>
            </div>
            
            <!-- ENTRY SIGNALS -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title green">Entry Signals</span>
                    <span class="signal-badge" style="background: {section_signals.get('entry', ('NO BUY', '#6b7280'))[1]}20; color: {section_signals.get('entry', ('NO BUY', '#6b7280'))[1]};">{section_signals.get('entry', ('NO BUY', '#6b7280'))[0]}</span>
                </div>
                <div class="signal-box {'active' if entry_on else 'inactive'}">
                    <div class="signal-text" style="color: {'#22c55e' if entry_on else '#6b7280'}">{'🟢 ENTRY ACTIVE' if entry_on else '⚪ No Entry'}</div>
                </div>
                {generate_signal_rows(signals, 'entry')}
            </div>
            
            <!-- EXIT SIGNALS -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title red">Exit Signals</span>
                    <span class="signal-badge" style="background: {section_signals.get('exit', ('NO SELL', '#6b7280'))[1]}20; color: {section_signals.get('exit', ('NO SELL', '#6b7280'))[1]};">{section_signals.get('exit', ('NO SELL', '#6b7280'))[0]}</span>
                </div>
                <div class="signal-box {'warning' if exit_on else 'inactive'}">
                    <div class="signal-text" style="color: {'#ef4444' if exit_on else '#6b7280'}">{'🔴 EXIT ACTIVE' if exit_on else '⚪ No Exit'}</div>
                </div>
                {generate_signal_rows(signals, 'exit')}
                <div style="margin-top: 10px; padding: 8px; background: #0f172a; border-radius: 6px; font-size: 11px;">
                    <span style="color: #94a3b8;">Trailing:</span> <span style="color: #f8fafc;">STRAT-002: 30% | STRAT-004: 12%</span>
                </div>
            </div>
            
            <!-- CYCLE CONTEXT -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title purple">Cycle</span>
                    <span>
                        <span class="zone-badge" style="background: {context['mvrv_z']['zone_color']}20; color: {context['mvrv_z']['zone_color']}">{context['mvrv_z']['zone']}</span>
                        <span class="signal-badge" style="background: {section_signals.get('cycle', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('cycle', ('HOLD', '#fbbf24'))[1]}; margin-left: 8px;">{section_signals.get('cycle', ('HOLD', '#fbbf24'))[0]}</span>
                    </span>
                </div>
                <div class="metric-row"><span class="metric-label">MVRV-Z</span><span class="metric-value" style="color: {context['mvrv_z']['zone_color']}">{fmt(context['mvrv_z']['value'], 2)}</span></div>
                <div class="metric-row"><span class="metric-label">MVRV</span><span class="metric-value">{fmt(context['mvrv']['value'], 2)}</span></div>
                <div class="metric-row"><span class="metric-label">AVIV</span><span class="metric-value">{fmt(context['aviv']['value'], 2)}</span></div>
                <div class="metric-row"><span class="metric-label">NUPL</span><span class="metric-value">{fmt(context['nupl']['value'], 2)}</span></div>
                
                <!-- Cycle Zone Guide -->
                <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #334155;">
                    <div style="font-size: 10px; color: #64748b; margin-bottom: 6px; text-transform: uppercase;">Interpretation Guide</div>
                    <div class="zone-row{'" active" style="background: #22c55e15;' if context['mvrv_z']['zone'] == 'DEEP VALUE' else '" style="background: #0f172a;'}" data-cycle-zone="ACCUMULATION" style="color: #22c55e;">
                        <span class="zone-emoji">🟢</span>
                        <span class="zone-name">ACCUMULATION</span>
                        <span class="zone-range">≤ 1</span>
                        <span class="zone-mult">Buy</span>
                    </div>
                    <div class="zone-row{'" active" style="background: #3b82f615;' if context['mvrv_z']['zone'] == 'FAIR VALUE' else '" style="background: #0f172a;'}" data-cycle-zone="FAIR VALUE" style="color: #3b82f6;">
                        <span class="zone-emoji">🔵</span>
                        <span class="zone-name">FAIR VALUE</span>
                        <span class="zone-range">1-2</span>
                        <span class="zone-mult">Hold</span>
                    </div>
                    <div class="zone-row{'" active" style="background: #f9731615;' if context['mvrv_z']['zone'] == 'EXPENSIVE' else '" style="background: #0f172a;'}" data-cycle-zone="EXPENSIVE" style="color: #f97316;">
                        <span class="zone-emoji">🟠</span>
                        <span class="zone-name">EXPENSIVE</span>
                        <span class="zone-range">2-3</span>
                        <span class="zone-mult">Reduce</span>
                    </div>
                    <div class="zone-row{'" active" style="background: #ef444415;' if context['mvrv_z']['zone'] == 'EUPHORIA' else '" style="background: #0f172a;'}" data-cycle-zone="EUPHORIA" style="color: #ef4444;">
                        <span class="zone-emoji">🔴</span>
                        <span class="zone-name">EUPHORIA</span>
                        <span class="zone-range">> 3</span>
                        <span class="zone-mult">Exit</span>
                    </div>
                </div>
            </div>
            
            <!-- SOPR -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title orange">SOPR</span>
                    <span class="signal-badge" style="background: {section_signals.get('sopr', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('sopr', ('HOLD', '#fbbf24'))[1]};">{section_signals.get('sopr', ('HOLD', '#fbbf24'))[0]}</span>
                </div>'''
    
    for key in ['sopr', 'sopr_sth', 'sopr_lth']:
        m = sopr_metrics.get(key, {})
        val = m.get('value', 1) or 1
        pct = max(0, min(100, (val - 0.8) / (1.5 - 0.8) * 100))
        color = '#4ade80' if val > 1 else '#f87171'
        html += f'''
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 3px;">
                        <span style="color: #94a3b8;">{m.get('name', key)}</span>
                        <span style="font-weight: 600; color: {color}">{fmt(m.get('value'), 4)}</span>
                    </div>
                    <div class="sopr-bar"><div class="sopr-center"></div><div class="sopr-marker" style="left: {pct}%"></div></div>
                </div>'''
    
    # Add price levels JSON for JavaScript
    import json
    levels_str = json.dumps(levels_json)
    
    # Supply Dynamics card
    lth_pct = supply_metrics.get('lth_pct', {}).get('value')
    sth_pct = supply_metrics.get('sth_pct', {}).get('value')
    ratio_val = supply_metrics.get('lth_sth_ratio', {}).get('value')
    ratio_change = supply_metrics.get('ratio_change_30d', {}).get('value')
    profit_pct = supply_metrics.get('supply_profit_pct', {}).get('value')
    
    # Determine accumulation/distribution phase
    if ratio_change is not None:
        if ratio_change > 2:
            phase, phase_color = 'ACCUMULATING', '#22c55e'
        elif ratio_change > 0:
            phase, phase_color = 'NEUTRAL', '#6b7280'
        elif ratio_change > -2:
            phase, phase_color = 'DISTRIBUTING', '#fbbf24'
        else:
            phase, phase_color = 'HEAVY DIST', '#ef4444'
    else:
        phase, phase_color = 'UNKNOWN', '#6b7280'
    
    html += f'''
            </div>
            
            <!-- SUPPLY DYNAMICS -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" style="color: #06b6d4;">Supply Dynamics</span>
                    <span>
                        <span class="zone-badge" style="background: {phase_color}20; color: {phase_color}">{phase}</span>
                        <span class="signal-badge" style="background: {section_signals.get('supply', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('supply', ('HOLD', '#fbbf24'))[1]}; margin-left: 8px;">{section_signals.get('supply', ('HOLD', '#fbbf24'))[0]}</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">LTH/STH Ratio</span>
                    <span class="metric-value">{fmt(ratio_val, 2)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">30d Change</span>
                    <span class="metric-value" style="color: {'#4ade80' if ratio_change and ratio_change > 0 else '#f87171' if ratio_change else '#6b7280'}">{'+' if ratio_change and ratio_change > 0 else ''}{fmt(ratio_change, 2)}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">LTH Supply %</span>
                    <span class="metric-value">{fmt(lth_pct, 1)}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">STH Supply %</span>
                    <span class="metric-value">{fmt(sth_pct, 1)}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Supply in Profit</span>
                    <span class="metric-value" style="color: {'#4ade80' if profit_pct and profit_pct > 75 else '#fbbf24' if profit_pct and profit_pct > 50 else '#f87171' if profit_pct else '#6b7280'}">{fmt(profit_pct, 1)}%</span>
                </div>
            </div>
            
            <!-- MOMENTUM / TREND -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" style="color: #ec4899;">Momentum / Trend</span>
                    <span>
                        <span class="zone-badge" style="background: {momentum_metrics.get('trend_color', '#6b7280')}20; color: {momentum_metrics.get('trend_color', '#6b7280')}">{momentum_metrics.get('trend', 'UNKNOWN')}</span>
                        <span class="signal-badge" style="background: {section_signals.get('momentum', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('momentum', ('HOLD', '#fbbf24'))[1]}; margin-left: 8px;">{section_signals.get('momentum', ('HOLD', '#fbbf24'))[0]}</span>
                    </span>
                </div>
                <div style="margin-bottom: 10px; padding: 8px; background: #0f172a; border-radius: 6px; text-align: center;">
                    <span style="font-size: 11px; color: {momentum_metrics.get('cross_color', '#6b7280')}; font-weight: 600;">{momentum_metrics.get('cross_status', 'N/A')}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">50 MA</span>
                    <span class="metric-value">{fmt_price(momentum_metrics.get('ma_50'))}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Price vs 50 MA</span>
                    <span class="metric-value" style="color: {'#4ade80' if momentum_metrics.get('price_vs_ma50') and momentum_metrics.get('price_vs_ma50') > 0 else '#f87171' if momentum_metrics.get('price_vs_ma50') else '#6b7280'}">{'+' if momentum_metrics.get('price_vs_ma50') and momentum_metrics.get('price_vs_ma50') > 0 else ''}{fmt(momentum_metrics.get('price_vs_ma50'), 1)}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">200 MA</span>
                    <span class="metric-value">{fmt_price(momentum_metrics.get('ma_200'))}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Price vs 200 MA</span>
                    <span class="metric-value" style="color: {'#4ade80' if momentum_metrics.get('price_vs_ma200') and momentum_metrics.get('price_vs_ma200') > 0 else '#f87171' if momentum_metrics.get('price_vs_ma200') else '#6b7280'}">{'+' if momentum_metrics.get('price_vs_ma200') and momentum_metrics.get('price_vs_ma200') > 0 else ''}{fmt(momentum_metrics.get('price_vs_ma200'), 1)}%</span>
                </div>
            </div>
        </div>
        
        <div class="footer">Entry: {len(ENTRY_SIGNALS)} | Exit: {len(EXIT_SIGNALS)} | 4+ confluence = high confidence</div>
    </div>
    <button class="refresh-btn" onclick="location.reload()">↻</button>
    
    <script>
        // Price levels from on-chain data
        const priceLevels = {levels_str};
        
        // Format price
        function formatPrice(price) {{
            return '$' + Math.round(price).toLocaleString();
        }}
        
        // Determine valuation zone based on price
        function getZone(price) {{
            if (price < priceLevels.realized_price) return {{ zone: 'EXTREME BEAR', color: '#ef4444', mult: '2x' }};
            if (price < priceLevels.true_market_mean) return {{ zone: 'UNDERVALUED', color: '#f97316', mult: '1.5x' }};
            if (price < priceLevels.sth_realized_price) return {{ zone: 'FAIR VALUE', color: '#22c55e', mult: '1x' }};
            if (price < priceLevels.vaulted_price) return {{ zone: 'OVERVALUED', color: '#fbbf24', mult: '0.5x' }};
            return {{ zone: 'EXTREME BULL', color: '#a855f7', mult: '0.25x' }};
        }}
        
        // Update price bars based on live price
        function updatePriceBars(price) {{
            const bars = document.querySelectorAll('.price-row');
            bars.forEach(row => {{
                const level = row.dataset.level;
                const levelPrice = priceLevels[level];
                if (levelPrice) {{
                    const pct = Math.min(100, (levelPrice / price) * 100);
                    const fill = row.querySelector('.price-bar-fill');
                    if (fill) fill.style.width = pct + '%';
                }}
            }});
        }}
        
        // Update zone highlighting
        function updateZoneHighlight(zoneName) {{
            const zones = document.querySelectorAll('.zone-row');
            zones.forEach(row => {{
                const isActive = row.dataset.zone === zoneName;
                row.classList.toggle('active', isActive);
                if (isActive) {{
                    row.style.background = row.style.color.replace(')', ', 0.15)').replace('rgb', 'rgba');
                }} else {{
                    row.style.background = '#0f172a';
                }}
            }});
        }}
        
        // Fetch price from Coinbase
        async function fetchPrice() {{
            try {{
                const response = await fetch('https://api.coinbase.com/v2/prices/BTC-USD/spot');
                const data = await response.json();
                const price = parseFloat(data.data.amount);
                
                // Update price display
                document.getElementById('live-price').textContent = formatPrice(price);
                document.getElementById('live-status').textContent = 'Live from Coinbase';
                
                // Get 24h change
                const tickerResponse = await fetch('https://api.exchange.coinbase.com/products/BTC-USD/ticker');
                const ticker = await tickerResponse.json();
                const open24h = parseFloat(ticker.open_24h);
                const change = ((price - open24h) / open24h) * 100;
                
                const changeEl = document.getElementById('price-change');
                changeEl.textContent = (change >= 0 ? '+' : '') + change.toFixed(2) + '%';
                changeEl.className = 'price-change ' + (change >= 0 ? 'up' : 'down');
                
                // Update valuation zone
                const zone = getZone(price);
                const zoneBadge = document.getElementById('zone-badge');
                zoneBadge.textContent = zone.zone;
                zoneBadge.style.background = zone.color + '20';
                zoneBadge.style.color = zone.color;
                
                const multEl = document.getElementById('position-mult');
                multEl.textContent = zone.mult;
                multEl.style.color = zone.color;
                
                // Update price bars and zone highlighting
                updatePriceBars(price);
                updateZoneHighlight(zone.zone);
                
            }} catch (error) {{
                console.error('Price fetch error:', error);
                document.getElementById('live-status').textContent = 'Update failed';
            }}
        }}
        
        // Initial fetch and then every 10 seconds
        fetchPrice();
        setInterval(fetchPrice, 10000);
    </script>
</body>
</html>'''
    return html

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 50)
    print("Bitcoin Trading Dashboard")
    print("=" * 50)
    
    if not DATA_DIR.exists():
        print(f"❌ Data not found: {DATA_DIR}")
        return
    
    metrics_needed = set(s['metric'] for s in ENTRY_SIGNALS + EXIT_SIGNALS)
    metrics_needed.update(['price', 'mvrv', 'mvrv_z', 'nupl', 'aviv', 'realized_price', 
                          'true_market_mean_price', 'vaulted_price', 'realized_price_sth',
                          'supply_lth', 'supply_sth', 'supply_lth_sth_ratio', 'supply_total',
                          'supply_in_profit_percent'])
    
    print("Loading...")
    data = {}
    latest_date = None
    for m in sorted(metrics_needed):
        data[m] = load_metric(m)
        val, ts = get_latest(data[m])
        if val: print(f"  ✓ {m}: {val:.4f}")
        else: print(f"  ✗ {m}")
        if ts and (not latest_date or ts > latest_date): latest_date = ts
    
    days_old = (datetime.now() - latest_date).days if latest_date else 999
    freshness = f"⚠️ {days_old}d old" if days_old > 1 else "✓ Current"
    
    signals = calculate_all_signals(data)
    context = calculate_context(data)
    confluence = calculate_confluence(signals, context)
    sopr = calculate_sopr_metrics(data)
    supply = calculate_supply_metrics(data)
    momentum = calculate_momentum_metrics(data)
    section_signals = calculate_signals(context, signals, sopr, supply, momentum)
    
    entry_on = signals['groups'].get('strat_002_004_entry', {}).get('triggered', False)
    exit_on = signals['groups'].get('distribution_exit', {}).get('triggered', False)
    
    print(f"\n{'─' * 40}")
    print(f"ENTRY: {'🟢 ACTIVE' if entry_on else '⚪ inactive'}")
    print(f"EXIT:  {'🔴 ACTIVE' if exit_on else '⚪ inactive'}")
    print(f"ZONE:  {context['price_zone']['zone']} ({context['price_zone']['position_mult']}x)")
    print(f"CONFLUENCE: {confluence['verdict']} ({confluence['total_buy']}↑ {confluence['total_sell']}↓)")
    print(f"{'─' * 40}")
    
    html = generate_html(signals, context, sopr, confluence, freshness, supply, momentum, section_signals)
    OUTPUT_PATH.write_text(html)
    print(f"\n✓ Saved: {OUTPUT_PATH}")
    
    if '--no-open' not in sys.argv:
        webbrowser.open(f"file://{OUTPUT_PATH.absolute()}")
    
    if '--watch' in sys.argv:
        print("\n⟳ Watch mode (60s)...")
        try:
            while True:
                time.sleep(60)
                main()
        except KeyboardInterrupt:
            print("\nStopped.")

if __name__ == "__main__":
    main()
