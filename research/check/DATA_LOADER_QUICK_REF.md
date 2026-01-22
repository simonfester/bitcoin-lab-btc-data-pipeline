# Unified Data Loader - Quick Reference

## Overview

The unified data loader supports **3 data sources** with automatic fallback:

| Source | Auth | Cost | Rate Limit | Best For |
|--------|------|------|------------|----------|
| **BRK** | None | FREE | None | Research, backtesting |
| **Bitcoin Lab** | Token | Paid | 40M DP/week | Production |
| **Local Cache** | None | FREE | None | Offline, speed |

## Quick Commands

```bash
# Check current strategy signals (from BRK - FREE)
python run.py signals

# Load specific metrics
python run.py data-load price,sopr_sth,mvrv

# Refresh local cache from BRK (FREE)
python run.py data-refresh

# Check cache freshness
python run.py data
```

## Python Usage

```python
from src.data_loader import DataLoader, load_data, print_signals

# Quick load (uses BRK by default)
df = load_data(['price', 'sopr_sth', 'mvrv'])

# Full control
loader = DataLoader(preferred_source='brk')
df = loader.load(['price', 'sopr_sth', 'sopr_lth', 'mvrv'], start_date='2020-01-01')

# Check signals
print_signals()  # Prints formatted STRAT-003 and Checkmate status
```

## Available Metrics

### Core (James Check Framework)
| Standard Name | BRK API | Bitcoin Lab |
|--------------|---------|-------------|
| `price` | price_close | market/price_usd_close |
| `sopr` | sopr | indicators/sopr |
| `sopr_sth` | sth_sopr | indicators/sopr_less_155 |
| `sopr_lth` | lth_sopr | indicators/sopr_more_155 |
| `mvrv` | mvrv | indicators/mvrv |
| `mvrv_sth` | sth_mvrv | indicators/mvrv_less_155 |
| `mvrv_lth` | lth_mvrv | indicators/mvrv_more_155 |
| `nupl` | nupl | indicators/nupl |
| `nupl_lth` | lth_nupl | indicators/nupl_more_155 |
| `nupl_sth` | sth_nupl | indicators/nupl_less_155 |

### Realized Metrics
| Standard Name | BRK API | Bitcoin Lab |
|--------------|---------|-------------|
| `realized_cap` | realized_cap | indicators/realized_cap |
| `realized_price` | realized_price | indicators/realized_price |
| `realized_price_sth` | sth_realized_price | indicators/realized_price_less_155 |
| `realized_price_lth` | lth_realized_price | indicators/realized_price_more_155 |

### Cointime Economics
| Standard Name | BRK API | Bitcoin Lab |
|--------------|---------|-------------|
| `active_price` | active_price | indicators/true_market_mean |
| `vaulted_price` | vaulted_price | indicators/vaulted_price |
| `aviv` | aviv | indicators/aviv_ratio |
| `liveliness` | liveliness | indicators/liveliness |

## Aliases

These names are interchangeable:
- `sth_sopr` ↔ `sopr_sth`
- `lth_sopr` ↔ `sopr_lth`
- `sth_mvrv` ↔ `mvrv_sth`
- `lth_mvrv` ↔ `mvrv_lth`
- `true_market_mean` ↔ `active_price`

## Strategy Signal Checker

```python
from src.data_loader import StrategySignalChecker

checker = StrategySignalChecker()
signals = checker.check_signals()

# Returns:
{
    'date': datetime.date(2025, 1, 11),
    'current_state': {
        'price': 95405,
        'sopr_sth': 1.0045,
        'mvrv': 1.695,
        ...
    },
    'strat003': {
        'entry_signal': False,
        'exit_trigger': False,
    },
    'checkmate': {
        'signal': 0.29,
        'interpretation': 'Neutral-Bearish',
        'recommended_size': 0.35,
    }
}
```

## BRK API Details

**Base URL:** `https://next.bitview.space`

**Endpoint Format:**
```
GET /api/metric/{metric}/dateindex
```

**Response Format:**
```json
{
  "version": 18,
  "total": 6219,
  "start": 0,
  "end": 6219,
  "data": [0.0, 0.0, 1.02, ...]
}
```

**Date Calculation:**
```python
# Day 0 = 2008-01-03
date = datetime(2008, 1, 3) + timedelta(days=index)
```

## Files

- `src/data_loader.py` - Main module
- `research/check/BRK_API_INTEGRATION.md` - Full BRK documentation
- `research/check/james_check_framework.md` - James Check metric guide

---
*Last updated: 2025-01-17*
