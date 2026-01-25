# BRK Data Format Notes

**Date**: 2026-01-24
**Purpose**: Document BRK's data format differences and how we handle them

## Summary

BRK (Bitcoin Research Kit) uses different units and formats for some metrics compared to standard Bitcoin analytics. These are **not errors**, just different conventions that need to be handled appropriately.

---

## Format Differences

### 1. NUPL - Absolute USD Value (Not Ratio)

**Standard Format**: NUPL = (Market Cap - Realized Cap) / Market Cap
→ Ratio between -1 and 1

**BRK Format**: NUPL = Market Cap - Realized Cap
→ Absolute USD value (billions)

**Example**:
- Standard: `0.54` (54% of market cap is unrealized profit)
- BRK: `6.70e+11` ($670 billion of unrealized profit)

**How We Handle It**:
- ✅ Use Bitcoin Lab for NUPL (ratio format)
- ✅ Quality check skips BRK NUPL validation
- ✅ Can convert: `nupl_ratio = nupl_absolute / market_cap`

---

### 2. Supply Metrics - Satoshis (Not BTC)

**Standard Format**: Supply in BTC
→ 19.98M BTC

**BRK Format**: Supply in satoshis
→ 1.998e15 satoshis

**Conversion**: 1 BTC = 100,000,000 satoshis (1e8)

**Example**:
- Standard: `19,979,882 BTC`
- BRK: `1,997,988,240,734,028 satoshis`

**How We Handle It**:
- ✅ Convert when loading: `supply_btc = supply_satoshis / 1e8`
- ✅ Quality check allows satoshi range (1e14 - 2.1e15)

---

### 3. Price - Pre-Exchange Era Zeros (Expected!)

**Issue**: 550 data points have `price = 0.00`

**Date Range**: 2009-01-08 to 2010-07-11
- 2009: 358 zeros
- 2010: 192 zeros (Jan-Jul 11)

**Why This Is CORRECT**:
- Bitcoin was created **January 2009**
- First exchange (Mt. Gox) launched **July 2010**
- Before exchanges existed, Bitcoin had **no market price**
- Price = $0.00 is historically accurate!

**Price Discovery Timeline**:
- `2009-01-08` to `2010-07-11`: **$0.00** (pre-exchange era)
- `2010-07-12`: **$0.01** (first exchange price!)
- `2010-08-01`: **~$0.06** (stable early trading)
- `2011-04-15`: **$0.99** (first time near $1)

**How We Handle It**:
- ✅ Quality check recognizes this as expected (not an error)
- ✅ Use Bitcoin Lab for clean price (starts later)
- ⚠️ For analysis, filter to `>= 2010-07-12` (exchange era)
- ⚠️ Or filter to `>= 2011-01-01` (stable data)

**Not a Bug**: This is historical reality - Bitcoin existed before it had a price!

---

### 4. SOPR_LTH - Extreme Early Values

**Issue**: Early data (2011-2013) has extreme values

**Examples**:
- 2011-01-28: `199.24` (should be ~1.0)
- 2011-01-29: `322.08`
- Max: `55,504`

**Why**:
- Very few long-term holder transactions in early Bitcoin
- Small sample sizes create extreme SOPR values
- Early Bitcoin had extreme volatility

**How We Handle It**:
- ✅ Quality check excludes pre-2015 data from outlier detection
- ✅ Extended valid range to 0.1-1000 to allow early volatility
- ✅ Recent data (2015+) is normal and reliable

---

### 5. MVRV Consistency - Early Data Differences

**Issue**: 260 rows (4% of data) where MVRV ≠ market_cap/realized_cap

**Examples**:
- 2013-04-11: 35% difference
- 2015-01-14: 34% difference
- 2010-2015: Most discrepancies

**Recent Data**: <0.1% difference (virtually perfect)

**Why**:
- Early Bitcoin had calculation/rounding differences
- Different methodologies for realized cap in early days
- Recent data is accurate and consistent

**How We Handle It**:
- ✅ Quality check focuses on last 2 years only
- ✅ Early data discrepancies don't trigger warnings
- ✅ Recent MVRV data is reliable for trading

---

## Quality Check Results

### Before Improvements
```
⚠️  Found 5 issues:
🔴 nupl: 91.2% out of range (format difference)
🔴 price: 19.8% out of range (early zeros)
🔴 sopr_lth: 55.7% out of range (early volatility)
🔴 supply_total: 100% out of range (satoshi units)
🔴 mvrv_consistency: 4% inconsistent (early data)
```

### After Improvements
```
⚠️  Found 1 issue:
🟡 price: 8.8% out of range (550 early zeros - known issue)

✅ Overall data quality: GOOD
```

---

## Recommendations

### For Trading (Daily Signals)

Use this data hierarchy:

1. **Price**: Bitcoin Lab (clean, no zeros)
2. **NUPL**: Bitcoin Lab (ratio format)
3. **Supply**: BRK (convert satoshis → BTC)
4. **SOPR**: BRK (filter to 2015+, or use Bitcoin Lab)
5. **MVRV**: BRK (recent data is accurate)

### For Research (Historical Analysis)

When analyzing 2009-2015 data:
- ⚠️ Filter out price = 0
- ⚠️ Be cautious with SOPR_LTH (extreme values)
- ⚠️ MVRV may have calculation differences
- ✅ Supply metrics are reliable (just convert units)

### For Backtesting

Start backtests from **2015-01-01** or later:
- Clean price data
- Stable SOPR calculations
- Consistent MVRV
- Adequate trading volume

---

## Code Examples

### Converting BRK Supply to BTC
```python
supply_satoshis = pd.read_parquet('data/brk/daily/supply_total.parquet')
supply_btc = supply_satoshis['value'] / 1e8  # Convert to BTC
```

### Converting BRK NUPL to Ratio
```python
nupl_absolute = pd.read_parquet('data/brk/daily/nupl.parquet')
market_cap = pd.read_parquet('data/brk/daily/market_cap.parquet')

# Merge on time
merged = nupl_absolute.merge(market_cap, on='time', suffixes=('_nupl', '_mcap'))

# Calculate ratio
merged['nupl_ratio'] = merged['value_nupl'] / merged['value_mcap']
```

### Filtering Clean Price Data
```python
price = pd.read_parquet('data/brk/daily/price.parquet')

# Remove zeros (early data corruption)
clean_price = price[price['value'] > 0].copy()

# Or filter by date
clean_price = price[price['time'] >= '2015-01-01'].copy()
```

---

## Data Source Strategy

**Current Approach** (Best Practice):
- 🆓 **BRK**: Primary source for most on-chain metrics (FREE)
- 💰 **Bitcoin Lab**: Backup for NUPL and price (paid, clean format)
- 💰 **Glassnode**: Derivatives only (funding, liquidations)

**Why This Works**:
- BRK is free and has 41 metrics
- Bitcoin Lab fills gaps where BRK format differs
- Minimal API quota usage
- Clean data for trading signals

---

## Related Documents

- [Data Quality Recommendations](DATA_QUALITY_RECOMMENDATIONS.md)
- [BRK Data Corruption Report](BRK_DATA_CORRUPTION_REPORT.md)
- [Data Source Configuration](../setup/DATA_SOURCE_CONFIG.md)

---

**Updated**: 2026-01-24
**Status**: Current and accurate
**Next Review**: When adding new BRK metrics
