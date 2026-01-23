#!/usr/bin/env python3
"""
Data Quality Dashboard - Generate HTML report of data quality status
====================================================================
Runs quality checks and displays results in a visual dashboard.

Usage:
    python dashboard_quality.py              # Generate quality dashboard
    python dashboard_quality.py --no-open    # Generate without opening browser
"""

import sys
import json
import webbrowser
from pathlib import Path
from datetime import datetime
import subprocess

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_PATH = PROJECT_ROOT / "dashboard_quality.html"


def run_quality_check():
    """Run quality checker and capture results"""
    try:
        # Run quality checker script
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / 'scripts' / 'check_data_quality.py')],
            capture_output=True,
            text=True,
            timeout=30
        )

        return {
            'stdout': result.stdout,
            'returncode': result.returncode,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {
            'stdout': f'Error running quality check: {str(e)}',
            'returncode': 1,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


def generate_html(quality_results):
    """Generate HTML dashboard for data quality"""

    output = quality_results['stdout']
    status = '🔴 ERRORS' if quality_results['returncode'] != 0 else '✅ CLEAN'

    # Parse output for summary stats
    lines = output.split('\n')
    total_issues = 0
    high_severity = 0
    medium_severity = 0
    low_severity = 0

    for line in lines:
        if 'Total Issues:' in line:
            try:
                total_issues = int(line.split(':')[1].strip())
            except:
                pass
        elif '🔴 High Severity:' in line:
            try:
                high_severity = int(line.split(':')[1].strip())
            except:
                pass
        elif '🟡 Medium Severity:' in line:
            try:
                medium_severity = int(line.split(':')[1].strip())
            except:
                pass
        elif '⚪ Low Severity:' in line:
            try:
                low_severity = int(line.split(':')[1].strip())
            except:
                pass

    # Determine overall status
    if high_severity > 0:
        overall_status = 'NEEDS ATTENTION'
        status_color = '#dc3545'
        status_icon = '❌'
    elif medium_severity > 3:
        overall_status = 'ACCEPTABLE'
        status_color = '#ffc107'
        status_icon = '⚠️'
    elif total_issues > 0:
        overall_status = 'GOOD'
        status_color = '#28a745'
        status_icon = '✅'
    else:
        overall_status = 'EXCELLENT'
        status_color = '#28a745'
        status_icon = '✅'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data Quality Dashboard - Bitcoin Lab</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #ffffff;
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
        }}

        header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(to right, #ffffff, #a8c0ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .timestamp {{
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.9rem;
        }}

        .nav {{
            text-align: center;
            margin-bottom: 20px;
        }}

        .nav a {{
            display: inline-block;
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.1);
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 0 10px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
        }}

        .nav a:hover {{
            background: rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
        }}

        .status-card {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            text-align: center;
        }}

        .status-card h2 {{
            font-size: 3rem;
            margin-bottom: 15px;
            color: {status_color};
        }}

        .status-card .status-text {{
            font-size: 2rem;
            font-weight: bold;
            color: {status_color};
            margin-bottom: 10px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .stat-box {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 25px;
            text-align: center;
        }}

        .stat-box .label {{
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.9rem;
            text-transform: uppercase;
            margin-bottom: 10px;
        }}

        .stat-box .value {{
            font-size: 2.5rem;
            font-weight: bold;
            color: white;
        }}

        .stat-box.high {{
            border-color: #dc3545;
        }}

        .stat-box.medium {{
            border-color: #ffc107;
        }}

        .stat-box.low {{
            border-color: #17a2b8;
        }}

        .output-section {{
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
        }}

        .output-section h3 {{
            margin-bottom: 15px;
            font-size: 1.3rem;
        }}

        .output-content {{
            background: #1a1a1a;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            white-space: pre-wrap;
            max-height: 600px;
            overflow-y: auto;
        }}

        .actions {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 25px;
        }}

        .actions h3 {{
            margin-bottom: 15px;
        }}

        .actions ul {{
            list-style-position: inside;
            color: rgba(255, 255, 255, 0.9);
        }}

        .actions li {{
            margin-bottom: 10px;
            padding: 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
        }}

        .actions code {{
            background: rgba(0, 0, 0, 0.3);
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            color: #00ff00;
        }}

        footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.2);
            color: rgba(255, 255, 255, 0.6);
            font-size: 0.85rem;
        }}

        .refresh-btn {{
            display: inline-block;
            padding: 12px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 25px;
            margin: 20px 0;
            border: none;
            cursor: pointer;
            font-size: 1rem;
            font-weight: bold;
            transition: transform 0.2s;
        }}

        .refresh-btn:hover {{
            transform: scale(1.05);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Data Quality Dashboard</h1>
            <div class="timestamp">Last Updated: {quality_results['timestamp']}</div>
        </header>

        <div class="nav">
            <a href="dashboard.html">← Back to Main Dashboard</a>
            <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
        </div>

        <div class="status-card">
            <h2>{status_icon}</h2>
            <div class="status-text">{overall_status}</div>
            <p>Overall Data Quality Assessment</p>
        </div>

        <div class="stats-grid">
            <div class="stat-box">
                <div class="label">Total Issues</div>
                <div class="value">{total_issues}</div>
            </div>
            <div class="stat-box high">
                <div class="label">🔴 High Severity</div>
                <div class="value">{high_severity}</div>
            </div>
            <div class="stat-box medium">
                <div class="label">🟡 Medium Severity</div>
                <div class="value">{medium_severity}</div>
            </div>
            <div class="stat-box low">
                <div class="label">⚪ Low Severity</div>
                <div class="value">{low_severity}</div>
            </div>
        </div>

        <div class="output-section">
            <h3>📋 Detailed Quality Report</h3>
            <div class="output-content">{output}</div>
        </div>

        <div class="actions">
            <h3>🛠️ Recommended Actions</h3>
            <ul>
                <li>
                    <strong>Fix Known Issues:</strong> <code>python scripts/fix_data_issues.py</code>
                </li>
                <li>
                    <strong>Check Sync Status:</strong> <code>python run.py brk-status</code>
                </li>
                <li>
                    <strong>Refresh BRK Data:</strong> <code>python run.py brk-sync</code>
                </li>
                <li>
                    <strong>Check Bitcoin Lab Quota:</strong> <code>python run.py quota</code>
                </li>
                <li>
                    <strong>Re-run Quality Check:</strong> <code>python scripts/check_data_quality.py</code>
                </li>
            </ul>
        </div>

        <footer>
            <p>Bitcoin Lab BTC Data Pipeline | Data Quality Monitoring</p>
            <p>Generated on {quality_results['timestamp']}</p>
        </footer>
    </div>

    <script>
        // Auto-refresh every 5 minutes
        setTimeout(function(){{
            location.reload();
        }}, 300000);
    </script>
</body>
</html>"""

    return html


def main():
    """Generate data quality dashboard"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate data quality dashboard')
    parser.add_argument('--no-open', action='store_true',
                       help='Generate without opening browser')
    args = parser.parse_args()

    print("=" * 80)
    print("DATA QUALITY DASHBOARD GENERATOR")
    print("=" * 80)
    print("\nRunning quality checks...")

    # Run quality check
    results = run_quality_check()

    print("\nGenerating HTML dashboard...")

    # Generate HTML
    html = generate_html(results)

    # Write to file
    OUTPUT_PATH.write_text(html)

    print(f"\n✓ Dashboard generated: {OUTPUT_PATH}")
    print(f"  Status: {results['returncode'] == 0 and '✅ Clean' or '⚠️ Issues Found'}")

    # Open in browser
    if not args.no_open:
        print("\n Opening in browser...")
        webbrowser.open(OUTPUT_PATH.as_uri())

    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
