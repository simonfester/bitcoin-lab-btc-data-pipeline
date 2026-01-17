# Strategy Registry

A structured tracker for strategies from exploration → paper testing → live.

---

## 📊 Status Definitions

| Status | Meaning |
|--------|---------|
| 🔬 EXPLORING | Initial idea, still testing |
| 📊 BACKTESTED | Walk-forward complete, results documented |
| ⏳ PAPER-READY | Meets criteria, ready for paper trading |
| 📝 PAPER-TESTING | Currently paper trading |
| ✅ LIVE | Running with real capital |
| ❌ ABANDONED | Tested, didn't work |
| 💤 PAUSED | Was promising, need to revisit |

---

## 🎯 Criteria for Paper-Ready

A strategy must have:
- [x] Walk-forward beat rate > 55%
- [x] Tested across multiple parameter values (robustness check)
- [x] Clear entry rules (no ambiguity)
- [x] Clear exit rules (no ambiguity)
- [x] Documented in LESSONS_LEARNED.md
- [x] **Regime filter tested** (result: not needed for contrarian strategies)

---

## 📋 Strategy Registry

### ⭐ STRAT-002: SOPR + Realized Loss + Simple Trail (LONG-TERM)

| Field | Value |
|-------|-------|
| **Status** | ✅ VALIDATED - DEPLOY & FORGET |
| **Created** | 2025-01-10 |
| **Last Updated** | 2025-01-11 |
| **Trade Frequency** | ~1-2 trades/year |
| **Avg Hold Period** | 300-500 days |
| **Best For** | Long-term wealth building |
| **Current Version** | v5 (simple trail) ✅ CONFIRMED BEST |

**Entry Rules:**
```
BUY when:
  - SOPR < 1 (market selling at loss)
  - AND STH_SOPR < 1 (short-term holders also selling at loss)
  - AND Realized Loss Z-Score > 0.5 (above average losses being realized)
  - First day all conditions are true (not continuation)
```

**Exit Rules (v5 - Current):**
```
SELL when:
  - Price drops 30% from peak (simple trailing stop, always active)
  - That's it. No MVRV trigger, no stop loss, no time limit.
```

**Exit Rules (v6 - Testing):**
```
SELL when:
  - Before trigger: 30% trailing stop
  - After MVRV > 2.0 + SOPR > 1.05: tighten to 15-20% trail
  - Uses REALIZED profit-taking as exit signal
```

**Backtest Results (2019-2026) - v5 VectorBT Validated:**
```
Total Return:    +5,754%
Buy & Hold:      +2,268%
CAGR:            +77.8%

Sharpe:          1.45
Sortino:         2.21
Win Rate:        62%
Profit Factor:   6.69
Max Drawdown:    -63.8%
Total Trades:    8

$100,000 → $5,853,745
```

**Key Files:**
- `research/21_realized_loss_entry.ipynb` - Entry signal discovery
- `research/31_exit_strategy_comparison.ipynb` - Exit comparison (found simple > MVRV)
- `research/41_historical_bottoms_analysis.ipynb` - Bottom analysis (100% caught)
- `research/42_historical_tops_analysis.ipynb` - Top analysis (exit timing)
- `research/44_realized_profit_exit.ipynb` - Realized exit discovery
- `research/45_strat002_v6_realized_exit.ipynb` - v6 comparison test
- `research/46_lth_sopr_exit.ipynb` - LTH-SOPR exit test (simple still won for long-term)
- `research/47_mvrvz_lth_exit.ipynb` - MVRV Z test (simple still won, but Z > raw MVRV)
- `research/48_realized_price_stop.ipynb` - RP stop test (REJECTED - marks bottoms not tops)
- `data/strat002_backtest_results.json` - Full results

**Notes:**
- Simple 30% trail DOUBLED returns vs complex MVRV trail (+7,298% vs +3,643%)
- Removed MVRV trigger - was causing edge case losses
- Removed stop loss - trail handles all exits
- Simpler = fewer edge cases = better performance
- ✅ Principle confirmed: "Simpler is better"
- ⚠️ **NOT for paper trading** - too infrequent, just deploy and monitor
- Currently has 1 open position (as of 2025-01-11)
- 🆕 v6 tested: Realized exit works for SHORT-term (+31% better) but NOT long-term (simple trail won by +2,000%)
- 🆕 LTH-SOPR exit tested: Also works for SHORT-term (+28% better) but NOT long-term (+7,827% vs +4,974%)
- 🆕 MVRV Z tested: Beats raw MVRV by +528% for triggered exits, but simple trail still wins (+6,122% vs +4,409%)

