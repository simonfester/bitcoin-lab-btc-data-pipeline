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

### 10. Use On-Chain Metrics to TRIGGER, Not Hard Exit

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

### 11. Grid Search Confirms Robustness

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

### 12. Regime Filters: Depends on Strategy Type ⭐ UPDATED

**Original Assumption:** Long-only strategies shouldn't trade in bear markets.

**Tested Result:** Regime filters did NOT improve our contrarian strategy!

| Strategy Type | Regime Filter Needed? | Why |
|--------------|----------------------|-----|
| **Trend-following** | ✅ Yes | Signals fire in trends, bear = wrong direction |
| **Contrarian** | ❌ No | Signals fire in capitulation = bear markets! |

**Why Contrarian Strategies Don't Need Regime Filters:**

1. **The signal IS bear market detection**
   - SOPR < 1 = people selling at loss = happens in downtrends
   - Filtering out bear markets removes the exact entries we want!

2. **Stop-loss provides protection**
   - 20% stop limits downside on bad entries
   - Bear trades that don't work get stopped out
   - No need for additional regime filter

3. **Best entries happen in bear markets**
   - March 2020 COVID crash → massive gains
   - Late 2022 FTX bottom → great entry
   - These would be filtered out!

**Key Distinction:**

| Concept | Trend-Following | Contrarian |
|---------|-----------------|------------|
| Entry filter | "Buy breakouts in uptrends" | "Buy capitulation (any regime)" |
| Protection | Regime filter | Stop-loss |
| Bear market | Don't trade | Best opportunities! |

**Updated Principle:** 
- Trend-following strategies need regime filters
- Contrarian strategies with stop-losses don't need them
- The stop-loss IS the protection mechanism

---

### 13. Accept Edge Case Losses in Trailing Stops ⭐ NEW

**Observation:** MVRV trail can exit at a loss if:
- Entry happens near a local peak
- MVRV triggers (market expensive)
- Price drops 25% from peak → exit below entry

**Example Problem Trade:**
```
Entry: $49,022
Peak: $50,983 (+4%)
MVRV > 2.0 → Trail activates
Price drops 25% from peak → Exit at $38,237
Result: -22% loss!
```

**Fixes Tested:**
| Fix | Logic | Result |
|-----|-------|--------|
| Profit gate 10% | Only trail if gain > 10% | No improvement |
| Higher MVRV (2.5) | Wait for more expensive | No improvement |
| Tighter trail (20%) | Exit sooner | No improvement |
| Trail from entry | Floor at entry price | No improvement |

**Why Fixes Don't Help:**
- The 3 problem trades are offset by benefits elsewhere
- Adding constraints might save those 3 trades but hurt others
- Net effect: zero improvement in walk-forward beat rate

**Lesson:** Some edge case losses are acceptable. If fixing them doesn't improve overall performance, the original logic is correct. Don't over-optimize for individual trades.

---

### 14. Let Winners Run - Avoid Arbitrary Time Exits ⭐ NEW

**Discovery:** Removing the 365-day max hold improved performance significantly.

| Metric | With 365d Max | Without Max | Change |
|--------|---------------|-------------|--------|
| Total Return | +3,305% | **+3,643%** | +338% |
| Alpha | +8.4%/yr | **+10.6%/yr** | +2.2% |
| Sharpe | 0.64 | **0.76** | +0.12 |

**Why Max Hold Hurt:**
- Forced exit on winning trades that hadn't reached MVRV trigger
- 2020 COVID entry: max_hold exited at +1007%, but could have been more
- 2022 bottom entry: max_hold exited at +120%, better exit timing without it

**Lesson:** If your exit logic is sound (MVRV trigger + trailing stop), don't add arbitrary time limits. Let the market tell you when to exit, not the calendar.

**When time exits DO make sense:**
- Mean-reversion strategies (edge decays quickly)
- Event-driven trades (catalyst has passed)
- Options/derivatives (time decay)

**When time exits DON'T make sense:**
- Trend-following with trailing stops ✅
- Contrarian entries waiting for cycle tops ✅

---

### 15. SIMPLER IS BETTER - The Ultimate Lesson ⭐ NEW

**Discovery:** Simple 30% trailing stop DOUBLED returns vs complex MVRV trail!

| Exit Strategy | Return | Complexity |
|---------------|--------|------------|
| MVRV > 2.0 triggers 25% trail + 20% SL | +3,643% | High (3 parameters, conditional logic) |
| **Simple 30% trail** | **+5,754%** | **Low (1 parameter, VectorBT validated)** |

**Why Simple Won:**

