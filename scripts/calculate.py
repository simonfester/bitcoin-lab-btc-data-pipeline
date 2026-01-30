#!/usr/bin/env python3
"""
Bitcoin Trading Framework - Signal Calculator
==============================================
Computes all signals, z-scores, and derived metrics from raw data.
Writes results to data/signals/ for dashboard consumption.

All 5 resolutions are supported and treated equally:
  daily, hourly (h1), h4, h8, h12

Usage:
    python calculate.py                          # Daily signals
    python calculate.py --resolution hourly      # Hourly (h1) signals
    python calculate.py --resolution h4          # 4-hourly signals
    python calculate.py --resolution h8          # 8-hourly signals
    python calculate.py --resolution h12         # 12-hourly signals
    python calculate.py --verbose                # With detailed output
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
import sys

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "brk" / "daily"
GLASSNODE_DIR = PROJECT_ROOT / "data" / "glassnode" / "daily"
GLASSNODE_HOURLY_DIR = PROJECT_ROOT / "data" / "glassnode" / "hourly"
SIGNALS_DIR = PROJECT_ROOT / "data" / "signals"

# All supported resolutions and their Bitcoin Lab data directories
ALL_RESOLUTIONS = ['daily', 'hourly', 'h4', 'h8', 'h12']
RESOLUTION_DIRS = {
    'daily':  PROJECT_ROOT / "data" / "bl" / "daily",
    'hourly': PROJECT_ROOT / "data" / "bl" / "hourly",
    'h4':     PROJECT_ROOT / "data" / "bl" / "h4",
    'h8':     PROJECT_ROOT / "data" / "bl" / "h8",
    'h12':    PROJECT_ROOT / "data" / "bl" / "h12",
}

# Metrics synced to Bitcoin Lab across all resolutions (54 metrics).
# See config/metrics.yaml for the full registry.
BL_METRICS = {
    'price', 'market_cap',
    'mvrv', 'mvrv_z', 'mvrv_lth', 'mvrv_sth', 'nvt', 'velocity',
    'sopr', 'sopr_lth', 'sopr_sth',
    'nupl', 'nupl_lth', 'nupl_sth', 'net_realized_pnl',
    'supply_in_profit', 'supply_in_profit_percent', 'supply_in_loss',
    'supply_lth', 'supply_sth', 'supply_lth_sth_ratio', 'supply_total',
    'realized_cap', 'realized_cap_lth', 'realized_cap_sth',
    'realized_price', 'realized_price_lth', 'realized_price_sth',
    'liveliness', 'vaultedness', 'supply_active', 'supply_vaulted',
    'true_market_mean_price', 'investor_cap', 'thermo_cap',
    'vaulted_price', 'aviv',
    'coindays_destroyed', 'asol', 'dormancy',
    'hashrate', 'difficulty', 'tx_count', 'utxo_increase',
    'fee_total', 'fee_total_usd', 'fee_avg',
    'volume_btc', 'volume_usd', 'volume_btc_adjusted',
    'unrealized_profit', 'unrealized_loss', 'unrealized_cap',
    'realized_profit', 'realized_loss',
}

# Keep backward-compatible alias
HOURLY_METRICS = BL_METRICS

# Hourly smoothing configuration
SMOOTHING_WINDOWS = [4, 6, 8, 12]  # hours
SMOOTH_METRICS = ['sopr', 'sopr_sth', 'sopr_lth', 'mvrv', 'mvrv_sth', 'realized_loss']

# Ensure output directory exists
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# SIGNAL DEFINITIONS
# =============================================================================

ENTRY_SIGNALS = [
    {"id": "sopr", "metric": "sopr", "condition": "lt", "threshold": 1.0,
     "label": "SOPR < 1", "description": "Market selling at loss", "category": "STRAT-002/004"},
    {"id": "sth_sopr", "metric": "sopr_sth", "condition": "lt", "threshold": 1.0,
     "label": "STH-SOPR < 1", "description": "Short-term holders capitulating", "category": "STRAT-002/004"},
    {"id": "realized_loss_z", "metric": "realized_loss", "condition": "gt", "threshold": 0.5,
     "label": "RL Z > 0.5", "description": "Elevated loss-taking", "use_zscore": True, "zscore_lookback": 365, "category": "STRAT-002/004"},
]

EXIT_SIGNALS = [
    {"id": "lth_sopr", "metric": "sopr_lth", "condition": "gt", "threshold": 1.5,
     "label": "LTH-SOPR > 1.5", "description": "Long-term holders taking profits", "category": "Distribution"},
    {"id": "mvrv_z_high", "metric": "mvrv_z", "condition": "gt", "threshold": 2.5,
     "label": "MVRV-Z > 2.5", "description": "Market expensive historically", "category": "Valuation"},
]

# Buy The Dip conditions (James Check framework)
BUY_THE_DIP_CONDITIONS = [
    {"id": "sth_mvrv", "metric": "mvrv_sth", "condition": "lt", "threshold": 1.0,
     "label": "STH-MVRV < 1", "description": "STH underwater"},
    {"id": "sth_sopr", "metric": "sopr_sth", "condition": "lt", "threshold": 1.0,
     "label": "STH-SOPR < 1", "description": "STH selling at loss"},
    {"id": "rplr", "metric": "realized_pl_ratio", "condition": "lt", "threshold": 1.0,
     "label": "RP/L Ratio < 1", "description": "Loss dominates profit", "derived": True},
    {"id": "funding", "metric": "funding_rate", "condition": "lte", "threshold": 0.0,
     "label": "Funding ≤ 0", "description": "Negative/neutral funding", "source": "glassnode"},
    {"id": "liquidations", "metric": "liquidation_ratio", "condition": "gt", "threshold": 1.0,
     "label": "Longs > Shorts Liq", "description": "More long liquidations", "source": "glassnode", "derived": True},
]

# =============================================================================
# DATA LOADING
# =============================================================================

def load_metric(name: str, source: str = "brk", resolution: str = "daily") -> pd.DataFrame:
    """Load metric from parquet file, normalizing to 'time' and 'value' columns.

    Resolution mapping (all resolutions treated equally):
      - daily  → data/bl/daily/  (fallback: data/brk/daily/)
      - hourly → data/bl/hourly/ (fallback: data/brk/daily/)
      - h4     → data/bl/h4/     (fallback: data/bl/daily/)
      - h8     → data/bl/h8/     (fallback: data/bl/daily/)
      - h12    → data/bl/h12/    (fallback: data/bl/daily/)

    Glassnode source always loads from data/glassnode/daily/ (no sub-daily).
    """
    if source == "glassnode":
        # Glassnode: try hourly dir for sub-daily, fall back to daily
        if resolution != "daily":
            path = GLASSNODE_HOURLY_DIR / f"{name}.parquet"
            if not path.exists():
                path = GLASSNODE_DIR / f"{name}.parquet"
        else:
            path = GLASSNODE_DIR / f"{name}.parquet"
    elif name in BL_METRICS:
        # Bitcoin Lab: use resolution-specific directory
        bl_dir = RESOLUTION_DIRS.get(resolution, RESOLUTION_DIRS['daily'])
        path = bl_dir / f"{name}.parquet"
        if not path.exists():
            # Fallback chain: BL daily → BRK daily
            if resolution != 'daily':
                bl_daily = RESOLUTION_DIRS['daily'] / f"{name}.parquet"
                if bl_daily.exists():
                    path = bl_daily
                else:
                    path = RAW_DATA_DIR / f"{name}.parquet"
            else:
                path = RAW_DATA_DIR / f"{name}.parquet"
    else:
        # Unknown metric: try BRK daily
        path = RAW_DATA_DIR / f"{name}.parquet"

    if not path.exists():
        return pd.DataFrame(columns=['time', 'value'])

    df = pd.read_parquet(path)

    # Normalize time column
    time_col = None
    for col in ['time', 'date', 'timestamp']:
        if col in df.columns:
            time_col = col
            break

    if time_col is None and isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        time_col = df.columns[0]

    if time_col and time_col != 'time':
        df = df.rename(columns={time_col: 'time'})

    if 'time' not in df.columns:
        return pd.DataFrame(columns=['time', 'value'])

    # Normalize value column
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

    df = df[['time', 'value']].sort_values('time').reset_index(drop=True)

    return df


def get_latest(df: pd.DataFrame) -> tuple:
    """Get latest value and timestamp from DataFrame."""
    if df.empty or 'value' not in df.columns:
        return None, None
    row = df.iloc[-1]
    return row['value'], row.get('time', None)


def calculate_z_score(df: pd.DataFrame, lookback: int = 365) -> float:
    """Calculate z-score of latest value vs lookback period."""
    if df.empty or len(df) < 10:
        return 0
    lookback = min(lookback, len(df))
    recent = df.tail(lookback)['value']
    latest = df.iloc[-1]['value']
    mean, std = recent.mean(), recent.std()
    return (latest - mean) / std if std and not pd.isna(std) else 0


def calculate_z_score_series(df: pd.DataFrame, lookback: int = 365) -> pd.DataFrame:
    """Calculate rolling z-score for entire series."""
    if df.empty:
        return df
    
    result = df.copy()
    result['z_score'] = (
        (result['value'] - result['value'].rolling(lookback, min_periods=10).mean()) /
        result['value'].rolling(lookback, min_periods=10).std()
    )
    return result


# =============================================================================
# SIGNAL EVALUATION
# =============================================================================

def evaluate_condition(value, condition: str, threshold: float) -> bool:
    """Evaluate a single condition."""
    if value is None or pd.isna(value):
        return False
    
    if condition == "lt":
        return value < threshold
    elif condition == "lte":
        return value <= threshold
    elif condition == "gt":
        return value > threshold
    elif condition == "gte":
        return value >= threshold
    elif condition == "eq":
        return value == threshold
    return False


def evaluate_signal(signal_def: dict, data: dict) -> dict:
    """Evaluate a single signal definition."""
    metric_name = signal_def["metric"]
    source = signal_def.get("source", "brk")
    
    # Handle derived metrics
    if signal_def.get("derived"):
        value = data.get(f"derived_{metric_name}")
    else:
        df = data.get(metric_name, pd.DataFrame())
        if df.empty:
            return {
                "id": signal_def["id"],
                "label": signal_def["label"],
                "value": None,
                "threshold": signal_def["threshold"],
                "triggered": False,
                "description": signal_def.get("description", "")
            }
        
        if signal_def.get("use_zscore"):
            value = calculate_z_score(df, signal_def.get("zscore_lookback", 365))
        else:
            value, _ = get_latest(df)
    
    triggered = evaluate_condition(value, signal_def["condition"], signal_def["threshold"])
    
    return {
        "id": signal_def["id"],
        "label": signal_def["label"],
        "value": value,
        "threshold": signal_def["threshold"],
        "triggered": triggered,
        "description": signal_def.get("description", "")
    }


# =============================================================================
# METRIC CALCULATIONS
# =============================================================================

def calculate_price_context(data: dict) -> dict:
    """Calculate price levels and zones."""
    price_val, price_time = get_latest(data.get('price', pd.DataFrame()))
    
    levels = {}
    for name, metric in [
        ('realized_price', 'realized_price'),
        ('true_market_mean', 'true_market_mean_price'),
        ('sth_realized_price', 'realized_price_sth'),
        ('vaulted_price', 'vaulted_price')
    ]:
        val, _ = get_latest(data.get(metric, pd.DataFrame()))
        levels[name] = val
    
    # Determine price zone
    zone = 'UNKNOWN'
    zone_color = '#6b7280'
    
    if price_val and all(levels.get(k) for k in levels):
        if price_val < levels['realized_price']:
            zone, zone_color = 'EXTREME BEAR', '#ef4444'
        elif price_val < levels['true_market_mean']:
            zone, zone_color = 'UNDERVALUED', '#f97316'
        elif price_val < levels['sth_realized_price']:
            zone, zone_color = 'FAIR VALUE', '#22c55e'
        elif price_val < levels['vaulted_price']:
            zone, zone_color = 'OVERVALUED', '#fbbf24'
        else:
            zone, zone_color = 'EXTREME BULL', '#a855f7'
    
    # Calculate % changes
    price_df = data.get('price', pd.DataFrame())
    change_24h = None
    change_7d = None
    if not price_df.empty and price_val is not None:
        if len(price_df) >= 2:
            prev = price_df.iloc[-2]['value']
            if prev and prev > 0:
                change_24h = (price_val - prev) / prev * 100
        if len(price_df) >= 8:
            prev_7d = price_df.iloc[-8]['value']
            if prev_7d and prev_7d > 0:
                change_7d = (price_val - prev_7d) / prev_7d * 100

    return {
        'price': price_val,
        'price_time': price_time,
        'levels': levels,
        'zone': zone,
        'zone_color': zone_color,
        'change_24h': change_24h,
        'change_7d': change_7d,
    }


def calculate_valuation_metrics(data: dict) -> dict:
    """Calculate MVRV, AVIV, and valuation zones."""
    mvrv_val, _ = get_latest(data.get('mvrv', pd.DataFrame()))
    mvrv_z_val, _ = get_latest(data.get('mvrv_z', pd.DataFrame()))
    aviv_val, _ = get_latest(data.get('aviv', pd.DataFrame()))
    
    # If no mvrv_z metric, calculate from mvrv
    if mvrv_z_val is None:
        mvrv_df = data.get('mvrv', pd.DataFrame())
        if not mvrv_df.empty and len(mvrv_df) >= 365:
            mvrv_z_val = calculate_z_score(mvrv_df, lookback=1460)
    
    # Determine zone
    if mvrv_z_val is not None:
        if mvrv_z_val < 0:
            zone, zone_color = 'DEEP VALUE', '#22c55e'
        elif mvrv_z_val < 1.5:
            zone, zone_color = 'FAIR VALUE', '#3b82f6'
        elif mvrv_z_val < 2.5:
            zone, zone_color = 'EXPENSIVE', '#f97316'
        else:
            zone, zone_color = 'EUPHORIA', '#ef4444'
    else:
        zone, zone_color = 'UNKNOWN', '#6b7280'
    
    return {
        'mvrv': mvrv_val,
        'mvrv_z': mvrv_z_val,
        'aviv': aviv_val,
        'zone': zone,
        'zone_color': zone_color
    }


def calculate_sopr_metrics(data: dict) -> dict:
    """Calculate spending behavior metrics (James Check framework)."""
    metrics = {}
    
    # Core SOPR values
    for key in ['sopr', 'sopr_sth', 'sopr_lth', 'sopr_adjusted']:
        val, _ = get_latest(data.get(key, pd.DataFrame()))
        metrics[key] = val
    
    sopr_val = metrics.get('sopr')
    sth_sopr_val = metrics.get('sopr_sth')
    lth_sopr_val = metrics.get('sopr_lth')
    
    # Position calculations (for visualization bars)
    metrics['sopr_position'] = max(0, min(100, (sopr_val - 0.9) / 0.2 * 100)) if sopr_val else 50
    metrics['sth_sopr_position'] = max(0, min(100, (sth_sopr_val - 0.95) / 0.1 * 100)) if sth_sopr_val else 50
    metrics['lth_sopr_position'] = max(0, min(100, (lth_sopr_val - 0.8) / 1.2 * 100)) if lth_sopr_val else 50
    
    # STH spending state
    if sth_sopr_val is not None:
        if sth_sopr_val < 0.97:
            metrics['sth_state'], metrics['sth_state_color'] = 'PANIC', '#22c55e'
        elif sth_sopr_val < 1.0:
            metrics['sth_state'], metrics['sth_state_color'] = 'LOSS-TAKING', '#4ade80'
        elif sth_sopr_val > 1.05:
            metrics['sth_state'], metrics['sth_state_color'] = 'DISTRIBUTION', '#ef4444'
        elif sth_sopr_val > 1.02:
            metrics['sth_state'], metrics['sth_state_color'] = 'PROFIT-TAKING', '#fbbf24'
        else:
            metrics['sth_state'], metrics['sth_state_color'] = 'NEUTRAL', '#6b7280'
    else:
        metrics['sth_state'], metrics['sth_state_color'] = 'UNKNOWN', '#6b7280'
    
    # LTH spending state
    if lth_sopr_val is not None:
        if lth_sopr_val < 1.0:
            metrics['lth_state'], metrics['lth_state_color'] = 'CAPITULATION', '#22c55e'
        elif lth_sopr_val > 2.0:
            metrics['lth_state'], metrics['lth_state_color'] = 'EXTREME DIST', '#ef4444'
        elif lth_sopr_val > 1.5:
            metrics['lth_state'], metrics['lth_state_color'] = 'DISTRIBUTION', '#fbbf24'
        else:
            metrics['lth_state'], metrics['lth_state_color'] = 'NORMAL', '#6b7280'
    else:
        metrics['lth_state'], metrics['lth_state_color'] = 'UNKNOWN', '#6b7280'
    
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
    
    # Net Realized P/L
    net_realized, _ = get_latest(data.get('net_realized_pnl', pd.DataFrame()))
    metrics['net_realized_pnl'] = net_realized
    
    # 7-day smoothed SOPR
    sopr_df = data.get('sopr', pd.DataFrame())
    if not sopr_df.empty and len(sopr_df) >= 7:
        metrics['sopr_7d_avg'] = sopr_df.tail(7)['value'].mean()
    else:
        metrics['sopr_7d_avg'] = sopr_val
    
    # SOPR trend
    if sopr_val and metrics.get('sopr_7d_avg'):
        metrics['sopr_trend'] = 'Rising' if sopr_val > metrics['sopr_7d_avg'] else 'Falling'
        metrics['sopr_trend_color'] = '#f87171' if sopr_val > metrics['sopr_7d_avg'] else '#4ade80'
    else:
        metrics['sopr_trend'], metrics['sopr_trend_color'] = 'N/A', '#6b7280'
    
    # Cohort divergence
    if sth_sopr_val is not None and lth_sopr_val is not None:
        if sth_sopr_val < 1.0 and lth_sopr_val > 1.5:
            metrics['cohort_divergence'] = 'STH PANIC / LTH SELLING'
            metrics['divergence_color'] = '#fbbf24'
        elif sth_sopr_val < 0.97 and lth_sopr_val < 1.0:
            metrics['cohort_divergence'] = 'ALL CAPITULATING'
            metrics['divergence_color'] = '#22c55e'
        elif sth_sopr_val > 1.02 and lth_sopr_val > 1.5:
            metrics['cohort_divergence'] = 'ALL DISTRIBUTING'
            metrics['divergence_color'] = '#ef4444'
        else:
            metrics['cohort_divergence'] = 'NORMAL'
            metrics['divergence_color'] = '#6b7280'
    else:
        metrics['cohort_divergence'], metrics['divergence_color'] = 'UNKNOWN', '#6b7280'
    
    return metrics


def calculate_supply_metrics(data: dict) -> dict:
    """Calculate supply distribution metrics."""
    metrics = {}
    
    # Core supply values
    supply_lth, _ = get_latest(data.get('supply_lth', pd.DataFrame()))
    supply_sth, _ = get_latest(data.get('supply_sth', pd.DataFrame()))
    supply_total, _ = get_latest(data.get('supply_total', pd.DataFrame()))
    supply_profit, _ = get_latest(data.get('supply_in_profit', pd.DataFrame()))
    supply_loss, _ = get_latest(data.get('supply_in_loss', pd.DataFrame()))
    
    metrics['supply_lth'] = supply_lth
    metrics['supply_sth'] = supply_sth
    metrics['supply_total'] = supply_total
    metrics['supply_in_profit'] = supply_profit
    metrics['supply_in_loss'] = supply_loss
    
    # Percentages
    if supply_total and supply_total > 0:
        metrics['lth_percent'] = (supply_lth / supply_total * 100) if supply_lth else 0
        metrics['sth_percent'] = (supply_sth / supply_total * 100) if supply_sth else 0
        metrics['profit_percent'] = (supply_profit / supply_total * 100) if supply_profit else 0
        metrics['loss_percent'] = (supply_loss / supply_total * 100) if supply_loss else 0
    else:
        metrics['lth_percent'] = metrics['sth_percent'] = 0
        metrics['profit_percent'] = metrics['loss_percent'] = 0
    
    # LTH/STH ratio
    if supply_sth and supply_sth > 0:
        metrics['lth_sth_ratio'] = supply_lth / supply_sth if supply_lth else 0
    else:
        metrics['lth_sth_ratio'] = None
    
    # Supply state
    if metrics['lth_percent'] > 70:
        metrics['supply_state'] = 'LTH DOMINANT'
        metrics['supply_state_color'] = '#22c55e'
    elif metrics['sth_percent'] > 35:
        metrics['supply_state'] = 'STH ELEVATED'
        metrics['supply_state_color'] = '#fbbf24'
    else:
        metrics['supply_state'] = 'BALANCED'
        metrics['supply_state_color'] = '#6b7280'
    
    return metrics


def calculate_profitability_metrics(data: dict) -> dict:
    """Calculate NUPL and profitability metrics."""
    metrics = {}
    
    # NUPL values
    nupl_val, _ = get_latest(data.get('nupl', pd.DataFrame()))
    nupl_lth, _ = get_latest(data.get('nupl_lth', pd.DataFrame()))
    nupl_sth, _ = get_latest(data.get('nupl_sth', pd.DataFrame()))
    
    # Normalize if needed (some sources give raw values)
    if nupl_val is not None and nupl_val > 10:
        market_cap, _ = get_latest(data.get('market_cap', pd.DataFrame()))
        if market_cap and market_cap > 0:
            nupl_val = nupl_val / market_cap
    
    metrics['nupl'] = nupl_val
    metrics['nupl_lth'] = nupl_lth
    metrics['nupl_sth'] = nupl_sth
    
    # NUPL emotion zones
    if nupl_val is not None:
        if nupl_val < 0:
            metrics['nupl_zone'] = 'CAPITULATION'
            metrics['nupl_color'] = '#ef4444'
        elif nupl_val < 0.25:
            metrics['nupl_zone'] = 'HOPE/FEAR'
            metrics['nupl_color'] = '#f97316'
        elif nupl_val < 0.5:
            metrics['nupl_zone'] = 'OPTIMISM'
            metrics['nupl_color'] = '#22c55e'
        elif nupl_val < 0.75:
            metrics['nupl_zone'] = 'BELIEF'
            metrics['nupl_color'] = '#3b82f6'
        else:
            metrics['nupl_zone'] = 'EUPHORIA'
            metrics['nupl_color'] = '#a855f7'
    else:
        metrics['nupl_zone'], metrics['nupl_color'] = 'UNKNOWN', '#6b7280'
    
    # Unrealized P/L
    unrealized_profit, _ = get_latest(data.get('unrealized_profit', pd.DataFrame()))
    unrealized_loss, _ = get_latest(data.get('unrealized_loss', pd.DataFrame()))
    metrics['unrealized_profit'] = unrealized_profit
    metrics['unrealized_loss'] = unrealized_loss
    
    return metrics


def calculate_liveliness_metrics(data: dict) -> dict:
    """Calculate liveliness and activity metrics."""
    metrics = {}
    
    liveliness, _ = get_latest(data.get('liveliness', pd.DataFrame()))
    cdd, _ = get_latest(data.get('coindays_destroyed', pd.DataFrame()))
    
    metrics['liveliness'] = liveliness
    metrics['coindays_destroyed'] = cdd
    
    # Vaultedness = 1 - Liveliness
    metrics['vaultedness'] = 1 - liveliness if liveliness is not None else None
    
    # Activity state
    if liveliness is not None:
        if liveliness > 0.7:
            metrics['activity_state'] = 'HIGH ACTIVITY'
            metrics['activity_color'] = '#ef4444'
        elif liveliness > 0.5:
            metrics['activity_state'] = 'MODERATE'
            metrics['activity_color'] = '#fbbf24'
        else:
            metrics['activity_state'] = 'LOW ACTIVITY'
            metrics['activity_color'] = '#22c55e'
    else:
        metrics['activity_state'], metrics['activity_color'] = 'UNKNOWN', '#6b7280'
    
    return metrics


def calculate_miner_metrics(data: dict) -> dict:
    """Calculate miner health metrics."""
    metrics = {}
    
    puell, _ = get_latest(data.get('puell_multiple', pd.DataFrame()))
    difficulty, _ = get_latest(data.get('difficulty', pd.DataFrame()))
    thermo_cap, _ = get_latest(data.get('thermo_cap', pd.DataFrame()))
    
    metrics['puell_multiple'] = puell
    metrics['difficulty'] = difficulty
    metrics['thermo_cap'] = thermo_cap
    
    # Puell zones
    if puell is not None:
        if puell < 0.5:
            metrics['puell_zone'] = 'MINER CAPITULATION'
            metrics['puell_color'] = '#22c55e'
        elif puell > 4:
            metrics['puell_zone'] = 'MINER PROFIT-TAKING'
            metrics['puell_color'] = '#ef4444'
        else:
            metrics['puell_zone'] = 'NORMAL'
            metrics['puell_color'] = '#6b7280'
    else:
        metrics['puell_zone'], metrics['puell_color'] = 'UNKNOWN', '#6b7280'
    
    return metrics


def calculate_checkmate_signal(data: dict) -> dict:
    """Calculate Checkmate composite signal (James Check framework)."""
    metrics = {}
    
    # Get MVRV components
    mvrv_sth, _ = get_latest(data.get('mvrv_sth', pd.DataFrame()))
    mvrv, _ = get_latest(data.get('mvrv', pd.DataFrame()))
    
    # Get SOPR components
    sopr_sth, _ = get_latest(data.get('sopr_sth', pd.DataFrame()))
    
    # Get sell-side risk
    sell_side_risk, _ = get_latest(data.get('sell_side_risk', pd.DataFrame()))
    
    conditions = []
    
    # Condition 1: STH-MVRV < 1 (STH underwater)
    if mvrv_sth is not None:
        cond1 = mvrv_sth < 1.0
        conditions.append({'name': 'STH-MVRV < 1', 'value': mvrv_sth, 'met': cond1})
    
    # Condition 2: STH-SOPR < 1 (STH selling at loss)
    if sopr_sth is not None:
        cond2 = sopr_sth < 1.0
        conditions.append({'name': 'STH-SOPR < 1', 'value': sopr_sth, 'met': cond2})
    
    # Condition 3: MVRV < 1.5 (not overheated)
    if mvrv is not None:
        cond3 = mvrv < 1.5
        conditions.append({'name': 'MVRV < 1.5', 'value': mvrv, 'met': cond3})
    
    # Condition 4: Sell-side risk low
    if sell_side_risk is not None:
        cond4 = sell_side_risk < 0.01  # Typical threshold
        conditions.append({'name': 'Low Sell Risk', 'value': sell_side_risk, 'met': cond4})
    
    # Score
    met_count = sum(1 for c in conditions if c['met'])
    total_count = len(conditions)
    
    metrics['conditions'] = conditions
    metrics['score'] = met_count
    metrics['total'] = total_count
    metrics['score_pct'] = (met_count / total_count * 100) if total_count > 0 else 0
    
    # Signal strength
    if met_count >= 3:
        metrics['signal'] = 'STRONG BUY'
        metrics['signal_color'] = '#22c55e'
    elif met_count >= 2:
        metrics['signal'] = 'BUY'
        metrics['signal_color'] = '#4ade80'
    elif met_count == 1:
        metrics['signal'] = 'NEUTRAL'
        metrics['signal_color'] = '#6b7280'
    else:
        metrics['signal'] = 'NO SIGNAL'
        metrics['signal_color'] = '#6b7280'
    
    return metrics


def calculate_buy_the_dip(data: dict, resolution: str = "daily") -> dict:
    """Calculate Buy The Dip checklist (James Check 5 conditions)."""
    metrics = {'conditions': [], 'met_count': 0}
    
    # Load Glassnode derivatives for funding/liquidations
    # Sub-daily Glassnode data often has trailing zeros — fall back to daily if latest is 0/null
    funding_df = load_metric('funding_rate', source='glassnode', resolution=resolution)
    long_liq_df = load_metric('liquidations_long', source='glassnode', resolution=resolution)
    short_liq_df = load_metric('liquidations_short', source='glassnode', resolution=resolution)

    if resolution != "daily":
        funding_val, _ = get_latest(funding_df)
        long_liq_val, _ = get_latest(long_liq_df)
        short_liq_val, _ = get_latest(short_liq_df)
        if not funding_val:
            funding_df = load_metric('funding_rate', source='glassnode', resolution='daily')
        if not long_liq_val:
            long_liq_df = load_metric('liquidations_long', source='glassnode', resolution='daily')
        if not short_liq_val:
            short_liq_df = load_metric('liquidations_short', source='glassnode', resolution='daily')

    # Derive liquidation ratio
    long_liq, _ = get_latest(long_liq_df)
    short_liq, _ = get_latest(short_liq_df)
    if long_liq and short_liq and short_liq > 0:
        data['derived_liquidation_ratio'] = long_liq / short_liq
    
    # Derive RP/L ratio
    rp, _ = get_latest(data.get('realized_profit', pd.DataFrame()))
    rl, _ = get_latest(data.get('realized_loss', pd.DataFrame()))
    if rp and rl and rl > 0:
        data['derived_realized_pl_ratio'] = rp / rl
    
    # Add funding rate to data
    if not funding_df.empty:
        data['funding_rate'] = funding_df
    
    for cond_def in BUY_THE_DIP_CONDITIONS:
        result = evaluate_signal(cond_def, data)
        metrics['conditions'].append(result)
        if result['triggered']:
            metrics['met_count'] += 1
    
    metrics['total'] = len(BUY_THE_DIP_CONDITIONS)
    metrics['score_pct'] = (metrics['met_count'] / metrics['total'] * 100) if metrics['total'] > 0 else 0
    
    # Signal determination
    if metrics['met_count'] >= 4:
        metrics['signal'] = 'STRONG DIP'
        metrics['signal_color'] = '#22c55e'
    elif metrics['met_count'] >= 3:
        metrics['signal'] = 'DIP FORMING'
        metrics['signal_color'] = '#4ade80'
    elif metrics['met_count'] >= 2:
        metrics['signal'] = 'EARLY DIP'
        metrics['signal_color'] = '#fbbf24'
    else:
        metrics['signal'] = 'NO DIP'
        metrics['signal_color'] = '#6b7280'
    
    return metrics


def calculate_8_metric_exit_detector(data: dict, resolution: str = "daily") -> dict:
    """
    James Check 8-Metric Cycle Extreme Detector (Masterclass #19)
    Detects when 4/8 (caution) or 6/8 (high risk) metrics flash extreme levels.
    """
    metrics = {'conditions': [], 'met_count': 0}

    # Load additional metrics needed
    price_df = data.get('price', pd.DataFrame())
    price_200sma_df = data.get('price_200d_sma', pd.DataFrame())
    funding_df = load_metric('funding_rate', source='glassnode', resolution=resolution)
    # Fall back to daily if sub-daily funding has trailing zeros
    if resolution != "daily":
        fv, _ = get_latest(funding_df)
        if not fv:
            funding_df = load_metric('funding_rate', source='glassnode', resolution='daily')

    # Calculate Mayer Multiple as time series
    if not price_df.empty and not price_200sma_df.empty:
        # Merge on time
        mayer_df = price_df.merge(price_200sma_df, on='time', suffixes=('_price', '_sma'))
        mayer_df['value'] = mayer_df['value_price'] / mayer_df['value_sma']
        data['mayer_multiple'] = mayer_df[['time', 'value']]

    # Add funding rate to data
    if not funding_df.empty:
        data['funding_rate'] = funding_df

    # Define 8-metric thresholds (James Check Masterclass #19)
    conditions = [
        {"id": "mvrv_z", "metric": "mvrv", "threshold": 1.5, "zscore_lookback": 1460,
         "label": "MVRV-Z > +1.5σ", "description": "Overall market overvalued"},
        {"id": "sth_mvrv_z", "metric": "mvrv_sth", "threshold": 1.25, "zscore_lookback": 365,
         "label": "STH-MVRV-Z > +1.25σ", "description": "Recent buyers euphoric"},
        {"id": "sopr_z", "metric": "sopr", "threshold": 1.5, "zscore_lookback": 365,
         "label": "SOPR-Z > +1.5σ", "description": "Heavy profit-taking"},
        {"id": "sth_sopr_z", "metric": "sopr_sth", "threshold": 1.0, "zscore_lookback": 365,
         "label": "STH-SOPR-Z > +1.0σ", "description": "STH distributing"},
        {"id": "mayer_z", "metric": "mayer_multiple", "threshold": 1.0, "zscore_lookback": 365,
         "label": "Mayer-Z > +1.0σ", "description": "Price extended vs 200MA"},
        {"id": "puell_z", "metric": "puell_multiple", "threshold": 1.5, "zscore_lookback": 365,
         "label": "Puell-Z > +1.5σ", "description": "Miners overheated"},
        {"id": "reserve_risk_z", "metric": "reserve_risk", "threshold": 1.5, "zscore_lookback": 365,
         "label": "Reserve Risk-Z > +1.5σ", "description": "HODLer sell incentive high"},
        {"id": "funding_z", "metric": "funding_rate", "threshold": 1.5, "zscore_lookback": 365,
         "label": "Funding-Z > +1.5σ", "description": "Derivatives mania", "source": "glassnode"},
    ]

    for cond in conditions:
        metric_df = data.get(cond['metric'], pd.DataFrame())

        # Skip if metric not available
        if metric_df.empty:
            metrics['conditions'].append({
                "id": cond["id"],
                "label": cond["label"],
                "value": None,
                "z_score": None,
                "triggered": False,
                "description": cond["description"]
            })
            continue

        # Calculate z-score
        z_val = calculate_z_score(metric_df, cond.get('zscore_lookback', 365))
        raw_val, _ = get_latest(metric_df)
        triggered = z_val > cond['threshold'] if z_val is not None else False

        metrics['conditions'].append({
            "id": cond["id"],
            "label": cond["label"],
            "value": raw_val,
            "z_score": z_val,
            "threshold": cond['threshold'],
            "triggered": triggered,
            "description": cond["description"]
        })

        if triggered:
            metrics['met_count'] += 1

    metrics['total'] = len(conditions)
    metrics['score_pct'] = (metrics['met_count'] / metrics['total'] * 100) if metrics['total'] > 0 else 0

    # Signal determination
    if metrics['met_count'] >= 6:
        metrics['signal'] = 'HIGH RISK'
        metrics['signal_color'] = '#ef4444'
        metrics['recommendation'] = 'Stop DCA, prepare to exit'
    elif metrics['met_count'] >= 4:
        metrics['signal'] = 'CAUTION'
        metrics['signal_color'] = '#f97316'
        metrics['recommendation'] = 'Slow DCA, reduce buys'
    elif metrics['met_count'] >= 2:
        metrics['signal'] = 'WARMING UP'
        metrics['signal_color'] = '#fbbf24'
        metrics['recommendation'] = 'Monitor closely'
    else:
        metrics['signal'] = 'NORMAL'
        metrics['signal_color'] = '#22c55e'
        metrics['recommendation'] = 'Continue accumulation'

    return metrics


def calculate_sth_mvrv_zones(data: dict) -> dict:
    """
    STH-MVRV zones for local top detection (Masterclass #21)
    Identifies when recent buyers are in overheated conditions.
    """
    sth_mvrv_df = data.get('mvrv_sth', pd.DataFrame())
    price_df = data.get('price', pd.DataFrame())

    if sth_mvrv_df.empty or price_df.empty:
        return {
            'current_value': None,
            'z_score': None,
            'zone': 'UNKNOWN',
            'zone_color': '#6b7280',
            'price_levels': {},
            'interpretation': 'Insufficient data'
        }

    # Calculate STH-MVRV Z-score
    sth_mvrv_val, _ = get_latest(sth_mvrv_df)
    sth_mvrv_z = calculate_z_score(sth_mvrv_df, lookback=365)
    price_val, _ = get_latest(price_df)

    # Calculate price levels for different Z-score thresholds
    # Price level = Realized Price STH * (1 + Z-threshold * std)
    realized_price_sth_df = data.get('realized_price_sth', pd.DataFrame())
    realized_price_sth, _ = get_latest(realized_price_sth_df)

    price_levels = {}
    if realized_price_sth and not sth_mvrv_df.empty and len(sth_mvrv_df) >= 365:
        recent_values = sth_mvrv_df.tail(365)['value']
        mean = recent_values.mean()
        std = recent_values.std()

        if not pd.isna(std) and std > 0:
            # Warming up: Z = +0.5σ
            price_levels['warming'] = realized_price_sth * (mean + 0.5 * std)
            # Local top: Z = +1.0σ (15% of days higher)
            price_levels['local_top'] = realized_price_sth * (mean + 1.0 * std)
            # Overheated: Z = +1.5σ (5% of days higher)
            price_levels['overheated'] = realized_price_sth * (mean + 1.5 * std)

    # Determine current zone
    if sth_mvrv_z is not None:
        if sth_mvrv_z > 1.5:
            zone, zone_color = 'OVERHEATED', '#ef4444'
            interpretation = 'STH extremely profitable, local top likely'
        elif sth_mvrv_z > 1.0:
            zone, zone_color = 'LOCAL TOP', '#f97316'
            interpretation = 'STH overextended, resistance likely'
        elif sth_mvrv_z > 0.5:
            zone, zone_color = 'WARMING UP', '#fbbf24'
            interpretation = 'Fresh ATHs may trigger profit-taking'
        elif sth_mvrv_z > 0:
            zone, zone_color = 'NORMAL', '#22c55e'
            interpretation = 'Room to run higher'
        elif sth_mvrv_z > -1.0:
            zone, zone_color = 'COOLED', '#3b82f6'
            interpretation = 'STH near breakeven, support level'
        else:
            zone, zone_color = 'CAPITULATION', '#8b5cf6'
            interpretation = 'STH underwater, buy opportunity'
    else:
        zone, zone_color = 'UNKNOWN', '#6b7280'
        interpretation = 'Insufficient data'

    return {
        'current_value': sth_mvrv_val,
        'z_score': sth_mvrv_z,
        'zone': zone,
        'zone_color': zone_color,
        'price_levels': price_levels,
        'current_price': price_val,
        'interpretation': interpretation
    }


def calculate_lth_distribution_signal(data: dict) -> dict:
    """
    LTH Distribution Signal: MVRV > 2.0 AND LTH-SOPR > 1.5
    Detects when smart money (HODLers) are distributing.
    """
    mvrv_df = data.get('mvrv', pd.DataFrame())
    lth_sopr_df = data.get('sopr_lth', pd.DataFrame())

    mvrv_val, _ = get_latest(mvrv_df)
    lth_sopr_val, _ = get_latest(lth_sopr_df)

    # Check conditions
    mvrv_triggered = mvrv_val is not None and mvrv_val > 2.0
    lth_sopr_triggered = lth_sopr_val is not None and lth_sopr_val > 1.5
    both_triggered = mvrv_triggered and lth_sopr_triggered

    # Determine signal strength
    if both_triggered:
        signal = 'DISTRIBUTION'
        signal_color = '#ef4444'
        interpretation = 'HODLers taking large profits - top likely forming'
    elif mvrv_triggered or lth_sopr_triggered:
        signal = 'EARLY DISTRIBUTION'
        signal_color = '#f97316'
        interpretation = 'HODLers starting to distribute'
    else:
        signal = 'ACCUMULATION'
        signal_color = '#22c55e'
        interpretation = 'HODLers holding/accumulating'

    return {
        'mvrv': mvrv_val,
        'mvrv_threshold': 2.0,
        'mvrv_triggered': mvrv_triggered,
        'lth_sopr': lth_sopr_val,
        'lth_sopr_threshold': 1.5,
        'lth_sopr_triggered': lth_sopr_triggered,
        'signal': signal,
        'signal_color': signal_color,
        'interpretation': interpretation,
        'both_triggered': both_triggered
    }


# =============================================================================
# HOURLY SMOOTHING
# =============================================================================

def smooth_hourly_data(data: dict, window: int) -> dict:
    """Apply rolling MA to key metrics in data dict, return new dict.

    Only smooths the signal-driving metrics listed in SMOOTH_METRICS.
    Other metrics pass through unchanged.
    """
    smoothed = dict(data)  # shallow copy
    for metric in SMOOTH_METRICS:
        df = data.get(metric, pd.DataFrame())
        if df.empty or len(df) < window:
            continue
        sdf = df.copy()
        sdf['value'] = sdf['value'].rolling(window, min_periods=max(1, window // 2)).mean()
        smoothed[metric] = sdf.dropna(subset=['value'])
    return smoothed


def calculate_smoothed_variants(resolution: str = "hourly", verbose: bool = False):
    """Run smoothed variants of sub-daily signal calculations.

    For each window in SMOOTHING_WINDOWS, smooths the raw data
    and re-runs all signal calculations, saving results with an MA suffix.
    """
    print("\n" + "=" * 50)
    print(f"Smoothed {resolution} Signal Variants")
    print("=" * 50)

    # Load raw data once
    metrics_needed = [
        'price', 'mvrv', 'mvrv_z', 'mvrv_sth', 'mvrv_lth', 'aviv',
        'nupl', 'nupl_lth', 'nupl_sth', 'market_cap',
        'realized_price', 'true_market_mean_price', 'vaulted_price', 'realized_price_sth',
        'supply_lth', 'supply_sth', 'supply_total', 'supply_in_profit', 'supply_in_loss',
        'sopr', 'sopr_sth', 'sopr_lth', 'sopr_adjusted',
        'realized_profit', 'realized_loss', 'net_realized_pnl',
        'liveliness', 'coindays_destroyed',
        'puell_multiple', 'difficulty', 'thermo_cap',
        'unrealized_profit', 'unrealized_loss',
        'sell_side_risk', 'reserve_risk', 'price_200d_sma'
    ]

    bl_dir = RESOLUTION_DIRS.get(resolution, RESOLUTION_DIRS['hourly'])
    print(f"\nLoading raw {resolution} metrics from {bl_dir}...")
    data = {}
    latest_time = None
    loaded = []

    for m in metrics_needed:
        df = load_metric(m, resolution=resolution)
        data[m] = df
        _, ts = get_latest(df)
        if m in BL_METRICS:
            metric_path = bl_dir / f"{m}.parquet"
            if metric_path.exists():
                loaded.append(m)
        if ts and (not latest_time or ts > latest_time):
            latest_time = ts

    print(f"  Loaded {len(loaded)} {resolution} metrics, latest: {latest_time}")

    for window in SMOOTHING_WINDOWS:
        print(f"\n--- MA-{window} ({window}-period smoothing) ---")
        smoothed_data = smooth_hourly_data(data, window)

        # Run all signal calculations on smoothed data
        results = {
            'meta': {
                'calculated_at': datetime.now().isoformat(),
                'data_as_of': latest_time.isoformat() if latest_time else None,
                'resolution': resolution,
                'smoothing': f'MA-{window}',
                'smoothing_window': window,
                'smoothed_metrics': SMOOTH_METRICS,
                'loaded_metrics': sorted(loaded),
            },
            'price_context': calculate_price_context(smoothed_data),
            'valuation': calculate_valuation_metrics(smoothed_data),
            'sopr': calculate_sopr_metrics(smoothed_data),
            'supply': calculate_supply_metrics(smoothed_data),
            'profitability': calculate_profitability_metrics(smoothed_data),
            'liveliness': calculate_liveliness_metrics(smoothed_data),
            'miner': calculate_miner_metrics(smoothed_data),
            'checkmate': calculate_checkmate_signal(smoothed_data),
            'buy_the_dip': calculate_buy_the_dip(smoothed_data, resolution=resolution),
            'exit_8_metric': calculate_8_metric_exit_detector(smoothed_data, resolution=resolution),
            'sth_mvrv_zones': calculate_sth_mvrv_zones(smoothed_data),
            'lth_distribution': calculate_lth_distribution_signal(smoothed_data),
        }

        results['entry_signals'] = [evaluate_signal(s, smoothed_data) for s in ENTRY_SIGNALS]
        results['exit_signals'] = [evaluate_signal(s, smoothed_data) for s in EXIT_SIGNALS]

        z_scores = {}
        for metric in ['mvrv', 'sopr', 'nupl', 'realized_loss', 'realized_profit', 'liveliness']:
            df = smoothed_data.get(metric, pd.DataFrame())
            if not df.empty:
                z_scores[metric] = {
                    'z_365': calculate_z_score(df, 365),
                    'z_90': calculate_z_score(df, 90)
                }
        results['z_scores'] = z_scores

        save_results(results, resolution=resolution, suffix=f"_ma{window}")

        # Print quick summary
        btd = results['buy_the_dip']
        cm = results['checkmate']
        lth = results['lth_distribution']
        print(f"  Buy The Dip: {btd['met_count']}/{btd['total']} → {btd['signal']}")
        print(f"  Checkmate:   {cm['score']}/{cm['total']} → {cm['signal']}")
        print(f"  LTH Dist:    {lth['signal']}")

    print(f"\n✅ All {len(SMOOTHING_WINDOWS)} smoothed variants saved!")


# =============================================================================
# MAIN CALCULATION
# =============================================================================

def calculate_all(verbose: bool = False, resolution: str = "daily") -> dict:
    """Calculate all metrics and signals.

    Args:
        verbose: Print detailed metric loading info.
        resolution: One of 'daily', 'hourly', 'h4', 'h8', 'h12'.
                    Each resolution loads from its Bitcoin Lab directory,
                    falling back to BL daily then BRK daily.
    """
    print("=" * 50)
    print(f"Signal Calculator ({resolution})")
    print("=" * 50)

    # Load all raw metrics
    metrics_needed = [
        'price', 'mvrv', 'mvrv_z', 'mvrv_sth', 'mvrv_lth', 'aviv',
        'nupl', 'nupl_lth', 'nupl_sth', 'market_cap',
        'realized_price', 'true_market_mean_price', 'vaulted_price', 'realized_price_sth',
        'supply_lth', 'supply_sth', 'supply_total', 'supply_in_profit', 'supply_in_loss',
        'sopr', 'sopr_sth', 'sopr_lth', 'sopr_adjusted',
        'realized_profit', 'realized_loss', 'net_realized_pnl',
        'liveliness', 'coindays_destroyed',
        'puell_multiple', 'difficulty', 'thermo_cap',
        'unrealized_profit', 'unrealized_loss',
        'sell_side_risk', 'reserve_risk', 'price_200d_sma'
    ]

    bl_dir = RESOLUTION_DIRS.get(resolution, RESOLUTION_DIRS['daily'])
    print(f"\nLoading raw metrics (resolution={resolution})...")
    print(f"  Primary dir: {bl_dir}")

    data = {}
    bl_loaded = []
    latest_time = None

    for m in metrics_needed:
        df = load_metric(m, resolution=resolution)
        data[m] = df
        val, ts = get_latest(df)

        # Track which metrics loaded from the resolution's BL directory
        if m in BL_METRICS:
            metric_path = bl_dir / f"{m}.parquet"
            if metric_path.exists():
                bl_loaded.append(m)

        if verbose and val is not None:
            src_tag = f" [{resolution}]" if m in bl_loaded else ""
            print(f"  ✓ {m}: {val:.6f}{src_tag}")
        elif verbose:
            print(f"  ✗ {m}")

        if ts and (not latest_time or ts > latest_time):
            latest_time = ts

    print(f"  Loaded {len(bl_loaded)}/{len(BL_METRICS)} {resolution} metrics")
    print(f"\nLatest data: {latest_time}")

    # Calculate all metric groups
    print("\nCalculating metrics...")

    results = {
        'meta': {
            'calculated_at': datetime.now().isoformat(),
            'data_as_of': latest_time.isoformat() if latest_time else None,
            'resolution': resolution,
            'loaded_metrics': sorted(bl_loaded),
        },
        'price_context': calculate_price_context(data),
        'valuation': calculate_valuation_metrics(data),
        'sopr': calculate_sopr_metrics(data),
        'supply': calculate_supply_metrics(data),
        'profitability': calculate_profitability_metrics(data),
        'liveliness': calculate_liveliness_metrics(data),
        'miner': calculate_miner_metrics(data),
        'checkmate': calculate_checkmate_signal(data),
        'buy_the_dip': calculate_buy_the_dip(data, resolution=resolution),
        'exit_8_metric': calculate_8_metric_exit_detector(data, resolution=resolution),
        'sth_mvrv_zones': calculate_sth_mvrv_zones(data),
        'lth_distribution': calculate_lth_distribution_signal(data)
    }
    
    # Calculate entry/exit signals
    print("Evaluating signals...")
    results['entry_signals'] = [evaluate_signal(s, data) for s in ENTRY_SIGNALS]
    results['exit_signals'] = [evaluate_signal(s, data) for s in EXIT_SIGNALS]
    
    # Calculate z-scores for key metrics
    print("Computing z-scores...")
    z_scores = {}
    for metric in ['mvrv', 'sopr', 'nupl', 'realized_loss', 'realized_profit', 'liveliness']:
        df = data.get(metric, pd.DataFrame())
        if not df.empty:
            z_scores[metric] = {
                'z_365': calculate_z_score(df, 365),
                'z_90': calculate_z_score(df, 90)
            }
    results['z_scores'] = z_scores
    
    return results


def save_results(results: dict, resolution: str = "daily", suffix: str = ""):
    """Save calculated results to parquet files.

    Args:
        results: Calculated signal results dict.
        resolution: One of 'daily', 'hourly', 'h4', 'h8', 'h12'.
        suffix: Extra suffix for smoothed variants (e.g. '_ma4').
    """
    print("\nSaving results...")

    # Custom JSON encoder to handle datetime/numpy while preserving booleans
    def json_serializer(obj):
        if isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if pd.isna(obj):
            return None
        raise TypeError(f"Type {type(obj)} not serializable")

    # Save main dashboard context as JSON (for easy reading)
    # daily → "" (no suffix), hourly → "_hourly", h4 → "_h4", etc.
    res_suffix = "" if resolution == "daily" else f"_{resolution}"
    full_suffix = f"{res_suffix}{suffix}"
    context_path = SIGNALS_DIR / f"dashboard_context{full_suffix}.json"
    with open(context_path, 'w') as f:
        json.dump(results, f, indent=2, default=json_serializer)
    print(f"  ✓ {context_path}")
    
    # Save entry signals
    entry_df = pd.DataFrame(results['entry_signals'])
    entry_path = SIGNALS_DIR / f"entry_signals{full_suffix}.parquet"
    entry_df.to_parquet(entry_path)
    print(f"  ✓ {entry_path}")

    # Save exit signals
    exit_df = pd.DataFrame(results['exit_signals'])
    exit_path = SIGNALS_DIR / f"exit_signals{full_suffix}.parquet"
    exit_df.to_parquet(exit_path)
    print(f"  ✓ {exit_path}")

    # Save buy the dip conditions
    btd_df = pd.DataFrame(results['buy_the_dip']['conditions'])
    btd_path = SIGNALS_DIR / f"buy_the_dip{full_suffix}.parquet"
    btd_df.to_parquet(btd_path)
    print(f"  ✓ {btd_path}")

    # Save checkmate conditions
    cm_df = pd.DataFrame(results['checkmate']['conditions'])
    cm_path = SIGNALS_DIR / f"checkmate{full_suffix}.parquet"
    cm_df.to_parquet(cm_path)
    print(f"  ✓ {cm_path}")
    
    print("\n✅ All signals calculated and saved!")


def main():
    verbose = '--verbose' in sys.argv or '-v' in sys.argv

    # Parse --resolution argument
    resolution = "daily"
    for i, arg in enumerate(sys.argv):
        if arg == '--resolution' and i + 1 < len(sys.argv):
            resolution = sys.argv[i + 1]
            break

    if resolution not in ALL_RESOLUTIONS:
        print(f"Unknown resolution: {resolution}. Use one of: {', '.join(ALL_RESOLUTIONS)}")
        sys.exit(1)

    results = calculate_all(verbose=verbose, resolution=resolution)
    save_results(results, resolution=resolution)

    # Run smoothed variants for sub-daily resolutions
    if resolution != "daily":
        calculate_smoothed_variants(resolution=resolution, verbose=verbose)

    # Print summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    # Price zone
    pc = results['price_context']
    print(f"\nPrice: ${pc['price']:,.0f}" if pc['price'] else "\nPrice: N/A")
    print(f"Zone: {pc['zone']}")
    
    # Valuation
    val = results['valuation']
    print(f"\nMVRV-Z: {val['mvrv_z']:.2f}" if val['mvrv_z'] else "\nMVRV-Z: N/A")
    print(f"Valuation: {val['zone']}")
    
    # Entry signals
    entry_triggered = [s for s in results['entry_signals'] if s['triggered']]
    print(f"\nEntry Signals: {len(entry_triggered)}/{len(results['entry_signals'])} triggered")
    for s in entry_triggered:
        print(f"  ✓ {s['label']}")
    
    # Buy the dip
    btd = results['buy_the_dip']
    print(f"\nBuy The Dip: {btd['met_count']}/{btd['total']} conditions met")
    print(f"Signal: {btd['signal']}")
    
    # Checkmate
    cm = results['checkmate']
    print(f"\nCheckmate: {cm['score']}/{cm['total']} conditions met")
    print(f"Signal: {cm['signal']}")


if __name__ == "__main__":
    main()
