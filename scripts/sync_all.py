#!/usr/bin/env python3
"""
Unified Data Sync Pipeline
==========================
Syncs all data sources and regenerates the dashboard.

Usage:
    python scripts/sync_all.py              # Full sync (BRK + Glassnode) + dashboard
    python scripts/sync_all.py --quick      # Quick sync (last 30 days only)
    python scripts/sync_all.py --brk-only   # BRK metrics only
    python scripts/sync_all.py --gn-only    # Glassnode derivatives only
    python scripts/sync_all.py --no-dash    # Sync data but don't regenerate dashboard

Data Sources:
    - BRK: FREE on-chain metrics (SOPR, MVRV, supply, etc.)
    - Glassnode: Derivatives (funding rates, liquidations, OI)

Workflow:
    1. Refresh BRK on-chain metrics
    2. Download Glassnode derivatives data
    3. Regenerate dashboard with fresh data
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import logging

# Setup
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)


def sync_brk(force: bool = False) -> bool:
    """Sync BRK on-chain metrics."""
    logger.info("=" * 50)
    logger.info("SYNCING BRK ON-CHAIN METRICS")
    logger.info("=" * 50)
    
    cmd = [sys.executable, "-m", "src.brk_downloader", "refresh" if force else "sync"]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=False,
            text=True
        )
        if result.returncode == 0:
            logger.info("✓ BRK sync complete")
            return True
        else:
            logger.error(f"✗ BRK sync failed (exit code {result.returncode})")
            return False
    except Exception as e:
        logger.error(f"✗ BRK sync error: {e}")
        return False


def sync_derivatives_free(days: int = 365) -> bool:
    """Sync FREE derivatives data from Binance/Bybit."""
    logger.info("=" * 50)
    logger.info("SYNCING FREE DERIVATIVES (Binance/Bybit)")
    logger.info("=" * 50)
    
    try:
        from src.derivatives_downloader import DerivativesDownloader
        
        downloader = DerivativesDownloader()
        results = downloader.download_all(days=days)
        
        logger.info("✓ Downloaded free derivatives metrics:")
        for name, df in results.items():
            if not df.empty:
                logger.info(f"  {name}: {len(df)} rows, latest: {df.index[-1]}")
        
        # Show current values
        latest = downloader.get_latest_values()
        if latest:
            logger.info("\nLatest values:")
            for name, info in latest.items():
                if 'funding' in name:
                    logger.info(f"  {name}: {info['value']:.6f} ({info['value']*100:.4f}%)")
                else:
                    logger.info(f"  {name}: {info['value']:.4f}")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ Import error: {e}")
        logger.info("  Run: pip install requests pandas pyarrow")
        return False
    except Exception as e:
        logger.error(f"✗ Free derivatives sync error: {e}")
        import traceback
        traceback.print_exc()
        return False


def sync_glassnode(since: str = None, btd_only: bool = True) -> bool:
    """Sync Glassnode derivatives data (PAID - $8K/year)."""
    logger.info("=" * 50)
    logger.info("SYNCING GLASSNODE DERIVATIVES (PAID)")
    logger.info("=" * 50)
    
    try:
        from src.glassnode_downloader import GlassnodeDownloader
        
        downloader = GlassnodeDownloader()
        
        if btd_only:
            results = downloader.download_buy_the_dip_metrics(since=since or "2019-01-01")
            logger.info(f"✓ Downloaded BTD metrics: {list(results.keys())}")
        else:
            results = downloader.download_all(since=since or "2019-01-01")
            logger.info(f"✓ Downloaded all metrics: {len(results)} total")
        
        latest = downloader.get_latest_values()
        if latest:
            logger.info("\nLatest Glassnode values:")
            for name, val in latest.items():
                if 'funding' in name:
                    logger.info(f"  {name}: {val:.6f}")
                elif 'liquidation' in name:
                    logger.info(f"  {name}: {val:,.0f}")
                else:
                    logger.info(f"  {name}: {val:,.2f}")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Glassnode sync error: {e}")
        return False


def regenerate_dashboard(open_browser: bool = False) -> bool:
    """Regenerate the dashboard HTML."""
    logger.info("=" * 50)
    logger.info("REGENERATING DASHBOARD")
    logger.info("=" * 50)
    
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "dashboard.py")]
    if not open_browser:
        cmd.append("--no-open")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=False,
            text=True
        )
        if result.returncode == 0:
            logger.info("✓ Dashboard regenerated")
            return True
        else:
            logger.error(f"✗ Dashboard generation failed (exit code {result.returncode})")
            return False
    except Exception as e:
        logger.error(f"✗ Dashboard error: {e}")
        return False


def get_sync_status() -> dict:
    """Get status of all data sources."""
    import pandas as pd
    
    status = {
        'brk': {'latest': None, 'count': 0},
        'derivatives_free': {'latest': None, 'count': 0, 'metrics': []},
        'glassnode': {'latest': None, 'count': 0, 'metrics': []}
    }
    
    # Check BRK data
    brk_dir = PROJECT_ROOT / "data" / "brk" / "daily"
    if brk_dir.exists():
        files = list(brk_dir.glob("*.parquet"))
        status['brk']['count'] = len(files)
        
        latest = None
        for f in files:
            try:
                df = pd.read_parquet(f)
                if len(df) > 0:
                    if hasattr(df.index, 'max'):
                        file_latest = df.index.max()
                    elif 'time' in df.columns:
                        file_latest = df['time'].max()
                    else:
                        continue
                    if latest is None or file_latest > latest:
                        latest = file_latest
            except:
                continue
        status['brk']['latest'] = latest
    
    # Check free derivatives data (Binance/Bybit)
    deriv_dir = PROJECT_ROOT / "data" / "derivatives" / "daily"
    if deriv_dir.exists():
        files = list(deriv_dir.glob("*.parquet"))
        status['derivatives_free']['count'] = len(files)
        status['derivatives_free']['metrics'] = [f.stem for f in files]
        
        latest = None
        for f in files:
            try:
                df = pd.read_parquet(f)
                if len(df) > 0:
                    file_latest = df.index.max()
                    if latest is None or file_latest > latest:
                        latest = file_latest
            except:
                continue
        status['derivatives_free']['latest'] = latest
    
    # Check Glassnode data (optional/paid)
    gn_dir = PROJECT_ROOT / "data" / "glassnode" / "daily"
    if gn_dir.exists():
        files = list(gn_dir.glob("*.parquet"))
        status['glassnode']['count'] = len(files)
        status['glassnode']['metrics'] = [f.stem for f in files]
        
        latest = None
        for f in files:
            try:
                df = pd.read_parquet(f)
                if len(df) > 0:
                    file_latest = df.index.max()
                    if latest is None or file_latest > latest:
                        latest = file_latest
            except:
                continue
        status['glassnode']['latest'] = latest
    
    return status


def print_status():
    """Print sync status."""
    import pandas as pd
    
    status = get_sync_status()
    
    print("\n" + "=" * 50)
    print("DATA SYNC STATUS")
    print("=" * 50)
    
    # BRK
    print(f"\n📊 BRK On-Chain Data:")
    print(f"   Files: {status['brk']['count']}")
    if status['brk']['latest']:
        days_old = (datetime.now() - pd.Timestamp(status['brk']['latest']).to_pydatetime().replace(tzinfo=None)).days
        print(f"   Latest: {status['brk']['latest']} ({days_old}d ago)")
    else:
        print(f"   Latest: No data")
    
    # Free Derivatives
    print(f"\n📈 FREE Derivatives (Binance/Bybit):")
    print(f"   Files: {status['derivatives_free']['count']}")
    if status['derivatives_free']['latest']:
        days_old = (datetime.now() - pd.Timestamp(status['derivatives_free']['latest']).to_pydatetime().replace(tzinfo=None)).days
        print(f"   Latest: {status['derivatives_free']['latest']} ({days_old}d ago)")
    else:
        print(f"   Latest: No data (run sync to download)")
    if status['derivatives_free']['metrics']:
        print(f"   Metrics: {', '.join(status['derivatives_free']['metrics'])}")
    
    # Glassnode (optional)
    if status['glassnode']['count'] > 0:
        print(f"\n💎 Glassnode (PAID):")
        print(f"   Files: {status['glassnode']['count']}")
        if status['glassnode']['latest']:
            days_old = (datetime.now() - pd.Timestamp(status['glassnode']['latest']).to_pydatetime().replace(tzinfo=None)).days
            print(f"   Latest: {status['glassnode']['latest']} ({days_old}d ago)")
        if status['glassnode']['metrics']:
            print(f"   Metrics: {', '.join(status['glassnode']['metrics'])}")
    
    print()


def main():
    parser = argparse.ArgumentParser(description="Sync all data sources")
    parser.add_argument("--quick", action="store_true", help="Quick sync (last 30 days)")
    parser.add_argument("--brk-only", action="store_true", help="Sync BRK only")
    parser.add_argument("--gn-only", action="store_true", help="Sync Glassnode only")
    parser.add_argument("--free", action="store_true", help="Use free Binance derivatives instead of Glassnode")
    parser.add_argument("--no-dash", action="store_true", help="Skip dashboard regeneration")
    parser.add_argument("--status", action="store_true", help="Show sync status only")
    parser.add_argument("--open", action="store_true", help="Open dashboard in browser")
    parser.add_argument("--force", action="store_true", help="Force full refresh")
    
    args = parser.parse_args()
    
    # Need pandas for status
    import pandas as pd
    
    if args.status:
        print_status()
        return
    
    # Calculate since date for quick sync
    since = None
    if args.quick:
        since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        logger.info(f"Quick sync mode: {since} to today")
    
    print("\n" + "=" * 60)
    print("  BITCOIN DATA PIPELINE - FULL SYNC")
    print("=" * 60 + "\n")
    
    success = True
    
    # Step 1: BRK sync
    if not args.gn_only:
        if not sync_brk(force=args.force):
            success = False
            logger.warning("BRK sync had issues, continuing...")
    
    # Step 2: Glassnode derivatives sync (default)
    if not args.brk_only:
        if args.free:
            # Use free Binance derivatives
            if not sync_derivatives_free(days=30 if args.quick else 365):
                success = False
                logger.warning("Free derivatives sync had issues, continuing...")
        else:
            # Use Glassnode (default)
            if not sync_glassnode(since=since):
                success = False
                logger.warning("Glassnode sync had issues, continuing...")
    
    # Step 4: Dashboard
    if not args.no_dash:
        if not regenerate_dashboard(open_browser=args.open):
            success = False
    
    # Summary
    print("\n" + "=" * 60)
    if success:
        print("  ✅ SYNC COMPLETE")
    else:
        print("  ⚠️  SYNC COMPLETED WITH WARNINGS")
    print("=" * 60)
    
    print_status()
    
    print("\n💡 To view dashboard: open dashboard.html in browser")
    print("   Or run: python scripts/dashboard.py")


if __name__ == "__main__":
    main()
