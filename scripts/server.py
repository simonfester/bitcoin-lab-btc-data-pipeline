#!/usr/bin/env python3
"""
Bitcoin Dashboard Server
========================
HTTPS server with auto-updating data and dashboard regeneration.

Usage:
    python scripts/server.py                    # Start server on port 8443
    python scripts/server.py --port 443         # Custom port (needs sudo for 443)
    python scripts/server.py --no-sync          # Don't auto-sync data
    python scripts/server.py --sync-interval 30 # Sync every 30 minutes

Features:
    - HTTPS only (self-signed cert auto-generated)
    - Auto-syncs BRK data (free) on schedule
    - Regenerates dashboard after each sync
    - Live price updates via Coinbase API (client-side)

For NUC Server:
    # Run as systemd service (see bottom of file for unit file)
    sudo python scripts/server.py --port 443
"""

import os
import sys
import ssl
import time
import signal
import argparse
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CERTS_DIR = PROJECT_ROOT / "certs"
DASHBOARD_PATH = PROJECT_ROOT / "dashboard.html"

DEFAULT_PORT = 8443
DEFAULT_SYNC_INTERVAL = 60  # minutes

# =============================================================================
# CERTIFICATE GENERATION
# =============================================================================

def generate_self_signed_cert():
    """Generate self-signed SSL certificate if not exists."""
    CERTS_DIR.mkdir(exist_ok=True)
    
    cert_file = CERTS_DIR / "server.crt"
    key_file = CERTS_DIR / "server.key"
    
    if cert_file.exists() and key_file.exists():
        print(f"✓ Using existing certificates in {CERTS_DIR}")
        return str(cert_file), str(key_file)
    
    print("Generating self-signed SSL certificate...")
    
    try:
        # Use openssl to generate cert
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:4096",
            "-keyout", str(key_file),
            "-out", str(cert_file),
            "-days", "365",
            "-nodes",
            "-subj", "/CN=bitcoin-dashboard/O=Local/C=US"
        ], check=True, capture_output=True)
        
        print(f"✓ Generated certificate: {cert_file}")
        return str(cert_file), str(key_file)
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to generate certificate: {e}")
        print("  Install openssl or provide your own certs in ./certs/")
        sys.exit(1)
    except FileNotFoundError:
        print("✗ openssl not found. Install it or provide your own certs.")
        sys.exit(1)


# =============================================================================
# DATA SYNC
# =============================================================================

def sync_brk_data():
    """Run BRK data sync (free)."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Syncing BRK data...")
    
    try:
        result = subprocess.run(
            [sys.executable, "run.py", "brk-sync"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300  # 5 min timeout
        )
        
        if result.returncode == 0:
            print("  ✓ BRK sync complete")
            return True
        else:
            print(f"  ✗ BRK sync failed: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ✗ BRK sync timed out")
        return False
    except Exception as e:
        print(f"  ✗ BRK sync error: {e}")
        return False


def regenerate_dashboard():
    """Regenerate the dashboard HTML."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Regenerating dashboard...")
    
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "dashboard.py"), "--no-open"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("  ✓ Dashboard regenerated")
            return True
        else:
            print(f"  ✗ Dashboard generation failed: {result.stderr[:200]}")
            return False
            
    except Exception as e:
        print(f"  ✗ Dashboard error: {e}")
        return False


def sync_loop(interval_minutes: int, stop_event: threading.Event):
    """Background thread for periodic data sync."""
    while not stop_event.is_set():
        # Wait for interval (check stop_event every 10 seconds)
        for _ in range(interval_minutes * 6):
            if stop_event.is_set():
                return
            time.sleep(10)
        
        # Sync and regenerate
        if sync_brk_data():
            regenerate_dashboard()


# =============================================================================
# HTTPS SERVER
# =============================================================================

class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom handler that serves from project root."""
    
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)
    
    def do_GET(self):
        # Redirect root to dashboard
        if self.path == "/" or self.path == "":
            self.path = "/dashboard.html"
        
        # Only serve dashboard.html and static assets
        allowed = ["/dashboard.html", "/favicon.ico"]
        if self.path not in allowed and not self.path.startswith("/static/"):
            self.send_error(404, "Not Found")
            return
        
        return super().do_GET()
    
    def log_message(self, format, *args):
        # Quieter logging
        if "dashboard.html" in args[0]:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] {self.address_string()} - {args[0]}")


def run_server(port: int, cert_file: str, key_file: str):
    """Start HTTPS server."""
    
    # Create SSL context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    
    # Create server
    handler = partial(DashboardHandler, directory=str(PROJECT_ROOT))
    server = HTTPServer(("0.0.0.0", port), handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    
    return server


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Bitcoin Dashboard HTTPS Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/server.py                     # Start on port 8443
    python scripts/server.py --port 443          # Port 443 (needs sudo)
    python scripts/server.py --no-sync           # Don't auto-sync
    python scripts/server.py --sync-interval 30  # Sync every 30 min
    
For NUC deployment, create a systemd service (see script comments).
        """
    )
    
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT,
                        help=f"HTTPS port (default: {DEFAULT_PORT})")
    parser.add_argument("--no-sync", action="store_true",
                        help="Disable automatic data sync")
    parser.add_argument("--sync-interval", type=int, default=DEFAULT_SYNC_INTERVAL,
                        help=f"Sync interval in minutes (default: {DEFAULT_SYNC_INTERVAL})")
    parser.add_argument("--cert", type=str, help="Path to SSL certificate")
    parser.add_argument("--key", type=str, help="Path to SSL private key")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Bitcoin Dashboard Server")
    print("=" * 60)
    
    # Generate or use provided certs
    if args.cert and args.key:
        cert_file, key_file = args.cert, args.key
    else:
        cert_file, key_file = generate_self_signed_cert()
    
    # Initial dashboard generation
    if not DASHBOARD_PATH.exists():
        print("\nGenerating initial dashboard...")
        regenerate_dashboard()
    
    # Start sync thread
    stop_event = threading.Event()
    sync_thread = None
    
    if not args.no_sync:
        print(f"\n✓ Auto-sync enabled (every {args.sync_interval} min)")
        sync_thread = threading.Thread(
            target=sync_loop,
            args=(args.sync_interval, stop_event),
            daemon=True
        )
        sync_thread.start()
    else:
        print("\n⚠ Auto-sync disabled")
    
    # Start server
    try:
        server = run_server(args.port, cert_file, key_file)
        
        print(f"\n{'─' * 60}")
        print(f"🚀 Server running at:")
        print(f"   https://localhost:{args.port}")
        print(f"   https://0.0.0.0:{args.port}")
        print(f"{'─' * 60}")
        print("Press Ctrl+C to stop\n")
        
        # Handle graceful shutdown
        def shutdown(signum, frame):
            print("\n\nShutting down...")
            stop_event.set()
            server.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)
        
        server.serve_forever()
        
    except PermissionError:
        print(f"\n✗ Permission denied for port {args.port}")
        print(f"  Use sudo or choose a port > 1024")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


# =============================================================================
# SYSTEMD SERVICE FILE (for NUC deployment)
# =============================================================================
"""
Save as /etc/systemd/system/bitcoin-dashboard.service:

[Unit]
Description=Bitcoin Dashboard HTTPS Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/bitcoin-lab-btc-data-pipeline
ExecStart=/path/to/bitcoin-lab-btc-data-pipeline/venv/bin/python scripts/server.py --port 8443
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

Then run:
    sudo systemctl daemon-reload
    sudo systemctl enable bitcoin-dashboard
    sudo systemctl start bitcoin-dashboard
    sudo systemctl status bitcoin-dashboard
"""
