# Using Hourly Data for Exit Signals

**Date**: 2026-01-25
**Strategy**: Daily entries, hourly exits

---

## 🎯 Strategy Overview

**Concept**: Use different timeframes for entries vs exits

| Signal Type | Timeframe | Why |
|-------------|-----------|-----|
| **Entry** | Daily | Less noise, confirmed trends |
| **Exit** | Hourly | Faster response to distribution |

**Benefit**: Catch tops earlier while avoiding false entry signals.

---

## 💡 Why This Works

### Daily for Entries
- ✅ Filters out intraday noise
- ✅ Confirmed accumulation signals
- ✅ Reduces false positives
- ✅ Better backtesting stability

### Hourly for Exits
- ✅ Catch distribution as it starts
- ✅ Exit before major dumps
- ✅ More responsive to SOPR spikes
- ✅ Capture more profit

**Example**:
```
Daily SOPR: Still looks ok at 1.3
Hourly SOPR: Spiking to 1.8+ (LTH taking profit!)
→ Exit signal triggers on hourly, you're out early ✅
```

---

## 🔧 Setup

### 1. Hourly Data Sync (Enabled by Default)

```bash
# Option A: Full sync with hourly data (DEFAULT)
python run.py dashboard

# Option B: Skip hourly to save quota
python run.py dashboard --skip-hourly

# Option C: Sync hourly data only (if daily already synced)
python run.py bl-sync-hourly
```

### 2. Check Data Availability

```python
import pandas as pd
from pathlib import Path

# Check hourly data exists
hourly_dir = Path('data/bl/hourly')
assert hourly_dir.exists(), "Run: python run.py bl-sync-hourly"

# Load hourly SOPR
sopr_hourly = pd.read_parquet(hourly_dir / 'sopr.parquet')
print(f"Hourly SOPR: {len(sopr_hourly):,} rows")
print(f"Latest: {sopr_hourly['time'].max()}")
```

---

## 📊 Example: Hourly Exit Signals

### Basic Hourly LTH-SOPR Exit

```python
import pandas as pd
from pathlib import Path

def check_hourly_exit_signal():
    """Check if hourly LTH-SOPR signals exit"""

    # Load hourly LTH-SOPR
    lth_sopr_hourly = pd.read_parquet('data/bl/hourly/sopr_lth.parquet')

    # Get last 24 hours
    recent = lth_sopr_hourly.tail(24)

    # Exit signal: LTH-SOPR > 1.5 (profit taking)
    exit_signal = (recent['value'] > 1.5).any()

    if exit_signal:
        max_sopr = recent['value'].max()
        print(f"🚨 EXIT SIGNAL: LTH-SOPR reached {max_sopr:.2f}")
        print(f"   Long-term holders taking profits!")
        return True

    return False

# Usage
if check_hourly_exit_signal():
    print("Consider exiting positions")
```

---

## 🎓 Advanced: Multi-Timeframe Strategy

### Daily Entries + Hourly Exits

