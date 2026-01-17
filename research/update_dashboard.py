#!/usr/bin/env python3
"""
Update Dashboard Data
=====================
Fetches latest data from Bitcoin Lab API and regenerates the dashboard.

Usage:
    python update_dashboard.py
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Change to project directory
PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data" / "daily"

print("=" * 60)
print("Dashboard Data Updater")
print("=" * 60)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Data dir: {DATA_DIR}")

# Check current data freshness
print("\n📊 Checking data freshness...")
import pandas as pd

metrics_to_check = ['price', 'sopr', 'sopr_sth', 'mvrv_z']
for metric in metrics_to_check:
    path = DATA_DIR / f"{metric}.parquet"
    if path.exists():
        df = pd.read_parquet(path)
        latest = df.iloc[-1]['time']
        print(f"  {metric}: latest = {latest}")
    else:
        print(f"  {metric}: MISSING")

# Ask user if they want to update
print("\n" + "=" * 60)
response = input("Do you want to download fresh data? [y/N]: ").strip().lower()

if response == 'y':
    print("\n📥 Downloading fresh data...")
    
    # Run the download command
    import os
    os.chdir(PROJECT_DIR)
    
    # Download key metrics
    metrics = [
        'price', 'sopr', 'sopr_sth', 'sopr_lth', 'realized_loss',
        'mvrv', 'mvrv_z', 'nupl', 'aviv',
        'realized_price', 'realized_price_sth', 'realized_price_lth',
        'true_market_mean_price', 'vaulted_price',
        'market_cap', 'realized_cap'
    ]
    
    for metric in metrics:
        print(f"  Downloading {metric}...")
        result = subprocess.run(
            [sys.executable, 'run.py', 'download', '--metrics', metric, '--resolution', 'd1'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"    ⚠️  Error: {result.stderr[:100] if result.stderr else 'Unknown error'}")
        else:
            print(f"    ✓ Done")
    
    print("\n✓ Data download complete!")

# Generate dashboard
print("\n📊 Generating dashboard...")
subprocess.run([sys.executable, str(PROJECT_DIR / "research" / "dashboard.py"), '--no-open'])

print("\n✓ Dashboard updated!")
print(f"  Open: {PROJECT_DIR / 'research' / 'dashboard.html'}")
