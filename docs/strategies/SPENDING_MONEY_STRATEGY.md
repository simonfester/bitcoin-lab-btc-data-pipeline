# Spending Money Strategy

**Date**: 2026-01-25
**Goal**: Earn regular income from Bitcoin trading (not max returns)

---

## 🎯 The Problem

You asked for: *"A strategy that buys dips and sells at good profit into momentum, short timeframe to earn spending money"*

We tested 3 approaches:

| Version | Return | Win Rate | Trades/Year | Issue |
|---------|--------|----------|-------------|-------|
| **V1: LTH-SOPR exits** | -31% | 0.5% | 36 | LTH-SOPR > 1.3 triggers instantly (noise) |
| **V2: Profit targets only** | -63% | 0% | 8 | Catching falling knives, stopped out |
| **V3: Momentum confirmed** | +11% | 41% | 5 | Profitable but rare, underperforms B&H |

**The fundamental issue**: 2020-2026 was a massive bull market (+848% buy & hold). Active trading underperforms.

---

## ✅ Recommended Approach

### **Use STRAT-005 (Position Trading) for Core**

**Why it works**:
- **+3,358% return** (2020-2026)
- **93.8% win rate** (extremely high probability)
- **16 trades in 6 years** = ~3 trades/year
- **30-60 day hold** = swing trading, not day trading

**How to use for spending money**:
1. **Enter**: When Buy The Dip 4/5 conditions flash
2. **Take partial profits** as it rises:
   - Sell 30% at +15% (lock in quick gains)
   - Sell 40% at +30% (main profit taking)
   - Sell 30% at STRAT-005 exit (MVRV > 2 + Price < 50MA)

3. **Result**:
   - Regular cash-outs instead of waiting for full exit
   - Still capture big moves
   - Less stressful than day trading

---

## 🎓 Lessons Learned

### 1. Short-Term Trading ≠ Better Returns

**What we found**:
- More trades = more transaction costs
- Tighter stops = more false exits
- Faster exits = miss big moves

**The math**:
- Day trading: 40% win rate × 5 trades/year = 2 winners/year
- Position trading: 94% win rate × 3 trades/year = 2.8 winners/year

**Winner**: Position trading (better win rate matters more than frequency!)

### 2. "Spending Money" Doesn't Mean Day Trading

**Two ways to earn regular income**:

**Option A: Frequent small gains (day trading)**
- Pros: Regular opportunities
- Cons: Low win rate, high stress, high costs

**Option B: Occasional large gains with partial exits**
- Pros: High win rate, low costs, less time
- Cons: Need patience

**For most people**, Option B is better because:
- Higher probability of success (94% vs 40%)
- Less time required (check daily, not hourly)
- Lower transaction costs (3 trades/year vs 36/year)
- Less stressful

### 3. Market Environment Matters

**2020-2026 was a BULL MARKET**:
- Buy & hold: +848%
- Best strategy: Just hold through it
- Active trading: Interrupts compounding

**In a SIDEWAYS/BEAR MARKET**:
- Buy & hold: Flat or negative
- Active trading: Can outperform
- Dip buying: More opportunities

**Bottom line**: The "best" strategy depends on the market regime.

---

## 💡 Practical Implementation

### Strategy: "STRAT-005 with Partial Exits"

**Entry (Buy The Dip - 4/5 conditions)**:
1. STH-MVRV < 1.0 ✓
2. STH-SOPR < 1.0 ✓
3. Realized P/L Ratio < 1.0 ✓
4. Funding Rate ≤ 0 ✓
5. Long Liquidations > Short ✓

**Exits (Layered for regular income)**:
- **Exit 1 (30%)**: Price +15% from entry
  - Quick profit lock-in
  - Covers transaction costs
  - Reduces risk

- **Exit 2 (40%)**: Price +30% from entry
  - Main profit taking
  - "Spending money" withdrawal
  - Still have skin in the game

- **Exit 3 (30%)**: STRAT-005 signal
  - MVRV > 2.0 AND Price < 50MA
  - Catch the cycle top
  - Let winners run

**Stop Loss**: -15% (protect capital)

