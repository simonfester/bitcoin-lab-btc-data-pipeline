#!/usr/bin/env python3
"""
Quick fix for known data quality issues.
Run this to clean the 5 null values found in Bitcoin Lab hourly data.
"""

from pathlib import Path
import pandas as pd
import sys

def fix_bl_hourly_nulls():
    """Fix null values in Bitcoin Lab hourly SOPR metrics."""

    bl_hourly = Path(__file__).parent.parent / 'data' / 'bl' / 'hourly'

    if not bl_hourly.exists():
        print("❌ Bitcoin Lab hourly directory not found")
        return False

    print("=" * 60)
    print("FIXING BITCOIN LAB HOURLY NULL VALUES")
    print("=" * 60)

    metrics_to_fix = ['sopr', 'sopr_lth', 'sopr_sth']
    total_fixed = 0

    for metric in metrics_to_fix:
        file = bl_hourly / f'{metric}.parquet'

        if not file.exists():
            print(f"⚠️  {metric}: File not found, skipping")
            continue

        # Read data
        df = pd.read_parquet(file)
        nulls_before = df['value'].isnull().sum()

        if nulls_before == 0:
            print(f"✓ {metric}: Already clean (no nulls)")
            continue

        # Forward fill nulls (max 3 consecutive to avoid propagating bad data)
        df['value'] = df['value'].fillna(method='ffill', limit=3)

        # If still nulls (at beginning), backward fill
        if df['value'].isnull().any():
            df['value'] = df['value'].fillna(method='bfill', limit=3)

        nulls_after = df['value'].isnull().sum()
        fixed_count = nulls_before - nulls_after

        # Save cleaned version
        df.to_parquet(file)

        print(f"✓ {metric}: Fixed {fixed_count} nulls ({nulls_before} → {nulls_after})")
        total_fixed += fixed_count

    print("\n" + "=" * 60)
    print(f"TOTAL: Fixed {total_fixed} null values")
    print("=" * 60)

    return total_fixed > 0

def verify_fix():
    """Verify that fixes worked."""

    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    bl_hourly = Path(__file__).parent.parent / 'data' / 'bl' / 'hourly'
    metrics = ['sopr', 'sopr_lth', 'sopr_sth', 'price', 'realized_loss']

    all_clean = True

    for metric in metrics:
        file = bl_hourly / f'{metric}.parquet'

        if not file.exists():
            continue

        df = pd.read_parquet(file)
        null_count = df['value'].isnull().sum()

        if null_count > 0:
            print(f"⚠️  {metric}: Still has {null_count} nulls")
            all_clean = False
        else:
            print(f"✓ {metric}: Clean (0 nulls)")

    if all_clean:
        print("\n✅ All metrics are now clean!")
    else:
        print("\n⚠️  Some nulls remain (may be at edges where fill limit reached)")

    return all_clean

if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════════════════════╗
║        DATA QUALITY FIX - Bitcoin Lab Hourly              ║
╚═══════════════════════════════════════════════════════════╝

This script will:
  1. Fix null values in sopr, sopr_lth, sopr_sth
  2. Use forward fill (max 3 consecutive)
  3. Backup not created (parquet files will be overwritten)

""")

    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)

    print()
    fixed = fix_bl_hourly_nulls()

    if fixed:
        verify_fix()
        print("\n✅ Data cleaning complete!")
    else:
        print("\n✓ No issues found - data already clean")
