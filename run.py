#!/usr/bin/env python3
"""
Run script for Bitcoin Lab data pipeline.

Usage:
    === BITCOIN LAB COMMANDS (paid, hourly+daily) ===
    ./run.py bl-sync              # Sync all resolutions
    ./run.py bl-sync-daily        # Daily incremental sync
    ./run.py bl-sync-hourly       # Hourly incremental sync
    ./run.py bl-sync-h4           # 4-hourly incremental sync
    ./run.py bl-sync-h8           # 8-hourly incremental sync
    ./run.py bl-sync-h12          # 12-hourly incremental sync
    ./run.py bl-backfill-daily    # Full daily backfill
    ./run.py bl-backfill-hourly   # Hourly backfill from 2015-01-01
    ./run.py bl-backfill-h4       # 4-hourly backfill
    ./run.py bl-backfill-h8       # 8-hourly backfill
    ./run.py bl-backfill-h12      # 12-hourly backfill
    ./run.py bl-backfill-all      # Backfill ALL resolutions
    ./run.py bl-status            # Show all sync status
    ./run.py bl-info              # Check API quota (raw)
    
    === BRK COMMANDS (FREE, daily only) ===
    ./run.py brk-sync             # BRK incremental sync
    ./run.py brk-backfill         # BRK full backfill
    ./run.py brk-status           # Show BRK sync status
    
    === QUOTA COMMANDS ===
    ./run.py quota                # Show quota status with visual
    ./run.py quota-estimate N     # Estimate cost for N days sync
    ./run.py quota-history        # Show usage history
    
    === DATA LOADER COMMANDS ===
    ./run.py data                 # Show cache status
    ./run.py data-refresh         # Refresh cache from BRK (free)
    ./run.py data-load METRICS    # Load metrics (comma-separated)
    ./run.py signals              # Check current strategy signals

    === DASHBOARD COMMANDS ===
    ./run.py dashboard            # Full pipeline: sync all (includes hourly) + calculate + open
    ./run.py dashboard --skip-hourly  # Skip hourly data sync (saves quota)
    ./run.py dashboard-quick      # Skip sync, just calculate and open dashboard
    ./run.py dashboard-quality    # Check data quality only

    === BACKTEST DATABASE COMMANDS ===
    ./run.py backtest-stats       # Show database statistics
    ./run.py backtest-list        # List recent backtest runs
    ./run.py backtest-top sharpe  # Top runs by metric (sharpe, return_pct, etc)
    ./run.py backtest-strategies  # Summary by strategy
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.downloader import cmd_sync, cmd_backfill, cmd_status, cmd_info

RESOLUTIONS = ["d1", "h1", "h4", "h8", "h12"]

def print_usage():
    print(__doc__)
    print("Available commands:")
    print("")
    print("  === BITCOIN LAB (paid, hourly+daily) ===")
    print("  bl-sync           Sync all resolutions")
    print("  bl-sync-daily     Sync daily (d1) metrics")
    print("  bl-sync-hourly    Sync hourly (h1) metrics")
    print("  bl-sync-h4        Sync 4-hourly (h4) metrics")
    print("  bl-sync-h8        Sync 8-hourly (h8) metrics")
    print("  bl-sync-h12       Sync 12-hourly (h12) metrics")
    print("")
    print("  bl-backfill-daily   Full daily backfill from 2015-01-01")
    print("  bl-backfill-hourly  Hourly backfill from 2015-01-01")
    print("  bl-backfill-h4      4-hourly backfill from 2015-01-01")
    print("  bl-backfill-h8      8-hourly backfill from 2015-01-01")
    print("  bl-backfill-h12     12-hourly backfill from 2015-01-01")
    print("  bl-backfill-all     Backfill ALL resolutions (warning: high API usage)")
    print("")
    print("  bl-status         Show sync status for all resolutions")
    print("  bl-status-daily   Show daily sync status")
    print("  bl-status-hourly  Show hourly sync status")
    print("  bl-info           Show raw API info")
    print("")
    print("  === BRK (FREE, daily only) ===")
    print("  brk-sync          Incremental sync (only new data)")
    print("  brk-backfill      Full historical download")
    print("  brk-status        Show sync status")
    print("  brk-discover      List available metrics")
    print("  brk-discover X    Search for metrics matching 'X'")
    print("")
    print("  === QUOTA COMMANDS ===")
    print("  quota             Show quota status with visual progress bar")
    print("  quota-estimate    Estimate quota cost (usage: quota-estimate DAYS [RESOLUTION])")
    print("  quota-history     Show usage history for last 30 days")
    print("")
    print("  === DATA LOADER COMMANDS ===")
    print("  data              Show cache freshness status")
    print("  data-refresh      Refresh ALL metrics from BRK API (FREE)")
    print("  data-load         Load metrics: data-load price,sopr,mvrv")
    print("  signals           Check current STRAT-003 and Checkmate signals")
    print("")
    print("  === DASHBOARD COMMANDS ===")
    print("  dashboard         Full pipeline: sync all → quality checks → calculate → open")
    print("  dashboard-quick   Skip sync, just calculate and open dashboard")
    print("  dashboard-quality Check data freshness and quality only")
    print("")
    print("  === BACKTEST DATABASE COMMANDS ===")
    print("  backtest-stats      Show database statistics")
    print("  backtest-list [N]   List recent N runs (default: 20)")
    print("  backtest-top [M] [N]  Top N runs by metric M (default: sharpe, 10)")
    print("  backtest-strategies Summary by strategy with best performance")
    print("  backtest-gui        Launch Streamlit backtest GUI")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    cmd = sys.argv[1]
    start_date = sys.argv[2] if len(sys.argv) > 2 else "2015-01-01"
    
    # === BL (BITCOIN LAB) SYNC COMMANDS ===
    if cmd == "bl-sync":
        for res in RESOLUTIONS:
            print(f"\n=== Syncing {res.upper()} ===")
            cmd_sync(res)
    
    elif cmd == "bl-sync-daily":
        cmd_sync("d1")
    
    elif cmd == "bl-sync-hourly":
        cmd_sync("h1")
    
    elif cmd == "bl-sync-h4":
        cmd_sync("h4")
    
    elif cmd == "bl-sync-h8":
        cmd_sync("h8")
    
    elif cmd == "bl-sync-h12":
        cmd_sync("h12")
    
    # === BL BACKFILL COMMANDS ===
    elif cmd == "bl-backfill-daily":
        cmd_backfill("d1", start_date)
    
    elif cmd == "bl-backfill-hourly":
        cmd_backfill("h1", start_date)
    
    elif cmd == "bl-backfill-h4":
        cmd_backfill("h4", start_date)
    
    elif cmd == "bl-backfill-h8":
        cmd_backfill("h8", start_date)
    
    elif cmd == "bl-backfill-h12":
        cmd_backfill("h12", start_date)
    
    elif cmd == "bl-backfill-all":
        print("="*60)
        print("BACKFILLING ALL RESOLUTIONS")
        print("Warning: This will use significant API quota!")
        print("="*60)
        for res in RESOLUTIONS:
            print(f"\n{'='*60}")
            print(f"=== Backfilling {res.upper()} ===")
            print(f"{'='*60}")
            cmd_backfill(res, start_date)
    
    # === BL STATUS COMMANDS ===
    elif cmd == "bl-status":
        for res in RESOLUTIONS:
            print(f"\n=== {res.upper()} Status ===")
            cmd_status(res)
    
    elif cmd == "bl-status-daily":
        cmd_status("d1")
    
    elif cmd == "bl-status-hourly":
        cmd_status("h1")
    
    elif cmd == "bl-status-h4":
        cmd_status("h4")
    
    elif cmd == "bl-status-h8":
        cmd_status("h8")
    
    elif cmd == "bl-status-h12":
        cmd_status("h12")
    
    # === BL INFO ===
    elif cmd == "bl-info":
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
    
    # === DATA LOADER COMMANDS ===
    elif cmd == "data":
        from src.data_loader import DataLoader
        loader = DataLoader()
        print("=" * 60)
        print("DATA CACHE STATUS")
        print("=" * 60)
        freshness = loader.check_data_freshness()
        print(freshness.to_string(index=False))
        
        stale = freshness[freshness['age_days'] > 1] if 'age_days' in freshness.columns else None
        if stale is not None and len(stale) > 0:
            print(f"\n⚠️  {len(stale)} metrics are stale (>1 day old)")
            print("Run 'python run.py data-refresh' to update from BRK (FREE)")
    
    elif cmd == "data-refresh":
        from src.data_loader import DataLoader
        loader = DataLoader()
        print("=" * 60)
        print("REFRESHING CACHE FROM BRK API (FREE)")
        print("=" * 60)
        
        # Core metrics for our strategies (including James Check framework)
        core_metrics = [
            # Price & Technical
            'price', 'price_200d_sma',
            
            # SOPR Family
            'sopr', 'sopr_sth', 'sopr_lth',
            
            # MVRV Family  
            'mvrv', 'mvrv_sth', 'mvrv_lth',
            
            # NUPL Family
            'nupl', 'nupl_lth', 'nupl_sth',
            'unrealized_profit', 'unrealized_loss',
            
            # Realized Metrics
            'realized_cap', 'realized_price',
            'realized_price_sth', 'realized_price_lth',
            'realized_profit', 'realized_loss',
            
            # Supply
            'supply_lth', 'supply_sth',
            
            # Cointime Economics
            'liveliness', 'aviv', 'active_price', 'vaulted_price',
            'cointime_price', 'investor_cap', 'thermo_cap',
            
            # Sell-side Risk (James Check - volatility prediction)
            'sell_side_risk', 'sell_side_risk_sth',
            
            # Mining
            'puell_multiple',
        ]
        
        loader.refresh_cache(metrics=core_metrics, source='brk')
    
    elif cmd == "data-load":
        from src.data_loader import DataLoader
        
        if len(sys.argv) < 3:
            print("Usage: python run.py data-load price,sopr,mvrv")
            sys.exit(1)
        
        metrics = sys.argv[2].split(',')
        loader = DataLoader()
        
        print(f"Loading: {metrics}")
        df = loader.load(metrics, source='brk')
        
        print(f"\nLoaded {len(df)} rows")
        print(f"Date range: {df.index.min().date()} to {df.index.max().date()}")
        print(f"\nLatest values:")
        print(df.tail(5).to_string())
    
    elif cmd == "signals":
        from src.data_loader import print_signals
        print_signals('brk')
    
    elif cmd == "signals-generate":
        from research.signals import generate_all_signals
        generate_all_signals()
    
    # === BRK COMMANDS (FREE, daily only) ===
    elif cmd == "brk-sync":
        from src.brk_downloader import cmd_sync as brk_sync
        brk_sync()
    
    elif cmd == "brk-backfill":
        from src.brk_downloader import cmd_backfill as brk_backfill
        brk_backfill()
    
    elif cmd == "brk-status":
        from src.brk_downloader import cmd_status as brk_status
        brk_status()
    
    elif cmd == "brk-refresh":
        from src.brk_downloader import cmd_refresh as brk_refresh
        brk_refresh()
    
    elif cmd == "brk-discover":
        from src.brk_downloader import cmd_discover as brk_discover
        query = sys.argv[2] if len(sys.argv) > 2 else None
        brk_discover(query)

    # === DASHBOARD COMMANDS ===
    elif cmd == "dashboard":
        """Full pipeline: sync all data, check quality, calculate, and open dashboard"""
        import subprocess
        subprocess.run([
            sys.executable,
            "scripts/sync_and_dashboard.py"
        ] + sys.argv[2:])  # Forward any additional arguments

    elif cmd == "dashboard-quick":
        """Skip sync, just calculate and open dashboard"""
        import subprocess
        subprocess.run([
            sys.executable,
            "scripts/sync_and_dashboard.py",
            "--skip-sync"
        ])

    elif cmd == "dashboard-quality":
        """Check data freshness and quality only"""
        import subprocess
        subprocess.run([
            sys.executable,
            "scripts/sync_and_dashboard.py",
            "--quality-only"
        ])

    # === BACKTEST DATABASE COMMANDS ===
    elif cmd == "backtest-stats":
        """Show backtest database statistics"""
        from src.backtest_db import BacktestDB
        db = BacktestDB()
        stats = db.get_stats()
        print("\n=== Backtest Database Stats ===")
        print(f"Total runs:       {stats['total_runs']}")
        print(f"Total strategies: {stats['total_strategies']}")
        print(f"First run:        {stats['first_run'] or 'N/A'}")
        print(f"Last run:         {stats['last_run'] or 'N/A'}")
        print(f"Database:         {stats['db_path']}")
        print(f"Runs directory:   {stats['runs_dir']}")

    elif cmd == "backtest-list":
        """List recent backtest runs"""
        from src.backtest_db import BacktestDB
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        strategy_id = sys.argv[3] if len(sys.argv) > 3 else None

        db = BacktestDB()
        runs = db.get_runs(strategy_id=strategy_id, limit=limit)

        print(f"\n{'Run ID':<22} {'Strategy':<12} {'Return':>10} {'Sharpe':>8} {'DD':>8} {'Trades':>7}")
        print("-" * 75)
        for run in runs:
            ret = run['return_pct'] or 0
            sharpe = run['sharpe'] or 0
            dd = run['max_dd'] or 0
            trades = run['num_trades'] or 0
            print(f"{run['run_id']:<22} {run['strategy_id']:<12} "
                  f"{ret:>+9.1f}% {sharpe:>8.2f} {dd:>7.1f}% {trades:>7}")

    elif cmd == "backtest-top":
        """Show top performing backtests"""
        from src.backtest_db import BacktestDB
        metric = sys.argv[2] if len(sys.argv) > 2 else "sharpe"
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10

        db = BacktestDB()
        runs = db.get_top_runs(metric=metric, limit=limit)

        print(f"\n=== Top {limit} by {metric} ===")
        print(f"{'Run ID':<22} {'Strategy':<12} {'Return':>10} {'Sharpe':>8} {'DD':>8}")
        print("-" * 65)
        for run in runs:
            ret = run['return_pct'] or 0
            sharpe = run['sharpe'] or 0
            dd = run['max_dd'] or 0
            print(f"{run['run_id']:<22} {run['strategy_id']:<12} "
                  f"{ret:>+9.1f}% {sharpe:>8.2f} {dd:>7.1f}%")

    elif cmd == "backtest-strategies":
        """Show backtest summary by strategy"""
        from src.backtest_db import BacktestDB
        db = BacktestDB()
        strategies = db.get_strategies()

        print(f"\n{'Strategy':<15} {'Runs':>6} {'Best Return':>12} {'Best Sharpe':>12} {'Last Run':<20}")
        print("-" * 75)
        for s in strategies:
            best_ret = s['best_return'] or 0
            best_sharpe = s['best_sharpe'] or 0
            last_run = (s['last_run'] or '')[:19]
            print(f"{s['strategy_id']:<15} {s['run_count']:>6} "
                  f"{best_ret:>+11.1f}% {best_sharpe:>12.2f} {last_run}")

    elif cmd == "backtest-gui":
        """Launch Streamlit backtest GUI"""
        import subprocess
        print("\n🚀 Launching Backtest GUI...")
        print("   Open http://localhost:8501 in your browser")
        print("   Press Ctrl+C to stop\n")
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "scripts/backtest_gui.py",
            "--server.headless", "true"
        ])

    else:
        print(f"Unknown command: {cmd}\n")
        print_usage()
        sys.exit(1)
