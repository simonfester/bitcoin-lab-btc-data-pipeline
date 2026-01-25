# Data Retention Policy

**Date**: 2026-01-25
**Status**: CRITICAL - DO NOT DELETE HISTORICAL DATA

---

## ⚠️ IMPORTANT: DO NOT DELETE PRE-2015 DATA

### TL;DR

**KEEP ALL HISTORICAL DATA** - Filter in code, don't delete files.

---

## Why Keep All Data (Including Pre-2015)?

### 1. Historical Archive Value 📚
- **Bitcoin history**: Pre-2015 data captures Bitcoin's genesis and early adoption
- **Irreplaceable**: Once deleted, may be hard to re-download
- **Research value**: Future analysis may benefit from full history
- **Educational**: Shows Bitcoin's evolution from $0 to today

**Example**: The 550 price zeros (2009-2010) are Bitcoin history! They show the pre-exchange era when Bitcoin existed but had no market price.

---

### 2. Different Use Cases Need Different Start Dates 🎯

| Use Case | Recommended Start | Why |
|----------|------------------|-----|
| **Production trading** | 2015-01-01 | Cleanest data |
| **Academic research** | 2015-01-01 | Most defensible |
| **Maximum history analysis** | 2011-01-18 | All metrics available |
| **SOPR-only strategies** | 2010-08-16 | Maximum SOPR history |
| **Historical research** | 2009-01-09 | Full Bitcoin timeline |
| **Price discovery studies** | 2010-07-12 | First exchange era |

**If you delete early data**, you lose flexibility for different analyses.

---

### 3. Storage is Cheap, Data is Precious 💾

**Current BRK data size**:
```bash
# Check actual size
du -sh data/brk/daily/
# Typically: ~50-100 MB total (compressed parquet)
```

**Cost-benefit**:
- ✅ Storage: Pennies per year
- ❌ Re-downloading: Time consuming, may lose access
- ❌ Lost research: Priceless

**Parquet compression** makes files very small. All BRK daily data is probably less than 100 MB!

---

### 4. Easy to Filter in Code 💻

**You don't need to delete - just filter!**

```python
# Simple date filter (takes milliseconds)
df = df[df['time'] >= '2015-01-01'].copy()

# Or use a constant
BACKTEST_START = '2015-01-01'  # Change as needed
df = df[df['time'] >= BACKTEST_START].copy()
```

**Benefits of filtering vs deleting**:
- ✅ Reversible (just change the date)
- ✅ Fast (parquet filters are optimized)
- ✅ Flexible (different dates for different analyses)
- ✅ Safe (original data preserved)

---

### 5. Early Data Documents Bitcoin's Reality 🏛️

**Pre-2015 data captures unique Bitcoin phases**:

#### 2009: Genesis Era
- Bitcoin created January 3, 2009
- No exchanges, no price
- Pure peer-to-peer transfers
- **Historical significance**: Birth of cryptocurrency

#### 2010: First Exchanges
- Mt. Gox launches July 2010
- First price: $0.01 (July 12)
- Price discovery begins
- **Historical significance**: Bitcoin gets market value

#### 2011: First Bubble
- Price reaches $31 (June 2011)
- Crashes to $2 (November 2011)
- Early volatility patterns
- **Historical significance**: First boom/bust cycle

#### 2012-2014: Early Adoption
- First halving (November 2012)
- Silk Road era
- Mt. Gox collapse (2014)
- **Historical significance**: Growing pains, market maturation

**This is Bitcoin's documented history** - deleting it loses educational and research value.

---

## When to Consider Data Cleanup

### DO Clean Up ✅

**Temporary/generated files**:
```bash
# Safe to delete (regeneratable)
rm -rf data/signals/*.parquet      # Regenerate with calculate.py
rm -rf dashboards/*.html            # Regenerate with dashboard scripts
rm -rf data/results/                # Backtest outputs
rm -rf logs/*.log                   # Old logs
```

**Duplicate/corrupted downloads**:
```bash
# If you have duplicates or corrupt files
# Verify first, then delete specific problem files
```

---

### DO NOT Delete ❌

**Raw downloaded data**:
```bash
# NEVER delete these
data/brk/daily/*.parquet            # BRK on-chain data
data/bl/daily/*.parquet             # Bitcoin Lab data
data/bl/hourly/*.parquet            # Bitcoin Lab hourly
data/glassnode/daily/*.parquet      # Glassnode data
```

**Why**:
- Takes time to re-download
- Uses API quota (Bitcoin Lab, Glassnode)
- May lose access to APIs in future
- Historical data may not be available forever

---

## Recommended Approach

### 1. Keep All Raw Data ✅
```bash
# Preserve everything in data/
# These are your source files
data/brk/daily/*.parquet      → KEEP
data/bl/daily/*.parquet       → KEEP
data/glassnode/daily/*.parquet → KEEP
```

### 2. Filter When Loading 📊
```python
# In your analysis/backtest scripts
def load_data(start_date='2015-01-01'):
    """Load data from specified start date"""
    df = pd.read_parquet('data/brk/daily/price.parquet')
    df = df[df['time'] >= start_date].copy()
    return df

# Usage
df = load_data('2015-01-01')  # Production backtests
df = load_data('2011-01-18')  # Maximum history
df = load_data('2010-07-12')  # Historical research
```

