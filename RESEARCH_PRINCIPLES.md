# Bitcoin Trading Research - Operational Guide

> **Full Framework:** See `STRATEGY_FRAMEWORK.md` for comprehensive documentation
> **Quick Reference:** See `QUICK_REFERENCE.md` for cheat sheet

---

## Core Principles

### 1. The Checkonchain Framework
Every metric is a cross-section of Bitcoin supply across 3 axes:
- **X-Axis:** Unspent Supply (lagging) vs Spent Volume (actionable)
- **Y-Axis:** Profit/Loss (unrealized=pressure, realized=decisions)
- **Z-Axis:** Cohorts (LTH, STH, Miners, Exchanges, etc.)

**For trading signals: Use SPENT VOLUME + REALIZED P/L**

### 2. The Confluence Principle
> "Whenever we can identify confluence between several models, it can help to add confidence about the trends playing out." — James Check

**Never trade single indicators. Require 4+ confirmations for full positions.**

### 3. Valuation-Based Sizing
Position size scales with how cheap/expensive the market is relative to cost basis models.

---

## Data Source

**Bitcoin Lab API ONLY** (https://api.researchbitcoin.net)
- See `config/metrics.yaml` for metric registry
- Supports: d1, h1, h4, h8, h12 resolutions

---

## Active Strategies

### STRAT-002: Macro Capitulation
```
Entry: SOPR < 1 AND STH-SOPR < 1 AND RL_Z > 0.5
Exit:  30% trailing stop
TF:    Daily
Freq:  ~2 trades/year
```

### STRAT-004: Income Generation
```
Entry: SOPR < 1 AND STH-SOPR < 1 AND RL_Z > 0.5
Exit:  12% trailing stop  
TF:    1 Hour
Freq:  ~15 trades/year
```

**What the signal means:**
"Short-term holders are spending their coins at a loss, and the magnitude of realized losses is elevated."

This is capitulation. This is when to buy.

---

## Position Sizing

| Valuation Zone | Condition | Multiplier |
|----------------|-----------|------------|
| Extreme Bear | Price < Realized Price | 2.0x |
| Undervalued | Price < True Market Mean | 1.5x |
| Fair Value | Price < STH Cost Basis | 1.0x |
| Overvalued | Price > STH Cost Basis | 0.5x |
| Extreme Bull | Price > Vaulted Price | 0.25x |

---

## New Strategy Workflow

1. **Define** - What behavior are you capturing? (See Framework Part 2)
2. **Build** - Select metrics across all 3 axes
3. **Backtest** - 7+ years, walk-forward, beat B&H
4. **Forward Test** - 1+ year out-of-sample
5. **Confluence Check** - 4+ independent confirmations
6. **Document** - Update this guide and dashboard

---

## Key Files

| File | Purpose |
|------|---------|
| `STRATEGY_FRAMEWORK.md` | Complete framework documentation |
| `QUICK_REFERENCE.md` | One-page cheat sheet |
| `config/metrics.yaml` | Bitcoin Lab API metric registry |
| `research/dashboard.py` | Live signal dashboard |
| `research/57_valuation_models.ipynb` | Valuation analysis |

---

## Lessons Learned

1. Spent Volume metrics > Unspent Supply for trading
2. Realized P/L > Unrealized P/L for decisions
3. ALL 3 entry conditions optimal (don't relax to 2-of-3)
4. Same entry, different exits = different strategies
5. Tighter trails = more trades, similar CAGR
6. STH-SOPR most predictive single indicator
7. Forward testing is essential (backtest ≠ reality)
8. $81-90k is fair value (multiple models converge, Jan 2025)

---

*Last Updated: 2025-01-16*
