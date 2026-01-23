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
┌─────────────────────────────────────────────┐
│         STAGE 1: DATA SOURCES               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   BRK    │  │ BitcoinLab│  │Glassnode │  │
│  │  (FREE)  │  │  (QUOTA)  │  │  (PAID)  │  │
│  │  Daily   │  │ h1/h4/h8  │  │ Derives  │  │
│  │41 metrics│  │ 5 metrics │  │3 metrics │  │
│  └────┬─────┘  └────┬──────┘  └────┬─────┘  │
└───────┼─────────────┼──────────────┼─────────┘
        │             │              │
        ▼             ▼              ▼
   data/brk/      data/bl/      data/glassnode/
    daily/      hourly/h4/h8/      daily/
  *.parquet      *.parquet       *.parquet
        │             │              │
        └─────────────┼──────────────┘
                      ▼
        ┌─────────────────────────┐
        │  STAGE 2: CALCULATIONS  │
        │   scripts/calculate.py  │
        │  - Compute signals      │
        │  - Generate features    │
        │  - Apply strategies     │
        └────────────┬────────────┘
                     ▼
              data/signals/
           dashboard_context.json
                *.parquet
                     │
                     ▼
        ┌─────────────────────────┐
        │   STAGE 3: DISPLAY      │
        │ scripts/dashboard_new.py│
        │  - HTML rendering       │
        │  - Live price (optional)│
        └────────────┬────────────┘
                     ▼
              dashboard.html
```

### Stage 1: Data Sync (`run.py`)
**Multi-source data acquisition:**
- **BRK** (FREE): `python run.py brk-sync` → `data/brk/daily/` (41 metrics)
- **Bitcoin Lab** (QUOTA): `python run.py bl-sync-hourly` → `data/bl/hourly/` (5 metrics)
- **Glassnode** (PAID): Manual sync → `data/glassnode/daily/` (derivatives)

### Stage 2: Signal Calculation (`scripts/calculate.py`)
- Reads raw parquets from all sources
- Computes signals using James Check framework (6 pillars)
- Outputs to `data/signals/dashboard_context.json` + parquets
- Run: `python scripts/calculate.py`

### Stage 3: Dashboard Display (`scripts/dashboard_new.py`)
- Pure HTML rendering, no calculations
- Displays 6 pillars with current market status
- Optionally fetches live price from Coinbase
- Run: `python scripts/dashboard_new.py`

## Data Sources & Availability

### Overview

**DO NOT USE GLASSNODE API** - Use Bitcoin Lab API and BRK API as primary sources.

| Source | Cost | Resolutions | Use Case |
|--------|------|-------------|----------|
| **BRK** | FREE | Daily only | **PRIMARY** - All daily on-chain metrics (41 metrics) |
| **Bitcoin Lab** | Paid (1M quota/week) | Hourly, 4h, 8h, 12h, Daily | **SECONDARY** - High-frequency data & backups |
| **Glassnode** | Paid | Daily | Derivatives only (funding rates, liquidations) |

### Current Data Availability (Last Synced: 2026-01-23)

#### BRK (FREE - PRIMARY SOURCE)
**Status**: ✅ Fully synced
**Resolution**: Daily only
**Date Range**: 2009-01-03 → 2026-01-23 (synced today)
**Metrics**: 41 on-chain metrics
**Total Rows**: 248,739 (~6,225 days × 41 metrics)

**Available Metrics:**
- **Price & Technical**: price, price_200d_sma, market_cap
- **SOPR Family**: sopr, sopr_sth, sopr_lth, sopr_adjusted
- **MVRV Family**: mvrv, mvrv_sth, mvrv_lth
- **NUPL Family**: nupl, nupl_sth, nupl_lth, unrealized_profit, unrealized_loss
- **Realized Metrics**: realized_cap, realized_price, realized_price_sth, realized_price_lth, realized_profit, realized_loss
- **Supply**: supply_total, supply_lth, supply_sth, supply_in_profit, supply_in_loss
- **Cointime Economics**: liveliness, aviv, active_price, vaulted_price, cointime_price, investor_cap, thermo_cap
- **Sell-side Risk**: sell_side_risk, sell_side_risk_sth, sell_side_risk_lth
- **Mining**: puell_multiple, difficulty, coindays_destroyed
- **Activity**: net_realized_pnl, true_market_mean_price

**Sync Commands:**
```bash
python run.py brk-sync          # Incremental daily sync (FREE)
python run.py brk-backfill      # Full historical download
python run.py brk-status        # Check sync status
```

#### Bitcoin Lab (PAID - HIGH FREQUENCY)
**Status**: ✅ Multi-resolution synced
**Quota**: 776,833 / 1,000,000 DPs remaining (77.7%)
**Quota Reset**: Every 7 days (next: 2026-01-30)
**Date Range**: 2015-01-01 → 2026-01-23

**Resolution Coverage:**

| Resolution | Metrics | Rows/Metric | Total Rows | Date Range | Last Sync |
|------------|---------|-------------|------------|------------|-----------|
| **h1** (hourly) | 5 | 96,735 | 483,675 | 2015-01-01 → 2026-01-23 11:00 | ✅ 2026-01-23 |
| **h4** (4-hourly) | 5 | 24,243 | 121,215 | 2015-01-01 → 2026-01-23 08:00 | ✅ 2026-01-23 |
| **h8** (8-hourly) | 5 | 12,121 | 60,605 | 2015-01-01 → 2026-01-23 00:00 | ✅ 2026-01-23 |
| **h12** (12-hourly) | 5 | 8,081 | 40,405 | 2015-01-01 → 2026-01-23 00:00 | ✅ 2026-01-23 |

**Available Metrics at All Resolutions:**
1. **price** - BTC/USD price
2. **sopr** - Spent Output Profit Ratio (all holders)
3. **sopr_lth** - SOPR for long-term holders (>155 days)
4. **sopr_sth** - SOPR for short-term holders (<155 days)
5. **realized_loss** - Total realized losses in USD

**Sync Commands:**
```bash
# Check quota before syncing
python run.py quota                # Show remaining quota