```python
import pandas as pd

class MultiTimeframeStrategy:
    """Daily entries, hourly exits"""

    def __init__(self):
        # Load daily data for entries
        self.sopr_daily = pd.read_parquet('data/brk/daily/sopr.parquet')
        self.sth_sopr_daily = pd.read_parquet('data/brk/daily/sopr_sth.parquet')

        # Load hourly data for exits
        self.lth_sopr_hourly = pd.read_parquet('data/bl/hourly/sopr_lth.parquet')
        self.sopr_hourly = pd.read_parquet('data/bl/hourly/sopr.parquet')

    def check_entry_signal(self, date):
        """Check daily entry conditions"""
        daily_data = self.sopr_daily[self.sopr_daily['time'] <= date]

        if len(daily_data) == 0:
            return False

        latest = daily_data.iloc[-1]

        # Entry: Daily SOPR < 1 and STH-SOPR < 1
        sopr = latest['value']
        sth_sopr_data = self.sth_sopr_daily[self.sth_sopr_daily['time'] == latest['time']]

        if len(sth_sopr_data) == 0:
            return False

        sth_sopr = sth_sopr_data.iloc[0]['value']

        entry_signal = (sopr < 1.0) and (sth_sopr < 1.0)

        return entry_signal

    def check_exit_signal(self, date):
        """Check hourly exit conditions (more responsive)"""
        # Get hourly data for this day
        hourly_data = self.lth_sopr_hourly[
            self.lth_sopr_hourly['time'].dt.date == date.date()
        ]

        if len(hourly_data) == 0:
            return False

        # Exit if ANY hourly reading shows LTH-SOPR > 1.5
        max_hourly_lth_sopr = hourly_data['value'].max()

        exit_signal = max_hourly_lth_sopr > 1.5

        if exit_signal:
            print(f"Exit triggered: Hourly LTH-SOPR = {max_hourly_lth_sopr:.2f}")

        return exit_signal

# Usage
strategy = MultiTimeframeStrategy()

# Check current signals
from datetime import datetime
today = pd.Timestamp.now(tz='UTC')

if strategy.check_entry_signal(today):
    print("📈 Entry signal active (daily)")

if strategy.check_exit_signal(today):
    print("📉 Exit signal active (hourly)")
```

---

## 📈 Exit Signal Examples

### 1. LTH-SOPR Spike Detection

```python
def detect_lth_sopr_spike(lookback_hours=24, threshold=1.5):
    """Detect sudden LTH-SOPR spikes on hourly"""

    lth_sopr = pd.read_parquet('data/bl/hourly/sopr_lth.parquet')
    recent = lth_sopr.tail(lookback_hours)

    # Check if any hourly reading crosses threshold
    spike = (recent['value'] > threshold).any()

    if spike:
        max_val = recent['value'].max()
        spike_time = recent[recent['value'] == max_val]['time'].iloc[0]

        print(f"🚨 LTH-SOPR spike detected!")
        print(f"   Peak: {max_val:.2f} at {spike_time}")
        print(f"   Signal: Long-term holders distributing")

        return True

    return False
```

### 2. SOPR Momentum Exit

```python
def check_sopr_momentum_exit():
    """Exit when hourly SOPR shows upward acceleration"""

    sopr = pd.read_parquet('data/bl/hourly/sopr.parquet')
    recent = sopr.tail(48)  # Last 48 hours

    if len(recent) < 48:
        return False

    # Calculate hourly rate of change
    recent['roc'] = recent['value'].pct_change()

    # Exit if sustained upward momentum
    last_24h_roc = recent.tail(24)['roc'].mean()

    # Strong upward momentum = distribution
    exit_signal = last_24h_roc > 0.02  # 2% avg hourly increase

    if exit_signal:
        print(f"🚨 SOPR momentum exit!")
        print(f"   24h avg ROC: {last_24h_roc:.2%}")
        print(f"   Signal: Accelerating profit-taking")

    return exit_signal
```

### 3. Combined Exit Confirmation

```python
def check_hourly_exit_confirmation():
    """Multiple hourly signals must agree"""

    lth_sopr = pd.read_parquet('data/bl/hourly/sopr_lth.parquet')
    sopr = pd.read_parquet('data/bl/hourly/sopr.parquet')

    # Get last 24 hours
    lth_recent = lth_sopr.tail(24)
    sopr_recent = sopr.tail(24)

    # Condition 1: LTH-SOPR > 1.5
    lth_signal = (lth_recent['value'] > 1.5).any()

    # Condition 2: SOPR trending up
    sopr_trend = sopr_recent['value'].iloc[-6:].mean() > sopr_recent['value'].iloc[:6].mean()

    # Condition 3: Peak SOPR in recent hours
    sopr_peak = sopr_recent['value'].max() > 1.3

    # Exit if 2+ conditions met
    signals_met = sum([lth_signal, sopr_trend, sopr_peak])

    if signals_met >= 2:
        print(f"🚨 Exit confirmation: {signals_met}/3 signals")
        print(f"   LTH-SOPR > 1.5: {'✅' if lth_signal else '❌'}")
        print(f"   SOPR trending up: {'✅' if sopr_trend else '❌'}")
        print(f"   SOPR peak > 1.3: {'✅' if sopr_peak else '❌'}")

        return True

    return False
```

