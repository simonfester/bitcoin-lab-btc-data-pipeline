# CLAUDE.md - Bitcoin Trading Framework

## Project Overview

This project implements James Check's on-chain analysis framework for Bitcoin trading signals. It provides a systematic approach to analyzing Bitcoin market conditions using on-chain data, organized around 6 analytical pillars that feed into actionable trading signals.

**Primary Goal**: Build and backtest systematic trading strategies based on the Checkonchain Framework.

## The 6 Pillars of On-Chain Analysis

| # | Pillar | Key Metrics | What It Tells Us |
|---|--------|-------------|------------------|
| 1 | **Valuation** | MVRV, MVRV-Z, AVIV, Price Levels | How expensive is BTC vs historical norms? |
| 2 | **Profitability** | NUPL, Supply in Profit/Loss | How much paper gains/losses exist? High = greed, low = fear |
| 3 | **Spending Behavior** | SOPR, STH/LTH-SOPR, Realized P/L Ratio | What are holders actually doing? Reveals capitulation & profit-taking |
| 4 | **Supply Distribution** | LTH/STH Supply, Age Bands | Who holds coins? High LTH% = strong hands, rising STH% = speculation |
| 5 | **Activity** | Liveliness, Vaultedness, CDD | Coins moving or dormant? High liveliness = spending, high vaultedness = HODLing |
| 6 | **Miner Health** | Puell Multiple, Difficulty | Miners profitable or stressed? Capitulation marks lows, high Puell = overheated |

## Three-Stage Pipeline Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   sync.py   │ ──▶ │ calculate.py │ ──▶ │ dashboard.py │
│ (Data Sync) │     │  (Signals)   │     │  (Display)   │
└─────────────┘     └──────────────┘     └──────────────┘
       │                   │                    │
       ▼                   ▼                    ▼
  data/brk/          data/signals/        dashboard.html
  data/glassnode/    *.parquet
  (raw parquets)     *.json
```

### Stage 1: Data Sync (`sync_all.py`, `run.py`)
- Downloads raw on-chain data from APIs
- Outputs to `data/brk/daily/`, `data/glassnode/daily/`
- Run: `python run.py brk-sync`

### Stage 2: Signal Calculation (`scripts/calculate.py`)
- Reads raw parquets, computes all metrics and signals
- Outputs to `data/signals/dashboard_context.json` + parquets
- Run: `python scripts/calculate.py`

### Stage 3: Dashboard Display (`scripts/dashboard_new.py`)
- Pure HTML rendering, no calculations
- Optionally fetches live price from Coinbase
- Run: `python scripts/dashboard_new.py`

## Data Sources

**DO NOT USE GLASSNODE API** - Use Bitcoin Lab API and BRK API as primary sources.

| Source | Cost | Use Case |
|--------|------|----------|
| **BRK** | FREE | Primary source for all daily on-chain metrics |
| **Bitcoin Lab** | Paid (quota) | Backup, hourly data |
| **Glassnode** | Paid | Derivatives data only (funding rates, liquidations) |

### API Credentials
- **Bitcoin Lab Token**: `ae92658e-373f-4fce-a5b3-1cfc1ffb4da6`
- **Bitcoin Lab URL**: `https://api.researchbitcoin.net`
- **BRK URL**: `https://next.bitview.space` (no token needed)

## Key Files

### Scripts
| File | Purpose |
|------|---------|
| `scripts/calculate.py` | Signal computation engine - all metric calculations |
| `scripts/dashboard_new.py` | Pure HTML rendering layer (6 pillars layout) |
| `scripts/dashboard.py` | Legacy dashboard (monolithic) |
| `scripts/sync_all.py` | Data synchronization |
| `run.py` | CLI entry point for all commands |

### Data
| Path | Contents |
|------|----------|
| `data/brk/daily/*.parquet` | BRK on-chain metrics (FREE) |
| `data/glassnode/daily/*.parquet` | Derivatives metrics |
| `data/signals/dashboard_context.json` | Pre-computed signals for dashboard |
| `data/signals/*.parquet` | Signal time series |

### Research
| Path | Contents |
|------|----------|
| `research/check/Masterclass.txt` | James Check's framework documentation |
| `research/` | Analysis notebooks and strategy development |

## Signal Definitions

### Buy The Dip (5 conditions)
1. STH-MVRV < 1.0 (short-term holders underwater)
2. STH-SOPR < 1.0 (short-term holders selling at loss)
3. Realized P/L Ratio < 1.0 (losses exceed profits)
4. Funding rates ≤ 0 (derivatives not overheated)
5. Long liquidations > Short liquidations

### Entry Signals
- SOPR < 1 (market selling at loss)
- STH-SOPR < 1 (short-term holder capitulation)
- Realized Loss Z-score > 0.5 (elevated loss-taking)

### Exit Signals
- LTH-SOPR > 1.5 (long-term holders taking profits)
- MVRV-Z > 2.5 (market historically expensive)

## Common Commands

```bash
# Data sync (run daily)
python run.py brk-sync              # Sync BRK data (FREE)
python run.py bl-sync-daily         # Sync Bitcoin Lab (uses quota)

# Generate dashboard
python scripts/calculate.py         # Compute signals
python scripts/dashboard_new.py     # Render HTML

# Quick status
python run.py brk-status            # Check BRK sync status
python run.py quota                 # Check Bitcoin Lab quota
```

## Parquet Data Format