# Sync specific resolutions
python run.py bl-sync-hourly       # Hourly (h1)
python run.py bl-sync-h4           # 4-hourly
python run.py bl-sync-h8           # 8-hourly
python run.py bl-sync-h12          # 12-hourly
python run.py bl-sync              # All resolutions (uses more quota)

# Backfill historical data
python run.py bl-backfill-hourly   # Backfill from 2015-01-01
python run.py bl-backfill-h4       # 4-hourly backfill
python run.py bl-backfill-all      # WARNING: Uses significant quota

# Check status
python run.py bl-status            # All resolutions status
python run.py bl-status-hourly     # Hourly status only
python run.py quota-estimate 30 h1 # Estimate cost for 30 days of hourly
```

**Quota Costs (per metric):**
- **h1** (hourly): ~24 datapoints/day
- **h4** (4-hourly): ~6 datapoints/day
- **h8** (8-hourly): ~3 datapoints/day
- **h12** (12-hourly): ~2 datapoints/day
- **d1** (daily): ~1 datapoint/day

**Example**: Syncing 30 days of hourly data for 5 metrics = 30 × 24 × 5 = 3,600 datapoints

#### Glassnode (PAID - DERIVATIVES ONLY)
**Status**: ⚠️ Manual sync required
**Resolution**: Daily only
**Use Case**: Derivatives data (funding rates, liquidations)

**Available Metrics:**
- `funding_rate` - Perpetual swap funding rates
- `liq_long` - Long liquidations volume
- `liq_short` - Short liquidations volume

**Note**: Needed for STRAT-004 and STRAT-005 (Buy The Dip strategies) which require derivatives data for signal confirmation.

### API Credentials

**Bitcoin Lab:**
- Token: `ae92658e-373f-4fce-a5b3-1cfc1ffb4da6`
- URL: `https://api.researchbitcoin.net`
- Tier: 2 (1M datapoints/week)
- Token Expires: 2026-04-06

**BRK:**
- URL: `https://next.bitview.space`
- Authentication: None (public API)
- Rate Limits: None (FREE)

**Glassnode:**
- URL: `https://api.glassnode.com`
- Token: (stored in environment variable)
- Use only for derivatives data

### Data Directory Structure

