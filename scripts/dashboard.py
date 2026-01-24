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
import requests
import os

# =============================================================================
# CONFIGURATION
# =============================================================================

# Data directories - use BRK as primary source (free, current data)
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "brk" / "daily"
OUTPUT_PATH = PROJECT_ROOT / "dashboard.html"

# API Configuration - load from environment variables
try:
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.secrets import get_bitcoin_lab_key, get_glassnode_key
    BITCOIN_LAB_API_TOKEN = get_bitcoin_lab_key()
    GLASSNODE_API_KEY = get_glassnode_key()
except (ImportError, ValueError):
    # Fallback to environment variables
    BITCOIN_LAB_API_TOKEN = os.environ.get('BITCOIN_LAB_API_KEY') or os.environ.get('BITCOIN_LAB_TOKEN')
    GLASSNODE_API_KEY = os.environ.get('GLASSNODE_API_KEY')

BITCOIN_LAB_API_URL = "https://api.researchbitcoin.net"
GLASSNODE_API_URL = "https://api.glassnode.com"

# Free derivatives data directory (Binance/Bybit - backup)
FREE_DERIVATIVES_DIR = PROJECT_ROOT / "data" / "derivatives" / "daily"

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
    """Load metric from parquet file, normalizing to 'time' and 'value' columns."""
    path = DATA_DIR / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame(columns=['time', 'value'])
    
    df = pd.read_parquet(path)
    
    time_col = None
    if 'time' in df.columns:
        time_col = 'time'
    elif 'date' in df.columns:
        time_col = 'date'
    elif 'timestamp' in df.columns:
        time_col = 'timestamp'
    elif isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        time_col = df.columns[0]
    elif df.index.name and 'time' in df.index.name.lower():
        df = df.reset_index()
        time_col = df.columns[0]
    
    if time_col and time_col != 'time':
        df = df.rename(columns={time_col: 'time'})
    
    if 'time' not in df.columns:
        return pd.DataFrame(columns=['time', 'value'])
    
    if 'value' not in df.columns:
        for col in df.columns:
            if col != 'time' and pd.api.types.is_numeric_dtype(df[col]):
                df = df.rename(columns={col: 'value'})
                break
    
    if 'value' not in df.columns:
        return pd.DataFrame(columns=['time', 'value'])
    
    df['time'] = pd.to_datetime(df['time'])
    if hasattr(df['time'].dt, 'tz') and df['time'].dt.tz is not None:
        df['time'] = df['time'].dt.tz_localize(None)
    
    df = df[['time', 'value']].copy()
    return df.sort_values('time').reset_index(drop=True)

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


def load_glassnode_cached(metric_name: str) -> pd.DataFrame:
    """Load Glassnode metric from cached parquet file.
    
    Args:
        metric_name: Name of metric (e.g., 'funding_rate', 'liquidations_long')
    
    Returns:
        DataFrame with time index and 'value' column, or empty DataFrame
    """
    gn_data_dir = PROJECT_ROOT / "data" / "glassnode" / "daily"
    file_path = gn_data_dir / f"{metric_name}.parquet"
    
    if file_path.exists():
        try:
            df = pd.read_parquet(file_path)
            return df
        except Exception as e:
            print(f"  ⚠ Error loading {metric_name}: {e}")
    return pd.DataFrame()


def load_free_derivatives(metric_name: str) -> pd.DataFrame:
    """Load free derivatives data from Binance/Bybit cache.
    
    Args:
        metric_name: Name of metric (e.g., 'funding_rate', 'open_interest')
    
    Returns:
        DataFrame with time index and 'value' column, or empty DataFrame
    """
    file_path = FREE_DERIVATIVES_DIR / f"{metric_name}.parquet"
    
    if file_path.exists():
        try:
            df = pd.read_parquet(file_path)
            return df
        except Exception as e:
            print(f"  ⚠ Error loading free {metric_name}: {e}")
    return pd.DataFrame()


