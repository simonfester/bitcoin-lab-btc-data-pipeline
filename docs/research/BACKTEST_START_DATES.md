# Backtest Start Date Recommendations

**Last Updated**: 2026-01-25

## TL;DR - Recommended Start Dates

| Use Case | Start Date | Data Points | Why |
|----------|-----------|-------------|-----|
| **🏆 Recommended** | **2015-01-01** | **4,043 (~11 yrs)** | **Cleanest data, all metrics stable** |
| ⚖️ Balanced | 2011-01-18 | 5,487 (~15 yrs) | All metrics available (inc. LTH-SOPR) |
| 🚀 Aggressive | 2010-08-16 | 5,642 (~15.4 yrs) | Maximum history (missing LTH-SOPR initially) |

**For your strategies**: Use **2015-01-01** or **2011-01-18**

---

## Metric Availability Timeline

### Critical Metrics for Your Strategies

| Metric | First Data | First Clean | Notes |
|--------|-----------|-------------|-------|
| **Price** | 2009-01-08 | **2010-07-12** | 550 zeros before Mt. Gox exchange |
| **SOPR** | 2010-08-16 | 2010-08-16 | Clean from start |
| **STH-SOPR** | 2010-08-16 | 2010-08-16 | Clean from start |
| **LTH-SOPR** | **2011-01-18** | **2011-01-18** | ⚠️ Latest critical metric |
| **MVRV** | 2009-01-09 | 2009-01-09 | Clean from start |
| **STH-MVRV** | 2009-01-09 | 2009-01-09 | Clean from start |
| **LTH-MVRV** | 2009-06-08 | 2009-06-08 | Clean from start |
| **NUPL** | 2009-01-08 | 2010-07-12 | Matches price (needs market cap) |
| **Supply LTH** | 2009-01-08 | 2009-06-08 | 151 zeros initially |
| **Supply STH** | 2009-01-08 | 2009-01-09 | 1 zero initially |
| **Puell Multiple** | 2010-08-16 | 2010-08-16 | Clean from start |
| **Realized Cap** | 2009-01-08 | 2010-08-16 | 585 zeros initially |

**Bottleneck**: LTH-SOPR starts **2011-01-18** (required for your exit signals!)

---

## Detailed Analysis by Date

### 2010-07-12: First Exchange Price
- **Data**: 5,677 points (~15.5 years)
- **What's Available**: Price, MVRV, basic metrics
- **Missing**: SOPR (all cohorts), Realized Cap, Puell Multiple
- **Use For**: Historical research only
- **❌ Not Recommended**: Too many missing metrics

### 2010-08-16: SOPR Era Begins
- **Data**: 5,642 points (~15.4 years)
- **What's Available**: Price, SOPR, STH-SOPR, MVRV, Puell, Realized Cap
- **Missing**: LTH-SOPR (until 2011-01-18)
- **Use For**: Strategies that don't need LTH-SOPR
- **⚠️ Limited**: Missing key exit signal (LTH-SOPR > 1.5)

### 2011-01-01: Clean Stable Data
- **Data**: 5,504 points (~15.1 years)
- **What's Available**: All metrics
- **Missing**: Nothing (LTH-SOPR starts 18 days later)
- **Use For**: Good compromise
- **✅ Good**: Clean, nearly all history

### 2011-01-18: ALL Metrics Available
- **Data**: 5,487 points (~15.0 years)
- **What's Available**: **EVERY metric** including LTH-SOPR
- **Missing**: Nothing!
- **Use For**: Maximum history with complete data
- **✅ Balanced**: 15 years of clean, complete data

### 2012-01-01: First Full Trading Year
- **Data**: 5,139 points (~14.1 years)
- **What's Available**: All metrics, stable trading
- **Missing**: Early 2011 volatility context
- **Use For**: Conservative approach
- **✅ Clean**: Very stable data

