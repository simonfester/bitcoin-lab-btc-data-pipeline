#!/usr/bin/env python3
"""
VectorBT Strategy Backtester
============================
Run backtests on strategy config files and save results as sidecar files.

Usage:
    python backtest_vectorbt.py --config my_strat.json  # Run from JSON file
    python backtest_vectorbt.py --strategy strat005     # Run by strategy ID
    python backtest_vectorbt.py --list                  # List available strategies
    python backtest_vectorbt.py --all                   # Run all strategies
    python backtest_vectorbt.py --walk-forward          # Include walk-forward analysis
    python backtest_vectorbt.py --debug                 # Show detailed trades

Strategy Config JSON Format:
    {
      "id": "MY-STRAT",
      "name": "My Strategy Name",
      "entry": {
        "conditions": [
          {"metric": "mvrv_sth", "operator": "<", "threshold": 1.0},
          {"metric": "sopr_sth", "operator": "<", "threshold": 1.0}
        ],
        "required_conditions": 2
      },
      "exit": {
        "conditions": [
          {"metric": "mvrv", "operator": ">", "threshold": 2.5}
        ]
      }
    }
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import json
from datetime import datetime
import warnings
import argparse
warnings.filterwarnings('ignore')

# Plotly for interactive charts
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("⚠ Plotly not installed - interactive charts disabled")

# Try to import vectorbt
try:
    import vectorbt as vbt
    print("✓ VectorBT loaded")
except ImportError:
    print("✗ VectorBT not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "vectorbt"])
    import vectorbt as vbt
    print("✓ VectorBT installed and loaded")

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "brk" / "daily"
GLASSNODE_DIR = PROJECT_ROOT / "data" / "glassnode" / "daily"
STRATEGIES_DIR = PROJECT_ROOT / "config" / "strategies"

# Split dates
# Note: Derivatives data (funding, liquidations) starts 2020-02-02
# So effective backtest start is 2020-02-02
DERIVATIVES_START = '2020-02-02'
TRAIN_END = '2022-12-31'
TEST_START = '2023-01-01'

# Costs
FEES = 0.001  # 0.1%
SLIPPAGE = 0.001  # 0.1%
INIT_CASH = 100000  # Starting portfolio value

# Position Sizing (Risk-Based) - Defaults, can be overridden in strategy config
RISK_PER_TRADE = 0.02  # 2% of portfolio risked per trade
STOP_LOSS_PCT = 0.10   # 10% stop-loss below entry
# Position size = (Portfolio * RISK_PER_TRADE) / STOP_LOSS_PCT
# Example: $10,000 * 0.02 / 0.10 = $2,000 position (20% of portfolio)

# Valid resolutions
VALID_RESOLUTIONS = ['daily', 'd1', 'h1', 'h4', 'h8', 'h12']
RESOLUTION_FREQ_MAP = {
    'daily': '1D', 'd1': '1D',
    'h1': '1h', 'h4': '4h', 'h8': '8h', 'h12': '12h'
}

# Smoothing configuration (matches calculate.py)
VALID_SMOOTHING_WINDOWS = [4, 6, 8, 12]
SMOOTH_COLUMNS = ['sopr', 'sopr_sth', 'sopr_lth', 'mvrv', 'mvrv_sth', 'realized_loss']


# =============================================================================
# STRATEGY CONFIGURATION
# =============================================================================

def list_strategies() -> list:
    """List all available strategy config files."""
    strategies = []
    for path in STRATEGIES_DIR.glob("*.json"):
        # Skip results files
        if path.stem.endswith("_results"):
            continue
        try:
            with open(path, 'r') as f:
                config = json.load(f)
            strategies.append({
                'file': path.stem,
                'id': config.get('id', path.stem),
                'name': config.get('name', 'Unknown'),
                'status': config.get('status', 'UNKNOWN'),
                'path': path
            })
        except Exception as e:
            print(f"  Warning: Could not load {path.name}: {e}")
    return sorted(strategies, key=lambda x: x['id'])


def load_strategy_config(strategy_id: str) -> dict:
    """Load a strategy config by ID or filename."""
    # Try exact match first
    for path in STRATEGIES_DIR.glob("*.json"):
        if path.stem.endswith("_results"):
            continue
        try:
            with open(path, 'r') as f:
                config = json.load(f)
            # Match by ID or filename
            if config.get('id', '').lower() == strategy_id.lower():
                config['_path'] = path
                return config
            if strategy_id.lower() in path.stem.lower():
                config['_path'] = path
                return config
        except Exception:
            continue
    return None


def load_strategy_from_file(filepath: str) -> dict:
    """Load a strategy config directly from a JSON file path."""
    path = Path(filepath)
    if not path.exists():
        print(f"✗ Config file not found: {filepath}")
        return None
    if not path.suffix == '.json':
        print(f"✗ Config file must be JSON: {filepath}")
        return None
    try:
        with open(path, 'r') as f:
            config = json.load(f)
        config['_path'] = path
        # Ensure required fields
        if 'id' not in config:
            config['id'] = path.stem.upper()
        if 'name' not in config:
            config['name'] = path.stem.replace('_', ' ').title()
        return config
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON in {filepath}: {e}")
        return None
    except Exception as e:
        print(f"✗ Error loading {filepath}: {e}")
        return None


def get_results_path(strategy_config: dict) -> Path:
    """Get the sidecar results file path for a strategy."""
    config_path = strategy_config.get('_path')
    smoothing = strategy_config.get('_smoothing_window')
    suffix = f"_ma{smoothing}" if smoothing else ""
    if config_path:
        return config_path.parent / f"{config_path.stem}_results{suffix}.json"
    return STRATEGIES_DIR / f"unknown_results{suffix}.json"


def save_strategy_results(strategy_config: dict, results: dict, save_to_db: bool = True) -> Path:
    """Save backtest results to sidecar file and database."""
    results_path = get_results_path(strategy_config)

    strategy_id = strategy_config.get('id', 'unknown')
    strategy_name = strategy_config.get('name', 'Unknown')

    # Add strategy metadata
    output = {
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "strategy_version": strategy_config.get('version', '1.0'),
        "run_date": datetime.now().isoformat(),
        **results
    }

    # Save to sidecar file (for backward compatibility with dashboard)
    with open(results_path, 'w') as f:
        json.dump(output, f, indent=2)

    # Save to database for long-term storage and querying
    if save_to_db:
        try:
            from src.backtest_db import BacktestDB

            db = BacktestDB()

            # Extract parameters from strategy config
            parameters = {
                'entry': strategy_config.get('entry', {}),
                'exit': strategy_config.get('exit', {}),
                'version': strategy_config.get('version', '1.0')
            }

            run_id = db.save_run(
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                results=results,
                parameters=parameters
            )
            print(f"  ✓ Saved to database: {run_id}")

        except Exception as e:
            print(f"  ⚠ Database save failed: {e}")

    return results_path

# =============================================================================
# DATA LOADING
# =============================================================================

def load_metric(name: str, source: str = "brk") -> pd.Series:
    """Load metric as time-indexed Series."""
    if source == "brk":
        path = DATA_DIR / f"{name}.parquet"
    elif source == "glassnode":
        path = GLASSNODE_DIR / f"{name}.parquet"
    else:
        return pd.Series(dtype=float)

    if not path.exists():
        return pd.Series(dtype=float)

    df = pd.read_parquet(path)

    # Normalize
    if 'time' not in df.columns and isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        if len(df.columns) == 2:
            df.columns = ['time', 'value']

    if 'value' not in df.columns:
        for col in df.columns:
            if col != 'time' and pd.api.types.is_numeric_dtype(df[col]):
                df['value'] = df[col]
                break

    if 'time' in df.columns and 'value' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        df = df.set_index('time')['value']
        df = df.sort_index()
        return df

    return pd.Series(dtype=float)


def load_data_for_resolution(resolution: str = 'daily') -> pd.DataFrame:
    """
    Load data for a specific resolution.

    Args:
        resolution: 'daily', 'd1', 'h1', 'h4', 'h8', 'h12'

    Returns:
        DataFrame with metrics for that resolution
    """
    resolution = resolution.lower()
    if resolution not in VALID_RESOLUTIONS:
        print(f"⚠ Invalid resolution '{resolution}', using 'daily'")
        resolution = 'daily'

    print(f"\nLoading {resolution} data...")

    # Map resolution to data directory
    if resolution in ['daily', 'd1']:
        # Daily data from BRK (free)
        return load_all_data()  # Use existing function
    else:
        # Hourly data from Bitcoin Lab
        res_dir = {
            'h1': PROJECT_ROOT / 'data' / 'bl' / 'hourly',
            'h4': PROJECT_ROOT / 'data' / 'bl' / 'h4',
            'h8': PROJECT_ROOT / 'data' / 'bl' / 'h8',
            'h12': PROJECT_ROOT / 'data' / 'bl' / 'h12'
        }.get(resolution)

        if not res_dir or not res_dir.exists():
            print(f"✗ Data directory not found for {resolution}: {res_dir}")
            print("  Run: python run.py bl-sync-hourly (or bl-sync-h4, etc.)")
            return pd.DataFrame()

        # Load available metrics from Bitcoin Lab hourly
        df_dict = {}
        bl_metrics = [
            'price', 'sopr', 'sopr_sth', 'sopr_lth', 'realized_loss',
            'mvrv', 'mvrv_sth', 'realized_profit'  # Also available at hourly
        ]

        for metric in bl_metrics:
            path = res_dir / f"{metric}.parquet"
            if path.exists():
                df = pd.read_parquet(path)
                if 'time' in df.columns:
                    df['time'] = pd.to_datetime(df['time'])
                    df = df.set_index('time')
                if 'value' in df.columns:
                    df_dict[metric] = df['value']
                elif len(df.columns) == 1:
                    df_dict[metric] = df.iloc[:, 0]
                print(f"  ✓ {metric}")
            else:
                print(f"  ✗ {metric} (missing)")

        if not df_dict:
            print(f"✗ No data found for resolution {resolution}")
            return pd.DataFrame()

        df = pd.DataFrame(df_dict)
        df = df.sort_index()

        # For hourly data, load remaining daily-only metrics and forward-fill
        # Note: mvrv, mvrv_sth, realized_profit now loaded from hourly above
        daily_metrics = [
            'mvrv_lth',                       # LTH MVRV (daily only)
            'nupl', 'puell_multiple',         # Other indicators (daily only)
            'price_200d_sma'                  # For momentum exit (daily only)
        ]
        # Derivatives from Glassnode (for Buy The Dip signals)
        derivatives_metrics = ['funding', 'liq_long', 'liq_short']

        for metric in daily_metrics:
            daily_series = load_metric(metric, 'brk')
            if not daily_series.empty:
                # Reindex to hourly and forward-fill
                df[metric] = daily_series.reindex(df.index, method='ffill')
                print(f"  ✓ {metric} (daily→{resolution})")

        # Load derivatives from Glassnode
        # Try hourly first, fall back to daily forward-fill
        deriv_file_map = {
            'funding': 'funding_rate',
            'liq_long': 'liquidations_long',
            'liq_short': 'liquidations_short'
        }
        glassnode_hourly_dir = PROJECT_ROOT / 'data' / 'glassnode' / 'hourly'

        for col_name, file_name in deriv_file_map.items():
            hourly_path = glassnode_hourly_dir / f"{file_name}.parquet"
            if hourly_path.exists():
                # Load hourly derivatives
                deriv_df = pd.read_parquet(hourly_path)
                if 'time' in deriv_df.columns:
                    deriv_df['time'] = pd.to_datetime(deriv_df['time'])
                    deriv_df = deriv_df.set_index('time')
                if 'value' in deriv_df.columns:
                    df[col_name] = deriv_df['value'].reindex(df.index, method='ffill')
                elif len(deriv_df.columns) == 1:
                    df[col_name] = deriv_df.iloc[:, 0].reindex(df.index, method='ffill')
                print(f"  ✓ {col_name} (hourly)")
            else:
                # Fall back to daily forward-fill
                daily_series = load_metric(file_name, 'glassnode')
                if not daily_series.empty:
                    df[col_name] = daily_series.reindex(df.index, method='ffill')
                    print(f"  ✓ {col_name} (daily→{resolution})")

        # Filter to only dates where all Buy The Dip metrics have valid data
        # This prevents false signals before derivatives data starts (2020-02-02 for funding)
        btd_required_cols = ['mvrv_sth', 'sopr_sth', 'realized_profit', 'realized_loss',
                             'funding', 'liq_long', 'liq_short']
        available_cols = [c for c in btd_required_cols if c in df.columns]

        if available_cols:
            has_all_data = df[available_cols].notna().all(axis=1)
            df_filtered = df[has_all_data].copy()

            print(f"\nData loaded: {len(df)} bars from {df.index[0]} to {df.index[-1]}")
            if len(df_filtered) < len(df):
                print(f"Valid data (all metrics): {len(df_filtered)} bars from {df_filtered.index[0]} to {df_filtered.index[-1]}")

            return df_filtered

        print(f"\nData loaded: {len(df)} bars from {df.index[0]} to {df.index[-1]}")
        return df


def load_all_data() -> pd.DataFrame:
    """Load all daily metrics into aligned DataFrame."""
    print("\nLoading daily data...")

    metrics = {
        'price': ('price', 'brk'),
        'mvrv': ('mvrv', 'brk'),
        'mvrv_sth': ('mvrv_sth', 'brk'),
        'mvrv_lth': ('mvrv_lth', 'brk'),
        'sopr': ('sopr', 'brk'),
        'sopr_sth': ('sopr_sth', 'brk'),
        'sopr_lth': ('sopr_lth', 'brk'),
        'realized_profit': ('realized_profit', 'brk'),
        'realized_loss': ('realized_loss', 'brk'),
        'puell': ('puell_multiple', 'brk'),
        'price_200sma': ('price_200d_sma', 'brk'),
        'funding': ('funding_rate', 'glassnode'),
        'liq_long': ('liquidations_long', 'glassnode'),
        'liq_short': ('liquidations_short', 'glassnode'),
    }

    df_dict = {}
    for name, (metric, source) in metrics.items():
        series = load_metric(metric, source)
        if not series.empty:
            df_dict[name] = series
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name} (missing)")

    # Combine all series
    df = pd.DataFrame(df_dict)

    # Forward fill missing values (common in derivatives data)
    df = df.fillna(method='ffill')

    # For STRAT-005: Filter to only dates where derivatives data is available
    # This prevents false signals before 2020
    derivatives_cols = ['funding', 'liq_long', 'liq_short']
    has_derivatives = df[derivatives_cols].notna().all(axis=1)
    df_filtered = df[has_derivatives].copy()

    print(f"\nData loaded: {len(df)} days from {df.index[0]} to {df.index[-1]}")
    print(f"With derivatives: {len(df_filtered)} days from {df_filtered.index[0]} to {df_filtered.index[-1]}")

    return df_filtered


# =============================================================================
# DATA SMOOTHING
# =============================================================================

def apply_smoothing(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Apply rolling MA smoothing to key signal-driving columns.

    Only smooths columns listed in SMOOTH_COLUMNS. Other columns pass through
    unchanged. Uses min_periods=window//2 to avoid excessive NaN at start.

    Args:
        df: DataFrame with metric columns
        window: Rolling window size (in bars — hours for hourly, days for daily)

    Returns:
        New DataFrame with smoothed columns
    """
    result = df.copy()
    smoothed_count = 0
    for col in SMOOTH_COLUMNS:
        if col in result.columns:
            result[col] = result[col].rolling(window, min_periods=max(1, window // 2)).mean()
            smoothed_count += 1
    print(f"  Applied MA-{window} smoothing to {smoothed_count} columns: "
          f"{[c for c in SMOOTH_COLUMNS if c in result.columns]}")
    # Drop rows where smoothed columns became NaN
    result = result.dropna(subset=[c for c in SMOOTH_COLUMNS if c in result.columns])
    return result


# =============================================================================
# SIGNAL GENERATION (NO LOOK-AHEAD BIAS)
# =============================================================================

def calculate_rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """Calculate rolling z-score using ONLY past data."""
    mean = series.rolling(window, min_periods=30).mean()
    std = series.rolling(window, min_periods=30).std()
    return (series - mean) / std


def generate_buy_the_dip_entries(df: pd.DataFrame, threshold: int = 4) -> pd.Series:
    """
    Generate Buy The Dip entry signals.
    CRITICAL: Each row only uses data available UP TO that date.

    Args:
        df: DataFrame with required metrics
        threshold: Number of conditions required (default 4 out of 5)
    """
    print(f"\nGenerating Buy The Dip signals ({threshold}/5 threshold)...")

    # Condition 1: STH-MVRV < 1.0
    c1 = df['mvrv_sth'] < 1.0

    # Condition 2: STH-SOPR < 1.0
    c2 = df['sopr_sth'] < 1.0

    # Condition 3: RP/L Ratio < 1.0
    rplr = df['realized_profit'] / df['realized_loss']
    c3 = rplr < 1.0

    # Condition 4: Funding <= 0
    c4 = df['funding'] <= 0.0

    # Condition 5: Long Liq > Short Liq
    liq_ratio = df['liq_long'] / df['liq_short']
    c5 = liq_ratio > 1.0

    # Count conditions
    count = c1.astype(int) + c2.astype(int) + c3.astype(int) + c4.astype(int) + c5.astype(int)

    # Entry when threshold+ conditions met
    entries = count >= threshold

    print(f"  Generated {entries.sum()} entry signals")

    return entries


def generate_lth_distribution_exits(df: pd.DataFrame) -> pd.Series:
    """Generate LTH Distribution exit signals."""
    print("Generating LTH Distribution exits...")

    exits = (df['mvrv'] > 2.0) & (df['sopr_lth'] > 1.5)

    print(f"  Generated {exits.sum()} exit signals")

    return exits


def generate_momentum_exit(df: pd.DataFrame, mvrv_threshold: float = 2.0, ma_period: int = 50,
                          mvrv_ma_period: int = None, use_daily_price_ma: bool = False) -> pd.Series:
    """
    Generate STRAT-005 Momentum-Confirmed Exit signals.
    Exit when: MVRV > threshold AND Price < MA

    Args:
        df: DataFrame with price and mvrv columns
        mvrv_threshold: MVRV threshold for overvaluation (default 2.0)
        ma_period: Price MA period (default 50)
        mvrv_ma_period: Optional MVRV smoothing period (None = use raw MVRV)
        use_daily_price_ma: If True, calculate MA on daily price then forward-fill
    """
    mvrv_desc = f"MVRV_MA{mvrv_ma_period}" if mvrv_ma_period else "MVRV"
    price_desc = f"Price<MA{ma_period}_daily" if use_daily_price_ma else f"Price<MA{ma_period}"
    print(f"Generating Momentum Exit ({mvrv_desc}>{mvrv_threshold} AND {price_desc})...")

    # Calculate price moving average
    if use_daily_price_ma:
        # Load daily price, calculate MA, then forward-fill to hourly
        daily_price = load_metric('price', 'brk')
        daily_ma = daily_price.rolling(window=ma_period, min_periods=ma_period).mean()
        # Forward-fill to match hourly index
        price_ma = daily_ma.reindex(df.index, method='ffill')
        print(f"  Using daily {ma_period}d MA forward-filled to hourly")
    else:
        price_ma = df['price'].rolling(window=ma_period, min_periods=ma_period).mean()

    # Calculate MVRV (optionally smoothed)
    if mvrv_ma_period:
        mvrv = df['mvrv'].rolling(window=mvrv_ma_period, min_periods=mvrv_ma_period).mean()
    else:
        mvrv = df['mvrv']

    # Exit conditions - both must be true
    mvrv_overvalued = mvrv > mvrv_threshold
    below_ma = df['price'] < price_ma

    exits = mvrv_overvalued & below_ma

    print(f"  Generated {exits.sum()} exit signals")

    return exits


def generate_8metric_exits(df: pd.DataFrame, threshold: int = 6) -> pd.Series:
    """Generate 8-Metric exit signals (6/8 threshold)."""
    print(f"Generating 8-Metric exits ({threshold}/8)...")

    # Calculate Z-scores using ONLY past data
    mvrv_z = calculate_rolling_zscore(df['mvrv'], 1460)
    mvrv_sth_z = calculate_rolling_zscore(df['mvrv_sth'], 365)
    sopr_z = calculate_rolling_zscore(df['sopr'], 365)
    sopr_sth_z = calculate_rolling_zscore(df['sopr_sth'], 365)
    puell_z = calculate_rolling_zscore(df['puell'], 365)

    # Mayer Multiple
    mayer = df['price'] / df['price_200sma']
    mayer_z = calculate_rolling_zscore(mayer, 365)

    # Funding Z
    funding_z = calculate_rolling_zscore(df['funding'], 365)

    # Count triggers
    count = (
        (mvrv_z > 1.5).astype(int) +
        (mvrv_sth_z > 1.25).astype(int) +
        (sopr_z > 1.5).astype(int) +
        (sopr_sth_z > 1.0).astype(int) +
        (mayer_z > 1.0).astype(int) +
        (puell_z > 1.5).astype(int) +
        (funding_z > 1.5).astype(int)
    )

    exits = count >= threshold

    print(f"  Generated {exits.sum()} exit signals")

    return exits


# =============================================================================
# INTERACTIVE TRADE CHART (PLOTLY)
# =============================================================================

def generate_trade_chart(df: pd.DataFrame, trades: list, strategy_name: str = "Strategy") -> str:
    """
    Generate interactive Plotly chart showing price with trade entry/exit markers.

    Returns HTML string that can be embedded in dashboard.
    """
    if not PLOTLY_AVAILABLE:
        return "<p>Plotly not available for interactive charts</p>"

    if not trades:
        return "<p>No trades to display</p>"

    # Create figure with secondary y-axis for equity
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=('Price & Trades', 'Portfolio Value')
    )

    # Add price line
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['price'],
            mode='lines',
            name='BTC Price',
            line=dict(color='#6b7280', width=1.5),
            hovertemplate='%{x}<br>Price: $%{y:,.0f}<extra></extra>'
        ),
        row=1, col=1
    )

    # Process trades for markers and regions
    entry_dates = []
    entry_prices = []
    entry_texts = []
    exit_dates = []
    exit_prices = []
    exit_colors = []
    exit_texts = []

    for i, trade in enumerate(trades):
        # Parse dates
        entry_date = pd.to_datetime(trade['entry_date'].split('+')[0].strip())
        exit_date = pd.to_datetime(trade['exit_date'].split('+')[0].strip())

        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        pnl = trade.get('pnl', 0)
        return_pct = trade.get('return_pct', 0)
        exit_type = trade.get('exit_type', 'SIGNAL')

        entry_dates.append(entry_date)
        entry_prices.append(entry_price)
        entry_texts.append(f"Trade {i+1} Entry<br>${entry_price:,.0f}")

        exit_dates.append(exit_date)
        exit_prices.append(exit_price)
        exit_colors.append('#22c55e' if pnl >= 0 else '#ef4444')
        exit_texts.append(f"Trade {i+1} Exit ({exit_type})<br>${exit_price:,.0f}<br>P&L: ${pnl:+,.0f} ({return_pct:+.1f}%)")

        # Add shaded region for trade period
        fig.add_vrect(
            x0=entry_date, x1=exit_date,
            fillcolor='#22c55e' if pnl >= 0 else '#ef4444',
            opacity=0.1,
            line_width=0,
            row=1, col=1
        )

        # Add stop-loss line during trade
        stop_price = trade.get('stop_price', 0)
        if stop_price > 0:
            fig.add_trace(
                go.Scatter(
                    x=[entry_date, exit_date],
                    y=[stop_price, stop_price],
                    mode='lines',
                    name=f'Stop {i+1}',
                    line=dict(color='#ef4444', width=1, dash='dot'),
                    showlegend=False,
                    hovertemplate=f'Stop Loss: ${stop_price:,.0f}<extra></extra>'
                ),
                row=1, col=1
            )

    # Add entry markers
    fig.add_trace(
        go.Scatter(
            x=entry_dates,
            y=entry_prices,
            mode='markers',
            name='Entry',
            marker=dict(
                symbol='triangle-up',
                size=14,
                color='#22c55e',
                line=dict(color='white', width=1)
            ),
            text=entry_texts,
            hovertemplate='%{text}<extra></extra>'
        ),
        row=1, col=1
    )

    # Add exit markers
    fig.add_trace(
        go.Scatter(
            x=exit_dates,
            y=exit_prices,
            mode='markers',
            name='Exit',
            marker=dict(
                symbol='triangle-down',
                size=14,
                color=exit_colors,
                line=dict(color='white', width=1)
            ),
            text=exit_texts,
            hovertemplate='%{text}<extra></extra>'
        ),
        row=1, col=1
    )

    # Calculate and add equity curve for subplot
    equity = [INIT_CASH]
    equity_dates = [df.index[0]]
    current_balance = INIT_CASH

    for trade in trades:
        exit_date = pd.to_datetime(trade['exit_date'].split('+')[0].strip())
        current_balance += trade.get('pnl', 0)
        equity_dates.append(exit_date)
        equity.append(current_balance)

    # Add final point
    equity_dates.append(df.index[-1])
    equity.append(current_balance)

    fig.add_trace(
        go.Scatter(
            x=equity_dates,
            y=equity,
            mode='lines+markers',
            name='Portfolio',
            line=dict(color='#3b82f6', width=2),
            marker=dict(size=6),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.1)',
            hovertemplate='%{x}<br>Portfolio: $%{y:,.0f}<extra></extra>'
        ),
        row=2, col=1
    )

    # Update layout
    fig.update_layout(
        title=dict(
            text=f'{strategy_name} - Trade Visualization',
            font=dict(size=16, color='#f3f4f6')
        ),
        template='plotly_dark',
        paper_bgcolor='#0f172a',
        plot_bgcolor='#1e293b',
        height=600,
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        xaxis=dict(
            rangeslider=dict(visible=True, thickness=0.05),
            type='date'
        ),
        yaxis=dict(
            title='Price (USD)',
            tickformat='$,.0f',
            gridcolor='#334155'
        ),
        yaxis2=dict(
            title='Portfolio (USD)',
            tickformat='$,.0f',
            gridcolor='#334155'
        ),
        xaxis2=dict(gridcolor='#334155'),
    )

    # Add range selector buttons
    fig.update_xaxes(
        rangeselector=dict(
            buttons=[
                dict(count=1, label='1M', step='month', stepmode='backward'),
                dict(count=3, label='3M', step='month', stepmode='backward'),
                dict(count=6, label='6M', step='month', stepmode='backward'),
                dict(count=1, label='1Y', step='year', stepmode='backward'),
                dict(step='all', label='All')
            ],
            bgcolor='#1e293b',
            activecolor='#3b82f6',
            font=dict(color='#f3f4f6')
        ),
        row=1, col=1
    )

    # Convert to HTML div (not full page)
    html = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={
            'displayModeBar': True,
            'scrollZoom': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            'displaylogo': False
        }
    )

    return html


