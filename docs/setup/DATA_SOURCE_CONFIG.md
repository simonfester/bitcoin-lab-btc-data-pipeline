# Data Source Configuration

**Last Updated:** 2026-01-23
**Decision:** Use Bitcoin Lab for all on-chain metrics, Glassnode for derivatives

---

## Final Configuration

### On-Chain Metrics (Bitcoin Lab)
**Source:** Bitcoin Lab API
**Path:** `data/bl/daily/*.parquet`
**Cost:** Paid subscription (already invested)
**Resolution:** Daily (hourly available)

**Why Bitcoin Lab:**
- ✅ Correct NUPL metric (0.19% error vs Glassnode)
- ✅ 56 on-chain metrics available
- ✅ Standard units (no conversions needed)
- ✅ Hourly resolution support
- ✅ Already paying for it

**Metrics Available:**
- Price, MVRV, NUPL (all variants)
- SOPR (all cohorts)
- Supply metrics (LTH, STH, total)
- Realized cap, market cap
- Liveliness, AVIV, vaultedness
- 50+ additional metrics

---

### Derivatives Data (Glassnode)
**Source:** Glassnode API (via MCP)
**Path:** `data/glassnode/daily/*.parquet` or direct MCP queries
**Cost:** Paid subscription
**Resolution:** Daily + Hourly

**Why Glassnode:**
- ✅ Industry standard for derivatives data
- ✅ Direct MCP access for live queries
- ✅ Funding rates, liquidations, open interest
- ✅ Reliable and well-maintained

**Metrics:**
- Funding rates (perpetual futures)
- Liquidations (long/short)
- Open interest
- Options data (if needed)

---

## Data Paths

### Bitcoin Lab Daily Data
```
data/bl/daily/
├── price.parquet
├── nupl.parquet
├── mvrv.parquet
├── sopr.parquet
├── sopr_lth.parquet
├── sopr_sth.parquet
├── supply_total.parquet
├── supply_lth.parquet
├── supply_sth.parquet
└── ... (47 more metrics)
```

### Glassnode Derivatives
```
data/glassnode/daily/
├── funding_rate.parquet
├── liquidations_long.parquet
├── liquidations_short.parquet
└── open_interest.parquet
```

---

## Sync Commands

### Bitcoin Lab
```bash
# Daily sync
python run.py bl-sync-daily

# Check status
python run.py bl-status

# Check quota
python run.py quota
```

### Glassnode
```bash
# Sync derivatives
python scripts/sync_glassnode_daily.py

# Or use MCP for live data
# Example: "Get Bitcoin funding rate for last 30 days"
```

---

## Loading Data in Strategies

### Python
```python
import pandas as pd

# Load Bitcoin Lab data (on-chain)
price = pd.read_parquet('data/bl/daily/price.parquet')
nupl = pd.read_parquet('data/bl/daily/nupl.parquet')
mvrv = pd.read_parquet('data/bl/daily/mvrv.parquet')

# Load Glassnode data (derivatives)
funding = pd.read_parquet('data/glassnode/daily/funding_rate.parquet')
liqs_long = pd.read_parquet('data/glassnode/daily/liquidations_long.parquet')
```

### Existing Code
Most existing strategy code already uses `data/bl/daily/` paths, so no changes needed.

---

## BRK Data (Deprecated)

**Status:** ⚠️ Not recommended for production use

**Issues Found:**
- Supply metrics in satoshis (needs conversion)
- NUPL is wrong metric (absolute P&L, not ratio)
- Price is accurate but Bitcoin Lab is close enough

**Keep For:**
- Research/comparison
- Backup if Bitcoin Lab is down

**Path:** `data/brk/daily/*.parquet`

---

## Quality Metrics

| Source | Metric | Error vs Glassnode | Status |
|--------|--------|-------------------|--------|
| Bitcoin Lab | NUPL | 0.19% MAE | ✅ Excellent |
| Bitcoin Lab | Price | $972 MAE | ✅ Good |
| Bitcoin Lab | Supply | 520 BTC MAE | ✅ Good |
| Glassnode | Derivatives | Reference | ✅ Gold Standard |

---

## Maintenance

### Daily Checks
```bash
# 1. Check freshness
python scripts/check_data_freshness.py

# 2. Sync if stale
python run.py bl-sync-daily

# 3. Check quality (weekly)
python scripts/check_data_quality.py
```

### Quota Management
```bash
# Check Bitcoin Lab quota remaining
python run.py quota

# Expected usage: ~50 credits/day for daily sync
```

---

## Migration from BRK (If needed)

If you have strategies using BRK data:

1. Change paths from `data/brk/daily/` to `data/bl/daily/`
2. No unit conversions needed (Bitcoin Lab uses standard units)
3. NUPL will work correctly (Bitcoin Lab has proper ratio)

**Example:**
```python
# Before (BRK)
df = pd.read_parquet('data/brk/daily/nupl.parquet')  # Wrong metric

# After (Bitcoin Lab)
df = pd.read_parquet('data/bl/daily/nupl.parquet')   # Correct metric ✅
```

---

## Summary

**Simple Rule:**
- **On-chain data** → Bitcoin Lab (`data/bl/daily/`)
- **Derivatives** → Glassnode (`data/glassnode/daily/` or MCP)

**Cost:** Both are paid services you're already subscribed to.
**Quality:** Both are industry-standard sources.
**Maintenance:** Daily syncs, weekly quality checks.

---

**Configuration Approved:** 2026-01-23
**Next Review:** As needed or when new data sources become available