### 3. Document Your Filtering 📝
```python
# At the top of your backtest script
"""
Backtest Configuration
=====================
START_DATE: 2015-01-01
REASON: Cleanest data, all metrics stable
DATA_POINTS: ~4,043 (11 years)
RATIONALE: See docs/research/BACKTEST_START_DATES.md
"""

BACKTEST_START = '2015-01-01'
```

---

## Data Backup Strategy

### Recommended Approach

1. **Local storage**: Keep all raw data locally
2. **Version control**: Don't commit data to git (already in `.gitignore`)
3. **Optional backup**: Cloud storage for raw data folders
4. **Re-download capability**: Your sync scripts can always refresh

### Backup Command (Optional)
```bash
# Backup to external drive or cloud
tar -czf bitcoin-data-backup-$(date +%Y%m%d).tar.gz data/

# Or use rsync
rsync -av data/ /path/to/backup/data/
```

---

## Summary: The Golden Rule

### 🏆 FILTER IN CODE, DON'T DELETE FILES

**Bad Approach** ❌:
```bash
# DON'T DO THIS
rm data/brk/daily/*  # Delete old files
# Re-download from 2015 only
python run.py brk-backfill --start-date 2015-01-01
```

**Good Approach** ✅:
```python
# DO THIS
# Keep all files, filter when loading
df = pd.read_parquet('data/brk/daily/price.parquet')
df = df[df['time'] >= '2015-01-01'].copy()  # Filter in memory
```

---

## Exceptions: When Deletion is OK

### Scenario 1: Disk Space Emergency
**Only if absolutely necessary**:
1. Delete regeneratable files first (signals, dashboards, logs)
2. Archive raw data to external storage before deleting
3. Document what was deleted and why
4. Keep ability to re-download

### Scenario 2: Data Corruption
**If files are corrupt**:
1. Identify specific corrupt files
2. Delete only those files
3. Re-download just those metrics
4. Verify integrity

### Scenario 3: API Source Deprecated
**If BRK shuts down**:
1. Keep local copy as archive
2. Switch to alternative source (Bitcoin Lab)
3. Don't delete - it becomes historical reference

---

## Cost-Benefit Analysis

### Deleting Pre-2015 Data

**Potential Savings**:
- ~20-30 MB disk space (trivial)
- Slightly faster loads (milliseconds difference)

**What You Lose**:
- ❌ Full Bitcoin history
- ❌ Flexibility for different analyses
- ❌ Educational/research value
- ❌ Ability to study early Bitcoin patterns
- ❌ Context for current market behavior
- ❌ Comparative analysis (early vs modern Bitcoin)

**Verdict**: **NOT WORTH IT**

---

## Action Items

### ✅ DO THIS
1. Keep all raw data files in `data/` folders
2. Use date filters in your analysis code
3. Set `BACKTEST_START = '2015-01-01'` in your scripts
4. Document why you chose that start date
5. Optional: Backup raw data to external storage

### ❌ DON'T DO THIS
1. Delete pre-2015 data files
2. Re-download with limited date range
3. Modify raw data files (keep them pristine)
4. Delete without backup

---

## Questions & Answers

### Q: "But I'll never use pre-2015 data for trading!"
**A**: Correct! But you filter it out in code, not by deleting files. Your backtest uses 2015+, but the data is still there if needed.

### Q: "Doesn't early data slow down my backtests?"
**A**: Negligible. Parquet filtering is fast. Loading 6,000 rows vs 4,000 rows takes milliseconds difference.

### Q: "What if BRK changes their API and I can't re-download?"
**A**: Exactly! That's why you keep local copies. Your current data is your insurance.

### Q: "Can I at least delete the hourly data I don't use?"
**A**: Bitcoin Lab hourly is already gitignored and optional. If you truly don't need it and want to save API quota, you can skip syncing it. But once downloaded, storage is cheap - keep it.

### Q: "Storage is not infinite on my machine"
**A**: Bitcoin on-chain data is tiny. All BRK daily data compressed is probably <100 MB. That's less than a single photo from your phone. If storage is truly critical, delete dashboards/signals (regeneratable) first.

---

## Final Recommendation

### 🏆 Official Policy

**RETAIN ALL HISTORICAL DATA**

**Reason**:
- Storage is cheap
- Data is precious
- Flexibility is valuable
- History is irreplaceable

**Implementation**:
- Keep all raw data files
- Filter dates in code
- Use `BACKTEST_START = '2015-01-01'` constant
- Document your filtering choices

---

**Related Docs**:
- [Backtest Start Dates](BACKTEST_START_DATES.md)
- [BRK Data Format Notes](../archive/BRK_DATA_FORMAT_NOTES.md)
- [Data Source Config](../setup/DATA_SOURCE_CONFIG.md)

**Last Updated**: 2026-01-25
**Policy Status**: **ACTIVE - DO NOT DELETE PRE-2015 DATA**