```
data/
├── brk/
│   └── daily/              # BRK daily metrics (41 metrics, FREE)
│       ├── price.parquet
│       ├── sopr.parquet
│       ├── mvrv.parquet
│       └── ... (38 more)
├── bl/                     # Bitcoin Lab (paid quota)
│   ├── hourly/             # h1 resolution (5 metrics)
│   │   ├── price.parquet
│   │   ├── sopr.parquet
│   │   ├── sopr_lth.parquet
│   │   ├── sopr_sth.parquet
│   │   └── realized_loss.parquet
│   ├── h4/                 # 4-hourly (5 metrics)
│   ├── h8/                 # 8-hourly (5 metrics)
│   └── h12/                # 12-hourly (5 metrics)
└── glassnode/
    └── daily/              # Derivatives data
        ├── funding_rate.parquet
        ├── liq_long.parquet
        └── liq_short.parquet
```

### Data Source Recommendations

**For Daily Analysis (Backtesting, Strategies):**
- ✅ **Use BRK** - Free, comprehensive (41 metrics), reliable
- ❌ Don't use Bitcoin Lab daily - wastes quota

**For Intraday/High-Frequency Analysis:**
- ✅ **Use Bitcoin Lab** - Only source for hourly/4h/8h/12h data
- 📊 Monitor quota usage: `python run.py quota`
- 💡 Start with h4 or h8 (lower quota cost) before going to h1

**For Derivatives Analysis:**
- ✅ **Use Glassnode** - Only source for funding rates and liquidations
- 🎯 Required for STRAT-004 and STRAT-005 (Buy The Dip)

**Data Loading Best Practices:**
```python
from src.data_loader import DataLoader

# Load daily data from BRK (FREE)
loader = DataLoader()
df = loader.load(['price', 'sopr', 'mvrv'], source='brk', resolution='d1')

# Load hourly data from Bitcoin Lab (uses cache)
df_hourly = loader.load(['price', 'sopr'], source='bl', resolution='h1')

# Check data freshness
freshness = loader.check_data_freshness()
print(freshness)

# Refresh stale data from BRK (FREE)
loader.refresh_cache(metrics=['price', 'sopr'], source='brk')
```

### Quota Management Tips

1. **Use BRK for daily backtesting** - Save Bitcoin Lab quota for intraday work
2. **Cache aggressively** - DataLoader caches to minimize API calls
3. **Sync incrementally** - Only fetch new data since last sync
4. **Monitor usage**: `python run.py quota` and `python run.py quota-history`
5. **Plan ahead**: `python run.py quota-estimate 30 h1` before large syncs
6. **Weekly refresh** - Quota resets every 7 days (1M datapoints)

### Data Freshness

Run daily to keep data current:
```bash
# Morning routine (FREE)
python run.py brk-sync              # Sync daily on-chain data
python run.py data-refresh          # Refresh cache

# Check what needs updating
python run.py data                  # Show cache status
python run.py brk-status            # Confirm BRK sync
python run.py bl-status-hourly      # Check hourly data

# Optional: Sync Bitcoin Lab hourly (uses ~120 DPs for 5 metrics)
python run.py bl-sync-hourly        # Only if doing intraday analysis
```

## Data Quality & Validation ⚠️ ACTION REQUIRED

### Current Status (as of 2026-01-23)

**Data Quality Scan Results:**
- ✅ **BRK Daily**: Perfect - All 41 metrics clean (0 issues in 248,739 rows)
- ⚠️ **Bitcoin Lab Hourly**: 5 minor nulls in SOPR metrics (0.001% of data)
  - `sopr`: 1 null value
  - `sopr_lth`: 3 null values
  - `sopr_sth`: 1 null value

**Current Validation (BASIC):**
- ✅ Automatic null removal after API fetch
- ✅ API error handling and tracking
- ✅ Sync state monitoring
- ✅ Data freshness checks

**Missing Validation (NEEDS IMPLEMENTATION):**
- ❌ Outlier detection (extreme value checks)
- ❌ Data consistency validation (cross-metric relationships)
- ❌ Time series gap detection and reporting
- ❌ Statistical validation (change rate limits)
- ❌ Cross-source validation (BRK vs Bitcoin Lab comparison)
- ❌ Pre-trading validation checks

### Immediate Actions Needed

#### 1. Fix Known Issues (30 seconds)
```bash
# Fix the 5 null values in Bitcoin Lab hourly data
python scripts/fix_data_issues.py

# Verify fix worked
python run.py data
```

#### 2. Before Live Trading (CRITICAL)