# =============================================================================
# MONTE CARLO SIMULATION
# =============================================================================

def run_monte_carlo(trades: list, init_cash: float = 10000, n_simulations: int = 1000,
                    seed: int = 42) -> dict:
    """
    Run Monte Carlo simulation by shuffling trade order.

    This tests whether strategy performance depends on lucky trade sequencing
    or represents a genuine edge.

    NOTE: For multiplicative returns, the FINAL return is always the same
    (multiplication is commutative). What changes is the PATH - specifically
    the maximum drawdown experienced along the way.

    Args:
        trades: List of trade dicts with 'return_pct' field
        init_cash: Starting capital
        n_simulations: Number of random shuffles to run
        seed: Random seed for reproducibility

    Returns:
        Dict with Monte Carlo statistics and distributions
    """
    if not trades or len(trades) < 2:
        return {
            'n_simulations': 0,
            'original_return': 0,
            'returns': [],
            'max_drawdowns': [],
            'percentiles': {}
        }

    np.random.seed(seed)

    # Extract trade returns
    trade_returns = np.array([t.get('return_pct', 0) / 100 for t in trades])
    n_trades = len(trade_returns)

    # Count winners/losers for context
    n_winners = int(np.sum(trade_returns > 0))
    n_losers = int(np.sum(trade_returns < 0))
    win_rate = n_winners / n_trades * 100

    # Store results
    max_drawdowns = []
    underwater_periods = []  # How many trades until recovery from drawdown
    worst_streaks = []  # Consecutive losing trades

    for i in range(n_simulations):
        # Shuffle trade order
        shuffled_returns = np.random.permutation(trade_returns)

        # Build equity curve
        equity = [init_cash]
        for ret in shuffled_returns:
            equity.append(equity[-1] * (1 + ret))

        equity = np.array(equity)

        # Calculate max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak * 100
        max_dd = np.max(drawdown)
        max_drawdowns.append(max_dd)

        # Calculate underwater period (trades below peak)
        underwater = np.sum(equity < peak)
        underwater_periods.append(underwater)

        # Calculate worst losing streak
        streak = 0
        max_streak = 0
        for ret in shuffled_returns:
            if ret < 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        worst_streaks.append(max_streak)

    max_drawdowns = np.array(max_drawdowns)
    underwater_periods = np.array(underwater_periods)
    worst_streaks = np.array(worst_streaks)

    # Calculate original (non-shuffled) metrics
    original_equity = [init_cash]
    for ret in trade_returns:
        original_equity.append(original_equity[-1] * (1 + ret))
    original_equity = np.array(original_equity)
    original_return = (original_equity[-1] / original_equity[0] - 1) * 100

    original_peak = np.maximum.accumulate(original_equity)
    original_dd = np.max((original_peak - original_equity) / original_peak * 100)

    # Final return is always the same (multiplication is commutative)
    # But we track variation in path metrics
    percentiles = {
        'return_5th': round(original_return, 2),  # Same for all
        'return_50th': round(original_return, 2),
        'return_95th': round(original_return, 2),
        'return_mean': round(original_return, 2),
        'return_std': 0.0,  # No variance in final return
        'dd_5th': float(np.percentile(max_drawdowns, 5)),
        'dd_25th': float(np.percentile(max_drawdowns, 25)),
        'dd_50th': float(np.percentile(max_drawdowns, 50)),
        'dd_75th': float(np.percentile(max_drawdowns, 75)),
        'dd_95th': float(np.percentile(max_drawdowns, 95)),
        'dd_max': float(np.max(max_drawdowns)),
        'dd_mean': float(np.mean(max_drawdowns)),
        'dd_std': float(np.std(max_drawdowns)),
        'underwater_mean': float(np.mean(underwater_periods)),
        'underwater_max': float(np.max(underwater_periods)),
        'worst_streak_mean': float(np.mean(worst_streaks)),
        'worst_streak_max': float(np.max(worst_streaks)),
    }

    # Risk metrics
    risk_of_20pct_dd = float(np.mean(max_drawdowns > 20) * 100)
    risk_of_30pct_dd = float(np.mean(max_drawdowns > 30) * 100)
    risk_of_50pct_dd = float(np.mean(max_drawdowns > 50) * 100)

    return {
        'n_simulations': n_simulations,
        'n_trades': n_trades,
        'n_winners': n_winners,
        'n_losers': n_losers,
        'win_rate': round(win_rate, 1),
        'original_return': round(original_return, 2),
        'original_max_dd': round(original_dd, 2),
        'percentiles': percentiles,
        'risk_of_20pct_dd': round(risk_of_20pct_dd, 2),
        'risk_of_30pct_dd': round(risk_of_30pct_dd, 2),
        'risk_of_50pct_dd': round(risk_of_50pct_dd, 2),
        'dd_distribution': [round(d, 2) for d in max_drawdowns.tolist()],
    }