### 2013-01-01: Post First Halving
- **Data**: 4,773 points (~13.1 years)
- **What's Available**: All metrics, mature market
- **Missing**: 2011-2012 early adoption phase
- **Use For**: Focus on halving cycles
- **✅ Clean**: Full halving cycle data

### 2015-01-01: Research Standard
- **Data**: 4,043 points (~11.1 years)
- **What's Available**: All metrics, very mature market
- **Missing**: Early Bitcoin history
- **Use For**: **Academic rigor, cleanest backtests**
- **✅ Recommended**: No early-era quirks, 11 years still excellent

---

## Why These Dates Matter

### Bitcoin's Historical Phases

| Period | Characteristics | Data Quality |
|--------|-----------------|--------------|
| **2009-2010** | Genesis, no exchanges | Price = $0, sparse data |
| **2010-2011** | First exchanges, price discovery | Emerging metrics |
| **2011-2013** | Early adoption, volatility | All metrics available |
| **2013-2015** | First bubble, crashes | Mature metrics |
| **2015+** | Established market | Very clean, stable |

### Data Issues by Period

**Pre-2010-07-12** (Genesis Era):
- ❌ No exchange price
- ❌ No realized cap (depends on price)
- ❌ No NUPL (depends on market cap)
- ⚠️ Sparse on-chain activity

**2010-07-12 to 2010-08-16** (Early Exchange):
- ✅ Price available ($0.01 - $0.10)
- ❌ No SOPR yet
- ❌ No Puell Multiple
- ⚠️ Low liquidity, high volatility

**2010-08-16 to 2011-01-18** (SOPR Era):
- ✅ Price, SOPR, STH-SOPR
- ❌ No LTH-SOPR (not enough aged coins)
- ⚠️ Extreme volatility (SOPR ranges 0.1-1000x)

**2011-01-18+** (Complete Data):
- ✅ All metrics available
- ✅ Stable calculations
- ⚠️ Still high volatility (2011 bubble to $31)

**2015-01-01+** (Mature Market):
- ✅ All metrics clean and stable
- ✅ Established market patterns
- ✅ Reliable for backtesting

---

## Your Strategy Requirements

Based on `scripts/calculate.py`, your strategies use:

### Entry Signals
- ✅ **SOPR < 1** (available from 2010-08-16)
- ✅ **STH-SOPR < 1** (available from 2010-08-16)
- ✅ **STH-MVRV < 1** (available from 2009-01-09)
- ✅ Realized Loss (available from 2010-08-16)

### Exit Signals
- ⚠️ **LTH-SOPR > 1.5** (available from **2011-01-18**)
- ✅ **MVRV-Z > 2.5** (available from 2010-08-16)

### Buy The Dip (5 conditions)
- ✅ **STH-MVRV < 1** (available from 2009-01-09)
- ✅ **STH-SOPR < 1** (available from 2010-08-16)
- ✅ Realized P/L Ratio < 1 (available from 2010-08-16)
- ✅ Funding rates ≤ 0 (available from Glassnode)
- ✅ Liquidations (available from Glassnode)

**Critical Bottleneck**: LTH-SOPR (exit signal) → minimum start date **2011-01-18**

---

## Recommendations by Goal

### 🏆 Best Overall: 2015-01-01
**Why**:
- ✅ Cleanest data (no early-era quirks)
- ✅ All metrics mature and stable
- ✅ 11 years is plenty for robust backtesting
- ✅ Covers 2 full halving cycles (2016, 2020)
- ✅ Industry standard for research

**Use When**:
- You want the most reliable results
- Publishing research or sharing findings
- Conservative risk assessment
- Avoiding any data quality concerns

**Trade-offs**:
- Misses early Bitcoin history (2011-2014)
- Fewer data points (still 4,043!)

---

### ⚖️ Balanced: 2011-01-18
**Why**:
- ✅ All metrics available (including LTH-SOPR)
- ✅ Maximum useful history (~15 years)
- ✅ Includes 2011-2013 early adoption phase
- ⚠️ Accept some early volatility/noise

**Use When**:
- You want maximum history
- You understand early Bitcoin was volatile
- You'll filter outliers anyway
- Testing long-term patterns

