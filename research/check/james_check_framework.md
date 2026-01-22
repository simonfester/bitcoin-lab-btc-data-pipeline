# James Check On-Chain Analysis Framework
## Synthesized from Checkonchain Masterclasses → Mapped to Bitcoin Lab API

---

## Core Principle

> "Most onchain metrics are a cross-section of the Bitcoin supply, telling us a story about **who holds it**, **for how long**, and **how profitable they are**."

---

## The Checkonchain Framework (Three Axes)

### Axis 1 (X): Unspent Supply vs Spent Volume
- **Unspent Supply**: Dormant, tells us about existing holders (softer, lagging)
- **Spent Volume**: Active, tells us about decisions being made NOW (actionable, leading)

### Axis 2 (Y): Profit vs Loss
- **Unrealized P/L**: Paper gains/losses → INCENTIVE to act
- **Realized P/L**: Locked-in gains/losses → CONFIRMATION of action
- **Supply/Volume in P/L**: Binary count of coins above/below cost basis

### Axis 3 (Z): Cohorts
- **Long-Term Holders (LTH)**: Coins held >155 days (statistically unlikely to move)
- **Short-Term Holders (STH)**: Coins held <155 days (statistically likely to move)
- **Miners, Exchanges, ETFs**: Explicitly labeled entities

---

## Key Metrics Hierarchy

### 1. Foundation: Cost Basis (Pricestamping)

| Metric | Description | Bitcoin Lab API Endpoint |
|--------|-------------|--------------------------|
| Realized Cap | Total value stored in Bitcoin | `/v2/realizedcap/realized_cap` |
| Realized Price | Avg cost basis per BTC | `/v2/realizedprice/realized_price` |
| LTH Realized Price | Cost basis for LTH cohort | `/v2/realizedprice/realized_price_lth` |
| STH Realized Price | Cost basis for STH cohort | `/v2/realizedprice/realized_price_sth` |
| True Market Mean | Avg cost basis for ACTIVE investors | `/v2/cointime_statistics/true_market_meanprice` |

### 2. Unrealized Profit/Loss (MVRV Family)

| Metric | What It Measures | Threshold Levels | API Endpoint |
|--------|------------------|------------------|--------------|
| MVRV | Avg paper profit multiple (all) | >2.0 = high, <1.0 = capitulation | `/v2/market_value_to_realized_value/mvrv` |
| MVRV Z-Score | Normalized MVRV | Top: +1.5σ, Bottom: -1.0σ | `/v2/market_value_to_realized_value/mvrv_z` |
| LTH-MVRV | Paper profit for HODLers | Macro cycle indicator | `/v2/market_value_to_realized_value/mvrv_lth` |
| **STH-MVRV** ⭐ | Paper profit for recent buyers | =1.0 is pivot (support in bull, resistance in bear) | `/v2/market_value_to_realized_value/mvrv_sth` |
| STH-MVRV Z-Score | Normalized STH-MVRV | Top: +1.25σ, Bottom: -1.0σ | `/v2/market_value_to_realized_value/mvrv_z_52k_window_sth` |
| NUPL | Net Unrealized P/L (% form) | >0.75 = euphoria, <0 = capitulation | `/v2/net_unrealized_profit_loss/net_unrealized_profit_loss` |

### 3. Realized Profit/Loss (SOPR Family)

| Metric | What It Measures | Threshold Levels | API Endpoint |
|--------|------------------|------------------|--------------|
| SOPR | Avg realized profit multiple | >1 = profit, <1 = loss, =1 = breakeven | `/v2/spent_output_profit_ratio/sopr` |
| LTH-SOPR | Realized P/L for HODLers | >10 = extreme top, <1 = capitulation | `/v2/spent_output_profit_ratio/sopr_lth` |
| **STH-SOPR** ⭐ | Realized P/L for recent buyers | Support at 1.0 (bull), Resistance at 1.0 (bear) | `/v2/spent_output_profit_ratio/sopr_sth` |
| Net Realized P/L | USD magnitude of P/L | Spikes at inflection points | `/v2/net_realized_profit_loss/net_realized_profit_loss` |

