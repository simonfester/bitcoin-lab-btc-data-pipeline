# Dashboard Workflow Guide

## Quick Start

### 🚀 One-Command Full Update
```bash
python run.py dashboard
```

This runs the entire pipeline:
1. ✅ Syncs BRK data (FREE, primary source)
2. ✅ Syncs Glassnode data (derivatives)
3. ✅ Checks data freshness
4. ✅ Checks data quality
5. ✅ Calculates all signals
6. ✅ Generates dashboards
7. ✅ Opens in browser

---

## Daily Workflow

### Morning Routine (Before Market Analysis)
```bash
python run.py dashboard
```
- Full sync + fresh dashboards
- Takes ~2-5 minutes
- Opens both dashboards automatically

### Quick Refresh (Dashboard Already Synced)
```bash
python run.py dashboard-quick
```
- Skips data sync
- Just recalculates signals and opens dashboards
- Takes ~30 seconds

### Quality Check Only
```bash
python run.py dashboard-quality
```
- Checks data freshness and quality
- No sync, no calculation
- Quick validation

---

## Alternative Commands

### Using the Full Script Directly
```bash
# Full pipeline
python scripts/sync_and_dashboard.py

# Skip sync
python scripts/sync_and_dashboard.py --skip-sync

# Quality only
python scripts/sync_and_dashboard.py --quality-only

# No browser open
python scripts/sync_and_dashboard.py --no-open

# Skip specific sources
python scripts/sync_and_dashboard.py --skip-brk
python scripts/sync_and_dashboard.py --skip-glassnode
```

---

## What Gets Generated

### Dashboards Created
1. **`dashboard.html`** - Main 6-pillar on-chain analysis dashboard
   - Price levels & valuation
   - Profitability metrics
   - Spending behavior
   - Supply distribution
   - Activity metrics
   - Miner health

2. **`dashboard_signals.html`** - Trading signals dashboard
   - Checkmate Signal
   - Buy The Dip checklist
   - 8-Metric Exit Detector
   - STH-MVRV Zones
   - LTH Distribution
   - Entry/Exit signals

### Data Generated
- `data/signals/dashboard_context.json` - Pre-computed signals
- `data/signals/*.parquet` - Signal time series

---

## Pipeline Steps Explained

### 1. Sync BRK Data (FREE)
- Downloads latest daily on-chain metrics
- ~41 metrics: SOPR, MVRV, NUPL, supply, etc.
- Incremental sync (only new data)
- FREE public API

### 2. Sync Glassnode Data (Derivatives)
- Funding rates
- Liquidations (long/short)
- Open interest
- Uses paid Glassnode API

### 3. Check Data Freshness
- Validates data is up-to-date
- Resolution-aware thresholds:
  - Daily: ≤48h (allows publication lag)
  - Hourly: ≤1h
- Non-blocking (continues even if stale)

### 4. Check Data Quality
- Value range validation
- Cross-metric consistency
- Data type validation
- Non-blocking (continues even with issues)

### 5. Calculate Signals
- Runs `scripts/calculate.py`
- Computes all metrics and signals
- Outputs to `data/signals/`
- Critical step - must succeed

### 6. Generate Dashboards
- Renders HTML from pre-computed signals
- Fetches live price from Coinbase
- Opens in default browser

---

## Troubleshooting

### "BRK sync failed"
```bash
# Check BRK status
python run.py brk-status

# Try manual sync
python run.py brk-sync
```

### "Glassnode sync failed"
- Non-critical - pipeline will continue
- Check if `scripts/sync_glassnode_daily.py` exists
- Verify Glassnode API key in MCP config

### "Data quality issues detected"
- Check quality report output
- Pipeline continues - signals still generated
- Run full quality check:
  ```bash
  python scripts/check_data_quality.py
  ```

### "Dashboards not opening"
- Add `--no-open` flag to skip browser opening
- Manually open `dashboard.html` and `dashboard_signals.html`

---

## Advanced Usage

### Custom Sync Options
```bash
# Sync BRK only
python scripts/sync_and_dashboard.py --skip-glassnode

# Sync Glassnode only
python scripts/sync_and_dashboard.py --skip-brk

# Generate dashboards without opening
python scripts/sync_and_dashboard.py --no-open
```

### Manual Pipeline Steps
```bash
# 1. Sync data
python run.py brk-sync

# 2. Check quality
python scripts/check_data_freshness.py
python scripts/check_data_quality.py

# 3. Calculate signals
python scripts/calculate.py

# 4. Generate dashboards
python scripts/dashboard_new.py
python scripts/dashboard_signals.py
```

---

## Automation

### Cron Job (Daily at 9 AM)
```cron
0 9 * * * cd /path/to/bitcoin-lab-btc-data-pipeline && python run.py dashboard --no-open
```

### Shell Alias
```bash
# Add to ~/.bashrc or ~/.zshrc
alias btc-dash="cd /path/to/bitcoin-lab-btc-data-pipeline && python run.py dashboard"
```

Then just run:
```bash
btc-dash
```

---

## File Locations

```
bitcoin-lab-btc-data-pipeline/
├── scripts/
│   ├── sync_and_dashboard.py     # Main wrapper script
│   ├── calculate.py               # Signal computation
│   ├── dashboard_new.py           # 6-pillar dashboard
│   ├── dashboard_signals.py       # Trading signals dashboard
│   ├── check_data_freshness.py   # Freshness validator
│   └── check_data_quality.py     # Quality validator
├── data/
│   ├── brk/daily/                 # BRK on-chain data
│   ├── glassnode/daily/           # Glassnode derivatives
│   └── signals/                   # Computed signals
├── run.py                         # CLI entry point
├── dashboard.html                 # Generated main dashboard
└── dashboard_signals.html         # Generated signals dashboard
```

---

## Cost & Performance

### BRK Sync
- **Cost**: FREE
- **Time**: ~30-60 seconds
- **Data**: ~41 daily metrics

### Glassnode Sync
- **Cost**: API credits (minimal for daily)
- **Time**: ~10-20 seconds
- **Data**: 4 derivatives metrics

### Total Pipeline Time
- **Full sync**: 2-5 minutes
- **Quick refresh**: 30 seconds
- **Quality check**: 10 seconds

### API Quota Usage
- BRK: No limits (FREE)
- Glassnode: ~10-20 credits per sync
- Bitcoin Lab: Not used (deprecated for daily workflow)

---

## Next Steps

1. **Run full sync**: `python run.py dashboard`
2. **Review signals**: Check `dashboard_signals.html`
3. **Analyze metrics**: Check `dashboard.html`
4. **Set up automation**: Add cron job for daily updates
5. **Customize**: Edit `scripts/calculate.py` for custom signals

---

**Last Updated**: 2026-01-24