1. **No edge cases** - Trail is always active, no "what if MVRV triggers at bad time"
2. **No confusion** - One rule: exit when price drops 30% from peak
3. **No dependencies** - Doesn't rely on external metric (MVRV) being accurate
4. **Better protection** - Trail active from day 1, not waiting for MVRV

**The Complex Strategy Failed Because:**
- MVRV trigger could activate at low profit → trail exit at loss
- Stop loss + trail = two conflicting exit mechanisms
- More parameters = more things to go wrong

**New Principle:**
> "When in doubt, simplify. If a simpler strategy performs as well or better, always choose simpler."

This is now the #1 lesson from this entire research project.

---

### 16. Combine ORTHOGONAL Signals, Not Redundant Ones

**Key Discovery:** Adding Realized Loss to SOPR improved beat rate from 62% → 67%!

| Signal Combination | Beat Rate | Why |
|-------------------|-----------|-----|
| SOPR alone | 62% | Sentiment direction only |
| SOPR + Supply in Profit | 54% | ❌ Both measure profitability (redundant) |
| SOPR + MVRV Z filter | 58% | ❌ Valuation doesn't help entry |
| **SOPR + Realized Loss** | **67%** | ✅ Direction + Intensity (orthogonal!) |

**The Framework - Categorize Metrics by What They Measure:**

| Category | What It Measures | Example Metrics | Correlation |
|----------|------------------|-----------------|-------------|
| **Profitability** | Are people in profit/loss? | SOPR, STH-SOPR, SIP | High within group |
| **Intensity** | How MUCH profit/loss? | Realized Loss, Realized Profit | Different from direction |
| **Valuation** | Over/undervalued? | MVRV, NUPL, MVRV-Z | 0.90 correlation (redundant!) |
| **Supply** | Who holds coins? | LTH/STH ratio, Exchange flows | Different dimension |

**Why SOPR + Realized Loss Works:**
- SOPR = "people selling at loss" (direction: loss vs profit)
- Realized Loss Z > 0.5 = "above average losses" (intensity: how much)
- Together = "meaningful capitulation, not just noise"

**Why SOPR + SIP Failed:**
- SOPR = "people selling at loss"
- SIP = "% of supply in profit"
- Both measure the SAME thing (profitability) from different angles
- No new information added → just filters out signals

**Lesson:** Before combining metrics, ask: "Does this add DIFFERENT information or just measure the same thing differently?" Group metrics by category and use ONE from each relevant category.

---

### 17. Use REALIZED Metrics for Entry, PRICE ACTION for Exit ⭐ NEW

**Key Insight:** Why do on-chain metrics work for entries but not exits?

| Metric Type | Examples | What It Measures | Best Use |
|-------------|----------|------------------|----------|
| **Realized (Flow)** | SOPR, STH-SOPR, Realized Loss | Coins moving NOW at profit/loss | ✅ Entry signals |
| **Unrealized (Stock)** | MVRV, NUPL, Supply in Profit | Paper gains/losses that COULD be realized | ❌ Exit signals |

**Why Realized Metrics Work for Entry:**
```
SOPR < 1 = People ARE selling at a loss (action)
         = Capitulation is HAPPENING
         = Observable, confirmed behavior
         = 100% bottom detection rate
```

When SOPR < 1, coins are **literally moving on-chain at a loss**. This is real behavior.

**Why Unrealized Metrics Fail for Exit:**
```
MVRV > 2.5 = People COULD sell at profit (potential)
           = Euphoria EXISTS but not acted on
           = Paper gains, not realized
           = Still +10-25% upside after signal!
```

When MVRV > 2.5, people **haven't sold yet**. They might:
- Hold longer (greed)
- Wait for higher prices
- Never sell (HODLers)

**The Core Asymmetry:**

| At Bottoms | At Tops |
|------------|----------|
| Panic is an **ACTION** | Greed is a **STATE** |
| People MUST sell (margin calls, fear) | People CAN hold forever |
| SOPR captures the action | MVRV only shows potential |
| Selling creates the bottom | Holding delays the top |

**Why Trailing Stops Work for Exits:**
```
Trailing stop = Waits for REALIZED selling pressure
             = Price actually dropping
             = People ARE selling (not just could sell)
             = Flow-based exit (like entry!)
```

**Updated Mental Model:**
```
ENTRY: Use REALIZED metrics (SOPR, STH-SOPR)
       → Catches actual capitulation behavior
       
EXIT: Use PRICE ACTION (trailing stop)
       → Catches actual reversal behavior
       
Don't use UNREALIZED metrics for hard exits
       → They show state, not action
       → People can stay irrational longer than expected
```

