# Strategy Framework - Quick Reference Card

## The 3 Axes (Checkonchain)

```
X-Axis: SUPPLY (lagging) vs VOLUME (actionable) → Choose VOLUME for trading
Y-Axis: PROFIT vs LOSS → Choose REALIZED P/L (actual decisions)
Z-Axis: COHORTS → Choose relevant group (STH, LTH, Miners, etc.)
```

## Signal Construction Formula

```
ENTRY = Spent_Volume_Metric + Realized_PL_Condition + Cohort_Filter + Confirmation

Example (STRAT-002/004):
  SOPR (spent volume)
  + < 1 (realized loss)  
  + STH (cohort)
  + RL Z > 0.5 (confirmation)
  = "Short-term holders spending at a loss with elevated loss magnitude"
```

## Confluence Requirements

| Level | Signals | Action |
|-------|---------|--------|
| 1 | Monitor | No trade |
| 2-3 | Small position | Tight stops |
| **4+** | **Full position** | **High conviction** |

## Valuation Zones & Position Sizing

| Zone | Price Level | Multiplier |
|------|-------------|------------|
| 🔴 Extreme Bear | < Realized Price | 2.0x |
| 🟠 Undervalued | < True Market Mean | 1.5x |
| 🟢 Fair Value | < STH Cost Basis | 1.0x |
| 🟡 Overvalued | > STH Cost Basis | 0.5x |
| 🟣 Extreme Bull | > Vaulted Price | 0.25x |

## Validation Checklist

**Backtest (7+ years):**
- [ ] Beats Buy & Hold
- [ ] Sharpe > 1.0
- [ ] Max DD < 50%
- [ ] 1-20 trades/year

**Forward Test (1+ year):**
- [ ] Positive return
- [ ] Competitive with B&H
- [ ] Expected trade count
- [ ] Win rate > threshold

## Active Strategies

| Strategy | Entry | Exit | Frequency |
|----------|-------|------|-----------|
| STRAT-002 | SOPR<1 + STH-SOPR<1 + RL_Z>0.5 | 30% trail | ~2/year |
| STRAT-004 | Same | 12% trail | ~15/year |

## Golden Rules

1. **VOLUME > SUPPLY** for signals (actionable vs lagging)
2. **REALIZED > UNREALIZED** for decisions (actions vs pressure)
3. **CONFLUENCE IS MANDATORY** (never single indicators)
4. **SIZE BY VALUATION** (bigger when cheaper)
5. **FORWARD TEST EVERYTHING** (backtest ≠ reality)

---
*See STRATEGY_FRAMEWORK.md for full documentation*
