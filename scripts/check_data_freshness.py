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


def get_file_freshness(file_path: Path) -> dict:
    """Get freshness info for a parquet file"""
    try:
        df = pd.read_parquet(file_path)

        if 'time' not in df.columns or len(df) == 0:
            return {
                'status': 'error',
                'message': 'No time column or empty file',
                'last_timestamp': None,
                'age_hours': None,
                'rows': 0
            }

        last_timestamp = df['time'].max()
        now = pd.Timestamp.now(tz='UTC')

        # Make sure last_timestamp is timezone-aware
        if last_timestamp.tz is None:
            last_timestamp = last_timestamp.tz_localize('UTC')

        age = now - last_timestamp
        age_hours = age.total_seconds() / 3600

        # Determine status based on age
        if age_hours < 24:
            status = 'fresh'
        elif age_hours < 48:
            status = 'acceptable'
        elif age_hours < 168:  # 1 week
            status = 'stale'
        else:
            status = 'very_stale'

        return {
            'status': status,
            'last_timestamp': last_timestamp.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'age_hours': round(age_hours, 1),
            'age_days': round(age_hours / 24, 1),
            'rows': len(df),
            'message': f"{round(age_hours, 1)}h ago"
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
            metrics_info[metric] = get_file_freshness(file)

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
        'h12': 'h12'
    }

    res_dir = resolution_map.get(resolution, resolution)
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

    # Check all metrics (usually just 5)
    metrics_info = {}

    for file in files:
        metric = file.stem
        metrics_info[metric] = get_file_freshness(file)

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

    for result in results:
        source = result.get('source')
        resolution = result.get('resolution', '')
        status = result.get('status')
        last_update = result.get('last_update', 'Unknown')
        age_hours = result.get('age_hours')

        # Status icons
        status_icon = {
            'fresh': '✅',
            'acceptable': '🟡',
            'stale': '🟠',
            'very_stale': '🔴',
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

    # Overall assessment
    print("=" * 80)
    print("FRESHNESS SUMMARY")
    print("=" * 80)

    fresh_count = sum(1 for r in results if r.get('status') == 'fresh')
    stale_count = sum(1 for r in results if r.get('status') in ['stale', 'very_stale'])
    missing_count = sum(1 for r in results if r.get('status') in ['missing', 'empty'])

    total = len(results)

    print(f"Fresh (<24h):     {fresh_count}/{total}")
    print(f"Stale (>48h):     {stale_count}/{total}")
    print(f"Missing/Empty:    {missing_count}/{total}")

    if fresh_count == total:
        print("\n✅ All data sources are FRESH")
    elif stale_count > 0:
        print("\n⚠️  Some data sources are STALE - consider running sync")

    if missing_count > 0:
        print("\n❌ Some data sources are MISSING - run initial sync")

    print("\nRECOMMENDED ACTIONS:")

    for result in results:
        status = result.get('status')
        source = result.get('source')
        resolution = result.get('resolution', '')

        if status == 'stale' or status == 'very_stale':
            if source == 'BRK':
                print(f"  • Run: python run.py brk-sync")
            elif source == 'Bitcoin Lab':
                if resolution == 'hourly':
                    print(f"  • Run: python run.py bl-sync-hourly")
                else:
                    print(f"  • Run: python run.py bl-sync-{resolution}")

        if status == 'missing' or status == 'empty':
            if source == 'BRK':
                print(f"  • Run: python run.py brk-backfill")
            elif source == 'Bitcoin Lab':
                print(f"  • Run: python run.py bl-backfill-{resolution}")


def main():
    """Check data freshness across all sources"""
    import argparse

    parser = argparse.ArgumentParser(description='Check data freshness')
    parser.add_argument('--source', choices=['brk', 'bl', 'all'], default='all',
                       help='Data source to check (default: all)')
    parser.add_argument('--resolution', choices=['hourly', 'h4', 'h8', 'h12', 'all'],
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
            for res in ['hourly', 'h4', 'h8', 'h12']:
                results.append(check_bl_freshness(res))
        else:
            results.append(check_bl_freshness(args.resolution))

    print_freshness_report(results, as_json=args.json)

    # Exit with error code if any stale or missing
    stale_or_missing = sum(1 for r in results
                          if r.get('status') in ['stale', 'very_stale', 'missing', 'empty'])

    sys.exit(1 if stale_or_missing > 0 else 0)


if __name__ == '__main__':
    main()
