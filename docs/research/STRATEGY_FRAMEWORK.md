# Bitcoin Strategy Development Framework

## Overview

This framework provides a systematic approach to generating, validating, and deploying Bitcoin trading strategies using on-chain data. It is grounded in the Checkonchain Framework and the Confluence Principle.

---

## PART 1: THEORETICAL FOUNDATION

### The Checkonchain Framework (3 Axes)

Every on-chain metric is a cross-section of the Bitcoin supply along one or more axes:

```
           AXIS Y: PROFIT/LOSS
                    ▲
                    │  Unrealized P/L (pressure)
                    │  Realized P/L (action) ← MOST ACTIONABLE
                    │  Supply in P/L (binary)
                    │  Cost Basis (levels)
                    │
    ────────────────┼────────────────► AXIS X: SUPPLY vs VOLUME
    UNSPENT SUPPLY  │  SPENT VOLUME
    (dormant,       │  (active,
     lagging,       │   dynamic,
     soft signals)  │   ACTIONABLE)
                    │
                    ▼
              AXIS Z: COHORTS
              • LTH / STH (by time)
              • Wallet Size (by amount)
              • Entities (exchanges, miners, ETFs)
```

### Key Insight: Metric Selection

| Axis X Position | Signal Type | Use Case |
|-----------------|-------------|----------|
| **Unspent Supply** | Soft, lagging | Context, macro positioning |
| **Spent Volume** | Dynamic, actionable | Entry/exit signals, active trading |

| Axis Y Category | What It Measures | Best For |
|-----------------|------------------|----------|
| Supply in P/L | Binary count | Macro cycle extremes |
| Unrealized P/L | Paper gains (MVRV, NUPL) | Implied pressure, context |
| **Realized P/L** | **Actual decisions** | **Trading signals** |
| Cost Basis | Support/resistance levels | Position sizing, targets |

### The Confluence Principle

> "Whenever we can identify confluence between several models, it can help to add confidence about the trends playing out." — James Check

**Never trade on a single indicator.** Always require multiple independent confirmations.

| Confluence Level | Confirmations | Action |
|------------------|---------------|--------|
| Weak | 1 | Monitor only |
| Moderate | 2-3 | Small position, tight stops |
| **Strong** | **4+** | **Full position with conviction** |

---

## PART 2: STRATEGY GENERATION PROCESS

### Step 1: Define the Market Behavior to Capture

Before building metrics, clearly articulate what market behavior you're trying to detect:

**Examples:**
- "Short-term holders capitulating after a drawdown" (STRAT-002/004)
- "Long-term holders distributing into strength" (exit signal)
- "Miners selling to cover costs during stress" (accumulation opportunity)
- "New capital entering via ETFs" (momentum confirmation)

### Step 2: Select Metrics Using the 3 Axes

For each strategy, consciously choose metrics across the axes:

**Entry Signal Construction:**
```
AXIS X: Choose SPENT VOLUME metrics (actionable, not lagging)
        ↓
AXIS Y: Choose REALIZED P/L metrics (actual decisions, not implied)
        ↓
AXIS Z: Choose appropriate COHORT (who is acting?)
```

**Example - STRAT-002/004 Entry:**
- X-Axis: SOPR (Spent Output Profit Ratio) → measures spent coins
- Y-Axis: SOPR < 1 → coins spent at a loss (realized loss)
- Z-Axis: STH-SOPR → isolates short-term holders

**Translation:** "Short-term holders are spending their coins at a loss."

### Step 3: Add Confirmation Layers

Each signal should have multiple confirmation layers from INDEPENDENT sources:

**Independence Matrix:**
| Source Type | Examples | Notes |
|-------------|----------|-------|
| Profit/Loss Metrics | SOPR, STH-SOPR, Realized Loss | Same family, partial independence |
| Valuation Metrics | MVRV, AVIV, NUPL | Cost basis ratios |
| Supply Metrics | Supply in Profit %, LTH/STH ratio | Binary/distribution |
| Technical | 200D MA, Power Law | Price-derived |
| Production Cost | Thermocap, Difficulty | Miner economics |

