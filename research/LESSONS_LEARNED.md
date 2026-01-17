# Bitcoin Signal Research: Lessons Learned

A living document capturing insights from our signal research and backtesting.

---

## 📍 Quick Navigation

| Section | Description |
|---------|-------------|
| [📚 Key Principles](#-key-principles) | 21 core lessons from research |
| [🎯 Master Signal Reference](#-master-signal-reference) | **⭐ START HERE** - Consolidated entry/exit signals |
| [🔬 Tested Signals](#-tested-signals) | Detailed analysis of each metric |
| [📊 Results Log](#-results-log) | Chronological test results |
| [🔑 Key Takeaways](#-key-takeaways) | Top lessons summary |

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

### 18. Realized Metrics Work for BOTH Entries AND Exits (Timeframe Dependent) ⭐ UPDATED

**Discovery:** Just as SOPR < 1 (realized loss) marks bottoms, SOPR > 1.05 (realized profit) marks tops!

**The Mirror Logic:**

| Entry (Bottoms) | Exit (Tops) |
|-----------------|-------------|
| SOPR < 1 (selling at loss) | SOPR > 1.05 (selling at profit) |
| Realized Loss spike | Realized Profit spike |
| Capitulation IS happening | Distribution IS happening |
| 100% of bottoms caught | Better exit timing (short-term) |

**Test Results - TIMEFRAME MATTERS:**

| Strategy | Simple Trail | Realized Exit | Winner |
|----------|--------------|---------------|--------|
| **Long-term (30% trail)** | **+5,766%** | +3,712% | **Simple** ✅ |
| **Short-term (8% trail)** | +1,144% | **+1,505%** | **Realized** ✅ |

**Why Different Results?**

| Factor | Long-Term | Short-Term |
|--------|-----------|------------|
| Base Trail | 30% (wide) | 8% (tight) |
| Avg Hold | 300-500 days | 29 days |
| Trades | 8 total | 65 total |
| Effect of Tightening | Exits too early | Better timing |

**The Nuance:**

```
LONG-TERM (wide trail):
  - 30% trail already lets winners run
  - Tightening to 15-20% = earlier exits
  - With 8 trades, each early exit costs huge returns
  - Simple wins: +5,766% vs +3,712%

SHORT-TERM (tight trail):
  - 8% trail is already aggressive
  - Realized signal helps catch reversals
  - With 65 trades, better timing compounds
  - Realized wins: +1,505% vs +1,144%
```

**The Complete Framework:**

```
ENTRY (Both timeframes):
  Context: Market sentiment negative
  Trigger: SOPR < 1 (people ARE selling at loss)
  = Capitulation IS happening → BUY

EXIT (Timeframe dependent):
  Long-term: Simple wide trail (30%) - let winners run
  Short-term: Realized exit OR tight trail (8-15%)
```

**When to Use Realized Exit:**
- ✅ Short-term strategies (tight base trail)
- ✅ Frequent trading (more samples to benefit)
- ✅ Goal is catching reversals quickly
- ❌ Long-term strategies (wide base trail)
- ❌ Few trades (each exit matters too much)
- ❌ Goal is letting winners run to maximum

**Lesson:** Realized metrics work for exits but are TIMEFRAME DEPENDENT. For long-term strategies, simple wide trails beat complex triggers. For short-term strategies, realized profit signals can improve timing. The principle "simpler is better" still holds for long-term wealth building.

**Why This Matters:**
- The insight about realized vs unrealized is STILL VALID for understanding WHY signals work
- But APPLYING realized exit signals depends on your strategy timeframe
- Long-term: Let winners run with wide trail (simple wins)
- Short-term: Tighter timing matters (realized can help)

---

### 19. LTH-SOPR is the Best Exit Signal for Short-Term Strategies ⭐ NEW

**Discovery:** Long-Term Holder SOPR provides a much stronger exit signal than STH-SOPR!

**Why LTH-SOPR Works Better:**

| Metric | STH-SOPR | LTH-SOPR |
|--------|----------|----------|
| Who | Traders (<155 days) | HODLers (>155 days) |
| Behavior | Trade frequently, noisy | Rarely sell, deliberate |
| Cost basis gap | Small (recent buys) | Huge (old buys) |
| Value at tops | ~1.03 | ~5.0 |
| Signal strength | Weak (always near 1) | Strong (5x = meaningful) |

**At Major Tops:**
```
STH-SOPR at tops: ~1.03 (traders taking 3% profit - happens constantly)
LTH-SOPR at tops: ~5.00 (HODLers taking 400% profit - rare, deliberate)
```

**Test Results:**

| Exit Strategy | Return | Improvement |
|---------------|--------|-------------|
| Simple Trail | +2,970% | Baseline |
| **LTH-SOPR > 1.5 Exit** | **+3,813%** | **+28% better** |

**The Complete Framework:**

```
ENTRY:  STH-SOPR < 1
        = Short-term holders selling at LOSS
        = Weak hands capitulating
        = BUY from panic

EXIT:   LTH-SOPR > 1.5 (with MVRV > 2.5 context)
        = Long-term holders selling at BIG PROFIT
        = Smart money distributing
        = SELL to greed
```

**Why This Works:**
- STH selling = Normal market noise
- LTH selling = "I've held for YEARS, NOW I'm selling"
- LTH distribution = Real cycle top behavior
- 5x signal strength = Much clearer timing

**Important Caveat:**
```
✅ Works for: Short-term strategies
   - Return: +3,813% (vs +2,970% simple trail)
   - +28% improvement

❌ Doesn't help: Long-term strategies
   - Simple 30% trail: +7,827%
   - LTH-SOPR exit: +4,974%
   - Simple still wins for long-term!
```

**Lesson:** Match your exit signal to who you're trying to detect. For exits, LTH behavior is more meaningful than STH behavior - they're the "smart money" with conviction. But this only helps short-term strategies where tighter timing matters.

---

### 20. MVRV Z-Score Beats Raw MVRV for Triggered Exits ⭐ NEW

**Discovery:** When using complex exit triggers, MVRV Z-Score outperforms raw MVRV.

**Why MVRV Z is Better:**

| Factor | Raw MVRV | MVRV Z-Score |
|--------|----------|---------------|
| Type | Absolute threshold | Relative to history |
| Meaning | "Market cap is 2.5x realized" | "2 std devs above mean" |
| Adapts to change? | No | Yes |
| At major tops | ~2.5 | ~3.6 |
| Statistical basis | None | Gaussian |

**Test Results (STRAT-002 Long-Term):**

| Exit Trigger | Return |
|--------------|--------|
| **Simple 30% trail** | **+6,122%** (still wins!) |
| MVRV Z>2.5 + LTH>1.5 | +4,409% |
| MVRV>2.5 + LTH>1.5 | +3,881% |

**MVRV Z beat raw MVRV by +528%** for the same trigger logic.

**Why Z-Score Adapts Better:**
```
2021 Bull Market:
  MVRV = 3.0 might be "normal euphoria"
  MVRV Z = 3.0 means "3 std devs above recent mean"

2024 Bull Market:
  Market structure changed (ETFs, institutions)
  Raw MVRV thresholds may be outdated
  Z-score auto-adjusts to new normal
```

**Important Caveat:**
```
✅ MVRV Z > raw MVRV for triggered exits
❌ But simple trail STILL beats both for long-term!
   Simple: +6,122%
   MVRV Z: +4,409%
   Raw MVRV: +3,881%
```

**When to Use What:**

| Strategy | Best Exit |
|----------|----------|
| Long-term (STRAT-002) | Simple 30% trail |
| Short-term (STRAT-003) | MVRV Z > 2.5 + LTH > 1.5 trigger |

**Lesson:** If you're going to use complex triggered exits, use MVRV Z-Score instead of raw MVRV - it adapts to market structure changes. But for long-term strategies, simple trailing stops still win because they let winners run without premature exits.

---

### 21. Realized Price is an ENTRY Signal, Not EXIT ⭐ NEW

**Discovery:** Using Realized Price as an exit stop HURTS performance massively!

**The Failed Hypothesis:**
```
"If price drops below Realized Price, bear market is accelerating"
"Exit to preserve gains"
```

**Test Results:**

| Strategy | Baseline | With RP Stop | Difference |
|----------|----------|--------------|------------|
| STRAT-002 (Long) | +5,763% | +3,252% | **-2,511%** ❌ |
| STRAT-003 (Short) | +2,634% | +816% | **-1,818%** ❌ |

**Why RP Stop Fails:**
```
Price < Realized Price:
  = Network is underwater on average
  = Maximum capitulation
  = MVRV < 1 (same thing)
  = Forward returns are POSITIVE!
  = This marks BOTTOMS, not danger!

RP Stop sells at the WORST possible time.
```

**Historical Context:**
- Price < RP only happened in 2018-2019 and 2022
- These were the BEST buying opportunities
- Forward 90d returns from below RP are strongly positive

**Lesson:** Realized Price crossing is a BOTTOM indicator, not a top indicator. Using it as an exit stop sells at maximum fear - exactly wrong.

---

## 🎯 Master Signal Reference

A consolidated reference of all validated entry and exit signals from this research.

### ✅ ENTRY SIGNALS (What Marks Bottoms)

| Signal | Type | Description | Validation |
|--------|------|-------------|------------|
| **SOPR < 1** | Realized | People ARE selling at loss | 100% of bottoms caught |
| **STH-SOPR < 1** | Realized | Short-term holders panicking | Weak hands capitulating |
| **Realized Loss Z > 0.5** | Realized | Above-average losses | Intensity filter |
| **Price < Realized Price** | Valuation | Network underwater | MVRV < 1 equivalent |
| **MVRV < 1** | Valuation | Market cap < realized cap | Deep value territory |

**Entry Framework:**
```
BEST ENTRY = Direction + Intensity

Direction: SOPR < 1 AND STH-SOPR < 1
           (Capitulation IS happening)

Intensity: Realized Loss Z > 0.5
           (Meaningful capitulation, not noise)
```

### ✅ EXIT SIGNALS (What Marks Tops)

| Signal | Type | Description | Best For |
|--------|------|-------------|----------|
| **Simple 30% Trail** | Price Action | Exit on 30% drop from peak | Long-term 🏆 |
| **LTH-SOPR > 1.5** | Realized | Smart money distributing | Short-term trigger |
| **MVRV Z > 2.5** | Valuation | Statistically expensive | Context for trigger |
| **MVRV > 2.5** | Valuation | Market cap 2.5x realized | Context (less adaptive) |

**Exit Framework:**
```
LONG-TERM STRATEGY:
  Simple 30% trailing stop
  No triggers, no complexity
  Let winners run to maximum

SHORT-TERM STRATEGY:
  Context: MVRV Z > 2.5 (market expensive)
  Trigger: LTH-SOPR > 1.5 (smart money selling)
  Action: Tighten trail to 15%
```

### ❌ FAILED EXIT SIGNALS (Don't Use)

| Signal | Why It Fails |
|--------|-------------|
| **Price < Realized Price** | Marks bottoms, not tops! Sells at worst time. |
| **MVRV > 2.5 alone** | Unrealized = state, not action. +10-25% upside remains. |
| **STH-SOPR > 1.05** | Too noisy, always near 1.0. Not meaningful. |
| **SOPR > 1.02** | +22% forward returns - way too early! |
| **Arbitrary time exits** | Market timing > calendar timing |

### 💡 The Core Principle

```
┌───────────────────────────────────────────────────────┐
│                    BOTTOMS                            │
│                                                       │
│  WHO: Short-term holders (weak hands)                │
│  WHAT: Selling at LOSS (SOPR < 1)                     │
│  WHY: Panic, margin calls, fear                       │
│  ACTION: Capitulation IS happening                    │
│                                                       │
│  → BUY from weak hands                               │
└───────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────┐
│                     TOPS                              │
│                                                       │
│  WHO: Long-term holders (smart money)                 │
│  WHAT: Selling at BIG PROFIT (LTH-SOPR > 1.5)         │
│  WHY: Taking gains after years of holding             │
│  ACTION: Distribution IS happening                    │
│                                                       │
│  → SELL to greedy late buyers                        │
└───────────────────────────────────────────────────────┘

             THE ASYMMETRY:
             
  At Bottoms: Panic is ACTION (must sell)
  At Tops: Greed is STATE (can hold forever)
  
  → Use REALIZED metrics for entries (detect action)
  → Use PRICE ACTION for exits (detect reversal)
  → Use UNREALIZED metrics for context only
```

### 🏆 Final Validated Strategies

**STRAT-002 (Long-Term Wealth Building):**
```
Entry: SOPR < 1 AND STH-SOPR < 1 AND RL Z > 0.5
Exit:  Simple 30% trailing stop

Return: +5,763% to +7,827%
Trades: ~8 over 7 years
Best for: Deploy and forget
```

**STRAT-003 (Active Trading):**
```
Entry: STH-SOPR < 1
Exit:  MVRV Z > 2.5 + LTH-SOPR > 1.5 → tighten to 15% trail

Return: +2,634% to +3,813%
Trades: ~15 over 7 years  
Best for: Paper trading, learning
```

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
| 2025-01-11 | **STRAT-002 v6 vs v5** | v5 wins | ✅ **CONFIRMED** | Simple 30% trail (+5,766%) beat realized exit (+3,712%) for long-term |
| 2025-01-12 | **LTH-SOPR exit test** | **+3,813%** | ✅✅ **BREAKTHROUGH** | LTH-SOPR > 1.5 beat simple trail (+2,970%) by +28% for short-term! |
| 2025-01-12 | LTH-SOPR for STRAT-002 | v5 wins | ✅ Confirmed | Simple 30% trail (+7,827%) still beats LTH exit (+4,974%) for long-term |
| 2025-01-12 | **MVRV Z + LTH exit test** | +4,409% | ✅ **INSIGHT** | MVRV Z > raw MVRV (+528% better) for triggered exits |
| 2025-01-12 | MVRV Z for STRAT-002 | v5 wins | ✅ Confirmed | Simple 30% trail (+6,122%) still beats all complex exits for long-term |
| 2025-01-12 | **Realized Price stop test** | -2,511% | ❌ **REJECTED** | RP marks BOTTOMS not tops! Selling at worst time. |

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
14. **Realized exits are TIMEFRAME DEPENDENT** - Works for short-term (tight trails, many trades), NOT for long-term (wide trails, few trades). Simple 30% trail beat realized exit by +2,000% for long-term! 🏆
15. **LTH-SOPR is the best exit signal for short-term** - At tops: LTH-SOPR ~5.0 vs STH-SOPR ~1.03. Smart money distribution beats trader noise. +28% improvement over simple trail! 🏆
16. **MVRV Z-Score > raw MVRV for triggered exits** - If using complex exits, MVRV Z > 2.5 beats MVRV > 2.5 by +528%. Z-score adapts to market structure changes. 🏆
17. **Realized Price is ENTRY signal, not EXIT** - Price < RP marks BOTTOMS (best buying). Using RP as exit stop costs -2,511%. Don't sell at maximum fear! 🏆

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

*Last updated: 2025-01-12*
