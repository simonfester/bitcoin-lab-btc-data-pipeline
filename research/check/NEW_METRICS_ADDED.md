# New Metrics Added - BRK API Integration

## Summary

Added **10 new metrics** to the data loader that were identified as missing from Bitcoin Lab API based on James Check's framework.

## New Metrics Available (from BRK - FREE)

### Sell-side Risk Ratio Family
*Formula: (Realized Profit + Realized Loss) / Realized Cap*
*High = instability/reversal, Low = equilibrium/volatility incoming*

| Metric | BRK Name | Current Value |
|--------|----------|---------------|
| `sell_side_risk` | sell_side_risk_ratio | 0.0368 |
| `sell_side_risk_lth` | lth_sell_side_risk_ratio | 0.0338 |
| `sell_side_risk_sth` | sth_sell_side_risk_ratio | 0.0397 |

### Cointime Economics (Floor Price Models)
| Metric | BRK Name | Current Value |
|--------|----------|---------------|
| `cointime_price` | cointime_price | $51,429 |
| `investor_cap` | investor_cap | $1,038B |
| `thermo_cap` | thermo_cap | $86B |

### Mining
| Metric | BRK Name | Current Value |
|--------|----------|---------------|
| `puell_multiple` | puell_multiple | 0.535 |

### Technical
| Metric | BRK Name | Current Value |
|--------|----------|---------------|
| `price_200d_sma` | price_200d_sma | $105,889 |

### Unrealized P/L
| Metric | BRK Name | Current Value |
|--------|----------|---------------|
| `unrealized_profit` | unrealized_profit | $847B |
| `unrealized_loss` | unrealized_loss | $64B |

## Usage

```python
from src.data_loader import load_data

# Load sell-side risk for volatility analysis
df = load_data(['price', 'sell_side_risk', 'sell_side_risk_lth'])

# Load cointime floor price models
df = load_data(['price', 'cointime_price', 'active_price', 'vaulted_price'])

# Load for 8-metric framework
df = load_data([
    'mvrv_z',        # MVRV Z-Score
    'sopr',          # SOPR
    'puell_multiple', # Mining stress
    'price_200d_sma', # For Mayer Multiple calculation
])
```

## What's Still Missing (Need External Sources)

| Metric | Source | Notes |
|--------|--------|-------|
| `funding_rate` | Glassnode/Exchange APIs | Derivatives sentiment |
| `reserve_risk` | Not found in BRK | May need calculation |
| `mayer_multiple` | Calculate: price / price_200d_sma | Have components |

## James Check 8-Metric Framework Status

| Metric | Status | Source |
|--------|--------|--------|
| MVRV Z-Score | ✓ | BRK: mvrv (calc Z yourself) |
| STH-MVRV Z-Score | ✓ | BRK: sth_mvrv |
| SOPR Z-Score | ✓ | BRK: sopr |
| STH-SOPR Z-Score | ✓ | BRK: sth_sopr |
| Mayer Multiple Z-Score | ⚠️ | Calc: price / price_200d_sma |
| Puell Multiple Z-Score | ✓ | BRK: puell_multiple |
| Reserve Risk Z-Score | ❌ | Not available |
| Funding Rates Z-Score | ❌ | Need Glassnode |

*6/8 metrics available = Usable for cycle detection*

---
*Updated: 2025-01-17*
