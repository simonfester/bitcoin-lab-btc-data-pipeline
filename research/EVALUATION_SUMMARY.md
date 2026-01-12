# STRAT-002 Evaluation Summary

**Last Updated:** 2025-01-10
**Status:** ✅ VectorBT Validated - Ready for Paper Trading

---

## Final Strategy Specification

### Entry Rules
```
BUY when ALL conditions are true:
  1. SOPR < 1 (market selling at loss)
  2. STH-SOPR < 1 (short-term holders selling at loss)  
  3. Realized Loss Z-Score > 0.5 (elevated capitulation)
  4. First day of signal (not continuation)
```

### Exit Rules
```
SELL when:
  - Price drops 30% from peak (trailing stop, always active)
  
That's it. One simple rule.
```

---

## VectorBT Validated Results

| Metric | Value |
|--------|-------|
| **Total Return** | +5,754% |
| **Buy & Hold** | +2,268% |
| **CAGR** | +77.8% |
| **Sharpe Ratio** | 1.45 |
| **Sortino Ratio** | 2.21 |
| **Win Rate** | 62% |
| **Profit Factor** | 6.69 |
| **Max Drawdown** | -63.8% |
| **Total Trades** | 8 |
| **Test Period** | 2019-01 to 2026-01 |
| **Final Equity** | $5,853,745 |

---

## Strategy Evolution

| Version | Change | Result | Date |
|---------|--------|--------|------|
| v1 | SOPR + trailing stop | 54% beat rate | 2025-01-09 |
| v2 | + MVRV > 2.25 exit trigger | 62% beat rate | 2025-01-10 |
| v3 | + Realized Loss Z-Score entry | 67% beat rate | 2025-01-10 |
| v4 | - Remove 365d max hold | +3,643% return | 2025-01-10 |
| **v5** | **Simple 30% trail (remove MVRV trigger)** | **+5,754% return** | **2025-01-10** |

---

## Tests Performed

### Entry Signal Tests

| Test | Signal | Result | Notes |
|------|--------|--------|-------|
| ✅ | SOPR < 1 + STH-SOPR < 1 | 62% beat rate | Baseline entry |
| ❌ | + Momentum filter (RSI > 30) | Worse | Removed best contrarian entries |
| ❌ | Supply in Profit < threshold | 38% beat rate | Too rare, lagging |
| ❌ | MVRV Z-Score < -1 | 42% beat rate | Valuation too slow for entry |
| ✅ | + Realized Loss Z > 0.5 | **67% beat rate** | Adds intensity to direction |

### Exit Strategy Tests

| Test | Exit Logic | Result | Notes |
|------|------------|--------|-------|
| ✅ | MVRV > 2.25 triggers 20% trail | 62% beat rate | Original |
| ✅ | MVRV > 2.0 triggers 25% trail | 67% beat rate | Slightly better |
| ❌ | NUPL > 0.6 exit | 54% beat rate | Redundant with MVRV |
| ❌ | Max 365 day hold | Hurt returns | Forced exit on winners |
| ✅ | **Simple 30% trail** | **+5,754%** | Best - no MVRV trigger needed |

### Robustness Tests

| Test | Result | Notes |
|------|--------|-------|
| Walk-forward validation | 67% beat rate | 3-year train, 1-year test |
| Parameter grid search | 74/140 configs beat baseline | 53% robustness |
| Regime filter test | No improvement | Not needed for contrarian |
| MVRV trail edge case fix | No improvement | Edge cases acceptable |

---

## Exit Strategy Comparison (Full Backtest)

| Strategy | Return | Sharpe | Notes |
|----------|--------|--------|-------|
| MVRV > 2.0 triggers 25% trail + 20% SL | +3,643% | 0.76 | Complex, edge cases |
| Simple 25% trail | +4,892% | ~1.2 | Better |
| **Simple 30% trail** | **+5,754%** | **1.45** | **Best** |
| Simple 20% trail | +4,100% | ~1.0 | Exits too early |
| Take profit 50% / Stop loss 20% | +2,100% | ~0.8 | Caps upside |
| MVRV > 2.5 hard exit | +3,200% | ~0.9 | Timing dependent |

---

## Key Lessons Learned

1. **Simpler is better** - Simple 30% trail beat complex MVRV trail by +58%
2. **Let winners run** - Removing max hold added +$1M to returns
3. **Combine orthogonal signals** - Direction (SOPR) + Intensity (RL) = best entry
4. **Avoid redundant metrics** - NUPL ≈ MVRV, don't stack them
5. **Contrarian doesn't need regime filters** - Stop loss provides protection
6. **On-chain for entry, price action for exit** - MVRV trigger added complexity without benefit

---

## Risk Considerations

| Risk | Mitigation |
|------|------------|
| 63.8% max drawdown | Position sizing, not all-in |
| Only 8 trades in 7 years | Patience required, diversify income |
| Overfitting to BTC cycles | Out-of-sample testing needed |
| On-chain data dependency | Multiple data sources for redundancy |
| Execution slippage | Use limit orders, not market |

---

## Implementation Checklist

- [x] Walk-forward validation
- [x] Robustness grid search
- [x] VectorBT backtest
- [x] Exit strategy comparison
- [x] Document lessons learned
- [ ] Build live monitoring
- [ ] Set up alerts
- [ ] Paper trade for 3-6 months
- [ ] Define position sizing rules
- [ ] Create execution playbook

---

## Files & Notebooks

| Notebook | Purpose |
|----------|---------|
| `21_realized_loss_entry.ipynb` | Entry signal discovery |
| `23_sopr_rl_robustness.ipynb` | Robustness grid search |
| `24_regime_filter_test.ipynb` | Regime filter testing |
| `31_exit_strategy_comparison.ipynb` | Exit comparison |
| `33_vectorbt_proper.ipynb` | Final VectorBT validation |

| Data File | Contents |
|-----------|----------|
| `strat002_v5_backtest_results.json` | Full backtest results |
| `sopr_rl_robustness_results.json` | Grid search results |
| `regime_filter_results.json` | Regime filter test |

---

## Next Steps

1. **Paper Trading Setup**
   - Daily signal check script
   - Alert when entry conditions fire
   - Track positions and P&L

2. **Additional Testing**
   - LTH/STH ratio metrics
   - Exchange flow signals
   - NVT variations

3. **Production Deployment**
   - Automated data pipeline
   - Signal monitoring dashboard
   - Position management tools

---

*Document maintained as part of bitcoin-lab research project*
