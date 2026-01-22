# Scripts

Core scripts for the Bitcoin trading system.

## Quick Start

```bash
cd /path/to/bitcoin-lab-btc-data-pipeline
source venv/bin/activate

# Full sync (BRK on-chain + Glassnode derivatives) + dashboard
python scripts/sync_all.py

# View dashboard (opens in browser)
python scripts/dashboard.py

# Start HTTPS server (for NUC/server deployment)
python scripts/server.py
```

## Daily Workflow (Recommended)

```bash
# Single command - syncs everything and regenerates dashboard
python scripts/sync_all.py

# Quick sync (last 30 days only) - faster for daily updates
python scripts/sync_all.py --quick
```

## Data Sources

| Source | Type | Cost | Data |
|--------|------|------|------|
| **BRK** | On-chain | FREE | SOPR, MVRV, NUPL, supply metrics |
| **Glassnode** | Derivatives | Subscription | Funding rates, liquidations, OI |
| **Bitcoin Lab** | On-chain | Paid (quota) | Hourly data (backup) |

## Files

| File | Purpose |
|------|---------|
| `sync_all.py` | **Unified sync** - BRK + Glassnode + dashboard |
| `signals.yaml` | Signal definitions (single source of truth) |
| `dashboard.py` | Generate dashboard HTML from cached data |
| `pipeline.py` | Data sync, analysis, backtesting CLI |
| `server.py` | HTTPS server with auto-sync |

## Sync All (Primary Workflow)

```bash
# Full sync - BRK + Glassnode + regenerate dashboard
python scripts/sync_all.py

# Quick sync (last 30 days only) - faster for daily updates
python scripts/sync_all.py --quick

# BRK on-chain only
python scripts/sync_all.py --brk-only

# Glassnode derivatives only
python scripts/sync_all.py --gn-only

# Use FREE Binance derivatives instead of Glassnode
python scripts/sync_all.py --free

# Sync data but don't regenerate dashboard
python scripts/sync_all.py --no-dash

# Check sync status without downloading
python scripts/sync_all.py --status

# Open dashboard in browser after sync
python scripts/sync_all.py --open
```

## Glassnode Derivatives Data

The following metrics are downloaded from Glassnode:

| Metric | Endpoint | Buy-the-Dip Use |
|--------|----------|-----------------|
| `funding_rate` | futures_funding_rate_perpetual | Condition 4: Funding ≤ 0 |
| `liquidations_long` | futures_liquidated_volume_long_sum | Condition 5: Long liq peak |
| `liquidations_short` | futures_liquidated_volume_short_sum | Liquidation ratio |
| `open_interest` | futures_open_interest_sum | Leverage indicator |
| `estimated_leverage_ratio` | futures_estimated_leverage_ratio | Risk assessment |

### Manual Glassnode Download

```bash
# Download Buy-the-Dip critical metrics
python -m src.glassnode_downloader --btd

# Download all derivatives metrics
python -m src.glassnode_downloader --all

# Download specific metric
python -m src.glassnode_downloader --metric funding_rate

# List available metrics
python -m src.glassnode_downloader --list
```

## Dashboard

```bash
# Generate and open
python scripts/dashboard.py

# Generate only (no browser)
python scripts/dashboard.py --no-open

# Auto-regenerate every 60s
python scripts/dashboard.py --watch
```

Output: `dashboard.html` in project root

**Data Priority:**
1. Glassnode cache - `data/glassnode/daily/`
2. Glassnode API (live fetch)
3. Free Binance derivatives (fallback) - `data/derivatives/daily/`

## Server (for NUC deployment)

```bash
# Start HTTPS server on port 8443
python scripts/server.py

# Custom port (443 needs sudo)
sudo python scripts/server.py --port 443

# Disable auto-sync
python scripts/server.py --no-sync

# Custom sync interval (minutes)
python scripts/server.py --sync-interval 30
```

Features:
- HTTPS only (self-signed cert auto-generated)
- Auto-syncs BRK data every 60 min
- Regenerates dashboard after sync
- Live price from Coinbase (client-side)

### Systemd Service (Linux)

Create `/etc/systemd/system/bitcoin-dashboard.service`:

```ini
[Unit]
Description=Bitcoin Dashboard HTTPS Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/bitcoin-lab-btc-data-pipeline
ExecStart=/path/to/venv/bin/python scripts/server.py --port 8443
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bitcoin-dashboard
sudo systemctl start bitcoin-dashboard
```

## Pipeline

```bash
# Check current market state
python scripts/pipeline.py status

# Sync data
python scripts/pipeline.py sync

# Run statistical analysis
python scripts/pipeline.py analyze

# Run backtests
python scripts/pipeline.py backtest

# Full pipeline
python scripts/pipeline.py all
```

## Alternative: Free Derivatives (Binance)

If you want to avoid the Glassnode subscription cost, use the `--free` flag:

```bash
python scripts/sync_all.py --free
```

This uses Binance Futures API (free) for:
- Funding rates
- Open interest
- Long/short ratio
- Taker buy/sell volume

**Note:** Liquidation data is not available in free APIs. The long/short ratio serves as a proxy.
