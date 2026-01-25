# ⚠️ DO NOT DELETE THIS DATA

## Important Notice

**This folder contains raw Bitcoin on-chain data downloaded from APIs.**

### 🚫 DO NOT DELETE

Even if you think the data is "too old" or "not needed":
- ✅ **KEEP all files** - they document Bitcoin's history
- ✅ **Filter in code** - use date filters in your analysis
- ❌ **DON'T delete** - storage is cheap, data is precious

### Why Keep All Data?

1. **Historical value**: Pre-2015 data is Bitcoin history
2. **Irreplaceable**: Hard to re-download if deleted
3. **Flexibility**: Different analyses need different date ranges
4. **Small size**: All data compressed is ~100 MB (tiny!)
5. **Re-download cost**: Uses API quota and time

### For Backtesting

**Recommended start date**: `2015-01-01` (cleanest data)

**How to use it**:
```python
# Filter in code - DON'T delete files
df = pd.read_parquet('data/brk/daily/price.parquet')
df = df[df['time'] >= '2015-01-01'].copy()  # Filter to 2015+
```

### Safe to Delete

Only these are regeneratable and safe to delete:
- ✅ `data/signals/*.parquet` (regenerate with `python scripts/calculate.py`)
- ✅ `data/results/*` (backtest outputs)

### NOT Safe to Delete

Keep these forever:
- ❌ `data/brk/daily/*.parquet` (raw BRK data)
- ❌ `data/bl/daily/*.parquet` (raw Bitcoin Lab data)
- ❌ `data/glassnode/daily/*.parquet` (raw Glassnode data)

---

📖 **Full explanation**: See [`docs/research/DATA_RETENTION_POLICY.md`](../docs/research/DATA_RETENTION_POLICY.md)

**Last Updated**: 2026-01-25