**Trade-offs**:
- Early 2011 has extreme SOPR values
- 2011 bubble ($31) may skew results
- Some metrics have calculation quirks

---

### 🚀 Aggressive: 2010-08-16
**Why**:
- ✅ Maximum possible history with SOPR
- ✅ Captures very early price discovery
- ❌ Missing LTH-SOPR until 2011-01-18

**Use When**:
- You don't use LTH-SOPR exit signals
- Research on SOPR/STH-SOPR only
- Very long-term pattern analysis

**Trade-offs**:
- Can't use LTH-SOPR strategies
- Extreme early volatility
- Sparse liquidity

---

## Practical Filtering Code

### Option 1: Conservative (2015-01-01)
```python
# Most reliable, cleanest data
df = df[df['time'] >= '2015-01-01'].copy()
print(f"Data points: {len(df):,} (~{len(df)/365:.1f} years)")
```

### Option 2: Balanced (2011-01-18)
```python
# All metrics available, good history
df = df[df['time'] >= '2011-01-18'].copy()
print(f"Data points: {len(df):,} (~{len(df)/365:.1f} years)")
```

### Option 3: Custom Filter
```python
# Define your own cutoff
START_DATE = '2015-01-01'  # Change as needed
df = df[df['time'] >= START_DATE].copy()

# Verify all critical metrics exist
required_metrics = ['price', 'sopr', 'sopr_sth', 'sopr_lth', 'mvrv']
for metric in required_metrics:
    assert metric in df.columns, f"Missing {metric}!"
    assert df[metric].notna().any(), f"{metric} all null!"
```

---

## Testing Different Start Dates

To see how your strategy performs across different periods:

```python
# Test multiple start dates
start_dates = ['2010-08-16', '2011-01-18', '2012-01-01', '2015-01-01']

for start_date in start_dates:
    df_test = df[df['time'] >= start_date].copy()

    # Run your strategy
    results = backtest_strategy(df_test)

    print(f"\n{start_date}: {len(df_test):,} points")
    print(f"  Total Return: {results['total_return']:.1f}%")
    print(f"  Sharpe Ratio: {results['sharpe']:.2f}")
    print(f"  Max Drawdown: {results['max_dd']:.1f}%")
```

**Compare results** to see if early data changes outcomes significantly.

---

## Summary Table

| Start Date | Years | All Metrics? | Data Quality | Best For |
|------------|-------|--------------|--------------|----------|
| 2010-07-12 | 15.5 | ❌ No | ⚠️ Sparse | Historical research |
| 2010-08-16 | 15.4 | ❌ No LTH-SOPR | ⚠️ Volatile | Maximum SOPR history |
| 2011-01-01 | 15.1 | ✅ Yes | ✅ Good | Good compromise |
| **2011-01-18** | **15.0** | **✅ Yes** | **✅ Good** | **Maximum complete history** |
| 2012-01-01 | 14.1 | ✅ Yes | ✅ Very Good | Conservative |
| 2013-01-01 | 13.1 | ✅ Yes | ✅ Very Good | Post-halving focus |
| **2015-01-01** | **11.1** | **✅ Yes** | **✅ Excellent** | **🏆 Recommended** |

---

## Final Recommendation

**For your trading strategies**: Start from **2015-01-01**

**Why**:
1. ✅ All metrics available and stable
2. ✅ No data quality concerns
3. ✅ 11 years = excellent statistical significance
4. ✅ Covers 2 full halving cycles
5. ✅ Industry-standard research cutoff
6. ✅ Results will be defensible and reliable

**Alternative**: Use **2011-01-18** if you need maximum history and are comfortable with early Bitcoin volatility.

---

**Related Docs**:
- [BRK Data Format Notes](../archive/BRK_DATA_FORMAT_NOTES.md)
- [Strategy Framework](STRATEGY_FRAMEWORK.md)
- [Research Principles](RESEARCH_PRINCIPLES.md)
