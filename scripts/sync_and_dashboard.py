#!/usr/bin/env python3
"""
Sync All Data & Generate Dashboard
===================================
One-click script to sync all data sources, validate quality, and open dashboards.

Usage:
    python scripts/sync_and_dashboard.py                    # Full sync + dashboard
    python scripts/sync_and_dashboard.py --skip-sync        # Skip sync, just calculate
    python scripts/sync_and_dashboard.py --quality-only     # Only check quality
    python scripts/sync_and_dashboard.py --no-open          # Don't open browsers
    python scripts/sync_and_dashboard.py --skip-brk         # Skip BRK sync
    python scripts/sync_and_dashboard.py --skip-glassnode   # Skip Glassnode sync

Pipeline:
    1. Sync BRK data (FREE, primary source)
    2. Sync Glassnode data (derivatives)
    3. Check data freshness
    4. Check data quality
    5. Run signal calculations
    6. Generate dashboards
    7. Open in browser
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import argparse

PROJECT_ROOT = Path(__file__).parent.parent


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def run_command(command: list, description: str, critical: bool = True) -> bool:
    """Run a command and handle errors."""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=False,
            text=True
        )
        print(f"✅ {description} - DONE")
        return True
    except subprocess.CalledProcessError as e:
        if critical:
            print(f"❌ {description} - FAILED")
            print(f"   Error: {e}")
            sys.exit(1)
        else:
            print(f"⚠️  {description} - FAILED (non-critical)")
            return False
    except FileNotFoundError as e:
        if critical:
            print(f"❌ {description} - COMMAND NOT FOUND")
            print(f"   Error: {e}")
            sys.exit(1)
        else:
            print(f"⚠️  {description} - COMMAND NOT FOUND (non-critical)")
            return False


def sync_brk_data():
    """Sync BRK data (primary on-chain source)."""
    print_section("STEP 1: Sync BRK Data (FREE)")
    run_command(
        ["python", "run.py", "brk-sync"],
        "Syncing BRK daily on-chain data",
        critical=True
    )


def sync_glassnode_data():
    """Sync Glassnode derivatives data."""
    print_section("STEP 2: Sync Glassnode Data (Derivatives)")

    # Check if sync script exists
    gn_sync_script = PROJECT_ROOT / "scripts" / "sync_glassnode_daily.py"

    if not gn_sync_script.exists():
        print("⚠️  Glassnode sync script not found - SKIPPING")
        print(f"   Expected: {gn_sync_script}")
        return False

    run_command(
        ["python", str(gn_sync_script)],
        "Syncing Glassnode derivatives data",
        critical=False  # Non-critical if Glassnode not set up
    )
    return True


def check_data_freshness():
    """Check if data is fresh."""
    print_section("STEP 3: Check Data Freshness")

    freshness_script = PROJECT_ROOT / "scripts" / "check_data_freshness.py"

    if not freshness_script.exists():
        print("⚠️  Freshness checker not found - SKIPPING")
        return False

    # Run freshness check (non-critical, informational only)
    result = subprocess.run(
        ["python", str(freshness_script), "--source", "all"],
        cwd=PROJECT_ROOT,
        capture_output=False,
        text=True
    )

    if result.returncode == 0:
        print("✅ All data sources are FRESH")
    else:
        print("⚠️  Some data may be stale - continuing anyway")

    return True


def check_data_quality():
    """Check data quality."""
    print_section("STEP 4: Check Data Quality")

    quality_script = PROJECT_ROOT / "scripts" / "check_data_quality.py"

    if not quality_script.exists():
        print("⚠️  Quality checker not found - SKIPPING")
        return False

    # Run quality check (non-critical, informational only)
    result = subprocess.run(
        ["python", str(quality_script)],
        cwd=PROJECT_ROOT,
        capture_output=False,
        text=True
    )

    if result.returncode == 0:
        print("✅ Data quality checks PASSED")
    else:
        print("⚠️  Some quality issues detected - continuing anyway")

    return True


def run_calculations():
    """Run signal calculations."""
    print_section("STEP 5: Calculate Trading Signals")

    calc_script = PROJECT_ROOT / "scripts" / "calculate.py"

    if not calc_script.exists():
        print("❌ calculate.py not found")
        sys.exit(1)

    run_command(
        ["python", str(calc_script)],
        "Computing all metrics and signals",
        critical=True
    )


def generate_dashboards(open_browser: bool = True):
    """Generate dashboard HTML files."""
    print_section("STEP 6: Generate Dashboards")

    # Generate main dashboard
    dashboard_script = PROJECT_ROOT / "scripts" / "dashboard_new.py"
    if dashboard_script.exists():
        cmd = ["python", str(dashboard_script)]
        if not open_browser:
            cmd.append("--no-open")
        run_command(cmd, "Generating main dashboard", critical=True)
    else:
        print("⚠️  Main dashboard script not found - SKIPPING")

    # Generate signals dashboard
    signals_script = PROJECT_ROOT / "scripts" / "dashboard_signals.py"
    if signals_script.exists():
        cmd = ["python", str(signals_script)]
        if not open_browser:
            cmd.append("--no-open")
        run_command(cmd, "Generating signals dashboard", critical=True)
    else:
        print("⚠️  Signals dashboard script not found - SKIPPING")

    # Generate quality dashboard
    quality_script = PROJECT_ROOT / "scripts" / "dashboard_quality.py"
    if quality_script.exists():
        cmd = ["python", str(quality_script)]
        if not open_browser:
            cmd.append("--no-open")
        run_command(cmd, "Generating quality dashboard", critical=False)
    else:
        print("⚠️  Quality dashboard script not found - SKIPPING")


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description='Sync all data sources and generate dashboards',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/sync_and_dashboard.py                    # Full pipeline
  python scripts/sync_and_dashboard.py --skip-sync        # Only calculate + dashboard
  python scripts/sync_and_dashboard.py --quality-only     # Only check quality
  python scripts/sync_and_dashboard.py --no-open          # Don't open browsers
        """
    )

    parser.add_argument('--skip-sync', action='store_true',
                       help='Skip data sync, only calculate and generate dashboards')
    parser.add_argument('--skip-brk', action='store_true',
                       help='Skip BRK sync')
    parser.add_argument('--skip-glassnode', action='store_true',
                       help='Skip Glassnode sync')
    parser.add_argument('--quality-only', action='store_true',
                       help='Only check data quality, skip everything else')
    parser.add_argument('--no-open', action='store_true',
                       help='Generate dashboards without opening in browser')

    args = parser.parse_args()

    print("=" * 80)
    print(" 🚀 Bitcoin Data Pipeline - Full Sync & Dashboard")
    print("=" * 80)
    print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Quality check only mode
    if args.quality_only:
        check_data_freshness()
        check_data_quality()
        print("\n" + "=" * 80)
        print(" ✅ Quality checks complete")
        print("=" * 80)
        return

    # Step 1-2: Sync data sources
    if not args.skip_sync:
        if not args.skip_brk:
            sync_brk_data()
        else:
            print_section("STEP 1: Sync BRK Data (SKIPPED)")

        if not args.skip_glassnode:
            sync_glassnode_data()
        else:
            print_section("STEP 2: Sync Glassnode Data (SKIPPED)")

        # Step 3-4: Quality checks
        check_data_freshness()
        check_data_quality()
    else:
        print_section("STEPS 1-4: Data Sync & Quality Checks (SKIPPED)")

    # Step 5: Run calculations
    run_calculations()

    # Step 6: Generate dashboards
    generate_dashboards(open_browser=not args.no_open)

    # Final summary
    print("\n" + "=" * 80)
    print(" ✅ PIPELINE COMPLETE")
    print("=" * 80)
    print(f" Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n 📊 Dashboards generated:")
    print("    • dashboard.html          - Main 6-pillar dashboard")
    print("    • dashboard_signals.html  - Trading signals dashboard")
    print("    • dashboard_quality.html  - Data quality report")

    if not args.no_open:
        print("\n 🌐 Dashboards opened in browser")

    print("\n 💡 Next steps:")
    print("    • Review signals on dashboard_signals.html")
    print("    • Check quality on dashboard_quality.html")
    print("    • Refresh data: python scripts/sync_and_dashboard.py")
    print("    • Quick update: python scripts/sync_and_dashboard.py --skip-sync")
    print("=" * 80)


if __name__ == "__main__":
    main()