**Evidence:**
- SOPR < 1 caught 100% of major bottoms
- MVRV > 2.5 still had +10% forward returns (too early!)
- SOPR > 1.02 still had +22% forward returns (way too early!)
- Simple 30% trail beat all on-chain exit signals

**Lesson:** Match metric type to use case:
- Realized (flow) metrics → Entry signals ✅
- Price action (trailing stop) → Exit signals ✅
- Unrealized (stock) metrics → Context only, not hard exits ⚠️

---

### 17. Realized Metrics for Entries, Price Action for Exits ⭐ NEW

**Key Insight:** SOPR works for entries because it measures REALIZED behavior (actual selling). MVRV doesn't work for exits because it measures UNREALIZED state (potential selling).

**The Fundamental Difference:**

| Metric Type | What It Measures | Example | Best Use |
|-------------|------------------|---------|----------|
| **Realized (Flow)** | Coins moving RIGHT NOW | SOPR, Realized Loss | Entries ✅ |
| **Unrealized (Stock)** | Paper gains/losses | MVRV, NUPL, Supply in Profit | Context only ⚠️ |

**Why Realized Works for Entries:**
```
SOPR < 1 = People ARE selling at a loss (observable action)
         = Capitulation is HAPPENING
         = Real behavior, confirmed on-chain
         = 100% of major bottoms caught
```

When SOPR < 1, coins are **literally moving on-chain at a loss**. This is behavior, not potential.

**Why Unrealized Fails for Exits:**
```
MVRV > 2.5 = People COULD sell at profit (potential)
           = Euphoria EXISTS but not acted on
           = Paper gains, holders haven't sold
           = Still +10-25% upside after signal!
```

When MVRV > 2.5, people **haven't sold yet**. They might hold longer, wait for higher prices, or never sell.

**The Core Asymmetry:**

| At Bottoms | At Tops |
|------------|--------|
| Panic is an **ACTION** | Greed is a **STATE** |
| People MUST sell (margin calls, fear) | People CAN hold forever |
| SOPR captures the action | MVRV only shows potential |
| Selling creates the bottom | Holding delays the top |

**Why Trailing Stops Work for Exits:**
```
Trailing stop = Waits for REALIZED selling pressure
             = Price actually dropping
             = People ARE selling (not just could sell)
             = Flow-based exit (like SOPR is flow-based entry)
```

**Metric Categories:**

| Flow Metrics (Realized) | Stock Metrics (Unrealized) |
|-------------------------|---------------------------|
| SOPR, STH-SOPR | MVRV, NUPL |
| Realized Loss/Profit | Supply in Profit |
| Exchange inflows | Market Cap |
| **Measure behavior** | **Measure state** |
| **Good for entries** | **Less reliable for exits** |

**The Principle:**
```
ENTRY: Use REALIZED metrics (SOPR, Realized Loss)
       → Catches actual capitulation behavior
       
EXIT: Use PRICE ACTION (trailing stop)
       → Catches actual reversal behavior
       
Don't use UNREALIZED metrics for hard exits
       → They show state, not action
       → People can stay irrational longer than expected
```

**Lesson:** Match your signal type to what you're trying to detect. Entries need to detect ACTION (use realized/flow metrics). Exits need to detect REVERSAL (use price action). Unrealized metrics tell you the market is expensive but not WHEN it will turn.

---

### 18. Realized Metrics Work for BOTH Entries AND Exits ⭐ NEW

**Discovery:** Just as SOPR < 1 (realized loss) marks bottoms, SOPR > 1.05 (realized profit) marks tops!

**The Mirror Logic:**

| Entry (Bottoms) | Exit (Tops) |
|-----------------|-------------|
| SOPR < 1 (selling at loss) | SOPR > 1.05 (selling at profit) |
| Realized Loss spike | Realized Profit spike |
| Capitulation IS happening | Distribution IS happening |
| 100% of bottoms caught | Better exit timing |

**Test Results:**

| Exit Strategy | Return | Improvement |
|---------------|--------|-------------|
| Simple Trail | +1,144% | Baseline |
| **Realized Exit** | **+1,505%** | **+31% better** |

**The Complete Framework:**

```
ENTRY:
  Context: Market sentiment negative
  Trigger: SOPR < 1 (people ARE selling at loss)
  = Capitulation IS happening → BUY

EXIT:
  Context: MVRV > 2.0 (market expensive)
  Trigger: SOPR > 1.05 (people ARE selling at profit)
  = Distribution IS happening → SELL (via tighter trail)
```