---

## 💰 API Quota Impact

### Daily Only (Current Default)
```
BRK:         FREE
BL Daily:    ~10-20 credits
Glassnode:   ~10-20 credits
Total:       ~20-40 credits/day
```

### With Hourly Data (--include-hourly)
```
BRK:         FREE
BL Daily:    ~10-20 credits
BL Hourly:   ~50-100 credits  ← Added
Glassnode:   ~10-20 credits
Total:       ~70-140 credits/day
```

**Cost increase**: ~3-5x more credits
**Benefit**: Earlier exits, capture more profit

---

## 🚀 Usage Commands

### Default: With Hourly Data

```bash
# Full sync with hourly (DEFAULT)
python run.py dashboard

# Just sync hourly (if daily already fresh)
python run.py bl-sync-hourly

# Check quota before syncing
python run.py quota
```

### Without Hourly (Save Quota)

```bash
# Daily only (saves quota)
python run.py dashboard --skip-hourly

# Skip Bitcoin Lab entirely (use BRK only)
python run.py dashboard --skip-bitcoin-lab
```

---

## 📊 Backtesting with Hourly Exits

### Resampling Approach

```python
import pandas as pd

# Load daily entries
entries = pd.read_parquet('data/signals/entry_signals.parquet')

# Load hourly exits
lth_sopr_hourly = pd.read_parquet('data/bl/hourly/sopr_lth.parquet')

# Backtest
position = None
for date in pd.date_range('2015-01-01', '2026-01-25', freq='D'):

    # Check daily entry
    if position is None:
        entry_data = entries[entries['time'] == date]
        if len(entry_data) > 0 and entry_data.iloc[0]['entry_signal']:
            position = {'entry_date': date, 'entry_price': entry_data.iloc[0]['price']}
            print(f"Enter: {date.date()} @ ${position['entry_price']:.0f}")

    # Check hourly exit (any hour of the day)
    elif position is not None:
        hourly_day = lth_sopr_hourly[lth_sopr_hourly['time'].dt.date == date.date()]

        if len(hourly_day) > 0:
            # Exit if any hourly reading > 1.5
            if (hourly_day['value'] > 1.5).any():
                exit_time = hourly_day[hourly_day['value'] > 1.5]['time'].iloc[0]
                print(f"Exit: {exit_time} (LTH-SOPR spike)")
                position = None
```

---

## 📝 Best Practices

### 1. Test Both Timeframes

```python
# Test daily-only vs daily+hourly
results_daily = backtest(entry='daily', exit='daily')
results_mixed = backtest(entry='daily', exit='hourly')

print(f"Daily only:  {results_daily['return']:.1f}%")
print(f"Mixed TF:    {results_mixed['return']:.1f}%")
```

### 2. Watch for False Exits

- Hourly data is noisier
- Use confirmation (multiple signals)
- Consider minimum hold period

### 3. Monitor Quota

```bash
# Check quota regularly if using hourly
python run.py quota-history
```

---

## 🏆 Summary

**Setup**: Hourly data enabled by default
**Strategy**: Daily entries, hourly exits
**Benefit**: Faster exit response
**Cost**: ~3x more API credits (vs daily-only)
**When to skip**: Use `--skip-hourly` to save quota

```bash
# Default: hourly data included
python run.py dashboard

# Skip hourly to save quota
python run.py dashboard --skip-hourly
```

---

**Related Docs**:
- [Backtest Start Dates](BACKTEST_START_DATES.md)
- [Strategy Framework](STRATEGY_FRAMEWORK.md)
- [Data Sync Workflow](../guides/DATA_SYNC_WORKFLOW.md)