# =============================================================================
# RANDOM FORWARD TESTING
# =============================================================================

def run_random_forward_test(df: pd.DataFrame, strategy_config: dict,
                            n_splits: int = 20, test_pct: float = 0.3,
                            min_test_days: int = 180, seed: int = 42) -> dict:
    """
    Run random forward testing by sampling different train/test splits.

    Unlike Monte Carlo (which shuffles existing trades), this tests if the
    strategy finds profitable trades across DIFFERENT time periods.

    Args:
        df: Full DataFrame with all data
        strategy_config: Strategy configuration dict
        n_splits: Number of random splits to test
        test_pct: Approximate percentage of data for test period
        min_test_days: Minimum test period length
        seed: Random seed for reproducibility

    Returns:
        Dict with random forward test statistics
    """
    np.random.seed(seed)

    if len(df) < min_test_days * 2:
        return {
            'n_splits': 0,
            'error': 'Insufficient data for random forward testing'
        }

    # Get strategy parameters
    entry_config = strategy_config.get('entry', {})
    exit_config = strategy_config.get('exit', {})
    entry_threshold = entry_config.get('required_conditions', 4)
    resolution = strategy_config.get('resolution', 'd1')

    # Parse exit parameters
    exit_conditions = exit_config.get('conditions', [])
    mvrv_threshold = 2.0
    ma_period = 50
    mvrv_ma_period = None
    use_daily_price_ma = False

    for c in exit_conditions:
        metric = c.get('metric', '')
        if metric == 'mvrv':
            mvrv_threshold = c.get('threshold', 2.0)
        elif metric.startswith('mvrv_ma_'):
            try:
                mvrv_ma_period = int(metric.split('_')[-1])
            except:
                pass

        metric_compare = c.get('metric_compare', '')
        if metric_compare.startswith('price_ma_'):
            if metric_compare.endswith('_daily'):
                use_daily_price_ma = True
                parts = metric_compare.replace('_daily', '').split('_')
            else:
                parts = metric_compare.split('_')
            try:
                ma_period = int(parts[-1])
            except:
                ma_period = 50

    # Calculate valid split range
    total_rows = len(df)
    min_train_rows = int(total_rows * 0.3)  # At least 30% for training

    # Determine row-based min test size
    if resolution in ['h1', 'hourly']:
        min_test_rows = min_test_days * 24
    elif resolution == 'h4':
        min_test_rows = min_test_days * 6
    elif resolution == 'h8':
        min_test_rows = min_test_days * 3
    else:
        min_test_rows = min_test_days

    # Valid split points: must leave enough for both train and test
    max_split_idx = total_rows - min_test_rows
    min_split_idx = min_train_rows

    if max_split_idx <= min_split_idx:
        return {
            'n_splits': 0,
            'error': 'Data range too small for meaningful splits'
        }

    # Generate random split points
    split_indices = np.random.randint(min_split_idx, max_split_idx, size=n_splits)

    # Run backtest for each split
    results = []

    for i, split_idx in enumerate(split_indices):
        try:
            train_df = df.iloc[:split_idx].copy()
            test_df = df.iloc[split_idx:].copy()

            if len(test_df) < 100:  # Skip if test period too small
                continue

            # Generate signals
            test_entries = generate_buy_the_dip_entries(test_df, threshold=entry_threshold)
            test_exits = generate_momentum_exit(
                test_df,
                mvrv_threshold=mvrv_threshold,
                ma_period=ma_period,
                mvrv_ma_period=mvrv_ma_period,
                use_daily_price_ma=use_daily_price_ma
            )

            # Skip if no entries
            if test_entries.sum() == 0:
                continue

            # Run backtest (simplified - just get key metrics)
            pf = vbt.Portfolio.from_signals(
                close=test_df['price'],
                entries=test_entries,
                exits=test_exits,
                size=0.2,  # 20% position size
                size_type='percent',
                fees=FEES,
                slippage=SLIPPAGE,
                init_cash=10000,
                freq=RESOLUTION_FREQ_MAP.get(resolution, '1D')
            )

            total_return = pf.total_return() * 100
            max_dd = pf.max_drawdown() * 100
            num_trades = pf.trades.count()
            win_rate = pf.trades.win_rate() * 100 if num_trades > 0 else 0
            sharpe = pf.sharpe_ratio()

            # Buy & hold benchmark
            bh_return = (test_df['price'].iloc[-1] / test_df['price'].iloc[0] - 1) * 100

            results.append({
                'split_idx': int(split_idx),
                'split_date': str(df.index[split_idx].date()),
                'test_start': str(test_df.index[0].date()),
                'test_end': str(test_df.index[-1].date()),
                'test_days': len(test_df),
                'return_pct': round(total_return, 2),
                'max_dd_pct': round(max_dd, 2),
                'num_trades': int(num_trades),
                'win_rate': round(win_rate, 1),
                'sharpe': round(sharpe, 2) if not np.isnan(sharpe) else 0,
                'bh_return': round(bh_return, 2),
                'vs_bh': round(total_return - bh_return, 2)
            })

        except Exception as e:
            # Skip failed splits silently
            continue

    if len(results) < 3:
        return {
            'n_splits': len(results),
            'error': 'Too few successful splits'
        }

    # Calculate statistics across all splits
    returns = np.array([r['return_pct'] for r in results])
    max_dds = np.array([r['max_dd_pct'] for r in results])
    trade_counts = np.array([r['num_trades'] for r in results])
    win_rates = np.array([r['win_rate'] for r in results])
    vs_bh = np.array([r['vs_bh'] for r in results])

    # How often strategy is profitable / beats B&H
    pct_profitable = float(np.mean(returns > 0) * 100)
    pct_beats_bh = float(np.mean(vs_bh > 0) * 100)

    return {
        'n_splits': len(results),
        'splits': results,
        'statistics': {
            'return_mean': round(float(np.mean(returns)), 2),
            'return_std': round(float(np.std(returns)), 2),
            'return_min': round(float(np.min(returns)), 2),
            'return_max': round(float(np.max(returns)), 2),
            'return_5th': round(float(np.percentile(returns, 5)), 2),
            'return_25th': round(float(np.percentile(returns, 25)), 2),
            'return_50th': round(float(np.percentile(returns, 50)), 2),
            'return_75th': round(float(np.percentile(returns, 75)), 2),
            'return_95th': round(float(np.percentile(returns, 95)), 2),
            'dd_mean': round(float(np.mean(max_dds)), 2),
            'dd_std': round(float(np.std(max_dds)), 2),
            'dd_worst': round(float(np.min(max_dds)), 2),  # Most negative
            'dd_best': round(float(np.max(max_dds)), 2),   # Least negative
            'trades_mean': round(float(np.mean(trade_counts)), 1),
            'trades_std': round(float(np.std(trade_counts)), 1),
            'win_rate_mean': round(float(np.mean(win_rates)), 1),
            'win_rate_std': round(float(np.std(win_rates)), 1),
            'pct_profitable': round(pct_profitable, 1),
            'pct_beats_bh': round(pct_beats_bh, 1),
        }
    }