**Must implement:**
1. **Outlier detection** for critical metrics (price, sopr, mvrv)
   - Detect extreme values (e.g., MVRV > 10, SOPR > 5)
   - Alert on impossible values (negative price, MVRV < 0)
   - Validate change rates (e.g., price change > 50%/day)

2. **Pre-trading validation**
   - Check data freshness (< 24 hours old)
   - Verify no nulls in critical metrics
   - Validate metric consistency
   - Confirm all required metrics present

3. **Consistency checks**
   - MVRV should equal price / realized_price
   - supply_total should only increase (monotonic)
   - Validate ratio relationships

Example validation before trading:
```python
def validate_for_trading(df):
    """Pre-flight checks before executing trades"""
    checks = {
        'data_fresh': (datetime.now() - df.index[-1]) < timedelta(hours=24),
        'no_nulls': df[CRITICAL_METRICS].isnull().sum().sum() == 0,
        'no_outliers': check_outliers(df),
        'consistent': validate_mvrv_consistency(df),
        'complete': all_required_metrics_present(df)
    }

    if not all(checks.values()):
        raise ValidationError(f"Trading validation failed: {checks}")

    return True
```

#### 3. Recommended Quality Checks

**Add to daily routine:**
```bash
# Check data quality
python scripts/check_data_quality.py  # Scan for issues

# Monitor sync status
python run.py brk-status              # Check for errors
python run.py data                    # Check freshness

# Fix any issues found
python scripts/fix_data_issues.py     # Auto-fix common issues
```

### Quality Check Implementation Plan

**Phase 1: Critical (Before Live Trading)**
- [ ] Fix existing nulls in Bitcoin Lab data ✅ (script ready)
- [ ] Add outlier detection module
- [ ] Add pre-trading validation
- [ ] Add gap detection and reporting
- [ ] Create `src/data_quality.py` module

**Phase 2: Important (Before Paper Trading at Scale)**
- [ ] Implement flexible cleaning strategies (forward/backward fill, interpolation)
- [ ] Add cross-metric consistency validation
- [ ] Add statistical validation (change rates, distributions)
- [ ] Create quality report dashboard

**Phase 3: Optimization (Production)**
- [ ] Cross-source validation (BRK vs Bitcoin Lab comparison)
- [ ] Real-time anomaly detection
- [ ] Automated alerting (email/Telegram)
- [ ] Historical quality tracking and reporting

### Validation Rules by Metric

**Price Metrics:**
- Range: > 0
- Change rate: < 50% per day (typical < 10%)
- No nulls allowed

**SOPR Family:**
- Range: 0.5 - 5.0 (typical 0.8 - 1.2)
- Must be > 0
- Can forward fill small gaps (< 3 hours)

**MVRV Family:**
- Range: 0.1 - 10.0 (extreme bull can exceed)
- Consistency: MVRV ≈ price / realized_price (tolerance: 1%)
- Cross-check with NUPL

**Supply Metrics:**
- supply_total: Must be monotonically increasing
- Range: 0 - 21,000,000 BTC
- supply_lth + supply_sth ≈ supply_total (tolerance: 0.1%)

**Realized Metrics:**
- realized_price, realized_cap: Must be > 0
- Monotonic: realized_cap should generally increase
- realized_profit + realized_loss should balance

### Documentation

**See full recommendations:**
- `docs/DATA_QUALITY_RECOMMENDATIONS.md` - Complete implementation guide
- `scripts/fix_data_issues.py` - Fix current known issues
- `scripts/check_data_quality.py` - Comprehensive quality scan (needs creation)

### Risk of Not Implementing

**Without proper validation, you risk:**
- Trading on stale data (losses from timing)
- Acting on API errors (bad data → bad signals)
- Missing critical data gaps (incomplete picture)
- False signals from outliers (bad trades)
- Consistency violations (conflicting metrics)

**Bottom Line:** Current data is GOOD, but validation is BASIC. Implement Phase 1 (outlier detection + pre-trading checks) BEFORE live trading to avoid costly errors.

---

## Key Files

### Scripts
| File | Purpose |
|------|---------|
| `run.py` | CLI entry point - sync, backfill, status, quota management |
| `scripts/calculate.py` | Signal computation engine - all metric calculations |
| `scripts/dashboard_new.py` | Pure HTML rendering layer (6 pillars layout) |
| `scripts/dashboard.py` | Legacy dashboard (monolithic) |
| `scripts/sync_all.py` | Data synchronization |
| `scripts/backtest_framework.py` | Custom backtest engine (use VectorBT instead) |

