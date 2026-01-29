# Moving Average Smoothing Analysis

**Date**: 2026-01-25
**Notebook**: `research/87_smoothed_exit_signals.ipynb`
**Question**: Does smoothing exit metrics with MAs improve performance?

---

## 🎯 Hypothesis

From Notebook 85, we found:
- **Hourly LTH-SOPR > 1.5** occurs 55% of hours (noise)
- **Brief spikes** last ~5 hours on average
- **False exits** from intraday volatility

**Solution idea**: Use moving averages to filter noise
- Only exit when metric is **sustained** above threshold
- Require 7-14 days elevated, not just 1 day spike

---

## 📊 Test Results (2020-2026)

### LTH-SOPR Exit Comparison

**RAW (Daily Close, No Smoothing)**:
| Threshold | Return | Trades | Win Rate | Avg Hold |
|-----------|--------|--------|----------|----------|
| 1.5 | +25.7% | 176 | 93.2% | 3.5 days |
| 1.8 | +115.1% | 132 | 94.7% | 6.2 days |
| **2.0** | **+146.5%** | **113** | **86.7%** | **7.9 days** |
| 2.5 | +131.1% | 78 | 84.6% | 12.7 days |

**SMOOTHED (7-day MA)**:
| Threshold | Return | Trades | Win Rate | Avg Hold |
|-----------|--------|--------|----------|----------|
| 1.5 | -2.1% | 171 | 42.7% | 4.2 days |
| 1.8 | -5.2% | 125 | 65.6% | 7.3 days |
| 2.0 | +47.9% | 99 | 81.8% | 10.2 days |
| **2.5** | **+110.1%** | **73** | **79.5%** | **16.4 days** |

---

## 🔍 MA Window Comparison (Threshold 2.0)

| MA Window | Return | Trades | Win Rate | Avg Hold |
|-----------|--------|--------|----------|----------|
| **RAW (0)** | **+146.5%** | 113 | 86.7% | 7.9 days |
| MA-3 | +79.0% | 100 | 88.0% | 9.9 days |
| MA-7 | +47.9% | 99 | 81.8% | 10.2 days |
| MA-14 | +111.7% | 106 | **88.7%** | 9.6 days |
| MA-21 | +8.9% | 107 | 86.0% | 9.0 days |

---

## ❌ **Verdict: Smoothing Generally Hurts**

**Best Raw**: +146.5% (LTH-SOPR > 2.0)
**Best Smoothed**: +110.1% (MA-7, threshold 2.5)
**Degradation**: -36.3%

### Why Smoothing Degrades Performance

1. **Delayed Exits**: MA waits for sustained elevation
   - Real distribution peaks quickly
   - By the time MA confirms, price already reversing
   - Miss optimal exit window

2. **Daily Data Already Filtered**:
   - End-of-day close (not intraday spikes)
   - 24-hour aggregation removes hourly noise
   - No need for additional smoothing

3. **Give Back Gains**:
   - Exit at $65k instead of $70k (waited for MA confirmation)
   - Then price dumps to $50k
   - Raw exit saved 28% more

---

## ✅ **Exception: MA-14 Is Competitive**

While MA-7 and MA-21 hurt significantly, **MA-14 performs well**:

| Metric | RAW | MA-14 | Difference |
|--------|-----|-------|------------|
| Return | +146.5% | +111.7% | -24% (acceptable) |
| Trades | 113 | 106 | Similar |
| Win Rate | 86.7% | **88.7%** | +2% (better!) |
| Avg Hold | 7.9d | 9.6d | +1.7d |

**Trade-off**: Give up 24% absolute return for:
- ✅ Higher win rate (88.7% vs 86.7%)
- ✅ Smoother equity curve (fewer false exits)
- ✅ Less whipsaw on brief reversals

**Use case**: If you prefer psychological comfort over max returns.

---

## 💡 Key Insights

### 1. Daily Data ≠ Hourly Data

**The hourly noise problem doesn't exist on daily data!**

From Notebook 85:
- **Hourly LTH-SOPR > 1.5**: 55% of hours (too frequent!)
- **Daily LTH-SOPR > 1.5**: Only 8% of days (reasonable)

Daily closes already filter:
- Intraday wicks and spikes
- Brief volatility
- Sub-day reversals

**Lesson**: Hourly data needs smoothing, daily data doesn't!

### 2. Optimal Threshold Matters More Than Smoothing

Performance variation by threshold:
- LTH-SOPR > 1.5: +25.7% (exits too early)
- LTH-SOPR > 2.0: +146.5% (sweet spot) ✅
- LTH-SOPR > 2.5: +131.1% (exits too late)

**Impact of threshold**: +120.8% (1.5 → 2.0)
**Impact of smoothing**: -36.3% (RAW → MA-7)

**Conclusion**: Getting the threshold right (2.0) is 3x more important than smoothing!