---

### ⭐ STRAT-003: Short-Term Active Trading

| Field | Value |
|-------|-------|
| **Status** | ✅ VALIDATED - PAPER READY |
| **Created** | 2025-01-11 |
| **Last Updated** | 2025-01-12 |
| **Trade Frequency** | ~9-15 trades/year |
| **Avg Hold Period** | 29 days |
| **Best For** | Active trading, paper testing |
| **Current Version** | v2 (LTH-SOPR exit) ✅ BEST |

**Entry Rules:**
```
BUY when:
  - STH-SOPR < 1 (short-term holders selling at loss)
  - First day condition is true
```

**Exit Rules (v1 - Simple):**
```
SELL when:
  - Price drops 8% from peak (tight trailing stop)
  - Return: +2,970%
```

**Exit Rules (v2 - LTH-SOPR) ✅ BEST:**
```
SELL when:
  - Before trigger: 30% trailing stop
  - After MVRV > 2.5 + LTH-SOPR > 1.50: tighten to 15% trail
  - Return: +3,813% (+28% improvement over simple)
```

**Exit Rules (v3 - MVRV Z + LTH) Alternative:**
```
SELL when:
  - Before trigger: 30% trailing stop
  - After MVRV Z > 2.5 + LTH-SOPR > 1.50: tighten to 15% trail
  - MVRV Z adapts to market structure changes
  - Return: +2,734% (MVRV Z > raw MVRV by +528% in controlled test)
```

**Backtest Results (2019-2026) - v2 LTH-SOPR Exit:**
```
Total Return:    +3,813%
Sharpe:          ~0.7
Max Drawdown:    ~55%
Win Rate:        ~50%
Total Trades:    ~15
```

**Key Insights:**
- Entry: STH-SOPR < 1 (weak hands capitulating)
- Exit: LTH-SOPR > 1.5 (smart money distributing)
- LTH-SOPR at major tops: ~5.0 (vs STH-SOPR ~1.03)
- LTH-SOPR is 5x stronger signal than STH-SOPR at tops!
- ✅ LTH-SOPR exit beat simple trail by +28%
- ⚠️ For SHORT-TERM only - simple trail still wins for long-term

**Why LTH-SOPR Works for Exits:**
```
STH-SOPR > 1.05 = Traders taking small profit (noisy, always ~1.0)
LTH-SOPR > 1.50 = HODLers taking BIG profit (rare, deliberate)
                = Smart money distribution
                = Real cycle top signal
```

**Key Files:**
- `research/40_sth_sopr_only.ipynb` - STH-SOPR entry test
- `research/41_historical_bottoms_analysis.ipynb` - Bottom analysis
- `research/42_historical_tops_analysis.ipynb` - Top analysis  
- `research/43_adaptive_trail_strategy.ipynb` - Adaptive trail tests
- `research/44_realized_profit_exit.ipynb` - Realized exit theory
- `research/46_lth_sopr_exit.ipynb` - LTH-SOPR exit discovery ⭐
- `research/47_mvrvz_lth_exit.ipynb` - MVRV Z vs raw MVRV comparison
- `research/48_realized_price_stop.ipynb` - RP stop test (REJECTED)

---

### STRAT-001: SOPR Double Capitulation + MVRV Trail (Original)

| Field | Value |
|-------|-------|
| **Status** | ⏳ PAPER-READY |
| **Created** | 2025-01-09 |
| **Last Updated** | 2025-01-10 |
| **Beat Rate** | 62% |
| **Robustness** | 32/35 configs beat baseline (91%) |

**Entry Rules:**
```
BUY when:
  - SOPR < 1 (market selling at loss)
  - AND STH_SOPR < 1 (short-term holders also selling at loss)
  - First day both conditions are true (not continuation)
```

**Exit Rules:**
```
SELL when:
  - MVRV > 2.25 triggers 20% trailing stop from peak
  - OR price drops 20% from entry (stop loss)
  - OR 365 days pass (max hold)
```

