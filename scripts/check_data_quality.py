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

    def check_outliers(self, df, metric, source):
        """Check for statistical outliers using Z-score"""
        values = df['value'].dropna()

        if len(values) < 100:
            return 0  # Not enough data for meaningful outlier detection

        # Calculate Z-scores
        mean = values.mean()
        std = values.std()

        if std == 0:
            return 0

        z_scores = np.abs((values - mean) / std)
        outliers = (z_scores > 6).sum()  # Very conservative threshold (6 sigma)

        if outliers > 0:
            outlier_pct = (outliers / len(values)) * 100
            if outlier_pct > 0.1:  # Only flag if > 0.1%
                self.issues.append({
                    'source': source,
                    'metric': metric,
                    'type': 'outliers',
                    'severity': 'medium',
                    'count': outliers,
                    'message': f"{outliers:,} statistical outliers (>6σ, {outlier_pct:.2f}%)"
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


def check_brk_quality():
    """Check BRK data quality"""
    brk_dir = DATA_DIR / 'brk' / 'daily'

    if not brk_dir.exists():
        print("⚠️  BRK directory not found")
        return []

    print("=" * 80)
    print("BRK DATA QUALITY CHECK (DAILY)")
    print("=" * 80)

    checker = DataQualityChecker()
    metrics_checked = 0

    for file in sorted(brk_dir.glob('*.parquet')):
        metric = file.stem
        try:
            df = pd.read_parquet(file)

            # Run all checks
            checker.check_nulls(df, metric, 'BRK')
            checker.check_infinites(df, metric, 'BRK')
            checker.check_duplicates(df, metric, 'BRK')
            checker.check_gaps(df, metric, 'BRK', expected_freq='1D')
            checker.check_outliers(df, metric, 'BRK')
            checker.check_negatives(df, metric, 'BRK')

            metrics_checked += 1

        except Exception as e:
            print(f"✗ {metric}: Error - {str(e)[:50]}")

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


def check_bl_quality(resolution='hourly'):
    """Check Bitcoin Lab data quality"""
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
    print("=" * 80)

    checker = DataQualityChecker()
    metrics_checked = 0

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
            checker.check_outliers(df, metric, f'BL-{resolution}')
            checker.check_negatives(df, metric, f'BL-{resolution}')

            metrics_checked += 1

        except Exception as e:
            print(f"✗ {metric}: Error - {str(e)[:50]}")

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


def check_all_bl_resolutions():
    """Check all Bitcoin Lab resolutions"""
    all_issues = []

    for resolution in ['hourly', 'h4', 'h8', 'h12']:
        issues = check_bl_quality(resolution)
        all_issues.extend(issues)

    return all_issues


def print_summary(brk_issues, bl_issues):
    """Print summary report"""
    print("\n" + "=" * 80)
    print("DATA QUALITY SUMMARY")
    print("=" * 80)

    total_issues = len(brk_issues) + len(bl_issues)

    # Count by severity
    high = sum(1 for i in brk_issues + bl_issues if i['severity'] == 'high')
    medium = sum(1 for i in brk_issues + bl_issues if i['severity'] == 'medium')
    low = sum(1 for i in brk_issues + bl_issues if i['severity'] == 'low')

    print(f"\nTotal Issues: {total_issues}")
    if high > 0:
        print(f"  🔴 High Severity:   {high}")
    if medium > 0:
        print(f"  🟡 Medium Severity: {medium}")
    if low > 0:
        print(f"  ⚪ Low Severity:    {low}")

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

        if any(i['type'] == 'nulls' for i in brk_issues + bl_issues):
            print("  1. Run: python scripts/fix_data_issues.py")

        if any(i['type'] == 'gaps' for i in brk_issues + bl_issues):
            print("  2. Check sync status: python run.py brk-status")

        if any(i['severity'] == 'high' for i in brk_issues + bl_issues):
            print("  3. Investigate high severity issues before trading")

    print(f"\nScan completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Check data quality across all sources')
    parser.add_argument('--source', choices=['brk', 'bl', 'all'], default='all',
                       help='Data source to check (default: all)')
    parser.add_argument('--resolution', choices=['hourly', 'h4', 'h8', 'h12', 'all'],
                       default='all', help='Bitcoin Lab resolution (default: all)')

    args = parser.parse_args()

    brk_issues = []
    bl_issues = []

    if args.source in ['brk', 'all']:
        brk_issues = check_brk_quality()

    if args.source in ['bl', 'all']:
        if args.resolution == 'all':
            bl_issues = check_all_bl_resolutions()
        else:
            bl_issues = check_bl_quality(args.resolution)

    print_summary(brk_issues, bl_issues)

    # Exit with error code if high severity issues found
    high_severity = sum(1 for i in brk_issues + bl_issues if i['severity'] == 'high')
    sys.exit(1 if high_severity > 0 else 0)