# =============================================================================
# VECTORBT BACKTESTING
# =============================================================================

def backtest_with_vectorbt(df: pd.DataFrame, entries: pd.Series, exits: pd.Series,
                           name: str = "Strategy",
                           stop_loss: float = None,
                           resolution: str = 'daily') -> dict:
    """
    Run backtest using VectorBT.
    VectorBT handles position sizing, fees, and statistics automatically.

    Args:
        df: DataFrame with price and metric data
        entries: Boolean Series for entry signals
        exits: Boolean Series for exit signals
        name: Strategy name for display
        stop_loss: Stop loss percentage (e.g., 0.10 for 10%). None uses default.
        resolution: Data resolution for frequency setting
    """
    print(f"\nBacktesting: {name}")

    # Use provided stop_loss or default
    sl_pct = stop_loss if stop_loss is not None else STOP_LOSS_PCT

    # Calculate position size based on risk parameters
    # Position % = Risk % / Stop Loss %
    # e.g., 2% risk / 10% stop = 20% of portfolio per trade
    position_size_pct = RISK_PER_TRADE / sl_pct

    # Get frequency from resolution
    freq = RESOLUTION_FREQ_MAP.get(resolution, '1D')

    print(f"  Stop Loss: {sl_pct*100:.1f}% | Position Size: {position_size_pct*100:.0f}% | Freq: {freq}")

    # Create portfolio with VectorBT using risk-based position sizing
    pf = vbt.Portfolio.from_signals(
        close=df['price'],
        entries=entries,
        exits=exits,
        size=position_size_pct,
        size_type='percent',
        fees=FEES,
        slippage=SLIPPAGE,
        init_cash=INIT_CASH,
        freq=freq,
        sl_stop=sl_pct,  # Stop-loss below entry
        accumulate=False  # Don't add to existing positions
    )

    # Get statistics
    stats = pf.stats()

    # Extract key metrics
    total_return = pf.total_return() * 100
    num_trades = pf.trades.count()
    win_rate = pf.trades.win_rate() * 100 if num_trades > 0 else 0
    sharpe = pf.sharpe_ratio()
    max_dd = pf.max_drawdown() * 100

    # Get equity curve as list of [timestamp, value] pairs
    equity = pf.value()
    equity_curve = [
        [int(ts.timestamp() * 1000), float(val)]
        for ts, val in zip(equity.index, equity.values)
    ]

    # Get trade records if any
    trades_data = []
    if num_trades > 0:
        try:
            trades_df = pf.trades.records_readable
            running_balance = INIT_CASH
            for _, trade in trades_df.iterrows():
                pnl = float(trade.get('PnL', 0))
                entry_price = float(trade.get('Avg Entry Price', 0))
                exit_price = float(trade.get('Avg Exit Price', 0))
                size_btc = float(trade.get('Size', 0))
                position_usd = entry_price * size_btc if entry_price and size_btc else 0
                balance_before = running_balance
                running_balance += pnl

                # Portfolio return (impact on total portfolio), not position return
                portfolio_return_pct = (pnl / balance_before) * 100 if balance_before > 0 else 0

                # Determine exit type based on exit price vs stop level
                stop_price = entry_price * (1 - STOP_LOSS_PCT)
                if exit_price <= stop_price * 1.01:  # 1% tolerance for stop-loss
                    exit_type = 'STOP'
                else:
                    exit_type = 'SIGNAL'

                # Get entry/exit timestamps for metric lookup
                entry_ts = trade.get('Entry Timestamp')
                exit_ts = trade.get('Exit Timestamp')

                # Capture entry trigger values (all 5 Buy The Dip conditions)
                entry_triggers = {}
                if entry_ts is not None and entry_ts in df.index:
                    row = df.loc[entry_ts]
                    # Calculate derived metrics
                    rpl_ratio = float(row.get('realized_profit', 0)) / float(row.get('realized_loss', 1)) if row.get('realized_loss', 0) > 0 else 0
                    liq_ratio = float(row.get('liq_long', 0)) / float(row.get('liq_short', 1)) if row.get('liq_short', 0) > 0 else 0

                    entry_triggers = {
                        'mvrv_sth': round(float(row.get('mvrv_sth', 0)), 3) if 'mvrv_sth' in df.columns else None,
                        'sopr_sth': round(float(row.get('sopr_sth', 0)), 3) if 'sopr_sth' in df.columns else None,
                        'rpl_ratio': round(rpl_ratio, 3),
                        'funding': round(float(row.get('funding', 0)), 4) if 'funding' in df.columns else None,
                        'liq_ratio': round(liq_ratio, 2),
                    }

                # Capture exit trigger values
                exit_triggers = {}
                if exit_type == 'STOP':
                    exit_triggers = {'reason': 'Stop-loss triggered'}
                elif exit_ts is not None and exit_ts in df.index:
                    row = df.loc[exit_ts]
                    ma50 = row.get('price_ma50', row.get('price', 0) * 0.9)  # fallback
                    exit_triggers = {
                        'mvrv': round(float(row.get('mvrv', 0)), 3) if 'mvrv' in df.columns else None,
                        'price_vs_ma50': 'below' if row.get('price', 0) < ma50 else 'above',
                    }

                trades_data.append({
                    'entry_date': str(trade.get('Entry Timestamp', '')),
                    'exit_date': str(trade.get('Exit Timestamp', '')),
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'stop_price': round(stop_price, 2),
                    'size_btc': round(size_btc, 6),
                    'size_usd': round(position_usd, 2),
                    'pnl': pnl,
                    'return_pct': round(portfolio_return_pct, 2),
                    'direction': str(trade.get('Direction', 'Long')),
                    'exit_type': exit_type,
                    'entry_triggers': entry_triggers,
                    'exit_triggers': exit_triggers,
                    'balance_before': round(balance_before, 2),
                    'balance_after': round(running_balance, 2)
                })
        except Exception as e:
            print(f"  Warning: Could not extract trade details: {e}")

    # Calculate additional metrics
    try:
        avg_hold_time = pf.trades.duration.mean().days if num_trades > 0 else 0
    except Exception:
        avg_hold_time = 0

    # Extract additional stats from VectorBT (built-in)
    def safe_float(val, default=0):
        """Safely convert to float, handling NaN and inf."""
        try:
            f = float(val)
            return default if (np.isnan(f) or np.isinf(f)) else f
        except:
            return default

    sortino = safe_float(stats.get('Sortino Ratio', 0))
    calmar = safe_float(stats.get('Calmar Ratio', 0))
    omega = safe_float(stats.get('Omega Ratio', 0))
    profit_factor = safe_float(stats.get('Profit Factor', 0))
    expectancy = safe_float(stats.get('Expectancy', 0))
    avg_win_pct = safe_float(stats.get('Avg Winning Trade [%]', 0))
    avg_loss_pct = safe_float(stats.get('Avg Losing Trade [%]', 0))
    best_trade = safe_float(stats.get('Best Trade [%]', 0))
    worst_trade = safe_float(stats.get('Worst Trade [%]', 0))
    max_dd_duration = stats.get('Max Drawdown Duration', pd.Timedelta(0))
    max_dd_days = max_dd_duration.days if hasattr(max_dd_duration, 'days') else 0

    print(f"  Position Size: {position_size_pct*100:.0f}% (Risk: {RISK_PER_TRADE*100:.0f}%, Stop: {STOP_LOSS_PCT*100:.0f}%)")
    print(f"  Total Return: {total_return:.1f}%")
    print(f"  Trades: {num_trades}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Sharpe: {sharpe:.2f}")
    print(f"  Max DD: {max_dd:.1f}%")

    return {
        'name': name,
        'total_return': total_return,
        'num_trades': int(num_trades),
        'win_rate': win_rate,
        'sharpe': float(sharpe) if not np.isnan(sharpe) else 0,
        'sortino': round(sortino, 2),
        'calmar': round(calmar, 2),
        'omega': round(omega, 2),
        'profit_factor': round(profit_factor, 2),
        'expectancy': round(expectancy, 2),
        'avg_win_pct': round(avg_win_pct, 2),
        'avg_loss_pct': round(avg_loss_pct, 2),
        'best_trade': round(best_trade, 2),
        'worst_trade': round(worst_trade, 2),
        'max_dd': max_dd,
        'max_dd_days': max_dd_days,
        'avg_hold_days': avg_hold_time,
        'equity_curve': equity_curve,
        'trades': trades_data,
        'portfolio': pf,
        'stats': stats
    }