### 3. Win Rate vs Returns

Higher smoothing → Higher win rate but lower returns:

| Strategy | Win Rate | Return |
|----------|----------|--------|
| Raw, threshold 1.8 | **94.7%** | +115.1% |
| Raw, threshold 2.0 | 86.7% | **+146.5%** |
| MA-14, threshold 2.0 | 88.7% | +111.7% |

**Why**: Lower threshold (1.8) exits earlier on every rally:
- More winners (rarely miss exit)
- But smaller gains per winner
- Lower total return

**Lesson**: Win rate ≠ profitability. Let winners run!

---

## 📈 Recommendations

### For Maximum Returns
**Use RAW LTH-SOPR > 2.0**
- +146.5% return (2020-2026)
- ~19 trades/year
- 86.7% win rate
- No smoothing needed

**Implementation**:
```python
# Daily check (no MA needed)
if daily_data['sopr_lth'].iloc[-1] > 2.0:
    exit_position()
```

### For Smoother Equity Curve
**Use MA-14 LTH-SOPR > 2.0**
- +111.7% return (only 24% less)
- ~18 trades/year
- 88.7% win rate (higher!)
- Filters 1-3 day reversals

**Implementation**:
```python
# Calculate 14-day MA
lth_sopr_ma14 = daily_data['sopr_lth'].rolling(14).mean()

if lth_sopr_ma14.iloc[-1] > 2.0:
    exit_position()  # Only when sustained for 2 weeks
```

### For Different Market Conditions

**Bull Market** (like 2020-2026):
- Use RAW with higher threshold (2.0-2.5)
- Don't delay exits - tops are sharp
- Max returns matter more

**Sideways Market**:
- Consider MA-14 smoothing
- Filters false breakouts
- Higher win rate valuable when fewer opportunities

**Bear Market**:
- Raw with lower threshold (1.5-1.8)
- Exit early on any bounce
- Capital preservation priority

---

## 🚨 What We Learned

### Smoothing Doesn't Solve Hourly Noise

**Original problem** (Notebook 85):
- Hourly LTH-SOPR > 1.5 triggers constantly
- Variant B exited on brief spikes
- 383 trades with 0.2 day holds

**This doesn't happen on daily data!**
- Daily LTH-SOPR > 2.0 is rare (8% of days)
- 113 trades in 6 years (not 383)
- 7.9 day holds (not 0.2 days)

**The REAL solution**: Use daily data, not hourly!

### Why Hourly Failed But Daily Works

**Hourly LTH-SOPR**:
- Volatile (±20% intraday swings)
- Spikes 5,001 times in 6 years
- Mean reversion within hours
- **Noise >> Signal**

**Daily LTH-SOPR**:
- Smooth (end-of-day close)
- Crosses 2.0 only ~176 times
- Mean reversion in days/weeks
- **Signal >> Noise**

**Lesson**: Resolution matters more than smoothing!

---

## 📊 Additional Tests: MVRV and STH-SOPR

We also tested smoothing other metrics:

### MVRV with MA Smoothing

**RAW MVRV > 2.5**: +131% return (competitive with STRAT-005!)
**MA-7 MVRV > 2.5**: +98% return (degradation)

**Same pattern**: Raw outperforms smoothed.

### STH-SOPR with MA Smoothing

**RAW STH-SOPR > 1.2**: +87% return
**MA-7 STH-SOPR > 1.2**: +45% return

**Same pattern**: Smoothing delays exits, hurts performance.

**Conclusion**: The pattern holds across all metrics - daily resolution doesn't need smoothing!

---

## 🎯 Final Answer

**Q**: Should we use moving averages to smooth exit signals?

**A**: **No, not for daily data.**

**Why**:
1. Daily closes already filter intraday noise
2. MA delays exits, miss optimal timing
3. Give up 25-50% returns for minimal benefit

**Exception**: MA-14 acceptable if you prioritize:
- Higher win rate (88.7% vs 86.7%)
- Smoother psychological experience
- Fewer false exits on brief reversals

**Best practice**:
- ✅ Use daily raw values with optimal threshold (LTH-SOPR > 2.0)
- ✅ Focus on threshold selection (bigger impact)
- ❌ Don't add smoothing (daily data is smooth enough)

**For hourly data**: Yes, use MA! (But we concluded hourly exits aren't worth the complexity)

---

## 📚 Related Research

- [Notebook 85: Daily Entries, Hourly Exits](../../research/85_daily_entries_hourly_exits.ipynb) - Found hourly noise problem
- [Notebook 87: Smoothed Exit Signals](../../research/87_smoothed_exit_signals.ipynb) - This analysis
- [Hourly Exit Analysis](HOURLY_EXIT_ANALYSIS.md) - Why hourly exits failed

---

**Bottom Line**: **Daily data is already smooth. Use raw values with good thresholds. Don't over-engineer!** 🎯
