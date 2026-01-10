# Bitcoin Signal Research: Lessons Learned

A living document capturing insights from our signal research and backtesting.

---

## 📚 Key Principles

### 1. Statistical Significance ≠ Trading Edge

| What Regression Shows | What It Doesn't Show |
|----------------------|---------------------|
| Direction of relationship | Optimal entry timing |
| Statistical significance (p-value) | Economic significance (profitability) |
| Average effect over time | Actual trade-by-trade results |
| R² (variance explained) | Whether you can beat buy & hold |

**Lesson:** A metric can be highly statistically significant (p < 0.001) but still not generate alpha. The relationship needs to be strong enough to overcome:
- Trading costs (fees, slippage)
- Timing imprecision
- Opportunity cost of being out of the market

### 2. In-Sample vs Out-of-Sample

**In-sample performance is meaningless.** Always use walk-forward validation:

```
For each period:
  1. TRAIN: Find optimal parameters on past data
  2. TEST: Apply to future (unseen) data
  3. Measure: Did it beat buy & hold?
```

**Key metric:** `Beat Buy & Hold %` should be >50%

### 3. Regime Changes Matter

Coefficients can flip between market cycles:

| Cycle | MVRV Coefficient | Direction |
|-------|-----------------|-----------|
| 2015-2017 | +0.086 | High = Good |
| 2020-2021 | -0.043 | High = Bad |
| 2024+ | -0.073 | High = Bad |

**Lesson:** Always test cycle-by-cycle consistency. Require 60%+ sign consistency.

### 4. Smoothness Indicates Robustness

A "smooth" Sharpe curve across thresholds = robust signal
A "spiky" Sharpe curve = overfit to specific threshold

```
Smoothness = std(sharpe_diffs) / mean(|sharpe|)
Target: < 0.5
```

### 5. Good Entry ≠ Good Trade

A signal can identify excellent entry points but still lose money if:
- The broader trend is against you (catching falling knives)
- Exit strategy is wrong (exiting too early or too late)
- Position sizing is off

