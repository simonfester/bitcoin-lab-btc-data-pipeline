# Hourly Exit Signals Analysis

**Date**: 2026-01-25
**Notebook**: `research/85_daily_entries_hourly_exits.ipynb`
**Period**: 2020-02-02 → 2026-01-25

---

## 🎯 Objective

Test if using **hourly data for exit signals** (while keeping daily entries) improves STRAT-005 performance.

**Hypothesis**: Hourly exits should catch distribution earlier and improve risk-adjusted returns.

---

## 📊 Results Summary

| Strategy | Return | Trades | Win Rate | Avg Hold | Max DD |
|----------|--------|--------|----------|----------|--------|
| **STRAT-005 Daily** (baseline) | +3,358% | 16 | 93.8% | ~30-60 days | -67.0% |
| **Variant B: LTH-SOPR > 1.5** | +16,936% | 383 | 67.4% | 0.2 days | -28.3% |
| Buy & Hold | +1,200% | 1 | 100% | 6 years | -76.7% |

**Initial reaction**: Variant B shows 5x better returns! 🎉

**After deep analysis**: ⚠️ **Not what it seems...**

---

## 🔍 Deep Dive Analysis

### 1. Trade Pattern Analysis

**Variant B Statistics:**
- 383 trades (24x more than baseline)
- Average hold: **0.2 days (~5 hours)**
- Median hold: 0.0 days (<12 hours)
- Returns distributed (not concentrated in lucky trades)

**Key Finding**: This is **intraday scalping**, not position trading!

---

### 2. LTH-SOPR Hourly Behavior

We analyzed LTH-SOPR > 1.5 threshold:

| Metric | Value |
|--------|-------|
| Occurs | **55.3% of all hours** |
| Spike events | 5,001 |
| Avg spike duration | **5.8 hours** |
| Recent spikes | 1-5 hour duration |

**Verdict**: LTH-SOPR > 1.5 is NOT a rare distribution signal - it's the **normal state**!

The strategy is exiting on brief intraday spikes, not sustained long-term holder distribution.

---

### 3. Threshold Robustness Test

We tested LTH-SOPR thresholds from 1.3 to 3.0:

| Threshold | Hours > | Return | Trades | Interpretation |
|-----------|---------|--------|--------|----------------|
| 1.3 | 65.1% | **+30,769%** | 399 | Lowest bar, highest return |
| 1.4 | 60.1% | +20,490% | 392 | ↓ |
| **1.5** | **55.3%** | **+16,936%** | **383** | **Original** |
| 1.6 | 51.0% | +14,080% | 368 | ↓ |
| 1.8 | 43.2% | +7,254% | 341 | ↓ |
| 2.0 | 36.1% | +4,917% | 327 | ↓ |
| 2.5 | 22.0% | +1,735% | 284 | ↓ |
| 3.0 | 14.4% | +1,419% | 242 | Highest bar, lowest return |

**🚨 CRITICAL FAILURE**: Lower threshold = Higher returns

**This is backwards!** If we were catching real distribution:
- Higher threshold (stronger signal) should = better exits
- What we see: Lower threshold (weaker signal) = better returns

**Conclusion**: Strategy is **overfitting to intraday noise**, not capturing genuine LTH distribution.

---

### 4. Variant C: STH-MVRV > 2.0 (Hourly)

**Result**: Zero trades executed

**Why**: STH-MVRV never exceeded 2.0 during the entire backtest period
- Maximum STH-MVRV: 1.82
- Hours > 1.5: 977 (1.9%)
- Hours > 2.0: **0** (0.0%)

**Lesson**: STH-MVRV threshold of 2.0 was too aggressive for 2020-2026 period.

---

### 5. Max Drawdown Analysis

✅ **This is the ONE real benefit!**

| Strategy | Max Drawdown |
|----------|--------------|
| Buy & Hold | -76.7% |
| STRAT-005 Daily | -67.0% |
| **Variant B (LTH-SOPR 1.5)** | **-28.3%** ✅ |

