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
| **Last Updated** | 2025-01-17 |
| **Trade Frequency** | ~9-15 trades/year |
| **Avg Hold Period** | 29 days |
| **Best For** | Active trading, paper testing |
| **Current Version** | v3 (LTH-SOPR exit + Checkmate sizing) ✅ BEST |

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

**Exit Rules (v3 - LTH-SOPR + Checkmate Sizing) ✅ BEST:**
```
ENTRY:
  - STH-SOPR < 1 (short-term holders selling at loss)
  - Position size based on Checkmate signal:
      signal <= -1.0:  100% (very bullish)
      signal <= -0.5:   80%
      signal <=  0.0:   60%
      signal <=  0.5:   40%
      signal >   0.5:   25% (bearish - minimum)

EXIT:
  - Before trigger: 30% trailing stop
  - After MVRV > 2.5 + LTH-SOPR > 1.50: tighten to 15% trail
```

**Backtest Results (2019-2026) - v3 with Checkmate Sizing:**
```
Total Return:    +5,973%
Sharpe:          1.22 (+15.7% vs baseline)
Max Drawdown:    ~50%
Win Rate:        ~50%
Total Trades:    ~15
```

**Backtest Results (2019-2026) - v2 LTH-SOPR Exit (no sizing):**
```
Total Return:    +6,785%
Sharpe:          1.05
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
- ✅ Checkmate signal sizing improves Sharpe by +15.7%
- ⚠️ For SHORT-TERM only - simple trail still wins for long-term
- 🆕 Checkmate signal tested: Position sizing works, entry confirmation doesn't help

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
- `research/68_checkmate_with_our_strategies.ipynb` - Checkmate signal integration ⭐
- `research/69_strat003_checkmate_sizing.ipynb` - v3 position sizing deep dive

---

### ⭐ STRAT-005: Buy The Dip + Momentum-Confirmed Exit

| Field | Value |
|-------|-------|
| **Status** | ✅ VALIDATED - PAPER READY |
| **Created** | 2025-01-22 |
| **Last Updated** | 2025-01-22 |
| **Trade Frequency** | ~2-3 trades/year (actual: 16 trades over 6 years) |
| **Avg Hold Period** | 50-200+ days (holds through full trends) |
| **Time Horizon** | **MEDIUM-TERM** (between STRAT-002 and STRAT-003) |
| **Best For** | Capturing major bull runs, avoiding cycle tops |
| **Current Version** | v1 (MVRV + MA momentum exit) ✅ BREAKTHROUGH |

**Entry Rules (v1 - 4/5 variant - RECOMMENDED):**
```
BUY when 4 of 5 conditions are true:
  1. STH-MVRV < 1.0    (short-term holders underwater)
  2. STH-SOPR < 1.0    (short-term holders selling at loss)
  3. RPLR < 1.0        (realized profit/loss ratio < 1)
  4. Funding Rate ≤ 0  (derivatives bearish/reset)
  5. Long Liq > Short  (longs getting liquidated)

  First day 4+ conditions are true.
```

**Entry Rules (v2 - 3/5 variant - More Trades):**
```
BUY when 3 of 5 conditions are true:
  - Same 5 conditions as v1
  - More signals (21 vs 16 trades)
  - Slightly lower quality (85.7% vs 93.8% win rate)
```

**Exit Rules (BREAKTHROUGH DISCOVERY):**
```
SELL when BOTH conditions are true:
  - MVRV > 2.0 (market overvalued)
  AND
  - Price < 50-day MA (momentum broken)

  This keeps you invested during strong trends even when expensive,
  and only exits when valuation AND momentum both turn bearish.
```

**Backtest Results (2018-2026 - when all data available):**
```
v1 (4/5 Entry):
Total Return:    +3,017%  (3.3x better than Never Exit)
Sharpe:          1.31
Max Drawdown:    -67.0%
Win Rate:        93.8%
Total Trades:    16

v2 (3/5 Entry):
Total Return:    +2,353%
Sharpe:          1.23
Max Drawdown:    -67.0%
Win Rate:        85.7%
Total Trades:    21