**Why MVRV Alone Fails for Exits:**
```
MVRV > 2.5 = People COULD sell (unrealized)
           = But they haven't yet!
           = Still +10-25% upside after signal
           = Too early

MVRV > 2.5 + SOPR > 1.05 = Expensive AND selling happening
                         = Distribution confirmed
                         = Better timing
```

**The Principle:**
- Unrealized metrics (MVRV, NUPL) tell you market STATE (expensive/cheap)
- Realized metrics (SOPR, Realized P/L) tell you market ACTION (buying/selling)
- STATE provides context, ACTION provides timing
- Use BOTH: Context (MVRV) + Action (SOPR) = Optimal signal

**Lesson:** The same logic that makes SOPR work for entries makes it work for exits. Realized metrics detect ACTION - whether that's panic selling (entries) or profit-taking (exits). Unrealized metrics only show potential, not behavior.

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

### ✅✅ SOPR + MVRV-Triggered Trailing Stop (v2)

**Signal:** Buy when SOPR < 1 AND STH SOPR < 1

**Exit Strategy:** 
- When MVRV > 2.25 → activate 20% trailing stop from peak
- Before MVRV triggers → 20% stop loss protection
- Max hold: 365 days

**Results:**
| Metric | Value |
|--------|-------|
| Walk-Forward Beat B&H | 62% |
| Avg Excess Return | -7.1% |
| Robustness | 32/35 configs beat baseline (91%) |

**Verdict:** Good strategy, superseded by v3.

---

### ✅✅✅ SOPR + Realized Loss + MVRV Trail (v3) ⭐ CURRENT BEST

**Signal:** Buy when SOPR < 1 AND STH SOPR < 1 AND Realized Loss Z > 0.5

**Exit Strategy:** 
- When MVRV > 2.0 → activate 25% trailing stop from peak
- Before MVRV triggers → 20% stop loss protection
- Max hold: 365 days

**Results:**
| Metric | Value |
|--------|-------|
| Walk-Forward Beat B&H | **67%** |
| Robustness | 74/140 configs beat 62% baseline (53%) |
| Improvement vs v2 | +5% beat rate |

**Why It's Better Than v2:**
- Adds intensity filter (RL Z > 0.5) to sentiment signal (SOPR)
- Filters for "meaningful capitulation" not just "any selling at loss"
- Lower MVRV trigger (2.0 vs 2.25) with wider trail (25% vs 20%)

**Verdict:** Current best strategy. Ready for paper trading.

---

## 📊 Metrics by Use Case

### Trading Signals (Entry)
- **SOPR < 1 + STH SOPR < 1** - Double capitulation (direction)
- **Realized Loss Z > 0.5** - Capitulation intensity (magnitude) 
- Combined = 67% beat rate ✅ BEST

### Trading Signals (Exit Triggers)
- **MVRV > 2.0** - Activates trailing stop ✅ BEST
- MVRV > 2.75 - More conservative trigger
- NUPL > 0.75 - Alternative (but 0.90 correlated with MVRV, redundant)

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

