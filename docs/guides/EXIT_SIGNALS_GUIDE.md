# Exit Signals Implementation Guide

## Quick Reference

### When Markets Are Overheated (Exit Signals)

#### 1. 🚨 8-Metric Exit Detector
**What it does:** Monitors 8 market sectors for euphoria  
**Thresholds:**
- 0-1 metrics: NORMAL (continue accumulation) 🟢
- 2-3 metrics: WARMING UP (monitor closely) 🟡
- 4-5 metrics: CAUTION (slow DCA, reduce buys) 🟠
- 6-8 metrics: HIGH RISK (stop DCA, prepare exit) 🔴

**Current Status:** 0/8 (NORMAL)

#### 2. 📊 STH-MVRV Zones
**What it does:** Detects local tops when recent buyers are profitable  
**Price Levels:**
- Warming: $102,266 (Z=+0.5σ) - Fresh ATHs may trigger profit-taking
- Local Top: $106,855 (Z=+1.0σ) - Resistance likely
- Overheated: $111,444 (Z=+1.5σ) - Local top forming

**Current Status:** COOLED (-0.91σ) - Support level

#### 3. 💎 LTH Distribution
**What it does:** Detects when smart money (HODLers) start distributing  
**Triggers:**
- MVRV > 2.0 (market expensive)
- LTH-SOPR > 1.5 (HODLers taking big profits)
- Both = Distribution (top forming)

**Current Status:** ACCUMULATION (1.59 / 1.21)

---

## Dashboard Usage

### Daily Workflow

1. **Update Signals**
   ```bash
   python scripts/calculate.py
   python scripts/dashboard_new.py
   ```

2. **Check Dashboard**
   - Open `dashboard.html` in browser
   - Review Entry Signals (buy opportunities)
   - Review Exit Signals (sell warnings)

3. **Take Action**
   - Entry: 4/5 Buy The Dip = Strong buy signal
   - Exit: 0/8 metrics = No sell pressure

---

## Interpretation Guide

### Current Market (2026-01-21)

**Entry Side:**
- ✅ 4/5 Buy The Dip conditions
- ✅ STH underwater and capitulating
- ✅ Heavy losses vs profits (0.46 ratio)
- ✅ 25x more long liquidations

**Exit Side:**
- ○ 0/8 exit metrics triggered
- ○ All Z-scores negative (market cold)
- ○ LTH-SOPR only 1.21 (need 1.5+ for distribution)
- ○ Price at $89k, resistance at $102k+

**Signal:** Strong accumulation environment, NOT a topping pattern.

---

## Alert Thresholds

Set up alerts when:

### Exit Alerts (Take Profits)
1. **8-Metric >= 4**: Caution zone - slow DCA
2. **8-Metric >= 6**: High risk - stop DCA
3. **STH-MVRV Zone = Overheated**: Local top forming
4. **LTH Distribution = BOTH**: HODLers distributing

### Entry Alerts (Buy Opportunities)
1. **Buy The Dip >= 4**: Strong buy signal
2. **STH-MVRV Zone = Capitulation**: Extreme buy opportunity
3. **MVRV-Z < -1.0**: Deep value zone

---

## Files Structure

```
bitcoin-lab-btc-data-pipeline/
├── scripts/
│   ├── calculate.py          # Compute all signals
│   └── dashboard_new.py      # Generate HTML dashboard
├── data/
│   └── signals/
│       └── dashboard_context.json  # Pre-computed signals
├── dashboard.html            # View in browser
└── EXIT_SIGNALS_GUIDE.md     # This file
```

---

## James Check Framework Sources

- **8-Metric Detector:** Masterclass #19 "Spotting Cycle Extremes"
- **STH-MVRV Zones:** Masterclass #21 "Wen Top?"
- **LTH Distribution:** Masterclass #16 "Understanding Long & Short-Term Holders"
- **Buy The Dip:** Masterclass #15 "My Buy-The-Dip Checklist"

All documentation: `research/check/Masterclass.txt`

---

## Pro Tips

1. **Don't fight the signals** - When 6/8 exit metrics flash, the market IS overheated
2. **Use zones, not exact prices** - STH-MVRV zones are ranges, not precise tops
3. **Combine signals** - Best confirmation is when multiple exit signals align
4. **Market phases** - Use 8-metric for cycle tops, STH-MVRV for local tops
5. **Trust the process** - James Check framework has proven track record

---

Generated: 2026-01-21  
Framework: James Check (Checkonchain)