# =============================================================================
# WALK-FORWARD TESTING
# =============================================================================

def run_walk_forward(df: pd.DataFrame, n_folds: int = 5):
    """
    Run walk-forward analysis with expanding window.

    Walk-forward tests the strategy on multiple out-of-sample periods:
    - Fold 1: Train on 20% of data, test on next 20%
    - Fold 2: Train on 40% of data, test on next 20%
    - Fold 3: Train on 60% of data, test on next 20%
    - etc.

    This validates the strategy works across different market regimes.
    """
    print("\n" + "=" * 80)
    print(f"WALK-FORWARD ANALYSIS ({n_folds} folds)")
    print("=" * 80)

    total_days = len(df)
    fold_size = total_days // n_folds

    results = {
        'STRAT-005 Momentum Exit': [],
        'LTH Distribution': [],
        'Buy & Hold': []
    }

    fold_info = []

    for fold in range(1, n_folds):
        # Expanding window: train on all data up to fold boundary
        train_end_idx = fold * fold_size
        test_start_idx = train_end_idx
        test_end_idx = min(test_start_idx + fold_size, total_days)

        train_df = df.iloc[:train_end_idx].copy()
        test_df = df.iloc[test_start_idx:test_end_idx].copy()

        if len(train_df) < 100 or len(test_df) < 30:
            continue

        train_start = train_df.index[0].strftime('%Y-%m-%d')
        train_end = train_df.index[-1].strftime('%Y-%m-%d')
        test_start = test_df.index[0].strftime('%Y-%m-%d')
        test_end = test_df.index[-1].strftime('%Y-%m-%d')

        print(f"\n--- Fold {fold} ---")
        print(f"Train: {train_start} to {train_end} ({len(train_df)} days)")
        print(f"Test:  {test_start} to {test_end} ({len(test_df)} days)")

        fold_info.append({
            'fold': fold,
            'train_start': train_start,
            'train_end': train_end,
            'test_start': test_start,
            'test_end': test_end,
            'train_days': len(train_df),
            'test_days': len(test_df)
        })

        # Generate signals for test period
        test_entries = generate_buy_the_dip_entries(test_df)

        # STRAT-005 Momentum Exit
        test_momentum_exits = generate_momentum_exit(test_df, mvrv_threshold=2.0, ma_period=50)
        strat005_result = backtest_with_vectorbt(test_df, test_entries, test_momentum_exits,
                                                  "STRAT-005")
        results['STRAT-005 Momentum Exit'].append({
            'fold': fold,
            'return': strat005_result['total_return'],
            'trades': strat005_result['num_trades'],
            'win_rate': strat005_result['win_rate'],
            'sharpe': strat005_result['sharpe'],
            'max_dd': strat005_result['max_dd']
        })

        # LTH Distribution
        test_lth_exits = generate_lth_distribution_exits(test_df)
        lth_result = backtest_with_vectorbt(test_df, test_entries, test_lth_exits,
                                            "LTH Dist")
        results['LTH Distribution'].append({
            'fold': fold,
            'return': lth_result['total_return'],
            'trades': lth_result['num_trades'],
            'win_rate': lth_result['win_rate'],
            'sharpe': lth_result['sharpe'],
            'max_dd': lth_result['max_dd']
        })

        # Buy & Hold
        bh_return = (test_df['price'].iloc[-1] / test_df['price'].iloc[0] - 1) * 100
        results['Buy & Hold'].append({
            'fold': fold,
            'return': bh_return,
            'trades': 1,
            'win_rate': 100 if bh_return > 0 else 0,
            'sharpe': 0,
            'max_dd': 0
        })

    # Summary
    print("\n" + "=" * 80)
    print("WALK-FORWARD SUMMARY")
    print("=" * 80)

    print(f"\n{'Strategy':<25} {'Avg Return':>12} {'Win Folds':>12} {'Avg Sharpe':>12} {'vs B&H':>10}")
    print("-" * 75)

    summary = {}
    bh_returns = [r['return'] for r in results['Buy & Hold']]

    for strategy, fold_results in results.items():
        if not fold_results:
            continue

        returns = [r['return'] for r in fold_results]
        sharpes = [r['sharpe'] for r in fold_results]

        avg_return = np.mean(returns)
        win_folds = sum(1 for r in returns if r > 0)
        total_folds = len(returns)
        avg_sharpe = np.mean([s for s in sharpes if s != 0]) if any(s != 0 for s in sharpes) else 0

        # Calculate how many folds beat B&H
        beats_bh = sum(1 for r, bh in zip(returns, bh_returns) if r > bh)

        summary[strategy] = {
            'avg_return': avg_return,
            'win_folds': win_folds,
            'total_folds': total_folds,
            'avg_sharpe': avg_sharpe,
            'beats_bh': beats_bh,
            'fold_returns': returns
        }

        beats_str = f"{beats_bh}/{total_folds}" if strategy != 'Buy & Hold' else "-"
        print(f"{strategy:<25} {avg_return:>+11.1f}% {win_folds:>6}/{total_folds:<5} {avg_sharpe:>11.2f} {beats_str:>10}")

    return {
        'folds': fold_info,
        'results': results,
        'summary': summary
    }


# =============================================================================
# STRATEGY-BASED BACKTEST
# =============================================================================