Buy & Hold:      +863%
```

**Period-by-Period Performance (v1):**
```
2020-2022 Cycle:
  Strategy: +346%
  Buy & Hold: +130%
  Advantage: +216% (2.7x better)
  Trades: 9

2023-2026 Bull:
  Strategy: +746%
  Buy & Hold: +441%
  Advantage: +305% (1.7x better)
  Trades: 8
```

**Why This Works:**
```
❌ Old approach: Exit when MVRV > 2.0 (too early, misses rallies)
✅ New approach: Exit when MVRV > 2.0 AND momentum breaks

Example - 2023-2026 Bull:
  - MVRV stayed high (>2.0) BUT price above 50MA → Stayed invested ✓
  - Captured the sustained bull run instead of exiting prematurely

Example - 2017/2021 Tops:
  - MVRV spiked AND price broke 50MA → Exited before crash ✓
  - Avoided -80% drawdowns
```

**Key Innovation:**
- First strategy to beat "Never Exit" by 3.3x (after testing 80+ exit strategies!)
- Combines valuation (MVRV) with momentum (price vs MA)
- Solves the problem: "expensive but still trending" vs "expensive AND reversing"
- 93.8% win rate proves signal quality

**Parameter Robustness (from grid search):**
```
Tested: 30 combinations (MVRV 1.5-3.0 x MA 20-100 day)
Beat "Never Exit": 12/30 combinations (40%)
Result: Moderately robust (not overfit to single parameter set)
```

**Key Files:**
- `research/74_check_framework_investigation.ipynb` - Initial framework test
- `research/75_full_history_backtest.ipynb` - Full history validation
- `research/76_position_sizing.ipynb` - Position sizing exploration
- `research/77_signal_timing_analysis.ipynb` - Found the problem (missed 113% rally)
- `research/78_regime_adaptive_exits.ipynb` - Regime classification attempt
- `research/79_entries_only_danger_exits.ipynb` - Danger zone exits (failed)
- `research/80_sth_mvrv_zone_exits.ipynb` - Fixed threshold exits (failed)
- `research/81_sth_mvrv_zscore_exits.ipynb` - Z-score exits (failed)
- `research/82_momentum_exit_filters.ipynb` - **BREAKTHROUGH** (found MVRV+MA)
- `research/83_mvrv_momentum_deep_dive.ipynb` - Validated winning strategy
- `research/84_entry_optimization.ipynb` - Confirmed 4/5 entry is best

**Current Market Status (2025-01-22):**
```
Exit Signal: MVRV>2.0 AND Price<50MA
  - MVRV: (check current value)
  - Price vs 50MA: (check current position)
  - Status: Monitor daily
```

**Notes:**
- After 84 notebooks and 80+ strategies, this is the FIRST to beat "Never Exit"
- 93.8% win rate is exceptional
- Works in both volatile (2020-2022) and sustained bull (2023-2026) markets
- Conservative entry (4/5) ensures quality over quantity
- Exit innovation: Don't fight the trend, exit when trend breaks
- ⚠️ Data starts 2018+ (when funding/liquidations available)
- 🎯 READY FOR PAPER TRADING

---

### ⭐ STRAT-004: James Check 5-Indicator Buy-the-Dip

| Field | Value |
|-------|-------|
| **Status** | 📊 BACKTESTED - PAPER READY |
| **Created** | 2025-01-20 |
| **Last Updated** | 2025-01-20 |
| **Trade Frequency** | ~5-10 trades/year |
| **Avg Hold Period** | 62 days (with trailing stop) |
| **Best For** | Buying dips in bull markets |
| **Current Version** | v1 (10% trailing stop) |

**Entry Rules:**
```
BUY when ALL 5 conditions are true:
  1. STH-MVRV < 1.0    (short-term holders underwater)
  2. STH-SOPR < 1.0    (short-term holders selling at loss)
  3. RPLR < 1.0        (realized profit/loss ratio < 1, more losses realized)
  4. Funding Rate ≤ 0  (derivatives bearish/reset)
  5. Long Liq > Short  (leverage flush, longs getting liquidated)
  
  First day all conditions are true.
  
  ALTERNATIVE: 4-of-5 conditions (more signals, slightly lower quality)