### Strategy Configs
| File | Strategy | Status |
|------|----------|--------|
| `config/strategies/strat001_sopr_mvrv_trail.json` | SOPR Double Capitulation + MVRV Trail | PAPER-READY |
| `config/strategies/strat002_long_term_capitulation.json` | Long-term Capitulation (+5,754%) | VALIDATED |
| `config/strategies/strat003_short_term_active.json` | Short-term Active (+5,973%) | PAPER-READY |
| `config/strategies/strat004_james_check_5indicator.json` | 5-Indicator Buy-the-Dip | BACKTESTED |
| `config/strategies/strat005_buy_the_dip_momentum_exit.json` | Buy The Dip + Momentum Exit (+3,017%) | PAPER-READY |

### Data
| Path | Contents |
|------|----------|
| `data/brk/daily/*.parquet` | BRK on-chain metrics - 41 metrics, daily (FREE) |
| `data/bl/hourly/*.parquet` | Bitcoin Lab hourly (h1) - 5 metrics, 2015-2026 |
| `data/bl/h4/*.parquet` | Bitcoin Lab 4-hourly - 5 metrics, 2015-2026 |
| `data/bl/h8/*.parquet` | Bitcoin Lab 8-hourly - 5 metrics, 2015-2026 |
| `data/bl/h12/*.parquet` | Bitcoin Lab 12-hourly - 5 metrics, 2015-2026 |
| `data/glassnode/daily/*.parquet` | Derivatives metrics (funding, liquidations) |
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
# ===== DAILY DATA SYNC (FREE) =====
python run.py brk-sync              # Sync BRK daily data (FREE, 41 metrics)
python run.py brk-status            # Check BRK sync status
python run.py data-refresh          # Refresh cache from BRK (FREE)

# ===== BITCOIN LAB SYNC (PAID - CHECK QUOTA FIRST) =====
python run.py quota                 # Check remaining quota (1M/week)
python run.py bl-sync-hourly        # Sync hourly data (h1, ~120 DPs)
python run.py bl-sync-h4            # Sync 4-hourly (h4, ~30 DPs)
python run.py bl-sync-h8            # Sync 8-hourly (h8, ~15 DPs)
python run.py bl-sync-h12           # Sync 12-hourly (h12, ~10 DPs)
python run.py bl-status             # Check all resolutions status

# ===== QUOTA MANAGEMENT =====
python run.py quota                 # Current quota status
python run.py quota-estimate 30 h1  # Estimate cost for 30 days hourly
python run.py quota-history         # Show 30-day usage history

# ===== DATA STATUS & FRESHNESS =====
python run.py data                  # Show cache freshness
python run.py brk-status            # BRK daily status
python run.py bl-status-hourly      # Bitcoin Lab hourly status

# ===== GENERATE DASHBOARD =====
python scripts/calculate.py         # Compute signals
python scripts/dashboard_new.py     # Render HTML
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
│   ├── brk/daily/               # BRK metrics (FREE, 41 metrics, daily)
│   ├── bl/                      # Bitcoin Lab (PAID, multi-resolution)
│   │   ├── hourly/              # h1: 5 metrics, 96K rows each
│   │   ├── h4/                  # 4-hourly: 5 metrics, 24K rows each
│   │   ├── h8/                  # 8-hourly: 5 metrics, 12K rows each
│   │   └── h12/                 # 12-hourly: 5 metrics, 8K rows each
│   ├── glassnode/daily/         # Derivatives (funding, liquidations)
│   ├── signals/                 # Computed signals
│   └── results/                 # Backtest results
├── config/
│   ├── strategies/              # Strategy JSON configs (STRAT-001 to 005)
│   ├── bl/                      # Bitcoin Lab sync state
│   └── brk_sync_state.json      # BRK sync state
├── research/
│   ├── check/Masterclass.txt    # James Check framework
│   └── *.ipynb                  # Analysis notebooks (1-84+)
└── src/                         # Source code modules
    ├── data_loader.py           # Unified data access layer
    ├── brk_downloader.py        # BRK API client
    ├── downloader.py            # Bitcoin Lab API client
    └── trading_system.py        # Strategy execution engine
```
