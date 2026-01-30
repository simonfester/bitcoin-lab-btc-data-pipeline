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
┌──────────────────────────────────────────────────┐
│              STAGE 1: DATA SOURCES               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │ BitcoinLab│  │    BRK    │  │ Glassnode │    │
│  │ (PRIMARY) │  │  (BACKUP) │  │  (PAID)   │    │
│  │ d1/h1/h4  │  │  Daily    │  │ Derives   │    │
│  │ h8/h12    │  │ 41 metrics│  │ 3 metrics │    │
│  │54 metrics │  │           │  │           │    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
└────────┼──────────────┼──────────────┼───────────┘
         │              │              │
         ▼              ▼              ▼
     data/bl/       data/brk/     data/glassnode/
  daily/hourly/      daily/          daily/
  h4/h8/h12/       *.parquet       *.parquet
   *.parquet            │              │
         │              └──────────────┘
         │         (fallback)    │
         └─────────────┬────────┘
                       ▼
     ┌──────────────────────────────────────┐
     │       STAGE 2: CALCULATIONS          │
     │        scripts/calculate.py          │
     │  Runs once per resolution:           │
     │    --resolution daily                │
     │    --resolution hourly               │
     │    --resolution h4                   │
     │    --resolution h8                   │
     │    --resolution h12                  │
     │  + smoothed variants (MA-4/6/8/12)  │
     └──────────────────┬───────────────────┘
                        ▼
                 data/signals/
          dashboard_context.json        (daily)
          dashboard_context_hourly.json (h1)
          dashboard_context_h4.json     (h4)
          dashboard_context_h8.json     (h8)
          dashboard_context_h12.json    (h12)
          + *_ma4, *_ma6, *_ma8, *_ma12 (smoothed)
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │          STAGE 3: DISPLAY            │
     │       scripts/dashboard_new.py       │
     │  - HTML rendering (6 pillars)        │
     │  - Live price (optional)             │
     └──────────────────┬───────────────────┘
                        ▼
                 dashboard.html
```

### Stage 1: Data Sync (`run.py`)
**Multi-source data acquisition:**
- **Bitcoin Lab** (PRIMARY): `python run.py bl-sync-hourly` → `data/bl/hourly/` (348 metrics available, quota-limited)
- **BRK** (BACKUP): `python run.py brk-sync` → `data/brk/daily/` (41 metrics, unreliable uptime)
- **Glassnode** (PAID): Manual sync → `data/glassnode/daily/` (derivatives)

### Stage 2: Signal Calculation (`scripts/calculate.py`)
- Runs **once per resolution** — all 5 resolutions treated equally
- Each resolution loads from its `data/bl/<res>/` directory (fallback: BL daily → BRK daily)
- Computes signals using James Check framework (6 pillars)
- Sub-daily resolutions also produce smoothed variants (MA-4, MA-6, MA-8, MA-12)
- Outputs per resolution: `dashboard_context[_<res>].json` + parquets

```bash
python scripts/calculate.py                      # Daily signals
python scripts/calculate.py --resolution hourly  # h1 signals + smoothed
python scripts/calculate.py --resolution h4      # h4 signals + smoothed
python scripts/calculate.py --resolution h8      # h8 signals + smoothed
python scripts/calculate.py --resolution h12     # h12 signals + smoothed
```

### Stage 3: Dashboard Display (`scripts/dashboard_new.py`)
- Pure HTML rendering, no calculations
- Displays 6 pillars with current market status
- Optionally fetches live price from Coinbase
- Run: `python scripts/dashboard_new.py`

## Data Sources & Availability

### Overview

**DO NOT USE GLASSNODE API** - Use Bitcoin Lab API as the primary source. BRK is backup only.

| Source | Cost | Resolutions | Use Case |
|--------|------|-------------|----------|
| **Bitcoin Lab** | Paid (40M quota/week) | Hourly, 4h, 8h, 12h, Daily | **PRIMARY** - 348 metrics at all resolutions |
| **BRK** | FREE | Daily only | **BACKUP** - 41 daily on-chain metrics (unreliable uptime) |
| **Glassnode** | Paid | Daily | Derivatives only (funding rates, liquidations) |

### Current Data Availability (Last Synced: 2026-01-30)

#### Bitcoin Lab (PAID - PRIMARY SOURCE)
**Status**: ✅ Fully synced — all resolutions, all metrics
**Quota**: 40,000,000 DPs/week (Tier 2)
**Quota Reset**: Every 7 days
**Date Range**: 2015-01-01 → 2026-01-30
**Subscription Expires**: 2026-09-08
**Token Expires**: 2026-04-06

**Resolution Coverage (54 metrics at every resolution):**

| Resolution | Metrics | Rows/Metric | Date Range | Last Sync |
|------------|---------|-------------|------------|-----------|
| **d1** (daily) | 56 | 4,047 | 2015-01-01 → 2026-01-30 | ✅ 2026-01-30 |
| **h1** (hourly) | 54 | ~96,876 | 2015-01-01 → 2026-01-30 | ✅ 2026-01-30 |
| **h4** (4-hourly) | 54 | 24,284 | 2015-01-01 → 2026-01-30 | ✅ 2026-01-30 |
| **h8** (8-hourly) | 54 | 12,142 | 2015-01-01 → 2026-01-30 | ✅ 2026-01-30 |
| **h12** (12-hourly) | 54 | 8,095 | 2015-01-01 → 2026-01-30 | ✅ 2026-01-30 |

**API supports 348 metrics across 34 categories at all resolutions** (h1, h4, h8, h12, d1, block).
- Full catalog: https://researchbitcoin.net/metrics/
- API spec: https://api.researchbitcoin.net/openapi/openapi.json

**Synced metrics (54, same across all resolutions):**
- **Price & Market**: price, market_cap
- **Valuation**: mvrv, mvrv_z, mvrv_lth, mvrv_sth, nvt, velocity, aviv
- **SOPR**: sopr, sopr_lth, sopr_sth
- **Profitability**: nupl, nupl_lth, nupl_sth, net_realized_pnl
- **Supply**: supply_in_profit, supply_in_profit_percent, supply_in_loss, supply_lth, supply_sth, supply_lth_sth_ratio, supply_total
- **Realized Cap/Price**: realized_cap, realized_cap_lth, realized_cap_sth, realized_price, realized_price_lth, realized_price_sth
- **Cointime**: liveliness, vaultedness, supply_active, supply_vaulted, true_market_mean_price, investor_cap, thermo_cap, vaulted_price
- **Dormancy**: coindays_destroyed, asol, dormancy
- **Network**: difficulty, tx_count, utxo_increase (hashrate d1-only)
- **Fees**: fee_total, fee_total_usd, fee_avg
- **Volume**: volume_btc, volume_usd, volume_btc_adjusted
- **Unrealized P&L**: unrealized_profit, unrealized_loss, unrealized_cap
- **Realized P&L**: realized_profit, realized_loss

**Weekly quota cost (incremental sync):**
- All 5 resolutions: ~13,600 DPs/week (0.03% of 40M quota)

**Sync Commands:**
```bash
# Check quota
python run.py quota                # Show remaining quota