### Step 7: Combine Orthogonal Signals ⭐ NEW
- Group metrics by category (profitability, intensity, valuation, supply)
- Test ONE metric from each relevant category
- Avoid combining correlated metrics (they're redundant)

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
├── 18_mvrv_grid_search.ipynb       # SOPR+MVRV optimization
├── 19_supply_in_profit_entry.ipynb # SIP test (failed)
├── 20_mvrv_z_score_entry.ipynb     # MVRV-Z test (failed)
├── 21_realized_loss_entry.ipynb    # RL discovery ⭐
├── 22_nupl_exit.ipynb              # NUPL test (redundant)
├── 23_sopr_rl_robustness.ipynb     # Final optimization ⭐⭐
├── STRATEGY_REGISTRY.md            # Strategy tracker
└── LESSONS_LEARNED.md              # This document

data/
├── sopr_rl_robustness_results.json # ⭐ Current best results
├── mvrv_grid_search_results.json   # v2 results
└── raw/                            
```

---

## 📈 Results Log

| Date | Signal | Beat B&H % | Verdict | Notes |
|------|--------|------------|---------|-------|
| 2025-01-09 | Liveliness < thresh | 12.5% | ❌ Fail | Use as regime filter |
| 2025-01-09 | SOPR + trailing stop | 54% | ✅ Usable | Baseline v1 |
| 2025-01-09 | SOPR + momentum filter | - | ❌ Worse | Filter removes best trades |
| 2025-01-09 | SOPR + MVRV > 3.0 hard | 62% | ⚠️ Misleading | Stop loss doing the work |
| 2025-01-10 | SOPR + MVRV > 2.25 trail | 62% | ✅✅ Good | v2, 91% robust |
| 2025-01-10 | Supply in Profit entry | 38% | ❌ Fail | Too rare, lagging |
| 2025-01-10 | MVRV Z-Score entry | 42% | ❌ Fail | Valuation too slow for entry |
| 2025-01-10 | NUPL exit | 54% | ❌ Fail | Redundant with MVRV (0.90 corr) |
| 2025-01-10 | **SOPR + RL + MVRV trail** | **67%** | ✅✅✅ **BEST** | v3, 53% robust |
| 2025-01-10 | Regime filter test | 67% | ✅ No change | Not needed for contrarian strategies |
| 2025-01-10 | MVRV trail fix (profit gate) | 67% | ✅ No change | Edge case losses acceptable |
| 2025-01-10 | **Remove max hold** | **+3,643%** | ✅✅✅ **BEST** | Alpha +10.6%/yr, let winners run |
| 2025-01-10 | **Simple 30% Trail** | **+5,754%** | ✅✅✅ **FINAL** | VectorBT validated, Sharpe 1.45 |
| 2025-01-11 | Historical bottoms analysis | 100% | ✅ Insight | STH-SOPR < 1 caught ALL major bottoms |
| 2025-01-11 | Historical tops analysis | N/A | ✅ Insight | Exit signals have +10-25% MORE upside |
| 2025-01-11 | Adaptive trail test | +1,886% | ✅ | Simple 8% trail beat adaptive variants |
| 2025-01-11 | **STRAT-003 (STH + 8% trail)** | **+1,886%** | ✅✅ **SHORT-TERM** | 9 trades/yr, 29d avg hold, paper ready |
| 2025-01-11 | Realized profit exit theory | +31% better | ✅✅ **INSIGHT** | SOPR > 1.05 marks tops like SOPR < 1 marks bottoms |

---

## 🔑 Key Takeaways

1. **Regression is for understanding, not trading**
2. **Walk-forward validation is mandatory**
3. **Beat Buy & Hold is the only metric that matters**
4. **Contrarian signals don't need trend filters** (for entry)
5. **Match exit TYPE to entry TYPE** (sentiment → valuation)
6. **Use on-chain metrics as TRIGGERS, not hard exits**
7. **Grid search confirms robustness** - majority of configs should work
8. **Combine ORTHOGONAL signals** - direction + intensity beats direction alone
9. **Avoid redundant metrics** - NUPL ≈ MVRV, SIP ≈ SOPR (don't stack them)
10. **Regime filters depend on strategy type** - trend-following needs them, contrarian doesn't!
11. **Let winners run** - avoid arbitrary time exits when exit logic is sound
12. **SIMPLER IS BETTER** - Simple 30% trail beat complex MVRV trail by 2x! 🏆
13. **Realized metrics for entries, price action for exits** - SOPR works because it's realized (action); MVRV fails for exits because it's unrealized (state). Panic is action, greed is state. 🏆
14. **Realized metrics work for BOTH entries AND exits** - SOPR < 1 marks bottoms, SOPR > 1.05 marks tops. Action beats state for timing! 🏆

---

## 🏆 FINAL STRATEGY (v5) - VectorBT Validated

```
┌─────────────────────────────────────────────────────────┐
│                    ENTRY SIGNAL                         │
│                                                         │
│    SOPR < 1  AND  STH SOPR < 1  AND  RL Z > 0.5        │
│    (Capitulation direction + intensity)                 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    EXIT LOGIC                           │
│                                                         │
│    30% trailing stop from peak (always active)         │
│                                                         │
│    That's it. Simple.                                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│           BACKTEST RESULTS (VectorBT)                   │
│              (2019-01 to 2026-01)                       │
│                                                         │
│    Total Return:    +5,754%                            │
│    Buy & Hold:      +2,268%                            │
│    CAGR:            +77.8%                             │
│                                                         │
│    Sharpe:          1.45                               │
│    Sortino:         2.21                               │
│    Win Rate:        62%                                │
│    Profit Factor:   6.69                               │
│    Max Drawdown:    -63.8%                             │
│    Total Trades:    8                                  │
│                                                         │
│    $100,000 → $5,853,745                              │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Future Work

1. **Test Supply Distribution category:**
   - LTH/STH ratio extremes
   - Exchange flows

2. **Test Network Activity category:**
   - NVT extremes
   - Active address anomalies

3. **Build production system:**
   - Live monitoring dashboard
   - Alert when entry conditions met
   - Position sizing rules

4. **Paper trade both strategies:**
   - STRAT-002 (67%, primary)
   - STRAT-001 (62%, backup)

---

*Last updated: 2025-01-11*