**Variant B significantly reduces drawdown** from -67% to -28%.

The frequent hourly exits DO help with risk management, even if the return improvement is suspect.

---

### 6. Trade Distribution Validation

**Question**: Is this overfitting to 1-2 lucky trades?

**Answer**: ✅ NO - returns are well-distributed

- Top 10 trades: 20.5% of total returns
- Remaining 373 trades: 79.5% of returns
- Consistent performance across all years (2020-2026)
- Return distribution:
  - 50th percentile: +1.08%
  - 75th percentile: +2.91%
  - 90th percentile: +5.17%

**Verdict**: Strategy is genuinely profitable across hundreds of trades, not lucky flukes.

---

## 💡 What's Actually Happening?

### Theory vs Reality

**What we thought**:
- Hourly LTH-SOPR > 1.5 catches long-term holders distributing
- Exits before major tops
- Improves both returns AND risk

**What's actually happening**:
1. **Intraday mean reversion trading**
   - LTH-SOPR > 1.5 occurs 55% of the time
   - Spikes last ~5 hours on average
   - Strategy exits on brief intraday spikes, not distribution events

2. **High-frequency churn**
   - 383 trades vs 16 for baseline
   - 0.2 day average hold (5 hours)
   - Possibly re-entering same day after exit

3. **Risk reduction, not alpha generation**
   - Max DD improvement (-28% vs -67%) is REAL
   - Return improvement (5x) is likely overfitted to 2020-2026 period
   - Frequent exits prevent some drawdowns

4. **Transaction costs not modeled**
   - 383 trades × 0.1% fee = -0.383% drag
   - 16 trades × 0.1% fee = -0.016% drag
   - **Could significantly reduce alpha**

---

## ⚠️ Red Flags

1. **Threshold robustness failure**
   - Lower threshold = better performance (backwards!)
   - Suggests overfitting to noise, not signal

2. **Signal frequency**
   - LTH-SOPR > 1.5 occurs 55% of the time
   - Not a rare "distribution" event

3. **Hold period**
   - 0.2 days = 5 hours average
   - Not position trading, it's scalping

4. **Transaction costs**
   - 24x more trades than baseline
   - Real-world costs would eat into returns

5. **Different strategy profile**
   - STRAT-005: Position trading, high win rate, patient
   - Variant B: Scalping, lower win rate, rapid

---

## ✅ What Actually Works

Despite the issues, Variant B DOES have one major benefit:

**Risk Reduction**: Max drawdown -28.3% vs -67.0%

The hourly exits prevent holding through some major drawdowns, even if they're not "distribution" signals.

---

## 🎓 Lessons Learned

### 1. Multi-timeframe ≠ Always Better

Just because you CAN use hourly data doesn't mean you SHOULD.

**STRAT-005's genius**: Waiting for DAILY momentum break (Price < 50MA)
- Filters out intraday noise
- High win rate (93.8%)
- Patient position trading

**Hourly exits**: More reactive, but also more noise-sensitive.

### 2. Threshold Robustness is Critical

When testing thresholds:
- Higher (stricter) threshold should = better signal
- Lower (looser) threshold should = more noise

**If backwards**: You're overfitting to noise!

### 3. Signal Frequency Matters

A good exit signal should be:
- **Rare**: Occurs 5-20% of the time
- **Sustained**: Lasts days, not hours
- **Economically meaningful**: LTH-SOPR > 3.0, not 1.5

**LTH-SOPR > 1.5 occurring 55% of the time** = Not a signal, it's noise!

### 4. Different Timeframes = Different Strategies

| Timeframe | Strategy Type | Trade Count | Hold Period | Win Rate |
|-----------|---------------|-------------|-------------|----------|
| **Daily** | Position Trading | 10-20 | 30-60 days | 90%+ |
| **Hourly** | Scalping/Day Trading | 200-400 | 0.2 days | 65-70% |

These are DIFFERENT trading strategies with different:
- Risk profiles
- Transaction costs
- Infrastructure requirements
- Psychological demands