# Incremental sync (daily use)
python run.py bl-sync-hourly       # Hourly (h1)
python run.py bl-sync-h4           # 4-hourly
python run.py bl-sync-h8           # 8-hourly
python run.py bl-sync-h12          # 12-hourly
python run.py bl-sync              # All resolutions

# Backfill historical data
python run.py bl-backfill-hourly   # h1 from 2015-01-01
python run.py bl-backfill-h4       # h4 from 2015-01-01
python run.py bl-backfill-h8       # h8 from 2015-01-01
python run.py bl-backfill-h12      # h12 from 2015-01-01
python run.py bl-backfill-daily    # d1 from 2015-01-01

# Check status
python run.py bl-status            # All resolutions status
python run.py bl-status-hourly     # Hourly status only
python run.py quota-estimate 7 h1  # Estimate cost for 7 days of hourly
```

#### BRK (FREE - BACKUP SOURCE)
**Status**: ⚠️ Unreliable — HTTP 530 outages (Cloudflare origin errors)
**Resolution**: Daily only
**Date Range**: 2009-01-03 → 2026-01-27 (last successful sync)
**Metrics**: 41 on-chain metrics

**Sync Commands:**
```bash
python run.py brk-sync          # Incremental daily sync (may fail)
python run.py brk-backfill      # Full historical download
python run.py brk-status        # Check sync status
```

**Quota Mechanics:**
- 1 DP = 1 numeric value for 1 metric at 1 timestamp
- Binned metrics: DP = timestamps × bins (e.g., `spent_output_by_age_sumbtc` at daily with 7 bins = 7 DP/day)
- Quota charged 1:1 with DP

**Quota Costs (simple series, per metric):**
- **h1** (hourly): ~24 DP/day
- **h4** (4-hourly): ~6 DP/day
- **h8** (8-hourly): ~3 DP/day
- **h12** (12-hourly): ~2 DP/day
- **d1** (daily): ~1 DP/day

**Tiers:**
| Tier | Weekly Quota | Historical Data | Activation |
|------|-------------|-----------------|------------|
| 0 (Free) | 55,000 DPs | Past 1 year | Free |
| 1 | 900,000 DPs | Unlimited | ≥ 0.00025 BTC |
| 2 | 40,000,000 DPs | Unlimited | ≥ 0.00100 BTC |

**Example**: Syncing 30 days of hourly data for 12 metrics = 30 × 24 × 12 = 8,640 DP

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
- Tier: 2 (40M datapoints/week)
- Token Expires: 2026-04-06
- API Spec: `https://api.researchbitcoin.net/openapi/openapi.json`
- Metrics Catalog: `https://researchbitcoin.net/metrics/`
- Error Codes: 400 (invalid params), 401 (missing/invalid token), 403 (forbidden/tier), 404 (not found), 429 (rate limited), 5xx (server error)

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
│   └── daily/              # BRK daily metrics (41 metrics, BACKUP)
│       ├── price.parquet
│       ├── sopr.parquet
│       └── ... (39 more)
├── bl/                     # Bitcoin Lab (PRIMARY - 54 metrics × 5 resolutions)
│   ├── daily/              # d1 - 54 metrics, 4,047 rows each
│   ├── hourly/             # h1 - 54 metrics, ~96K rows each
│   ├── h4/                 # h4 - 54 metrics, 24,284 rows each
│   ├── h8/                 # h8 - 54 metrics, 12,142 rows each
│   └── h12/                # h12 - 54 metrics, 8,095 rows each
├── glassnode/
│   └── daily/              # Derivatives data
│       ├── funding_rate.parquet
│       ├── liq_long.parquet
│       └── liq_short.parquet
└── signals/                # Computed signals (per resolution)
    ├── dashboard_context.json          # Daily signals
    ├── dashboard_context_hourly.json   # h1 signals
    ├── dashboard_context_h4.json       # h4 signals
    ├── dashboard_context_h8.json       # h8 signals
    ├── dashboard_context_h12.json      # h12 signals
    ├── dashboard_context_*_ma*.json    # Smoothed variants
    ├── entry_signals*.parquet          # Entry signals per resolution
    ├── exit_signals*.parquet           # Exit signals per resolution
    ├── buy_the_dip*.parquet            # BTD conditions per resolution
    └── checkmate*.parquet              # Checkmate conditions per resolution