**Key Files:**
- `research/18_mvrv_grid_search.ipynb` - Final optimization
- `data/mvrv_grid_search_results.json` - Results

**Notes:**
- Simpler entry (no RL filter)
- Higher robustness (91% vs 53%) but lower beat rate
- Good fallback if STRAT-002 underperforms in paper trading
- ✅ **Regime filter tested** - not needed (contrarian signal + stop-loss provides protection)

---

## 💡 Ideas Backlog

Ideas to explore, not yet tested:

| ID | Idea | Priority | Notes |
|----|------|----------|-------|
| **IDEA-008** | **Metric Group Analysis** | **HIGH** | Group metrics by type, find best from each, combine across groups |
| IDEA-005 | LTH/STH ratio extremes | Medium | Supply dynamics |
| IDEA-006 | NVT extremes | Low | Valuation signal |

### IDEA-008: Metric Grouping Strategy

**Concept:** Categorize metrics by what they measure, find the best signal from each category, then combine signals across categories (which should be uncorrelated).

**Current Progress:**

| Category | What It Measures | Best Metric | Status |
|----------|------------------|-------------|--------|
| **Profitability/Sentiment** | Are people in profit/loss? | SOPR + STH-SOPR | ✅ Done |
| **Capitulation Intensity** | How much loss is being realized? | RL Z > 0.5 | ✅ Done |
| **Valuation** | Is market over/undervalued? | MVRV > 2.0 (exit) | ✅ Done |
| **Supply Distribution** | Who holds the coins? | TBD | 🔬 Next |
| **Network Activity** | Is network being used? | TBD | Backlog |
| **Cost Basis** | What did people pay? | TBD | Backlog |

**Current Best Combined Strategy:**
- Entry: Profitability (SOPR) + Intensity (RL Z)
- Exit: Valuation (MVRV)
- Result: 67% beat rate

---

## ❌ Abandoned Strategies

Strategies tested and rejected (so we don't re-test them):

| ID | Strategy | Beat Rate | Why Abandoned |
|----|----------|-----------|---------------|
| ABN-001 | Liveliness < threshold | 12.5% | Signal too slow, use as filter only |
| ABN-002 | SOPR + Price > 200 MA filter | Worse | Filter removes best contrarian entries |
| ABN-003 | SOPR + Distance from high filter | 54% | No improvement over baseline |
| ABN-004 | SOPR exit on SOPR > 1.02 | 54% | No improvement, sentiment too noisy |
| ABN-005 | MVRV > 3.0 hard exit | 62%* | *Misleading - stop loss did the work, MVRV only fired 2x |
| ABN-006 | Supply in Profit < 50% entry | 38% | Too rare, less timely than SOPR (lagging stock vs flow) |
| ABN-007 | SOPR + SIP filter | 54% | Adding SIP filter reduces beat rate from 62% to 54% |
| ABN-008 | MVRV Z-Score < 0 entry | 42% | Worse than SOPR, valuation signal too slow for entry |
| ABN-009 | SOPR + MVRV Z filter | 58% | Filter reduces beat rate from 62% to 58% |
| ABN-010 | MVRV Z > 2.5 exit | 62% | Ties MVRV > 2.25, no improvement - same signal type |
| ABN-011 | NUPL > 0.75 exit | 54% | Worse than MVRV, 0.90 correlated (redundant) |
| ABN-012 | Realized Price stop | -2,511% | RP marks BOTTOMS not tops! Sells at worst time. |

---

## 📝 Paper Trading Log

When a strategy moves to paper testing, log trades here:

### STRAT-002 Paper Trades (Primary)

| Date | Action | Price | SOPR | STH_SOPR | RL Z | MVRV | Notes |
|------|--------|-------|------|----------|------|------|-------|
| | | | | | | | |

### STRAT-001 Paper Trades (Backup)

| Date | Action | Price | SOPR | STH_SOPR | MVRV | Notes |
|------|--------|-------|------|----------|------|-------|
| | | | | | | |

---

## 🔄 Review Schedule

- **Weekly:** Check if any EXPLORING strategies are ready for BACKTESTED
- **Monthly:** Review PAPER-TESTING results
- **Quarterly:** Decide on LIVE promotion

---

*Last updated: 2025-01-12*