def run_strategy_backtest(strategy_config: dict, df: pd.DataFrame,
                          include_walk_forward: bool = False) -> dict:
    """
    Run a complete backtest for a strategy config and return results.

    Args:
        strategy_config: Strategy configuration dict
        df: DataFrame with all required metrics
        include_walk_forward: Whether to include walk-forward analysis

    Returns:
        Dict with complete backtest results
    """
    strategy_id = strategy_config.get('id', 'unknown')
    strategy_name = strategy_config.get('name', 'Unknown Strategy')

    # Extract risk management settings from config
    risk_config = strategy_config.get('risk_management', {})
    stop_loss = risk_config.get('stop_loss_pct')
    if stop_loss is not None:
        stop_loss = stop_loss / 100 if stop_loss > 1 else stop_loss  # Convert % to decimal

    # Extract resolution from config
    resolution = strategy_config.get('resolution', 'daily')

    print(f"\n{'=' * 80}")
    print(f"BACKTESTING: {strategy_id} - {strategy_name}")
    print(f"Resolution: {resolution} | Stop Loss: {stop_loss*100 if stop_loss else STOP_LOSS_PCT*100:.0f}%")
    print(f"{'=' * 80}")

    # Split train/test
    train_df = df[df.index <= TRAIN_END].copy()
    test_df = df[df.index >= TEST_START].copy()

    print(f"\nData periods:")
    print(f"  Train: {train_df.index[0].date()} to {train_df.index[-1].date()} ({len(train_df)} days)")
    print(f"  Test:  {test_df.index[0].date()} to {test_df.index[-1].date()} ({len(test_df)} days)")

    # Generate entry signals (Buy The Dip for now - can be extended based on config)
    entry_config = strategy_config.get('entry', {})
    entry_logic = entry_config.get('logic', 'COUNT_THRESHOLD')
    entry_threshold = entry_config.get('required_conditions', 4)  # Default 4/5 threshold

    train_entries = generate_buy_the_dip_entries(train_df, threshold=entry_threshold)
    test_entries = generate_buy_the_dip_entries(test_df, threshold=entry_threshold)

    # Generate exit signals based on strategy config
    exit_config = strategy_config.get('exit', {})
    exit_conditions = exit_config.get('conditions', [])

    # Determine exit type from config
    has_mvrv_exit = any(c.get('metric', '').startswith('mvrv') for c in exit_conditions)
    has_momentum_exit = any(c.get('metric_compare', '').startswith('price_ma') for c in exit_conditions)
    has_lth_sopr = any(c.get('metric') == 'sopr_lth' for c in exit_conditions)

    if has_mvrv_exit and has_momentum_exit:
        # STRAT-005 style: MVRV + Momentum
        mvrv_threshold = 2.0
        ma_period = 50
        mvrv_ma_period = None  # None = raw MVRV, int = smoothed MVRV
        use_daily_price_ma = False  # True = use daily price for MA calculation
        for c in exit_conditions:
            metric = c.get('metric', '')
            if metric == 'mvrv':
                mvrv_threshold = c.get('threshold', 2.0)
            elif metric.startswith('mvrv_ma_'):
                # MVRV with MA smoothing (e.g., mvrv_ma_500)
                mvrv_threshold = c.get('threshold', 2.0)
                try:
                    mvrv_ma_period = int(metric.split('_')[-1])
                except:
                    mvrv_ma_period = None
            metric_compare = c.get('metric_compare', '')
            if metric_compare.startswith('price_ma_'):
                # Check for _daily suffix (e.g., price_ma_50_daily)
                if metric_compare.endswith('_daily'):
                    use_daily_price_ma = True
                    # Extract period from price_ma_XX_daily
                    parts = metric_compare.replace('_daily', '').split('_')
                    try:
                        ma_period = int(parts[-1])
                    except:
                        ma_period = 50
                else:
                    # Standard hourly MA (e.g., price_ma_1200)
                    try:
                        ma_period = int(metric_compare.split('_')[-1])
                    except:
                        ma_period = 50

        train_exits = generate_momentum_exit(train_df, mvrv_threshold, ma_period, mvrv_ma_period, use_daily_price_ma)
        test_exits = generate_momentum_exit(test_df, mvrv_threshold, ma_period, mvrv_ma_period, use_daily_price_ma)
        mvrv_desc = f"MVRV_MA{mvrv_ma_period}" if mvrv_ma_period else "MVRV"
        price_desc = f"Price<MA{ma_period}d" if use_daily_price_ma else f"Price<MA{ma_period}h"
        exit_description = f"Momentum Exit ({mvrv_desc}>{mvrv_threshold} AND {price_desc})"

    elif has_mvrv_exit and has_lth_sopr:
        # LTH Distribution style
        train_exits = generate_lth_distribution_exits(train_df)
        test_exits = generate_lth_distribution_exits(test_df)
        exit_description = "LTH Distribution (MVRV>2 AND LTH-SOPR>1.5)"

    else:
        # Default to LTH Distribution
        train_exits = generate_lth_distribution_exits(train_df)
        test_exits = generate_lth_distribution_exits(test_df)
        exit_description = "LTH Distribution (default)"

    print(f"\nExit strategy: {exit_description}")

    # Run backtests
    print(f"\n--- Train Period ---")
    train_result = backtest_with_vectorbt(
        train_df, train_entries, train_exits,
        name=f"{strategy_id} (Train)",
        stop_loss=stop_loss,
        resolution=resolution
    )

    print(f"\n--- Test Period (Out-of-Sample) ---")
    test_result = backtest_with_vectorbt(
        test_df, test_entries, test_exits,
        name=f"{strategy_id} (Test)",
        stop_loss=stop_loss,
        resolution=resolution
    )

    # Buy & Hold benchmark
    bh_train = (train_df['price'].iloc[-1] / train_df['price'].iloc[0] - 1) * 100
    bh_test = (test_df['price'].iloc[-1] / test_df['price'].iloc[0] - 1) * 100

    print(f"\nBenchmark (Buy & Hold):")
    print(f"  Train: {bh_train:+.1f}%")
    print(f"  Test:  {bh_test:+.1f}%")

    # Generate interactive trade chart
    print(f"\n--- Generating Trade Chart ---")
    trade_chart_html = ""
    if PLOTLY_AVAILABLE and test_result.get('trades'):
        trade_chart_html = generate_trade_chart(test_df, test_result['trades'], strategy_name)
        print(f"  ✓ Interactive chart generated")
    else:
        print(f"  ⚠ Chart skipped (no trades or Plotly unavailable)")

    # Monte Carlo simulation
    print(f"\n--- Monte Carlo Simulation ---")
    mc_result = None
    test_trades = test_result.get('trades', [])
    if len(test_trades) >= 2:
        mc_result = run_monte_carlo(test_trades, n_simulations=1000)
        print(f"  Simulations: {mc_result['n_simulations']}")
        print(f"  Trades: {mc_result['n_trades']} ({mc_result['n_winners']}W/{mc_result['n_losers']}L)")
        print(f"  Return: {mc_result['original_return']:+.1f}%")
        print(f"  Max DD: {mc_result['original_max_dd']:.1f}% (actual)")
        print(f"  MC DD Range: {mc_result['percentiles']['dd_5th']:.1f}% - {mc_result['percentiles']['dd_95th']:.1f}%")
    else:
        print(f"  Skipped (need >= 2 trades, have {len(test_trades)})")

    # Random Forward Testing
    print(f"\n--- Random Forward Testing ---")
    rft_result = None
    try:
        rft_result = run_random_forward_test(df, strategy_config, n_splits=20)
        if rft_result.get('n_splits', 0) >= 3:
            stats = rft_result['statistics']
            print(f"  Splits tested: {rft_result['n_splits']}")
            print(f"  Return range: {stats['return_5th']:.1f}% to {stats['return_95th']:.1f}%")
            print(f"  Return mean: {stats['return_mean']:.1f}% (std: {stats['return_std']:.1f}%)")
            print(f"  Profitable: {stats['pct_profitable']:.0f}% of splits")
            print(f"  Beats B&H: {stats['pct_beats_bh']:.0f}% of splits")
        else:
            print(f"  Skipped ({rft_result.get('error', 'insufficient splits')})")
            rft_result = None
    except Exception as e:
        print(f"  Error: {e}")

    # Walk-forward analysis
    wf_result = None
    if include_walk_forward:
        print(f"\n--- Walk-Forward Analysis ---")
        wf_raw = run_walk_forward_for_strategy(df, strategy_config)
        if wf_raw:
            wf_result = {
                'n_folds': len(wf_raw['folds']),
                'folds': wf_raw['folds'],
                'summary': wf_raw['summary']
            }

    # Build results dict
    results = {
        "data_range": {
            "start": str(df.index[0].date()),
            "end": str(df.index[-1].date()),
            "total_days": len(df)
        },
        "train_period": {
            "start": str(train_df.index[0].date()),
            "end": str(train_df.index[-1].date()),
            "days": len(train_df)
        },
        "test_period": {
            "start": str(test_df.index[0].date()),
            "end": str(test_df.index[-1].date()),
            "days": len(test_df)
        },
        "exit_strategy": exit_description,
        "position_sizing": {
            "type": "risk_based",
            "risk_per_trade_pct": RISK_PER_TRADE * 100,
            "stop_loss_pct": STOP_LOSS_PCT * 100,
            "position_size_pct": (RISK_PER_TRADE / STOP_LOSS_PCT) * 100
        },
        "train": {
            "return_pct": round(train_result['total_return'], 2),
            "sharpe": round(train_result['sharpe'], 2),
            "sortino": train_result.get('sortino', 0),
            "calmar": train_result.get('calmar', 0),
            "omega": train_result.get('omega', 0),
            "profit_factor": train_result.get('profit_factor', 0),
            "expectancy": train_result.get('expectancy', 0),
            "avg_win_pct": train_result.get('avg_win_pct', 0),
            "avg_loss_pct": train_result.get('avg_loss_pct', 0),
            "best_trade": train_result.get('best_trade', 0),
            "worst_trade": train_result.get('worst_trade', 0),
            "max_dd": round(train_result['max_dd'], 2),
            "max_dd_days": train_result.get('max_dd_days', 0),
            "num_trades": train_result['num_trades'],
            "win_rate": round(train_result['win_rate'], 2),
            "avg_hold_days": train_result.get('avg_hold_days', 0)
        },
        "test": {
            "return_pct": round(test_result['total_return'], 2),
            "sharpe": round(test_result['sharpe'], 2),
            "sortino": test_result.get('sortino', 0),
            "calmar": test_result.get('calmar', 0),
            "omega": test_result.get('omega', 0),
            "profit_factor": test_result.get('profit_factor', 0),
            "expectancy": test_result.get('expectancy', 0),
            "avg_win_pct": test_result.get('avg_win_pct', 0),
            "avg_loss_pct": test_result.get('avg_loss_pct', 0),
            "best_trade": test_result.get('best_trade', 0),
            "worst_trade": test_result.get('worst_trade', 0),
            "max_dd": round(test_result['max_dd'], 2),
            "max_dd_days": test_result.get('max_dd_days', 0),
            "num_trades": test_result['num_trades'],
            "win_rate": round(test_result['win_rate'], 2),
            "avg_hold_days": test_result.get('avg_hold_days', 0)
        },
        "benchmark": {
            "train_return": round(bh_train, 2),
            "test_return": round(bh_test, 2),
            "equity_curve": [
                [int(ts.timestamp() * 1000), float(INIT_CASH * (1 + (p / test_df['price'].iloc[0] - 1)))]
                for ts, p in zip(test_df.index, test_df['price'].values)
            ]
        },
        "equity_curve": test_result.get('equity_curve', []),
        "trades": test_result.get('trades', []),
        "trade_chart_html": trade_chart_html,
        "monte_carlo": mc_result,
        "random_forward": rft_result,
        "walk_forward": wf_result
    }

    return results


def run_walk_forward_for_strategy(df: pd.DataFrame, strategy_config: dict, n_folds: int = 6) -> dict:
    """Run walk-forward analysis for a specific strategy."""
    strategy_id = strategy_config.get('id', 'unknown')

    total_days = len(df)
    fold_size = total_days // n_folds

    results = []
    fold_info = []
    bh_returns = []

    for fold in range(1, n_folds):
        train_end_idx = fold * fold_size
        test_start_idx = train_end_idx
        test_end_idx = min(test_start_idx + fold_size, total_days)

        train_df = df.iloc[:train_end_idx].copy()
        test_df = df.iloc[test_start_idx:test_end_idx].copy()

        if len(train_df) < 100 or len(test_df) < 30:
            continue

        fold_info.append({
            'fold': fold,
            'train_start': train_df.index[0].strftime('%Y-%m-%d'),
            'train_end': train_df.index[-1].strftime('%Y-%m-%d'),
            'test_start': test_df.index[0].strftime('%Y-%m-%d'),
            'test_end': test_df.index[-1].strftime('%Y-%m-%d'),
            'train_days': len(train_df),
            'test_days': len(test_df)
        })

        # Generate signals
        test_entries = generate_buy_the_dip_entries(test_df)

        # Determine exit type from config
        exit_config = strategy_config.get('exit', {})
        exit_conditions = exit_config.get('conditions', [])
        has_momentum = any(c.get('metric_compare', '').startswith('price_ma') for c in exit_conditions)

        if has_momentum:
            test_exits = generate_momentum_exit(test_df, 2.0, 50)
        else:
            test_exits = generate_lth_distribution_exits(test_df)

        # Run backtest (quiet mode)
        pf = vbt.Portfolio.from_signals(
            close=test_df['price'],
            entries=test_entries,
            exits=test_exits,
            fees=FEES,
            slippage=SLIPPAGE,
            init_cash=10000,
            freq='1D'
        )

        results.append({
            'fold': fold,
            'return': pf.total_return() * 100,
            'trades': pf.trades.count(),
            'sharpe': float(pf.sharpe_ratio()) if not np.isnan(pf.sharpe_ratio()) else 0,
            'max_dd': pf.max_drawdown() * 100
        })

        bh_return = (test_df['price'].iloc[-1] / test_df['price'].iloc[0] - 1) * 100
        bh_returns.append(bh_return)

    if not results:
        return None

    # Build summary
    returns = [r['return'] for r in results]
    sharpes = [r['sharpe'] for r in results]

    summary = {
        strategy_id: {
            'avg_return': round(np.mean(returns), 2),
            'win_folds': sum(1 for r in returns if r > 0),
            'total_folds': len(returns),
            'avg_sharpe': round(np.mean([s for s in sharpes if s != 0]) if any(s != 0 for s in sharpes) else 0, 2),
            'beats_bh': sum(1 for r, bh in zip(returns, bh_returns) if r > bh),
            'fold_returns': [round(r, 2) for r in returns]
        },
        'Buy & Hold': {
            'avg_return': round(np.mean(bh_returns), 2),
            'win_folds': sum(1 for r in bh_returns if r > 0),
            'total_folds': len(bh_returns),
            'avg_sharpe': 0,
            'beats_bh': 0,
            'fold_returns': [round(r, 2) for r in bh_returns]
        }
    }

    return {
        'folds': fold_info,
        'results': results,
        'summary': summary
    }