### 4. Supply Distribution

| Metric | What It Measures | API Endpoint |
|--------|------------------|--------------|
| LTH Supply | Coins held >155 days | `/v2/supply_distribution/supply_lth` |
| STH Supply | Coins held <155 days | `/v2/supply_distribution/supply_sth` |
| LTH/STH Ratio | Balance of conviction | `/v2/supply_distribution/supply_lth_sth_ratio` |
| Supply in Profit | Coins above cost basis | `/v2/supply_in_profitloss/supply_in_profit` |
| Supply in Loss | Coins below cost basis | `/v2/supply_in_profitloss/supply_in_loss` |
| STH Supply in Loss | Recent buyers underwater | `/v2/supply_in_profitloss/supply_in_loss_sth` |

### 5. Cointime Economics (Adjusted for Lost/Dormant Coins)

| Metric | What It Measures | API Endpoint |
|--------|------------------|--------------|
| True Market Mean | Fair value for active investors | `/v2/cointime_statistics/true_market_meanprice` |
| Cointime Price | Floor model (bear market low) | `/v2/cointime_statistics/cointime_price` |
| Vaulted Price | Euphoria zone (HODLer sell-side starts) | `/v2/cointime_statistics/vaulted_realized_price` |
| Active MVRV | MVRV adjusted for active supply | `/v2/cointime_statistics/active_mvrv` |
| AVIV (NUPL) | NUPL for active investors | `/v2/cointime_statistics/aviv_nupl` |
| Liveliness | Economic activity ratio | `/v2/cointime_statistics/liveliness` |

### 6. Dormancy & Coin Age

| Metric | What It Measures | API Endpoint |
|--------|------------------|--------------|
| Coindays Destroyed | Volume × holding time spent | `/v2/utxo_dormancy/coindays_destroyed` |
| CDD by LTH | Old coins moving | `/v2/utxo_dormancy/coindays_destroyed_lth` |
| Dormancy | Avg age of spent coins | `/v2/utxo_dormancy/dormancy_raw` |

---

## Price Model Framework

### Floor Models (Bear Market Lows)
```
Cointime Price < Delta Price < Balanced Price < Realized Price
```
- **Cointime Price** (preferred): HODLer activity vs dormancy
- Historically touched only in late-stage bear markets

### Mean Reversion Models (Gravitational Center)
```
Realized Price < True Market Mean < STH Cost Basis
```
- **True Market Mean** (preferred): The actual middle of the market
- MVRV around True Market Mean has mean & median of ~1.0

### Euphoria Models (Bull Market Tops)
```
Vaulted Price < MVRV +1σ Band < MVRV +2σ Band
```
- **Vaulted Price**: Where HODLer profit-taking ramps up
- MVRV bands: Statistical overextension levels

---

## Trading Signals Framework

### Bull Market Buy-the-Dip Checklist
| Signal | Condition | Weight |
|--------|-----------|--------|
| STH-MVRV | < 1.0 (STHs underwater) | Required |
| STH-SOPR | < 1.0 (top buyers capitulating) | Required |
| STH-RPLR | < 0 (losses > profits) | Confirming |
| Funding Rates | Cooled off or negative | Confirming |
| Long Liquidations | Spike then short squeeze | Confirming |

### Bear Market Accumulation Signals
| Signal | Condition | Interpretation |
|--------|-----------|----------------|
| MVRV | < 1.0 | Market-wide capitulation |
| LTH-SOPR | < 1.0 | First-cycle HODLers capitulating |
| Price | Below True Market Mean | Deep value zone |
| STH-SOPR | Divergence (rising while price flat/down) | Seller exhaustion |

