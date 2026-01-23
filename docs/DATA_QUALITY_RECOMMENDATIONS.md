# Data Quality Recommendations

## Executive Summary

Current data quality: **GOOD** (minimal issues found)
Current validation: **BASIC** (only null removal and error tracking)
**Recommendation**: Add comprehensive validation before production trading

---

## Current Issues Found (2026-01-23)

### Bitcoin Lab Hourly Data
- `sopr`: 1 null value (0.001% of 96,735 rows)
- `sopr_lth`: 3 null values (0.003%)
- `sopr_sth`: 1 null value (0.001%)

**Impact**: Negligible - can be handled with forward fill

### BRK Daily Data
- ✅ No issues found (all 41 metrics clean)

---

## Recommended Additions

### 1. Data Quality Module (HIGH PRIORITY)

Create `src/data_quality.py`:

```python
class DataQualityChecker:
    """Comprehensive data quality validation"""

    def check_outliers(self, df, metric):
        """Detect extreme values using configurable thresholds"""
        # Z-score method
        # IQR method
        # Known range validation

    def check_consistency(self, df):
        """Validate cross-metric relationships"""
        # MVRV = price / realized_price
        # supply_total monotonicity
        # Ratio validations

    def check_timeseries(self, df):
        """Validate time series properties"""
        # Gap detection
        # Duplicate detection
        # Ordering validation

    def check_statistics(self, df, metric):
        """Statistical validation"""
        # Distribution checks
        # Change rate limits
        # Correlation validation

    def generate_report(self):
        """Generate comprehensive quality report"""
        # Summary statistics
        # Issue list with severity
        # Recommended actions
```

### 2. Data Cleaning Options (MEDIUM PRIORITY)

Extend DataLoader with cleaning strategies:

```python
class DataLoader:
    def load(
        self,
        metrics,
        cleaning_strategy='dropna'  # 'dropna', 'ffill', 'bfill', 'interpolate'
    ):
        """Load with configurable cleaning"""

    def clean_nulls(self, df, method='forward_fill', limit=3):
        """Flexible null handling"""
        # Forward fill for small gaps (< limit)
        # Drop for large gaps
        # Interpolate for smooth metrics (price)
```

### 3. Cross-Source Validation (LOW PRIORITY)

Compare overlapping metrics between sources:

```python
def compare_sources(metric, date_range):
    """Compare BRK vs Bitcoin Lab for same metric"""
    brk_data = load_from_brk(metric)
    bl_data = load_from_bl(metric)

    # Calculate differences
    # Flag significant divergence (>5%)
    # Return consensus value
```

### 4. Pre-Trading Validation (HIGH PRIORITY)

Add validation before strategy execution:

```python
def validate_for_trading(df):
    """Pre-flight checks before live trading"""
    checks = {
        'data_freshness': check_data_age(df) < 24h,
        'no_nulls': df.isnull().sum().sum() == 0,
        'no_outliers': check_outliers(df),
        'consistent': check_consistency(df),
        'complete': all_required_metrics_present(df)
    }

    if not all(checks.values()):
        raise ValidationError(f"Failed checks: {checks}")
```

### 5. Monitoring & Alerting (MEDIUM PRIORITY)

Add continuous monitoring:

```python
class DataMonitor:
    """Real-time data quality monitoring"""

    def check_incoming_data(self, new_data):
        """Validate each sync"""
        # Compare to historical distribution
        # Detect anomalies
        # Alert if suspicious

    def alert_on_issues(self, issues):
        """Send alerts for quality issues"""
        # Email/Telegram notifications
        # Severity-based routing
```

---

## Implementation Priority

### Phase 1: Critical (Before Live Trading)
1. ✅ Fix existing nulls in Bitcoin Lab hourly data (forward fill)
2. Add outlier detection for critical metrics (price, sopr, mvrv)
3. Add pre-trading validation checks
4. Add gap detection and reporting

### Phase 2: Important (Before Paper Trading at Scale)
1. Implement cleaning strategy options
2. Add consistency validation (cross-metric checks)
3. Add statistical validation (change rate limits)
4. Create quality report dashboard

### Phase 3: Nice to Have (Optimization)
1. Cross-source validation
2. Real-time monitoring
3. Automated alerting
4. Historical quality tracking

---

## Quick Fixes for Current Issues

### Fix Bitcoin Lab Hourly Nulls

```python
# Run this to fix the 5 null values found:
from pathlib import Path
import pandas as pd

bl_hourly = Path('data/bl/hourly')

for metric in ['sopr', 'sopr_lth', 'sopr_sth']:
    file = bl_hourly / f'{metric}.parquet'
    df = pd.read_parquet(file)

    # Forward fill nulls (max 3 consecutive)
    df['value'] = df['value'].fillna(method='ffill', limit=3)

    # Save cleaned version
    df.to_parquet(file)
    print(f"✓ Cleaned {metric}: {df['value'].isnull().sum()} nulls remaining")
```

### Add Basic Quality Check to Daily Routine

```bash
# Add to your morning routine:
python run.py data                  # Check freshness
python run.py brk-status            # Check for errors
python scripts/check_data_quality.py # Run quality scan (create this)
```

---

## Validation Rules by Metric Type

### Price Metrics
- Range: > 0
- Change rate: < 50% per day
- No nulls allowed

### SOPR Family
- Range: 0.5 - 5.0 (typical)
- Ratio metrics: should be > 0
- Small gaps OK (can forward fill up to 3 days)

### MVRV Family
- Range: 0.1 - 10.0 (typical, can go higher in euphoria)
- Should equal price / realized_price
- Consistency check with NUPL

### Supply Metrics
- Monotonic: supply_total should only increase
- Sum check: supply_lth + supply_sth ≈ supply_total
- Range: 0 - 21,000,000 BTC

### Realized Metrics
- Range: > 0 for cap/price
- Profit/Loss can be any value
- Should sum correctly across cohorts

---

## Resources Needed

1. **Create**: `src/data_quality.py` (validation module)
2. **Create**: `scripts/check_data_quality.py` (daily quality scan)
3. **Create**: `scripts/fix_data_issues.py` (automated cleaning)
4. **Update**: `src/data_loader.py` (add cleaning strategies)
5. **Create**: `docs/QUALITY_METRICS.md` (define acceptable ranges)

---

## Testing Strategy

Before implementing in production:

1. **Backtest with dirty data** - Ensure strategies handle nulls gracefully
2. **Test cleaning methods** - Verify forward fill doesn't introduce bias
3. **Validate validation** - Ensure checks don't false positive
4. **Performance test** - Quality checks shouldn't slow down sync

---

## Monitoring Dashboard (Future)

Ideal quality dashboard would show:

```
DATA QUALITY DASHBOARD
======================

Overall Status: 🟢 GOOD (98.5% score)

Metrics Status:
  ✅ 38/41 BRK metrics clean
  ⚠️  3/5 BL hourly metrics have minor issues

Recent Issues (Last 7 Days):
  - 2026-01-23: 5 nulls in BL hourly (fixed)
  - 2026-01-20: 1 outlier in MVRV (confirmed valid)

Data Freshness:
  BRK:  2 hours ago ✅
  BL:   4 hours ago ✅

Quality Metrics:
  Completeness:  99.99%
  Consistency:   100%
  Timeliness:    ✅
  Accuracy:      98.5% (est)
```

---

*Last Updated: 2026-01-23*
*Next Review: Before live trading deployment*
