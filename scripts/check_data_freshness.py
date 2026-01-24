#!/usr/bin/env python3
"""
Data Freshness Checker - Verify data is up-to-date
===================================================
Checks when data was last updated for all sources and resolutions.

Usage:
    python check_data_freshness.py              # Check all sources
    python check_data_freshness.py --source brk # Check specific source
    python check_data_freshness.py --json       # Output as JSON
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import sys
import json

DATA_DIR = Path(__file__).parent.parent / 'data'


def get_file_freshness(file_path: Path, expected_freq='1D') -> dict:
    """Get freshness info for a parquet file with resolution-aware thresholds"""
    try:
        df = pd.read_parquet(file_path)

        if len(df) == 0:
            return {
                'status': 'error',
                'message': 'Empty file',
                'last_timestamp': None,
                'age_hours': None,
                'rows': 0
            }

        # Handle both time as column and time as index
        if 'time' in df.columns:
            last_timestamp = df['time'].max()
        elif df.index.name == 'time' or isinstance(df.index, pd.DatetimeIndex):
            last_timestamp = df.index.max()
        else:
            return {
                'status': 'error',
                'message': 'No time column or datetime index',
                'last_timestamp': None,
                'age_hours': None,
                'rows': 0
            }
        now = pd.Timestamp.now(tz='UTC')

        # Make sure last_timestamp is timezone-aware
        if last_timestamp.tz is None:
            last_timestamp = last_timestamp.tz_localize('UTC')

        age = now - last_timestamp
        age_hours = age.total_seconds() / 3600

        # Strict resolution-aware freshness thresholds
        # Fresh = within the expected update interval
        # Note: Daily aggregates have 1-day publication lag (normal)

        thresholds = {
            '1H': 1,      # Hourly: fresh if ≤ 1h
            '4H': 4,      # 4-hourly: fresh if ≤ 4h
            '8H': 8,      # 8-hourly: fresh if ≤ 8h
            '12H': 12,    # 12-hourly: fresh if ≤ 12h
            '1D': 48,     # Daily: fresh if ≤ 48h (allows for 1-day publication lag)
        }

        fresh_threshold = thresholds.get(expected_freq, thresholds['1D'])

        # Simple binary: fresh or stale
        if age_hours <= fresh_threshold:
            status = 'fresh'
        else:
            status = 'stale'

        return {
            'status': status,
            'last_timestamp': last_timestamp.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'age_hours': round(age_hours, 1),
            'age_days': round(age_hours / 24, 1),
            'rows': len(df),
            'message': f"{round(age_hours, 1)}h ago",
            'expected_freq': expected_freq
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error: {str(e)[:50]}',
            'last_timestamp': None,
            'age_hours': None,
            'rows': 0
        }


def check_brk_freshness() -> dict:
    """Check BRK data freshness"""
    brk_dir = DATA_DIR / 'brk' / 'daily'

    if not brk_dir.exists():
        return {
            'source': 'BRK',
            'status': 'missing',
            'message': 'Directory not found',
            'metrics': {}
        }

    files = list(brk_dir.glob('*.parquet'))

    if not files:
        return {
            'source': 'BRK',
            'status': 'empty',
            'message': 'No data files found',
            'metrics': {}
        }

    # Check a sample of key metrics
    key_metrics = ['price', 'sopr', 'mvrv', 'nupl']
    metrics_info = {}

    for metric in key_metrics:
        file = brk_dir / f'{metric}.parquet'
        if file.exists():
            metrics_info[metric] = get_file_freshness(file, expected_freq='1D')

    # Get overall status (use price as representative)
    if 'price' in metrics_info:
        overall_status = metrics_info['price']['status']
        overall_age = metrics_info['price']['age_hours']
        last_update = metrics_info['price']['last_timestamp']
    else:
        overall_status = 'unknown'
        overall_age = None
        last_update = None

    return {
        'source': 'BRK',
        'resolution': 'daily',
        'status': overall_status,
        'last_update': last_update,
        'age_hours': overall_age,
        'total_files': len(files),
        'metrics': metrics_info
    }


def check_bl_freshness(resolution='hourly') -> dict:
    """Check Bitcoin Lab data freshness"""
    resolution_map = {
        'hourly': 'hourly',
        'h1': 'hourly',
        'h4': 'h4',
        'h8': 'h8',
        'h12': 'h12',
        'daily': 'daily',
        'd1': 'daily'
    }

    freq_map = {
        'hourly': '1H',
        'h4': '4H',
        'h8': '8H',
        'h12': '12H',
        'daily': '1D'
    }

    res_dir = resolution_map.get(resolution, resolution)
    expected_freq = freq_map.get(res_dir, '1H')
    bl_dir = DATA_DIR / 'bl' / res_dir

    if not bl_dir.exists():
        return {
            'source': 'Bitcoin Lab',
            'resolution': resolution,
            'status': 'missing',
            'message': 'Directory not found',
            'metrics': {}
        }

    files = list(bl_dir.glob('*.parquet'))

    if not files:
        return {
            'source': 'Bitcoin Lab',
            'resolution': resolution,
            'status': 'empty',
            'message': 'No data files found',
            'metrics': {}
        }

    # Check all metrics (usually just 5) with resolution-aware thresholds
    metrics_info = {}

    for file in files:
        metric = file.stem
        metrics_info[metric] = get_file_freshness(file, expected_freq=expected_freq)

    # Get overall status (use price as representative)
    if 'price' in metrics_info:
        overall_status = metrics_info['price']['status']
        overall_age = metrics_info['price']['age_hours']
        last_update = metrics_info['price']['last_timestamp']
    else:
        # Use first available metric
        first_metric = list(metrics_info.keys())[0]
        overall_status = metrics_info[first_metric]['status']
        overall_age = metrics_info[first_metric]['age_hours']
        last_update = metrics_info[first_metric]['last_timestamp']

    return {
        'source': 'Bitcoin Lab',
        'resolution': resolution,
        'status': overall_status,
        'last_update': last_update,
        'age_hours': overall_age,
        'total_files': len(files),
        'metrics': metrics_info
    }


def check_glassnode_freshness() -> dict:
    """Check Glassnode data freshness"""
    gn_dir = DATA_DIR / 'glassnode' / 'daily'

    if not gn_dir.exists():
        return {
            'source': 'Glassnode',
            'resolution': 'daily',
            'status': 'missing',
            'message': 'Directory not found',
            'metrics': {}
        }

    files = list(gn_dir.glob('*.parquet'))

    if not files:
        return {
            'source': 'Glassnode',
            'resolution': 'daily',
            'status': 'empty',
            'message': 'No data files found',
            'metrics': {}
        }

    # Check derivatives metrics
    key_metrics = ['funding_rate', 'liquidations_long', 'liquidations_short', 'open_interest']
    metrics_info = {}

    for metric in key_metrics:
        file = gn_dir / f'{metric}.parquet'
        if file.exists():
            metrics_info[metric] = get_file_freshness(file, expected_freq='1D')

    # Get overall status (use funding_rate as representative)
    if 'funding_rate' in metrics_info:
        overall_status = metrics_info['funding_rate']['status']
        overall_age = metrics_info['funding_rate']['age_hours']
        last_update = metrics_info['funding_rate']['last_timestamp']
    elif metrics_info:
        # Use first available metric
        first_metric = list(metrics_info.keys())[0]
        overall_status = metrics_info[first_metric]['status']
        overall_age = metrics_info[first_metric]['age_hours']
        last_update = metrics_info[first_metric]['last_timestamp']
    else:
        overall_status = 'unknown'
        overall_age = None
        last_update = None

    return {
        'source': 'Glassnode',
        'resolution': 'daily',
        'status': overall_status,
        'last_update': last_update,
        'age_hours': overall_age,
        'total_files': len(files),
        'metrics': metrics_info
    }


def print_freshness_report(results: list, as_json: bool = False):
    """Print freshness report"""

    if as_json:
        print(json.dumps(results, indent=2))
        return

    print("=" * 80)
    print("DATA FRESHNESS REPORT")
    print("=" * 80)
    print(f"Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Categorize results by importance
    critical_sources = []  # Daily data used for signals
    non_critical_sources = []  # Hourly data (optional)

    for result in results:
        resolution = result.get('resolution', '')
        if resolution == 'daily':
            critical_sources.append(result)
        else:
            non_critical_sources.append(result)

    # Show critical sources first
    if critical_sources:
        print("CRITICAL DATA (Used for Daily Signals):")
        print("-" * 80)
        for result in critical_sources:
            source = result.get('source')
            resolution = result.get('resolution', '')
            status = result.get('status')
            last_update = result.get('last_update', 'Unknown')
            age_hours = result.get('age_hours')

            # Status icons
            status_icon = {
                'fresh': '✅',
                'stale': '🔴',
                'missing': '❌',
                'empty': '❌',
                'error': '⚠️',
                'unknown': '❓'
            }.get(status, '❓')

            print(f"{status_icon} {source} ({resolution})")
            print(f"   Status: {status.upper()}")
            print(f"   Last Update: {last_update}")

            if age_hours is not None:
                days = age_hours / 24
                if days >= 1:
                    print(f"   Age: {days:.1f} days ({age_hours:.1f} hours)")
                else:
                    print(f"   Age: {age_hours:.1f} hours")

            print(f"   Files: {result.get('total_files', 0)}")
            print()

    # Show non-critical sources
    if non_critical_sources:
        print("\nOPTIONAL DATA (Not used for daily signals, can be stale):")
        print("-" * 80)
        for result in non_critical_sources:
            source = result.get('source')
            resolution = result.get('resolution', '')
            status = result.get('status')
            last_update = result.get('last_update', 'Unknown')
            age_hours = result.get('age_hours')

            # Use different icons for non-critical sources
            if status == 'stale':
                status_icon = '⚠️'  # Warning instead of red X
            else:
                status_icon = {
                    'fresh': '✅',
                    'missing': '❌',
                    'empty': '❌',
                    'error': '⚠️',
                    'unknown': '❓'
                }.get(status, '❓')

            print(f"{status_icon} {source} ({resolution})")
            print(f"   Status: {status.upper()}")
            print(f"   Last Update: {last_update}")

            if age_hours is not None:
                days = age_hours / 24
                if days >= 1:
                    print(f"   Age: {days:.1f} days ({age_hours:.1f} hours)")
                else:
                    print(f"   Age: {age_hours:.1f} hours")

            print(f"   Files: {result.get('total_files', 0)}")
            print()

    # Overall assessment (focus on critical sources only)
    print("=" * 80)
    print("FRESHNESS SUMMARY")
    print("=" * 80)

    # Count all sources
    fresh_count = sum(1 for r in results if r.get('status') == 'fresh')
    stale_count = sum(1 for r in results if r.get('status') == 'stale')
    missing_count = sum(1 for r in results if r.get('status') in ['missing', 'empty'])
    error_count = sum(1 for r in results if r.get('status') == 'error')

    # Count critical sources only
    critical_results = critical_sources  # From above
    critical_fresh = sum(1 for r in critical_results if r.get('status') == 'fresh')
    critical_stale = sum(1 for r in critical_results if r.get('status') == 'stale')
    critical_missing = sum(1 for r in critical_results if r.get('status') in ['missing', 'empty'])

    total = len(results)
    total_critical = len(critical_results)

    print(f"All Sources:      {fresh_count}/{total} fresh")
    print(f"Critical (Daily): {critical_fresh}/{total_critical} fresh")
    print()
    print(f"✅ Fresh:         {fresh_count}/{total}")
    print(f"🔴 Stale:         {stale_count}/{total}")
    print(f"❌ Missing/Empty: {missing_count}/{total}")
    if error_count > 0:
        print(f"⚠️  Errors:        {error_count}/{total}")

    print("\nFreshness Thresholds:")
    print("  Hourly (h1):   Fresh if ≤ 1h")
    print("  4-hourly (h4): Fresh if ≤ 4h")
    print("  8-hourly (h8): Fresh if ≤ 8h")
    print("  12-hourly:     Fresh if ≤ 12h")
    print("  Daily:         Fresh if ≤ 48h (allows for 1-day publication lag)")

    # Assessment based on CRITICAL sources only
    if critical_fresh == total_critical:
        print("\n✅ All CRITICAL data sources are FRESH - ready for signals!")
        if stale_count > 0:
            print("   (Note: Some optional hourly data is stale, but this doesn't affect daily signals)")
    elif critical_stale > 0:
        print("\n🔴 CRITICAL data sources are STALE - run sync immediately!")

    if critical_missing > 0:
        print("\n❌ CRITICAL data sources are MISSING - run initial sync!")

    print("\nRECOMMENDED ACTIONS:")

    actions_needed = False

    for result in results:
        status = result.get('status')
        source = result.get('source')
        resolution = result.get('resolution', '')

        if status == 'stale':
            actions_needed = True
            if source == 'BRK':
                print(f"  • Run: python run.py brk-sync")
            elif source == 'Bitcoin Lab':
                if resolution == 'hourly':
                    print(f"  • Run: python run.py bl-sync-hourly")
                else:
                    print(f"  • Run: python run.py bl-sync-{resolution}")
            elif source == 'Glassnode':
                print(f"  • Run: python run.py gn-sync  (or manual Glassnode sync)")

        if status in ['missing', 'empty']:
            actions_needed = True
            if source == 'BRK':
                print(f"  • Run: python run.py brk-backfill")
            elif source == 'Bitcoin Lab':
                print(f"  • Run: python run.py bl-backfill-{resolution}")
            elif source == 'Glassnode':
                print(f"  • Run: python run.py gn-backfill  (or manual Glassnode sync)")

    if not actions_needed:
        print("  None - all data is fresh!")


def main():
    """Check data freshness across all sources"""
    import argparse

    parser = argparse.ArgumentParser(description='Check data freshness')
    parser.add_argument('--source', choices=['brk', 'bl', 'gn', 'all'], default='all',
                       help='Data source to check (default: all)')
    parser.add_argument('--resolution', choices=['daily', 'hourly', 'h4', 'h8', 'h12', 'all'],
                       default='all', help='Bitcoin Lab resolution (default: all)')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')

    args = parser.parse_args()

    results = []

    # Check BRK
    if args.source in ['brk', 'all']:
        results.append(check_brk_freshness())

    # Check Bitcoin Lab
    if args.source in ['bl', 'all']:
        if args.resolution == 'all':
            for res in ['daily', 'hourly', 'h4', 'h8', 'h12']:
                results.append(check_bl_freshness(res))
        else:
            results.append(check_bl_freshness(args.resolution))

    # Check Glassnode
    if args.source in ['gn', 'all']:
        results.append(check_glassnode_freshness())

    print_freshness_report(results, as_json=args.json)

    # Exit with error code ONLY if CRITICAL (daily) sources are stale or missing
    # Hourly data being stale is not a blocker for daily signals
    critical_issues = sum(1 for r in results
                         if r.get('resolution') == 'daily' and
                         r.get('status') in ['stale', 'missing', 'empty'])

    sys.exit(1 if critical_issues > 0 else 0)


if __name__ == '__main__':
    main()
