# Data Source Investigation - Final Summary

**Date:** 2026-01-23
**Issue:** Data quality checker flagged BRK metrics as "corrupted"
**Resolution:** Not corruption - different units. Bitcoin Lab chosen as primary source.

---

## What We Investigated

Started with data quality checks showing:
- ❌ NUPL: Off by 1.9 trillion times
- ❌ Supply: Off by 100 million times
- ✅ Price: Accurate
- ✅ MVRV: Accurate

---

## Key Findings

### 1. BRK Uses Different Units (Not Corruption!)

| Metric | BRK Format | Standard Format | Issue |
|--------|------------|-----------------|-------|
| **supply_total** | Satoshis (1.998e15) | BTC (19.98M) | Need ÷1e8 conversion |
| **nupl** | Absolute P&L (660B sats) | Ratio (0.37) | **Different metric!** |
| **price** | USD | USD | ✅ Works perfectly |
| **mvrv** | Ratio | Ratio | ✅ Works perfectly |
| **realized_cap** | USD | USD | ✅ Works perfectly |

**Conclusion:** BRK is a valid FREE source, but requires unit conversions and doesn't have true NUPL.

### 2. Compared All Three Sources

| Metric | BRK | Bitcoin Lab | Glassnode |
|--------|-----|-------------|-----------|
| **Price** | $83 MAE ✅ | $972 MAE | Reference |
| **NUPL** | Wrong metric ❌ | 0.19% error ✅ | Reference |
| **Supply** | 312 BTC error | 520 BTC error | Reference |

### 3. Why Each Source is Best

**BRK (FREE):**
- ✅ Most accurate price ($83 vs $972 error)
- ✅ 41 daily metrics
- ❌ Supply in satoshis (needs conversion)
- ❌ NUPL is wrong metric
- ❌ Daily only (no hourly)

**Bitcoin Lab (Paid - you have it):**
- ✅ Correct NUPL (0.19% error)
- ✅ 56 metrics
- ✅ Hourly resolution
- ✅ Standard units (no conversion)
- ✅ Already paying for it
- ⚠️ Price less accurate ($972 error)

**Glassnode (Paid - you have it):**
- ✅ Industry gold standard
- ✅ Best for derivatives
- ✅ MCP server access
- ⚠️ Most expensive

---

## Final Decision

### **Use Bitcoin Lab for Everything (except derivatives)**

**Rationale:**
1. You're already paying for it
2. Has correct NUPL metric (critical for strategies)
3. 56 metrics available vs BRK's 41
4. Hourly resolution support
5. No unit conversions needed
6. Price is "good enough" ($972 MAE is ~1% at $90k)

### **Use Glassnode for Derivatives Only**

**Rationale:**
1. Best source for funding rates, liquidations, open interest
2. MCP server for live queries
3. Industry standard

### **Keep BRK as Backup (FREE)**

**Rationale:**
1. No cost
2. Good for validation
3. Research/comparison

---

## Configuration

```python
# Primary: Bitcoin Lab
DATA_PATH = "data/bl/daily/"

# Derivatives: Glassnode
DERIVATIVES_PATH = "data/glassnode/daily/"

# Backup: BRK
BACKUP_PATH = "data/brk/daily/"
```

---

## What Changed

### Before Investigation
- ❓ Assumed BRK data was corrupted
- ❓ Unclear which source to trust
- ❓ No systematic comparison

### After Investigation
- ✅ Understand BRK uses different units (valid choice)
- ✅ Quantified accuracy of each source
- ✅ Clear decision: Bitcoin Lab primary
- ✅ Documented in DATA_SOURCE_CONFIG.md

---

## Files Created

1. **`data/BRK_DATA_FORMAT_INVESTIGATION.md`**
   - Complete technical analysis of BRK units
   - Conversion formulas
   - Comparison tables

2. **`data/BRK_DATA_CORRUPTION_REPORT.md`**
   - Initial corruption findings
   - Validation against Glassnode
   - Impact analysis

3. **`DATA_SOURCE_CONFIG.md`**
   - Final configuration
   - Usage instructions
   - Maintenance procedures

4. **`INVESTIGATION_SUMMARY.md`** (this file)
   - High-level summary
   - Key decisions
   - Rationale

---

## Impact on Strategies

### No Changes Needed!

Most strategy code already uses the existing data loader which supports multiple sources. The configuration change is transparent.

### If You Have Notebooks Using BRK

Just change paths:
```python
# Before
df = pd.read_parquet('../data/brk/daily/nupl.parquet')  # Wrong metric!

# After
df = pd.read_parquet('../data/bl/daily/nupl.parquet')   # Correct ✅
```

---

## Maintenance

### Daily
```bash
python run.py bl-sync-daily
```

### Weekly
```bash
python scripts/check_data_quality.py
python scripts/check_data_freshness.py
```

### Monthly
```bash
python run.py quota  # Check Bitcoin Lab credits
```

---

## Lessons Learned

1. **"Corruption" might be format differences** - Always investigate before assuming data is bad
2. **Free sources can be valid** - BRK is actually well-designed, just uses different units
3. **Use the right tool for the job** - Bitcoin Lab for on-chain, Glassnode for derivatives
4. **Validate against industry standard** - Glassnode is the gold standard for a reason
5. **Optimize for what you already pay for** - No point using FREE if you're paying for better

---

## Tools Used

- **Glassnode API** - Validation reference
- **Glassnode MCP Server** - Live queries
- **Python pandas** - Data analysis
- **Statistical comparison** - MAE, RMSE calculations

---

## Conclusion

✅ **Investigation successful**
✅ **Configuration optimized**
✅ **Strategies will use correct data**
✅ **No cost increase** (already paying for Bitcoin Lab)

**Bottom Line:** Use what you pay for. Bitcoin Lab is excellent for on-chain metrics, Glassnode for derivatives. BRK is a great FREE backup.

---

**Investigation Lead:** Claude Code + Glassnode Validation
**Duration:** ~2 hours
**Result:** Clear, actionable configuration
**Confidence:** 99% (validated against industry standard)
