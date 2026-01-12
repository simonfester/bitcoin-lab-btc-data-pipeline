import pandas as pd
import numpy as np
from pathlib import Path
import vectorbt as vbt
import warnings
warnings.filterwarnings('ignore')

# Load data
DATA_DIR = Path("data/raw")

price = pd.read_parquet(DATA_DIR / "price.parquet").rename(columns={"value": "price"}).set_index("time")
sopr = pd.read_parquet(DATA_DIR / "sopr.parquet").rename(columns={"value": "sopr"}).set_index("time")
sopr_sth = pd.read_parquet(DATA_DIR / "sopr_sth.parquet").rename(columns={"value": "sopr_sth"}).set_index("time")
realized_loss = pd.read_parquet(DATA_DIR / "realized_loss.parquet").rename(columns={"value": "realized_loss"}).set_index("time")

df = price.join(sopr, how='inner').join(sopr_sth, how='inner').join(realized_loss, how='inner')
df = df.sort_index()

# Create RL z-score
df['rl_zscore'] = (df['realized_loss'] - df['realized_loss'].rolling(30).mean()) / df['realized_loss'].rolling(30).std()

# FILTER TO LAST 2 YEARS
df = df[df.index >= '2024-01-01'].dropna()

print(f"Data: {len(df)} rows")
print(f"Date range: {df.index.min().date()} to {df.index.max().date()}")

# Entry signals
entry_condition = (
    (df['sopr'] < 1) & 
    (df['sopr_sth'] < 1) & 
    (df['rl_zscore'] > 0.5)
)
entries = entry_condition & ~entry_condition.shift(1).fillna(False)

print(f"\nEntry signals: {entries.sum()}")
print(f"\nEntry dates:")
for date in entries[entries].index:
    print(f"  {date.date()}: ${df.loc[date, 'price']:,.0f}")

# VectorBT Portfolio
close = df['price']

pf = vbt.Portfolio.from_signals(
    close=close,
    entries=entries,
    exits=None,
    sl_stop=0.30,
    sl_trail=True,
    stop_exit_price='close',
    fees=0.001,
    init_cash=100000,
    freq='D'
)

print("\n" + "="*60)
print("LAST 2 YEARS PERFORMANCE (2024-2026)")
print("="*60)

print(f"\nTotal Return: {pf.total_return() * 100:+,.1f}%")
print(f"Max Drawdown: {pf.max_drawdown() * 100:.1f}%")
print(f"Total Trades: {pf.trades.count()}")
if pf.trades.count() > 0:
    print(f"Win Rate: {pf.trades.win_rate() * 100:.0f}%")
print(f"Final Value: ${pf.final_value():,.0f}")

# Buy & hold comparison
bh_return = (close.iloc[-1] / close.iloc[0]) - 1
strategy_return = pf.total_return()

print(f"\n" + "="*60)
print("VS BUY & HOLD")
print("="*60)
print(f"Strategy: {strategy_return * 100:+,.1f}%")
print(f"Buy & Hold: {bh_return * 100:+,.1f}%")
print(f"Difference: {(strategy_return - bh_return) * 100:+,.1f}%")
print(f"\nStrategy: $100,000 → ${pf.final_value():,.0f}")
print(f"Buy & Hold: $100,000 → ${100000 * (1 + bh_return):,.0f}")

if strategy_return > bh_return:
    print(f"\n✅ Strategy BEAT Buy & Hold!")
else:
    print(f"\n❌ Strategy UNDERPERFORMED Buy & Hold")

# Trade details
if pf.trades.count() > 0:
    print(f"\n" + "="*60)
    print("TRADES")
    print("="*60)
    print(pf.trades.records_readable.to_string())