# =============================================================================
# MAIN
# =============================================================================

def print_smoothing_comparison(outputs: list):
    """Print comparison table across smoothing windows."""
    print(f"\n{'=' * 80}")
    print("SMOOTHING COMPARISON")
    print(f"{'=' * 80}")
    print(f"\n{'Window':<10} {'Train Return':>14} {'Test Return':>13} {'Test Sharpe':>13} "
          f"{'Test MaxDD':>12} {'Test Trades':>13} {'Test WinRate':>13}")
    print("-" * 88)

    for results_path, window, results in outputs:
        label = f"MA-{window}" if window else "Raw"
        train = results.get('train', {})
        test = results.get('test', {})
        train_ret = train.get('return_pct', 0)
        test_ret = test.get('return_pct', 0)
        test_sharpe = test.get('sharpe', 0)
        test_dd = test.get('max_dd', 0)
        test_trades = test.get('num_trades', 0)
        test_wr = test.get('win_rate', 0)
        print(f"{label:<10} {train_ret:>+13.1f}% {test_ret:>+12.1f}% {test_sharpe:>13.2f} "
              f"{test_dd:>11.1f}% {test_trades:>13} {test_wr:>12.1f}%")

    print()


def parse_smoothing_windows(smoothing_arg: str) -> list:
    """Parse --smoothing argument into list of window sizes."""
    if smoothing_arg is None:
        return [None]  # No smoothing — single run with raw data
    if smoothing_arg.lower() == 'all':
        return VALID_SMOOTHING_WINDOWS
    try:
        window = int(smoothing_arg)
        if window not in VALID_SMOOTHING_WINDOWS:
            print(f"⚠ Smoothing window {window} not in standard set {VALID_SMOOTHING_WINDOWS}")
            print(f"  Using it anyway.")
        return [window]
    except ValueError:
        print(f"✗ Invalid --smoothing value: '{smoothing_arg}'. Use a number or 'all'.")
        sys.exit(1)


def run_backtest_for_config(config: dict, df_raw: pd.DataFrame, smoothing_windows: list,
                            include_walk_forward: bool = False) -> list:
    """Run backtest(s) for a config across one or more smoothing windows.

    Args:
        config: Strategy configuration dict
        df_raw: Raw (unsmoothed) DataFrame
        smoothing_windows: List of window sizes (None = no smoothing)
        include_walk_forward: Whether to include walk-forward analysis

    Returns:
        List of (results_path, window, results) tuples
    """
    outputs = []
    for window in smoothing_windows:
        if window is not None:
            print(f"\n{'=' * 80}")
            print(f"SMOOTHING: MA-{window}")
            print(f"{'=' * 80}")
            df = apply_smoothing(df_raw, window)
            # Tag config so results file gets a unique name
            config['_smoothing_window'] = window
        else:
            df = df_raw
            config.pop('_smoothing_window', None)

        results = run_strategy_backtest(config, df, include_walk_forward=include_walk_forward)

        # Add smoothing metadata to results
        if window is not None:
            results['smoothing'] = {
                'window': window,
                'label': f'MA-{window}',
                'smoothed_columns': [c for c in SMOOTH_COLUMNS if c in df_raw.columns]
            }

        results_path = save_strategy_results(config, results)
        label = f" (MA-{window})" if window else ""
        print(f"\n{'=' * 80}")
        print(f"✓ Results{label} saved to: {results_path}")
        print(f"{'=' * 80}")
        outputs.append((results_path, window, results))

    return outputs


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='VectorBT Strategy Backtester')
    parser.add_argument('--config', '-c', type=str, help='Path to strategy config JSON file')
    parser.add_argument('--strategy', '-s', type=str, help='Strategy ID to backtest (e.g., strat005)')
    parser.add_argument('--resolution', '-r', type=str, default='daily',
                        choices=['daily', 'd1', 'h1', 'h4', 'h8', 'h12'],
                        help='Data resolution: daily, h1, h4, h8, h12 (default: daily)')
    parser.add_argument('--stop-loss', type=float, help='Stop loss percentage (e.g., 10 for 10%%)')
    parser.add_argument('--list', '-l', action='store_true', help='List available strategies')
    parser.add_argument('--all', '-a', action='store_true', help='Run backtest for all strategies')
    parser.add_argument('--smoothing', type=str, default=None,
                        help='MA smoothing window for signal metrics. '
                             'Use a number (4,6,8,12) or "all" to run all windows.')
    parser.add_argument('--walk-forward', '-w', action='store_true', help='Include walk-forward analysis')
    parser.add_argument('--debug', '-d', action='store_true', help='Show detailed debug output')
    return parser.parse_args()


