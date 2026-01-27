#!/usr/bin/env python3
"""
Backtest Results Dashboard
===========================
Generates HTML dashboard with index + detail pages for backtest results.

Usage:
    python dashboard_backtest.py              # Generate all dashboards
    python dashboard_backtest.py --no-open    # Generate without opening browser

Output:
    dashboards/dashboard_backtest.html       # Index page listing all strategies
    dashboards/backtest_strat001.html        # Detail page for each strategy
    dashboards/backtest_strat002.html
    ...

Prerequisites:
    Run backtest_vectorbt.py --all to generate strategy results files.
"""

import json
from pathlib import Path
from datetime import datetime
import webbrowser
import sys
import os

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
STRATEGIES_DIR = PROJECT_ROOT / "config" / "strategies"
DASHBOARDS_DIR = PROJECT_ROOT / "dashboards"
INDEX_PATH = DASHBOARDS_DIR / "dashboard_backtest.html"

# Legacy paths (for backward compatibility)
LEGACY_RESULTS_PATH = PROJECT_ROOT / "data" / "results" / "backtest_results.json"
LEGACY_WALK_FORWARD_PATH = PROJECT_ROOT / "data" / "results" / "walk_forward_results.json"

# Ensure dashboards directory exists
DASHBOARDS_DIR.mkdir(exist_ok=True)

# Colors matching existing dashboard
COLORS = {
    "bg": "#0f172a",
    "card": "#1e293b",
    "border": "#334155",
    "text": "#f1f5f9",
    "muted": "#9ca3af",
    "green": "#22c55e",
    "red": "#ef4444",
    "orange": "#f59e0b",
    "blue": "#3b82f6",
    "purple": "#a855f7",
}

# Strategy colors for charts
STRATEGY_COLORS = [COLORS["green"], COLORS["orange"], COLORS["purple"], COLORS["blue"]]


# =============================================================================
# DATA LOADING
# =============================================================================

def load_all_strategy_results() -> list:
    """Load all strategy results from sidecar files."""
    results = []

    for path in STRATEGIES_DIR.glob("*_results.json"):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            data['_path'] = path
            data['_config_path'] = path.parent / path.name.replace('_results.json', '.json')
            results.append(data)
        except Exception as e:
            print(f"  Warning: Could not load {path.name}: {e}")

    # Sort by strategy ID
    return sorted(results, key=lambda x: x.get('strategy_id', 'zzz'))