**Good Confluence:** SOPR < 1 + Price < TMM + MVRV < 1.5
**Weak Confluence:** SOPR < 1 + STH-SOPR < 1 (same metric family)

### Step 4: Define Entry and Exit Rules

**Entry Rules Template:**
```
IF [Primary Signal] AND [Confirmation 1] AND [Confirmation 2]:
    ENTER position
    
Position Size = Base Size × Valuation Multiplier
```

**Exit Rules Options:**
1. **Trailing Stop** - Best for capturing trends (our primary method)
2. **Indicator-Based** - Exit when opposite signal fires
3. **Target-Based** - Exit at predefined levels (e.g., Vaulted Price)
4. **Time-Based** - Exit after N days

**STRAT-002 vs STRAT-004 Insight:**
Same entry logic, different exit management:
- STRAT-002: 30% trail → macro swings, ~2 trades/year
- STRAT-004: 12% trail → income generation, ~15 trades/year

---

## PART 3: VALIDATION FRAMEWORK

### Stage 1: Backtest (In-Sample)

**Requirements:**
- Minimum 7 years of data (captures multiple cycles)
- Walk-forward validation (no look-ahead bias)
- Compare against Buy & Hold benchmark

**Metrics to Evaluate:**
| Metric | Threshold | Notes |
|--------|-----------|-------|
| Total Return | > B&H | Must beat passive holding |
| CAGR | > 30% | Sustainable growth |
| Sharpe Ratio | > 1.0 | Risk-adjusted returns |
| Max Drawdown | < 50% | Survivable losses |
| Win Rate | > 40% | Don't need to be right often |
| Trades/Year | 1-20 | Reasonable frequency |
| Avg Hold Period | > 7 days | Not noise trading |

**Scoring Formula:**
```
Score = CAGR × Sharpe × sqrt(Trades_per_Year)
```

### Stage 2: Forward Test (Out-of-Sample)

**Requirements:**
- Minimum 1 year of unseen data
- No parameter changes from backtest
- Real market conditions

**Pass Criteria (all must pass):**
1. ✅ Positive absolute return
2. ✅ Competitive with Buy & Hold (within 20%)
3. ✅ Generated expected number of trades
4. ✅ Win rate above minimum threshold

### Stage 3: Robustness Testing

**Tests to Run:**
1. **Parameter Sensitivity** - Does ±10% parameter change break strategy?
2. **Time Period Stability** - Does it work across different market regimes?
3. **Relaxed Conditions** - What happens with 2-of-3 instead of 3-of-3?
4. **Single Condition Analysis** - Which signal contributes most edge?

### Stage 4: Confluence Verification

Before deployment, verify the strategy has confluence:

**Checklist:**
- [ ] Multiple independent signal sources (not just SOPR family)
- [ ] Aligns with valuation models (entry below fair value)
- [ ] Supported by cost basis analysis
- [ ] Consistent with cycle context

---

## PART 4: POSITION SIZING FRAMEWORK

### Valuation-Based Sizing

Position size should scale with conviction, which comes from valuation:

| Valuation Zone | Price Relative To | Multiplier |
|----------------|-------------------|------------|
| Extreme Bear | Below Realized Price | 2.0x |
| Undervalued | RP → True Market Mean | 1.5x |
| Fair Value | TMM → STH Cost Basis | 1.0x |
| Overvalued | Above STH Cost Basis | 0.5x |
| Extreme Bull | Above Vaulted Price | 0.25x |

### Confluence-Based Sizing

Additional multiplier based on signal strength:

| Confluence | Multiplier |
|------------|------------|
| 1-2 signals | 0.5x |
| 3 signals | 1.0x |
| 4+ signals | 1.25x |

### Final Position Size
```
Position = Base_Allocation × Valuation_Mult × Confluence_Mult

Example:
  Base = 10% of portfolio
  Valuation = Fair Value (1.0x)
  Confluence = 4 signals (1.25x)
  → Position = 10% × 1.0 × 1.25 = 12.5%
```

---

## PART 5: STRATEGY IDEAS TO EXPLORE