### Cycle Top Warning Signals (8-Metric Framework from Masterclass #19)
| Metric | Top Threshold | Bottom Threshold |
|--------|---------------|------------------|
| MVRV Z-Score | > +1.5σ | < -1.0σ |
| STH-MVRV Z-Score | > +1.25σ | < -1.0σ |
| SOPR Z-Score | > +1.5σ | < -1.0σ |
| STH-SOPR Z-Score | > +1.0σ | < -1.0σ |
| Mayer Multiple Z-Score | > +1.0σ | < -1.0σ |
| Puell Multiple Z-Score | > +1.5σ | < -1.0σ |
| Reserve Risk Z-Score | > +1.5σ | < -1.0σ |
| Funding Rates 1yr Z-Score | > +1.5σ | < -1.0σ |

**Interpretation:**
- 4/8 metrics flashing = Caution
- 6/8 metrics flashing = High risk zone

---

## Sell-side Risk Ratio

```
Sell-side Risk Ratio = (Realized Profit + Realized Loss) / Realized Cap
```

| Value | Interpretation |
|-------|----------------|
| High | Market instability, trend exhaustion, expect reversal |
| Low | Equilibrium reached, volatility incoming |

**Key Insight**: Correlates strongly with options implied volatility - can be used as "expected volatility" gauge.

---

## The Swiss Army Knife Metrics

James Check's daily analysis toolkit (in order of importance):

1. **STH-MVRV** - Unrealized P/L for recent buyers
2. **STH-SOPR** - Realized P/L for recent buyers  
3. **Funding Rates** - Leverage sentiment (not in Bitcoin Lab API - use Glassnode/exchange data)

> "If I could only take two Bitcoin metrics with me, it would be STH-MVRV and STH-SOPR. They are the bread and butter of my dip buying strategy."

---

## Data Download Priority for Bitcoin Lab API

### Tier 1: Critical (Always Current)
```
price
market_cap
realized_cap
realized_price
realized_price_sth
mvrv
mvrv_sth
sopr
sopr_sth
```

### Tier 2: Core Framework
```
realized_price_lth
mvrv_lth
mvrv_z
sopr_lth
net_realized_profit_loss
net_unrealized_profit_loss
supply_lth
supply_sth
supply_in_profit
supply_in_loss
```

### Tier 3: Cointime Economics
```
true_market_meanprice
cointime_price
vaulted_realized_price
active_mvrv
aviv_nupl
liveliness
```

### Tier 4: Supporting Metrics
```
coindays_destroyed
dormancy_raw
supply_in_loss_sth
supply_in_profit_sth
net_realized_profit_loss_sth
net_realized_profit_loss_lth
```

---

## Key Behavioral Insights

1. **Every buyer is matched with a seller** - Profit taking = capital inflows
2. **A little profit is good, too much creates sellers** - Monitor magnitude
3. **Bottoms form when HODLers remain, tops form when speculators saturate**
4. **The shot across the bow** - First major sell-off after bull peak shatters confidence
5. **Divergences matter** - Price vs MVRV divergence signals saturation
6. **155 days is data-driven** - Not arbitrary, based on spend probability analysis

---

## Implementation Notes for Trading System

### Signal Generation Approach
1. **Not for discovery** - Use signals as confirmation, not discovery tools
2. **Backtest as confirmation** - Test whether signals have predictive power first
3. **Daily resolution** - All metrics work well at daily timeframe
4. **Z-Score everything** - Normalize for cross-cycle comparison
5. **Cohort focus** - STH metrics for tactical, LTH metrics for strategic

### Recommended Statistical Tests Before Backtesting
- Autocorrelation analysis of returns following signal
- Regression of forward returns on signal values
- Parameter stability across bull/bear regimes
- Out-of-sample validation across cycles

### Integration with Other Data Sources
- **Glassnode**: Funding rates, exchange flows, ETF data
- **Coinbase Portfolio**: Position sizing, execution
- **Derivatives data**: Confirmation via funding, open interest

---

*Framework synthesized from James Check's Checkonchain Masterclasses #1-21*
*Mapped to Bitcoin Lab API v2 endpoints*