def load_strategy_config(config_path: Path) -> dict:
    """Load strategy configuration file."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except:
        return {}


def load_legacy_results() -> dict:
    """Load legacy backtest results (for backward compatibility)."""
    if not LEGACY_RESULTS_PATH.exists():
        return None
    with open(LEGACY_RESULTS_PATH, 'r') as f:
        return json.load(f)


def load_legacy_walk_forward() -> dict:
    """Load legacy walk-forward results (for backward compatibility)."""
    if not LEGACY_WALK_FORWARD_PATH.exists():
        return None
    with open(LEGACY_WALK_FORWARD_PATH, 'r') as f:
        return json.load(f)


# =============================================================================
# HTML HELPERS
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
    return f"{prefix}{val:.{decimals}f}{suffix}"


def format_percent(val, decimals=1):
    """Format as percentage."""
    if val is None:
        return "N/A"
    color = COLORS["green"] if val >= 0 else COLORS["red"]
    return f'<span style="color:{color}">{val:+.{decimals}f}%</span>'


def format_date(date_str):
    """Format date string for display."""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return date_str


# =============================================================================
# CHART GENERATION (SVG)
# =============================================================================

def generate_equity_curve_svg(data: dict, width: int = 800, height: int = 400) -> str:
    """Generate SVG line chart for equity curves."""
    strategies = data.get("strategies", [])
    benchmark = data.get("benchmark", {})

    if not strategies:
        return '<div style="color:#9ca3af;text-align:center;padding:40px;">No strategy data available</div>'

    # Find time range and value range
    all_times = []
    all_values = []

    for strat in strategies:
        curve = strat.get("equity_curve", [])
        for ts, val in curve:
            all_times.append(ts)
            all_values.append(val)

    bh_curve = benchmark.get("equity_curve", [])
    for ts, val in bh_curve:
        all_times.append(ts)
        all_values.append(val)

    if not all_times or not all_values:
        return '<div style="color:#9ca3af;text-align:center;padding:40px;">No equity curve data</div>'

    min_time = min(all_times)
    max_time = max(all_times)
    min_val = min(all_values) * 0.95
    max_val = max(all_values) * 1.05

    # Padding
    pad_left = 60
    pad_right = 20
    pad_top = 20
    pad_bottom = 40
    chart_width = width - pad_left - pad_right
    chart_height = height - pad_top - pad_bottom

    def scale_x(ts):
        if max_time == min_time:
            return pad_left
        return pad_left + (ts - min_time) / (max_time - min_time) * chart_width

    def scale_y(val):
        if max_val == min_val:
            return height - pad_bottom
        return height - pad_bottom - (val - min_val) / (max_val - min_val) * chart_height

    # Build SVG
    svg_parts = [f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="{COLORS['card']}"/>

        <!-- Grid lines -->
        <g stroke="#374151" stroke-width="1" stroke-dasharray="4,4">''']

    # Y-axis grid lines
    num_y_lines = 5
    for i in range(num_y_lines + 1):
        y = pad_top + i * chart_height / num_y_lines
        val = max_val - i * (max_val - min_val) / num_y_lines
        svg_parts.append(f'<line x1="{pad_left}" y1="{y}" x2="{width - pad_right}" y2="{y}"/>')
        svg_parts.append(f'<text x="{pad_left - 5}" y="{y + 4}" fill="{COLORS["muted"]}" font-size="11" text-anchor="end">${val/1000:.1f}k</text>')

    svg_parts.append('</g>')

    # Strategy colors
    strat_colors = [COLORS["green"], COLORS["orange"], COLORS["purple"], COLORS["blue"]]

    # Draw benchmark line (dashed)
    if bh_curve:
        points = " ".join([f"{scale_x(ts)},{scale_y(val)}" for ts, val in bh_curve])
        svg_parts.append(f'''
            <polyline points="{points}" fill="none" stroke="{COLORS['muted']}" stroke-width="2" stroke-dasharray="8,4"/>
        ''')

    # Draw strategy lines
    for idx, strat in enumerate(strategies):
        curve = strat.get("equity_curve", [])
        if not curve:
            continue
        color = strat_colors[idx % len(strat_colors)]
        points = " ".join([f"{scale_x(ts)},{scale_y(val)}" for ts, val in curve])
        svg_parts.append(f'''
            <polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"/>
        ''')

    # X-axis labels
    svg_parts.append(f'''
        <line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#374151" stroke-width="1"/>
    ''')

    # Date labels (start, middle, end)
    for pos in [0, 0.5, 1]:
        ts = min_time + (max_time - min_time) * pos
        x = scale_x(ts)
        date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m")
        svg_parts.append(f'<text x="{x}" y="{height - pad_bottom + 20}" fill="{COLORS["muted"]}" font-size="11" text-anchor="middle">{date_str}</text>')

    svg_parts.append('</svg>')

    return "\n".join(svg_parts)


def generate_legend(data: dict) -> str:
    """Generate legend for equity curves."""
    strategies = data.get("strategies", [])
    strat_colors = [COLORS["green"], COLORS["orange"], COLORS["purple"], COLORS["blue"]]

    items = []
    for idx, strat in enumerate(strategies):
        color = strat_colors[idx % len(strat_colors)]
        items.append(f'''
            <span style="display:inline-flex;align-items:center;margin-right:20px;">
                <span style="display:inline-block;width:20px;height:3px;background:{color};margin-right:8px;"></span>
                {strat['name']}
            </span>
        ''')

    # Add benchmark
    items.append(f'''
        <span style="display:inline-flex;align-items:center;">
            <span style="display:inline-block;width:20px;height:2px;background:{COLORS['muted']};margin-right:8px;border-top:2px dashed {COLORS['muted']};height:0;"></span>
            Buy &amp; Hold
        </span>
    ''')

    return f'<div style="text-align:center;margin-top:12px;font-size:0.85em;">{"".join(items)}</div>'


# =============================================================================
# CARD GENERATORS
# =============================================================================

def generate_header_card(data: dict, strategy_config: dict = None) -> str:
    """Generate unified header with run info and strategy parameters."""
    run_date = format_date(data.get("run_date", ""))
    train = data.get("train_period", {})
    test = data.get("test_period", {})
    pos_sizing = data.get("position_sizing", {})
    exit_strategy = data.get("exit_strategy", "")

    # Position sizing info
    pos_size = pos_sizing.get('position_size_pct', 100)
    risk_pct = pos_sizing.get('risk_per_trade_pct', 0)
    stop_pct = pos_sizing.get('stop_loss_pct', 0)
    sizing_str = f"{pos_size:.0f}%"
    sizing_detail = f"Risk: {risk_pct:.0f}%, Stop: {stop_pct:.0f}%" if risk_pct else "Full allocation"

    # Resolution (from config or default to daily)
    resolution = "Daily"
    if strategy_config:
        impl = strategy_config.get('implementation', {})
        calc_freq = impl.get('calculation_frequency', 'daily')
        resolution_map = {
            'daily': 'Daily',
            'hourly': 'Hourly',
            '4h': '4-Hourly',
            '8h': '8-Hourly',
            '12h': '12-Hourly',
            '1h': 'Hourly'
        }
        resolution = resolution_map.get(calc_freq.lower(), calc_freq.capitalize())

    # Extract strategy parameters from config
    entry_html = ""
    exit_html = ""

    if strategy_config:
        # Entry conditions
        entry = strategy_config.get('entry', {})
        entry_conditions = entry.get('conditions', [])
        required = entry.get('required_conditions', len(entry_conditions))
        total = entry.get('total_conditions', len(entry_conditions))

        if entry_conditions:
            conditions_list = []
            for cond in entry_conditions:
                metric = cond.get('metric', '')
                operator = cond.get('operator', '')
                threshold = cond.get('threshold', '')
                compare = cond.get('metric_compare', '')

                if compare:
                    conditions_list.append(f"{metric} {operator} {compare}")
                elif threshold != '':
                    conditions_list.append(f"{metric} {operator} {threshold}")

            entry_html = f'''
                <div class="params-section">
                    <div class="params-title" style="color:{COLORS['green']}">ENTRY ({required}/{total} required)</div>
                    <div class="params-conditions">
                        {"".join(f'<span class="param-chip">{c}</span>' for c in conditions_list)}
                    </div>
                </div>
            '''

        # Exit conditions
        exit_cfg = strategy_config.get('exit', {})
        exit_conditions = exit_cfg.get('conditions', [])
        exit_logic = exit_cfg.get('logic', 'AND')

        if exit_conditions:
            exit_list = []
            for cond in exit_conditions:
                metric = cond.get('metric', '')
                operator = cond.get('operator', '')
                threshold = cond.get('threshold', '')
                compare = cond.get('metric_compare', '')

                if compare:
                    exit_list.append(f"{metric} {operator} {compare}")
                elif threshold != '':
                    exit_list.append(f"{metric} {operator} {threshold}")

            exit_html = f'''
                <div class="params-section">
                    <div class="params-title" style="color:{COLORS['orange']}">EXIT ({exit_logic})</div>
                    <div class="params-conditions">
                        {"".join(f'<span class="param-chip">{c}</span>' for c in exit_list)}
                    </div>
                </div>
            '''
    elif exit_strategy:
        # Fallback to exit_strategy string from results
        exit_html = f'''
            <div class="params-section">
                <div class="params-title" style="color:{COLORS['orange']}">EXIT</div>
                <div class="params-conditions">
                    <span class="param-chip">{exit_strategy}</span>
                </div>
            </div>
        '''

    return f'''
        <div class="backtest-config">
            <div class="config-header">
                <div class="config-row">
                    <div class="config-item">
                        <div class="config-label">Run Date</div>
                        <div class="config-value">{run_date}</div>
                    </div>
                    <div class="config-item">
                        <div class="config-label">Resolution</div>
                        <div class="config-value" style="color:{COLORS['blue']}">{resolution}</div>
                    </div>
                    <div class="config-item">
                        <div class="config-label">Train Period</div>
                        <div class="config-value">{train.get('start', '')} → {train.get('end', '')}</div>
                        <div class="config-sublabel">{train.get('days', 0):,} days</div>
                    </div>
                    <div class="config-item">
                        <div class="config-label">Test Period (OOS)</div>
                        <div class="config-value">{test.get('start', '')} → {test.get('end', '')}</div>
                        <div class="config-sublabel">{test.get('days', 0):,} days</div>
                    </div>
                    <div class="config-item">
                        <div class="config-label">Position Size</div>
                        <div class="config-value" style="color:{COLORS['orange']}">{sizing_str}</div>
                        <div class="config-sublabel">{sizing_detail}</div>
                    </div>
                </div>
            </div>
            <div class="config-signals">
                {entry_html}
                {exit_html}
            </div>
        </div>
    '''


def generate_comparison_table(data: dict) -> str:
    """Generate strategy comparison table."""
    strategies = data.get("strategies", [])
    benchmark = data.get("benchmark", {})

    if not strategies:
        return '<div class="card">No strategy data available</div>'

    rows = []
    for strat in strategies:
        name = strat.get("name", "Unknown")
        test = strat.get("test", {})

        # Determine row highlight
        ret = test.get("return_pct", 0)
        sharpe = test.get("sharpe", 0)

        rows.append(f'''
            <tr>
                <td style="font-weight:600;">{name}</td>
                <td>{format_percent(test.get('return_pct', 0))}</td>
                <td style="color:{COLORS['green'] if sharpe > 1 else COLORS['muted']}">{sharpe:.2f}</td>
                <td style="color:{COLORS['red']}">{test.get('max_dd', 0):.1f}%</td>
                <td>{test.get('win_rate', 0):.1f}%</td>
                <td>{test.get('num_trades', 0)}</td>
                <td>{test.get('avg_hold_days', 0):.0f}</td>
            </tr>
        ''')

    # Add benchmark row
    rows.append(f'''
        <tr style="background:#1a2332;border-top:2px solid #374151;">
            <td style="font-weight:600;color:{COLORS['muted']}">Buy &amp; Hold</td>
            <td>{format_percent(benchmark.get('test_return', 0))}</td>
            <td style="color:{COLORS['muted']}">-</td>
            <td style="color:{COLORS['muted']}">-</td>
            <td style="color:{COLORS['muted']}">-</td>
            <td style="color:{COLORS['muted']}">1</td>
            <td style="color:{COLORS['muted']}">{data.get('test_period', {}).get('days', 0)}</td>
        </tr>
    ''')

    return f'''
        <div class="card" style="grid-column:span 2;">
            <h3>Strategy Comparison (Out-of-Sample)</h3>
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>Strategy</th>
                        <th>Return</th>
                        <th>Sharpe</th>
                        <th>Max DD</th>
                        <th>Win Rate</th>
                        <th>Trades</th>
                        <th>Avg Hold</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
    '''


def generate_strategy_card(strat: dict, color: str) -> str:
    """Generate individual strategy card."""
    name = strat.get("name", "Unknown")
    train = strat.get("train", {})
    test = strat.get("test", {})

    return f'''
        <div class="card">
            <h3 style="border-left:4px solid {color};padding-left:12px;">{name}</h3>

            <div class="metric-grid">
                <div class="metric-box">
                    <div class="metric-label">Test Return</div>
                    <div class="metric-value" style="font-size:1.8em;">{format_percent(test.get('return_pct', 0))}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Sharpe Ratio</div>
                    <div class="metric-value" style="color:{COLORS['green'] if test.get('sharpe', 0) > 1 else COLORS['muted']}">{test.get('sharpe', 0):.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Max Drawdown</div>
                    <div class="metric-value" style="color:{COLORS['red']}">{test.get('max_dd', 0):.1f}%</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Win Rate</div>
                    <div class="metric-value">{test.get('win_rate', 0):.1f}%</div>
                </div>
            </div>

            <div style="margin-top:16px;padding-top:12px;border-top:1px solid #374151;">
                <div style="display:flex;justify-content:space-between;color:{COLORS['muted']};font-size:0.85em;">
                    <span>Trades: {test.get('num_trades', 0)}</span>
                    <span>Avg Hold: {test.get('avg_hold_days', 0):.0f} days</span>
                </div>
            </div>

            <div style="margin-top:12px;">
                <div style="display:flex;justify-content:space-between;font-size:0.8em;color:{COLORS['muted']};margin-bottom:4px;">
                    <span>Train ({train.get('return_pct', 0):+.1f}%)</span>
                    <span>Test ({test.get('return_pct', 0):+.1f}%)</span>
                </div>
                <div style="height:8px;background:#374151;border-radius:4px;overflow:hidden;display:flex;">
                    <div style="width:50%;height:100%;background:{COLORS['blue']};opacity:0.5;"></div>
                    <div style="width:50%;height:100%;background:{color};"></div>
                </div>
            </div>
        </div>
    '''


def generate_stats_card(strat: dict) -> str:
    """Generate detailed statistics card with VectorBT metrics."""
    test = strat.get("test", {})

    # Risk-adjusted returns
    sharpe = test.get('sharpe', 0)
    sortino = test.get('sortino', 0)
    calmar = test.get('calmar', 0)
    omega = test.get('omega', 0)

    # Trade statistics
    profit_factor = test.get('profit_factor', 0)
    expectancy = test.get('expectancy', 0)
    avg_win = test.get('avg_win_pct', 0)
    avg_loss = test.get('avg_loss_pct', 0)
    best_trade = test.get('best_trade', 0)
    worst_trade = test.get('worst_trade', 0)

    # Risk metrics
    max_dd = test.get('max_dd', 0)
    max_dd_days = test.get('max_dd_days', 0)

    # Color coding helper
    def ratio_color(val, threshold=1):
        return COLORS['green'] if val > threshold else COLORS['muted']

    return f'''
        <div class="card">
            <h3>Detailed Statistics (Test Period)</h3>

            <div class="stats-grid">
                <div class="stats-section">
                    <div class="stats-section-title">Risk-Adjusted Returns</div>
                    <div class="stats-row">
                        <span class="stats-label">Sharpe Ratio</span>
                        <span class="stats-value" style="color:{ratio_color(sharpe)}">{sharpe:.2f}</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Sortino Ratio</span>
                        <span class="stats-value" style="color:{ratio_color(sortino)}">{sortino:.2f}</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Calmar Ratio</span>
                        <span class="stats-value" style="color:{ratio_color(calmar)}">{calmar:.2f}</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Omega Ratio</span>
                        <span class="stats-value" style="color:{ratio_color(omega)}">{omega:.2f}</span>
                    </div>
                </div>

                <div class="stats-section">
                    <div class="stats-section-title">Trade Statistics</div>
                    <div class="stats-row">
                        <span class="stats-label">Profit Factor</span>
                        <span class="stats-value" style="color:{ratio_color(profit_factor)}">{profit_factor:.2f}</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Expectancy</span>
                        <span class="stats-value" style="color:{COLORS['green'] if expectancy > 0 else COLORS['red']}">${expectancy:,.0f}</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Avg Win</span>
                        <span class="stats-value" style="color:{COLORS['green']}">{avg_win:+.1f}%</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Avg Loss</span>
                        <span class="stats-value" style="color:{COLORS['red']}">{avg_loss:.1f}%</span>
                    </div>
                </div>

                <div class="stats-section">
                    <div class="stats-section-title">Best / Worst</div>
                    <div class="stats-row">
                        <span class="stats-label">Best Trade</span>
                        <span class="stats-value" style="color:{COLORS['green']}">{best_trade:+.1f}%</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Worst Trade</span>
                        <span class="stats-value" style="color:{COLORS['red']}">{worst_trade:.1f}%</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Max DD</span>
                        <span class="stats-value" style="color:{COLORS['red']}">{max_dd:.1f}%</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">DD Duration</span>
                        <span class="stats-value">{max_dd_days} days</span>
                    </div>
                </div>
            </div>
        </div>
    '''


def generate_trades_timeline(data: dict) -> str:
    """Generate trades timeline visualization with entry/exit prices and portfolio balance."""
    strategies = data.get("strategies", [])
    strat_colors = [COLORS["green"], COLORS["orange"], COLORS["purple"], COLORS["blue"]]

    all_trades = []
    for idx, strat in enumerate(strategies):
        color = strat_colors[idx % len(strat_colors)]
        for trade in strat.get("trades", []):
            all_trades.append({
                "strategy": strat["name"],
                "color": color,
                **trade
            })

    if not all_trades:
        return '''
            <div class="card">
                <h3>Trade Timeline</h3>
                <div style="color:#9ca3af;text-align:center;padding:20px;">No trade data available</div>
            </div>
        '''

    # Sort by entry date
    all_trades.sort(key=lambda x: x.get("entry_date", ""))

    trade_rows = []
    for trade in all_trades[:20]:  # Show max 20 trades
        pnl = trade.get("return_pct", 0)
        pnl_color = COLORS["green"] if pnl >= 0 else COLORS["red"]
        pnl_value = trade.get("pnl", 0)
        entry_price = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        stop_price = trade.get("stop_price", 0)
        balance_before = trade.get("balance_before", 0)
        balance_after = trade.get("balance_after", 0)
        size_usd = trade.get("size_usd", 0)
        size_btc = trade.get("size_btc", 0)
        exit_type = trade.get("exit_type", "SIGNAL")
        entry_triggers = trade.get("entry_triggers", {})
        exit_triggers = trade.get("exit_triggers", {})

        # Format values
        entry_str = f"${entry_price:,.0f}" if entry_price else "-"
        exit_str = f"${exit_price:,.0f}" if exit_price else "-"
        stop_str = f"${stop_price:,.0f}" if stop_price else "-"
        balance_before_str = f"${balance_before:,.0f}" if balance_before else "-"
        balance_after_str = f"${balance_after:,.0f}" if balance_after else "-"
        pnl_str = f"${pnl_value:+,.0f}" if pnl_value else "-"
        size_usd_str = f"${size_usd:,.0f}" if size_usd else "-"
        size_btc_str = f"{size_btc:.4f} BTC" if size_btc else "-"

        # Format entry triggers (all 5 Buy The Dip conditions)
        entry_trigger_parts = []
        conditions_met = 0

        if entry_triggers.get('mvrv_sth') is not None:
            val = entry_triggers['mvrv_sth']
            met = val < 1
            conditions_met += 1 if met else 0
            color = COLORS['green'] if met else COLORS['muted']
            entry_trigger_parts.append(f'<span style="color:{color}">MVRV: {val}</span>')

        if entry_triggers.get('sopr_sth') is not None:
            val = entry_triggers['sopr_sth']
            met = val < 1
            conditions_met += 1 if met else 0
            color = COLORS['green'] if met else COLORS['muted']
            entry_trigger_parts.append(f'<span style="color:{color}">SOPR: {val}</span>')

        if entry_triggers.get('rpl_ratio') is not None:
            val = entry_triggers['rpl_ratio']
            met = val < 1
            conditions_met += 1 if met else 0
            color = COLORS['green'] if met else COLORS['muted']
            entry_trigger_parts.append(f'<span style="color:{color}">RPL: {val}</span>')

        if entry_triggers.get('funding') is not None:
            val = entry_triggers['funding']
            met = val <= 0
            conditions_met += 1 if met else 0
            color = COLORS['green'] if met else COLORS['muted']
            entry_trigger_parts.append(f'<span style="color:{color}">Fund: {val:.4f}</span>')

        if entry_triggers.get('liq_ratio') is not None:
            val = entry_triggers['liq_ratio']
            met = val > 1
            conditions_met += 1 if met else 0
            color = COLORS['green'] if met else COLORS['muted']
            entry_trigger_parts.append(f'<span style="color:{color}">Liq: {val}</span>')

        conditions_badge = f'<span class="conditions-badge">{conditions_met}/5</span>' if entry_trigger_parts else ''
        entry_trigger_str = f'{conditions_badge} ' + ' | '.join(entry_trigger_parts) if entry_trigger_parts else '-'

        # Format exit triggers
        if exit_type == "STOP":
            exit_trigger_str = f'<span style="color:{COLORS["red"]}">Stop-loss hit at ${exit_price:,.0f}</span>'
        else:
            exit_trigger_parts = []
            if exit_triggers.get('mvrv') is not None:
                val = exit_triggers['mvrv']
                color = COLORS['orange'] if val > 2 else COLORS['muted']
                exit_trigger_parts.append(f'<span style="color:{color}">MVRV: {val}</span>')
            if exit_triggers.get('price_vs_ma50'):
                val = exit_triggers['price_vs_ma50']
                color = COLORS['orange'] if val == 'below' else COLORS['muted']
                exit_trigger_parts.append(f'<span style="color:{color}">Price {val} MA50</span>')
            exit_trigger_str = ' | '.join(exit_trigger_parts) if exit_trigger_parts else '-'

        # Exit type badge styling
        if exit_type == "STOP":
            exit_badge = f'<span class="exit-badge exit-stop">STOP</span>'
        else:
            exit_badge = f'<span class="exit-badge exit-signal">SIGNAL</span>'

        trade_rows.append(f'''
            <div class="trade-row-expanded">
                <div class="trade-bar" style="background:{trade['color']};"></div>
                <div class="trade-main">
                    <div class="trade-header">
                        <span class="trade-strategy">{trade['strategy'][:20]}</span>
                        <span style="display:flex;align-items:center;gap:8px;">
                            {exit_badge}
                            <span class="trade-pnl" style="color:{pnl_color}">{pnl:+.1f}%</span>
                        </span>
                    </div>
                    <div class="trade-dates">{trade.get('entry_date', '')[:10]} → {trade.get('exit_date', '')[:10]}</div>
                    <div class="trade-triggers">
                        <div class="trigger-row">
                            <span class="trigger-label">ENTRY:</span>
                            <span class="trigger-values">{entry_trigger_str}</span>
                        </div>
                        <div class="trigger-row">
                            <span class="trigger-label">EXIT:</span>
                            <span class="trigger-values">{exit_trigger_str}</span>
                        </div>
                    </div>
                    <div class="trade-details">
                        <span class="trade-detail">
                            <span class="trade-detail-label">Start Bal</span>
                            <span class="trade-detail-value">{balance_before_str}</span>
                        </span>
                        <span class="trade-detail">
                            <span class="trade-detail-label">Position</span>
                            <span class="trade-detail-value">{size_usd_str}</span>
                        </span>
                        <span class="trade-detail">
                            <span class="trade-detail-label">Size</span>
                            <span class="trade-detail-value" style="font-size:0.8em">{size_btc_str}</span>
                        </span>
                        <span class="trade-detail">
                            <span class="trade-detail-label">Entry</span>
                            <span class="trade-detail-value">{entry_str}</span>
                        </span>
                        <span class="trade-detail">
                            <span class="trade-detail-label">Stop</span>
                            <span class="trade-detail-value" style="color:{COLORS['red']}">{stop_str}</span>
                        </span>
                        <span class="trade-detail">
                            <span class="trade-detail-label">Exit</span>
                            <span class="trade-detail-value">{exit_str}</span>
                        </span>
                        <span class="trade-detail">
                            <span class="trade-detail-label">P&L</span>
                            <span class="trade-detail-value" style="color:{pnl_color}">{pnl_str}</span>
                        </span>
                        <span class="trade-detail">
                            <span class="trade-detail-label">End Bal</span>
                            <span class="trade-detail-value" style="color:{COLORS['blue']}">{balance_after_str}</span>
                        </span>
                    </div>
                </div>
            </div>
        ''')

    return f'''
        <div class="card" style="grid-column:span 2;">
            <h3>Trade Timeline (Test Period)</h3>
            <div class="trades-container-expanded">
                {"".join(trade_rows)}
            </div>
            {f'<div style="color:{COLORS["muted"]};font-size:0.8em;margin-top:8px;">Showing first 20 of {len(all_trades)} trades</div>' if len(all_trades) > 20 else ''}
        </div>
    '''


def generate_return_distribution(data: dict) -> str:
    """Generate trade return distribution as CSS histogram."""
    strategies = data.get("strategies", [])

    all_returns = []
    for strat in strategies:
        for trade in strat.get("trades", []):
            all_returns.append(trade.get("return_pct", 0))

    if not all_returns:
        return '''
            <div class="card">
                <h3>Return Distribution</h3>
                <div style="color:#9ca3af;text-align:center;padding:20px;">No trade return data</div>
            </div>
        '''

    # Create histogram bins
    min_ret = min(all_returns)
    max_ret = max(all_returns)
    num_bins = 10
    bin_width = (max_ret - min_ret) / num_bins if max_ret != min_ret else 1

    bins = [0] * num_bins
    for ret in all_returns:
        bin_idx = min(int((ret - min_ret) / bin_width), num_bins - 1)
        bins[bin_idx] += 1

    max_count = max(bins) if bins else 1

    # Generate bars
    bars = []
    for i, count in enumerate(bins):
        bin_start = min_ret + i * bin_width
        height_pct = (count / max_count * 100) if max_count > 0 else 0
        color = COLORS["green"] if bin_start >= 0 else COLORS["red"]

        bars.append(f'''
            <div class="hist-bar-container">
                <div class="hist-bar" style="height:{height_pct}%;background:{color};"></div>
                <div class="hist-label">{bin_start:.0f}%</div>
            </div>
        ''')

    # Stats
    avg_ret = sum(all_returns) / len(all_returns)
    median_ret = sorted(all_returns)[len(all_returns) // 2]
    win_count = sum(1 for r in all_returns if r >= 0)

    return f'''
        <div class="card">
            <h3>Return Distribution</h3>
            <div class="histogram">
                {"".join(bars)}
            </div>
            <div style="display:flex;justify-content:space-around;margin-top:16px;font-size:0.85em;">
                <div style="text-align:center;">
                    <div style="color:{COLORS['muted']}">Avg Return</div>
                    <div style="color:{COLORS['green'] if avg_ret >= 0 else COLORS['red']};font-weight:600;">{avg_ret:+.1f}%</div>
                </div>
                <div style="text-align:center;">
                    <div style="color:{COLORS['muted']}">Median</div>
                    <div style="font-weight:600;">{median_ret:+.1f}%</div>
                </div>
                <div style="text-align:center;">
                    <div style="color:{COLORS['muted']}">Win/Total</div>
                    <div style="font-weight:600;">{win_count}/{len(all_returns)}</div>
                </div>
            </div>
        </div>
    '''


# =============================================================================
# MONTE CARLO VISUALIZATION
# =============================================================================

def generate_monte_carlo_histogram_svg(mc_data: dict, width: int = 350, height: int = 180) -> str:
    """Generate SVG histogram of Monte Carlo MAX DRAWDOWN distribution."""
    if not mc_data:
        return '<div style="color:#9ca3af;text-align:center;padding:20px;">No Monte Carlo data</div>'

    # Use drawdown distribution (this varies with trade order, unlike returns)
    dd_values = mc_data.get('dd_distribution', [])
    if not dd_values:
        return '<div style="color:#9ca3af;text-align:center;padding:20px;">No distribution data</div>'

    original_dd = mc_data.get('original_max_dd', 0)
    percentiles = mc_data.get('percentiles', {})

    # Create histogram bins
    min_dd = min(dd_values)
    max_dd = max(dd_values)

    # Handle case where all values are the same
    if max_dd == min_dd:
        return f'''
            <div style="text-align:center;padding:20px;">
                <div style="font-size:2em;font-weight:bold;color:{COLORS['green']}">{min_dd:.1f}%</div>
                <div style="color:{COLORS['muted']};font-size:0.85em;margin-top:8px;">
                    Max DD is constant<br>(only {mc_data.get('n_losers', 0)} losing trade{'s' if mc_data.get('n_losers', 0) != 1 else ''})
                </div>
            </div>
        '''

    num_bins = 20
    bin_width = (max_dd - min_dd) / num_bins

    bins = [0] * num_bins
    for dd in dd_values:
        bin_idx = min(int((dd - min_dd) / bin_width), num_bins - 1)
        bins[bin_idx] += 1

    max_count = max(bins) if bins else 1

    # SVG dimensions
    pad_left = 35
    pad_right = 10
    pad_top = 10
    pad_bottom = 25
    chart_width = width - pad_left - pad_right
    chart_height = height - pad_top - pad_bottom
    bar_w = chart_width / num_bins

    def scale_x(val):
        if max_dd == min_dd:
            return pad_left + chart_width / 2
        return pad_left + (val - min_dd) / (max_dd - min_dd) * chart_width

    # Build SVG
    svg_parts = [f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#0f172a"/>''']

    # Draw bars - color based on severity
    for i, count in enumerate(bins):
        bin_start = min_dd + i * bin_width
        x = pad_left + i * bar_w
        bar_height = (count / max_count) * chart_height if max_count > 0 else 0
        y = height - pad_bottom - bar_height

        # Color gradient: green (low DD) -> yellow -> red (high DD)
        if bin_start < 15:
            color = COLORS["green"]
        elif bin_start < 25:
            color = COLORS["orange"]
        else:
            color = COLORS["red"]

        svg_parts.append(f'<rect x="{x}" y="{y}" width="{bar_w - 1}" height="{bar_height}" fill="{color}" opacity="0.7"/>')

    # Draw original DD line
    orig_x = scale_x(original_dd)
    svg_parts.append(f'<line x1="{orig_x}" y1="{pad_top}" x2="{orig_x}" y2="{height - pad_bottom}" stroke="{COLORS["purple"]}" stroke-width="2"/>')

    # Draw 95th percentile line
    p95 = percentiles.get('dd_95th', max_dd)
    p95_x = scale_x(p95)
    svg_parts.append(f'<line x1="{p95_x}" y1="{pad_top}" x2="{p95_x}" y2="{height - pad_bottom}" stroke="{COLORS["red"]}" stroke-width="1" stroke-dasharray="3,2"/>')

    # X-axis labels
    for val in [min_dd, (min_dd + max_dd) / 2, max_dd]:
        x = scale_x(val)
        svg_parts.append(f'<text x="{x}" y="{height - 6}" fill="{COLORS["muted"]}" font-size="9" text-anchor="middle">{val:.0f}%</text>')

    # Legend
    svg_parts.append(f'<text x="{width - 5}" y="15" fill="{COLORS["purple"]}" font-size="8" text-anchor="end">Actual</text>')
    svg_parts.append(f'<text x="{width - 5}" y="25" fill="{COLORS["red"]}" font-size="8" text-anchor="end">95th %ile</text>')

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def generate_monte_carlo_card(strat: dict, color: str) -> str:
    """Generate Monte Carlo results card for a strategy."""
    mc = strat.get('monte_carlo')
    name = strat.get('name', 'Unknown')

    if not mc:
        return f'''
            <div class="card">
                <h3 style="border-left:4px solid {color};padding-left:12px;">Monte Carlo: {name}</h3>
                <div style="color:{COLORS['muted']};text-align:center;padding:20px;">
                    Not enough trades for Monte Carlo simulation (need >= 2)
                </div>
            </div>
        '''

    percentiles = mc.get('percentiles', {})
    original_return = mc.get('original_return', 0)
    original_dd = mc.get('original_max_dd', 0)
    n_sims = mc.get('n_simulations', 0)
    n_trades = mc.get('n_trades', 0)
    n_winners = mc.get('n_winners', 0)
    n_losers = mc.get('n_losers', 0)
    win_rate = mc.get('win_rate', 0)

    # Risk metrics
    risk_20 = mc.get('risk_of_20pct_dd', 0)
    risk_30 = mc.get('risk_of_30pct_dd', 0)
    risk_50 = mc.get('risk_of_50pct_dd', 0)

    # Drawdown stats
    dd_median = percentiles.get('dd_50th', 0)
    dd_95th = percentiles.get('dd_95th', 0)
    dd_max = percentiles.get('dd_max', 0)
    dd_std = percentiles.get('dd_std', 0)

    # Determine risk level
    if dd_95th < 15:
        risk_level = "LOW RISK"
        risk_color = COLORS["green"]
        risk_bg = "#14532d"
    elif dd_95th < 30:
        risk_level = "MODERATE RISK"
        risk_color = COLORS["orange"]
        risk_bg = "#78350f"
    else:
        risk_level = "HIGH RISK"
        risk_color = COLORS["red"]
        risk_bg = "#7f1d1d"

    return f'''
        <div class="card">
            <h3 style="border-left:4px solid {color};padding-left:12px;">Monte Carlo: {name}</h3>

            <div style="display:flex;gap:16px;margin-bottom:16px;">
                <div style="flex:1;">
                    <div style="font-size:0.8em;color:{COLORS['muted']};margin-bottom:8px;text-align:center;">Max Drawdown Distribution</div>
                    {generate_monte_carlo_histogram_svg(mc)}
                </div>
                <div style="flex:1;">
                    <div class="mc-stats">
                        <div class="mc-stat-row">
                            <span class="mc-label">Simulations</span>
                            <span class="mc-value">{n_sims:,}</span>
                        </div>
                        <div class="mc-stat-row">
                            <span class="mc-label">Trades</span>
                            <span class="mc-value">{n_trades} ({n_winners}W/{n_losers}L)</span>
                        </div>
                        <div class="mc-stat-row">
                            <span class="mc-label">Win Rate</span>
                            <span class="mc-value">{win_rate:.0f}%</span>
                        </div>
                        <div class="mc-stat-row" style="margin-top:8px;padding-top:8px;border-top:1px solid #374151;">
                            <span class="mc-label">Return</span>
                            <span class="mc-value" style="color:{COLORS['green']}">{original_return:+.1f}%</span>
                        </div>
                        <div class="mc-stat-row">
                            <span class="mc-label">Actual Max DD</span>
                            <span class="mc-value" style="color:{COLORS['purple']}">{original_dd:.1f}%</span>
                        </div>
                        <div class="mc-stat-row">
                            <span class="mc-label">MC Median DD</span>
                            <span class="mc-value">{dd_median:.1f}%</span>
                        </div>
                        <div class="mc-stat-row">
                            <span class="mc-label">MC 95th DD</span>
                            <span class="mc-value" style="color:{COLORS['red']}">{dd_95th:.1f}%</span>
                        </div>
                        <div class="mc-stat-row">
                            <span class="mc-label">MC Worst DD</span>
                            <span class="mc-value" style="color:{COLORS['red']}">{dd_max:.1f}%</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Risk Meters -->
            <div style="display:flex;gap:8px;margin-bottom:12px;">
                <div style="flex:1;text-align:center;padding:8px;background:#0f172a;border-radius:6px;">
                    <div style="font-size:0.7em;color:{COLORS['muted']}">Risk of 20%+ DD</div>
                    <div style="font-size:1.2em;font-weight:600;color:{COLORS['green'] if risk_20 < 10 else COLORS['orange'] if risk_20 < 50 else COLORS['red']}">{risk_20:.0f}%</div>
                </div>
                <div style="flex:1;text-align:center;padding:8px;background:#0f172a;border-radius:6px;">
                    <div style="font-size:0.7em;color:{COLORS['muted']}">Risk of 30%+ DD</div>
                    <div style="font-size:1.2em;font-weight:600;color:{COLORS['green'] if risk_30 < 5 else COLORS['orange'] if risk_30 < 25 else COLORS['red']}">{risk_30:.0f}%</div>
                </div>
                <div style="flex:1;text-align:center;padding:8px;background:#0f172a;border-radius:6px;">
                    <div style="font-size:0.7em;color:{COLORS['muted']}">Risk of 50%+ DD</div>
                    <div style="font-size:1.2em;font-weight:600;color:{COLORS['green'] if risk_50 < 1 else COLORS['orange'] if risk_50 < 10 else COLORS['red']}">{risk_50:.0f}%</div>
                </div>
            </div>

            <div style="background:{risk_bg};padding:12px;border-radius:8px;text-align:center;">
                <div style="font-weight:600;color:{risk_color};font-size:1.1em;">{risk_level}</div>
                <div style="font-size:0.75em;color:{COLORS['muted']};margin-top:4px;">
                    Based on 95th percentile max drawdown across {n_sims:,} simulations
                </div>
            </div>
        </div>
    '''


def generate_monte_carlo_section(data: dict) -> str:
    """Generate full Monte Carlo section with all strategies."""
    strategies = data.get("strategies", [])
    strat_colors = [COLORS["green"], COLORS["orange"], COLORS["purple"], COLORS["blue"]]

    cards = ""
    for idx, strat in enumerate(strategies):
        color = strat_colors[idx % len(strat_colors)]
        cards += generate_monte_carlo_card(strat, color)

    return cards


# =============================================================================
# WALK-FORWARD VISUALIZATION
# =============================================================================

def generate_walk_forward_chart_svg(wf_data: dict, width: int = 800, height: int = 300) -> str:
    """Generate SVG bar chart showing returns by fold for each strategy."""
    if not wf_data:
        return '<div style="color:#9ca3af;text-align:center;padding:40px;">No walk-forward data available</div>'

    summary = wf_data.get('summary', {})
    folds = wf_data.get('folds', [])
    n_folds = len(folds)

    if n_folds == 0:
        return '<div style="color:#9ca3af;text-align:center;padding:40px;">No fold data</div>'

    # Strategy colors
    strat_colors = {
        'STRAT-005 Momentum Exit': COLORS['green'],
        'LTH Distribution': COLORS['orange'],
        'Buy & Hold': COLORS['muted'],
    }

    # Find y-axis range
    all_returns = []
    for strat_name, strat_data in summary.items():
        all_returns.extend(strat_data.get('fold_returns', []))

    if not all_returns:
        return '<div style="color:#9ca3af;text-align:center;padding:40px;">No return data</div>'

    min_ret = min(min(all_returns), 0) * 1.1
    max_ret = max(max(all_returns), 0) * 1.1

    # SVG dimensions
    pad_left = 60
    pad_right = 20
    pad_top = 30
    pad_bottom = 60
    chart_width = width - pad_left - pad_right
    chart_height = height - pad_top - pad_bottom

    strategies = list(summary.keys())
    n_strats = len(strategies)
    group_width = chart_width / n_folds
    bar_width = (group_width - 20) / n_strats

    def scale_y(val):
        if max_ret == min_ret:
            return height - pad_bottom - chart_height / 2
        return height - pad_bottom - (val - min_ret) / (max_ret - min_ret) * chart_height

    zero_y = scale_y(0)

    # Build SVG
    svg_parts = [f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="{COLORS['card']}"/>

        <!-- Grid lines -->
        <g stroke="#374151" stroke-width="1" stroke-dasharray="4,4">''']

    # Y-axis grid lines
    num_y_lines = 5
    for i in range(num_y_lines + 1):
        y = pad_top + i * chart_height / num_y_lines
        val = max_ret - i * (max_ret - min_ret) / num_y_lines
        svg_parts.append(f'<line x1="{pad_left}" y1="{y}" x2="{width - pad_right}" y2="{y}"/>')
        svg_parts.append(f'<text x="{pad_left - 5}" y="{y + 4}" fill="{COLORS["muted"]}" font-size="11" text-anchor="end">{val:+.0f}%</text>')

    svg_parts.append('</g>')

    # Zero line (bold)
    svg_parts.append(f'<line x1="{pad_left}" y1="{zero_y}" x2="{width - pad_right}" y2="{zero_y}" stroke="#64748b" stroke-width="2"/>')

    # Draw bars for each fold
    for fold_idx in range(n_folds):
        group_x = pad_left + fold_idx * group_width + 10

        for strat_idx, strat_name in enumerate(strategies):
            strat_data = summary.get(strat_name, {})
            fold_returns = strat_data.get('fold_returns', [])

            if fold_idx < len(fold_returns):
                ret = fold_returns[fold_idx]
                color = strat_colors.get(strat_name, COLORS['blue'])

                bar_x = group_x + strat_idx * bar_width
                bar_y = scale_y(ret) if ret >= 0 else zero_y
                bar_height = abs(scale_y(ret) - zero_y)

                opacity = "0.9" if strat_name != 'Buy & Hold' else "0.5"
                svg_parts.append(f'<rect x="{bar_x}" y="{bar_y}" width="{bar_width - 2}" height="{bar_height}" fill="{color}" opacity="{opacity}" rx="2"/>')

                # Value label
                label_y = bar_y - 5 if ret >= 0 else bar_y + bar_height + 12
                svg_parts.append(f'<text x="{bar_x + bar_width/2}" y="{label_y}" fill="{COLORS["text"]}" font-size="9" text-anchor="middle">{ret:+.0f}%</text>')

        # Fold label
        fold_info = folds[fold_idx]
        test_period = f"{fold_info.get('test_start', '')[:7]}"
        svg_parts.append(f'<text x="{group_x + group_width/2 - 5}" y="{height - pad_bottom + 18}" fill="{COLORS["text"]}" font-size="11" text-anchor="middle">Fold {fold_idx + 1}</text>')
        svg_parts.append(f'<text x="{group_x + group_width/2 - 5}" y="{height - pad_bottom + 32}" fill="{COLORS["muted"]}" font-size="9" text-anchor="middle">{test_period}</text>')

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def generate_walk_forward_legend(wf_data: dict) -> str:
    """Generate legend for walk-forward chart."""
    summary = wf_data.get('summary', {})

    strat_colors = {
        'STRAT-005 Momentum Exit': COLORS['green'],
        'LTH Distribution': COLORS['orange'],
        'Buy & Hold': COLORS['muted'],
    }

    items = []
    for strat_name in summary.keys():
        color = strat_colors.get(strat_name, COLORS['blue'])
        items.append(f'''
            <span style="display:inline-flex;align-items:center;margin-right:20px;">
                <span style="display:inline-block;width:16px;height:12px;background:{color};margin-right:8px;border-radius:2px;opacity:0.9;"></span>
                {strat_name}
            </span>
        ''')

    return f'<div style="text-align:center;margin-top:12px;font-size:0.85em;">{"".join(items)}</div>'


def generate_walk_forward_summary_table(wf_data: dict) -> str:
    """Generate walk-forward summary table."""
    summary = wf_data.get('summary', {})

    if not summary:
        return '<div style="color:#9ca3af;text-align:center;padding:20px;">No summary data</div>'

    rows = []
    for strat_name, strat_data in summary.items():
        avg_ret = strat_data.get('avg_return', 0)
        win_folds = strat_data.get('win_folds', 0)
        total_folds = strat_data.get('total_folds', 5)
        avg_sharpe = strat_data.get('avg_sharpe', 0)
        beats_bh = strat_data.get('beats_bh', 0)

        # Color coding
        ret_color = COLORS['green'] if avg_ret >= 0 else COLORS['red']
        is_benchmark = strat_name == 'Buy & Hold'
        row_style = 'background:#1a2332;border-top:2px solid #374151;' if is_benchmark else ''

        rows.append(f'''
            <tr style="{row_style}">
                <td style="font-weight:600;{'color:' + COLORS['muted'] + ';' if is_benchmark else ''}">{strat_name}</td>
                <td style="color:{ret_color}">{avg_ret:+.1f}%</td>
                <td>{win_folds}/{total_folds}</td>
                <td style="color:{COLORS['green'] if avg_sharpe > 0.5 else COLORS['muted']}">{avg_sharpe:.2f}</td>
                <td>{beats_bh}/{total_folds if not is_benchmark else '-'}</td>
            </tr>
        ''')

    return f'''
        <table class="comparison-table">
            <thead>
                <tr>
                    <th>Strategy</th>
                    <th>Avg Return</th>
                    <th>Profitable Folds</th>
                    <th>Avg Sharpe</th>
                    <th>Beats B&H</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    '''


def generate_walk_forward_folds_table(wf_data: dict) -> str:
    """Generate table showing fold periods."""
    folds = wf_data.get('folds', [])

    if not folds:
        return ''

    rows = []
    for fold in folds:
        fold_num = fold.get('fold', 0)
        train_start = fold.get('train_start', '')
        train_end = fold.get('train_end', '')
        test_start = fold.get('test_start', '')
        test_end = fold.get('test_end', '')
        train_days = fold.get('train_days', 0)
        test_days = fold.get('test_days', 0)

        rows.append(f'''
            <tr>
                <td style="font-weight:600;">Fold {fold_num}</td>
                <td>{train_start} - {train_end}</td>
                <td style="color:{COLORS['muted']}">{train_days}d</td>
                <td>{test_start} - {test_end}</td>
                <td style="color:{COLORS['muted']}">{test_days}d</td>
            </tr>
        ''')

    return f'''
        <table class="comparison-table" style="font-size:0.9em;">
            <thead>
                <tr>
                    <th>Fold</th>
                    <th>Train Period</th>
                    <th>Days</th>
                    <th>Test Period (OOS)</th>
                    <th>Days</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    '''


def generate_walk_forward_section(wf_data: dict) -> str:
    """Generate complete walk-forward analysis section."""
    if not wf_data:
        return ''

    n_folds = wf_data.get('n_folds', 0)
    data_range = wf_data.get('data_range', {})
    run_date = wf_data.get('run_date', '')

    return f'''
        <div class="wf-section">
            <div class="wf-section-header">
                <h2>Walk-Forward Analysis</h2>
                <p>Expanding window validation across {n_folds} out-of-sample periods ({data_range.get('start', '')} to {data_range.get('end', '')})</p>
            </div>

            <!-- Returns by Fold Chart -->
            <div class="equity-section">
                <h3>Out-of-Sample Returns by Fold</h3>
                {generate_walk_forward_chart_svg(wf_data)}
                {generate_walk_forward_legend(wf_data)}
            </div>

            <div class="grid">
                <!-- Summary Table -->
                <div class="card" style="grid-column:span 2;">
                    <h3>Walk-Forward Summary</h3>
                    {generate_walk_forward_summary_table(wf_data)}
                </div>
            </div>

            <div class="grid">
                <!-- Fold Periods -->
                <div class="card" style="grid-column:span 2;">
                    <h3>Fold Periods (Expanding Window)</h3>
                    {generate_walk_forward_folds_table(wf_data)}
                    <div style="margin-top:12px;color:{COLORS['muted']};font-size:0.8em;">
                        Training window expands with each fold, ensuring strategies are tested on truly out-of-sample data.
                    </div>
                </div>
            </div>
        </div>
    '''


# =============================================================================
# INDEX PAGE GENERATION
# =============================================================================

def generate_index_strategy_card(result: dict, idx: int) -> str:
    """Generate a strategy card for the index page."""
    strategy_id = result.get('strategy_id', 'unknown')
    strategy_name = result.get('strategy_name', 'Unknown Strategy')
    run_date = result.get('run_date', '')
    test = result.get('test', {})
    benchmark = result.get('benchmark', {})
    wf = result.get('walk_forward', {})

    color = STRATEGY_COLORS[idx % len(STRATEGY_COLORS)]

    # Calculate vs benchmark
    test_return = test.get('return_pct', 0)
    bh_return = benchmark.get('test_return', 0)
    vs_bh = test_return - bh_return

    # Format date
    try:
        dt = datetime.fromisoformat(run_date.replace('Z', '+00:00'))
        run_date_str = dt.strftime("%Y-%m-%d %H:%M")
    except:
        run_date_str = run_date[:16] if run_date else 'N/A'

    # Walk-forward summary
    wf_html = ""
    if wf and wf.get('summary'):
        summary = wf.get('summary', {}).get(strategy_id, {})
        if summary:
            win_folds = summary.get('win_folds', 0)
            total_folds = summary.get('total_folds', 0)
            beats_bh = summary.get('beats_bh', 0)
            wf_html = f'''
                <div style="display:flex;justify-content:space-between;margin-top:8px;padding-top:8px;border-top:1px solid {COLORS['border']};font-size:0.8em;color:{COLORS['muted']};">
                    <span>WF: {win_folds}/{total_folds} profitable</span>
                    <span>Beats B&H: {beats_bh}/{total_folds}</span>
                </div>
            '''

    # Detail page link
    detail_file = f"backtest_{strategy_id.lower().replace('-', '')}.html"

    return f'''
        <a href="{detail_file}" class="strategy-card-link">
            <div class="strategy-card">
                <div class="card-header" style="border-left:4px solid {color};">
                    <div class="card-id">{strategy_id}</div>
                    <div class="card-name">{strategy_name}</div>
                </div>

                <div class="card-metrics">
                    <div class="metric">
                        <div class="metric-label">Test Return</div>
                        <div class="metric-value" style="color:{COLORS['green'] if test_return >= 0 else COLORS['red']}">{test_return:+.1f}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">vs B&H</div>
                        <div class="metric-value" style="color:{COLORS['green'] if vs_bh >= 0 else COLORS['red']}">{vs_bh:+.1f}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Sharpe</div>
                        <div class="metric-value" style="color:{COLORS['green'] if test.get('sharpe', 0) > 1 else COLORS['muted']}">{test.get('sharpe', 0):.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Max DD</div>
                        <div class="metric-value" style="color:{COLORS['red']}">{test.get('max_dd', 0):.1f}%</div>
                    </div>
                </div>

                <div class="card-footer">
                    <span>Trades: {test.get('num_trades', 0)}</span>
                    <span>Win: {test.get('win_rate', 0):.0f}%</span>
                </div>

                {wf_html}

                <div class="card-updated">Last run: {run_date_str}</div>
            </div>
        </a>
    '''


def generate_index_page(results: list) -> str:
    """Generate the index page listing all strategies."""

    # Generate strategy cards
    strategy_cards = ""
    for idx, result in enumerate(results):
        strategy_cards += generate_index_strategy_card(result, idx)

    # Summary stats
    total_strategies = len(results)
    profitable = sum(1 for r in results if r.get('test', {}).get('return_pct', 0) > 0)
    beats_bh = sum(1 for r in results if r.get('test', {}).get('return_pct', 0) > r.get('benchmark', {}).get('test_return', 0))

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Results - Strategy Index</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: {COLORS['bg']};
            color: {COLORS['text']};
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
        .header .subtitle {{
            color: {COLORS['muted']};
            font-size: 0.9em;
        }}
        .header .nav {{
            margin-top: 16px;
        }}
        .header .nav a {{
            display: inline-block;
            padding: 8px 16px;
            margin: 0 8px;
            background: rgba(245, 158, 11, 0.1);
            color: {COLORS['orange']};
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
            max-width: 1400px;
            margin: 0 auto;
        }}

        /* Summary stats */
        .summary {{
            display: flex;
            justify-content: center;
            gap: 32px;
            margin-bottom: 32px;
            padding: 20px;
            background: {COLORS['card']};
            border-radius: 12px;
            border: 1px solid {COLORS['border']};
        }}
        .summary-stat {{
            text-align: center;
        }}
        .summary-stat .value {{
            font-size: 2em;
            font-weight: 700;
        }}
        .summary-stat .label {{
            color: {COLORS['muted']};
            font-size: 0.85em;
        }}

        /* Strategy cards grid */
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
        }}
        .strategy-card-link {{
            text-decoration: none;
            color: inherit;
        }}
        .strategy-card {{
            background: {COLORS['card']};
            border-radius: 12px;
            padding: 20px;
            border: 1px solid {COLORS['border']};
            transition: all 0.3s ease;
        }}
        .strategy-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
            border-color: {COLORS['orange']};
        }}
        .card-header {{
            padding-left: 12px;
            margin-bottom: 16px;
        }}
        .card-id {{
            font-size: 0.75em;
            color: {COLORS['muted']};
            letter-spacing: 0.1em;
        }}
        .card-name {{
            font-size: 1.1em;
            font-weight: 600;
            margin-top: 4px;
        }}
        .card-metrics {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }}
        .metric {{
            background: {COLORS['bg']};
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-label {{
            font-size: 0.7em;
            color: {COLORS['muted']};
            margin-bottom: 4px;
        }}
        .metric-value {{
            font-size: 1.2em;
            font-weight: 600;
        }}
        .card-footer {{
            display: flex;
            justify-content: space-between;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid {COLORS['border']};
            color: {COLORS['muted']};
            font-size: 0.85em;
        }}
        .card-updated {{
            margin-top: 12px;
            font-size: 0.75em;
            color: {COLORS['muted']};
            text-align: right;
        }}

        .footer {{
            text-align: center;
            margin-top: 40px;
            color: {COLORS['muted']};
            font-size: 0.8em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Backtest Results</h1>
        <div class="subtitle">Click on a strategy to view detailed results</div>
        <div class="nav">
            <a href="dashboard_runs.html">All Runs</a>
            <a href="dashboard.html">Dashboard</a>
            <a href="dashboard_signals.html">Trading Signals</a>
        </div>
    </div>

    <div class="container">
        <div class="summary">
            <div class="summary-stat">
                <div class="value">{total_strategies}</div>
                <div class="label">Total Strategies</div>
            </div>
            <div class="summary-stat">
                <div class="value" style="color:{COLORS['green']}">{profitable}</div>
                <div class="label">Profitable (Test)</div>
            </div>
            <div class="summary-stat">
                <div class="value" style="color:{COLORS['green'] if beats_bh > 0 else COLORS['muted']}">{beats_bh}</div>
                <div class="label">Beat Buy & Hold</div>
            </div>
        </div>

        <div class="cards-grid">
            {strategy_cards}
        </div>
    </div>

    <div class="footer">
        <p>Run <code>python scripts/backtest_vectorbt.py --all</code> to update all backtests</p>
    </div>
</body>
</html>
'''
    return html


# =============================================================================
# DETAIL PAGE GENERATION
# =============================================================================

def generate_detail_page(result: dict, idx: int = 0) -> str:
    """Generate a detail page for a single strategy."""
    strategy_id = result.get('strategy_id', 'unknown')
    strategy_name = result.get('strategy_name', 'Unknown Strategy')
    trade_chart_html = result.get('trade_chart_html', '')

    # Load strategy config for parameters display
    config_path = result.get('_config_path')
    strategy_config = load_strategy_config(config_path) if config_path else {}

    # Convert to format expected by existing card generators
    data = {
        "strategies": [{
            "name": strategy_name,
            "train": result.get('train', {}),
            "test": result.get('test', {}),
            "equity_curve": result.get('equity_curve', []),
            "trades": result.get('trades', []),
            "monte_carlo": result.get('monte_carlo', None)
        }],
        "benchmark": result.get('benchmark', {}),
        "train_period": result.get('train_period', {}),
        "test_period": result.get('test_period', {}),
        "run_date": result.get('run_date', ''),
        "position_sizing": result.get('position_sizing', {}),
        "exit_strategy": result.get('exit_strategy', '')
    }

    wf_data = result.get('walk_forward')

    # Use existing generators
    return generate_detail_page_html(data, wf_data, strategy_id, strategy_name, trade_chart_html, strategy_config)


def generate_detail_page_html(data: dict, wf_data: dict, strategy_id: str, strategy_name: str, trade_chart_html: str = "", strategy_config: dict = None) -> str:
    """Generate complete detail page HTML for a strategy."""
    strategies = data.get("strategies", [])
    color = STRATEGY_COLORS[0]  # Use first color for single strategy

    # Generate header with strategy parameters
    header_card = generate_header_card(data, strategy_config)

    # Generate strategy card
    strategy_card = generate_strategy_card(strategies[0], color) if strategies else ""

    # Generate detailed stats card
    stats_card = generate_stats_card(strategies[0]) if strategies else ""

    # Generate Monte Carlo card
    mc_card = generate_monte_carlo_card(strategies[0], color) if strategies else ""

    # Generate interactive trade chart section
    trade_chart_section = ""
    if trade_chart_html:
        trade_chart_section = f'''
        <div class="equity-section">
            <h3>Interactive Trade Chart</h3>
            <p style="color:{COLORS['muted']};font-size:0.85em;margin-bottom:16px;">
                Zoom with scroll wheel or range slider. Click legend items to toggle. Drag to pan.
            </p>
            {trade_chart_html}
        </div>
        '''

    # Generate walk-forward section if data available
    walk_forward_html = ""
    if wf_data:
        # Adapt walk-forward data for single strategy display
        adapted_wf = {
            'folds': wf_data.get('folds', []),
            'summary': wf_data.get('summary', {})
        }
        walk_forward_html = generate_walk_forward_section_single(adapted_wf, strategy_id)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{strategy_id} - {strategy_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: {COLORS['bg']};
            color: {COLORS['text']};
            min-height: 100vh;
            padding: 24px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 32px;
        }}
        .header h1 {{
            font-size: 1.8em;
            margin-bottom: 4px;
        }}
        .header .subtitle {{
            color: {COLORS['muted']};
            font-size: 1em;
        }}
        .header .nav {{
            margin-top: 16px;
        }}
        .header .nav a {{
            display: inline-block;
            padding: 8px 16px;
            margin: 0 8px;
            background: rgba(245, 158, 11, 0.1);
            color: {COLORS['orange']};
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
        .header .nav a.back {{
            background: rgba(59, 130, 246, 0.1);
            color: {COLORS['blue']};
            border-color: rgba(59, 130, 246, 0.3);
        }}
        .header .nav a.back:hover {{
            background: rgba(59, 130, 246, 0.2);
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        .card {{
            background: {COLORS['card']};
            border-radius: 12px;
            padding: 20px;
            border: 1px solid {COLORS['border']};
        }}
        .card h3 {{
            margin-bottom: 16px;
            color: #e2e8f0;
            font-size: 1.1em;
        }}

        /* Backtest config (unified header + params) */
        .backtest-config {{
            background: {COLORS['card']};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid {COLORS['border']};
        }}
        .config-header {{
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid {COLORS['border']};
        }}
        .config-row {{
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .config-item {{
            text-align: center;
            min-width: 120px;
        }}
        .config-label {{
            color: {COLORS['muted']};
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}
        .config-value {{
            font-size: 1em;
            font-weight: 600;
        }}
        .config-sublabel {{
            color: {COLORS['muted']};
            font-size: 0.75em;
            margin-top: 2px;
        }}
        .config-signals {{
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
        }}
        .params-section {{
            flex: 1;
            min-width: 280px;
        }}
        .params-title {{
            font-size: 0.75em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 10px;
        }}
        .params-conditions {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .param-chip {{
            background: {COLORS['bg']};
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.85em;
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
            border: 1px solid {COLORS['border']};
        }}

        /* Legacy header-card (for backward compat) */
        .header-card {{
            display: flex;
            justify-content: space-around;
            background: {COLORS['card']};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid {COLORS['border']};
        }}
        .header-item {{
            text-align: center;
        }}
        .header-label {{
            color: {COLORS['muted']};
            font-size: 0.8em;
            margin-bottom: 4px;
        }}
        .header-value {{
            font-size: 1.1em;
            font-weight: 600;
        }}
        .header-sublabel {{
            color: {COLORS['muted']};
            font-size: 0.75em;
            margin-top: 2px;
        }}

        /* Comparison table */
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .comparison-table th, .comparison-table td {{
            padding: 12px 8px;
            text-align: left;
            border-bottom: 1px solid {COLORS['border']};
        }}
        .comparison-table th {{
            color: {COLORS['muted']};
            font-weight: 500;
            font-size: 0.85em;
        }}
        .comparison-table tr:hover {{
            background: rgba(255,255,255,0.02);
        }}

        /* Metric grid */
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }}
        .metric-box {{
            background: #0f172a;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-label {{
            color: {COLORS['muted']};
            font-size: 0.75em;
            margin-bottom: 4px;
        }}
        .metric-value {{
            font-size: 1.3em;
            font-weight: 600;
        }}

        /* Trades */
        .trades-container {{
            max-height: 300px;
            overflow-y: auto;
        }}
        .trade-row {{
            display: flex;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid {COLORS['border']};
        }}
        .trade-bar {{
            width: 4px;
            height: 24px;
            border-radius: 2px;
            margin-right: 12px;
        }}
        .trade-info {{
            flex: 1;
        }}
        .trade-strategy {{
            font-weight: 500;
            display: block;
        }}
        .trade-dates {{
            color: {COLORS['muted']};
            font-size: 0.8em;
        }}
        .trade-pnl {{
            font-weight: 600;
        }}

        /* Expanded trades */
        .trades-container-expanded {{
            max-height: 500px;
            overflow-y: auto;
        }}
        .trade-row-expanded {{
            display: flex;
            padding: 12px 0;
            border-bottom: 1px solid {COLORS['border']};
        }}
        .trade-row-expanded:last-child {{
            border-bottom: none;
        }}
        .trade-main {{
            flex: 1;
        }}
        .trade-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}
        .trade-details {{
            display: flex;
            gap: 16px;
            margin-top: 8px;
            flex-wrap: wrap;
        }}
        .trade-detail {{
            display: flex;
            flex-direction: column;
            background: {COLORS['bg']};
            padding: 6px 10px;
            border-radius: 6px;
            min-width: 80px;
        }}
        .trade-detail-label {{
            font-size: 0.65em;
            color: {COLORS['muted']};
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .trade-detail-value {{
            font-size: 0.9em;
            font-weight: 600;
            margin-top: 2px;
        }}

        /* Exit type badges */
        .exit-badge {{
            font-size: 0.65em;
            font-weight: 600;
            padding: 2px 6px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .exit-signal {{
            background: rgba(34, 197, 94, 0.2);
            color: {COLORS['green']};
            border: 1px solid rgba(34, 197, 94, 0.3);
        }}
        .exit-stop {{
            background: rgba(239, 68, 68, 0.2);
            color: {COLORS['red']};
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}

        /* Trade triggers */
        .trade-triggers {{
            background: {COLORS['bg']};
            border-radius: 6px;
            padding: 8px 10px;
            margin: 8px 0;
            font-size: 0.8em;
        }}
        .trigger-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }}
        .trigger-row:last-child {{
            margin-bottom: 0;
        }}
        .trigger-label {{
            font-weight: 600;
            color: {COLORS['muted']};
            font-size: 0.85em;
            min-width: 45px;
        }}
        .trigger-values {{
            color: {COLORS['text']};
        }}
        .conditions-badge {{
            background: {COLORS['green']};
            color: {COLORS['bg']};
            padding: 1px 6px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.9em;
            margin-right: 6px;
        }}

        /* Stats grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }}
        .stats-section {{
            background: {COLORS['bg']};
            border-radius: 8px;
            padding: 12px;
        }}
        .stats-section-title {{
            font-size: 0.75em;
            font-weight: 600;
            color: {COLORS['muted']};
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid {COLORS['border']};
        }}
        .stats-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
        }}
        .stats-label {{
            font-size: 0.85em;
            color: {COLORS['muted']};
        }}
        .stats-value {{
            font-size: 0.95em;
            font-weight: 600;
        }}

        /* Histogram */
        .histogram {{
            display: flex;
            align-items: flex-end;
            height: 120px;
            gap: 4px;
        }}
        .hist-bar-container {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .hist-bar {{
            width: 100%;
            min-height: 4px;
            border-radius: 2px 2px 0 0;
        }}
        .hist-label {{
            font-size: 0.65em;
            color: {COLORS['muted']};
            margin-top: 4px;
            transform: rotate(-45deg);
        }}

        /* Equity chart section */
        .equity-section {{
            background: {COLORS['card']};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid {COLORS['border']};
        }}
        .equity-section h3 {{
            margin-bottom: 16px;
        }}

        .footer {{
            text-align: center;
            margin-top: 32px;
            color: {COLORS['muted']};
            font-size: 0.8em;
        }}

        /* Monte Carlo styles */
        .mc-section {{
            margin-top: 32px;
            padding-top: 24px;
            border-top: 2px solid {COLORS['border']};
        }}
        .mc-section-header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .mc-section-header h2 {{
            font-size: 1.5em;
            color: {COLORS['purple']};
            margin-bottom: 8px;
        }}
        .mc-section-header p {{
            color: {COLORS['muted']};
            font-size: 0.9em;
        }}
        .mc-stats {{
            font-size: 0.9em;
        }}
        .mc-stat-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
        }}
        .mc-label {{
            color: {COLORS['muted']};
        }}
        .mc-value {{
            font-weight: 600;
        }}

        /* Walk-Forward styles */
        .wf-section {{
            margin-top: 32px;
            padding-top: 24px;
            border-top: 2px solid {COLORS['border']};
        }}
        .wf-section-header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .wf-section-header h2 {{
            font-size: 1.5em;
            color: {COLORS['blue']};
            margin-bottom: 8px;
        }}
        .wf-section-header p {{
            color: {COLORS['muted']};
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{strategy_id}</h1>
        <div class="subtitle">{strategy_name}</div>
        <div class="nav">
            <a href="dashboard_backtest.html" class="back">&larr; All Strategies</a>
            <a href="dashboard.html">Dashboard</a>
            <a href="dashboard_signals.html">Trading Signals</a>
        </div>
    </div>

    <div class="container">
        {header_card}

        <!-- Equity Curves -->
        <div class="equity-section">
            <h3>Equity Curve (Test Period)</h3>
            {generate_equity_curve_svg(data)}
            {generate_legend(data)}
        </div>

        <!-- Strategy Card -->
        <div class="grid">
            {strategy_card}
            {generate_return_distribution(data)}
        </div>

        <!-- Detailed Statistics -->
        {stats_card}

        <!-- Trade Timeline -->
        <div class="grid">
            {generate_trades_timeline(data)}
        </div>

        <!-- Interactive Trade Chart (Plotly) -->
        {trade_chart_section}

        <!-- Monte Carlo Section -->
        <div class="mc-section">
            <div class="mc-section-header">
                <h2>Monte Carlo Simulation</h2>
                <p>Testing strategy robustness by shuffling trade order 1,000 times</p>
            </div>
            <div class="grid">
                {mc_card}
            </div>
        </div>

        <!-- Walk-Forward Analysis Section -->
        {walk_forward_html}
    </div>

    <div class="footer">
        <p>Generated by VectorBT Backtest Framework | Run <code>python scripts/backtest_vectorbt.py --strategy {strategy_id.lower()}</code> to update</p>
    </div>
</body>
</html>
'''
    return html


def generate_walk_forward_section_single(wf_data: dict, strategy_id: str) -> str:
    """Generate walk-forward section for a single strategy."""
    if not wf_data or not wf_data.get('summary'):
        return ''

    folds = wf_data.get('folds', [])
    summary = wf_data.get('summary', {})

    # Get this strategy's summary
    strat_summary = summary.get(strategy_id, {})
    bh_summary = summary.get('Buy & Hold', {})

    if not strat_summary:
        return ''

    n_folds = len(folds)
    fold_returns = strat_summary.get('fold_returns', [])
    bh_returns = bh_summary.get('fold_returns', [])

    # Generate fold bars
    bars_html = ""
    for i, fold in enumerate(folds):
        strat_ret = fold_returns[i] if i < len(fold_returns) else 0
        bh_ret = bh_returns[i] if i < len(bh_returns) else 0

        strat_color = COLORS['green'] if strat_ret >= 0 else COLORS['red']
        bh_color = COLORS['muted']

        bars_html += f'''
            <div class="wf-fold">
                <div class="wf-fold-label">Fold {fold.get('fold', i+1)}</div>
                <div class="wf-fold-period">{fold.get('test_start', '')[:7]}</div>
                <div class="wf-fold-bars">
                    <div class="wf-bar">
                        <div class="wf-bar-label" style="color:{strat_color}">{strat_ret:+.0f}%</div>
                        <div class="wf-bar-fill" style="background:{strat_color};height:{min(abs(strat_ret), 100)}px;"></div>
                    </div>
                    <div class="wf-bar">
                        <div class="wf-bar-label" style="color:{bh_color}">{bh_ret:+.0f}%</div>
                        <div class="wf-bar-fill" style="background:{bh_color};height:{min(abs(bh_ret), 100)}px;opacity:0.5;"></div>
                    </div>
                </div>
            </div>
        '''

    return f'''
        <div class="wf-section">
            <div class="wf-section-header">
                <h2>Walk-Forward Analysis</h2>
                <p>{n_folds} out-of-sample periods with expanding training window</p>
            </div>

            <style>
                .wf-folds {{ display: flex; justify-content: space-around; margin-bottom: 24px; }}
                .wf-fold {{ text-align: center; }}
                .wf-fold-label {{ font-weight: 600; font-size: 0.9em; }}
                .wf-fold-period {{ font-size: 0.75em; color: {COLORS['muted']}; margin-bottom: 8px; }}
                .wf-fold-bars {{ display: flex; gap: 8px; justify-content: center; align-items: flex-end; height: 120px; }}
                .wf-bar {{ width: 30px; display: flex; flex-direction: column; align-items: center; }}
                .wf-bar-label {{ font-size: 0.7em; margin-bottom: 4px; }}
                .wf-bar-fill {{ width: 100%; border-radius: 4px 4px 0 0; min-height: 4px; }}
                .wf-legend {{ display: flex; justify-content: center; gap: 24px; margin-top: 16px; font-size: 0.85em; }}
                .wf-legend-item {{ display: flex; align-items: center; gap: 8px; }}
                .wf-legend-dot {{ width: 12px; height: 12px; border-radius: 2px; }}
            </style>

            <div class="card">
                <div class="wf-folds">
                    {bars_html}
                </div>
                <div class="wf-legend">
                    <div class="wf-legend-item">
                        <div class="wf-legend-dot" style="background:{COLORS['green']};"></div>
                        <span>{strategy_id}</span>
                    </div>
                    <div class="wf-legend-item">
                        <div class="wf-legend-dot" style="background:{COLORS['muted']};opacity:0.5;"></div>
                        <span>Buy & Hold</span>
                    </div>
                </div>

                <div style="margin-top:24px;">
                    <table class="comparison-table">
                        <thead>
                            <tr>
                                <th>Metric</th>
                                <th>{strategy_id}</th>
                                <th>Buy & Hold</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Average Return</td>
                                <td style="color:{COLORS['green'] if strat_summary.get('avg_return', 0) >= 0 else COLORS['red']}">{strat_summary.get('avg_return', 0):+.1f}%</td>
                                <td style="color:{COLORS['muted']}">{bh_summary.get('avg_return', 0):+.1f}%</td>
                            </tr>
                            <tr>
                                <td>Profitable Folds</td>
                                <td>{strat_summary.get('win_folds', 0)}/{strat_summary.get('total_folds', 0)}</td>
                                <td style="color:{COLORS['muted']}">{bh_summary.get('win_folds', 0)}/{bh_summary.get('total_folds', 0)}</td>
                            </tr>
                            <tr>
                                <td>Beats Benchmark</td>
                                <td>{strat_summary.get('beats_bh', 0)}/{strat_summary.get('total_folds', 0)}</td>
                                <td style="color:{COLORS['muted']}">-</td>
                            </tr>
                            <tr>
                                <td>Average Sharpe</td>
                                <td style="color:{COLORS['green'] if strat_summary.get('avg_sharpe', 0) > 0.5 else COLORS['muted']}">{strat_summary.get('avg_sharpe', 0):.2f}</td>
                                <td style="color:{COLORS['muted']}">-</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    '''


# =============================================================================
# LEGACY HTML GENERATION (for backward compatibility)
# =============================================================================

def generate_legacy_dashboard_html(data: dict, wf_data: dict = None) -> str:
    """Generate complete backtest dashboard HTML (legacy format)."""
    strategies = data.get("strategies", [])
    strat_colors = [COLORS["green"], COLORS["orange"], COLORS["purple"], COLORS["blue"]]

    # Generate strategy cards
    strategy_cards = ""
    for idx, strat in enumerate(strategies):
        color = strat_colors[idx % len(strat_colors)]
        strategy_cards += generate_strategy_card(strat, color)

    # Generate walk-forward section if data available
    walk_forward_html = generate_walk_forward_section(wf_data) if wf_data else ""

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Results Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: {COLORS['bg']};
            color: {COLORS['text']};
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
        .header .nav {{
            margin-top: 12px;
        }}
        .header .nav a {{
            display: inline-block;
            padding: 8px 16px;
            margin: 0 8px;
            background: rgba(245, 158, 11, 0.1);
            color: {COLORS['orange']};
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
            max-width: 1400px;
            margin: 0 auto;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        .card {{
            background: {COLORS['card']};
            border-radius: 12px;
            padding: 20px;
            border: 1px solid {COLORS['border']};
        }}
        .card h3 {{
            margin-bottom: 16px;
            color: #e2e8f0;
            font-size: 1.1em;
        }}

        /* Backtest config (unified header + params) */
        .backtest-config {{
            background: {COLORS['card']};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid {COLORS['border']};
        }}
        .config-header {{
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid {COLORS['border']};
        }}
        .config-row {{
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .config-item {{
            text-align: center;
            min-width: 120px;
        }}
        .config-label {{
            color: {COLORS['muted']};
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}
        .config-value {{
            font-size: 1em;
            font-weight: 600;
        }}
        .config-sublabel {{
            color: {COLORS['muted']};
            font-size: 0.75em;
            margin-top: 2px;
        }}
        .config-signals {{
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
        }}
        .params-section {{
            flex: 1;
            min-width: 280px;
        }}
        .params-title {{
            font-size: 0.75em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 10px;
        }}
        .params-conditions {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .param-chip {{
            background: {COLORS['bg']};
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.85em;
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
            border: 1px solid {COLORS['border']};
        }}

        /* Legacy header-card (for backward compat) */
        .header-card {{
            display: flex;
            justify-content: space-around;
            background: {COLORS['card']};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid {COLORS['border']};
        }}
        .header-item {{
            text-align: center;
        }}
        .header-label {{
            color: {COLORS['muted']};
            font-size: 0.8em;
            margin-bottom: 4px;
        }}
        .header-value {{
            font-size: 1.1em;
            font-weight: 600;
        }}
        .header-sublabel {{
            color: {COLORS['muted']};
            font-size: 0.75em;
            margin-top: 2px;
        }}

        /* Comparison table */
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .comparison-table th, .comparison-table td {{
            padding: 12px 8px;
            text-align: left;
            border-bottom: 1px solid {COLORS['border']};
        }}
        .comparison-table th {{
            color: {COLORS['muted']};
            font-weight: 500;
            font-size: 0.85em;
        }}
        .comparison-table tr:hover {{
            background: rgba(255,255,255,0.02);
        }}

        /* Metric grid */
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }}
        .metric-box {{
            background: #0f172a;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-label {{
            color: {COLORS['muted']};
            font-size: 0.75em;
            margin-bottom: 4px;
        }}
        .metric-value {{
            font-size: 1.3em;
            font-weight: 600;
        }}

        /* Trades */
        .trades-container {{
            max-height: 300px;
            overflow-y: auto;
        }}
        .trade-row {{
            display: flex;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid {COLORS['border']};
        }}
        .trade-bar {{
            width: 4px;
            height: 24px;
            border-radius: 2px;
            margin-right: 12px;
        }}
        .trade-info {{
            flex: 1;
        }}
        .trade-strategy {{
            font-weight: 500;
            display: block;
        }}
        .trade-dates {{
            color: {COLORS['muted']};
            font-size: 0.8em;
        }}
        .trade-pnl {{
            font-weight: 600;
        }}

        /* Expanded trades */
        .trades-container-expanded {{
            max-height: 500px;
            overflow-y: auto;
        }}
        .trade-row-expanded {{
            display: flex;
            padding: 12px 0;
            border-bottom: 1px solid {COLORS['border']};
        }}
        .trade-row-expanded:last-child {{
            border-bottom: none;
        }}
        .trade-main {{
            flex: 1;
        }}
        .trade-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}
        .trade-details {{
            display: flex;
            gap: 16px;
            margin-top: 8px;
            flex-wrap: wrap;
        }}
        .trade-detail {{
            display: flex;
            flex-direction: column;
            background: {COLORS['bg']};
            padding: 6px 10px;
            border-radius: 6px;
            min-width: 80px;
        }}
        .trade-detail-label {{
            font-size: 0.65em;
            color: {COLORS['muted']};
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .trade-detail-value {{
            font-size: 0.9em;
            font-weight: 600;
            margin-top: 2px;
        }}

        /* Exit type badges */
        .exit-badge {{
            font-size: 0.65em;
            font-weight: 600;
            padding: 2px 6px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .exit-signal {{
            background: rgba(34, 197, 94, 0.2);
            color: {COLORS['green']};
            border: 1px solid rgba(34, 197, 94, 0.3);
        }}
        .exit-stop {{
            background: rgba(239, 68, 68, 0.2);
            color: {COLORS['red']};
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}

        /* Trade triggers */
        .trade-triggers {{
            background: {COLORS['bg']};
            border-radius: 6px;
            padding: 8px 10px;
            margin: 8px 0;
            font-size: 0.8em;
        }}
        .trigger-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }}
        .trigger-row:last-child {{
            margin-bottom: 0;
        }}
        .trigger-label {{
            font-weight: 600;
            color: {COLORS['muted']};
            font-size: 0.85em;
            min-width: 45px;
        }}
        .trigger-values {{
            color: {COLORS['text']};
        }}
        .conditions-badge {{
            background: {COLORS['green']};
            color: {COLORS['bg']};
            padding: 1px 6px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.9em;
            margin-right: 6px;
        }}

        /* Stats grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }}
        .stats-section {{
            background: {COLORS['bg']};
            border-radius: 8px;
            padding: 12px;
        }}
        .stats-section-title {{
            font-size: 0.75em;
            font-weight: 600;
            color: {COLORS['muted']};
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid {COLORS['border']};
        }}
        .stats-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
        }}
        .stats-label {{
            font-size: 0.85em;
            color: {COLORS['muted']};
        }}
        .stats-value {{
            font-size: 0.95em;
            font-weight: 600;
        }}

        /* Histogram */
        .histogram {{
            display: flex;
            align-items: flex-end;
            height: 120px;
            gap: 4px;
        }}
        .hist-bar-container {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .hist-bar {{
            width: 100%;
            min-height: 4px;
            border-radius: 2px 2px 0 0;
        }}
        .hist-label {{
            font-size: 0.65em;
            color: {COLORS['muted']};
            margin-top: 4px;
            transform: rotate(-45deg);
        }}

        /* Equity chart section */
        .equity-section {{
            background: {COLORS['card']};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid {COLORS['border']};
        }}
        .equity-section h3 {{
            margin-bottom: 16px;
        }}

        .footer {{
            text-align: center;
            margin-top: 32px;
            color: {COLORS['muted']};
            font-size: 0.8em;
        }}

        /* Monte Carlo styles */
        .mc-section {{
            margin-top: 32px;
            padding-top: 24px;
            border-top: 2px solid {COLORS['border']};
        }}
        .mc-section-header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .mc-section-header h2 {{
            font-size: 1.5em;
            color: {COLORS['purple']};
            margin-bottom: 8px;
        }}
        .mc-section-header p {{
            color: {COLORS['muted']};
            font-size: 0.9em;
        }}
        .mc-stats {{
            font-size: 0.9em;
        }}
        .mc-stat-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
        }}
        .mc-label {{
            color: {COLORS['muted']};
        }}
        .mc-value {{
            font-weight: 600;
        }}

        /* Walk-Forward styles */
        .wf-section {{
            margin-top: 32px;
            padding-top: 24px;
            border-top: 2px solid {COLORS['border']};
        }}
        .wf-section-header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .wf-section-header h2 {{
            font-size: 1.5em;
            color: {COLORS['blue']};
            margin-bottom: 8px;
        }}
        .wf-section-header p {{
            color: {COLORS['muted']};
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Backtest Results Dashboard</h1>
        <div class="nav">
            <a href="dashboard.html">Dashboard</a>
            <a href="dashboard_signals.html">Trading Signals</a>
            <a href="dashboard_quality.html">Data Quality</a>
        </div>
    </div>

    <div class="container">
        {generate_header_card(data)}

        <!-- Equity Curves -->
        <div class="equity-section">
            <h3>Equity Curves (Test Period)</h3>
            {generate_equity_curve_svg(data)}
            {generate_legend(data)}
        </div>

        <!-- Comparison Table -->
        <div class="grid">
            {generate_comparison_table(data)}
        </div>

        <!-- Strategy Cards -->
        <div class="grid">
            {strategy_cards}
        </div>

        <!-- Trade Analysis -->
        <div class="grid">
            {generate_trades_timeline(data)}
            {generate_return_distribution(data)}
        </div>

        <!-- Monte Carlo Section -->
        <div class="mc-section">
            <div class="mc-section-header">
                <h2>Monte Carlo Simulation</h2>
                <p>Testing strategy robustness by shuffling trade order 1,000 times</p>
            </div>
            <div class="grid">
                {generate_monte_carlo_section(data)}
            </div>
        </div>

        <!-- Walk-Forward Analysis Section -->
        {walk_forward_html}
    </div>

    <div class="footer">
        <p>Generated by VectorBT Backtest Framework | Run <code>python scripts/backtest_vectorbt.py</code> to update</p>
    </div>
</body>
</html>
'''
    return html


# =============================================================================
# ALL RUNS BROWSER PAGE
# =============================================================================

def generate_runs_browser_page() -> str:
    """Generate interactive page to browse all backtest runs from database."""
    try:
        from src.backtest_db import BacktestDB, RUNS_DIR
        db = BacktestDB()
        runs = db.get_runs(limit=1000)
        stats = db.get_stats()
        strategies = db.get_strategies()
    except Exception as e:
        return f"<html><body><h1>Error loading database: {e}</h1></body></html>"

    # Generate table rows
    table_rows = []
    for run in runs:
        run_id = run['run_id']
        strategy_id = run['strategy_id'] or ''
        ret = run['return_pct'] or 0
        sharpe = run['sharpe'] or 0
        sortino = run['sortino'] or 0
        max_dd = run['max_dd'] or 0
        win_rate = run['win_rate'] or 0
        num_trades = run['num_trades'] or 0
        run_date = (run['run_date'] or '')[:16]

        ret_color = COLORS['green'] if ret >= 0 else COLORS['red']
        sharpe_color = COLORS['green'] if sharpe >= 1.0 else COLORS['muted']

        # Link to detail page (by strategy)
        detail_file = f"backtest_{strategy_id.lower().replace('-', '')}.html"

        table_rows.append(f'''
            <tr data-strategy="{strategy_id}" data-return="{ret}" data-sharpe="{sharpe}" data-dd="{max_dd}">
                <td><code>{run_id}</code></td>
                <td><a href="{detail_file}" class="strategy-link">{strategy_id}</a></td>
                <td style="color:{ret_color};font-weight:600;">{ret:+.1f}%</td>
                <td style="color:{sharpe_color}">{sharpe:.2f}</td>
                <td>{sortino:.2f}</td>
                <td style="color:{COLORS['red']}">{max_dd:.1f}%</td>
                <td>{win_rate:.0f}%</td>
                <td>{num_trades}</td>
                <td style="color:{COLORS['muted']}">{run_date}</td>
                <td><a href="run_details.html?id={run_id}" class="view-btn">View</a></td>
            </tr>
        ''')

    # Strategy filter options
    strategy_options = ''.join(
        f'<option value="{s["strategy_id"]}">{s["strategy_id"]} ({s["run_count"]} runs)</option>'
        for s in strategies
    )

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Backtest Runs</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: {COLORS['bg']};
            color: {COLORS['text']};
            min-height: 100vh;
            padding: 24px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 1.8em;
            margin-bottom: 8px;
        }}
        .header .subtitle {{
            color: {COLORS['muted']};
        }}
        .nav {{
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-top: 16px;
        }}
        .nav a {{
            padding: 8px 16px;
            background: rgba(245, 158, 11, 0.1);
            color: {COLORS['orange']};
            text-decoration: none;
            border-radius: 6px;
            border: 1px solid rgba(245, 158, 11, 0.3);
            font-size: 0.85em;
            transition: all 0.2s;
        }}
        .nav a:hover {{
            background: rgba(245, 158, 11, 0.2);
        }}
        .nav a.active {{
            background: {COLORS['orange']};
            color: {COLORS['bg']};
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}

        /* Stats bar */
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 32px;
            padding: 16px;
            background: {COLORS['card']};
            border-radius: 12px;
            margin-bottom: 24px;
            border: 1px solid {COLORS['border']};
        }}
        .stat {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 1.5em;
            font-weight: 700;
        }}
        .stat-label {{
            font-size: 0.8em;
            color: {COLORS['muted']};
        }}

        /* Filters */
        .filters {{
            display: flex;
            gap: 16px;
            margin-bottom: 16px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .filter-group {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .filter-group label {{
            font-size: 0.85em;
            color: {COLORS['muted']};
        }}
        .filter-group select, .filter-group input {{
            padding: 8px 12px;
            background: {COLORS['card']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            color: {COLORS['text']};
            font-size: 0.9em;
        }}
        .filter-group input {{
            width: 80px;
        }}
        .reset-btn {{
            padding: 8px 16px;
            background: {COLORS['card']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            color: {COLORS['muted']};
            cursor: pointer;
            font-size: 0.85em;
        }}
        .reset-btn:hover {{
            background: {COLORS['border']};
            color: {COLORS['text']};
        }}

        /* Table */
        .table-container {{
            background: {COLORS['card']};
            border-radius: 12px;
            border: 1px solid {COLORS['border']};
            overflow: hidden;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid {COLORS['border']};
        }}
        th {{
            background: {COLORS['bg']};
            color: {COLORS['muted']};
            font-weight: 600;
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            cursor: pointer;
            user-select: none;
            position: sticky;
            top: 0;
        }}
        th:hover {{
            color: {COLORS['text']};
        }}
        th.sorted-asc::after {{
            content: ' ▲';
            color: {COLORS['orange']};
        }}
        th.sorted-desc::after {{
            content: ' ▼';
            color: {COLORS['orange']};
        }}
        tbody tr:hover {{
            background: rgba(255, 255, 255, 0.02);
        }}
        tbody tr.hidden {{
            display: none;
        }}
        code {{
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 0.85em;
            color: {COLORS['muted']};
        }}
        .strategy-link {{
            color: {COLORS['blue']};
            text-decoration: none;
            font-weight: 600;
        }}
        .strategy-link:hover {{
            text-decoration: underline;
        }}
        .view-btn {{
            padding: 4px 12px;
            background: rgba(59, 130, 246, 0.1);
            color: {COLORS['blue']};
            text-decoration: none;
            border-radius: 4px;
            font-size: 0.85em;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}
        .view-btn:hover {{
            background: rgba(59, 130, 246, 0.2);
        }}

        .results-count {{
            padding: 12px 16px;
            color: {COLORS['muted']};
            font-size: 0.85em;
            border-top: 1px solid {COLORS['border']};
        }}

        .footer {{
            text-align: center;
            margin-top: 32px;
            color: {COLORS['muted']};
            font-size: 0.8em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>All Backtest Runs</h1>
        <div class="subtitle">{stats['total_runs']} runs across {stats['total_strategies']} strategies</div>
        <div class="nav">
            <a href="dashboard_backtest.html">Strategies</a>
            <a href="dashboard_runs.html" class="active">All Runs</a>
            <a href="dashboard.html">Dashboard</a>
        </div>
    </div>

    <div class="container">
        <div class="stats-bar">
            <div class="stat">
                <div class="stat-value">{stats['total_runs']}</div>
                <div class="stat-label">Total Runs</div>
            </div>
            <div class="stat">
                <div class="stat-value">{stats['total_strategies']}</div>
                <div class="stat-label">Strategies</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="filtered-count">{stats['total_runs']}</div>
                <div class="stat-label">Showing</div>
            </div>
        </div>

        <div class="filters">
            <div class="filter-group">
                <label>Strategy:</label>
                <select id="filter-strategy">
                    <option value="">All Strategies</option>
                    {strategy_options}
                </select>
            </div>
            <div class="filter-group">
                <label>Min Sharpe:</label>
                <input type="number" id="filter-sharpe" step="0.1" placeholder="0">
            </div>
            <div class="filter-group">
                <label>Min Return:</label>
                <input type="number" id="filter-return" step="1" placeholder="0">%
            </div>
            <div class="filter-group">
                <label>Max DD:</label>
                <input type="number" id="filter-dd" step="1" placeholder="-100">%
            </div>
            <button class="reset-btn" onclick="resetFilters()">Reset Filters</button>
        </div>

        <div class="table-container">
            <table id="runs-table">
                <thead>
                    <tr>
                        <th data-col="run_id">Run ID</th>
                        <th data-col="strategy">Strategy</th>
                        <th data-col="return" data-type="number">Return</th>
                        <th data-col="sharpe" data-type="number">Sharpe</th>
                        <th data-col="sortino" data-type="number">Sortino</th>
                        <th data-col="dd" data-type="number">Max DD</th>
                        <th data-col="winrate" data-type="number">Win Rate</th>
                        <th data-col="trades" data-type="number">Trades</th>
                        <th data-col="date">Date</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
            <div class="results-count">
                Showing <span id="visible-count">{len(runs)}</span> of {len(runs)} runs
            </div>
        </div>
    </div>

    <div class="footer">
        <p>Database: {stats['db_path']}</p>
    </div>

    <script>
        // Sorting
        let currentSort = {{ col: 'date', dir: 'desc' }};

        document.querySelectorAll('th[data-col]').forEach(th => {{
            th.addEventListener('click', () => {{
                const col = th.dataset.col;
                const isNumber = th.dataset.type === 'number';

                // Toggle direction if same column
                if (currentSort.col === col) {{
                    currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
                }} else {{
                    currentSort.col = col;
                    currentSort.dir = 'desc';
                }}

                // Update header classes
                document.querySelectorAll('th').forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
                th.classList.add(currentSort.dir === 'asc' ? 'sorted-asc' : 'sorted-desc');

                // Sort rows
                const tbody = document.querySelector('#runs-table tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));

                rows.sort((a, b) => {{
                    let aVal = a.children[getColIndex(col)].textContent.trim();
                    let bVal = b.children[getColIndex(col)].textContent.trim();

                    if (isNumber) {{
                        aVal = parseFloat(aVal.replace(/[^-0-9.]/g, '')) || 0;
                        bVal = parseFloat(bVal.replace(/[^-0-9.]/g, '')) || 0;
                    }}

                    if (currentSort.dir === 'asc') {{
                        return aVal > bVal ? 1 : -1;
                    }} else {{
                        return aVal < bVal ? 1 : -1;
                    }}
                }});

                rows.forEach(row => tbody.appendChild(row));
            }});
        }});

        function getColIndex(col) {{
            const map = {{ run_id: 0, strategy: 1, return: 2, sharpe: 3, sortino: 4, dd: 5, winrate: 6, trades: 7, date: 8 }};
            return map[col] || 0;
        }}

        // Filtering
        function applyFilters() {{
            const strategyFilter = document.getElementById('filter-strategy').value;
            const sharpeFilter = parseFloat(document.getElementById('filter-sharpe').value) || -Infinity;
            const returnFilter = parseFloat(document.getElementById('filter-return').value) || -Infinity;
            const ddFilter = parseFloat(document.getElementById('filter-dd').value) || -Infinity;

            const rows = document.querySelectorAll('#runs-table tbody tr');
            let visibleCount = 0;

            rows.forEach(row => {{
                const strategy = row.dataset.strategy;
                const ret = parseFloat(row.dataset.return);
                const sharpe = parseFloat(row.dataset.sharpe);
                const dd = parseFloat(row.dataset.dd);

                const show = (
                    (!strategyFilter || strategy === strategyFilter) &&
                    sharpe >= sharpeFilter &&
                    ret >= returnFilter &&
                    dd >= ddFilter
                );

                row.classList.toggle('hidden', !show);
                if (show) visibleCount++;
            }});

            document.getElementById('visible-count').textContent = visibleCount;
            document.getElementById('filtered-count').textContent = visibleCount;
        }}

        function resetFilters() {{
            document.getElementById('filter-strategy').value = '';
            document.getElementById('filter-sharpe').value = '';
            document.getElementById('filter-return').value = '';
            document.getElementById('filter-dd').value = '';
            applyFilters();
        }}

        // Attach filter listeners
        ['filter-strategy', 'filter-sharpe', 'filter-return', 'filter-dd'].forEach(id => {{
            document.getElementById(id).addEventListener('input', applyFilters);
        }});
    </script>
</body>
</html>
'''
    return html


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("Backtest Results Dashboard Generator")
    print("=" * 60)

    # Load all strategy results from sidecar files
    print("\nLoading strategy results...")
    results = load_all_strategy_results()

    if not results:
        print("  No strategy results found!")
        print("  Run 'python scripts/backtest_vectorbt.py --all' to generate results.")
        return

    print(f"  Loaded {len(results)} strategies:")
    for r in results:
        print(f"    - {r.get('strategy_id')}: {r.get('strategy_name')}")

    # Generate index page
    print("\nGenerating index page...")
    index_html = generate_index_page(results)
    INDEX_PATH.write_text(index_html)
    print(f"  Saved to {INDEX_PATH}")

    # Generate detail pages for each strategy
    print("\nGenerating detail pages...")
    detail_paths = []
    for idx, result in enumerate(results):
        strategy_id = result.get('strategy_id', 'unknown')
        filename = f"backtest_{strategy_id.lower().replace('-', '')}.html"
        detail_path = DASHBOARDS_DIR / filename

        detail_html = generate_detail_page(result, idx)
        detail_path.write_text(detail_html)
        detail_paths.append(detail_path)
        print(f"  Saved {filename}")

    # Generate All Runs browser page (from database)
    print("\nGenerating All Runs browser page...")
    try:
        runs_html = generate_runs_browser_page()
        runs_path = DASHBOARDS_DIR / "dashboard_runs.html"
        runs_path.write_text(runs_html)
        print(f"  Saved dashboard_runs.html")
    except Exception as e:
        print(f"  ⚠ Skipped runs page: {e}")
        runs_path = None

    # Summary
    print(f"\n{'=' * 60}")
    page_count = len(results) + 1 + (1 if runs_path else 0)
    print(f"Generated {page_count} dashboard pages:")
    print(f"  Index:  {INDEX_PATH.name}")
    if runs_path:
        print(f"  Runs:   dashboard_runs.html")
    for p in detail_paths:
        print(f"  Detail: {p.name}")

    # Open in browser
    if '--no-open' not in sys.argv:
        webbrowser.open(f'file://{INDEX_PATH.absolute()}')
        print("\n  Opened index page in browser")

    print("\nDone!")


if __name__ == "__main__":
    main()
