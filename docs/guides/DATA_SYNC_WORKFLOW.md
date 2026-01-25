# Data Sync Workflow

**Last Updated**: 2026-01-24

## Full Pipeline Command

```bash
python run.py dashboard
```

This **one command** syncs all data sources, checks quality, calculates signals, and opens dashboards.

---

## What Gets Synced

When you run `python run.py dashboard`, here's what happens:

### STEP 1: Sync BRK Data (FREE) ✅
**Source**: https://next.bitview.space
**Cost**: FREE
**What**: 41 daily on-chain metrics

**Metrics**:
- SOPR (all cohorts)
- MVRV (all cohorts)
- Supply metrics (LTH/STH)
- Realized metrics
- Cointime economics
- And more...

**Format Notes**:
- NUPL: Absolute USD (not ratio)
- Supply: Satoshis (not BTC)
- Early data: Has zeros and extreme values

**Why**: Primary free source for most metrics

---

### STEP 2: Sync Bitcoin Lab Data (Daily) ✅
**Source**: https://api.researchbitcoin.net
**Cost**: Uses API quota (~10-20 credits per sync)
**What**: Clean daily on-chain metrics

**Key Metrics**:
- NUPL (ratio format: -1 to 1)
- Price (no zeros, clean)
- SOPR (clean calculations)
- MVRV (standard format)

**Why**: Backup for BRK format differences

---

### STEP 3: Sync Glassnode Data (Derivatives) ✅
**Source**: Glassnode Studio
**Cost**: Uses API quota
**What**: Derivatives data only

**Metrics**:
- Funding rates
- Liquidations (long/short)
- Open interest
- Derivatives risk metrics

**Why**: BRK and Bitcoin Lab don't have derivatives data

---

### STEP 4: Check Data Freshness
**Validates**:
- Daily data ≤ 48h old
- Hourly data ≤ 1h old

**Categorizes**:
- Critical: Daily sources (used for signals)
- Optional: Hourly sources (not used)

---

### STEP 5: Check Data Quality
**Validates**:
- No nulls, infinites, duplicates
- Values in expected ranges
- Cross-metric consistency
- Handles BRK format differences

**Result**: Clean/Good/Needs Attention status

---

### STEP 6: Calculate Trading Signals
**Computes**:
- Entry signals (SOPR, STH-SOPR, Realized Loss)
- Exit signals (LTH-SOPR, MVRV-Z)
- Buy The Dip (5 conditions)
- Checkmate Signal (4 conditions)

**Output**: `data/signals/dashboard_context.json`

---

### STEP 7: Generate Dashboards
**Creates**:
1. `dashboards/dashboard.html` - 6-pillar on-chain analysis
2. `dashboards/dashboard_signals.html` - Trading signals
3. `dashboards/dashboard_quality.html` - Data quality report

**Opens**: All 3 dashboards in browser

---

## Quick Commands

### Full Sync (Everything)
```bash
python run.py dashboard
```
**Time**: 2-5 minutes
**Cost**: ~20-40 API credits (Bitcoin Lab + Glassnode)

---

### Quick Refresh (Skip Sync)
```bash
python run.py dashboard-quick
```
**Time**: 30 seconds
**Cost**: FREE (no API calls)

---

### Quality Check Only
```bash
python run.py dashboard-quality
```
**Time**: 10 seconds
**Cost**: FREE

---

### Skip Specific Sources

```bash
# Skip BRK (use Bitcoin Lab only)
python run.py dashboard --skip-brk

# Skip Bitcoin Lab (use BRK only, save quota)
python run.py dashboard --skip-bitcoin-lab

# Skip Glassnode (no derivatives data)
python run.py dashboard --skip-glassnode

# Skip all syncs (just recalculate)
python run.py dashboard --skip-sync
```

---

## Data Source Comparison

| Feature | BRK | Bitcoin Lab | Glassnode |
|---------|-----|-------------|-----------|
| **Cost** | FREE | ~10-20 credits/day | ~10-20 credits/day |
| **Metrics** | 41 daily | 56 daily | 5 derivatives |
| **NUPL Format** | Absolute USD | Ratio (-1 to 1) | N/A |
| **Supply Units** | Satoshis | BTC | N/A |
| **Price Data** | Has zeros (2009-2011) | Clean | N/A |
| **Derivatives** | ❌ No | ❌ No | ✅ Yes |
| **Update Frequency** | Daily | Daily/Hourly | Daily |

---

## Recommended Workflow

### Daily Trading Routine
```bash
# Morning: Full sync
python run.py dashboard

# Later: Quick refresh (no sync)
python run.py dashboard-quick

# Check quality anytime
python run.py dashboard-quality
```

---

### Save API Quota
```bash
# Use BRK only (FREE, skip Bitcoin Lab)
python run.py dashboard --skip-bitcoin-lab

# Or sync less frequently
# Only sync 2-3x per week instead of daily
```

---

### Backfill Missing Data
```bash
# BRK full backfill (FREE)
python run.py brk-backfill

# Bitcoin Lab backfill (uses quota)
python run.py bl-backfill-daily

# Check what's missing
python run.py brk-status
python run.py bl-status
```

---

## Which Sources Do We Actually Use?

Based on `scripts/calculate.py`, here's the **actual usage**:

### Primary Source: BRK (FREE)
- SOPR, STH-SOPR, LTH-SOPR ✅
- MVRV, STH-MVRV, LTH-MVRV ✅
- Supply LTH, Supply STH ✅
- Realized metrics ✅
- Most on-chain data ✅

### Backup: Bitcoin Lab
- NUPL (ratio format) ✅
- Price (clean, no zeros) ✅
- Backup for any BRK issues ✅

### Derivatives: Glassnode
- Funding rates ✅
- Liquidations (long/short) ✅
- Used in "Buy The Dip" signal ✅

---

## Troubleshooting

### "BRK sync failed"
```bash
# Check status
python run.py brk-status

# Retry sync
python run.py brk-sync
```

### "Bitcoin Lab quota exceeded"
```bash
# Check quota
python run.py quota

# Skip Bitcoin Lab, use BRK only
python run.py dashboard --skip-bitcoin-lab
```

### "Stale data warning"
```bash
# Full sync to update everything
python run.py dashboard

# Or sync individual sources
python run.py brk-sync
python run.py bl-sync-daily
```

---

## Summary

**Before**: `python run.py dashboard` synced only 2/3 sources (BRK + Glassnode)
**Now**: Syncs all 3 sources (BRK + Bitcoin Lab + Glassnode) ✅

**Cost per full sync**: ~30-50 API credits total
- Bitcoin Lab daily: ~10-20 credits
- Glassnode daily: ~10-20 credits
- BRK: FREE

**Best Practice**:
- Run full sync 2-3x per week
- Use `dashboard-quick` for daily refreshes
- Skip Bitcoin Lab to save quota if needed

---

**Related Docs**:
- [Dashboard Workflow](DASHBOARD_WORKFLOW.md)
- [Data Source Config](../setup/DATA_SOURCE_CONFIG.md)
- [BRK Data Format Notes](../archive/BRK_DATA_FORMAT_NOTES.md)
