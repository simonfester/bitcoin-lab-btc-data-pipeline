#!/usr/bin/env python3
"""
Run script for Bitcoin Lab data pipeline.

Usage:
    ./run.py sync          # Daily incremental sync
    ./run.py backfill      # Full historical download
    ./run.py status        # Check sync status
    ./run.py info          # Check API quota
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.downloader import cmd_sync, cmd_backfill, cmd_status, cmd_info

if __name__ == "__main__":
    commands = {
        "sync": cmd_sync,
        "backfill": cmd_backfill,
        "status": cmd_status,
        "info": cmd_info,
    }
    
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(__doc__)
        print(f"Available commands: {', '.join(commands.keys())}")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "backfill" and len(sys.argv) > 2:
        commands[cmd](sys.argv[2])
    else:
        commands[cmd]()
