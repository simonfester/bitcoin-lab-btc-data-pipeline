# %% [markdown]
# # Notebook 50: Hourly Timeframe Strategy Testing
# 
# Test STRAT-002 and STRAT-003 on hourly data to see if higher resolution improves entry/exit timing.
# 
# **Strategies:**
# - STRAT-002: SOPR < 1 + STH-SOPR < 1 + RL z-score > 0.5, 30% trail exit
# - STRAT-003: Same entry, LTH-SOPR > 1.5 exit

# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Paths
DATA_DIR = Path("../data")
DAILY_DIR = DATA_DIR / "daily"
HOURLY_DIR = DATA_DIR / "hourly"

# %% [markdown]
# ## 1. Load Hourly Data

# %%
# Load hourly data
def load_hourly():
    price = pd.read_parquet(HOURLY_DIR / "price.parquet")
    sopr = pd.read_parquet(HOURLY_DIR / "sopr.parquet")
    sopr_sth = pd.read_parquet(HOURLY_DIR / "sopr_sth.parquet")
    sopr_lth = pd.read_parquet(HOURLY_DIR / "sopr_lth.parquet")
    realized_loss = pd.read_parquet(HOURLY_DIR / "realized_loss.parquet")
    
    # Merge all
    df = price.rename(columns={"value": "price"}).set_index("time")
    df["sopr"] = sopr.set_index("time")["value"]
    df["sopr_sth"] = sopr_sth.set_index("time")["value"]
    df["sopr_lth"] = sopr_lth.set_index("time")["value"]
    df["realized_loss"] = realized_loss.set_index("time")["value"]
    
    return df

df_hourly = load_hourly()
print(f"Hourly data: {len(df_hourly):,} rows")
print(f"Date range: {df_hourly.index.min()} to {df_hourly.index.max()}")
print(f"\nColumns: {df_hourly.columns.tolist()}")
print(f"\nMissing values:\n{df_hourly.isna().sum()}")

# %%
# Check data quality
df_hourly.info()

# %%
# Forward fill small gaps (up to 4 hours), drop larger gaps
df = df_hourly.ffill(limit=4).dropna()
print(f"After cleaning: {len(df):,} rows")
print(f"Date range: {df.index.min()} to {df.index.max()}")

# %% [markdown]
# ## 2. Calculate Signals

# %%
# Calculate realized loss z-score (rolling 365-day window in hours)
# 365 days * 24 hours = 8760 hours
WINDOW_HOURS = 365 * 24