Based on the framework, here are untested strategy ideas:

### Idea 1: LTH Distribution Exit
**Hypothesis:** Long-term holders distribute into bull market tops
**Metrics:**
- LTH-SOPR > 1.5 (LTH taking profits)
- LTH Supply declining
- Price > Vaulted Price
**Use:** Exit signal for STRAT-002

### Idea 2: Miner Capitulation Entry
**Hypothesis:** Miner stress creates buying opportunities
**Metrics:**
- Hash Ribbon inversion (hashrate declining)
- Miner outflows elevated
- Price < Difficulty Regression
**Use:** Additional entry confirmation

### Idea 3: ETF Flow Momentum
**Hypothesis:** Sustained ETF inflows confirm trend
**Metrics:**
- ETF net inflows positive for 5+ days
- Price above 200D MA
- MVRV-Z < 2
**Use:** Trend following overlay

### Idea 4: Whale Accumulation
**Hypothesis:** Large wallet accumulation precedes rallies
**Metrics:**
- Whale balance increasing
- Exchange balance decreasing
- Price below TMM
**Use:** Accumulation confirmation

### Idea 5: Realized Loss Exhaustion
**Hypothesis:** Extreme realized losses mark bottoms
**Metrics:**
- Realized Loss Z-score > 2
- SOPR < 0.95 (deep losses)
- Price < Realized Price
**Use:** Extreme bear market entry

---

## PART 6: WORKFLOW CHECKLIST

### New Strategy Development

1. **Define Behavior**
   - [ ] What market behavior are you capturing?
   - [ ] Who is acting? (cohort)
   - [ ] What are they doing? (accumulating/distributing)
   - [ ] When does this happen? (cycle phase)

2. **Select Metrics**
   - [ ] Chose Spent Volume metric (actionable)
   - [ ] Chose Realized P/L metric (decisions)
   - [ ] Identified relevant cohort
   - [ ] Added independent confirmation sources

3. **Backtest**
   - [ ] 7+ years of data
   - [ ] Walk-forward validation
   - [ ] Beats Buy & Hold
   - [ ] Sharpe > 1.0
   - [ ] Reasonable trade frequency

4. **Forward Test**
   - [ ] 1+ year out-of-sample
   - [ ] No parameter changes
   - [ ] Passed all 4 criteria

5. **Robustness**
   - [ ] Parameter sensitivity tested
   - [ ] Works across market regimes
   - [ ] Relaxed conditions tested
   - [ ] Single condition analysis done

6. **Confluence Check**
   - [ ] 3+ independent confirmations
   - [ ] Aligns with valuation models
   - [ ] Supported by cost basis
   - [ ] Matches cycle context

7. **Document**
   - [ ] Strategy definition saved
   - [ ] Backtest results archived
   - [ ] Added to dashboard
   - [ ] RESEARCH_PRINCIPLES.md updated

---

## APPENDIX: Validated Strategies

### STRAT-002 (Macro Capitulation)
- **Entry:** SOPR < 1 AND STH-SOPR < 1 AND RL Z > 0.5
- **Exit:** 30% trailing stop
- **Timeframe:** Daily
- **Performance:** +5,754% to +7,827% (backtest), 8 trades/7yr

### STRAT-004 (Income Generation)
- **Entry:** SOPR < 1 AND STH-SOPR < 1 AND RL Z > 0.5
- **Exit:** 12% trailing stop
- **Timeframe:** 1 Hour
- **Performance:** +3,129% (backtest), +134% (forward test), ~15 trades/yr

---

## Key Reminders

1. **Spent Volume > Unspent Supply** for actionable signals
2. **Realized P/L > Unrealized P/L** for trading decisions
3. **Confluence is mandatory** - never trade single indicators
4. **Valuation context matters** - size positions accordingly
5. **Forward test everything** - backtest is necessary but not sufficient
6. **Document everything** - future you will thank present you

---

*Framework Version: 1.0*
*Last Updated: 2025-01-16*
*Based on: Checkonchain Framework (James Check), Bitcoin Lab API*