**Lesson:** Entry signals need proper EXIT STRATEGIES (but not always filters - see #7).

### 6. Asymmetric Returns Can Overcome Low Win Rate

You don't need to win often if your winners are much bigger than losers:

```
Win Rate: 44%
Avg Win: +39%
Avg Loss: -6%
Risk/Reward: 6:1
Profit Factor: 4.85

Still profitable despite losing more than half the trades!
```

**Lesson:** Focus on Profit Factor (gross wins / gross losses) not just win rate.

### 7. Contrarian Signals DON'T Need Momentum Filters

**Counterintuitive finding:** Adding momentum filters to SOPR capitulation signal made results WORSE.

| Filter | Total Return | Win Rate |
|--------|-------------|----------|
| **No Filter** | **5,558%** | 44% |
| Price > 200 MA | 158% | 35% |
| Price > 50 AND 50>200 | -20% | 27% |

**Why?** The best capitulation entries happen when price is BELOW moving averages:
- March 2020 COVID crash - price below ALL MAs, but best buy in years
- Late 2022 bottom - price below 200 MA, perfect entry
- Every major bottom - happens in downtrends, not uptrends

**Lesson:** Contrarian signals (buying fear/capitulation) are SUPPOSED to fire in downtrends. Adding a trend filter removes the best trades. The trailing stop already protects against extended losses.

**When to use momentum filters:**
- ✅ Trend-following signals (breakouts, momentum strategies)
- ❌ Contrarian signals (capitulation, fear-based entries)

### 8. Match Exit Type to Entry Type

**Discovery:** Contrarian entry should have valuation-based exit!

| Entry Type | Exit Type | Beat Rate |
|------------|-----------|-----------|
| SOPR < 1 (fear) | Trailing stop (price-based) | 54% |
| SOPR < 1 (fear) | SOPR > 1.02 (greed) | 54% |
| SOPR < 1 (fear) | **MVRV-triggered trail** | **62%** |

**Why MVRV works better:**
- SOPR measures short-term sentiment (noisy, mean-reverts quickly)
- MVRV measures fundamental valuation (stable, marks cycle extremes)
- Entry on sentiment extreme + Exit on valuation extreme = Full cycle capture

**Lesson:** Don't just optimize exit parameters - fundamentally match exit TYPE to entry TYPE.

### 9. Beat Rate vs Avg Excess Can Diverge

**Observation:** MVRV strategy has 62% beat rate but -7.1% avg excess return.

**Why?**
- We win 62% of periods (more frequent small wins)
- But when we lose, we lose big (miss parabolic runs)
- Total wins > total losses in COUNT but not in MAGNITUDE

**Implication:**
- Beat rate = consistency (how often you win)
- Avg excess = magnitude (how much you win/lose)
- Both matter, but beat rate is better for confidence/psychology

**Lesson:** A strategy can be reliably better than B&H (high beat rate) while still underperforming in total return (negative excess). Choose based on your goals.

### 10. Use On-Chain Metrics to TRIGGER, Not Hard Exit ⭐ NEW

**Problem discovered:** MVRV > 3.0 as hard exit only triggered 2 times in 7 years!

| Exit Reason | Count | What Actually Happened |
|-------------|-------|------------------------|
| MVRV Exit | 2 | Signal rarely fires |
| Stop Loss | 5 | This was doing the work |
| Max Hold | 3 | Timed out |

**Solution:** Use MVRV to ACTIVATE a trailing stop, not as a hard exit.

| Approach | How It Works | Result |
|----------|--------------|--------|
| MVRV > 3.0 hard exit | Exit immediately when hit | Rarely fires |
| **MVRV > 2.25 → trail** | Activate 20% trail when hit | Actually uses the signal! |

**Why this works:**
- MVRV > 2.25 fires more often (market getting expensive)
- Trailing stop lets you ride the remaining upside
- Locks in gains when price drops 20% from peak
- Best of both worlds: on-chain trigger + price protection

**Lesson:** On-chain metrics often work better as TRIGGERS than hard exits. Let price action determine exact exit timing.

### 11. Grid Search Confirms Robustness ⭐ NEW

**Finding:** 32 out of 35 MVRV + trailing configs beat baseline!

| MVRV Triggers Tested | Trail % Tested | Total Combos |
|---------------------|----------------|--------------|
| 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0 | 10%, 15%, 20%, 25%, 30% | 35 |

**Pattern Analysis:**
| Parameter | Best on Average | Why |
|-----------|-----------------|-----|
| MVRV Trigger | > 2.75 | More consistent across trail % |
| Trail % | 30% | More forgiving, catches more upside |
| Single Best | > 2.25 + 20% | Optimal balance |

**Lesson:** When 91% of nearby configurations also work, you have a robust strategy, not an overfit one. This is the holy grail of backtesting.

---

## 🔬 Tested Signals

### ❌ Liveliness (as Trading Signal)

**Hypothesis:** Buy when liveliness < threshold (dormant coins = HODLers accumulating)

**Results:**
| Metric | Value |
|--------|-------|
| Statistical significance | ✅ p < 0.001 |
| Cycle consistency | ✅ 4/5 cycles (80%) |
| Sharpe smoothness | ✅ 0.13 (smooth) |
| **Beat Buy & Hold** | ❌ 12.5% of periods |

**Conclusion:** Statistically significant but not tradeable.

**Better use:** Regime indicator / filter for other signals.

---

### ✅ SOPR Double Capitulation + Trailing Stop (v1)

**Signal:** Buy when SOPR < 1 AND STH SOPR < 1

**Exit Strategy:** Trailing stop (8% stop loss, 12% trail, activates at 5% profit)

**Results:**
| Metric | Value |
|--------|-------|
| Walk-Forward Beat B&H | 54% |
| Profit Factor | 4.85 |

**Verdict:** Usable but marginal. Baseline for comparison.

---

### ✅✅ SOPR + MVRV-Triggered Trailing Stop (v2) ⭐ FINAL STRATEGY

**Signal:** Buy when SOPR < 1 AND STH SOPR < 1

**Exit Strategy:** 
- When MVRV > 2.25 → activate 20% trailing stop from peak
- Before MVRV triggers → 20% stop loss protection
- Max hold: 365 days

**Results:**
| Metric | Value |
|--------|-------|
| Walk-Forward Beat B&H | **62%** |
| Avg Excess Return | -7.1% |
| Robustness | 32/35 configs beat baseline |

**Why It's Better Than v1:**
- Uses on-chain valuation (MVRV) to time exit regime
- Trailing stop lets profits run after MVRV triggers
- More exits from the actual signal, fewer from stop loss

**Exit Breakdown (v2):**
| Exit Type | What It Means |
|-----------|---------------|
| MVRV Trail | Valuation elevated → trail activated → locked in gains |
| Stop Loss | Bear market entry → protected from further losses |
| Max Hold | Sideways market → timed out |

---

## 📊 Metrics by Use Case

### Trading Signals (Entry)
- **SOPR < 1 + STH SOPR < 1** - Double capitulation ✅ WORKS

### Trading Signals (Exit Triggers)
- **MVRV > 2.25** - Activates trailing stop ✅ WORKS
- MVRV > 2.75 - More conservative trigger
- NUPL > 0.75 - Alternative euphoria signal

### Regime Indicators (Filters)
- **Liveliness** - low = accumulation phase
- **Vaultedness** - high = coins locked away
- **LTH/STH ratio** - high = strong hands dominating

### Confirmation Indicators
- NVT - valuation context
- MVRV Z-score - cycle position
- NUPL - sentiment

---

## 🧪 Testing Methodology

### Step 1: Regression Analysis
Check coefficient sign, p-value, R²

### Step 2: Cycle-by-Cycle Validation
Require 60%+ sign consistency across cycles

### Step 3: Grid Search + Smoothness
Test multiple thresholds, look for smooth Sharpe curves

### Step 4: Walk-Forward Validation
365-day train, 90-day test, 90-day step

### Step 5: Entry Analysis
Plot price paths, measure drawdowns and gains

### Step 6: Exit Strategy Design
- Match exit TYPE to entry TYPE
- Use on-chain as TRIGGER, not hard exit
- Confirm robustness with grid search

---

## 📁 File Structure

```
research/
├── 01-05: Regression and early backtests
├── 06-10: SOPR signal development
├── 11-14: Entry analysis and filters
├── 15_mvrv_exit.ipynb              # MVRV discovery
├── 16_mvrv_deep_dive.ipynb         # Analysis
├── 17_mvrv_exit_fix.ipynb          # MVRV as trigger
├── 18_mvrv_grid_search.ipynb       # Final optimization ⭐
└── LESSONS_LEARNED.md              # This document

data/
├── mvrv_grid_search_results.json   # ⭐ Final results
├── sopr_mvrv_exit_results.json     
└── raw/                            
```

---

## 📈 Results Log

| Date | Signal | Beat B&H % | Verdict | Notes |
|------|--------|------------|---------|-------|
| 2025-01-09 | Liveliness < thresh | 12.5% | ❌ Fail | Use as regime filter |
| 2025-01-09 | SOPR + trailing stop | 54% | ✅ Usable | Baseline |
| 2025-01-09 | SOPR + momentum filter | - | ❌ Worse | Filter removes best trades |
| 2025-01-09 | SOPR + MVRV > 3.0 hard | 62% | ⚠️ Misleading | Stop loss doing the work |
| 2025-01-10 | **SOPR + MVRV > 2.25 trail** | **62%** | ✅✅ **FINAL** | 32/35 configs work! |

---

## 🔑 Key Takeaways

1. **Regression is for understanding, not trading**
2. **Walk-forward validation is mandatory**
3. **Beat Buy & Hold is the only metric that matters**
4. **Contrarian signals don't need trend filters**
5. **Match exit TYPE to entry TYPE** (sentiment → valuation)
6. **Use on-chain metrics as TRIGGERS, not hard exits**
7. **Grid search confirms robustness** - 91% of nearby configs should also work

---

## 🏆 FINAL STRATEGY

```
┌─────────────────────────────────────────────────────────┐
│                    ENTRY SIGNAL                         │
│                                                         │
│    SOPR < 1  AND  STH SOPR < 1                         │
│    (Both short-term and overall market selling at loss) │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    EXIT LOGIC                           │
│                                                         │
│  IF MVRV > 2.25:                                       │
│      Activate 20% trailing stop from peak              │
│      Exit when price drops 20% from highest point      │
│                                                         │
│  ELSE IF price drops 20% from entry:                   │
│      Stop loss exit (protection before MVRV triggers)  │
│                                                         │
│  ELSE IF 365 days pass:                                │
│      Max hold exit                                      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    RESULTS                              │
│                                                         │
│    Walk-Forward Beat Rate:  62%                        │
│    Avg Excess Return:       -7.1%                      │
│    Robustness:              32/35 configs beat baseline │
│                                                         │
│    Best MVRV trigger avg:   > 2.75                     │
│    Best trail % avg:        30%                        │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Future Work

1. **Test other entry signals:**
   - Supply in Profit < 50%
   - MVRV Z-Score < 0
   - Realized Loss spikes

2. **Test other exit triggers:**
   - NUPL > 0.75
   - Supply in Profit > 95%

3. **Build production system:**
   - Live monitoring dashboard
   - Alert when entry conditions met
   - Position sizing rules

---

*Last updated: 2025-01-10*
