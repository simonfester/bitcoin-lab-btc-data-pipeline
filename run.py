#!/usr/bin/env python3
"""
Run script for Bitcoin Lab data pipeline.

Usage:
    ./run.py sync                # Sync all resolutions
    ./run.py sync-daily          # Daily incremental sync
    ./run.py sync-hourly         # Hourly incremental sync
    ./run.py sync-h4             # 4-hourly incremental sync
    ./run.py sync-h8             # 8-hourly incremental sync
    ./run.py sync-h12            # 12-hourly incremental sync
    ./run.py backfill-daily      # Full daily backfill
    ./run.py backfill-hourly     # Hourly backfill from 2015-01-01
    ./run.py backfill-h4         # 4-hourly backfill
    ./run.py backfill-h8         # 8-hourly backfill
    ./run.py backfill-h12        # 12-hourly backfill
    ./run.py backfill-all        # Backfill ALL resolutions
    ./run.py status              # Show all sync status
    ./run.py info                # Check API quota (raw)
    
    === QUOTA COMMANDS ===
    ./run.py quota               # Show quota status with visual
    ./run.py quota-estimate N    # Estimate cost for N days sync
    ./run.py quota-history       # Show usage history
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.downloader import cmd_sync, cmd_backfill, cmd_status, cmd_info

RESOLUTIONS = ["d1", "h1", "h4", "h8", "h12"]

def print_usage():
    print(__doc__)
    print("Available commands:")
    print("  sync             Sync all resolutions")
    print("  sync-daily       Sync daily (d1) metrics")
    print("  sync-hourly      Sync hourly (h1) metrics")
    print("  sync-h4          Sync 4-hourly (h4) metrics")
    print("  sync-h8          Sync 8-hourly (h8) metrics")
    print("  sync-h12         Sync 12-hourly (h12) metrics")
    print("")
    print("  backfill-daily   Full daily backfill from 2015-01-01")
    print("  backfill-hourly  Hourly backfill from 2015-01-01")
    print("  backfill-h4      4-hourly backfill from 2015-01-01")
    print("  backfill-h8      8-hourly backfill from 2015-01-01")
    print("  backfill-h12     12-hourly backfill from 2015-01-01")
    print("  backfill-all     Backfill ALL resolutions (warning: high API usage)")
    print("")
    print("  status           Show sync status for all resolutions")
    print("  status-daily     Show daily sync status")
    print("  status-hourly    Show hourly sync status")
    print("  status-h4        Show 4-hourly sync status")
    print("  status-h8        Show 8-hourly sync status")
    print("  status-h12       Show 12-hourly sync status")
    print("")
    print("  info             Show raw API info")
    print("")
    print("  === QUOTA COMMANDS ===")
    print("  quota            Show quota status with visual progress bar")
    print("  quota-estimate   Estimate quota cost (usage: quota-estimate DAYS [RESOLUTION])")
    print("  quota-history    Show usage history for last 30 days")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    cmd = sys.argv[1]
    start_date = sys.argv[2] if len(sys.argv) > 2 else "2015-01-01"
    
    # === SYNC COMMANDS ===
    if cmd == "sync":
        for res in RESOLUTIONS:
            print(f"\n=== Syncing {res.upper()} ===")
            cmd_sync(res)
    
    elif cmd == "sync-daily":
        cmd_sync("d1")
    
    elif cmd == "sync-hourly":
        cmd_sync("h1")
    
    elif cmd == "sync-h4":
        cmd_sync("h4")
    
    elif cmd == "sync-h8":
        cmd_sync("h8")
    
    elif cmd == "sync-h12":
        cmd_sync("h12")
    
    # === BACKFILL COMMANDS ===
    elif cmd == "backfill-daily":
        cmd_backfill("d1", start_date)
    
    elif cmd == "backfill-hourly":
        cmd_backfill("h1", start_date)
    
    elif cmd == "backfill-h4":
        cmd_backfill("h4", start_date)
    
    elif cmd == "backfill-h8":
        cmd_backfill("h8", start_date)
    
    elif cmd == "backfill-h12":
        cmd_backfill("h12", start_date)
    
    elif cmd == "backfill-all":
        print("="*60)
        print("BACKFILLING ALL RESOLUTIONS")
        print("Warning: This will use significant API quota!")
        print("="*60)
        for res in RESOLUTIONS:
            print(f"\n{'='*60}")
            print(f"=== Backfilling {res.upper()} ===")
            print(f"{'='*60}")
            cmd_backfill(res, start_date)
    
    # === STATUS COMMANDS ===
    elif cmd == "status":
        for res in RESOLUTIONS:
            print(f"\n=== {res.upper()} Status ===")
            cmd_status(res)
    
    elif cmd == "status-daily":
        cmd_status("d1")
    
    elif cmd == "status-hourly":
        cmd_status("h1")
    
    elif cmd == "status-h4":
        cmd_status("h4")
    
    elif cmd == "status-h8":
        cmd_status("h8")
    
    elif cmd == "status-h12":
        cmd_status("h12")
    
    # === INFO ===
    elif cmd == "info":
        cmd_info()
    
    # === QUOTA COMMANDS ===
    elif cmd == "quota":
        from src.quota import cmd_quota
        cmd_quota()
    
    elif cmd == "quota-estimate":
        from src.quota import cmd_quota_estimate
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        resolution = sys.argv[3] if len(sys.argv) > 3 else "d1"
        cmd_quota_estimate(days, resolution)
    
    elif cmd == "quota-history":
        from src.quota import cmd_quota_history
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        cmd_quota_history(days)
    
    else:
        print(f"Unknown command: {cmd}\n")
        print_usage()
        sys.exit(1)
