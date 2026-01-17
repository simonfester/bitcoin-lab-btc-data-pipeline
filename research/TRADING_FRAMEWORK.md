# Bitcoin Trading Framework v1.0

A systematic, backtested framework for automated Bitcoin trading.

---

## 🎯 Framework Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     MARKET CONTEXT                              │
│                  "Where are we in the cycle?"                   │
│                                                                 │
│   MVRV-Z < 0    │   MVRV-Z 0-2   │   MVRV-Z > 2               │
│   DEEP VALUE    │   FAIR VALUE   │   OVERVALUED               │
│   Accumulate    │   Hold/Trade   │   Distribution             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ENTRY SIGNALS                               │
│                  "When to buy?"                                 │
│                                                                 │
│   PRIMARY: Capitulation Detection                               │
│   SOPR < 1 AND STH-SOPR < 1 AND Realized Loss Z > 0.5          │
│                                                                 │
│   SECONDARY: Deep Value (untested, for consideration)           │
│   Price < True Market Mean OR Price < Realized Price           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     POSITION MANAGEMENT                         │
│                  "How to manage the trade?"                     │
│                                                                 │
│   LONG-TERM: 30% trailing stop (always active)                 │
│   SHORT-TERM: 8-15% trailing stop                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXIT SIGNALS                                │
│                  "When to sell?"                                │
│                                                                 │
│   LONG-TERM: Let trail do the work                             │
│   SHORT-TERM: LTH-SOPR > 1.5 → tighten trail to 15%           │
│                                                                 │
│   CONTEXT (not hard exits):                                     │
│   Price > Vaulted Price = entering distribution zone           │
│   AVIV > 1.5 = market getting expensive                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 The Three Layers

### Layer 1: CONTEXT (Where Are We?)

Context metrics tell you the market's current state but are NOT direct trading signals.

| Metric | Deep Value | Fair Value | Expensive | Euphoria |
|--------|------------|------------|-----------|----------|
| **MVRV-Z** | < 0 | 0 - 1.5 | 1.5 - 2.5 | > 2.5 |
| **MVRV** | < 1 | 1 - 2 | 2 - 3 | > 3 |
| **AVIV** | < 0.8 | 0.8 - 1.2 | 1.2 - 1.5 | > 1.5 |
| **NUPL** | < 0 | 0 - 0.5 | 0.5 - 0.75 | > 0.75 |

**Price vs Cost Basis Levels:**

| Level | Meaning | Historical Occurrence |
|-------|---------|----------------------|
| Price < Realized Price | Network underwater | Major bottoms only |
| Price < True Market Mean | Active investors underwater | Accumulation zones |
| Price > True Market Mean | Active investors in profit | Normal/bull market |
| Price > Vaulted Price | Entering HODLer distribution zone | Late bull market |

**How to Use Context:**
- Context informs POSITION SIZING, not entry/exit
- Deep Value → larger positions, more aggressive
- Euphoria → smaller positions, tighter stops
- Context NEVER overrides validated entry/exit signals

---

### Layer 2: ENTRY (When to Buy?)

Entry signals detect REALIZED behavior - actual on-chain actions, not potential.

#### Primary Entry: Capitulation Detection ✅ VALIDATED

```
SIGNAL: SOPR < 1 AND STH-SOPR < 1 AND Realized Loss Z > 0.5

MEANING:
  SOPR < 1         = People ARE selling at loss (direction)
  STH-SOPR < 1     = Short-term holders panicking (who)
  RL Z > 0.5       = Above-average losses (intensity)
  
COMBINED = "Meaningful capitulation is happening"
```

| Component | What It Detects | Why It Matters |
|-----------|-----------------|----------------|
| SOPR < 1 | Loss-taking | Confirms selling pressure |
| STH-SOPR < 1 | Weak hands | They capitulate first at bottoms |
| Realized Loss Z > 0.5 | Intensity | Filters noise from real capitulation |

**Backtest Results:**
- Beat Buy & Hold: 67% of periods
- Return: +5,754% to +7,827%
- Caught 100% of major bottoms

#### Secondary Entries (For Consideration - Not Yet Validated)

