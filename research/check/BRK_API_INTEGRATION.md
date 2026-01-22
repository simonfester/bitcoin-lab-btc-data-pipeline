# Bitcoin Research Kit (BRK) API Integration

## Overview

**BRK** is a FREE, open-source Bitcoin on-chain data API - an alternative to paid services like Bitcoin Lab, Glassnode, etc.

| Feature | Bitcoin Lab API | BRK API |
|---------|----------------|---------|
| **Cost** | Paid subscription | **FREE** |
| **Rate Limits** | 40M DP/week (Tier 2) | **None specified** |
| **Open Source** | No | **Yes (MIT)** |
| **API Format** | REST + Token Auth | REST (no auth needed) |
| **Data Range** | Full history | Full history (2009-present) |

## Base URL

```
https://next.bitview.space
```

## Key Endpoints

### Metric Discovery
```bash
# List all metrics (paginated, 1000/page)
GET /api/metrics/list?page=1

# Search metrics
GET /api/metrics/search/{query}?limit=20

# Get metric info (available indexes)
GET /api/metric/{metric}
```

### Fetch Data
```bash
# Single metric
GET /api/metric/{metric}/{index}?start={n}&end={n}&limit={n}&format=json|csv

# Bulk metrics
GET /api/metrics/bulk?metrics=price_close,sopr,mvrv&index=dateindex
```

### Index Types
| Index | Description |
|-------|-------------|
| `dateindex` | Daily (day number since 2008-01-03) |
| `height` | By block height |
| `weekindex` | Weekly |
| `monthindex` | Monthly |
| `halvingepoch` | By halving period |

## Available Metrics (Mapped to James Check Framework)

### Core SOPR Family
| Metric | BRK Name | Description |
|--------|----------|-------------|
| SOPR | `sopr` | Spent Output Profit Ratio |
| STH-SOPR | `sth_sopr` | Short-term holder SOPR |
| LTH-SOPR | `lth_sopr` | Long-term holder SOPR |
| Adjusted SOPR | `adjusted_sopr` | SOPR adjusted for outputs <1hr |
| SOPR 7d EMA | `sopr_7d_ema` | Smoothed SOPR |

### Core MVRV Family
| Metric | BRK Name | Description |
|--------|----------|-------------|
| MVRV | `mvrv` | Market Value to Realized Value |
| STH-MVRV | `sth_mvrv` | Short-term holder MVRV |
| LTH-MVRV | `lth_mvrv` | Long-term holder MVRV |
| Epoch MVRV | `epoch_N_mvrv` | MVRV by halving epoch |

### NUPL Family
| Metric | BRK Name | Description |
|--------|----------|-------------|
| LTH NUPL | `lth_nupl` | LTH Net Unrealized P/L |
| STH NUPL | `sth_nupl` | STH Net Unrealized P/L |

### Realized Metrics
| Metric | BRK Name | Description |
|--------|----------|-------------|
| Realized Cap | `realized_cap` | Total realized value |
| Realized Price | `realized_price` | Average cost basis |
| STH Realized Price | `sth_realized_price` | STH cost basis |
| LTH Realized Price | `lth_realized_price` | LTH cost basis |
| Net Realized P/L | `net_realized_pnl` | Daily realized P/L |
| Realized Profit | `realized_profit` | Daily profit volume |
| Realized Loss | `realized_loss` | Daily loss volume |

### Supply Metrics
| Metric | BRK Name | Description |
|--------|----------|-------------|
| LTH Supply | `lth_supply` | Long-term holder supply |
| STH Supply | `sth_supply` | Short-term holder supply |
| Supply in Profit | `supply_in_profit` | Coins above cost basis |
| Supply in Loss | `supply_in_loss` | Coins below cost basis |
| LTH Supply in Profit | `lth_supply_in_profit` | LTH coins in profit |
| LTH Supply in Loss | `lth_supply_in_loss` | LTH coins in loss |

### Price Models
| Metric | BRK Name | Description |
|--------|----------|-------------|
| Price | `price_close` | Daily close price |
| Active Price | `active_price` | True market mean |
| Vaulted Price | `vaulted_price` | HODLer euphoria zone |
| 200 DMA | `price_200d_sma` | 200-day moving average |
| 1Y SMA | `price_1y_sma` | 1-year moving average |

### Cost Basis Distribution
| Metric | BRK Name | Description |
|--------|----------|-------------|
| Cost Basis Pct50 | `cost_basis_pct50` | Median holder cost basis |
| Cost Basis Pct95 | `cost_basis_pct95` | 95th percentile cost basis |
| LTH Cost Basis Pct50 | `lth_cost_basis_pct50` | Median LTH cost basis |

## Python Client

```bash
pip install brk-client
```

```python
from brk_client import Client

client = Client("https://next.bitview.space")

# Get SOPR data
sopr = client.metric("sopr", "dateindex")

# Get bulk data
data = client.bulk(["price_close", "sopr", "mvrv"], "dateindex")
```

## Manual Python (No Client)

```python
import requests
import pandas as pd

BASE_URL = "https://next.bitview.space"

def fetch_brk_metric(metric, index="dateindex", start=None, end=None):
    """Fetch a single metric from BRK API."""
    url = f"{BASE_URL}/api/metric/{metric}/{index}"
    params = {}
    if start: params['start'] = start
    if end: params['end'] = end
    
    response = requests.get(url, params=params)
    data = response.json()
    
    # Convert to DataFrame
    # dateindex starts at 2008-01-03 (day 0)
    start_date = pd.Timestamp('2008-01-03')
    df = pd.DataFrame({
        'day': range(data['start'], data['end']),
        'value': data['data']
    })
    df['date'] = start_date + pd.to_timedelta(df['day'], unit='D')
    df = df.set_index('date')
    
    return df[['value']]

# Example usage
sopr = fetch_brk_metric('sopr')
sth_sopr = fetch_brk_metric('sth_sopr')
mvrv = fetch_brk_metric('mvrv')
```

## Integration with Existing Pipeline

Replace Bitcoin Lab API calls with BRK:

```python
# Old (Bitcoin Lab)
# from bitcoin_lab import fetch_metric
# sopr = fetch_metric('sopr', token='xxx')

# New (BRK) - No auth needed!
import requests

def fetch_brk(metric):
    url = f"https://next.bitview.space/api/metric/{metric}/dateindex"
    return requests.get(url).json()['data']

sopr = fetch_brk('sopr')
sth_sopr = fetch_brk('sth_sopr')
mvrv = fetch_brk('mvrv')
```

## Advantages Over Bitcoin Lab API

1. **FREE** - No subscription required
2. **No Rate Limits** - Fetch as much as needed
3. **No Authentication** - Just call the API
4. **Open Source** - Can self-host if needed
5. **LLM Optimized** - Compact API spec at `/api.json`
6. **Multiple Formats** - JSON and CSV output

## Links

- **GitHub**: https://github.com/bitcoinresearchkit/brk
- **Web App**: https://bitview.space
- **API Spec**: https://next.bitview.space/api.json

---

*Added: 2025-01-17*