```

### Data Source Recommendations

**For Daily Analysis (Backtesting, Strategies):**
- ✅ **Use Bitcoin Lab** - Primary source, 348 metrics, all resolutions
- 📊 Monitor quota usage: `python run.py quota`
- 🔄 **BRK as fallback** - Free but unreliable uptime (HTTP 530 outages)

**For Intraday/High-Frequency Analysis:**
- ✅ **Use Bitcoin Lab** - Primary source for hourly/4h/8h/12h data
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

1. **Use Bitcoin Lab as primary source** - BRK is backup only (unreliable uptime)
2. **Cache aggressively** - DataLoader caches to minimize API calls
3. **Sync incrementally** - Only fetch new data since last sync
4. **Monitor usage**: `python run.py quota` and `python run.py quota-history`
5. **Plan ahead**: `python run.py quota-estimate 30 h1` before large syncs
6. **Weekly refresh** - Quota resets every 7 days (40M datapoints)

### Data Freshness

Run daily to keep data current:
```bash
# Morning routine (PRIMARY - Bitcoin Lab)
python run.py quota                 # Check remaining quota
python run.py bl-sync-hourly        # Sync all resolutions
python run.py bl-status             # Confirm sync

# Calculate all resolutions and render dashboard
python scripts/calculate.py                      # Daily signals
python scripts/calculate.py --resolution hourly  # h1 signals + smoothed
python scripts/calculate.py --resolution h4      # h4 signals + smoothed
python scripts/calculate.py --resolution h8      # h8 signals + smoothed
python scripts/calculate.py --resolution h12     # h12 signals + smoothed
python scripts/dashboard_new.py                  # Render dashboard

# Or use the full pipeline (syncs + calculates all resolutions + dashboard)
python scripts/sync_and_dashboard.py             # Full pipeline
python scripts/sync_and_dashboard.py --skip-sync # Calculate + dashboard only

# Check what needs updating
python run.py data                  # Show cache status

