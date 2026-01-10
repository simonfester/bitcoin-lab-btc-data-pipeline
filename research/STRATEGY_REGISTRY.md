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
- [ ] Walk-forward beat rate > 55%
- [ ] Tested across multiple parameter values (robustness check)
- [ ] Clear entry rules (no ambiguity)
- [ ] Clear exit rules (no ambiguity)
- [ ] Documented in LESSONS_LEARNED.md

---

## 📋 Strategy Registry

### STRAT-001: SOPR Double Capitulation + MVRV Trail

| Field | Value |
|-------|-------|
| **Status** | ⏳ PAPER-READY |
| **Created** | 2025-01-09 |
| **Last Updated** | 2025-01-10 |
| **Beat Rate** | 62% |
| **Robustness** | 32/35 configs beat baseline |

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
- Best single config: MVRV > 2.25, 20% trail
- Best on average: MVRV > 2.75, 30% trail
- Consider testing both in paper trading

---

### STRAT-002: [Template for Next Strategy]

| Field | Value |
|-------|-------|
| **Status** | 🔬 EXPLORING |
| **Created** | YYYY-MM-DD |
| **Last Updated** | YYYY-MM-DD |
| **Beat Rate** | TBD |
| **Robustness** | TBD |

**Entry Rules:**
```
TBD
```

**Exit Rules:**
```
TBD
```

**Key Files:**
- TBD

**Notes:**
- TBD

---

## 💡 Ideas Backlog

Ideas to explore, not yet tested:

| ID | Idea | Priority | Notes |
|----|------|----------|-------|
| IDEA-002 | MVRV Z-Score < 0 entry | High | Undervaluation signal |
| IDEA-003 | Realized Loss spike entry | Medium | Capitulation event |
| IDEA-004 | NUPL > 0.75 exit trigger | Medium | Alternative to MVRV |
| IDEA-005 | LTH/STH ratio extremes | Medium | Supply dynamics |
| IDEA-006 | NVT extremes | Low | Valuation signal |
| IDEA-007 | Multi-metric entry composite | Low | Combine SOPR + Supply + MVRV Z |

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
| ABN-006 | Supply in Profit < 50% entry | 38% | Too rare, less timely than SOPR (lagging) |
| ABN-007 | SOPR + SIP filter | 54% | Adding SIP filter reduces beat rate from 62% to 54% |

---

## 📝 Paper Trading Log

When a strategy moves to paper testing, log trades here:

### STRAT-001 Paper Trades

| Date | Action | Price | SOPR | STH_SOPR | MVRV | Notes |
|------|--------|-------|------|----------|------|-------|
| | | | | | | |

---

## 🔄 Review Schedule

- **Weekly:** Check if any EXPLORING strategies are ready for BACKTESTED
- **Monthly:** Review PAPER-TESTING results
- **Quarterly:** Decide on LIVE promotion

---

*Last updated: 2025-01-10*