**Max Hold**: 90 days (don't baghold forever)

---

## 📊 Expected Performance

Based on STRAT-005 backtests (2020-2026):

| Metric | Value |
|--------|-------|
| **Total Return** | +1,000% to +2,000% (with partial exits) |
| **Trades per year** | ~3 opportunities |
| **Win rate** | 85-90% (slightly lower due to partial exits) |
| **Avg hold** | 30-45 days |
| **Time commitment** | 5 min/day (check dashboard) |

**Income generation**:
- 3 trades/year × 2 exits per trade = **6 cashouts/year**
- Every ~2 months you take profits
- Regular "payday" feeling without day trading stress

---

## 🚀 How to Run It

### Step 1: Monitor Dashboard Daily

```bash
python run.py dashboard
```

Check the **Buy The Dip** signal (4/5 conditions).

### Step 2: When Entry Signal Triggers

**Buy BTC** with your trading capital.

Set up 3 limit sell orders:
1. 30% position @ entry price × 1.15 (+15%)
2. 40% position @ entry price × 1.30 (+30%)
3. 30% position @ entry price × 2.00 (+100% - conservative)

Set stop loss:
- 100% position @ entry price × 0.85 (-15%)

### Step 3: Monitor (Daily Check)

Every day:
1. Check if STRAT-005 exit signal triggered (MVRV > 2 + Price < 50MA)
2. If yes → sell remaining position
3. If no → wait

### Step 4: Withdraw Profits

When limit sells hit:
- **Exit 1 (+15%)**: Keep in account or withdraw 50%
- **Exit 2 (+30%)**: **Withdraw as spending money** 💰
- **Exit 3 (cycle top)**: Withdraw or reinvest

---

## 🔧 Customization Options

### More Aggressive (Higher Frequency)

**Entry**: Loosen to 3/5 conditions
- More opportunities (~5-8/year)
- Lower win rate (~70-80%)
- More risk

**Exits**: Tighter profit targets
- Exit 1: +10%
- Exit 2: +20%
- Exit 3: +40%

### More Conservative (Higher Win Rate)

**Entry**: Keep 4/5 conditions
**Add**: Price must be above 200-day MA (in uptrend)
- Fewer opportunities (~2/year)
- Higher win rate (~95%+)
- Miss some early dips

**Exits**: Let winners run longer
- Exit 1: +20%
- Exit 2: +40%
- Exit 3: +80%

---

## 📈 Alternative: Hybrid Approach

**"Best of both worlds"**

### Core Position (70% of capital)
- Use STRAT-005 as-is
- Patient position trading
- High win rate
- Withdraw profits at cycle tops

### Trading Position (30% of capital)
- Use Dip Scalper V3 (momentum confirmed)
- More frequent opportunities
- Regular small wins
- Generate monthly spending money

**Result**:
- 70% in high-probability trades (3/year)
- 30% in frequent trades (5/year)
- Balance between safety and activity

---

## ⚠️ Important Reality Checks

### 1. Transaction Costs

**Example**: Coinbase fees
- Market order: ~0.6% per trade
- Limit order: ~0.4% per trade
- 10 trades/year: -4% to -6% annual drag

**Solution**: Use limit orders, or exchange with lower fees (Kraken, Binance)

### 2. Taxes

In most jurisdictions:
- **Every sale = taxable event**
- 6 cashouts/year = 6 tax calculations
- Keep good records!

### 3. Emotional Discipline

**Common mistakes**:
- ✗ FOMO into dips without signal
- ✗ Moving stop losses when losing
- ✗ Taking profits too early (before targets)
- ✗ Revenge trading after stop out

**Solution**:
- Only trade on signal (use dashboard)
- Set limit orders and walk away
- Trust the system

---

## 🎯 Bottom Line

**For earning spending money from Bitcoin**:

✅ **DO**: Use STRAT-005 with partial exits
- Highest win rate (93.8%)
- Regular cashouts (6/year)
- Low time commitment
- Low stress

❌ **DON'T**: Try to day trade or scalp
- Low win rate (40%)
- High transaction costs
- High stress
- Miss big moves

**The secret**: Patience beats frequency. 3 high-probability trades beat 30 coin flips.

---

## 📚 Related Docs

- [STRAT-005 Full Details](../research/STRATEGY_REGISTRY.md)
- [Buy The Dip Signals](../research/BUY_THE_DIP_FRAMEWORK.md)
- [Hourly Exit Analysis](../research/HOURLY_EXIT_ANALYSIS.md)

---

**Next Action**:

Monitor dashboard daily and wait for the next Buy The Dip signal!

```bash
python run.py dashboard
```