# Optional: BRK backup sync (FREE but unreliable)
python run.py brk-sync              # May fail with HTTP 530
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
| `scripts/calculate.py` | Signal computation engine - all 5 resolutions (daily, hourly, h4, h8, h12) |
| `scripts/sync_and_dashboard.py` | Full pipeline - sync all sources, calculate all resolutions, generate dashboards |
| `scripts/dashboard_new.py` | Pure HTML rendering layer (6 pillars layout) |
| `scripts/dashboard.py` | Legacy dashboard (monolithic) |
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
| `data/brk/daily/*.parquet` | BRK on-chain metrics - 41 metrics, daily (BACKUP) |
| `data/bl/daily/*.parquet` | Bitcoin Lab daily (d1) - 54 metrics, 2015-2026 |
| `data/bl/hourly/*.parquet` | Bitcoin Lab hourly (h1) - 54 metrics, 2015-2026 |
| `data/bl/h4/*.parquet` | Bitcoin Lab 4-hourly - 54 metrics, 2015-2026 |
| `data/bl/h8/*.parquet` | Bitcoin Lab 8-hourly - 54 metrics, 2015-2026 |
| `data/bl/h12/*.parquet` | Bitcoin Lab 12-hourly - 54 metrics, 2015-2026 |
| `data/glassnode/daily/*.parquet` | Derivatives metrics (funding, liquidations) |
| `data/signals/dashboard_context.json` | Daily signals for dashboard |
| `data/signals/dashboard_context_hourly.json` | Hourly (h1) signals |
| `data/signals/dashboard_context_h4.json` | 4-hourly signals |
| `data/signals/dashboard_context_h8.json` | 8-hourly signals |
| `data/signals/dashboard_context_h12.json` | 12-hourly signals |
| `data/signals/*_ma{4,6,8,12}.json` | Smoothed variants per sub-daily resolution |
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
# ===== PRIMARY DATA SYNC (Bitcoin Lab) =====
python run.py quota                 # Check remaining quota (40M/week)
python run.py bl-sync-hourly        # Sync hourly data (h1, primary source)
python run.py bl-sync-h4            # Sync 4-hourly (h4)
python run.py bl-sync-h8            # Sync 8-hourly (h8)
python run.py bl-sync-h12           # Sync 12-hourly (h12)
python run.py bl-sync-daily         # Sync daily (d1)
python run.py bl-status             # Check all resolutions status

# ===== BACKUP DATA SYNC (BRK - FREE but unreliable) =====
python run.py brk-sync              # Sync BRK daily data (may fail with 530)
python run.py brk-status            # Check BRK sync status

# ===== QUOTA MANAGEMENT =====
python run.py quota                 # Current quota status
python run.py quota-estimate 30 h1  # Estimate cost for 30 days hourly
python run.py quota-history         # Show 30-day usage history

# ===== DATA STATUS & FRESHNESS =====
python run.py data                  # Show cache freshness
python run.py brk-status            # BRK daily status
python run.py bl-status-hourly      # Bitcoin Lab hourly status

# ===== CALCULATE SIGNALS (all 5 resolutions) =====
python scripts/calculate.py                      # Daily signals
python scripts/calculate.py --resolution hourly  # h1 + smoothed variants
python scripts/calculate.py --resolution h4      # h4 + smoothed variants
python scripts/calculate.py --resolution h8      # h8 + smoothed variants
python scripts/calculate.py --resolution h12     # h12 + smoothed variants

# ===== GENERATE DASHBOARD =====
python scripts/dashboard_new.py     # Render HTML from daily signals

# ===== FULL PIPELINE (sync + calculate all + dashboard) =====
python scripts/sync_and_dashboard.py             # Everything
python scripts/sync_and_dashboard.py --skip-sync # Calculate + dashboard only
python scripts/sync_and_dashboard.py --no-open   # Don't open browser
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
│   ├── calculate.py             # Signal computation (all 5 resolutions)
│   ├── dashboard_new.py         # HTML rendering (6 pillars)
│   └── sync_and_dashboard.py    # Full pipeline (sync + calc + dashboard)
├── data/
│   ├── brk/daily/               # BRK metrics (BACKUP, 41 metrics, daily)
│   ├── bl/                      # Bitcoin Lab (PRIMARY, 54 metrics × 5 resolutions)
│   │   ├── daily/               # d1: 54 metrics, 4K rows each
│   │   ├── hourly/              # h1: 54 metrics, 96K rows each
│   │   ├── h4/                  # h4: 54 metrics, 24K rows each
│   │   ├── h8/                  # h8: 54 metrics, 12K rows each
│   │   └── h12/                 # h12: 54 metrics, 8K rows each
│   ├── glassnode/daily/         # Derivatives (funding, liquidations)
│   ├── signals/                 # Computed signals (per resolution + smoothed)
│   └── results/                 # Backtest results
├── config/
│   ├── metrics.yaml             # Metrics registry (54 metrics, all resolutions)
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