df["rl_mean"] = df["realized_loss"].rolling(window=WINDOW_HOURS, min_periods=WINDOW_HOURS//2).mean()
df["rl_std"] = df["realized_loss"].rolling(window=WINDOW_HOURS, min_periods=WINDOW_HOURS//2).std()
df["rl_zscore"] = (df["realized_loss"] - df["rl_mean"]) / df["rl_std"]

print(f"RL z-score stats:")
print(df["rl_zscore"].describe())

# %%
# Filter to backtest period (need warm-up for z-score)
df = df[df.index >= "2019-01-01"].copy()
print(f"Backtest period: {len(df):,} rows ({df.index.min()} to {df.index.max()})")

# %% [markdown]
# ## 3. Backtester for Hourly Data

# %%
import vectorbt as vbt

def run_backtest_hourly(df, entry_signal, exit_signal=None, trail=None):
    """Run backtest on hourly data."""
    
    if exit_signal is None and trail is None:
        raise ValueError("Need either exit_signal or trail")
    
    if trail:
        # Trail stop exit
        pf = vbt.Portfolio.from_signals(
            close=df["price"],
            entries=entry_signal,
            exits=None,
            sl_stop=trail,
            sl_trail=True,
            freq="1h",
            init_cash=10000,
            fees=0.001
        )
    else:
        # Signal-based exit
        pf = vbt.Portfolio.from_signals(
            close=df["price"],
            entries=entry_signal,
            exits=exit_signal,
            freq="1h",
            init_cash=10000,
            fees=0.001
        )
    
    return pf

def get_metrics(pf, years):
    """Extract key metrics from portfolio."""
    trades = pf.trades.records_readable
    if len(trades) == 0:
        return None
    
    total_return = pf.total_return() * 100
    
    return {
        "return": total_return,
        "cagr": ((1 + total_return/100) ** (1/years) - 1) * 100,
        "sharpe": pf.sharpe_ratio(),
        "max_dd": pf.max_drawdown() * 100,
        "trades": len(trades),
        "win_rate": (trades["PnL"] > 0).mean() * 100,
        "profit_factor": abs(trades[trades["PnL"] > 0]["PnL"].sum() / trades[trades["PnL"] < 0]["PnL"].sum()) if (trades["PnL"] < 0).any() else np.inf
    }

# Calculate years for CAGR
years = (df.index.max() - df.index.min()).days / 365.25
print(f"Backtest period: {years:.2f} years")

# Buy and hold benchmark
bh_return = (df["price"].iloc[-1] / df["price"].iloc[0] - 1) * 100
print(f"Buy & Hold: {bh_return:+,.0f}%")

# %% [markdown]
# ## 4. STRAT-002 on Hourly

# %%
# STRAT-002 Entry: SOPR < 1 AND STH-SOPR < 1 AND RL z-score > 0.5
strat002_cond = (df["sopr"] < 1) & (df["sopr_sth"] < 1) & (df["rl_zscore"] > 0.5)
strat002_entry = strat002_cond & ~strat002_cond.shift(1).fillna(False)

print(f"STRAT-002 entry signals: {strat002_entry.sum()}")
print(f"Entry rate: {strat002_entry.sum() / len(df) * 100:.4f}%")

# %%
# Test with 30% trail stop
pf_strat002 = run_backtest_hourly(df, strat002_entry, trail=0.30)
m = get_metrics(pf_strat002, years)

print("\n" + "="*80)
print("STRAT-002 (Hourly) - 30% Trail")
print("="*80)
if m:
    print(f"Return:       {m['return']:+,.0f}%")
    print(f"CAGR:         {m['cagr']:+.1f}%")
    print(f"Sharpe:       {m['sharpe']:.2f}")
    print(f"Max DD:       {m['max_dd']:.1f}%")
    print(f"Trades:       {m['trades']}")
    print(f"Win Rate:     {m['win_rate']:.0f}%")
    print(f"Profit Factor: {m['profit_factor']:.2f}")

# %% [markdown]
# ## 5. STRAT-003 on Hourly (LTH-SOPR Exit)

# %%
# STRAT-003: Same entry, LTH-SOPR > 1.5 exit
strat003_entry = strat002_entry.copy()
strat003_exit_cond = df["sopr_lth"] > 1.5
strat003_exit = strat003_exit_cond & ~strat003_exit_cond.shift(1).fillna(False)

print(f"STRAT-003 exit signals: {strat003_exit.sum()}")

# %%
pf_strat003 = run_backtest_hourly(df, strat003_entry, exit_signal=strat003_exit)
m3 = get_metrics(pf_strat003, years)

print("\n" + "="*80)
print("STRAT-003 (Hourly) - LTH-SOPR > 1.5 Exit")
print("="*80)
if m3:
    print(f"Return:       {m3['return']:+,.0f}%")
    print(f"CAGR:         {m3['cagr']:+.1f}%")
    print(f"Sharpe:       {m3['sharpe']:.2f}")
    print(f"Max DD:       {m3['max_dd']:.1f}%")
    print(f"Trades:       {m3['trades']}")
    print(f"Win Rate:     {m3['win_rate']:.0f}%")
    print(f"Profit Factor: {m3['profit_factor']:.2f}")

# %% [markdown]
# ## 6. Compare Hourly vs Daily

# %%
# Load daily data for comparison
def load_daily():
    price = pd.read_parquet(DAILY_DIR / "price.parquet")
    sopr = pd.read_parquet(DAILY_DIR / "sopr.parquet")
    sopr_sth = pd.read_parquet(DAILY_DIR / "sopr_sth.parquet")
    sopr_lth = pd.read_parquet(DAILY_DIR / "sopr_lth.parquet")
    realized_loss = pd.read_parquet(DAILY_DIR / "realized_loss.parquet")
    
    df = price.rename(columns={"value": "price"}).set_index("time")
    df["sopr"] = sopr.set_index("time")["value"]
    df["sopr_sth"] = sopr_sth.set_index("time")["value"]
    df["sopr_lth"] = sopr_lth.set_index("time")["value"]
    df["realized_loss"] = realized_loss.set_index("time")["value"]
    
    # Z-score
    df["rl_mean"] = df["realized_loss"].rolling(window=365, min_periods=180).mean()
    df["rl_std"] = df["realized_loss"].rolling(window=365, min_periods=180).std()
    df["rl_zscore"] = (df["realized_loss"] - df["rl_mean"]) / df["rl_std"]
    
    return df[df.index >= "2019-01-01"].dropna()

df_daily = load_daily()
print(f"Daily data: {len(df_daily):,} rows")

# %%
# Run daily backtests
daily_strat002_cond = (df_daily["sopr"] < 1) & (df_daily["sopr_sth"] < 1) & (df_daily["rl_zscore"] > 0.5)
daily_strat002_entry = daily_strat002_cond & ~daily_strat002_cond.shift(1).fillna(False)

pf_daily_002 = vbt.Portfolio.from_signals(
    close=df_daily["price"],
    entries=daily_strat002_entry,
    exits=None,
    sl_stop=0.30,
    sl_trail=True,
    freq="1d",
    init_cash=10000,
    fees=0.001
)

daily_years = (df_daily.index.max() - df_daily.index.min()).days / 365.25
m_daily = get_metrics(pf_daily_002, daily_years)

# %%
# Summary comparison
print("\n" + "="*100)
print("COMPARISON: HOURLY vs DAILY")
print("="*100)
print(f"\n{'Metric':<20} {'STRAT-002 Daily':>18} {'STRAT-002 Hourly':>18} {'STRAT-003 Hourly':>18}")
print("-"*100)

if m_daily and m and m3:
    print(f"{'Return':<20} {m_daily['return']:>+17,.0f}% {m['return']:>+17,.0f}% {m3['return']:>+17,.0f}%")
    print(f"{'CAGR':<20} {m_daily['cagr']:>+17.1f}% {m['cagr']:>+17.1f}% {m3['cagr']:>+17.1f}%")
    print(f"{'Sharpe':<20} {m_daily['sharpe']:>18.2f} {m['sharpe']:>18.2f} {m3['sharpe']:>18.2f}")
    print(f"{'Max Drawdown':<20} {m_daily['max_dd']:>17.1f}% {m['max_dd']:>17.1f}% {m3['max_dd']:>17.1f}%")
    print(f"{'Trades':<20} {m_daily['trades']:>18} {m['trades']:>18} {m3['trades']:>18}")
    print(f"{'Win Rate':<20} {m_daily['win_rate']:>17.0f}% {m['win_rate']:>17.0f}% {m3['win_rate']:>17.0f}%")
    print(f"{'Profit Factor':<20} {m_daily['profit_factor']:>18.2f} {m['profit_factor']:>18.2f} {m3['profit_factor']:>18.2f}")

print("-"*100)
print(f"{'Buy & Hold':<20} {bh_return:>+17,.0f}%")

# %% [markdown]
# ## 7. Trade Analysis

# %%
# Show hourly trades
print("\nSTRAT-002 Hourly Trades:")
print(pf_strat002.trades.records_readable[["Entry Timestamp", "Exit Timestamp", "PnL", "Return"]].to_string())

# %%
# Plot equity curves
fig, ax = plt.subplots(figsize=(14, 6))

pf_strat002.value().plot(ax=ax, label="STRAT-002 Hourly (30% trail)")
if m3:
    pf_strat003.value().plot(ax=ax, label="STRAT-003 Hourly (LTH exit)")

ax.set_title("Hourly Strategy Equity Curves")
ax.set_ylabel("Portfolio Value ($)")
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# %% [markdown]
# ## 8. Entry Timing Analysis
# 
# Does hourly data provide better entry timing than daily?

# %%
# Compare entry prices: hourly vs daily
hourly_entries = df.index[strat002_entry]
daily_entries = df_daily.index[daily_strat002_entry]

print(f"Hourly entries: {len(hourly_entries)}")
print(f"Daily entries: {len(daily_entries)}")

# Find matching days
print("\nEntry Price Comparison (same day entries):")
for daily_entry in daily_entries[:10]:
    # Find hourly entries on same day
    day_start = daily_entry.normalize()
    day_end = day_start + pd.Timedelta(days=1)
    hourly_same_day = hourly_entries[(hourly_entries >= day_start) & (hourly_entries < day_end)]
    
    if len(hourly_same_day) > 0:
        daily_price = df_daily.loc[daily_entry, "price"]
        hourly_price = df.loc[hourly_same_day[0], "price"]
        diff_pct = (hourly_price - daily_price) / daily_price * 100
        print(f"  {daily_entry.date()}: Daily ${daily_price:,.0f} | Hourly ${hourly_price:,.0f} ({diff_pct:+.2f}%)")