| Signal | Logic | Status |
|--------|-------|--------|
| Price < Realized Price | Network underwater = deep value | Untested as entry |
| Price < True Market Mean | Active investors underwater | Untested as entry |
| MVRV < 1 | Market cap < realized cap | Equivalent to Price < RP |

---

### Layer 3: EXIT (When to Sell?)

Exit signals must detect REVERSAL - actual price action, not just expensive valuations.

#### Long-Term Strategy: Simple Trail ✅ VALIDATED

```
EXIT: 30% trailing stop from peak (always active)

WHY IT WORKS:
  - No premature exits from "expensive" readings
  - Lets winners run to maximum
  - Only exits when price ACTUALLY reverses
  - Beat all complex exit strategies by 2x
```

**Backtest Results:**
- Return: +5,754% (vs +3,643% with MVRV trigger)
- Sharpe: 1.45
- Trades: 8 over 7 years

#### Short-Term Strategy: LTH-SOPR Trigger ✅ VALIDATED

```
EXIT: When LTH-SOPR > 1.5, tighten trail to 15%

WHY IT WORKS:
  - LTH-SOPR at tops: ~5.0 (vs STH-SOPR ~1.03)
  - Detects smart money distribution
  - 5x signal strength vs short-term noise
  - +28% improvement over simple trail
```

**Backtest Results:**
- Return: +3,813% (vs +2,970% simple trail)
- Better for frequent trading

#### Context for Exits (NOT Hard Exits)

| Metric | Level | Meaning | Action |
|--------|-------|---------|--------|
| Price > Vaulted Price | - | Entering distribution zone | Be alert, not exit |
| AVIV > 1.5 | - | Market expensive | Consider tightening trail |
| MVRV-Z > 2.5 | - | Statistically expensive | Context only |
| LTH-SOPR > 1.5 | - | Smart money selling | Tighten trail (short-term) |

**Why Not Hard Exits on Valuation:**
```
MVRV > 2.5 still has +10-25% upside!
Unrealized metrics show STATE, not ACTION.
People can stay greedy longer than expected.
Only price reversal confirms the top.
```

---

## 🤖 Bot Implementation

### Strategy A: STRAT-002 (Long-Term Wealth Building)

```python
# ENTRY CONDITIONS (ALL must be true)
entry_signal = (
    sopr < 1.0 and
    sth_sopr < 1.0 and
    realized_loss_z > 0.5
)

# EXIT CONDITIONS
trailing_stop_pct = 0.30  # 30% from peak
# No other exit logic needed

# POSITION SIZING (based on context)
if mvrv_z < 0:
    position_size = 1.0      # Full position - deep value
elif mvrv_z < 1.5:
    position_size = 0.75     # 75% - fair value  
elif mvrv_z < 2.5:
    position_size = 0.50     # 50% - getting expensive
else:
    position_size = 0.25     # 25% - euphoria (still trade signals!)
```

**Expected Performance:**
- CAGR: ~78%
- Sharpe: ~1.45
- Trades: ~1-2 per year
- Max Drawdown: ~64%

### Strategy B: STRAT-003 (Active Trading)

```python
# ENTRY CONDITIONS
entry_signal = sth_sopr < 1.0

# EXIT CONDITIONS  
base_trail = 0.08  # 8% trailing stop

# Tighten on distribution signal
if lth_sopr > 1.5 and mvrv_z > 2.5:
    trailing_stop_pct = 0.15  # Tighten to 15%
else:
    trailing_stop_pct = base_trail
```

**Expected Performance:**
- CAGR: ~50-60%
- Trades: ~9 per year
- Avg Hold: ~29 days
- Better for learning/paper trading

---

## 📈 Key Price Levels

These levels provide context for where we are in the cycle:

| Level | Calculation | Meaning |
|-------|-------------|---------|
| **Realized Price** | Realized Cap / Supply | Average cost basis of all coins |
| **True Market Mean** | Investor Cap / Active Supply | Cost basis of active investors |
| **STH Realized Price** | STH Realized Cap / STH Supply | Short-term holder cost basis |
| **Vaulted Price** | Vaulted Cap / Vaulted Supply | HODLer cost basis (distribution ceiling) |

