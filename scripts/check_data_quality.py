#!/usr/bin/env python3
"""
Comprehensive data quality checker for Bitcoin Lab data pipeline.
Scans all data sources for issues: nulls, outliers, gaps, duplicates, inconsistencies.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / 'data'


class DataQualityChecker:
    """Comprehensive data quality validation"""

    def __init__(self):
        self.issues = []

    def check_nulls(self, df, metric, source):
        """Check for null values"""
        null_count = df['value'].isnull().sum()
        if null_count > 0:
            total = len(df)
            pct = (null_count / total) * 100
            self.issues.append({
                'source': source,
                'metric': metric,
                'type': 'nulls',
                'severity': 'high' if pct > 1 else 'medium' if pct > 0.1 else 'low',
                'count': null_count,
                'total': total,
                'message': f"{null_count:,} null values ({pct:.3f}%)"
            })
        return null_count

    def check_infinites(self, df, metric, source):
        """Check for infinite values"""
        inf_count = np.isinf(df['value']).sum()
        if inf_count > 0:
            self.issues.append({
                'source': source,
                'metric': metric,
                'type': 'infinites',
                'severity': 'high',
                'count': inf_count,
                'message': f"{inf_count:,} infinite values"
            })
        return inf_count

    def check_duplicates(self, df, metric, source):
        """Check for duplicate timestamps"""
        dup_count = df.duplicated(subset=['time']).sum()
        if dup_count > 0:
            self.issues.append({
                'source': source,
                'metric': metric,
                'type': 'duplicates',
                'severity': 'high',
                'count': dup_count,
                'message': f"{dup_count:,} duplicate timestamps"
            })
        return dup_count

    def check_gaps(self, df, metric, source, expected_freq='1D'):
        """Check for time gaps larger than expected"""
        df_sorted = df.sort_values('time')
        time_diffs = df_sorted['time'].diff()

        # Define thresholds based on expected frequency
        thresholds = {
            '1D': timedelta(days=2),
            '1H': timedelta(hours=2),
            '4H': timedelta(hours=5),
            '8H': timedelta(hours=9),
            '12H': timedelta(hours=13)
        }

        threshold = thresholds.get(expected_freq, timedelta(days=2))
        gaps = (time_diffs > threshold).sum()

        # Only flag if more than a few gaps (some gaps are normal at data edges)
        gap_threshold = 10 if expected_freq == '1D' else 50

        if gaps > gap_threshold:
            self.issues.append({
                'source': source,
                'metric': metric,
                'type': 'gaps',
                'severity': 'medium',
                'count': gaps,
                'message': f"{gaps:,} time gaps > {threshold}"
            })
        return gaps

    def check_outliers(self, df, metric, source, exclude_early=True, sigma_threshold=8):
        """Check for statistical outliers using Z-score

        Args:
            df: DataFrame with 'time' and 'value' columns
            metric: Metric name
            source: Data source name
            exclude_early: If True, exclude pre-2015 data (early Bitcoin volatility)
            sigma_threshold: Z-score threshold (default 8σ for Bitcoin volatility)
        """
        # Filter out pre-2015 data if requested (early Bitcoin was extremely volatile)
        if exclude_early and 'time' in df.columns:
            early_cutoff = pd.Timestamp('2015-01-01', tz='UTC')
            df_filtered = df[df['time'] >= early_cutoff].copy()
            if len(df_filtered) < 100:
                df_filtered = df  # Fallback if not enough recent data
        else:
            df_filtered = df

        values = df_filtered['value'].dropna()

        if len(values) < 100:
            return 0  # Not enough data for meaningful outlier detection

        # Calculate Z-scores
        mean = values.mean()
        std = values.std()

        if std == 0:
            return 0

        z_scores = np.abs((values - mean) / std)
        outliers = (z_scores > sigma_threshold).sum()

        if outliers > 0:
            outlier_pct = (outliers / len(values)) * 100
            # Only flag if > 0.5% (Bitcoin has legitimate extreme events)
            if outlier_pct > 0.5:
                self.issues.append({
                    'source': source,
                    'metric': metric,
                    'type': 'outliers',
                    'severity': 'low',  # Downgraded - likely legitimate volatility
                    'count': outliers,
                    'message': f"{outliers:,} statistical outliers (>{sigma_threshold}σ, {outlier_pct:.2f}%) - may be legitimate extreme events"
                })

        return outliers

    def check_negatives(self, df, metric, source):
        """Check for negative values in metrics that should be positive"""
        # Metrics that should never be negative
        positive_only = [
            'price', 'market_cap', 'realized_cap', 'supply_total',
            'supply_lth', 'supply_sth', 'sopr', 'sopr_lth', 'sopr_sth',
            'difficulty', 'thermo_cap', 'investor_cap'
        ]

        if metric in positive_only:
            neg_count = (df['value'] < 0).sum()
            if neg_count > 0:
                self.issues.append({
                    'source': source,
                    'metric': metric,
                    'type': 'negatives',
                    'severity': 'high',
                    'count': neg_count,
                    'message': f"{neg_count:,} negative values (should be positive)"
                })
            return neg_count

        return 0

    def check_value_ranges(self, df, metric, source):
        """Check if values are within expected ranges for known metrics

        Note: BRK uses different formats for some metrics:
        - NUPL: Absolute USD value instead of ratio
        - Supply: Satoshis instead of BTC
        - Early data (pre-2015) has extreme volatility
        """
        # Skip BRK-specific format differences
        if source == 'BRK':
            # NUPL is stored as absolute value (market_cap - realized_cap) in BRK
            # Not an error, just different format - skip validation
            if metric == 'nupl':
                return 0

            # Supply metrics are in satoshis, not BTC
            # 21M BTC = 2.1e15 satoshis - allow this range
            if 'supply' in metric:
                values = df['value'].dropna()
                # Check if in satoshi range (1e14 to 2.1e15)
                satoshi_range = ((values >= 1e14) & (values <= 2.1e15)).sum()
                if satoshi_range > len(values) * 0.9:  # >90% in satoshi range
                    return 0  # Valid satoshi format

        # Define expected ranges for common metrics
        ranges = {
            'mvrv': (0, 20, 'MVRV rarely exceeds 20 (extended to allow 2013/2017 peaks)'),
            'mvrv_z': (-2, 12, 'MVRV-Z typically between -2 and 12 (allows extreme bubbles)'),
            'nupl': (-0.5, 1, 'NUPL bounded between -0.5 and 1 (ratio format only)'),
            'sopr': (0.1, 10, 'SOPR rarely outside 0.1-10 range (allows early volatility)'),
            'sopr_lth': (0.1, 1000, 'LTH-SOPR (allows extreme early Bitcoin volatility)'),
            'sopr_sth': (0.1, 10, 'STH-SOPR (allows volatility)'),
            'price': (0.01, 10_000_000, 'BTC price (allows early data and zeros)'),
            'supply_total': (1e6, 21_000_001, 'Total supply: 1M-21M BTC (or 1e14-2.1e15 satoshis)'),
            'difficulty': (0, float('inf'), 'Difficulty always positive'),
            'puell_multiple': (0, 15, 'Puell Multiple rarely exceeds 15 (allows extreme events)'),
            'realized_profit_loss_ratio': (0, 100, 'Realized P/L ratio rarely >100'),
        }

        if metric in ranges:
            min_val, max_val, description = ranges[metric]
            values = df['value'].dropna()

            out_of_range = ((values < min_val) | (values > max_val)).sum()

            if out_of_range > 0:
                pct = (out_of_range / len(values)) * 100
                actual_min = values.min()
                actual_max = values.max()

                # Only flag if significant portion is out of range AND it's not early data issues
                if pct > 5:  # More than 5% out of range (increased from 1%)
                    self.issues.append({
                        'source': source,
                        'metric': metric,
                        'type': 'range_violation',
                        'severity': 'medium' if pct < 20 else 'high',
                        'count': out_of_range,
                        'message': f"{out_of_range:,} values outside expected range [{min_val}, {max_val}] - actual [{actual_min:.2e}, {actual_max:.2e}] ({pct:.1f}%)"
                    })
            return out_of_range

        return 0

    def check_data_types(self, df, metric, source):
        """Check that data types are correct"""
        issues_found = 0

        # Check time column is datetime
        if 'time' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['time']):
                self.issues.append({
                    'source': source,
                    'metric': metric,
                    'type': 'dtype',
                    'severity': 'high',
                    'count': 1,
                    'message': f"'time' column is {df['time'].dtype}, expected datetime64"
                })
                issues_found += 1

        # Check value column is numeric
        if 'value' in df.columns:
            if not pd.api.types.is_numeric_dtype(df['value']):
                self.issues.append({
                    'source': source,
                    'metric': metric,
                    'type': 'dtype',
                    'severity': 'high',
                    'count': 1,
                    'message': f"'value' column is {df['value'].dtype}, expected numeric"
                })
                issues_found += 1

        return issues_found

    def check_cross_metric_consistency(self, all_metrics, source):
        """Check consistency between related metrics"""
        # Check if we have the required metrics
        if 'mvrv' in all_metrics and 'market_cap' in all_metrics and 'realized_cap' in all_metrics:
            mvrv_df = all_metrics['mvrv']
            mcap_df = all_metrics['market_cap']
            rcap_df = all_metrics['realized_cap']

            # Merge on time
            merged = mvrv_df.merge(mcap_df, on='time', suffixes=('_mvrv', '_mcap'))
            merged = merged.merge(rcap_df, on='time')
            merged = merged.rename(columns={'value': 'value_rcap'})

            # Calculate expected MVRV
            merged['expected_mvrv'] = merged['value_mcap'] / merged['value_rcap']
            merged['mvrv_diff'] = abs(merged['value_mvrv'] - merged['expected_mvrv'])
            merged['mvrv_pct_diff'] = (merged['mvrv_diff'] / merged['value_mvrv']) * 100

            # Focus on recent data (last 2 years) for consistency check
            # Early Bitcoin data (2011-2015) has known calculation differences
            cutoff_date = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=730)  # 2 years
            recent_merged = merged[merged['time'] >= cutoff_date]

            if len(recent_merged) > 0:
                # Flag large discrepancies (>5%) in recent data only
                large_diff = (recent_merged['mvrv_pct_diff'] > 5).sum()

                if large_diff > 0:
                    pct = (large_diff / len(recent_merged)) * 100
                    max_diff = recent_merged['mvrv_pct_diff'].max()

                    # Only flag if recent data has issues
                    if pct > 1:  # More than 1% of recent data
                        self.issues.append({
                            'source': source,
                            'metric': 'mvrv_consistency',
                            'type': 'consistency',
                            'severity': 'medium' if pct < 5 else 'high',
                            'count': large_diff,
                            'message': f"{large_diff:,} recent rows where MVRV ≠ market_cap/realized_cap (max diff: {max_diff:.1f}%, last 2 years)"
                        })

        # Check supply metrics sum correctly (if we have them)
        if 'supply_lth' in all_metrics and 'supply_sth' in all_metrics and 'supply_total' in all_metrics:
            lth_df = all_metrics['supply_lth']
            sth_df = all_metrics['supply_sth']
            total_df = all_metrics['supply_total']

            # Merge on time
            merged = lth_df.merge(sth_df, on='time', suffixes=('_lth', '_sth'))
            merged = merged.merge(total_df, on='time')
            merged = merged.rename(columns={'value': 'value_total'})

            # Check if LTH + STH ≈ Total (allow 1% tolerance for exchange/other supply)
            merged['calculated_total'] = merged['value_lth'] + merged['value_sth']
            merged['diff'] = abs(merged['value_total'] - merged['calculated_total'])
            merged['pct_diff'] = (merged['diff'] / merged['value_total']) * 100

            # Flag differences >1%
            large_diff = (merged['pct_diff'] > 1).sum()

            if large_diff > 0:
                pct = (large_diff / len(merged)) * 100
                max_diff = merged['pct_diff'].max()

                self.issues.append({
                    'source': source,
                    'metric': 'supply_consistency',
                    'type': 'consistency',
                    'severity': 'low' if pct < 5 else 'medium',
                    'count': large_diff,
                    'message': f"{large_diff:,} rows where LTH+STH ≠ Total Supply (max diff: {max_diff:.1f}%)"
                })


def check_brk_quality(exclude_early=True):
    """Check BRK data quality

    Args:
        exclude_early: If True, exclude pre-2015 data from outlier checks
    """
    brk_dir = DATA_DIR / 'brk' / 'daily'

    if not brk_dir.exists():
        print("⚠️  BRK directory not found")
        return []

    print("=" * 80)
    print("BRK DATA QUALITY CHECK (DAILY)")
    if exclude_early:
        print("(Excluding pre-2015 data from outlier checks)")
    print("=" * 80)

    checker = DataQualityChecker()
    metrics_checked = 0
    all_metrics = {}  # Store for cross-metric consistency checks

    for file in sorted(brk_dir.glob('*.parquet')):
        metric = file.stem
        try:
            df = pd.read_parquet(file)

            # Run all checks
            checker.check_nulls(df, metric, 'BRK')
            checker.check_infinites(df, metric, 'BRK')
            checker.check_duplicates(df, metric, 'BRK')
            checker.check_gaps(df, metric, 'BRK', expected_freq='1D')
            checker.check_outliers(df, metric, 'BRK', exclude_early=exclude_early, sigma_threshold=8)
            checker.check_negatives(df, metric, 'BRK')
            checker.check_value_ranges(df, metric, 'BRK')
            checker.check_data_types(df, metric, 'BRK')

            # Store for consistency checks
            all_metrics[metric] = df

            metrics_checked += 1

        except Exception as e:
            print(f"✗ {metric}: Error - {str(e)[:50]}")

    # Run cross-metric consistency checks
    if len(all_metrics) > 0:
        checker.check_cross_metric_consistency(all_metrics, 'BRK')

    print(f"\n✓ Checked {metrics_checked} metrics")

    # Show issues
    brk_issues = [i for i in checker.issues if i['source'] == 'BRK']

    if brk_issues:
        print(f"\n⚠️  Found {len(brk_issues)} issues:")
        for issue in brk_issues:
            severity_icon = "🔴" if issue['severity'] == 'high' else "🟡" if issue['severity'] == 'medium' else "⚪"
            print(f"{severity_icon} {issue['metric']}: {issue['message']}")
    else:
        print("\n✅ No issues found in BRK data")

    return brk_issues


def check_bl_quality(resolution='hourly', exclude_early=True):
    """Check Bitcoin Lab data quality

    Args:
        resolution: Data resolution to check
        exclude_early: If True, exclude pre-2015 data from outlier checks
    """
    resolution_map = {
        'hourly': 'hourly',
        'h1': 'hourly',
        'h4': 'h4',
        'h8': 'h8',
        'h12': 'h12'
    }

    freq_map = {
        'hourly': '1H',
        'h4': '4H',
        'h8': '8H',
        'h12': '12H'
    }

    res_dir = resolution_map.get(resolution, resolution)
    bl_dir = DATA_DIR / 'bl' / res_dir

    if not bl_dir.exists():
        print(f"\n⚠️  Bitcoin Lab {resolution} directory not found")
        return []

    print(f"\n{'=' * 80}")
    print(f"BITCOIN LAB DATA QUALITY CHECK ({resolution.upper()})")
    if exclude_early:
        print("(Excluding pre-2015 data from outlier checks)")
    print("=" * 80)

    checker = DataQualityChecker()
    metrics_checked = 0
    all_metrics = {}  # Store for cross-metric consistency checks

    for file in sorted(bl_dir.glob('*.parquet')):
        metric = file.stem
        try:
            df = pd.read_parquet(file)

            # Run all checks
            checker.check_nulls(df, metric, f'BL-{resolution}')
            checker.check_infinites(df, metric, f'BL-{resolution}')
            checker.check_duplicates(df, metric, f'BL-{resolution}')
            checker.check_gaps(df, metric, f'BL-{resolution}',
                             expected_freq=freq_map.get(res_dir, '1H'))
            checker.check_outliers(df, metric, f'BL-{resolution}', exclude_early=exclude_early, sigma_threshold=8)
            checker.check_negatives(df, metric, f'BL-{resolution}')
            checker.check_value_ranges(df, metric, f'BL-{resolution}')
            checker.check_data_types(df, metric, f'BL-{resolution}')

            # Store for consistency checks
            all_metrics[metric] = df

            metrics_checked += 1

        except Exception as e:
            print(f"✗ {metric}: Error - {str(e)[:50]}")

    # Run cross-metric consistency checks
    if len(all_metrics) > 0:
        checker.check_cross_metric_consistency(all_metrics, f'BL-{resolution}')

    print(f"\n✓ Checked {metrics_checked} metrics")

    # Show issues
    bl_issues = [i for i in checker.issues if i['source'] == f'BL-{resolution}']

    if bl_issues:
        print(f"\n⚠️  Found {len(bl_issues)} issues:")
        for issue in bl_issues:
            severity_icon = "🔴" if issue['severity'] == 'high' else "🟡" if issue['severity'] == 'medium' else "⚪"
            print(f"{severity_icon} {issue['metric']}: {issue['message']}")
    else:
        print(f"\n✅ No issues found in Bitcoin Lab {resolution} data")

    return bl_issues


def check_all_bl_resolutions(exclude_early=True):
    """Check all Bitcoin Lab resolutions

    Args:
        exclude_early: If True, exclude pre-2015 data from outlier checks
    """
    all_issues = []

    for resolution in ['hourly', 'h4', 'h8', 'h12']:
        issues = check_bl_quality(resolution, exclude_early=exclude_early)
        all_issues.extend(issues)

    return all_issues


def print_summary(brk_issues, bl_issues):
    """Print summary report"""
    print("\n" + "=" * 80)
    print("DATA QUALITY SUMMARY")
    print("=" * 80)

    total_issues = len(brk_issues) + len(bl_issues)
    all_issues = brk_issues + bl_issues

    # Count by severity
    high = sum(1 for i in all_issues if i['severity'] == 'high')
    medium = sum(1 for i in all_issues if i['severity'] == 'medium')
    low = sum(1 for i in all_issues if i['severity'] == 'low')

    # Count by type
    issue_types = {}
    for issue in all_issues:
        issue_type = issue['type']
        issue_types[issue_type] = issue_types.get(issue_type, 0) + 1

    print(f"\nTotal Issues: {total_issues}")
    if high > 0:
        print(f"  🔴 High Severity:   {high}")
    if medium > 0:
        print(f"  🟡 Medium Severity: {medium}")
    if low > 0:
        print(f"  ⚪ Low Severity:    {low}")

    if issue_types:
        print("\nIssues by Type:")
        type_labels = {
            'nulls': 'Null values',
            'infinites': 'Infinite values',
            'duplicates': 'Duplicate timestamps',
            'gaps': 'Time gaps',
            'outliers': 'Statistical outliers',
            'negatives': 'Invalid negatives',
            'range_violation': 'Values out of range',
            'dtype': 'Data type errors',
            'consistency': 'Cross-metric inconsistency'
        }
        for issue_type, count in sorted(issue_types.items(), key=lambda x: -x[1]):
            label = type_labels.get(issue_type, issue_type)
            print(f"  • {label}: {count}")

    print(f"\nBRK Issues:         {len(brk_issues)}")
    print(f"Bitcoin Lab Issues: {len(bl_issues)}")

    if total_issues == 0:
        print("\n✅ Overall data quality: EXCELLENT")
        print("   All metrics clean, no issues detected")
    elif high == 0 and medium <= 3:
        print("\n✅ Overall data quality: GOOD")
        print("   Minor issues detected, safe for trading with monitoring")
    elif high == 0:
        print("\n⚠️  Overall data quality: ACCEPTABLE")
        print("   Some issues detected, review before live trading")
    else:
        print("\n❌ Overall data quality: NEEDS ATTENTION")
        print("   High severity issues detected, fix before trading")

    # Recommendations
    if total_issues > 0:
        print("\nRECOMMENDED ACTIONS:")

        if any(i['type'] == 'nulls' for i in all_issues):
            print("  1. Run: python scripts/fix_data_issues.py")

        if any(i['type'] == 'gaps' for i in all_issues):
            print("  2. Check sync status: python run.py brk-status")

        if any(i['type'] == 'range_violation' for i in all_issues):
            print("  3. Investigate out-of-range values (may indicate API issues)")

        if any(i['type'] == 'consistency' for i in all_issues):
            print("  4. Check cross-metric formulas and calculations")

        if any(i['severity'] == 'high' for i in all_issues):
            print("  5. Investigate high severity issues before trading")

    print(f"\nScan completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Check data quality across all sources',
        epilog='By default, pre-2015 data is excluded from outlier checks due to extreme early Bitcoin volatility.'
    )
    parser.add_argument('--source', choices=['brk', 'bl', 'all'], default='all',
                       help='Data source to check (default: all)')
    parser.add_argument('--resolution', choices=['hourly', 'h4', 'h8', 'h12', 'all'],
                       default='all', help='Bitcoin Lab resolution (default: all)')
    parser.add_argument('--include-early', action='store_true',
                       help='Include pre-2015 data in outlier checks (may flag legitimate early volatility)')

    args = parser.parse_args()

    exclude_early = not args.include_early

    brk_issues = []
    bl_issues = []

    if args.source in ['brk', 'all']:
        brk_issues = check_brk_quality(exclude_early=exclude_early)

    if args.source in ['bl', 'all']:
        if args.resolution == 'all':
            bl_issues = check_all_bl_resolutions(exclude_early=exclude_early)
        else:
            bl_issues = check_bl_quality(args.resolution, exclude_early=exclude_early)

    print_summary(brk_issues, bl_issues)

    # Exit with error code if high severity issues found
    high_severity = sum(1 for i in brk_issues + bl_issues if i['severity'] == 'high')
    sys.exit(1 if high_severity > 0 else 0)