def main():
    args = parse_args()

    # List mode
    if args.list:
        print("=" * 80)
        print("AVAILABLE STRATEGIES")
        print("=" * 80)
        strategies = list_strategies()
        print(f"\n{'ID':<15} {'Name':<45} {'Status':<20}")
        print("-" * 80)
        for s in strategies:
            print(f"{s['id']:<15} {s['name'][:44]:<45} {s['status']:<20}")
        print(f"\nTotal: {len(strategies)} strategies")
        print("\nUsage: python backtest_vectorbt.py --strategy <ID>")
        return

    print("=" * 80)
    print("VECTORBT STRATEGY BACKTESTER")
    print("=" * 80)

    # Parse smoothing windows
    smoothing_windows = parse_smoothing_windows(args.smoothing)

    # Config file mode (direct JSON file path)
    if args.config:
        config = load_strategy_from_file(args.config)
        if not config:
            return

        # Determine resolution: CLI > config > default
        resolution = args.resolution
        if resolution == 'daily' and 'resolution' in config:
            resolution = config['resolution']
        # Update config with final resolution so backtest uses correct frequency
        config['resolution'] = resolution
        print(f"\n📊 Resolution: {resolution}")
        if args.smoothing:
            print(f"📈 Smoothing: {args.smoothing} (windows: {[w for w in smoothing_windows]})")

        # Apply CLI stop-loss override if provided
        if args.stop_loss is not None:
            if 'risk_management' not in config:
                config['risk_management'] = {}
            config['risk_management']['stop_loss_pct'] = args.stop_loss
            print(f"📉 Stop Loss: {args.stop_loss}% (CLI override)")
        elif config.get('risk_management', {}).get('stop_loss_pct'):
            print(f"📉 Stop Loss: {config['risk_management']['stop_loss_pct']}% (from config)")

        # Load data for resolution
        df = load_data_for_resolution(resolution)
        if df.empty:
            print("✗ Failed to load data")
            return

        print(f"\n📋 Strategy: {config.get('id', 'UNKNOWN')} - {config.get('name', 'Unknown')}")
        outputs = run_backtest_for_config(config, df, smoothing_windows,
                                         include_walk_forward=args.walk_forward)

        if len(outputs) > 1:
            print_smoothing_comparison(outputs)
        return

    # Strategy-based backtest mode (by ID)
    if args.strategy:
        config = load_strategy_config(args.strategy)
        if not config:
            print(f"\n✗ Strategy '{args.strategy}' not found.")
            print("  Use --list to see available strategies.")
            return

        # Determine resolution: CLI > config > default
        resolution = args.resolution
        if resolution == 'daily' and 'resolution' in config:
            resolution = config['resolution']
        # Update config with final resolution so backtest uses correct frequency
        config['resolution'] = resolution
        print(f"\n📊 Resolution: {resolution}")
        if args.smoothing:
            print(f"📈 Smoothing: {args.smoothing} (windows: {[w for w in smoothing_windows]})")

        # Apply CLI stop-loss override if provided
        if args.stop_loss is not None:
            if 'risk_management' not in config:
                config['risk_management'] = {}
            config['risk_management']['stop_loss_pct'] = args.stop_loss
            print(f"📉 Stop Loss: {args.stop_loss}% (CLI override)")
        elif config.get('risk_management', {}).get('stop_loss_pct'):
            print(f"📉 Stop Loss: {config['risk_management']['stop_loss_pct']}% (from config)")

        # Load data for resolution
        df = load_data_for_resolution(resolution)
        if df.empty:
            print("✗ Failed to load data")
            return

        outputs = run_backtest_for_config(config, df, smoothing_windows,
                                         include_walk_forward=args.walk_forward)

        if len(outputs) > 1:
            print_smoothing_comparison(outputs)
        return

    # All strategies mode
    if args.all:
        strategies = list_strategies()
        print(f"\nRunning backtest for {len(strategies)} strategies...")
        print(f"📊 Resolution: {args.resolution}")
        if args.stop_loss is not None:
            print(f"📉 Stop Loss: {args.stop_loss}% (CLI override for all)")

        # Load data once for all strategies
        df = load_data_for_resolution(args.resolution)
        if df.empty:
            print("✗ Failed to load data")
            return

        for strat in strategies:
            config = load_strategy_config(strat['id'])
            if config:
                try:
                    # Apply CLI stop-loss override if provided
                    if args.stop_loss is not None:
                        if 'risk_management' not in config:
                            config['risk_management'] = {}
                        config['risk_management']['stop_loss_pct'] = args.stop_loss

                    results = run_strategy_backtest(config, df, include_walk_forward=args.walk_forward)
                    results_path = save_strategy_results(config, results)
                    print(f"\n✓ {strat['id']}: Saved to {results_path.name}")
                except Exception as e:
                    print(f"\n✗ {strat['id']}: Error - {e}")

        print(f"\n{'=' * 80}")
        print(f"✓ Completed backtest for {len(strategies)} strategies")
        print(f"{'=' * 80}")
        return

    # Legacy walk-forward mode (standalone, for backward compatibility)
    # Only runs if no --strategy or --all specified
    if args.walk_forward and not args.strategy and not args.all:
        print("\nRunning legacy walk-forward analysis...")
        print(f"📊 Resolution: {args.resolution}")

        # Load data for resolution
        df = load_data_for_resolution(args.resolution)
        if df.empty:
            print("✗ Failed to load data")
            return

        wf_results = run_walk_forward(df, n_folds=6)

        # Save walk-forward results to JSON
        results_path = PROJECT_ROOT / "data" / "results" / "walk_forward_results.json"
        results_path.parent.mkdir(parents=True, exist_ok=True)

        output = {
            'run_date': datetime.now().isoformat(),
            'n_folds': len(wf_results['folds']),
            'data_range': {
                'start': str(df.index[0].date()),
                'end': str(df.index[-1].date()),
                'days': len(df)
            },
            'folds': wf_results['folds'],
            'summary': {
                strategy: {
                    'avg_return': round(data['avg_return'], 2),
                    'win_folds': data['win_folds'],
                    'total_folds': data['total_folds'],
                    'avg_sharpe': round(data['avg_sharpe'], 2),
                    'beats_bh': data['beats_bh'],
                    'fold_returns': [round(r, 2) for r in data['fold_returns']]
                }
                for strategy, data in wf_results['summary'].items()
            }
        }

        with open(results_path, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\n✓ Saved walk-forward results to {results_path}")
        print("\n" + "=" * 80)
        return

    # =========================================================================
    # LEGACY MODE: Run all hardcoded strategies (for backward compatibility)
    # =========================================================================
    print("\nRunning legacy backtest mode (use --strategy or --all for new mode)...")
    print(f"📊 Resolution: {args.resolution}")

    # Load data for resolution
    df = load_data_for_resolution(args.resolution)
    if df.empty:
        print("✗ Failed to load data")
        return

    # Split train/test
    train_df = df[df.index <= TRAIN_END].copy()
    test_df = df[df.index >= TEST_START].copy()

    print(f"\nTrain: {train_df.index[0]} to {train_df.index[-1]} ({len(train_df)} days)")
    print(f"Test:  {test_df.index[0]} to {test_df.index[-1]} ({len(test_df)} days)")

    # Generate signals
    print("\n" + "=" * 80)
    print("SIGNAL GENERATION")
    print("=" * 80)

    # Entry signals
    train_entries = generate_buy_the_dip_entries(train_df)
    test_entries = generate_buy_the_dip_entries(test_df)

    # Exit signals
    strategies = []

    # 1. STRAT-005: Momentum-Confirmed Exit (MVRV>2 AND Price<MA50)
    train_momentum_exits = generate_momentum_exit(train_df, mvrv_threshold=2.0, ma_period=50)
    test_momentum_exits = generate_momentum_exit(test_df, mvrv_threshold=2.0, ma_period=50)

    # 2. LTH Distribution
    train_lth_exits = generate_lth_distribution_exits(train_df)
    test_lth_exits = generate_lth_distribution_exits(test_df)

    # 3. 8-Metric High Risk (6/8)
    train_8m_exits = generate_8metric_exits(train_df, threshold=6)
    test_8m_exits = generate_8metric_exits(test_df, threshold=6)

    # 4. 8-Metric Caution (4/8)
    train_4m_exits = generate_8metric_exits(train_df, threshold=4)
    test_4m_exits = generate_8metric_exits(test_df, threshold=4)

    # Run backtests
    print("\n" + "=" * 80)
    print("TRAIN PERIOD BACKTESTS (2009-2022)")
    print("=" * 80)

    train_strat005 = backtest_with_vectorbt(train_df, train_entries, train_momentum_exits,
                                            "STRAT-005 Momentum Exit")
    train_lth = backtest_with_vectorbt(train_df, train_entries, train_lth_exits,
                                       "LTH Distribution")
    train_8m = backtest_with_vectorbt(train_df, train_entries, train_8m_exits,
                                      "8-Metric High Risk (6/8)")
    train_4m = backtest_with_vectorbt(train_df, train_entries, train_4m_exits,
                                      "8-Metric Caution (4/8)")

    print("\n" + "=" * 80)
    print("TEST PERIOD BACKTESTS (2023-2026) - OUT OF SAMPLE")
    print("=" * 80)

    test_strat005 = backtest_with_vectorbt(test_df, test_entries, test_momentum_exits,
                                           "STRAT-005 Momentum Exit")
    test_lth = backtest_with_vectorbt(test_df, test_entries, test_lth_exits,
                                      "LTH Distribution")
    test_8m = backtest_with_vectorbt(test_df, test_entries, test_8m_exits,
                                     "8-Metric High Risk (6/8)")
    test_4m = backtest_with_vectorbt(test_df, test_entries, test_4m_exits,
                                     "8-Metric Caution (4/8)")

    # Buy and hold
    print("\nBenchmark: Buy & Hold")
    bh_train = (train_df['price'].iloc[-1] / train_df['price'].iloc[0] - 1) * 100
    bh_test = (test_df['price'].iloc[-1] / test_df['price'].iloc[0] - 1) * 100
    print(f"  Train: {bh_train:.1f}%")
    print(f"  Test:  {bh_test:.1f}%")

    # Results table
    print("\n" + "=" * 80)
    print("RESULTS COMPARISON")
    print("=" * 80)

    print(f"\n{'Strategy':<30} {'Train Return':>12} {'Test Return':>12} {'Win Rate':>10} {'Sharpe':>8} {'Max DD':>8}")
    print("-" * 80)

    results = [
        ("STRAT-005 Momentum Exit", train_strat005, test_strat005),
        ("LTH Distribution", train_lth, test_lth),
        ("8-Metric High Risk (6/8)", train_8m, test_8m),
        ("8-Metric Caution (4/8)", train_4m, test_4m),
    ]

    for name, train_r, test_r in results:
        print(f"{name:<30} "
              f"{train_r['total_return']:>11.1f}% "
              f"{test_r['total_return']:>11.1f}% "
              f"{test_r['win_rate']:>9.1f}% "
              f"{test_r['sharpe']:>8.2f} "
              f"{test_r['max_dd']:>7.1f}%")

    print(f"{'Buy & Hold':<30} {bh_train:>11.1f}% {bh_test:>11.1f}% {'':>10} {'':>8} {'':>8}")

    # Comparison with custom backtest
    print("\n" + "=" * 80)
    print("COMPARISON WITH CUSTOM BACKTEST")
    print("=" * 80)

    print("\nCustom Backtest Results (from earlier):")
    print("  LTH Distribution:        +348.7% (15 trades)")
    print("  8-Metric High Risk 6/8:  +473.2% (4 trades)")
    print("  Buy & Hold:              +437.5%")

    print("\nVectorBT Results (OOS 2023-2026):")
    print(f"  LTH Distribution:        {test_lth['total_return']:+.1f}% ({int(test_lth['num_trades'])} trades)")
    print(f"  8-Metric High Risk 6/8:  {test_8m['total_return']:+.1f}% ({int(test_8m['num_trades'])} trades)")
    print(f"  Buy & Hold:              {bh_test:+.1f}%")

    # Check for discrepancies
    print("\n" + "=" * 80)
    print("VERIFICATION STATUS")
    print("=" * 80)

    lth_diff = abs(test_lth['total_return'] - 348.7)
    m8_diff = abs(test_8m['total_return'] - 473.2)
    bh_diff = abs(bh_test - 437.5)

    print(f"\nReturn Differences:")
    print(f"  LTH Distribution: {lth_diff:.1f}% difference")
    print(f"  8-Metric 6/8:     {m8_diff:.1f}% difference")
    print(f"  Buy & Hold:       {bh_diff:.1f}% difference")

    if lth_diff < 20 and m8_diff < 50 and bh_diff < 20:
        print("\n✅ VERIFICATION PASSED")
        print("   Results match within expected variance (fees, slippage, implementation)")
    else:
        print("\n⚠️  LARGE DISCREPANCIES FOUND")
        print("   Investigate for potential look-ahead bias or bugs")

    # Debug mode - show trades
    if args.debug:
        print("\n" + "=" * 80)
        print("TRADE DETAILS (8-Metric High Risk)")
        print("=" * 80)
        print(test_8m['portfolio'].trades.records_readable)

    # Run Monte Carlo simulations
    print("\n" + "=" * 80)
    print("MONTE CARLO SIMULATION (1000 runs)")
    print("=" * 80)

    mc_results = {}
    for name, train_r, test_r in results:
        trades = test_r.get('trades', [])
        if len(trades) >= 2:
            print(f"\n{name}:")
            mc = run_monte_carlo(trades, n_simulations=1000)
            mc_results[name] = mc

            print(f"  Trades: {mc['n_trades']} ({mc['n_winners']}W/{mc['n_losers']}L, {mc['win_rate']:.0f}% win rate)")
            print(f"  Return: {mc['original_return']:+.1f}% (same for all sequences)")
            print(f"  Original Max DD: {mc['original_max_dd']:.1f}%")
            print(f"  MC Max DD Range: {mc['percentiles']['dd_5th']:.1f}% - {mc['percentiles']['dd_95th']:.1f}%")
            print(f"  Risk of 20%+ DD: {mc['risk_of_20pct_dd']:.1f}%")
            print(f"  Risk of 30%+ DD: {mc['risk_of_30pct_dd']:.1f}%")
        else:
            print(f"\n{name}: Not enough trades for Monte Carlo (need >= 2)")
            mc_results[name] = None

    # Save JSON results for dashboard
    print("\n" + "=" * 80)
    print("SAVING JSON RESULTS")
    print("=" * 80)

    # Build JSON output
    output = {
        "run_date": datetime.now().isoformat(),
        "train_period": {
            "start": str(train_df.index[0].date()),
            "end": str(train_df.index[-1].date()),
            "days": len(train_df)
        },
        "test_period": {
            "start": str(test_df.index[0].date()),
            "end": str(test_df.index[-1].date()),
            "days": len(test_df)
        },
        "strategies": [],
        "benchmark": {
            "train_return": round(bh_train, 2),
            "test_return": round(bh_test, 2),
            "equity_curve": [
                [int(ts.timestamp() * 1000), float(10000 * (1 + (p / test_df['price'].iloc[0] - 1)))]
                for ts, p in zip(test_df.index, test_df['price'].values)
            ]
        }
    }

    # Add each strategy with Monte Carlo results
    for name, train_r, test_r in results:
        mc = mc_results.get(name)

        strategy_data = {
            "name": name,
            "train": {
                "return_pct": round(train_r['total_return'], 2),
                "sharpe": round(train_r['sharpe'], 2),
                "max_dd": round(train_r['max_dd'], 2),
                "num_trades": train_r['num_trades'],
                "win_rate": round(train_r['win_rate'], 2),
                "avg_hold_days": train_r.get('avg_hold_days', 0)
            },
            "test": {
                "return_pct": round(test_r['total_return'], 2),
                "sharpe": round(test_r['sharpe'], 2),
                "max_dd": round(test_r['max_dd'], 2),
                "num_trades": test_r['num_trades'],
                "win_rate": round(test_r['win_rate'], 2),
                "avg_hold_days": test_r.get('avg_hold_days', 0)
            },
            "equity_curve": test_r.get('equity_curve', []),
            "trades": test_r.get('trades', []),
            "monte_carlo": mc if mc else None
        }
        output["strategies"].append(strategy_data)

    # Save to file
    results_path = PROJECT_ROOT / "data" / "results" / "backtest_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)

    with open(results_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"  ✓ Saved to {results_path}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