def fetch_glassnode_metric(endpoint: str, asset: str = 'BTC', interval: str = '24h', lookback_days: int = 7) -> list:
    """Fetch metric from Glassnode API (fallback when cache unavailable).
    
    Args:
        endpoint: Metric endpoint (e.g., '/v1/metrics/derivatives/futures_funding_rate_perpetual')
        asset: Asset symbol (default: 'BTC')
        interval: Time interval ('1h', '24h', etc.)
        lookback_days: Number of days to fetch
    
    Returns:
        List of {timestamp, value} dicts, or empty list on error
    """
    import time as time_module
    from datetime import timedelta
    
    url = f"{GLASSNODE_API_URL}{endpoint}"
    
    # Calculate time range
    now = datetime.now()
    since = int((now - timedelta(days=lookback_days)).timestamp())
    
    params = {
        'a': asset,
        'i': interval,
        's': since,
        'api_key': GLASSNODE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  ⚠ Glassnode API error ({response.status_code}): {endpoint}")
            return []
    except Exception as e:
        print(f"  ⚠ Glassnode fetch failed: {e}")
        return []


def get_glassnode_derivatives() -> dict:
    """Get derivatives data with priority: Glassnode cache > Glassnode API > Free (Binance).
    
    Priority order:
    1. Cached Glassnode data (from glassnode_downloader)
    2. Live Glassnode API
    3. Free derivatives data (Binance/Bybit as fallback)
    
    Returns:
        Dict with funding_rate and liquidation data
    """
    result = {
        'funding_rate': None,
        'funding_rate_negative': False,
        'long_liquidations': None,
        'short_liquidations': None,
        'liquidation_ratio': None,
        'long_liq_peak': False,
        'available': False,
        'source': 'none',
        'long_short_ratio': None,
        'taker_buy_sell_ratio': None
    }
    
    # =========================================================================
    # PRIORITY 1: Cached Glassnode data
    # =========================================================================
    funding_df = load_glassnode_cached('funding_rate')
    long_liq_df = load_glassnode_cached('liquidations_long')
    short_liq_df = load_glassnode_cached('liquidations_short')
    
    cache_available = not funding_df.empty or not long_liq_df.empty
    
    if cache_available:
        print("  Using cached Glassnode data")
        result['source'] = 'glassnode_cache'
        
        # Funding rate from cache
        if not funding_df.empty:
            latest_funding = funding_df['value'].iloc[-1]
            result['funding_rate'] = latest_funding
            result['funding_rate_negative'] = latest_funding <= 0
            result['available'] = True
        
        # Long liquidations from cache
        if not long_liq_df.empty:
            result['long_liquidations'] = long_liq_df['value'].iloc[-1]
            
            # Check for peak (last value vs recent average)
            if len(long_liq_df) >= 3:
                recent_avg = long_liq_df['value'].tail(3).mean()
                if result['long_liquidations'] > recent_avg * 1.5:
                    result['long_liq_peak'] = True
        
        # Short liquidations from cache
        if not short_liq_df.empty:
            result['short_liquidations'] = short_liq_df['value'].iloc[-1]
        
        # Calculate liquidation ratio
        if result['long_liquidations'] and result['short_liquidations'] and result['short_liquidations'] > 0:
            result['liquidation_ratio'] = result['long_liquidations'] / result['short_liquidations']
        
        return result
    
    # =========================================================================
    # PRIORITY 3: Live Glassnode API (expensive fallback)
    # =========================================================================
    print("  Fetching Glassnode derivatives from API (expensive)...")
    result['source'] = 'glassnode_api'
    
    # Fetch funding rate
    funding_data = fetch_glassnode_metric(
        '/v1/metrics/derivatives/futures_funding_rate_perpetual',
        lookback_days=7
    )
    if funding_data:
        latest_funding = funding_data[-1] if funding_data else None
        if latest_funding and 'v' in latest_funding:
            result['funding_rate'] = latest_funding['v']
            result['funding_rate_negative'] = latest_funding['v'] <= 0
            result['available'] = True
    
    # Fetch long liquidations
    long_liq_data = fetch_glassnode_metric(
        '/v1/metrics/derivatives/futures_liquidated_volume_long_sum',
        lookback_days=7
    )
    if long_liq_data:
        latest_long = long_liq_data[-1] if long_liq_data else None
        if latest_long and 'v' in latest_long:
            result['long_liquidations'] = latest_long['v']
            
            # Check if long liquidations peaked
            if len(long_liq_data) >= 3:
                recent_longs = [d['v'] for d in long_liq_data[-3:]]
                avg_recent = sum(recent_longs) / len(recent_longs)
                if result['long_liquidations'] > avg_recent * 1.5:
                    result['long_liq_peak'] = True
    
    # Fetch short liquidations
    short_liq_data = fetch_glassnode_metric(
        '/v1/metrics/derivatives/futures_liquidated_volume_short_sum',
        lookback_days=7
    )
    if short_liq_data:
        latest_short = short_liq_data[-1] if short_liq_data else None
        if latest_short and 'v' in latest_short:
            result['short_liquidations'] = latest_short['v']
    
    # Calculate liquidation ratio
    if result['long_liquidations'] and result['short_liquidations'] and result['short_liquidations'] > 0:
        result['liquidation_ratio'] = result['long_liquidations'] / result['short_liquidations']
    
    return result

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
    if mvrv_z_val is None:
        mvrv_df = data.get('mvrv', pd.DataFrame())
        if not mvrv_df.empty and len(mvrv_df) >= 365:
            mvrv_z_val = calculate_z_score(mvrv_df, lookback=1460)
    
    if mvrv_z_val is not None:
        if mvrv_z_val < 0: zone, zc = 'DEEP VALUE', '#22c55e'
        elif mvrv_z_val < 1.5: zone, zc = 'FAIR VALUE', '#3b82f6'
        elif mvrv_z_val < 2.5: zone, zc = 'EXPENSIVE', '#f97316'
        else: zone, zc = 'EUPHORIA', '#ef4444'
    else: zone, zc = 'UNKNOWN', '#6b7280'
    ctx['mvrv_z'] = {'value': mvrv_z_val, 'zone': zone, 'zone_color': zc}
    
    for key in ['mvrv', 'aviv']:
        val, _ = get_latest(data.get(key, pd.DataFrame()))
        ctx[key] = {'value': val}
    
    nupl_val, _ = get_latest(data.get('nupl', pd.DataFrame()))
    if nupl_val is not None and nupl_val > 10:
        market_cap, _ = get_latest(data.get('market_cap', pd.DataFrame()))
        if market_cap and market_cap > 0:
            nupl_val = nupl_val / market_cap
    ctx['nupl'] = {'value': nupl_val}
    
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
    """Calculate spending behavior metrics (James Check framework).
    
    SOPR = Spent Output Profit Ratio
    - < 1: Market selling at loss (capitulation, buy signal)
    - = 1: Break-even (support/resistance)
    - > 1: Market selling at profit (distribution)
    
    STH-SOPR: Short-term holder spending (more reactive, sentiment indicator)
    - < 0.97: STH panic selling at significant loss (strong buy)
    - < 1.0: STH selling at loss (accumulate)
    - > 1.0: STH taking profits (normal)
    - > 1.05: STH aggressive profit-taking (distribution)
    
    LTH-SOPR: Long-term holder spending (conviction, cycle indicator)
    - < 1.0: LTH capitulation (rare, extreme buy signal)
    - 1.0-1.5: Normal LTH profit-taking
    - > 1.5: LTH heavy distribution (cycle top warning)
    - > 2.0: LTH extreme distribution (take profits)
    
    Realized P/L Ratio = Realized Profit / Realized Loss
    - > 10: Extreme profit dominance (distribution phase)
    - 1-10: Healthy profit-taking
    - < 1: Loss dominance (capitulation)
    """
    metrics = {}
    
    # Core SOPR metrics with additional context
    for name, key in [('SOPR', 'sopr'), ('STH-SOPR', 'sopr_sth'), ('LTH-SOPR', 'sopr_lth'), ('Adj-SOPR', 'sopr_adjusted')]:
        val, _ = get_latest(data.get(key, pd.DataFrame()))
        metrics[key] = {'name': name, 'value': val}
    
    # Extract for easier access
    sopr_val = metrics.get('sopr', {}).get('value')
    sth_sopr_val = metrics.get('sopr_sth', {}).get('value')
    lth_sopr_val = metrics.get('sopr_lth', {}).get('value')
    
    # SOPR position calculations for visualization bars (map to 0-100%)
    # SOPR typically ranges from 0.9 to 1.1 for interesting zones
    if sopr_val is not None:
        metrics['sopr_position'] = max(0, min(100, (sopr_val - 0.9) / 0.2 * 100))
    else:
        metrics['sopr_position'] = 50
    
    # STH-SOPR position (more volatile, 0.95-1.05 range)
    if sth_sopr_val is not None:
        metrics['sth_sopr_position'] = max(0, min(100, (sth_sopr_val - 0.95) / 0.1 * 100))
    else:
        metrics['sth_sopr_position'] = 50
    
    # LTH-SOPR position (wider range, 0.8-2.0 is interesting)
    if lth_sopr_val is not None:
        metrics['lth_sopr_position'] = max(0, min(100, (lth_sopr_val - 0.8) / 1.2 * 100))
    else:
        metrics['lth_sopr_position'] = 50
    
    # STH spending state
    if sth_sopr_val is not None:
        if sth_sopr_val < 0.97:
            metrics['sth_state'] = 'PANIC'
            metrics['sth_state_color'] = '#22c55e'
        elif sth_sopr_val < 1.0:
            metrics['sth_state'] = 'LOSS-TAKING'
            metrics['sth_state_color'] = '#4ade80'
        elif sth_sopr_val > 1.05:
            metrics['sth_state'] = 'DISTRIBUTION'
            metrics['sth_state_color'] = '#ef4444'
        elif sth_sopr_val > 1.02:
            metrics['sth_state'] = 'PROFIT-TAKING'
            metrics['sth_state_color'] = '#fbbf24'
        else:
            metrics['sth_state'] = 'NEUTRAL'
            metrics['sth_state_color'] = '#6b7280'
    else:
        metrics['sth_state'] = 'UNKNOWN'
        metrics['sth_state_color'] = '#6b7280'
    
    # LTH spending state (different thresholds - LTH moves are more significant)
    if lth_sopr_val is not None:
        if lth_sopr_val < 1.0:
            metrics['lth_state'] = 'CAPITULATION'
            metrics['lth_state_color'] = '#22c55e'
        elif lth_sopr_val > 2.0:
            metrics['lth_state'] = 'EXTREME DIST'
            metrics['lth_state_color'] = '#ef4444'
        elif lth_sopr_val > 1.5:
            metrics['lth_state'] = 'DISTRIBUTION'
            metrics['lth_state_color'] = '#fbbf24'
        else:
            metrics['lth_state'] = 'NORMAL'
            metrics['lth_state_color'] = '#6b7280'
    else:
        metrics['lth_state'] = 'UNKNOWN'
        metrics['lth_state_color'] = '#6b7280'
    
    # Realized Profit/Loss
    realized_profit, _ = get_latest(data.get('realized_profit', pd.DataFrame()))
    realized_loss, _ = get_latest(data.get('realized_loss', pd.DataFrame()))
    metrics['realized_profit'] = realized_profit
    metrics['realized_loss'] = realized_loss
    
    # Realized P/L Ratio
    if realized_profit and realized_loss and realized_loss > 0:
        metrics['realized_pl_ratio'] = realized_profit / realized_loss
    else:
        metrics['realized_pl_ratio'] = None
    
    # Net Realized P/L (for direction)
    net_realized, _ = get_latest(data.get('net_realized_pnl', pd.DataFrame()))
    metrics['net_realized_pnl'] = net_realized
    
    # 7-day smoothed SOPR for trend (reduces noise)
    sopr_df = data.get('sopr', pd.DataFrame())
    if not sopr_df.empty and len(sopr_df) >= 7:
        metrics['sopr_7d_avg'] = sopr_df.tail(7)['value'].mean()
    else:
        metrics['sopr_7d_avg'] = sopr_val
    
    # SOPR trend (current vs 7d avg)
    if sopr_val and metrics.get('sopr_7d_avg'):
        metrics['sopr_trend'] = 'Rising' if sopr_val > metrics['sopr_7d_avg'] else 'Falling'
        metrics['sopr_trend_color'] = '#f87171' if sopr_val > metrics['sopr_7d_avg'] else '#4ade80'
    else:
        metrics['sopr_trend'] = 'N/A'
        metrics['sopr_trend_color'] = '#6b7280'
    
    # Cohort divergence (STH vs LTH behavior)
    if sth_sopr_val is not None and lth_sopr_val is not None:
        if sth_sopr_val < 1.0 and lth_sopr_val > 1.5:
            metrics['cohort_divergence'] = 'STH PANIC / LTH SELLING'
            metrics['divergence_color'] = '#fbbf24'
            metrics['divergence_desc'] = 'Mixed signals - be cautious'
        elif sth_sopr_val < 0.97 and lth_sopr_val < 1.0:
            metrics['cohort_divergence'] = 'ALL CAPITULATING'
            metrics['divergence_color'] = '#22c55e'
            metrics['divergence_desc'] = 'Maximum fear - strong buy'
        elif sth_sopr_val > 1.02 and lth_sopr_val > 1.5:
            metrics['cohort_divergence'] = 'ALL DISTRIBUTING'
            metrics['divergence_color'] = '#ef4444'
            metrics['divergence_desc'] = 'Maximum greed - take profits'
        else:
            metrics['cohort_divergence'] = 'NORMAL'
            metrics['divergence_color'] = '#6b7280'
            metrics['divergence_desc'] = 'Typical market behavior'
    else:
        metrics['cohort_divergence'] = 'UNKNOWN'
        metrics['divergence_color'] = '#6b7280'
        metrics['divergence_desc'] = 'Insufficient data'
    
    # Composite spending sentiment (overall market)
    pl_ratio = metrics.get('realized_pl_ratio')
    if sopr_val is not None and sth_sopr_val is not None:
        if sopr_val < 0.97 and sth_sopr_val < 0.97:
            metrics['sentiment'] = 'CAPITULATION'
            metrics['sentiment_color'] = '#22c55e'
            metrics['sentiment_desc'] = 'Heavy loss-taking - buy zone'
        elif sopr_val < 1.0 or sth_sopr_val < 1.0:
            metrics['sentiment'] = 'LOSS-TAKING'
            metrics['sentiment_color'] = '#4ade80'
            metrics['sentiment_desc'] = 'Selling at loss - accumulate'
        elif sopr_val > 1.05 and (pl_ratio and pl_ratio > 5):
            metrics['sentiment'] = 'PROFIT-TAKING'
            metrics['sentiment_color'] = '#fbbf24'
            metrics['sentiment_desc'] = 'Taking profits - caution'
        elif sopr_val > 1.1:
            metrics['sentiment'] = 'DISTRIBUTION'
            metrics['sentiment_color'] = '#ef4444'
            metrics['sentiment_desc'] = 'Heavy profit-taking - sell zone'
        else:
            metrics['sentiment'] = 'NEUTRAL'
            metrics['sentiment_color'] = '#6b7280'
            metrics['sentiment_desc'] = 'Balanced spending'
    else:
        metrics['sentiment'] = 'UNKNOWN'
        metrics['sentiment_color'] = '#6b7280'
        metrics['sentiment_desc'] = 'No data'
    
    return metrics

def calculate_checkmate_signal(data: dict) -> dict:
    """Calculate the Checkmate composite signal (James Check framework)."""
    metrics = {}
    
    mvrv, _ = get_latest(data.get('mvrv', pd.DataFrame()))
    sth_mvrv, _ = get_latest(data.get('mvrv_sth', pd.DataFrame()))
    sopr, _ = get_latest(data.get('sopr', pd.DataFrame()))
    sth_sopr, _ = get_latest(data.get('sopr_sth', pd.DataFrame()))
    lth_sopr, _ = get_latest(data.get('sopr_lth', pd.DataFrame()))
    nupl, _ = get_latest(data.get('nupl', pd.DataFrame()))
    if nupl is not None and nupl > 10:
        market_cap, _ = get_latest(data.get('market_cap', pd.DataFrame()))
        if market_cap and market_cap > 0:
            nupl = nupl / market_cap
    puell, _ = get_latest(data.get('puell_multiple', pd.DataFrame()))
    sell_side_risk, _ = get_latest(data.get('sell_side_risk', pd.DataFrame()))
    
    metrics['mvrv'] = mvrv
    metrics['sth_mvrv'] = sth_mvrv
    metrics['sopr'] = sopr
    metrics['sth_sopr'] = sth_sopr
    metrics['lth_sopr'] = lth_sopr
    metrics['nupl'] = nupl
    metrics['puell'] = puell
    metrics['sell_side_risk'] = sell_side_risk
    
    scores = []
    score_details = []
    
    if mvrv is not None:
        mvrv_score = np.clip((mvrv - 2) / 2, -1, 1)
        scores.append(mvrv_score * 1.5)
        score_details.append(('MVRV', mvrv, mvrv_score))
    
    if sth_mvrv is not None:
        sth_mvrv_score = np.clip((sth_mvrv - 1) / 0.5, -1, 1)
        scores.append(sth_mvrv_score * 2.0)
        score_details.append(('STH-MVRV', sth_mvrv, sth_mvrv_score))
    
    if sopr is not None:
        sopr_score = np.clip((sopr - 1) / 0.1, -1, 1)
        scores.append(sopr_score * 1.0)
        score_details.append(('SOPR', sopr, sopr_score))
    
    if sth_sopr is not None:
        sth_sopr_score = np.clip((sth_sopr - 1) / 0.05, -1, 1)
        scores.append(sth_sopr_score * 1.5)
        score_details.append(('STH-SOPR', sth_sopr, sth_sopr_score))
    
    if lth_sopr is not None:
        lth_sopr_score = np.clip((lth_sopr - 1) / 0.5, -1, 1)
        scores.append(lth_sopr_score * 1.0)
        score_details.append(('LTH-SOPR', lth_sopr, lth_sopr_score))
    
    if nupl is not None:
        nupl_score = np.clip((nupl - 0.4) / 0.4, -1, 1)
        scores.append(nupl_score * 1.2)
        score_details.append(('NUPL', nupl, nupl_score))
    
    if puell is not None:
        puell_score = np.clip((puell - 1) / 1, -1, 1)
        scores.append(puell_score * 1.0)
        score_details.append(('Puell', puell, puell_score))
    
    if sell_side_risk is not None:
        ssr_score = np.clip((sell_side_risk - 0.1) / 0.3, -1, 1)
        scores.append(ssr_score * 0.5)
        score_details.append(('Sell-Risk', sell_side_risk, ssr_score))
    
    if scores:
        total_weight = 1.5 + 2.0 + 1.0 + 1.5 + 1.0 + 1.2 + 1.0 + 0.5
        composite = sum(scores) / (total_weight / len(scores))
        composite = np.clip(composite, -1, 1)
    else:
        composite = 0
    
    if composite <= -0.5:
        zone, zone_color = 'STRONG ACCUMULATE', '#22c55e'
        position_size = 1.5
    elif composite <= -0.2:
        zone, zone_color = 'ACCUMULATE', '#4ade80'
        position_size = 1.25
    elif composite <= 0.2:
        zone, zone_color = 'NEUTRAL', '#6b7280'
        position_size = 1.0
    elif composite <= 0.5:
        zone, zone_color = 'DISTRIBUTE', '#fbbf24'
        position_size = 0.5
    else:
        zone, zone_color = 'STRONG DISTRIBUTE', '#ef4444'
        position_size = 0.25
    
    return {
        'composite': composite,
        'zone': zone,
        'zone_color': zone_color,
        'position_size': position_size,
        'metrics': metrics,
        'score_details': score_details,
    }

def calculate_supply_metrics(data: dict) -> dict:
    """Calculate supply distribution metrics (James Check framework)."""
    metrics = {}
    
    # Raw values
    lth_val, _ = get_latest(data.get('supply_lth', pd.DataFrame()))
    sth_val, _ = get_latest(data.get('supply_sth', pd.DataFrame()))
    total_val, _ = get_latest(data.get('supply_total', pd.DataFrame()))
    profit_val, _ = get_latest(data.get('supply_in_profit', pd.DataFrame()))
    loss_val, _ = get_latest(data.get('supply_in_loss', pd.DataFrame()))
    
    metrics['supply_lth'] = lth_val
    metrics['supply_sth'] = sth_val
    metrics['supply_total'] = total_val
    
    # Percentages
    if lth_val and total_val and total_val > 0:
        metrics['lth_pct'] = (lth_val / total_val) * 100
    else:
        metrics['lth_pct'] = None
    
    if sth_val and total_val and total_val > 0:
        metrics['sth_pct'] = (sth_val / total_val) * 100
    else:
        metrics['sth_pct'] = None
    
    # LTH/STH Ratio
    if lth_val and sth_val and sth_val > 0:
        metrics['lth_sth_ratio'] = lth_val / sth_val
    else:
        metrics['lth_sth_ratio'] = None
    
    # Supply in Profit/Loss percentages
    if profit_val and total_val and total_val > 0:
        metrics['profit_pct'] = (profit_val / total_val) * 100
    else:
        metrics['profit_pct'] = None
    
    if loss_val and total_val and total_val > 0:
        metrics['loss_pct'] = (loss_val / total_val) * 100
    else:
        metrics['loss_pct'] = None
    
    # 30d change in LTH/STH ratio (accumulation trend)
    lth_df = data.get('supply_lth', pd.DataFrame())
    sth_df = data.get('supply_sth', pd.DataFrame())
    if not lth_df.empty and not sth_df.empty and len(lth_df) >= 30 and len(sth_df) >= 30:
        lth_30d_ago = lth_df.iloc[-30]['value']
        sth_30d_ago = sth_df.iloc[-30]['value']
        if lth_30d_ago and sth_30d_ago and sth_30d_ago > 0:
            ratio_30d_ago = lth_30d_ago / sth_30d_ago
            if metrics['lth_sth_ratio'] and ratio_30d_ago:
                metrics['ratio_change_30d'] = ((metrics['lth_sth_ratio'] - ratio_30d_ago) / ratio_30d_ago) * 100
            else:
                metrics['ratio_change_30d'] = None
        else:
            metrics['ratio_change_30d'] = None
    else:
        metrics['ratio_change_30d'] = None
    
    # 90d change for longer-term trend
    if not lth_df.empty and not sth_df.empty and len(lth_df) >= 90 and len(sth_df) >= 90:
        lth_90d_ago = lth_df.iloc[-90]['value']
        sth_90d_ago = sth_df.iloc[-90]['value']
        if lth_90d_ago and sth_90d_ago and sth_90d_ago > 0:
            ratio_90d_ago = lth_90d_ago / sth_90d_ago
            if metrics['lth_sth_ratio'] and ratio_90d_ago:
                metrics['ratio_change_90d'] = ((metrics['lth_sth_ratio'] - ratio_90d_ago) / ratio_90d_ago) * 100
            else:
                metrics['ratio_change_90d'] = None
        else:
            metrics['ratio_change_90d'] = None
    else:
        metrics['ratio_change_90d'] = None
    
    # Determine phase based on ratio changes
    r30 = metrics.get('ratio_change_30d')
    r90 = metrics.get('ratio_change_90d')
    if r30 is not None and r90 is not None:
        if r30 > 1 and r90 > 2:
            metrics['phase'] = 'STRONG ACCUMULATION'
            metrics['phase_color'] = '#22c55e'
        elif r30 > 0:
            metrics['phase'] = 'ACCUMULATION'
            metrics['phase_color'] = '#4ade80'
        elif r30 < -1 and r90 < -2:
            metrics['phase'] = 'HEAVY DISTRIBUTION'
            metrics['phase_color'] = '#ef4444'
        elif r30 < 0:
            metrics['phase'] = 'DISTRIBUTION'
            metrics['phase_color'] = '#fbbf24'
        else:
            metrics['phase'] = 'NEUTRAL'
            metrics['phase_color'] = '#6b7280'
    elif r30 is not None:
        if r30 > 1:
            metrics['phase'] = 'ACCUMULATION'
            metrics['phase_color'] = '#4ade80'
        elif r30 < -1:
            metrics['phase'] = 'DISTRIBUTION'
            metrics['phase_color'] = '#fbbf24'
        else:
            metrics['phase'] = 'NEUTRAL'
            metrics['phase_color'] = '#6b7280'
    else:
        metrics['phase'] = 'UNKNOWN'
        metrics['phase_color'] = '#6b7280'
    
    return metrics


def calculate_liveliness_metrics(data: dict) -> dict:
    """Calculate liveliness/activity metrics (James Check framework).
    
    Liveliness = Coindays Destroyed / Coindays Created
    - High liveliness (>0.6): Old coins moving, potential distribution
    - Low liveliness (<0.4): Coins dormant, accumulation phase
    
    Vaultedness = 1 - Liveliness
    - How much of the supply is "vaulted" (not moving)
    """
    metrics = {}
    
    # Liveliness
    liveliness, _ = get_latest(data.get('liveliness', pd.DataFrame()))
    metrics['liveliness'] = liveliness
    
    # Vaultedness (inverse of liveliness)
    if liveliness is not None:
        metrics['vaultedness'] = 1 - liveliness
    else:
        metrics['vaultedness'] = None
    
    # Coindays Destroyed (CDD)
    cdd, _ = get_latest(data.get('coindays_destroyed', pd.DataFrame()))
    metrics['cdd'] = cdd
    
    # CDD 90-day average for context
    cdd_df = data.get('coindays_destroyed', pd.DataFrame())
    if not cdd_df.empty and len(cdd_df) >= 90:
        metrics['cdd_90d_avg'] = cdd_df.tail(90)['value'].mean()
        if cdd and metrics['cdd_90d_avg'] and metrics['cdd_90d_avg'] > 0:
            metrics['cdd_vs_avg'] = (cdd / metrics['cdd_90d_avg'] - 1) * 100
        else:
            metrics['cdd_vs_avg'] = None
    else:
        metrics['cdd_90d_avg'] = None
        metrics['cdd_vs_avg'] = None
    
    # Liveliness trend (30d change)
    liveliness_df = data.get('liveliness', pd.DataFrame())
    if not liveliness_df.empty and len(liveliness_df) >= 30:
        liveliness_30d_ago = liveliness_df.iloc[-30]['value']
        if liveliness and liveliness_30d_ago:
            metrics['liveliness_change_30d'] = (liveliness - liveliness_30d_ago) * 100  # In percentage points
        else:
            metrics['liveliness_change_30d'] = None
    else:
        metrics['liveliness_change_30d'] = None
    
    # Determine activity state
    if liveliness is not None:
        if liveliness > 0.65:
            metrics['state'] = 'HIGH ACTIVITY'
            metrics['state_color'] = '#ef4444'
            metrics['interpretation'] = 'Old coins moving - potential top'
        elif liveliness > 0.55:
            metrics['state'] = 'ELEVATED'
            metrics['state_color'] = '#fbbf24'
            metrics['interpretation'] = 'Above average activity'
        elif liveliness > 0.45:
            metrics['state'] = 'NORMAL'
            metrics['state_color'] = '#6b7280'
            metrics['interpretation'] = 'Typical activity levels'
        elif liveliness > 0.35:
            metrics['state'] = 'LOW ACTIVITY'
            metrics['state_color'] = '#4ade80'
            metrics['interpretation'] = 'Coins dormant - accumulation'
        else:
            metrics['state'] = 'DEEP DORMANCY'
            metrics['state_color'] = '#22c55e'
            metrics['interpretation'] = 'Extreme HODLing - cycle bottom'
    else:
        metrics['state'] = 'UNKNOWN'
        metrics['state_color'] = '#6b7280'
        metrics['interpretation'] = 'No data'
    
    return metrics


def calculate_buy_the_dip(data: dict) -> dict:
    """Calculate James Check's Buy-The-Dip checklist.
    
    The 5 conditions:
    1. STH-MVRV < 1.0 - Short-term holders stressed (underwater)
    2. STH-SOPR < 1.0 - Local top buyers capitulating (selling at loss)
    3. STH-RPLR < 1.0 - More realized losses than profits (STH cohort)
    4. Futures funding rates cooled off or negative
    5. Long liquidations peaked, followed by short squeeze
    
    Note: Conditions 4 & 5 require derivatives data (not available from Bitcoin Lab API).
    These are marked as manual checks.
    """
    metrics = {}
    conditions = []
    
    # Condition 1: STH-MVRV < 1.0
    sth_mvrv, _ = get_latest(data.get('mvrv_sth', pd.DataFrame()))
    metrics['sth_mvrv'] = sth_mvrv
    if sth_mvrv is not None:
        cond1 = sth_mvrv < 1.0
        conditions.append({
            'id': 'sth_mvrv',
            'name': 'STH-MVRV < 1.0',
            'description': 'Short-term holders stressed',
            'value': sth_mvrv,
            'threshold': 1.0,
            'triggered': cond1,
            'available': True
        })
    else:
        conditions.append({
            'id': 'sth_mvrv',
            'name': 'STH-MVRV < 1.0',
            'description': 'Short-term holders stressed',
            'value': None,
            'threshold': 1.0,
            'triggered': False,
            'available': False
        })
    
    # Condition 2: STH-SOPR < 1.0
    sth_sopr, _ = get_latest(data.get('sopr_sth', pd.DataFrame()))
    metrics['sth_sopr'] = sth_sopr
    if sth_sopr is not None:
        cond2 = sth_sopr < 1.0
        conditions.append({
            'id': 'sth_sopr',
            'name': 'STH-SOPR < 1.0',
            'description': 'Local top buyers capitulating',
            'value': sth_sopr,
            'threshold': 1.0,
            'triggered': cond2,
            'available': True
        })
    else:
        conditions.append({
            'id': 'sth_sopr',
            'name': 'STH-SOPR < 1.0',
            'description': 'Local top buyers capitulating',
            'value': None,
            'threshold': 1.0,
            'triggered': False,
            'available': False
        })
    
    # Condition 3: STH-RPLR < 1.0 (Realized Profit/Loss Ratio)
    # Using market-wide realized profit/loss as proxy (STH-specific not available in BRK)
    realized_profit, _ = get_latest(data.get('realized_profit', pd.DataFrame()))
    realized_loss, _ = get_latest(data.get('realized_loss', pd.DataFrame()))
    
    if realized_profit and realized_loss and realized_loss > 0:
        rplr = realized_profit / realized_loss
        metrics['rplr'] = rplr
        metrics['realized_profit'] = realized_profit
        metrics['realized_loss'] = realized_loss
        cond3 = rplr < 1.0
        conditions.append({
            'id': 'rplr',
            'name': 'RPLR < 1.0',
            'description': 'More losses than profits realized',
            'value': rplr,
            'threshold': 1.0,
            'triggered': cond3,
            'available': True
        })
    else:
        metrics['rplr'] = None
        conditions.append({
            'id': 'rplr',
            'name': 'RPLR < 1.0',
            'description': 'More losses than profits realized',
            'value': None,
            'threshold': 1.0,
            'triggered': False,
            'available': False
        })
    
    # Fetch derivatives data from Glassnode
    print("  Fetching Glassnode derivatives data...")
    derivatives = get_glassnode_derivatives()
    metrics['derivatives'] = derivatives
    
    # Condition 4: Futures funding rates cooled off or negative
    if derivatives.get('available') and derivatives.get('funding_rate') is not None:
        funding_rate = derivatives['funding_rate']
        # Convert to percentage for display (funding rates are typically very small decimals)
        funding_pct = funding_rate * 100
        cond4 = funding_rate <= 0
        conditions.append({
            'id': 'funding_rates',
            'name': 'Funding Rates ≤ 0',
            'description': 'Derivatives cooling off',
            'value': funding_pct,
            'value_fmt': f"{funding_pct:.4f}%",
            'threshold': 0.0,
            'triggered': cond4,
            'available': True,
            'source': 'Glassnode'
        })
    else:
        conditions.append({
            'id': 'funding_rates',
            'name': 'Funding Rates ≤ 0',
            'description': 'Derivatives cooling off',
            'value': None,
            'threshold': 0.0,
            'triggered': False,
            'available': False,
            'manual': True,
            'manual_source': 'Glassnode API unavailable'
        })
    
    # Condition 5: Long liquidations peaked, followed by short squeeze
    # Logic: Long liq > Short liq AND long liq elevated = longs getting rekt = dip happening
    if derivatives.get('long_liquidations') is not None and derivatives.get('short_liquidations') is not None:
        long_liq = derivatives['long_liquidations']
        short_liq = derivatives['short_liquidations']
        liq_ratio = derivatives.get('liquidation_ratio', 0)
        
        # Condition is MET when:
        # - Long liquidations significantly exceed short liquidations (ratio > 2)
        # - This indicates longs are being flushed out (dip/correction)
        cond5 = liq_ratio > 2.0 if liq_ratio else False
        
        # Format for display
        long_liq_m = long_liq / 1_000_000  # Convert to millions
        short_liq_m = short_liq / 1_000_000
        
        conditions.append({
            'id': 'liquidations',
            'name': 'Long Liq > Short Liq',
            'description': f'Longs: ${long_liq_m:.1f}M / Shorts: ${short_liq_m:.1f}M',
            'value': liq_ratio,
            'value_fmt': f"{liq_ratio:.2f}x" if liq_ratio else 'N/A',
            'threshold': 2.0,
            'triggered': cond5,
            'available': True,
            'source': 'Glassnode'
        })
    else:
        conditions.append({
            'id': 'liquidations',
            'name': 'Long Liq > Short Liq',
            'description': 'Liquidation data',
            'value': None,
            'threshold': 2.0,
            'triggered': False,
            'available': False,
            'manual': True,
            'manual_source': 'Glassnode API unavailable'
        })
    
    metrics['conditions'] = conditions
    
    # Count triggered conditions
    # On-chain conditions (first 3)
    onchain_triggered = sum(1 for c in conditions[:3] if c.get('triggered', False))
    onchain_available = sum(1 for c in conditions[:3] if c.get('available', False))
    
    # Derivatives conditions (last 2)
    derivatives_triggered = sum(1 for c in conditions[3:5] if c.get('triggered', False))
    derivatives_available = sum(1 for c in conditions[3:5] if c.get('available', False))
    
    # Total
    total_triggered = onchain_triggered + derivatives_triggered
    total_available = onchain_available + derivatives_available
    
    metrics['onchain_triggered'] = onchain_triggered
    metrics['onchain_available'] = onchain_available
    metrics['onchain_pct'] = (onchain_triggered / onchain_available * 100) if onchain_available > 0 else 0
    metrics['derivatives_triggered'] = derivatives_triggered
    metrics['derivatives_available'] = derivatives_available
    metrics['total_triggered'] = total_triggered
    metrics['total_available'] = total_available
    
    # Determine overall signal based on ALL available conditions
    # Strong signal requires on-chain + derivatives confirmation
    if total_triggered >= 4:
        metrics['signal'] = 'STRONG DIP'
        metrics['signal_color'] = '#22c55e'
        metrics['signal_desc'] = f'{total_triggered}/{total_available} conditions met - high conviction'
    elif total_triggered >= 3 or (onchain_triggered >= 2 and derivatives_triggered >= 1):
        metrics['signal'] = 'BUY THE DIP'
        metrics['signal_color'] = '#4ade80'
        metrics['signal_desc'] = f'{total_triggered}/{total_available} conditions met - confirmed dip'
    elif onchain_triggered >= 2:
        metrics['signal'] = 'ON-CHAIN DIP'
        metrics['signal_color'] = '#4ade80'
        metrics['signal_desc'] = f'On-chain stress ({onchain_triggered}/3) - watch derivatives'
    elif total_triggered >= 1:
        metrics['signal'] = 'WATCH'
        metrics['signal_color'] = '#fbbf24'
        metrics['signal_desc'] = f'{total_triggered}/{total_available} conditions - wait for more'
    else:
        metrics['signal'] = 'NO DIP'
        metrics['signal_color'] = '#6b7280'
        metrics['signal_desc'] = 'No stress signals - not a dip'
    
    return metrics


def calculate_miner_metrics(data: dict) -> dict:
    """Calculate miner health metrics (James Check framework).
    
    Puell Multiple = Daily Miner Revenue / 365-day MA of Revenue
    - < 0.5: Miners under stress, potential capitulation (buy zone)
    - 0.5-1.0: Healthy but cautious
    - 1.0-2.0: Profitable mining
    - > 2.0: Excessive profitability (potential top)
    - > 4.0: Extreme - historical tops
    """
    metrics = {}
    
    # Puell Multiple
    puell, _ = get_latest(data.get('puell_multiple', pd.DataFrame()))
    metrics['puell'] = puell
    
    # Difficulty
    difficulty, _ = get_latest(data.get('difficulty', pd.DataFrame()))
    metrics['difficulty'] = difficulty
    
    # Thermocap (cumulative miner revenue)
    thermo_cap, _ = get_latest(data.get('thermo_cap', pd.DataFrame()))
    metrics['thermo_cap'] = thermo_cap
    
    # Difficulty change (30d)
    diff_df = data.get('difficulty', pd.DataFrame())
    if not diff_df.empty and len(diff_df) >= 30:
        diff_30d_ago = diff_df.iloc[-30]['value']
        if difficulty and diff_30d_ago and diff_30d_ago > 0:
            metrics['difficulty_change_30d'] = ((difficulty - diff_30d_ago) / diff_30d_ago) * 100
        else:
            metrics['difficulty_change_30d'] = None
    else:
        metrics['difficulty_change_30d'] = None
    
    # Puell trend
    puell_df = data.get('puell_multiple', pd.DataFrame())
    if not puell_df.empty and len(puell_df) >= 30:
        puell_30d_ago = puell_df.iloc[-30]['value']
        if puell and puell_30d_ago:
            metrics['puell_change_30d'] = puell - puell_30d_ago
        else:
            metrics['puell_change_30d'] = None
    else:
        metrics['puell_change_30d'] = None
    
    # Determine miner health state
    if puell is not None:
        if puell < 0.5:
            metrics['state'] = 'CAPITULATION'
            metrics['state_color'] = '#22c55e'
            metrics['interpretation'] = 'Miners stressed - buy zone'
        elif puell < 1.0:
            metrics['state'] = 'RECOVERY'
            metrics['state_color'] = '#4ade80'
            metrics['interpretation'] = 'Miners recovering'
        elif puell < 2.0:
            metrics['state'] = 'HEALTHY'
            metrics['state_color'] = '#6b7280'
            metrics['interpretation'] = 'Normal profitability'
        elif puell < 4.0:
            metrics['state'] = 'ELEVATED'
            metrics['state_color'] = '#fbbf24'
            metrics['interpretation'] = 'High profitability - caution'
        else:
            metrics['state'] = 'EXTREME'
            metrics['state_color'] = '#ef4444'
            metrics['interpretation'] = 'Euphoric - potential top'
    else:
        metrics['state'] = 'UNKNOWN'
        metrics['state_color'] = '#6b7280'
        metrics['interpretation'] = 'No data'
    
    return metrics


def calculate_profitability_metrics(data: dict) -> dict:
    """Calculate profitability metrics (James Check framework).
    
    NUPL = Net Unrealized Profit/Loss
    - < 0: Market in loss (capitulation zone)
    - 0-0.25: Hope/Fear
    - 0.25-0.5: Optimism/Anxiety  
    - 0.5-0.75: Belief/Denial
    - > 0.75: Euphoria/Greed (distribution zone)
    
    Supply in Profit %
    - < 50%: More holders underwater (buy zone)
    - 50-75%: Healthy market
    - > 95%: Everyone in profit (distribution risk)
    
    STH vs LTH Unrealized P/L
    - When STH underwater but LTH in profit: typical correction
    - When both underwater: deep bear (generational buy)
    - When both highly profitable: distribution risk
    """
    metrics = {}
    
    # NUPL (normalize if needed)
    nupl, _ = get_latest(data.get('nupl', pd.DataFrame()))
    if nupl is not None and nupl > 10:
        market_cap, _ = get_latest(data.get('market_cap', pd.DataFrame()))
        if market_cap and market_cap > 0:
            nupl = nupl / market_cap
    metrics['nupl'] = nupl
    
    # LTH NUPL
    nupl_lth, _ = get_latest(data.get('nupl_lth', pd.DataFrame()))
    if nupl_lth is not None and nupl_lth > 10:
        market_cap, _ = get_latest(data.get('market_cap', pd.DataFrame()))
        if market_cap and market_cap > 0:
            nupl_lth = nupl_lth / market_cap
    metrics['nupl_lth'] = nupl_lth
    
    # STH NUPL
    nupl_sth, _ = get_latest(data.get('nupl_sth', pd.DataFrame()))
    if nupl_sth is not None and nupl_sth > 10:
        market_cap, _ = get_latest(data.get('market_cap', pd.DataFrame()))
        if market_cap and market_cap > 0:
            nupl_sth = nupl_sth / market_cap
    metrics['nupl_sth'] = nupl_sth
    
    # Supply in Profit/Loss
    supply_profit, _ = get_latest(data.get('supply_in_profit', pd.DataFrame()))
    supply_loss, _ = get_latest(data.get('supply_in_loss', pd.DataFrame()))
    total_supply, _ = get_latest(data.get('supply_total', pd.DataFrame()))
    
    if supply_profit and total_supply and total_supply > 0:
        metrics['supply_profit_pct'] = (supply_profit / total_supply) * 100
    else:
        metrics['supply_profit_pct'] = None
    
    if supply_loss and total_supply and total_supply > 0:
        metrics['supply_loss_pct'] = (supply_loss / total_supply) * 100
    else:
        metrics['supply_loss_pct'] = None
    
    # Unrealized Profit/Loss (absolute values)
    unrealized_profit, _ = get_latest(data.get('unrealized_profit', pd.DataFrame()))
    unrealized_loss, _ = get_latest(data.get('unrealized_loss', pd.DataFrame()))
    metrics['unrealized_profit'] = unrealized_profit
    metrics['unrealized_loss'] = unrealized_loss
    
    # Profit/Loss Ratio
    if unrealized_profit and unrealized_loss and unrealized_loss > 0:
        metrics['profit_loss_ratio'] = unrealized_profit / unrealized_loss
    else:
        metrics['profit_loss_ratio'] = None
    
    # NUPL historical percentile (where are we in history?)
    nupl_df = data.get('nupl', pd.DataFrame())
    if not nupl_df.empty and nupl is not None:
        # Normalize historical NUPL if needed
        historical_nupl = nupl_df['value'].copy()
        if historical_nupl.max() > 10:  # Needs normalization
            mc_df = data.get('market_cap', pd.DataFrame())
            if not mc_df.empty:
                # Simple approximation: normalize by latest market cap
                mc_latest, _ = get_latest(mc_df)
                if mc_latest and mc_latest > 0:
                    historical_nupl = historical_nupl / mc_latest
        metrics['nupl_percentile'] = (historical_nupl < nupl).mean() * 100
    else:
        metrics['nupl_percentile'] = None
    
    # STH vs LTH cohort analysis
    if nupl_sth is not None and nupl_lth is not None:
        # Determine cohort divergence state
        if nupl_sth < 0 and nupl_lth < 0:
            metrics['cohort_state'] = 'BOTH UNDERWATER'
            metrics['cohort_color'] = '#22c55e'
            metrics['cohort_desc'] = 'Deep bear - generational opportunity'
        elif nupl_sth < 0 and nupl_lth > 0:
            metrics['cohort_state'] = 'STH PAIN'
            metrics['cohort_color'] = '#4ade80'
            metrics['cohort_desc'] = 'Typical correction - STH capitulating'
        elif nupl_sth > 0.5 and nupl_lth > 0.5:
            metrics['cohort_state'] = 'BOTH EUPHORIC'
            metrics['cohort_color'] = '#ef4444'
            metrics['cohort_desc'] = 'Distribution risk - take profits'
        elif nupl_sth > 0.3 and nupl_lth > 0.3:
            metrics['cohort_state'] = 'BOTH PROFITABLE'
            metrics['cohort_color'] = '#fbbf24'
            metrics['cohort_desc'] = 'Bull market - manage risk'
        else:
            metrics['cohort_state'] = 'MIXED'
            metrics['cohort_color'] = '#6b7280'
            metrics['cohort_desc'] = 'No clear signal'
    else:
        metrics['cohort_state'] = 'UNKNOWN'
        metrics['cohort_color'] = '#6b7280'
        metrics['cohort_desc'] = 'Insufficient data'
    
    # Determine market emotion based on NUPL (James Check's emotion cycle)
    if nupl is not None:
        if nupl < 0:
            metrics['emotion'] = 'CAPITULATION'
            metrics['emotion_color'] = '#22c55e'
            metrics['emotion_emoji'] = '😱'
            metrics['emotion_desc'] = 'Max pain - generational buy'
        elif nupl < 0.25:
            metrics['emotion'] = 'HOPE/FEAR'
            metrics['emotion_color'] = '#4ade80'
            metrics['emotion_emoji'] = '😰'
            metrics['emotion_desc'] = 'Recovery beginning - accumulate'
        elif nupl < 0.5:
            metrics['emotion'] = 'OPTIMISM'
            metrics['emotion_color'] = '#3b82f6'
            metrics['emotion_emoji'] = '😊'
            metrics['emotion_desc'] = 'Healthy bull market'
        elif nupl < 0.75:
            metrics['emotion'] = 'BELIEF'
            metrics['emotion_color'] = '#fbbf24'
            metrics['emotion_emoji'] = '🤑'
            metrics['emotion_desc'] = 'Getting greedy - reduce risk'
        else:
            metrics['emotion'] = 'EUPHORIA'
            metrics['emotion_color'] = '#ef4444'
            metrics['emotion_emoji'] = '🚀'
            metrics['emotion_desc'] = 'Max greed - take profits'
    else:
        metrics['emotion'] = 'UNKNOWN'
        metrics['emotion_color'] = '#6b7280'
        metrics['emotion_emoji'] = '❓'
        metrics['emotion_desc'] = 'No data'
    
    # NUPL position for visualization (0-100%)
    if nupl is not None:
        # Map NUPL from -0.5 to 1.0 range to 0-100%
        metrics['nupl_position'] = max(0, min(100, (nupl + 0.5) / 1.5 * 100))
    else:
        metrics['nupl_position'] = 50
    
    # STH and LTH NUPL positions for cohort comparison bar
    if nupl_sth is not None:
        metrics['sth_nupl_position'] = max(0, min(100, (nupl_sth + 0.5) / 1.5 * 100))
    else:
        metrics['sth_nupl_position'] = 50
    
    if nupl_lth is not None:
        metrics['lth_nupl_position'] = max(0, min(100, (nupl_lth + 0.5) / 1.5 * 100))
    else:
        metrics['lth_nupl_position'] = 50
    
    return metrics

def calculate_signals(context: dict, signals: dict, sopr_metrics: dict, supply_metrics: dict, momentum_metrics: dict, liveliness_metrics: dict = None, miner_metrics: dict = None, profitability_metrics: dict = None) -> dict:
    section_signals = {}
    liveliness_metrics = liveliness_metrics or {}
    miner_metrics = miner_metrics or {}
    profitability_metrics = profitability_metrics or {}
    
    zone = context['price_zone']['zone']
    if zone in ['EXTREME BEAR', 'UNDERVALUED']:
        section_signals['price'] = ('BUY', '#22c55e')
    elif zone in ['OVERVALUED', 'EXTREME BULL']:
        section_signals['price'] = ('SELL', '#ef4444')
    else:
        section_signals['price'] = ('HOLD', '#fbbf24')
    
    section_signals['valuation'] = section_signals['price']
    
    entry_triggered = signals['groups'].get('strat_002_004_entry', {}).get('triggered', False)
    if entry_triggered:
        section_signals['entry'] = ('BUY', '#22c55e')
    else:
        section_signals['entry'] = ('NO BUY', '#6b7280')
    
    exit_count = sum(1 for s in signals['exit'].values() if s.get('triggered', False))
    if exit_count >= 2:
        section_signals['exit'] = ('SELL', '#ef4444')
    elif exit_count >= 1:
        section_signals['exit'] = ('CAUTION', '#fbbf24')
    else:
        section_signals['exit'] = ('NO SELL', '#6b7280')
    
    mvrv_zone = context['mvrv_z']['zone']
    if mvrv_zone == 'DEEP VALUE':
        section_signals['cycle'] = ('BUY', '#22c55e')
    elif mvrv_zone == 'EUPHORIA':
        section_signals['cycle'] = ('SELL', '#ef4444')
    elif mvrv_zone == 'EXPENSIVE':
        section_signals['cycle'] = ('CAUTION', '#fbbf24')
    else:
        section_signals['cycle'] = ('HOLD', '#fbbf24')
    
    # Spending behavior signal (from SOPR sentiment)
    spending_sentiment = sopr_metrics.get('sentiment', 'UNKNOWN')
    if spending_sentiment == 'CAPITULATION':
        section_signals['sopr'] = ('BUY', '#22c55e')
    elif spending_sentiment == 'LOSS-TAKING':
        section_signals['sopr'] = ('ACCUMULATE', '#4ade80')
    elif spending_sentiment == 'DISTRIBUTION':
        section_signals['sopr'] = ('SELL', '#ef4444')
    elif spending_sentiment == 'PROFIT-TAKING':
        section_signals['sopr'] = ('CAUTION', '#fbbf24')
    else:
        section_signals['sopr'] = ('HOLD', '#fbbf24')
    
    ratio_change = supply_metrics.get('ratio_change_30d')
    if ratio_change is not None:
        if ratio_change > 2:
            section_signals['supply'] = ('BUY', '#22c55e')
        elif ratio_change < -2:
            section_signals['supply'] = ('SELL', '#ef4444')
        else:
            section_signals['supply'] = ('HOLD', '#fbbf24')
    else:
        section_signals['supply'] = ('HOLD', '#fbbf24')
    
    # Liveliness signal
    liveliness_state = liveliness_metrics.get('state', 'UNKNOWN')
    if liveliness_state in ['DEEP DORMANCY', 'LOW ACTIVITY']:
        section_signals['liveliness'] = ('BUY', '#22c55e')
    elif liveliness_state == 'HIGH ACTIVITY':
        section_signals['liveliness'] = ('SELL', '#ef4444')
    elif liveliness_state == 'ELEVATED':
        section_signals['liveliness'] = ('CAUTION', '#fbbf24')
    else:
        section_signals['liveliness'] = ('HOLD', '#fbbf24')
    
    # Miner signal
    miner_state = miner_metrics.get('state', 'UNKNOWN')
    if miner_state == 'CAPITULATION':
        section_signals['miner'] = ('BUY', '#22c55e')
    elif miner_state == 'RECOVERY':
        section_signals['miner'] = ('ACCUMULATE', '#4ade80')
    elif miner_state in ['ELEVATED', 'EXTREME']:
        section_signals['miner'] = ('CAUTION', '#fbbf24')
    else:
        section_signals['miner'] = ('HOLD', '#fbbf24')
    
    # Profitability signal
    emotion = profitability_metrics.get('emotion', 'UNKNOWN')
    if emotion == 'CAPITULATION':
        section_signals['profitability'] = ('BUY', '#22c55e')
    elif emotion == 'HOPE/FEAR':
        section_signals['profitability'] = ('ACCUMULATE', '#4ade80')
    elif emotion in ['BELIEF', 'EUPHORIA']:
        section_signals['profitability'] = ('CAUTION', '#fbbf24')
    else:
        section_signals['profitability'] = ('HOLD', '#fbbf24')
    
    trend = momentum_metrics.get('trend', 'UNKNOWN')
    if trend in ['STRONG UPTREND', 'UPTREND']:
        section_signals['momentum'] = ('BUY', '#22c55e')
    elif trend in ['STRONG DOWNTREND', 'DOWNTREND']:
        section_signals['momentum'] = ('SELL', '#ef4444')
    else:
        section_signals['momentum'] = ('HOLD', '#fbbf24')
    
    return section_signals

def calculate_momentum_metrics(data: dict) -> dict:
    metrics = {}
    
    price_df = data.get('price', pd.DataFrame())
    if price_df.empty:
        return {'ma_50': None, 'ma_200': None, 'price': None, 'trend': 'UNKNOWN', 'trend_color': '#6b7280'}
    
    price_val, _ = get_latest(price_df)
    metrics['price'] = price_val
    
    if len(price_df) >= 50:
        metrics['ma_50'] = price_df.tail(50)['value'].mean()
    else:
        metrics['ma_50'] = None
    
    if len(price_df) >= 200:
        metrics['ma_200'] = price_df.tail(200)['value'].mean()
    else:
        metrics['ma_200'] = None
    
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
    
    if price_val and metrics['ma_50']:
        metrics['price_vs_ma50'] = ((price_val - metrics['ma_50']) / metrics['ma_50']) * 100
    else:
        metrics['price_vs_ma50'] = None
    
    if price_val and metrics['ma_200']:
        metrics['price_vs_ma200'] = ((price_val - metrics['ma_200']) / metrics['ma_200']) * 100
    else:
        metrics['price_vs_ma200'] = None
    
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

def generate_html(signals: dict, context: dict, sopr_metrics: dict, confluence: dict, data_freshness: str, supply_metrics: dict = None, momentum_metrics: dict = None, section_signals: dict = None, checkmate: dict = None, liveliness_metrics: dict = None, miner_metrics: dict = None, profitability_metrics: dict = None, buy_the_dip: dict = None) -> str:
    import json
    
    supply_metrics = supply_metrics or {}
    momentum_metrics = momentum_metrics or {}
    section_signals = section_signals or {}
    checkmate = checkmate or {'composite': 0, 'zone': 'UNKNOWN', 'zone_color': '#6b7280', 'position_size': 1.0, 'score_details': []}
    liveliness_metrics = liveliness_metrics or {}
    miner_metrics = miner_metrics or {}
    profitability_metrics = profitability_metrics or {}
    buy_the_dip = buy_the_dip or {'signal': 'UNKNOWN', 'signal_color': '#6b7280', 'conditions': [], 'onchain_triggered': 0, 'onchain_available': 0}
    def fmt(val, d=4): return f"{val:,.{d}f}" if val is not None else 'N/A'
    def fmt_price(val): return f"${val:,.0f}" if val is not None else 'N/A'
    
    ts = context['price']['time']
    ts_str = ts.strftime('%Y-%m-%d') if ts else 'Unknown'
    
    entry_on = signals['groups'].get('strat_002_004_entry', {}).get('triggered', False)
    exit_on = signals['groups'].get('distribution_exit', {}).get('triggered', False)
    
    levels_json = {
        'realized_price': context['price_levels'].get('realized_price'),
        'true_market_mean': context['price_levels'].get('true_market_mean'),
        'sth_realized_price': context['price_levels'].get('sth_realized_price'),
        'vaulted_price': context['price_levels'].get('vaulted_price'),
    }
    levels_str = json.dumps(levels_json)
    
    # Get current action for valuation
    val_action = section_signals.get('valuation', ('HOLD', '#fbbf24'))
    action_class = 'buy' if val_action[0] == 'BUY' else ('sell' if val_action[0] == 'SELL' else 'hold')
    
    # Get price level values for display
    rp = context['price_levels'].get('realized_price', 0)
    tmm = context['price_levels'].get('true_market_mean', 0)
    sth = context['price_levels'].get('sth_realized_price', 0)
    vp = context['price_levels'].get('vaulted_price', 0)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitcoin Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 1800px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 24px; }}
        .header h1 {{ font-size: 24px; font-weight: 700; color: #f8fafc; }}
        .header .sub {{ color: #64748b; font-size: 13px; margin-top: 4px; }}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 18px; border: 1px solid #334155; }}
        .card.wide {{ grid-column: span 2; }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid #334155; }}
        .card-title {{ font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
        .card-title.blue {{ color: #60a5fa; }} .card-title.green {{ color: #4ade80; }} .card-title.red {{ color: #f87171; }}
        .card-title.purple {{ color: #c084fc; }} .card-title.orange {{ color: #fb923c; }}
        .big-value {{ font-size: 32px; font-weight: 700; color: #f8fafc; }}
        .price-change {{ font-size: 14px; margin-left: 10px; }}
        .price-change.up {{ color: #4ade80; }} .price-change.down {{ color: #f87171; }}
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
        .sopr-bar {{ width: 100%; height: 20px; background: linear-gradient(90deg, #ef4444 0%, #6b7280 50%, #22c55e 100%); border-radius: 4px; position: relative; margin: 6px 0; }}
        .sopr-marker {{ position: absolute; top: -3px; width: 3px; height: 26px; background: #f8fafc; border-radius: 2px; transform: translateX(-50%); }}
        .sopr-center {{ position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background: #f8fafc; opacity: 0.4; }}
        /* Thermometer Styles */
        .action-badge {{ padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 700; }}
        .action-badge.hold {{ background: rgba(251, 191, 36, 0.2); color: #fbbf24; }}
        .action-badge.buy {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}
        .action-badge.sell {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
        .thermo-current {{ text-align: center; padding: 20px; border-radius: 12px; margin-bottom: 16px; }}
        .thermo-current.buy {{ background: linear-gradient(135deg, #166534, #14532d); }}
        .thermo-current.hold {{ background: linear-gradient(135deg, #78350f, #92400e); }}
        .thermo-current.sell {{ background: linear-gradient(135deg, #7f1d1d, #991b1b); }}
        .thermo-current .label {{ font-size: 11px; color: #86efac; text-transform: uppercase; margin-bottom: 4px; }}
        .thermo-current .price {{ font-size: 32px; font-weight: 700; color: #f8fafc; }}
        .thermo-current .zone {{ font-size: 14px; color: #4ade80; font-weight: 600; }}
        .thermo-bar-wrapper {{ position: relative; padding: 30px 0 10px 0; }}
        .thermo-bar {{ display: flex; height: 24px; border-radius: 6px; overflow: hidden; }}
        .thermo-marker {{ position: absolute; top: 10px; transform: translateX(-50%); }}
        .thermo-marker::before {{ content: '▼'; color: #f8fafc; font-size: 16px; }}
        .thermo-labels {{ display: flex; margin-top: 8px; }}
        .thermo-label {{ text-align: center; padding-top: 4px; border-top: 2px solid transparent; }}
        .thermo-label.active {{ border-top-color: #f8fafc; }}
        .thermo-label .name {{ font-size: 9px; color: #64748b; text-transform: uppercase; }}
        .thermo-label .lprice {{ font-size: 11px; color: #94a3b8; }}
        .thermo-label .action {{ font-size: 11px; font-weight: 700; margin-top: 2px; }}
        .thermo-label .action.buy {{ color: #4ade80; }}
        .thermo-label .action.hold {{ color: #fbbf24; }}
        .thermo-label .action.sell {{ color: #f87171; }}
        .thermo-label .mult {{ font-size: 10px; color: #64748b; }}
        .zone-bear {{ background: #ef4444; }}
        .zone-under {{ background: #f97316; }}
        .zone-fair {{ background: #22c55e; }}
        .zone-over {{ background: #fbbf24; }}
        .zone-bull {{ background: #a855f7; }}
        .footer {{ text-align: center; margin-top: 24px; padding-top: 16px; border-top: 1px solid #334155; color: #64748b; font-size: 12px; }}
        .live-dot {{ display: inline-block; width: 8px; height: 8px; background: #22c55e; border-radius: 50%; margin-right: 6px; animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
        .refresh-btn {{ position: fixed; bottom: 20px; right: 20px; background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }}
        @media (max-width: 1400px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
        @media (max-width: 800px) {{ .grid {{ grid-template-columns: 1fr; }} .card.wide {{ grid-column: span 1; }} }}
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
            
            <!-- VALUATION (2 columns) -->
            <div class="card wide">
                <div class="card-header">
                    <span class="card-title purple">Valuation</span>
                    <span class="action-badge {action_class}" id="action-badge">{val_action[0]}</span>
                </div>
                
                <div class="thermo-current {action_class}" id="thermo-current">
                    <div class="label">Current Price</div>
                    <div class="price" id="thermo-price">{fmt_price(context['price']['value'])}</div>
                    <div class="zone" id="thermo-zone">🟢 {context['price_zone']['zone']} • {val_action[0]}</div>
                </div>
                <div class="thermo-bar-wrapper">
                    <div class="thermo-marker" id="thermo-marker" style="left: 50%;"></div>
                    <div class="thermo-bar">
                        <div class="zone-bear" style="width: 15%;"></div>
                        <div class="zone-under" style="width: 20%;"></div>
                        <div class="zone-fair" style="width: 15%;"></div>
                        <div class="zone-over" style="width: 35%;"></div>
                        <div class="zone-bull" style="width: 15%;"></div>
                    </div>
                    <div class="thermo-labels">
                        <div class="thermo-label{' active' if context['price_zone']['zone'] == 'EXTREME BEAR' else ''}" data-zone="EXTREME BEAR" style="width: 15%;">
                            <div class="name">Extreme Bear</div>
                            <div class="lprice">&lt; ${int(rp/1000)}K</div>
                            <div class="action buy">BUY</div>
                            <div class="mult">(max accumulate) 2x</div>
                        </div>
                        <div class="thermo-label{' active' if context['price_zone']['zone'] == 'UNDERVALUED' else ''}" data-zone="UNDERVALUED" style="width: 20%;">
                            <div class="name">Undervalued</div>
                            <div class="lprice">${int(rp/1000)}K-${int(tmm/1000)}K</div>
                            <div class="action buy">BUY</div>
                            <div class="mult">(accumulate) 1.5x</div>
                        </div>
                        <div class="thermo-label{' active' if context['price_zone']['zone'] == 'FAIR VALUE' else ''}" data-zone="FAIR VALUE" style="width: 15%;">
                            <div class="name">Fair Value</div>
                            <div class="lprice">${int(tmm/1000)}K-${int(sth/1000)}K</div>
                            <div class="action hold">HOLD</div>
                            <div class="mult">1x</div>
                        </div>
                        <div class="thermo-label{' active' if context['price_zone']['zone'] == 'OVERVALUED' else ''}" data-zone="OVERVALUED" style="width: 35%;">
                            <div class="name">Overvalued</div>
                            <div class="lprice">${int(sth/1000)}K-${int(vp/1000)}K</div>
                            <div class="action sell">SELL</div>
                            <div class="mult">(reduce) 0.5x</div>
                        </div>
                        <div class="thermo-label{' active' if context['price_zone']['zone'] == 'EXTREME BULL' else ''}" data-zone="EXTREME BULL" style="width: 15%;">
                            <div class="name">Extreme Bull</div>
                            <div class="lprice">&gt; ${int(vp/1000)}K</div>
                            <div class="action sell">SELL</div>
                            <div class="mult">(protect gains) 0.25x</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- SPENDING BEHAVIOR -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title orange">Spending Behavior</span>
                    <span>
                        <span class="zone-badge" style="background: {sopr_metrics.get('sentiment_color', '#6b7280')}20; color: {sopr_metrics.get('sentiment_color', '#6b7280')}">{sopr_metrics.get('sentiment', 'UNKNOWN')}</span>
                        <span class="signal-badge" style="background: {section_signals.get('sopr', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('sopr', ('HOLD', '#fbbf24'))[1]}; margin-left: 8px;">{section_signals.get('sopr', ('HOLD', '#fbbf24'))[0]}</span>
                    </span>
                </div>
                <!-- SOPR Visual Bar -->
                <div style="margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; font-size: 10px; color: #64748b; margin-bottom: 4px;">
                        <span>Loss-Taking</span><span>Break-even</span><span>Profit-Taking</span>
                    </div>
                    <div style="height: 12px; background: linear-gradient(90deg, #22c55e 0%, #4ade80 35%, #6b7280 50%, #fbbf24 65%, #ef4444 100%); border-radius: 6px; position: relative;">
                        <div style="position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background: #f8fafc; opacity: 0.5;"></div>
                        <div style="position: absolute; left: {sopr_metrics.get('sopr_position', 50)}%; top: -2px; width: 4px; height: 16px; background: #f8fafc; border-radius: 2px; transform: translateX(-50%); box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 9px; color: #475569; margin-top: 2px;">
                        <span>0.9</span><span>1.0</span><span>1.1</span>
                    </div>
                </div>
                <!-- STH vs LTH SOPR Comparison -->
                <div style="margin-bottom: 12px; padding: 8px; background: #0f172a; border-radius: 6px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 10px; color: #64748b;">Cohort Spending</span>
                        <span class="zone-badge" style="background: {sopr_metrics.get('divergence_color', '#6b7280')}20; color: {sopr_metrics.get('divergence_color', '#6b7280')}; font-size: 9px; padding: 2px 6px;">{sopr_metrics.get('cohort_divergence', 'UNKNOWN')}</span>
                    </div>
                    <div style="margin-bottom: 6px;">
                        <div style="display: flex; justify-content: space-between; font-size: 9px; margin-bottom: 2px;">
                            <span style="color: #f97316;">STH-SOPR</span>
                            <span style="color: {sopr_metrics.get('sth_state_color', '#6b7280')};">{sopr_metrics.get('sth_state', 'UNKNOWN')}</span>
                        </div>
                        <div style="height: 8px; background: linear-gradient(90deg, #22c55e 0%, #6b7280 50%, #ef4444 100%); border-radius: 4px; position: relative;">
                            <div style="position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: #f8fafc; opacity: 0.3;"></div>
                            <div style="position: absolute; left: {sopr_metrics.get('sth_sopr_position', 50)}%; top: -1px; width: 3px; height: 10px; background: #f97316; border-radius: 2px; transform: translateX(-50%);"></div>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 8px; color: #475569; margin-top: 1px;">
                            <span>0.95</span><span>1.0</span><span>1.05</span>
                        </div>
                    </div>
                    <div>
                        <div style="display: flex; justify-content: space-between; font-size: 9px; margin-bottom: 2px;">
                            <span style="color: #22c55e;">LTH-SOPR</span>
                            <span style="color: {sopr_metrics.get('lth_state_color', '#6b7280')};">{sopr_metrics.get('lth_state', 'UNKNOWN')}</span>
                        </div>
                        <div style="height: 8px; background: linear-gradient(90deg, #22c55e 0%, #6b7280 17%, #fbbf24 58%, #ef4444 100%); border-radius: 4px; position: relative;">
                            <div style="position: absolute; left: 17%; top: 0; bottom: 0; width: 1px; background: #f8fafc; opacity: 0.3;"></div>
                            <div style="position: absolute; left: {sopr_metrics.get('lth_sopr_position', 50)}%; top: -1px; width: 3px; height: 10px; background: #22c55e; border-radius: 2px; transform: translateX(-50%);"></div>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 8px; color: #475569; margin-top: 1px;">
                            <span>0.8</span><span>1.0</span><span>1.5</span><span>2.0</span>
                        </div>
                    </div>
                    <div style="font-size: 9px; color: #64748b; margin-top: 6px; text-align: center;">{sopr_metrics.get('divergence_desc', '')}</div>
                </div>'''
    
    # SOPR metric rows with trend
    sopr_m = sopr_metrics.get('sopr', {})
    sopr_val = sopr_m.get('value')
    sopr_color = '#4ade80' if sopr_val and sopr_val < 1 else '#f87171' if sopr_val and sopr_val > 1.05 else '#6b7280'
    sopr_trend = sopr_metrics.get('sopr_trend', 'N/A')
    sopr_trend_color = sopr_metrics.get('sopr_trend_color', '#6b7280')
    html += f'''
                <div class="metric-row"><span class="metric-label">SOPR</span><span><span class="metric-value" style="color: {sopr_color}">{fmt(sopr_val, 4)}</span><span style="font-size: 9px; color: {sopr_trend_color}; margin-left: 6px;">({sopr_trend})</span></span></div>'''
    
    # STH-SOPR with state
    sth_m = sopr_metrics.get('sopr_sth', {})
    sth_val = sth_m.get('value')
    sth_color = '#4ade80' if sth_val and sth_val < 1 else '#f87171' if sth_val and sth_val > 1.02 else '#6b7280'
    html += f'''
                <div class="metric-row"><span class="metric-label">STH-SOPR</span><span class="metric-value" style="color: {sth_color}">{fmt(sth_val, 4)}</span></div>'''
    
    # LTH-SOPR with state
    lth_m = sopr_metrics.get('sopr_lth', {})
    lth_val = lth_m.get('value')
    lth_color = '#22c55e' if lth_val and lth_val < 1 else '#ef4444' if lth_val and lth_val > 1.5 else '#6b7280'
    html += f'''
                <div class="metric-row"><span class="metric-label">LTH-SOPR</span><span class="metric-value" style="color: {lth_color}">{fmt(lth_val, 4)}</span></div>'''
    
    # Realized P/L Ratio
    pl_ratio = sopr_metrics.get('realized_pl_ratio')
    pl_color = '#4ade80' if pl_ratio and pl_ratio < 1 else '#f87171' if pl_ratio and pl_ratio > 10 else '#6b7280'
    html += f'''
                <div class="metric-row"><span class="metric-label">Realized P/L Ratio</span><span class="metric-value" style="color: {pl_color}">{fmt(pl_ratio, 2)}</span></div>
                <div style="margin-top: 8px; padding: 6px; background: #0f172a; border-radius: 4px; font-size: 10px; color: #64748b;">
                    {sopr_metrics.get('sentiment_desc', 'No data')}
                </div>'''
    
    html += f'''
            </div>
            
            <!-- PROFITABILITY -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" style="color: #f472b6;">Profitability</span>
                    <span>
                        <span class="zone-badge" style="background: {profitability_metrics.get('emotion_color', '#6b7280')}20; color: {profitability_metrics.get('emotion_color', '#6b7280')}">{profitability_metrics.get('emotion_emoji', '')} {profitability_metrics.get('emotion', 'UNKNOWN')}</span>
                        <span class="signal-badge" style="background: {section_signals.get('profitability', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('profitability', ('HOLD', '#fbbf24'))[1]}; margin-left: 8px;">{section_signals.get('profitability', ('HOLD', '#fbbf24'))[0]}</span>
                    </span>
                </div>
                <!-- NUPL Emotion Cycle Bar -->
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 9px; color: #64748b; margin-bottom: 4px;">
                        <span>😱 Capitulation</span><span>😰 Fear</span><span>😊 Optimism</span><span>🤑 Belief</span><span>🚀 Euphoria</span>
                    </div>
                    <div style="height: 14px; background: linear-gradient(90deg, #22c55e 0%, #4ade80 17%, #3b82f6 33%, #6b7280 50%, #fbbf24 67%, #f97316 83%, #ef4444 100%); border-radius: 6px; position: relative;">
                        <div style="position: absolute; left: {profitability_metrics.get('nupl_position', 50)}%; top: -2px; width: 4px; height: 18px; background: #f8fafc; border-radius: 2px; transform: translateX(-50%); box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 9px; color: #475569; margin-top: 2px;">
                        <span>&lt;0</span><span>0.25</span><span>0.5</span><span>0.75</span><span>&gt;0.75</span>
                    </div>
                </div>
                <!-- Supply in Profit/Loss Bar -->
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px;">
                        <span style="color: #4ade80;">In Profit {fmt(profitability_metrics.get('supply_profit_pct'), 1)}%</span>
                        <span style="color: #f87171;">In Loss {fmt(profitability_metrics.get('supply_loss_pct'), 1)}%</span>
                    </div>
                    <div style="height: 10px; background: #334155; border-radius: 5px; overflow: hidden; display: flex;">
                        <div style="width: {profitability_metrics.get('supply_profit_pct') or 50}%; background: linear-gradient(90deg, #22c55e, #4ade80);"></div>
                        <div style="width: {profitability_metrics.get('supply_loss_pct') or 50}%; background: linear-gradient(90deg, #f87171, #ef4444);"></div>
                    </div>
                </div>
                <!-- STH vs LTH Cohort Comparison -->
                <div style="margin-bottom: 12px; padding: 8px; background: #0f172a; border-radius: 6px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 10px; color: #64748b;">STH vs LTH Unrealized P/L</span>
                        <span class="zone-badge" style="background: {profitability_metrics.get('cohort_color', '#6b7280')}20; color: {profitability_metrics.get('cohort_color', '#6b7280')}; font-size: 9px; padding: 2px 6px;">{profitability_metrics.get('cohort_state', 'UNKNOWN')}</span>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <div style="flex: 1;">
                            <div style="font-size: 9px; color: #f97316; margin-bottom: 2px;">STH</div>
                            <div style="height: 8px; background: linear-gradient(90deg, #ef4444 0%, #6b7280 33%, #22c55e 100%); border-radius: 4px; position: relative;">
                                <div style="position: absolute; left: {profitability_metrics.get('sth_nupl_position', 50)}%; top: -1px; width: 3px; height: 10px; background: #f97316; border-radius: 2px; transform: translateX(-50%);"></div>
                            </div>
                        </div>
                        <div style="flex: 1;">
                            <div style="font-size: 9px; color: #22c55e; margin-bottom: 2px;">LTH</div>
                            <div style="height: 8px; background: linear-gradient(90deg, #ef4444 0%, #6b7280 33%, #22c55e 100%); border-radius: 4px; position: relative;">
                                <div style="position: absolute; left: {profitability_metrics.get('lth_nupl_position', 50)}%; top: -1px; width: 3px; height: 10px; background: #22c55e; border-radius: 2px; transform: translateX(-50%);"></div>
                            </div>
                        </div>
                    </div>
                    <div style="font-size: 9px; color: #64748b; margin-top: 4px; text-align: center;">{profitability_metrics.get('cohort_desc', '')}</div>
                </div>
                <div class="metric-row"><span class="metric-label">NUPL</span><span><span class="metric-value" style="color: {profitability_metrics.get('emotion_color', '#6b7280')}">{fmt(profitability_metrics.get('nupl'), 3)}</span><span style="font-size: 10px; color: #64748b; margin-left: 6px;">P{fmt(profitability_metrics.get('nupl_percentile'), 0) if profitability_metrics.get('nupl_percentile') else 'N/A'}</span></span></div>
                <div class="metric-row"><span class="metric-label">STH-NUPL</span><span class="metric-value" style="color: {'#4ade80' if profitability_metrics.get('nupl_sth') and profitability_metrics.get('nupl_sth') > 0 else '#f87171' if profitability_metrics.get('nupl_sth') else '#6b7280'}">{fmt(profitability_metrics.get('nupl_sth'), 3)}</span></div>
                <div class="metric-row"><span class="metric-label">LTH-NUPL</span><span class="metric-value" style="color: {'#4ade80' if profitability_metrics.get('nupl_lth') and profitability_metrics.get('nupl_lth') > 0 else '#f87171' if profitability_metrics.get('nupl_lth') else '#6b7280'}">{fmt(profitability_metrics.get('nupl_lth'), 3)}</span></div>
                <div class="metric-row"><span class="metric-label">Unrealized P/L Ratio</span><span class="metric-value" style="color: {'#4ade80' if profitability_metrics.get('profit_loss_ratio') and profitability_metrics.get('profit_loss_ratio') > 1 else '#f87171' if profitability_metrics.get('profit_loss_ratio') else '#6b7280'}">{fmt(profitability_metrics.get('profit_loss_ratio'), 2)}</span></div>
                <div style="margin-top: 8px; padding: 6px; background: #0f172a; border-radius: 4px; font-size: 10px; color: #64748b;">
                    {profitability_metrics.get('emotion_desc', 'No data')}
                </div>'''
    
    # Supply Dynamics - access values directly (not nested dicts)
    lth_pct = supply_metrics.get('lth_pct')
    sth_pct = supply_metrics.get('sth_pct')
    ratio_val = supply_metrics.get('lth_sth_ratio')
    ratio_change = supply_metrics.get('ratio_change_30d')
    ratio_change_90d = supply_metrics.get('ratio_change_90d')
    profit_pct = supply_metrics.get('profit_pct')
    loss_pct = supply_metrics.get('loss_pct')
    supply_phase = supply_metrics.get('phase', 'UNKNOWN')
    supply_phase_color = supply_metrics.get('phase_color', '#6b7280')
    
    # Phase is already calculated in calculate_supply_metrics()
    
    html += f'''
            </div>
            
            <!-- SUPPLY DYNAMICS -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" style="color: #06b6d4;">Supply Dynamics</span>
                    <span>
                        <span class="zone-badge" style="background: {supply_phase_color}20; color: {supply_phase_color}">{supply_phase}</span>
                        <span class="signal-badge" style="background: {section_signals.get('supply', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('supply', ('HOLD', '#fbbf24'))[1]}; margin-left: 8px;">{section_signals.get('supply', ('HOLD', '#fbbf24'))[0]}</span>
                    </span>
                </div>
                <!-- LTH/STH Distribution Bar -->
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px;">
                        <span style="color: #22c55e;">LTH {fmt(lth_pct, 1)}%</span>
                        <span style="color: #f97316;">STH {fmt(sth_pct, 1)}%</span>
                    </div>
                    <div style="height: 12px; background: #334155; border-radius: 6px; overflow: hidden; display: flex;">
                        <div style="width: {lth_pct or 50}%; background: #22c55e;"></div>
                        <div style="width: {sth_pct or 50}%; background: #f97316;"></div>
                    </div>
                </div>
                <div class="metric-row"><span class="metric-label">LTH/STH Ratio</span><span class="metric-value">{fmt(ratio_val, 2)}</span></div>
                <div class="metric-row"><span class="metric-label">30d Trend</span><span class="metric-value" style="color: {'#4ade80' if ratio_change and ratio_change > 0 else '#f87171' if ratio_change else '#6b7280'}">{'+' if ratio_change and ratio_change > 0 else ''}{fmt(ratio_change, 2)}%</span></div>
                <div class="metric-row"><span class="metric-label">90d Trend</span><span class="metric-value" style="color: {'#4ade80' if ratio_change_90d and ratio_change_90d > 0 else '#f87171' if ratio_change_90d else '#6b7280'}">{'+' if ratio_change_90d and ratio_change_90d > 0 else ''}{fmt(ratio_change_90d, 2)}%</span></div>
                <div class="metric-row"><span class="metric-label">Supply in Profit</span><span class="metric-value" style="color: {'#4ade80' if profit_pct and profit_pct > 75 else '#fbbf24' if profit_pct and profit_pct > 50 else '#f87171' if profit_pct else '#6b7280'}">{fmt(profit_pct, 1)}%</span></div>
            </div>
            
            <!-- LIVELINESS / ACTIVITY -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" style="color: #8b5cf6;">Liveliness</span>
                    <span>
                        <span class="zone-badge" style="background: {liveliness_metrics.get('state_color', '#6b7280')}20; color: {liveliness_metrics.get('state_color', '#6b7280')}">{liveliness_metrics.get('state', 'UNKNOWN')}</span>
                        <span class="signal-badge" style="background: {section_signals.get('liveliness', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('liveliness', ('HOLD', '#fbbf24'))[1]}; margin-left: 8px;">{section_signals.get('liveliness', ('HOLD', '#fbbf24'))[0]}</span>
                    </span>
                </div>
                <!-- Liveliness vs Vaultedness Bar -->
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px;">
                        <span style="color: #ef4444;">Active {fmt((liveliness_metrics.get('liveliness') or 0) * 100, 1)}%</span>
                        <span style="color: #22c55e;">Vaulted {fmt((liveliness_metrics.get('vaultedness') or 0) * 100, 1)}%</span>
                    </div>
                    <div style="height: 12px; background: #334155; border-radius: 6px; overflow: hidden; display: flex;">
                        <div style="width: {(liveliness_metrics.get('liveliness') or 0.5) * 100}%; background: linear-gradient(90deg, #ef4444, #fbbf24);"></div>
                        <div style="width: {(liveliness_metrics.get('vaultedness') or 0.5) * 100}%; background: linear-gradient(90deg, #4ade80, #22c55e);"></div>
                    </div>
                </div>
                <div class="metric-row"><span class="metric-label">Liveliness</span><span class="metric-value">{fmt(liveliness_metrics.get('liveliness'), 4)}</span></div>
                <div class="metric-row"><span class="metric-label">30d Change</span><span class="metric-value" style="color: {'#f87171' if liveliness_metrics.get('liveliness_change_30d') and liveliness_metrics.get('liveliness_change_30d') > 0 else '#4ade80' if liveliness_metrics.get('liveliness_change_30d') else '#6b7280'}">{'+' if liveliness_metrics.get('liveliness_change_30d') and liveliness_metrics.get('liveliness_change_30d') > 0 else ''}{fmt(liveliness_metrics.get('liveliness_change_30d'), 2)}%</span></div>
                <div class="metric-row"><span class="metric-label">CDD</span><span class="metric-value">{fmt(liveliness_metrics.get('cdd'), 0) if liveliness_metrics.get('cdd') else 'N/A'}</span></div>
                <div class="metric-row"><span class="metric-label">CDD vs 90d Avg</span><span class="metric-value" style="color: {'#f87171' if liveliness_metrics.get('cdd_vs_avg') and liveliness_metrics.get('cdd_vs_avg') > 50 else '#4ade80' if liveliness_metrics.get('cdd_vs_avg') and liveliness_metrics.get('cdd_vs_avg') < -20 else '#6b7280'}">{'+' if liveliness_metrics.get('cdd_vs_avg') and liveliness_metrics.get('cdd_vs_avg') > 0 else ''}{fmt(liveliness_metrics.get('cdd_vs_avg'), 1)}%</span></div>
                <div style="margin-top: 8px; padding: 6px; background: #0f172a; border-radius: 4px; font-size: 10px; color: #64748b;">
                    {liveliness_metrics.get('interpretation', 'No data')}
                </div>
            </div>
            
            <!-- MINER HEALTH -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" style="color: #14b8a6;">Miner Health</span>
                    <span>
                        <span class="zone-badge" style="background: {miner_metrics.get('state_color', '#6b7280')}20; color: {miner_metrics.get('state_color', '#6b7280')}">{miner_metrics.get('state', 'UNKNOWN')}</span>
                        <span class="signal-badge" style="background: {section_signals.get('miner', ('HOLD', '#fbbf24'))[1]}20; color: {section_signals.get('miner', ('HOLD', '#fbbf24'))[1]}; margin-left: 8px;">{section_signals.get('miner', ('HOLD', '#fbbf24'))[0]}</span>
                    </span>
                </div>
                <!-- Puell Multiple Bar -->
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 10px; color: #64748b; margin-bottom: 4px;">
                        <span>Capitulation</span><span>Healthy</span><span>Euphoric</span>
                    </div>
                    <div style="height: 12px; background: linear-gradient(90deg, #22c55e 0%, #4ade80 25%, #6b7280 50%, #fbbf24 75%, #ef4444 100%); border-radius: 6px; position: relative;">
                        <div style="position: absolute; left: {min(100, max(0, (miner_metrics.get('puell') or 1) / 4 * 100))}%; top: -2px; width: 4px; height: 16px; background: #f8fafc; border-radius: 2px; transform: translateX(-50%); box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 9px; color: #475569; margin-top: 2px;">
                        <span>0.5</span><span>1.0</span><span>2.0</span><span>4.0+</span>
                    </div>
                </div>
                <div class="metric-row"><span class="metric-label">Puell Multiple</span><span class="metric-value" style="color: {miner_metrics.get('state_color', '#6b7280')}">{fmt(miner_metrics.get('puell'), 2)}</span></div>
                <div class="metric-row"><span class="metric-label">Puell 30d Δ</span><span class="metric-value" style="color: {'#4ade80' if miner_metrics.get('puell_change_30d') and miner_metrics.get('puell_change_30d') > 0 else '#f87171' if miner_metrics.get('puell_change_30d') else '#6b7280'}">{'+' if miner_metrics.get('puell_change_30d') and miner_metrics.get('puell_change_30d') > 0 else ''}{fmt(miner_metrics.get('puell_change_30d'), 2)}</span></div>
                <div class="metric-row"><span class="metric-label">Difficulty</span><span class="metric-value">{fmt(miner_metrics.get('difficulty') / 1e12 if miner_metrics.get('difficulty') else None, 2)}T</span></div>
                <div class="metric-row"><span class="metric-label">Diff 30d Δ</span><span class="metric-value" style="color: {'#4ade80' if miner_metrics.get('difficulty_change_30d') and miner_metrics.get('difficulty_change_30d') > 0 else '#f87171' if miner_metrics.get('difficulty_change_30d') else '#6b7280'}">{'+' if miner_metrics.get('difficulty_change_30d') and miner_metrics.get('difficulty_change_30d') > 0 else ''}{fmt(miner_metrics.get('difficulty_change_30d'), 1)}%</span></div>
                <div style="margin-top: 8px; padding: 6px; background: #0f172a; border-radius: 4px; font-size: 10px; color: #64748b;">
                    {miner_metrics.get('interpretation', 'No data')}
                </div>
            </div>
            
            <!-- CHECKMATE COMPOSITE SIGNAL -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" style="color: #fbbf24;">Checkmate Signal</span>
                    <span class="zone-badge" style="background: {checkmate['zone_color']}20; color: {checkmate['zone_color']}">{checkmate['zone']}</span>
                </div>
                <div style="text-align: center; margin-bottom: 14px;">
                    <div style="font-size: 36px; font-weight: 700; color: {checkmate['zone_color']}">{checkmate['composite']:+.2f}</div>
                    <div style="font-size: 11px; color: #64748b;">-1 = Accumulate | +1 = Distribute</div>
                </div>
                <div style="margin-bottom: 14px;">
                    <div style="display: flex; justify-content: space-between; font-size: 10px; color: #64748b; margin-bottom: 4px;">
                        <span>Accumulate</span><span>Neutral</span><span>Distribute</span>
                    </div>
                    <div style="height: 12px; background: linear-gradient(90deg, #22c55e 0%, #4ade80 25%, #6b7280 50%, #fbbf24 75%, #ef4444 100%); border-radius: 6px; position: relative;">
                        <div style="position: absolute; left: {(checkmate['composite'] + 1) / 2 * 100:.0f}%; top: -2px; width: 4px; height: 16px; background: #f8fafc; border-radius: 2px; transform: translateX(-50%); box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>
                    </div>
                </div>
                <div style="font-size: 11px; color: #64748b; margin-bottom: 8px;">Component Scores:</div>'''
    
    for name, val, score in checkmate.get('score_details', []):
        score_color = '#22c55e' if score < -0.3 else '#ef4444' if score > 0.3 else '#6b7280'
        html += f'''
                <div class="metric-row">
                    <span class="metric-label">{name}</span>
                    <span><span style="color: #94a3b8; font-size: 11px; margin-right: 8px;">{val:.3f}</span><span class="metric-value" style="color: {score_color}">{score:+.2f}</span></span>
                </div>'''
    
    html += f'''
                <div style="margin-top: 12px; padding: 10px; background: #0f172a; border-radius: 6px; text-align: center;">
                    <span style="color: #94a3b8; font-size: 11px;">Position Size:</span>
                    <span style="font-size: 20px; font-weight: 700; margin-left: 8px; color: {checkmate['zone_color']}">{checkmate['position_size']}x</span>
                </div>
            </div>
            
            <!-- BUY THE DIP CHECKLIST -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" style="color: #10b981;">Buy The Dip</span>
                    <span class="zone-badge" style="background: {buy_the_dip.get('signal_color', '#6b7280')}20; color: {buy_the_dip.get('signal_color', '#6b7280')}">{buy_the_dip.get('signal', 'UNKNOWN')}</span>
                </div>
                <div style="text-align: center; margin-bottom: 14px; padding: 14px; background: {'linear-gradient(135deg, #14532d, #166534)' if buy_the_dip.get('onchain_triggered', 0) >= 2 else 'linear-gradient(135deg, #1e293b, #334155)'}; border-radius: 8px; border: 2px solid {buy_the_dip.get('signal_color', '#6b7280')};">
                    <div style="font-size: 28px; font-weight: 700; color: {buy_the_dip.get('signal_color', '#6b7280')};">{buy_the_dip.get('onchain_triggered', 0)}/{buy_the_dip.get('onchain_available', 0)}</div>
                    <div style="font-size: 11px; color: #64748b;">On-Chain Conditions Met</div>
                </div>
                <div style="font-size: 11px; color: #64748b; margin-bottom: 8px;">James Check's Checklist:</div>'''
    
    # Generate Buy the Dip condition rows
    for cond in buy_the_dip.get('conditions', []):
        if cond.get('manual'):
            # Manual check conditions (derivatives unavailable)
            html += f'''
                <div class="metric-row">
                    <span class="metric-label" style="color: #fbbf24;">{cond['name']}</span>
                    <span>
                        <span style="font-size: 10px; color: #64748b; margin-right: 6px;">Check: {cond.get('manual_source', 'External')}</span>
                        <span class="badge badge-gray" style="background: #78350f; color: #fbbf24;">⚠ Manual</span>
                    </span>
                </div>'''
        elif cond.get('source') == 'Glassnode':
            # Glassnode derivatives data (auto-checked from cache or API)
            val_str = cond.get('value_fmt') or (f"{cond['value']:.4f}" if cond.get('value') is not None else 'N/A')
            badge_class = 'badge-green' if cond.get('triggered') else 'badge-gray'
            val_color = '#4ade80' if cond.get('triggered') else '#f87171' if cond.get('value') is not None else '#6b7280'
            html += f'''
                <div class="metric-row">
                    <span class="metric-label">{cond['name']}</span>
                    <span>
                        <span class="metric-value" style="color: {val_color};">{val_str}</span>
                        <span style="font-size: 8px; color: #3b82f6; margin-left: 4px;">GN</span>
                        <span class="badge {badge_class}">{"✓" if cond.get('triggered') else "○"}</span>
                    </span>
                </div>'''
        else:
            # On-chain conditions (BRK data)
            val_str = f"{cond['value']:.4f}" if cond.get('value') is not None else 'N/A'
            badge_class = 'badge-green' if cond.get('triggered') else 'badge-gray'
            val_color = '#4ade80' if cond.get('triggered') else '#f87171' if cond.get('value') is not None else '#6b7280'
            html += f'''
                <div class="metric-row">
                    <span class="metric-label">{cond['name']}</span>
                    <span>
                        <span class="metric-value" style="color: {val_color};">{val_str}</span>
                        <span class="badge {badge_class}">{"✓" if cond.get('triggered') else "○"}</span>
                    </span>
                </div>'''
    
    html += f'''
                <div style="margin-top: 12px; padding: 10px; background: #0f172a; border-radius: 6px;">
                    <div style="font-size: 10px; color: #64748b; margin-bottom: 6px;">Signal Interpretation:</div>
                    <div style="font-size: 12px; color: {buy_the_dip.get('signal_color', '#6b7280')}; font-weight: 600;">{buy_the_dip.get('signal_desc', 'No data')}</div>
                    <div style="font-size: 9px; color: #475569; margin-top: 4px;">💡 Requires 2+ on-chain conditions + derivatives confirmation</div>
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
        </div>
        
        <div class="footer">Data: BRK | Entry: {len(ENTRY_SIGNALS)} | Exit: {len(EXIT_SIGNALS)} | Checkmate: 8 metrics | Buy The Dip: 5 conditions | James Check Framework</div>
    </div>
    <button class="refresh-btn" onclick="location.reload()">↻</button>
    
    <script>
        const priceLevels = {levels_str};
        
        function formatPrice(price) {{ return '$' + Math.round(price).toLocaleString(); }}
        
        function getZone(price) {{
            if (price < priceLevels.realized_price) return {{ zone: 'EXTREME BEAR', action: 'BUY', color: '#ef4444', emoji: '🔴' }};
            if (price < priceLevels.true_market_mean) return {{ zone: 'UNDERVALUED', action: 'BUY', color: '#f97316', emoji: '🟠' }};
            if (price < priceLevels.sth_realized_price) return {{ zone: 'FAIR VALUE', action: 'HOLD', color: '#22c55e', emoji: '🟢' }};
            if (price < priceLevels.vaulted_price) return {{ zone: 'OVERVALUED', action: 'SELL', color: '#fbbf24', emoji: '🟡' }};
            return {{ zone: 'EXTREME BULL', action: 'SELL', color: '#a855f7', emoji: '🟣' }};
        }}
        
        function getThermometerPosition(price) {{
            const rp = priceLevels.realized_price;
            const tmm = priceLevels.true_market_mean;
            const sth = priceLevels.sth_realized_price;
            const vp = priceLevels.vaulted_price;
            if (price < rp) return Math.max(2, 15 * (price / rp));
            if (price < tmm) return 15 + 20 * ((price - rp) / (tmm - rp));
            if (price < sth) return 35 + 15 * ((price - tmm) / (sth - tmm));
            if (price < vp) return 50 + 35 * ((price - sth) / (vp - sth));
            return Math.min(98, 85 + 15 * Math.min(1, (price - vp) / (vp * 0.5)));
        }}
        
        function updatePriceBars(price) {{
            document.querySelectorAll('.price-row').forEach(row => {{
                const level = row.dataset.level;
                const levelPrice = priceLevels[level];
                if (levelPrice) {{
                    const pct = Math.min(100, (levelPrice / price) * 100);
                    const fill = row.querySelector('.price-bar-fill');
                    if (fill) fill.style.width = pct + '%';
                }}
            }});
        }}
        
        function updateThermometer(price, zone) {{
            const marker = document.getElementById('thermo-marker');
            if (marker) marker.style.left = getThermometerPosition(price) + '%';
            
            const priceEl = document.getElementById('thermo-price');
            if (priceEl) priceEl.textContent = formatPrice(price);
            
            const zoneEl = document.getElementById('thermo-zone');
            if (zoneEl) zoneEl.textContent = zone.emoji + ' ' + zone.zone + ' • ' + zone.action;
            
            const actionBadge = document.getElementById('action-badge');
            if (actionBadge) {{
                actionBadge.textContent = zone.action;
                actionBadge.className = 'action-badge ' + zone.action.toLowerCase();
            }}
            
            const thermoCurrent = document.getElementById('thermo-current');
            if (thermoCurrent) {{
                thermoCurrent.className = 'thermo-current ' + zone.action.toLowerCase();
            }}
            
            document.querySelectorAll('.thermo-label').forEach(label => {{
                if (label.dataset.zone === zone.zone) {{
                    label.classList.add('active');
                }} else {{
                    label.classList.remove('active');
                }}
            }});
        }}
        
        async function fetchPrice() {{
            try {{
                const response = await fetch('https://api.coinbase.com/v2/prices/BTC-USD/spot');
                const data = await response.json();
                const price = parseFloat(data.data.amount);
                
                document.getElementById('live-price').textContent = formatPrice(price);
                document.getElementById('live-status').textContent = 'Live from Coinbase';
                
                const tickerResponse = await fetch('https://api.exchange.coinbase.com/products/BTC-USD/ticker');
                const ticker = await tickerResponse.json();
                const open24h = parseFloat(ticker.open_24h);
                const change = ((price - open24h) / open24h) * 100;
                
                const changeEl = document.getElementById('price-change');
                changeEl.textContent = (change >= 0 ? '+' : '') + change.toFixed(2) + '%';
                changeEl.className = 'price-change ' + (change >= 0 ? 'up' : 'down');
                
                const zone = getZone(price);
                updatePriceBars(price);
                updateThermometer(price, zone);
            }} catch (error) {{
                console.error('Price fetch error:', error);
                document.getElementById('live-status').textContent = 'Update failed';
            }}
        }}
        
        (function() {{
            const initialPrice = {context['price']['value'] or 0};
            if (initialPrice > 0) {{
                const zone = getZone(initialPrice);
                updateThermometer(initialPrice, zone);
            }}
        }})();
        
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
    metrics_needed.update([
        'price', 'mvrv', 'mvrv_z', 'nupl', 'nupl_lth', 'nupl_sth', 'aviv', 'market_cap',
        'realized_price', 'true_market_mean_price', 'vaulted_price', 'realized_price_sth',
        'supply_lth', 'supply_sth', 'supply_total', 'supply_in_profit', 'supply_in_loss',
        'supply_lth_sth_ratio', 'supply_in_profit_percent',
        'sopr_adjusted', 'mvrv_sth', 'puell_multiple', 'sell_side_risk', 'sopr_lth',
        # Liveliness/Activity metrics
        'liveliness', 'coindays_destroyed',
        # Miner metrics  
        'difficulty', 'thermo_cap',
        # Profitability metrics
        'unrealized_profit', 'unrealized_loss',
        # Buy the Dip metrics
        'realized_profit', 'realized_loss'
    ])
    
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
    momentum = calculate_momentum_metrics