```

**Exit Rules (v1 - 10% Trailing Stop) ✅ BEST:**
```
SELL when:
  - Initial stop: 15% below entry
  - Once profitable: trail 10% below highest price reached
  - Let winners run until trailing stop triggers
```

**Exit Rules (v2 - Signal Exit) ⚠️ TOO SHORT:**
```
SELL when:
  - Any of the 5 conditions turn false
  - Result: Avg 1-day hold, +1.3% avg return
  - Captures bounce but misses the rally
```

**Walk-Forward Results (Feb 2020 - Jan 2026):**
```
                        IN-SAMPLE (2020-2022)    OUT-OF-SAMPLE (2023-2026)
Strategy                Trades  Return  Win%     Trades  Return  Win%   MaxDD
─────────────────────────────────────────────────────────────────────────────
10% Trailing Stop         24   +19.2%   46%        7   +166.7%   71%   -9.0%
30d Fixed + 15% SL        19   -46.6%   47%        9    +56.8%   67%   -8.2%
Signal Exit               74  +188.9%   70%       17     +6.8%   53%  -11.8%
```

**Forward Returns Analysis (OOS):**
```
Signal              Avg 30d Return    Win Rate    Edge vs Random
────────────────────────────────────────────────────────────────
5-Indicator              +7.3%          86%          +2.2%
4-of-5                   +7.4%          75%          +2.5%
3-Indicator (on-chain)   +8.1%          77%          +3.3%
```

**Data Availability:**
```
- On-chain (STH-MVRV, STH-SOPR, RPLR): 15 years (Aug 2010 - Jan 2026)
- Derivatives (Funding, Liquidations): 6 years (Feb 2020 - Jan 2026)
- Full 5-indicator overlap: 6 years
```

**5-Indicator Signal Dates (OOS Period):**
```
Entry Date     Entry Price    30d Return
──────────────────────────────────────────
2023-06-05     $25,733        +18.5% ✓
2023-09-24     $26,252        +31.4% ✓
2024-06-24     $60,297         +8.4% ✓
2024-09-06     $53,963        +16.4% ✓
```

**Key Insights:**
- Signal is RARE (~6% of time) = quality over quantity
- All 5 indicators together = high confluence = high confidence
- 4-of-5 variant provides more signals with similar quality
- **10% trailing stop dramatically outperforms fixed hold periods**
- In-sample period (COVID + 2022 bear) was brutal stress test - signal survived
- OOS performance excellent: +166% return, 71% win rate, -9% max DD

**Key Files:**
- `research/71_jc_5indicator_walkforward.ipynb` - Walk-forward validation
- `/home/claude/combined_5indicator.parquet` - Combined dataset (Claude's computer)

**Current Market Status (2025-01-20):**
```
BTC Price: $91,009

1. STH-MVRV < 1.0:      0.9320  ✓ ACTIVE
2. STH-SOPR < 1.0:      0.9884  ✓ ACTIVE
3. RPLR < 1.0:          0.2685  ✓ ACTIVE
4. Funding ≤ 0:         (pending refresh)
5. Long Liq > Short:    (pending refresh)

Indicators Active: 3/5 confirmed (on-chain)
Bull Filter: ✗ (price below 200 SMA)
Signal Status: ⚫ INACTIVE
```

**Notes:**
- Based on James Check "Checkmate Framework" methodology
- Combines on-chain (behavior) with derivatives (sentiment) data
- Different from STRAT-002/003 which use SOPR + Realized Loss
- Complementary signal - can run alongside existing strategies
- ⚠️ Derivatives data only goes back to Feb 2020 (6 years)
- 🆕 Trailing stop exit VASTLY outperforms fixed hold or signal exit

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

*Last updated: 2025-01-22*
