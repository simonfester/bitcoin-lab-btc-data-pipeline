# Bitcoin Lab Data Pipeline

A data pipeline for downloading, storing, and analysing Bitcoin on-chain metrics from the [Bitcoin Lab API](https://docs.researchbitcoin.net) for backtesting, machine learning, and trading strategy development.

## Features

- **53 on-chain metrics** including MVRV, SOPR, NUPL, NVT, supply distributions, and more
- **Incremental sync** — only downloads new data since last update
- **Parquet storage** — fast, compressed, ML-friendly columnar format

## Quick Start

### 1. Setup

```bash
cd bitcoin-lab-btc-data-pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API Token

Get your token from [Bitcoin Lab](https://researchbitcoin.net) and set it:

```bash
export BITCOIN_LAB_TOKEN="your-token-here"
```

### 3. Download Data

```bash
# Full historical backfill (first time)
python run.py backfill

# Daily incremental sync (subsequent runs)
python run.py sync

# Check status
python run.py status
```

## Project Structure

```
bitcoin-lab-btc-data-pipeline/
├── config/
│   ├── metrics.yaml       # Metric definitions (endpoints, priorities)
│   └── sync_state.json    # Auto-generated sync state (gitignored)
├── data/
│   └── raw/               # Parquet files per metric (gitignored)
├── logs/
│   └── sync.log           # Sync logs
├── src/
│   └── downloader.py      # Core pipeline code
├── run.py                 # CLI entry point
├── requirements.txt
└── README.md
```

## Available Metrics (53)

| Category | Metrics |
|----------|---------|
| **Valuation** | mvrv, mvrv_z, mvrv_lth, mvrv_sth, nupl, nupl_lth, nupl_sth |
| **Profitability** | sopr, sopr_lth, sopr_sth, supply_in_profit, supply_in_profit_percent |
| **Supply** | supply_lth, supply_sth, supply_lth_sth_ratio, supply_total, supply_active, supply_vaulted |
| **Realized** | realized_cap, realized_price, realized_price_lth, realized_price_sth |
| **Network** | hashrate, difficulty, tx_count, volume_btc, volume_usd |
| **Cointime** | liveliness, vaultedness, coindays_destroyed, asol, dormancy |
| **Fees** | fee_total, fee_total_usd, fee_avg |
| **Other** | nvt, velocity, thermo_cap, investor_cap, true_market_mean_price |

See `config/metrics.yaml` for full list with descriptions.

## Usage

### Loading Data in Python

```python
import pandas as pd
from pathlib import Path

# Load single metric
mvrv = pd.read_parquet("data/raw/mvrv.parquet")

# Load all metrics into one DataFrame
def load_all_metrics():
    data_dir = Path("data/raw")
    dfs = {}
    for f in data_dir.glob("*.parquet"):
        df = pd.read_parquet(f).set_index("time")
        df = df.rename(columns={"value": f.stem})
        dfs[f.stem] = df
    return pd.concat(dfs.values(), axis=1).sort_index()

df = load_all_metrics()
print(df.shape)  # (4024, 53)
```

### Loading with DuckDB

```python
import duckdb

con = duckdb.connect()
df = con.execute("""
    SELECT * FROM 'data/raw/mvrv.parquet'
    WHERE time >= '2020-01-01'
""").df()
```

## API Requirements

- **Tier 2** Bitcoin Lab subscription (or higher)
- Rate limit: 60 requests/minute
- Weekly quota: 40M data points

## Development

```bash
# Run tests
pytest tests/

# Add new metric
# 1. Add to config/metrics.yaml
# 2. Run: python run.py sync
```

## License

MIT

## Acknowledgements

- [Bitcoin Lab](https://researchbitcoin.net) for the on-chain data API
