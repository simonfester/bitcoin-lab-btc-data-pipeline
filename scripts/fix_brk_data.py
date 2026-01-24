#!/usr/bin/env python3
"""
Fix corrupted BRK data based on Glassnode validation
====================================================

Issues found:
1. supply_total: Values in satoshis instead of BTC (divide by 1e8)
2. nupl: Wrong calculation - values are absolute profit instead of ratio
3. Other metrics: Need validation

This script:
- Fixes supply_total by converting satoshis to BTC
- Flags NUPL for re-download (can't fix mathematically without source data)
- Validates other metrics against expected ranges
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import shutil

DATA_DIR = Path(__file__).parent.parent / 'data' / 'brk' / 'daily'
BACKUP_DIR = Path(__file__).parent.parent / 'data' / 'brk' / 'daily_backup'

# Create backup directory
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("BRK DATA FIX UTILITY")
print("=" * 80)
print(f"Data directory: {DATA_DIR}")
print(f"Backup directory: {BACKUP_DIR}")
print()


def backup_file(filename):
    """Backup a file before modifying"""
    src = DATA_DIR / filename
    dst = BACKUP_DIR / filename
    if src.exists():
        shutil.copy2(src, dst)
        print(f"  ✓ Backed up to {dst}")


def fix_supply_total():
    """Fix supply_total: Convert from satoshis to BTC"""
    print("1. Fixing supply_total (satoshis → BTC)")
    print("-" * 80)

    file_path = DATA_DIR / 'supply_total.parquet'

    if not file_path.exists():
        print("  ✗ File not found")
        return

    # Backup
    backup_file('supply_total.parquet')

    # Load and fix
    df = pd.read_parquet(file_path)

    print(f"  Original range: [{df['value'].min():.2e}, {df['value'].max():.2e}]")

    # Convert satoshis to BTC
    df['value'] = df['value'] / 1e8

    print(f"  Fixed range:    [{df['value'].min():.2f}, {df['value'].max():.2f}]")
    print(f"  Expected range: [18,000,000, 21,000,000]")

    # Validate fix
    if df['value'].min() >= 18_000_000 and df['value'].max() <= 21_000_000:
        # Save fixed data
        df.to_parquet(file_path, compression='zstd')
        print(f"  ✅ FIXED and saved")
    else:
        print(f"  ⚠️  Fix didn't work as expected, not saving")

    print()


def flag_nupl():
    """Flag NUPL as needing re-download"""
    print("2. Flagging NUPL for re-download")
    print("-" * 80)

    file_path = DATA_DIR / 'nupl.parquet'

    if not file_path.exists():
        print("  ✗ File not found")
        return

    # Backup
    backup_file('nupl.parquet')

    df = pd.read_parquet(file_path)
    print(f"  Current range: [{df['value'].min():.2e}, {df['value'].max():.2e}]")
    print(f"  Expected range: [-1, 1]")
    print(f"  ⚠️  Cannot fix mathematically - BRK API returns wrong data")
    print(f"  ⚠️  Recommend using Glassnode or Bitcoin Lab instead")
    print()


def validate_other_metrics():
    """Validate other metrics that showed issues"""
    print("3. Validating other metrics")
    print("-" * 80)

    metrics_to_check = {
        'sopr_lth': (0.8, 1.5),
        'mvrv': (0, 15),
    }

    for metric, (min_expected, max_expected) in metrics_to_check.items():
        file_path = DATA_DIR / f'{metric}.parquet'

        if not file_path.exists():
            print(f"  {metric}: File not found")
            continue

        df = pd.read_parquet(file_path)
        actual_min = df['value'].min()
        actual_max = df['value'].max()

        out_of_range = ((df['value'] < min_expected) | (df['value'] > max_expected)).sum()
        pct = (out_of_range / len(df)) * 100

        print(f"  {metric}:")
        print(f"    Range: [{actual_min:.2f}, {actual_max:.2f}]")
        print(f"    Expected: [{min_expected}, {max_expected}]")
        print(f"    Out of range: {out_of_range:,} rows ({pct:.1f}%)")

        if pct > 10:
            print(f"    ⚠️  High percentage out of range - may need re-download")
        elif pct > 0:
            print(f"    ℹ️  Some outliers present (may be valid extreme values)")
        else:
            print(f"    ✅ All values in expected range")
        print()


def generate_report():
    """Generate summary report"""
    print("=" * 80)
    print("FIX SUMMARY")
    print("=" * 80)
    print()
    print("✅ FIXED:")
    print("  • supply_total: Converted from satoshis to BTC")
    print()
    print("⚠️  NEEDS RE-DOWNLOAD:")
    print("  • nupl: BRK API returns wrong data format")
    print("  • nupl_sth: Likely same issue as nupl")
    print("  • nupl_lth: Likely same issue as nupl")
    print()
    print("ℹ️  RECOMMENDATIONS:")
    print("  1. Use Glassnode for NUPL metrics (more reliable)")
    print("  2. Use Bitcoin Lab as alternative for on-chain metrics")
    print("  3. Re-run data quality check: python scripts/check_data_quality.py")
    print("  4. Validate fixes: python scripts/check_data_freshness.py")
    print()
    print(f"Backups saved to: {BACKUP_DIR}")
    print("=" * 80)


if __name__ == '__main__':
    fix_supply_total()
    flag_nupl()
    validate_other_metrics()
    generate_report()
