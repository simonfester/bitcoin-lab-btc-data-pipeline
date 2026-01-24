# Bitcoin Data Pipeline

**DO NOT USE GLASSNODE API** - Use Bitcoin Lab API and BRK API as primary/redundant data sources.

This pipeline downloads and stores Bitcoin on-chain metrics from two data sources for backtesting and analysis.

## Data Sources

| Source | Cost | Resolutions | Data Freshness | Use Case |
|--------|------|-------------|----------------|----------|
| **BRK** (Bitcoin Research Kit) | FREE | Daily only | ✅ Current | Primary source, all daily metrics |
| **Bitcoin Lab** | Paid (quota) | Daily + Hourly | ✅ Current | Hourly data, backup |

### BRK Data

BRK provides current daily data for all key on-chain metrics. Use as primary source to conserve Bitcoin Lab quota.

## Folder Structure

```
data/
├── bl/                      # Bitcoin Lab (paid)
│   ├── daily/               # d1 - daily resolution
│   ├── hourly/              # h1 - hourly resolution
│   ├── h4/                  # 4-hourly resolution
│   ├── h8/                  # 8-hourly resolution
│   ├── h12/                 # 12-hourly resolution
│   └── block/               # per-block resolution
│
├── brk/                     # BRK (FREE)
│   └── daily/               # daily resolution only
│       ├── price.parquet
│       ├── mvrv.parquet
│       ├── sopr.parquet
│       └── ...
│
└── claude.md                # This file
```

## Commands

### BRK Commands (FREE - Mixed Freshness)

```bash
python run.py brk-sync       # Incremental sync (only new data since last sync)
python run.py brk-backfill   # Full historical download (~41 metrics)
python run.py brk-status     # Show sync status
python run.py brk-discover   # List all available metrics
python run.py brk-discover mvrv  # Search for metrics matching 'mvrv'
```

### Bitcoin Lab Commands (Paid - Uses API Quota)

```bash
# Sync commands (incremental)
python run.py bl-sync-daily      # Daily data
python run.py bl-sync-hourly     # Hourly data (expensive!)
python run.py bl-sync-h4         # 4-hourly data
python run.py bl-sync            # All resolutions

# Backfill commands (full history)
python run.py bl-backfill-daily  # Full daily backfill
python run.py bl-backfill-hourly # Full hourly backfill (very expensive!)
python run.py bl-backfill-all    # All resolutions

# Status
python run.py bl-status          # Show all sync status
python run.py bl-info            # Show API quota
```

### Quota Commands

```bash
python run.py quota              # Show current quota usage
python run.py quota-estimate 30  # Estimate cost for 30 days sync
python run.py quota-history      # Show usage history
```

### Data Loader Commands

```bash
python run.py data               # Show cache freshness
python run.py data-refresh       # Refresh from BRK (FREE)
python run.py data-load price,mvrv,sopr  # Load specific metrics
python run.py signals            # Check current trading signals
```

## BRK Metrics

All key metrics available and current:
- SOPR (sopr, sth_sopr, lth_sopr)
- MVRV (mvrv, sth_mvrv, lth_mvrv)  
- NUPL, AVIV, Supply metrics
- Price, Realized Price, Market Cap

## Available Metrics

### Core Metrics (~41 in BRK)

| Category | Metrics |
|----------|---------|
| **Price** | price, price_200d_sma |
| **SOPR** | sopr, sopr_sth, sopr_lth, sopr_adjusted |
| **MVRV** | mvrv, mvrv_sth, mvrv_lth |
| **NUPL** | nupl, nupl_sth, nupl_lth, unrealized_profit, unrealized_loss |
| **Realized** | realized_cap, realized_price, realized_price_sth, realized_price_lth, realized_profit, realized_loss, net_realized_pnl |
| **Supply** | supply_total, supply_lth, supply_sth, supply_in_profit, supply_in_loss |
| **Cointime** | liveliness, aviv, active_price, vaulted_price, cointime_price, investor_cap, thermo_cap |
| **Sell-side Risk** | sell_side_risk, sell_side_risk_sth, sell_side_risk_lth |
| **Mining** | puell_multiple, difficulty |
| **Coindays** | coindays_destroyed |
| **Market Cap** | market_cap |

## Sync Strategy

### Current Recommendation

**Primary: Use BRK (FREE)**
```bash
python run.py brk-sync          # Daily sync - FREE, all metrics current
python run.py brk-backfill      # Full historical download
```

**Secondary: Use Bitcoin Lab for hourly data only**
```bash
python run.py bl-sync-hourly    # Hourly data (costs quota)
```

### Cost Optimization

- Use BRK for all daily data (FREE, current)
- Use Bitcoin Lab only for hourly resolution (costs quota)

## BRK API Details

### Base URL
```
https://next.bitview.space
```

### Endpoints
```
GET /api/metric/{metric}/{index}?start={N}&end={N}&limit={N}
GET /api/metrics/search/{query}
GET /api/server/sync
```

### Index Types
- `dateindex` - Day number since 2008-01-03 (⚠️ STALE for most metrics)
- `height` - Block height (✅ CURRENT for supported metrics)
- `weekindex`, `monthindex`, `yearindex` - Time aggregations

### Query Parameters
- `start=-5` → Last 5 values
- `start=6000&end=6100` → Specific range
- `limit=100` → First 100 values

## State Files

Sync state is tracked separately for each source:

```
config/
├── bl/                          # Bitcoin Lab state
│   ├── sync_state_d1.json       # Daily sync state
│   ├── sync_state_h1.json       # Hourly sync state
│   └── ...
├── brk_sync_state.json          # BRK sync state
└── metrics.yaml                 # Metric definitions
```

## Data Format

All data is stored as Parquet files with two columns:
- `time`: UTC timestamp (datetime64)
- `value`: Metric value (float64)

Example loading in Python:
```python
import pandas as pd

# Load single metric
df = pd.read_parquet('data/brk/daily/mvrv.parquet')

# Or use the DataLoader
from src.data_loader import load_data
df = load_data(['price', 'mvrv', 'sopr'], source='brk')
```

## API Tokens

- **BRK**: No token required (FREE public API)
- **Bitcoin Lab**: Set `BITCOIN_LAB_TOKEN` environment variable or configure in `config/metrics.yaml`

## Troubleshooting

### BRK sync fails
- Check internet connection
- BRK API: https://next.bitview.space
- No rate limits, but may have occasional downtime

### BRK data issues
- Check BRK API status: https://next.bitview.space
- Run `python run.py brk-status` to check sync state

### Bitcoin Lab quota exceeded
- Check quota: `python run.py quota`
- Wait for weekly reset or upgrade tier
- Use BRK for historical data to conserve quota

### Missing metrics
- Check if metric is available in source: `python run.py brk-status`
- Some metrics are only available in Bitcoin Lab (hourly data)
- Some metrics are only available in BRK

## Links

- **BRK API**: https://next.bitview.space
- **BRK Docs**: https://next.bitview.space/api
- **BRK OpenAPI**: https://next.bitview.space/openapi.json
- **Bitcoin Lab API**: https://api.researchbitcoin.net
- **Bitcoin Lab Docs**: https://api.researchbitcoin.net/docs