All metrics stored as parquet with consistent schema:
```python
# Columns: time (datetime64), value (float64)
import pandas as pd
df = pd.read_parquet('data/brk/daily/mvrv.parquet')
```

## Key Concepts

### Timestamping
Assigns age to coins based on when they last moved. Longer held = stronger hands.

### Pricestamping  
Assigns cost basis to coins when they transact. Enables profit/loss calculations.

### Cohorts
Groups supply by behavior: LTH (>155 days), STH (<155 days), exchanges, miners.

### MVRV-Z Zones
- < 0: Deep Value (accumulation zone)
- 0-1: Fair Value
- 1-2.5: Expensive
- > 2.5: Euphoria (distribution zone)

### NUPL Emotions
- < 0: Capitulation
- 0-0.25: Hope/Fear
- 0.25-0.5: Optimism
- 0.5-0.75: Belief
- > 0.75: Euphoria

## Research Principles

1. **Use backesting as confirmation, not discovery** - Test signals with regressions and statistical validation first
2. **Fixed thresholds for economic meaning** - STH-MVRV < 1 means underwater
3. **Z-scores for relative comparisons** - Adapt to market regimes
4. **Check's Swiss Army Knife** - STH-MVRV and STH-SOPR are primary daily indicators

## Backtesting Principles ⚠️ CRITICAL

### ALWAYS USE VECTORBT FOR BACKTESTING

**Lesson learned (2026-01-21):** Custom backtest engine produced inflated results (+473% vs actual +271%) due to look-ahead bias and implementation bugs.

**MANDATORY RULES:**

1. **Use VectorBT for all backtests** - Industry-standard, battle-tested library
   - Handles position sizing correctly
   - Prevents look-ahead bias
   - Calculates fees/slippage properly
   - Provides reliable statistics

2. **Always verify "too good to be true" results** - If results seem unrealistic:
   - Run independent verification with VectorBT
   - Check for look-ahead bias
   - Verify signal generation uses ONLY past data
   - Compare against buy-and-hold benchmark

3. **Walk-forward validation required** - Always split:
   - Train period: Use for development/optimization
   - Test period: Out-of-sample validation only
   - Never optimize on test data

4. **Realistic expectations** - Framework results (verified):
   - LTH Distribution exit: +351% (2023-2026)
   - Buy & Hold benchmark: +438% (same period)
   - Framework provides RISK MANAGEMENT, not alpha
   - Sharpe 1.67 vs ~1.0 for B&H (better risk-adjusted)
   - Max DD -20% vs -40%+ for B&H (better risk control)

### Backtesting Script Locations

| Script | Purpose | Status |
|--------|---------|--------|
| `scripts/backtest_vectorbt.py` | **USE THIS** - VectorBT verified | ✅ Reliable |
| `scripts/backtest_framework.py` | Custom engine - has bugs | ⚠️ Do not use for 8-metric exit |

### Example VectorBT Backtest

```python
import vectorbt as vbt

# Generate signals (ensure no look-ahead bias!)
entries = generate_buy_the_dip_entries(df)  # Boolean series
exits = generate_lth_distribution_exits(df)  # Boolean series

# Run backtest
pf = vbt.Portfolio.from_signals(
    close=df['price'],
    entries=entries,
    exits=exits,
    fees=0.001,      # 0.1%
    slippage=0.001,  # 0.1%
    init_cash=10000,
    freq='1D'
)

# Get results
print(f"Total Return: {pf.total_return() * 100:.1f}%")
print(f"Sharpe Ratio: {pf.sharpe_ratio():.2f}")
print(f"Max Drawdown: {pf.max_drawdown() * 100:.1f}%")
print(f"Win Rate: {pf.trades.win_rate() * 100:.1f}%")
```

### Common Backtest Pitfalls

❌ **AVOID:**
- Custom backtest engines (prone to bugs)
- Using future data in signal generation
- Optimizing on test data
- Cherry-picking favorable periods
- Ignoring transaction costs

✅ **DO:**
- Use VectorBT or other established libraries
- Ensure signals only use past data (rolling calculations)
- Walk-forward validation (train/test split)
- Compare against buy-and-hold benchmark
- Include realistic fees and slippage

### Framework Performance Summary (VectorBT Verified)

**Out-of-Sample (2023-2026):**
- Entry: Buy The Dip (4/5 conditions)
- Exit: LTH Distribution (MVRV>2 + LTH-SOPR>1.5)
- Return: +350.9%
- Buy & Hold: +437.5%
- **Verdict**: Framework provides risk management (Sharpe 1.67, DD -20%), not absolute returns

**Use Cases:**
1. ✅ Risk management (lower drawdowns)
2. ✅ Educational (learn on-chain signals)
3. ✅ Risk overlay (80% B&H + 20% signals)
4. ❌ NOT for maximum absolute returns (B&H wins)

## File Locations Summary

```
bitcoin-lab-btc-data-pipeline/
├── CLAUDE.md                    # This file
├── run.py                       # CLI entry point
├── scripts/
│   ├── calculate.py             # Signal computation
│   └── dashboard_new.py         # HTML rendering (6 pillars)
├── data/
│   ├── brk/daily/               # BRK metrics (primary)
│   ├── glassnode/daily/         # Derivatives
│   ├── signals/                 # Computed signals
│   └── claude.md                # Data source docs
├── research/
│   └── check/Masterclass.txt    # James Check framework
└── config/                      # Sync state files
```