---

## 🚀 Recommendations

### 1. Keep STRAT-005 Daily as Primary Strategy

**Why**:
- Proven 93.8% win rate
- Economic meaning (MVRV > 2 + momentum break)
- Low transaction costs (16 trades)
- Robust threshold behavior

### 2. Use Hourly Data for RISK MANAGEMENT Only

**How**:
- Monitor hourly LTH-SOPR for early warnings
- Don't auto-exit, but **increase vigilance**
- Manual override if hourly confirms daily signal

**Example**:
```
Daily: MVRV approaching 2.0, price near 50MA
Hourly: LTH-SOPR spiking to 2.5+ (sustained 24+ hours)
→ Exit NOW instead of waiting for daily close
```

### 3. If Implementing Hourly Exits

**Requirements**:
1. **Use higher threshold**: LTH-SOPR > 2.5 or 3.0 (not 1.5)
2. **Require sustained signal**: Must stay elevated 24+ hours
3. **Model transaction costs**: Assume 0.1-0.2% per trade
4. **Paper trade first**: Validate with real-time data
5. **Compare apples-to-apples**: Run same backtest period as STRAT-005

### 4. Test Hybrid Approach

**Concept**: Combine daily entries with hourly confirmation

```python
# Daily check first
if daily_mvrv > 2.0 and daily_price < daily_ma50:
    # Then check hourly confirmation
    if hourly_lth_sopr > 2.5 for 24+ hours:
        EXIT
```

This filters out brief intraday spikes while catching real distribution faster.

---

## 📊 Final Verdict

| Aspect | STRAT-005 Daily | Variant B (Hourly) | Winner |
|--------|-----------------|-------------------|--------|
| **Returns (backtest)** | +3,358% | +16,936% | Hourly* |
| **Risk (max DD)** | -67.0% | -28.3% | ✅ Hourly |
| **Trade count** | 16 | 383 | Daily |
| **Win rate** | 93.8% | 67.4% | Daily |
| **Threshold robustness** | ✅ Pass | ❌ Fail | Daily |
| **Economic meaning** | ✅ Clear | ❌ Noise | Daily |
| **Transaction costs** | Minimal | Significant | Daily |
| **Implementation** | Simple | Complex | Daily |

**\* Questionable due to robustness failure**

---

## 🎯 Conclusion

**Initial finding**: Hourly exits show 5x better returns! 🎉

**After analysis**:
- ✅ Hourly exits DO reduce drawdown significantly (-28% vs -67%)
- ❌ Return improvement is likely overfitted to 2020-2026 period
- ❌ Strategy fails threshold robustness test
- ❌ "Signal" occurs 55% of the time (not a signal, it's noise)
- ❌ High transaction costs not modeled

**Final recommendation**:

1. **Keep STRAT-005 Daily as primary strategy** - proven, robust, economically meaningful
2. **Use hourly data for monitoring** - early warning system, not auto-exit
3. **If using hourly exits**: Require LTH-SOPR > 2.5-3.0 sustained for 24+ hours
4. **Test hybrid approach**: Daily signal + hourly confirmation

**The real lesson**:
> "Faster is not always better. STRAT-005's patience (waiting for daily momentum break) is a feature, not a bug. The high win rate comes from filtering out noise, not catching every wiggle."

---

## 📚 Related Research

- [Hourly Exit Signals Guide](HOURLY_EXIT_SIGNALS.md)
- [Strategy Registry](../../research/STRATEGY_REGISTRY.md)
- [Backtest Methodology](BACKTEST_START_DATES.md)
- Notebook: `research/85_daily_entries_hourly_exits.ipynb`

---

**Next Steps**:

1. ✅ Document findings (this file)
2. ⏭️ Test hybrid approach (daily + hourly confirmation)
3. ⏭️ Paper trade hourly exits with transaction costs
4. ⏭️ Compare to STRAT-005 over next 6 months
5. ⏭️ Update STRATEGY_REGISTRY.md with learnings