**Price Level Hierarchy (Bottom to Top):**
```
DEEP VALUE:     Price < Realized Price
ACCUMULATION:   Realized Price < Price < True Market Mean  
FAIR VALUE:     True Market Mean < Price < Vaulted Price
DISTRIBUTION:   Price > Vaulted Price
```

---

## 🎯 Decision Tree

```
START
  │
  ├─► Is there an ENTRY SIGNAL?
  │     │
  │     ├─► YES: SOPR < 1 AND STH-SOPR < 1 AND RL Z > 0.5
  │     │     │
  │     │     └─► ENTER POSITION
  │     │           │
  │     │           └─► Size based on MVRV-Z context
  │     │
  │     └─► NO: Wait for signal
  │
  └─► Are we IN A POSITION?
        │
        ├─► Check trailing stop
        │     │
        │     ├─► Price dropped 30% from peak? → EXIT
        │     │
        │     └─► Still above trail → HOLD
        │
        └─► (Short-term only) Check LTH-SOPR
              │
              └─► LTH-SOPR > 1.5? → Tighten trail to 15%
```

---

## 📊 Monitoring Dashboard Metrics

### Always Monitor (Core)

| Metric | Current | Signal Level | Status |
|--------|---------|--------------|--------|
| SOPR | - | < 1.0 | Entry component |
| STH-SOPR | - | < 1.0 | Entry component |
| Realized Loss Z | - | > 0.5 | Entry component |
| LTH-SOPR | - | > 1.5 | Exit trigger (short-term) |
| Trail Distance | - | 30% | Exit mechanism |

### Context Metrics (Information Only)

| Metric | Current | Zone | Interpretation |
|--------|---------|------|----------------|
| MVRV-Z | - | - | Cycle position |
| AVIV | - | - | Active investor valuation |
| Price vs Vaulted Price | - | - | Distribution zone? |
| Price vs True Market Mean | - | - | Fair value reference |

---

## ⚠️ What NOT To Do

### Don't Use These as Hard Exits:
- ❌ MVRV > X → sell immediately
- ❌ Price > Vaulted Price → sell immediately  
- ❌ NUPL > 0.75 → sell immediately
- ❌ Arbitrary time limits (365 days max hold)
- ❌ Price < Realized Price → stop loss (this marks BOTTOMS!)

### Don't Add These Filters to Entries:
- ❌ Price > 200 MA (removes best contrarian entries)
- ❌ Bull market only (capitulation happens in bear markets!)
- ❌ Multiple on-chain confirmations (redundant, reduces signals)

### Don't Combine Redundant Metrics:
- ❌ MVRV + NUPL (0.90 correlation)
- ❌ SOPR + Supply in Profit (both measure profitability)
- ❌ Multiple valuation metrics for same decision

---

## 🔬 Validation Status

| Component | Validated? | Beat Rate | Notes |
|-----------|------------|-----------|-------|
| Entry: SOPR + STH-SOPR + RL Z | ✅ Yes | 67% | Primary entry signal |
| Exit: 30% Trail | ✅ Yes | - | Best for long-term |
| Exit: LTH-SOPR trigger | ✅ Yes | +28% | Best for short-term |
| Context: MVRV-Z zones | ⚠️ Partial | - | Used for sizing, not tested |
| Context: Price levels | ❌ No | - | Informational only |
| Context: AVIV | ❌ No | - | New metric, needs testing |
| Context: Vaulted Price | ❌ No | - | New metric, needs testing |

---

## 📝 Future Enhancements

### To Test:
1. **Position sizing by MVRV-Z** - Does scaling position by context improve returns?
2. **Vaulted Price as distribution warning** - Does entering this zone predict tops?
3. **AVIV extremes** - What levels mark cycle tops/bottoms?
4. **Sell-Side Risk Ratio** - Does high ratio predict corrections?

### To Build:
1. Live monitoring dashboard
2. Alert system for entry signals
3. Automated position tracking
4. Performance attribution

---

## 📚 References

- James Check "Wen Top?" Masterclass #21
- LESSONS_LEARNED.md (this repo)
- STRATEGY_REGISTRY.md (this repo)
- Notebooks 01-48 (validation work)

---

*Framework Version: 1.0*
*Last Updated: 2025-01-14*
*Status: Core validated, context metrics pending*
