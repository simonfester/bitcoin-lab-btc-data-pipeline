#!/usr/bin/env python3
"""
112 — Tight Zone TUI Dashboard (Textual) with Live Coinbase Websocket
======================================================================
Live BTC price via Coinbase websocket. On-chain data refreshes hourly.

Usage:  python research/112_tui_dashboard.py
Keys:   r=refresh, t=toggle history, q=quit
"""

import asyncio
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional
import warnings
import os
import time
import hashlib
import hmac
import base64
import secrets
from urllib.parse import urlencode
warnings.filterwarnings('ignore')

try:
    import requests as http_client
    HAS_HTTP_CLIENT = True
except ImportError:
    HAS_HTTP_CLIENT = False

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

try:
    from cryptography.hazmat.primitives import serialization
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
except ImportError:
    pass

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, Static, DataTable, Sparkline
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message
from rich.text import Text

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BL_DIR = PROJECT_ROOT / 'data' / 'bl'
COINBASE_WS_URL = "wss://advanced-trade-ws.coinbase.com"
COINBASE_API_URL = "https://api.coinbase.com"
PRODUCT_ID = "BTC-USD"

RESOLUTIONS = ['daily', 'hourly', 'h4', 'h8', 'h12']


class CoinbaseAPI:
    """Coinbase Advanced Trade API client for position tracking (CDP JWT auth)."""

    def __init__(self):
        self.api_key = os.getenv('COINBASE_API_KEY', '')
        self.api_secret = os.getenv('COINBASE_API_SECRET', '')
        # Handle escaped newlines in private key (literal backslash-n from .env file)
        if self.api_secret:
            # chr(92) is backslash - needed because '\\n' in source is interpreted as newline
            self.api_secret = self.api_secret.replace(chr(92) + 'n', '\n')

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret and HAS_HTTP_CLIENT and HAS_JWT and HAS_CRYPTO)

    def _load_private_key(self):
        """Load the EC private key from api_secret."""
        if not HAS_CRYPTO:
            return None
        try:
            return serialization.load_pem_private_key(
                self.api_secret.encode('utf-8'),
                password=None
            )
        except Exception:
            return None

    def _build_jwt(self, method: str, path: str) -> str:
        """Build JWT token for Coinbase CDP API authentication."""
        if not HAS_JWT or not HAS_CRYPTO:
            return ''

        private_key = self._load_private_key()
        if not private_key:
            return ''

        # Build JWT payload
        uri = f"{method} api.coinbase.com{path}"
        now = int(time.time())
        payload = {
            'sub': self.api_key,
            'iss': 'cdp',
            'nbf': now,
            'exp': now + 120,  # 2 minute expiry
            'uri': uri,
            'nonce': secrets.token_hex(16),  # Required by CDP API
        }

        # JWT headers with kid (API key)
        jwt_headers = {
            'kid': self.api_key,
            'typ': 'JWT',
            'nonce': secrets.token_hex(16),
        }

        # Sign with ES256
        token = jwt.encode(payload, private_key, algorithm='ES256', headers=jwt_headers)
        return token

    def build_ws_jwt(self) -> str:
        """Build JWT token for Coinbase websocket authentication."""
        if not HAS_JWT or not HAS_CRYPTO:
            return ''

        private_key = self._load_private_key()
        if not private_key:
            return ''

        now = int(time.time())
        payload = {
            'sub': self.api_key,
            'iss': 'cdp',
            'nbf': now,
            'exp': now + 120,  # 2 minute expiry
            'nonce': secrets.token_hex(16),
        }

        jwt_headers = {
            'kid': self.api_key,
            'typ': 'JWT',
            'nonce': secrets.token_hex(16),
        }

        token = jwt.encode(payload, private_key, algorithm='ES256', headers=jwt_headers)
        return token

    def _get_headers(self, method: str, path: str) -> dict:
        """Generate headers with JWT auth for Coinbase API request."""
        token = self._build_jwt(method, path)
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    def get_accounts(self) -> list:
        """Fetch all accounts/balances."""
        if not self.is_configured:
            return []

        path = '/api/v3/brokerage/accounts'
        headers = self._get_headers('GET', path)

        try:
            resp = http_client.get(COINBASE_API_URL + path, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('accounts', [])
        except Exception:
            pass
        return []

    def get_all_balances(self) -> dict:
        """Get all account balances. Returns dict of {currency: balance}."""
        accounts = self.get_accounts()
        balances = {}
        for acc in accounts:
            currency = acc.get('currency', '')
            if not currency:
                continue
            # Try different field structures (API may vary)
            available = 0.0
            hold = 0.0

            # Structure 1: available_balance.value
            if 'available_balance' in acc:
                ab = acc['available_balance']
                if isinstance(ab, dict):
                    available = float(ab.get('value', 0))
                else:
                    available = float(ab or 0)

            # Structure 2: direct 'balance' field
            if 'balance' in acc:
                bal = acc['balance']
                if isinstance(bal, dict):
                    available = float(bal.get('value', 0))
                else:
                    available = float(bal or 0)

            # Hold balance
            if 'hold' in acc:
                h = acc['hold']
                if isinstance(h, dict):
                    hold = float(h.get('value', 0))
                else:
                    hold = float(h or 0)

            total = available + hold
            if total > 0:
                balances[currency] = total

        return balances

    def get_btc_balance(self) -> tuple:
        """Get BTC balance and USD value. Returns (btc_amount, usd_value)."""
        balances = self.get_all_balances()
        return balances.get('BTC', 0.0), None

    def get_usdc_balance(self) -> float:
        """Get USDC balance (available cash)."""
        balances = self.get_all_balances()
        return balances.get('USDC', 0.0)

    def get_usd_balance(self) -> float:
        """Get USD balance (fiat cash)."""
        balances = self.get_all_balances()
        return balances.get('USD', 0.0)

    def get_btc_orders(self, limit: int = 100) -> list:
        """Fetch recent BTC buy orders to calculate avg entry."""
        if not self.is_configured:
            return []

        path = f'/api/v3/brokerage/orders/historical/fills?product_id=BTC-USD&limit={limit}'
        headers = self._get_headers('GET', path)

        try:
            resp = http_client.get(COINBASE_API_URL + path, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('fills', [])
        except Exception:
            pass
        return []

    def calculate_avg_entry(self) -> float:
        """Calculate average entry price from recent buy orders."""
        fills = self.get_btc_orders()
        if not fills:
            return 0.0

        total_btc = 0.0
        total_cost = 0.0

        for fill in fills:
            if fill.get('side') == 'BUY':
                size = float(fill.get('size', 0))
                price = float(fill.get('price', 0))
                total_btc += size
                total_cost += size * price

        if total_btc > 0:
            return total_cost / total_btc
        return 0.0


# Global Coinbase client
coinbase_api = CoinbaseAPI() if HAS_HTTP_CLIENT else None


def load_parquet(name: str, resolution: str = 'daily') -> pd.Series:
    p = BL_DIR / resolution / f'{name}.parquet'
    if not p.exists():
        return pd.Series(dtype=float)
    df = pd.read_parquet(p)
    tc = next((c for c in ['time', 'date', 'timestamp'] if c in df.columns), None)
    vc = 'value' if 'value' in df.columns else None
    if tc and vc:
        s = df.set_index(tc)[vc].sort_index()
        s.index = pd.to_datetime(s.index)
        if s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        return s.astype(float).dropna()
    return pd.Series(dtype=float)


def load_all(resolution: str = 'daily') -> pd.DataFrame:
    metrics = {
        'price': 'price', 'tmm': 'true_market_mean_price',
        'sth_rp': 'realized_price_sth', 'realized_price': 'realized_price',
        'sip': 'supply_in_profit_percent', 'mvrv': 'mvrv', 'mvrv_sth': 'mvrv_sth',
        'sopr_sth': 'sopr_sth', 'sopr': 'sopr', 'sopr_lth': 'sopr_lth',
        'realized_loss': 'realized_loss', 'realized_profit': 'realized_profit',
        'mvrv_z': 'mvrv_z', 'nupl': 'nupl', 'aviv': 'aviv',
        'vaulted_price': 'vaulted_price',
    }
    data = {}
    for col, metric in metrics.items():
        s = load_parquet(metric, resolution)
        if not s.empty:
            data[col] = s
    df = pd.DataFrame(data).dropna(subset=['price']).ffill()
    if 'sip' in df.columns and df['sip'].max() <= 1.0:
        df['sip'] = df['sip'] * 100
    df['returns'] = df['price'].pct_change()
    if 'realized_loss' in df.columns:
        rl_roll = df['realized_loss'].rolling(365, min_periods=90)
        df['rl_z'] = (df['realized_loss'] - rl_roll.mean()) / rl_roll.std()
    df['sma_200'] = df['price'].rolling(200, min_periods=100).mean()
    # Derived metrics
    if 'realized_profit' in df.columns and 'realized_loss' in df.columns:
        df['rpl_ratio'] = df['realized_profit'] / df['realized_loss'].replace(0, np.nan)
    if 'price' in df.columns and 'sma_200' in df.columns:
        df['mayer_multiple'] = df['price'] / df['sma_200']
    return df.dropna(subset=['price'])


def compute_buy_the_dip(df: pd.DataFrame, latest: dict) -> dict:
    """Compute Buy The Dip conditions (on-chain only, no Glassnode derivatives)."""
    conditions = []

    # 1. STH-MVRV < 1.0 (short-term holders underwater)
    sth_mvrv = latest.get('mvrv_sth', np.nan)
    conditions.append({
        'label': 'STH-MVRV < 1.0',
        'desc': 'STH underwater',
        'value': sth_mvrv,
        'triggered': pd.notna(sth_mvrv) and sth_mvrv < 1.0
    })

    # 2. STH-SOPR < 1.0 (short-term holders selling at loss)
    sth_sopr = latest.get('sopr_sth', np.nan)
    conditions.append({
        'label': 'STH-SOPR < 1.0',
        'desc': 'STH selling at loss',
        'value': sth_sopr,
        'triggered': pd.notna(sth_sopr) and sth_sopr < 1.0
    })

    # 3. Realized P/L Ratio < 1.0 (losses exceed profits)
    rpl = latest.get('rpl_ratio', np.nan)
    conditions.append({
        'label': 'RP/L Ratio < 1.0',
        'desc': 'Loss > profit',
        'value': rpl,
        'triggered': pd.notna(rpl) and rpl < 1.0
    })

    # 4. NUPL < 0.25 (fear/capitulation zone)
    nupl = latest.get('nupl', np.nan)
    conditions.append({
        'label': 'NUPL < 0.25',
        'desc': 'Fear zone',
        'value': nupl,
        'triggered': pd.notna(nupl) and nupl < 0.25
    })

    # 5. Supply in Profit < 60% (majority underwater)
    sip = latest.get('sip', np.nan)
    conditions.append({
        'label': 'SIP < 60%',
        'desc': 'Majority underwater',
        'value': sip,
        'triggered': pd.notna(sip) and sip < 60
    })

    met_count = sum(1 for c in conditions if c['triggered'])

    if met_count >= 4:
        signal, color = 'STRONG DIP', 'green'
    elif met_count >= 3:
        signal, color = 'DIP FORMING', 'dark_green'
    elif met_count >= 2:
        signal, color = 'EARLY DIP', 'yellow'
    else:
        signal, color = 'NO DIP', 'dim'

    return {'conditions': conditions, 'met': met_count, 'total': len(conditions),
            'signal': signal, 'color': color}


def compute_exit_detector(df: pd.DataFrame, latest: dict) -> dict:
    """Compute 8-Metric Exit Detector (z-score based)."""
    conditions = []

    def z_score(series, lookback=365):
        if len(series) < lookback // 2:
            return np.nan
        recent = series.iloc[-lookback:]
        val = series.iloc[-1]
        return (val - recent.mean()) / recent.std() if recent.std() > 0 else 0

    metrics_config = [
        ('mvrv', 'MVRV', 1.5, 1460),
        ('mvrv_sth', 'STH-MVRV', 1.25, 365),
        ('sopr', 'SOPR', 1.5, 365),
        ('sopr_sth', 'STH-SOPR', 1.0, 365),
        ('mayer_multiple', 'Mayer', 1.0, 365),
        ('nupl', 'NUPL', 1.5, 365),
        ('sopr_lth', 'LTH-SOPR', 1.5, 365),
    ]

    for key, label, threshold, lookback in metrics_config:
        if key in df.columns:
            z = z_score(df[key].dropna(), lookback)
            val = latest.get(key, np.nan)
            triggered = pd.notna(z) and z > threshold
        else:
            z, val, triggered = np.nan, np.nan, False

        conditions.append({
            'label': f'{label}-Z > {threshold}σ',
            'value': val,
            'z_score': z,
            'threshold': threshold,
            'triggered': triggered
        })

    met_count = sum(1 for c in conditions if c['triggered'])

    if met_count >= 5:
        signal, color, rec = 'HIGH RISK', 'red', 'Exit positions'
    elif met_count >= 3:
        signal, color, rec = 'CAUTION', 'dark_orange', 'Reduce exposure'
    elif met_count >= 2:
        signal, color, rec = 'WARMING', 'yellow', 'Monitor closely'
    else:
        signal, color, rec = 'NORMAL', 'green', 'Continue DCA'

    return {'conditions': conditions, 'met': met_count, 'total': len(conditions),
            'signal': signal, 'color': color, 'recommendation': rec}


def classify_regime(price, sth_rp, tmm, rp):
    if pd.notna(rp) and price < rp: return 'EXTREME BEAR', 3
    if pd.notna(tmm) and price < tmm: return 'BEAR PH.2', 2
    if pd.notna(sth_rp) and price < sth_rp: return 'BEAR PH.1', 1
    return 'BULL', 0


def classify_zone(sip):
    if pd.isna(sip): return 'UNKNOWN', 0
    if sip < 40: return 'CAPITULATION', 5
    if sip < 50: return 'DEEP VALUE', 3
    if sip < 60: return 'VALUE', 2
    if sip < 75: return 'NORMAL', 0
    return 'OVERHEATED', 0


def compute_signal(row, live_price=None):
    price = live_price if live_price else row.get('price', np.nan)
    regime, phase = classify_regime(price, row.get('sth_rp'), row.get('tmm'), row.get('realized_price'))
    zone, zone_mult = classify_zone(row.get('sip'))
    dca_active = phase >= 1
    
    sopr_sth = row.get('sopr_sth', np.nan)
    rl_z = row.get('rl_z', np.nan)
    boost = 0
    if dca_active and zone_mult > 0:
        if pd.notna(sopr_sth) and sopr_sth < 0.90: boost += 1
        if pd.notna(rl_z) and rl_z > 2.0: boost += 1
    
    base_mult = max(zone_mult, 2) if dca_active and zone_mult > 0 and phase >= 2 else zone_mult
    final_mult = min(base_mult + boost, 5) if dca_active else 0
    
    ret = row.get('returns', 0)
    slug = zone_mult >= 3 and dca_active and pd.notna(ret) and ret < -0.05
    dca = 100 * final_mult + (300 if slug else 0)
    
    if not dca_active: action = 'WAIT'
    elif final_mult == 0: action = 'HOLD'
    elif slug: action = f'SLUG ${dca:.0f}'
    elif boost: action = f'BOOST ${dca:.0f}'
    else: action = f'BUY ${dca:.0f}'
    
    return {'regime': regime, 'phase': phase, 'zone': zone, 'mult': final_mult, 
            'boost': boost, 'slug': slug, 'dca': dca, 'action': action}


def pctile(series, val):
    if len(series) == 0 or pd.isna(val): return np.nan
    return (series < val).mean() * 100


def compute_price_zones(df: pd.DataFrame, latest: dict, current_price: float) -> list:
    """Compute price zones for the ladder display.

    Returns list of dicts: {'label': str, 'price': float, 'pct': float, 'icon': str, 'style': str, 'above': bool}
    Sorted from highest to lowest price.
    """
    zones = []

    # Get key values
    sth_rp = latest.get('sth_rp', np.nan)
    tmm = latest.get('tmm', np.nan)
    rp = latest.get('realized_price', np.nan)

    # === RESISTANCE LEVELS (above current price) ===

    # STH-MVRV based zones (warming, local top, overheated)
    if pd.notna(sth_rp) and sth_rp > 0:
        # Warming: STH-MVRV ~ 1.15-1.2
        warming = sth_rp * 1.18
        zones.append({'label': 'Warming', 'price': warming, 'icon': '🟡', 'style': 'yellow'})

        # Local Top: STH-MVRV ~ 1.3-1.4
        local_top = sth_rp * 1.35
        zones.append({'label': 'Local Top', 'price': local_top, 'icon': '🟠', 'style': 'dark_orange'})

        # Overheated: STH-MVRV ~ 1.5+
        overheated = sth_rp * 1.55
        zones.append({'label': 'Overheated (+1σ)', 'price': overheated, 'icon': '🔴', 'style': 'red'})

    # === SUPPORT LEVELS (below current price) ===

    # STH Cost Basis
    if pd.notna(sth_rp):
        zones.append({'label': 'STH Cost Basis', 'price': sth_rp, 'icon': '🟢', 'style': 'green'})

    # True Market Mean
    if pd.notna(tmm):
        zones.append({'label': 'True Mkt Mean', 'price': tmm, 'icon': '🟢', 'style': 'green'})

    # Realized Price
    if pd.notna(rp):
        zones.append({'label': 'Realized Price', 'price': rp, 'icon': '🔵', 'style': 'blue'})

    # Deep Value: estimate using AVIV z-score relationship
    # At -1.5σ AVIV, price is typically ~15-20% below TMM
    if pd.notna(tmm):
        deep_value = tmm * 0.70  # -1.5σ approximation
        zones.append({'label': 'Deep Value (-1.5σ)', 'price': deep_value, 'icon': '💎', 'style': 'cyan'})

    # Calculate distance from current price and sort
    for z in zones:
        z['pct'] = (current_price / z['price'] - 1) * 100 if z['price'] > 0 else 0
        z['above'] = z['price'] > current_price

    # Sort: highest price first
    zones.sort(key=lambda x: x['price'], reverse=True)

    return zones


ZONE_STYLES = {
    'CAPITULATION': ('bold white on red', '🔴'),
    'DEEP VALUE': ('bold white on dark_orange', '🟠'),
    'VALUE': ('bold black on yellow', '🟡'),
    'NORMAL': ('dim', '⚪'),
    'OVERHEATED': ('bold white on blue', '🔵'),
    'UNKNOWN': ('dim', '❓'),
}

REGIME_STYLES = {
    'EXTREME BEAR': 'bold white on red',
    'BEAR PH.2': 'bold white on dark_orange',
    'BEAR PH.1': 'bold yellow',
    'BULL': 'bold green',
}


class TickerUpdate(Message):
    def __init__(self, price: float, high_24h: float = 0, low_24h: float = 0, volume_24h: float = 0) -> None:
        self.price = price
        self.high_24h = high_24h
        self.low_24h = low_24h
        self.volume_24h = volume_24h
        super().__init__()


class ConnectionStatus(Message):
    def __init__(self, connected: bool, authenticated: bool = False) -> None:
        self.connected = connected
        self.authenticated = authenticated
        super().__init__()


class OrderUpdate(Message):
    """Real-time order update from websocket."""
    def __init__(self, order_id: str, status: str, side: str, product_id: str,
                 filled_size: float = 0, filled_value: float = 0, avg_price: float = 0) -> None:
        self.order_id = order_id
        self.status = status
        self.side = side
        self.product_id = product_id
        self.filled_size = filled_size
        self.filled_value = filled_value
        self.avg_price = avg_price
        super().__init__()


class BalanceUpdate(Message):
    """Real-time balance update from websocket."""
    def __init__(self, currency: str, available: float, hold: float = 0) -> None:
        self.currency = currency
        self.available = available
        self.hold = hold
        super().__init__()


class TightZoneDashboard(App):
    TITLE = "Tight Zone DCA"

    CSS = """
    Screen { background: $surface; }

    /* === HEADER SECTION (both bars) === */
    #header-section {
        dock: top;
        height: auto;
    }

    /* === TOP BAR === */
    #top-bar {
        height: 3;
        background: $primary-background;
        padding: 0 2;
    }

    #price-row {
        height: 1;
        layout: horizontal;
    }

    #status-col {
        width: 12;
    }

    #price-col {
        width: 1fr;
        text-align: center;
    }

    #change-col {
        width: 12;
        text-align: right;
    }

    #stats-row {
        height: 1;
        layout: horizontal;
        color: $text-muted;
    }

    #stats-col {
        width: 1fr;
        text-align: center;
    }

    /* === ACTION BAR === */
    #action-bar {
        height: 1;
        layout: horizontal;
        padding: 0 2;
        background: $surface-darken-1;
    }

    #regime-badge { width: auto; padding: 0 2; }
    #zone-badge { width: auto; padding: 0 2; margin-left: 1; }
    #action-text { width: 1fr; text-align: right; text-style: bold; }

    /* === MAIN === */
    #main-area { layout: horizontal; height: 1fr; margin: 1 1 0 1; }
    #left-panel { width: 1fr; padding: 0 1 0 0; }
    #center-panel { width: 1fr; padding: 0 1; }
    #right-panel { width: 1fr; padding: 0 0 0 1; }

    .section-title { background: $primary-background; text-style: bold; padding: 0 1; height: 1; }
    #price-zones { height: auto; max-height: 14; padding: 0 1; }
    #current-price-marker { background: $primary-background; text-style: bold; padding: 0 1; height: 1; text-align: center; }
    #signals-table { height: auto; max-height: 12; }
    #history-table { height: 1fr; }
    #sparkline-box { height: 6; }
    #sparkline-label { height: 1; color: $text-muted; text-style: italic; padding: 0 1; }
    Sparkline { height: 5; margin: 0 1; }
    Sparkline > .sparkline--max-color { color: $success; }
    Sparkline > .sparkline--min-color { color: $error; }

    /* === CHECKLISTS === */
    #btd-panel { height: auto; max-height: 12; padding: 0 1; }
    #exit-panel { height: auto; max-height: 12; padding: 0 1; }

    /* === POSITION === */
    #position-panel { height: auto; padding: 0 1; }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("t", "toggle_history", "7d/30d"),
        Binding("f", "toggle_resolution", "Timeframe"),
        Binding("a", "toggle_alerts", "Alerts"),
        Binding("p", "set_position", "Position"),
        Binding("q", "quit", "Quit"),
    ]

    show_30d = reactive(False)
    resolution = reactive("daily")
    live_price = reactive(0.0)
    prev_price = reactive(0.0)
    alerts_enabled = reactive(True)
    # Position tracking
    position_btc = reactive(0.0)
    position_entry = reactive(0.0)
    cash_balance = reactive(0.0)  # USDC or USD available
    all_balances = reactive({})  # All account balances
    high_24h = reactive(0.0)
    low_24h = reactive(0.0)
    volume_24h = reactive(0.0)
    ws_connected = reactive(False)
    ws_authenticated = reactive(False)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # Both bars in a single docked container
        with Vertical(id="header-section"):
            # Top bar: price display with stats
            with Vertical(id="top-bar"):
                with Horizontal(id="price-row"):
                    yield Static("○", id="status-col")
                    yield Static("$---,---", id="price-col")
                    yield Static("", id="change-col")
                with Horizontal(id="stats-row"):
                    yield Static("24h High: ---  ·  24h Low: ---  ·  Vol: ---", id="stats-col")

            # Action bar
            with Horizontal(id="action-bar"):
                yield Static("", id="regime-badge")
                yield Static("", id="zone-badge")
                yield Static("", id="action-text")

        # Main content - 3 columns
        with Horizontal(id="main-area"):
            with Vertical(id="left-panel"):
                yield Static("PRICE ZONES", classes="section-title")
                yield Static("", id="price-zones")
                yield Static("")  # spacer
                yield Static("SIGNALS", classes="section-title")
                yield DataTable(id="signals-table", show_cursor=False)
            with Vertical(id="center-panel"):
                yield Static("BUY THE DIP", classes="section-title")
                yield Static("", id="btd-panel")
                yield Static("")  # spacer
                yield Static("EXIT DETECTOR", classes="section-title")
                yield Static("", id="exit-panel")
            with Vertical(id="right-panel"):
                yield Static("POSITION", classes="section-title")
                yield Static("", id="position-panel")
                yield Static("")  # spacer
                yield Static("HISTORY (7d)", classes="section-title", id="history-title")
                yield DataTable(id="history-table", show_cursor=False)
                with Container(id="sparkline-box"):
                    yield Static("90-day price", id="sparkline-label")
                    yield Sparkline([], id="price-spark")

        yield Footer()

    def on_mount(self) -> None:
        self.df = pd.DataFrame()
        self.latest_row = {}
        self.all_balances = {}
        self.refresh_data()
        self.set_interval(3600, self.refresh_data)
        # Auto-sync Coinbase position on startup and refresh every 5 min
        if coinbase_api and coinbase_api.is_configured:
            self.sync_coinbase_position()
            self.set_interval(300, self.sync_coinbase_position)  # 5 min refresh
        if HAS_WEBSOCKETS:
            asyncio.create_task(self.websocket_loop())

    async def websocket_loop(self) -> None:
        while True:
            try:
                async with websockets.connect(COINBASE_WS_URL) as ws:
                    # Subscribe to ticker (unauthenticated - for price)
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "product_ids": [PRODUCT_ID],
                        "channel": "ticker"
                    }))

                    # Subscribe to user channel (authenticated - for orders/balances)
                    authenticated = False
                    if coinbase_api and coinbase_api.is_configured:
                        jwt_token = coinbase_api.build_ws_jwt()
                        if jwt_token:
                            await ws.send(json.dumps({
                                "type": "subscribe",
                                "channel": "user",
                                "product_ids": [PRODUCT_ID],
                                "jwt": jwt_token,
                            }))
                            authenticated = True

                    self.post_message(ConnectionStatus(True, authenticated))

                    async for message in ws:
                        try:
                            data = json.loads(message)
                            channel = data.get("channel", "")

                            # Handle ticker updates (price)
                            if channel == "ticker" and "events" in data:
                                for event in data["events"]:
                                    if event.get("type") == "update":
                                        for ticker in event.get("tickers", []):
                                            if ticker.get("product_id") == PRODUCT_ID:
                                                price = float(ticker.get("price", 0))
                                                high_24h = float(ticker.get("high_24_h", 0))
                                                low_24h = float(ticker.get("low_24_h", 0))
                                                volume_24h = float(ticker.get("volume_24_h", 0))
                                                if price > 0:
                                                    self.post_message(TickerUpdate(price, high_24h, low_24h, volume_24h))

                            # Handle user channel updates (orders, balances)
                            elif channel == "user" and "events" in data:
                                for event in data["events"]:
                                    event_type = event.get("type", "")

                                    # Order updates
                                    if event_type == "snapshot" or event_type == "update":
                                        for order in event.get("orders", []):
                                            self.post_message(OrderUpdate(
                                                order_id=order.get("order_id", ""),
                                                status=order.get("status", ""),
                                                side=order.get("side", ""),
                                                product_id=order.get("product_id", ""),
                                                filled_size=float(order.get("filled_size", 0) or 0),
                                                filled_value=float(order.get("filled_value", 0) or 0),
                                                avg_price=float(order.get("average_filled_price", 0) or 0),
                                            ))

                        except Exception:
                            pass
            except Exception:
                self.post_message(ConnectionStatus(False, False))
                await asyncio.sleep(5)

    def on_ticker_update(self, message: TickerUpdate) -> None:
        old_price = self.live_price
        self.live_price = message.price
        if message.high_24h > 0:
            self.high_24h = message.high_24h
        if message.low_24h > 0:
            self.low_24h = message.low_24h
        if message.volume_24h > 0:
            self.volume_24h = message.volume_24h
        self.update_price_display()
        self.update_action_bar()
        self.update_price_zones()
        self.update_position_panel()
        # Check for level crossings
        if self.alerts_enabled and old_price > 0:
            self.check_level_alerts(old_price, message.price)
        self.prev_price = old_price

    def check_level_alerts(self, old_price: float, new_price: float) -> None:
        """Check if price crossed any key levels and alert."""
        if not self.latest_row:
            return

        levels = [
            ('STH Cost Basis', self.latest_row.get('sth_rp')),
            ('True Mkt Mean', self.latest_row.get('tmm')),
            ('Realized Price', self.latest_row.get('realized_price')),
        ]

        for name, level in levels:
            if level is None or pd.isna(level):
                continue
            # Check for crossing
            crossed_up = old_price < level <= new_price
            crossed_down = old_price > level >= new_price
            if crossed_up:
                self.bell()
                self.notify(f"🔼 Price crossed ABOVE {name} (${level:,.0f})", severity="information")
            elif crossed_down:
                self.bell()
                self.notify(f"🔽 Price crossed BELOW {name} (${level:,.0f})", severity="warning")

    def on_connection_status(self, message: ConnectionStatus) -> None:
        self.ws_connected = message.connected
        self.ws_authenticated = message.authenticated
        self.update_price_display()
        if message.authenticated:
            self.notify("🔐 Authenticated websocket connected", severity="information")

    def on_order_update(self, message: OrderUpdate) -> None:
        """Handle real-time order updates."""
        if message.product_id != PRODUCT_ID:
            return

        # Show notification for order status changes
        if message.status == "FILLED":
            side_emoji = "🟢" if message.side == "BUY" else "🔴"
            self.bell()
            self.notify(
                f"{side_emoji} {message.side} FILLED: {message.filled_size:.6f} BTC @ ${message.avg_price:,.0f}",
                severity="information" if message.side == "BUY" else "warning"
            )
            # Refresh balances after fill
            if coinbase_api and coinbase_api.is_configured:
                self.sync_coinbase_position()
        elif message.status == "PENDING" or message.status == "OPEN":
            side_emoji = "🟡"
            self.notify(f"{side_emoji} Order {message.side}: {message.status}")

    def on_balance_update(self, message: BalanceUpdate) -> None:
        """Handle real-time balance updates."""
        # Update our tracked balances
        total = message.available + message.hold
        if hasattr(self, 'all_balances') and self.all_balances:
            if total > 0:
                self.all_balances[message.currency] = total
            elif message.currency in self.all_balances:
                del self.all_balances[message.currency]

            # Update cash balance if relevant
            if message.currency in ('USDC', 'USD'):
                usdc = self.all_balances.get('USDC', 0)
                usd = self.all_balances.get('USD', 0)
                self.cash_balance = usdc + usd

            # Update BTC position
            if message.currency == 'BTC':
                self.position_btc = total

            self.update_position_panel()

    def refresh_data(self) -> None:
        try:
            self.df = load_all(self.resolution)
            if not self.df.empty:
                self.latest_row = self.df.iloc[-1].to_dict()
                if self.live_price == 0:
                    self.live_price = self.latest_row.get('price', 0)
            self.update_display()
            self.sub_title = f"[{self.resolution.upper()}]"
        except Exception as e:
            self.query_one("#action-text").update(f"ERROR: {e}")

    def update_price_display(self) -> None:
        if not self.latest_row:
            return
        price = self.live_price if self.live_price > 0 else self.latest_row.get('price', 0)
        last_close = self.latest_row.get('price', price)
        change_pct = (price / last_close - 1) * 100 if last_close > 0 else 0

        # Status indicator - show auth status
        if self.ws_connected and self.ws_authenticated:
            status = "● AUTH"
            status_style = "bold green"
        elif self.ws_connected:
            status = "● LIVE"
            status_style = "bold cyan"
        else:
            status = "○"
            status_style = "dim yellow"
        self.query_one("#status-col").update(Text(status, style=status_style))

        # Big centered price
        self.query_one("#price-col").update(Text(f"${price:,.0f}", style="bold"))

        # Change percentage
        change_style = "bold green" if change_pct >= 0 else "bold red"
        self.query_one("#change-col").update(Text(f"{change_pct:+.2f}%", style=change_style))

        # Stats row: 24h High, Low, Volume
        high_str = f"${self.high_24h:,.0f}" if self.high_24h > 0 else "---"
        low_str = f"${self.low_24h:,.0f}" if self.low_24h > 0 else "---"
        if self.volume_24h >= 1_000_000_000:
            vol_str = f"${self.volume_24h / 1_000_000_000:.1f}B"
        elif self.volume_24h >= 1_000_000:
            vol_str = f"${self.volume_24h / 1_000_000:.1f}M"
        elif self.volume_24h > 0:
            vol_str = f"${self.volume_24h:,.0f}"
        else:
            vol_str = "---"

        stats_text = Text.assemble(
            ("24h High: ", "dim"),
            (high_str, "green"),
            ("  ·  ", "dim"),
            ("24h Low: ", "dim"),
            (low_str, "red"),
            ("  ·  ", "dim"),
            ("Vol: ", "dim"),
            (vol_str, ""),
        )
        self.query_one("#stats-col").update(stats_text)

    def update_action_bar(self) -> None:
        if not self.latest_row:
            return
        sig = compute_signal(self.latest_row, self.live_price if self.live_price > 0 else None)
        
        # Regime
        regime_style = REGIME_STYLES.get(sig['regime'], 'dim')
        self.query_one("#regime-badge").update(Text(f" {sig['regime']} ", style=regime_style))
        
        # Zone
        zone_style, zone_icon = ZONE_STYLES.get(sig['zone'], ('dim', ''))
        self.query_one("#zone-badge").update(Text(f" {zone_icon} {sig['zone']} ", style=zone_style))
        
        # Action
        if sig['action'].startswith('WAIT'):
            action_style, action_text = "dim", "WAIT — Preserve capital"
        elif sig['action'].startswith('HOLD'):
            action_style, action_text = "dim", "HOLD — Wait for value"
        elif sig['action'].startswith('SLUG'):
            action_style, action_text = "bold white on red", f"⚡ SLUG {sig['mult']}x + 3x"
        elif sig['action'].startswith('BOOST'):
            action_style, action_text = "bold white on dark_orange", f"🔥 BOOST {sig['mult']}x"
        elif sig['action'].startswith('BUY'):
            action_style, action_text = "bold white on dark_green", f"✅ BUY {sig['mult']}x"
        else:
            action_style, action_text = "", sig['action']
        self.query_one("#action-text").update(Text(action_text, style=action_style))

    def update_price_zones(self) -> None:
        if not self.latest_row or self.df.empty:
            return

        price = self.live_price if self.live_price > 0 else self.latest_row.get('price', 0)
        zones = compute_price_zones(self.df, self.latest_row, price)

        # Build the ladder display
        lines = []

        # Resistance zones (above current price)
        resistance = [z for z in zones if z['above']]
        for z in resistance:
            pct_str = f"{z['pct']:+.1f}%"
            line = Text.assemble(
                (f"${z['price']:>7,.0f}", z['style']),
                (" ▴ ", "dim"),
                (f"{z['label']:<20}", z['style']),
                (f"{pct_str:>8}", "dim red"),
                ("  ", ""),
                (z['icon'], ""),
            )
            lines.append(line)

        # Current price marker
        lines.append(Text("═" * 44 + " ", style="bold white"))
        current_line = Text.assemble(
            (f"${price:>7,.0f}", "bold white"),
            ("   ◄── ", "bold yellow"),
            ("YOU ARE HERE", "bold yellow"),
        )
        lines.append(current_line)
        lines.append(Text("═" * 44 + " ", style="bold white"))

        # Support zones (below current price)
        support = [z for z in zones if not z['above']]
        for z in support:
            pct_str = f"{z['pct']:+.1f}%"
            line = Text.assemble(
                (f"${z['price']:>7,.0f}", z['style']),
                (" ▾ ", "dim"),
                (f"{z['label']:<20}", z['style']),
                (f"{pct_str:>8}", "dim green"),
                ("  ", ""),
                (z['icon'], ""),
            )
            lines.append(line)

        # Join all lines
        combined = Text("\n").join(lines)
        self.query_one("#price-zones").update(combined)

    def update_btd_panel(self) -> None:
        if not self.latest_row or self.df.empty:
            return

        btd = compute_buy_the_dip(self.df, self.latest_row)
        lines = []

        # Header with score
        score_style = btd['color']
        header = Text.assemble(
            (f"{btd['met']}/{btd['total']}", f"bold {score_style}"),
            (" conditions met  ", "dim"),
            (f"[{btd['signal']}]", f"bold {score_style}"),
        )
        lines.append(header)
        lines.append(Text("─" * 36, style="dim"))

        # Conditions
        for cond in btd['conditions']:
            icon = "✓" if cond['triggered'] else "○"
            icon_style = "bold green" if cond['triggered'] else "dim"
            val = cond['value']
            val_str = f"{val:.3f}" if pd.notna(val) else "N/A"

            line = Text.assemble(
                (f" {icon} ", icon_style),
                (f"{cond['label']:<16}", "bold" if cond['triggered'] else "dim"),
                (f"{val_str:>8}", "cyan" if cond['triggered'] else "dim"),
            )
            lines.append(line)

        combined = Text("\n").join(lines)
        self.query_one("#btd-panel").update(combined)

    def update_exit_panel(self) -> None:
        if not self.latest_row or self.df.empty:
            return

        exit_data = compute_exit_detector(self.df, self.latest_row)
        lines = []

        # Header with score and recommendation
        score_style = exit_data['color']
        header = Text.assemble(
            (f"{exit_data['met']}/{exit_data['total']}", f"bold {score_style}"),
            (" triggered  ", "dim"),
            (f"[{exit_data['signal']}]", f"bold {score_style}"),
        )
        lines.append(header)
        rec_line = Text.assemble(
            ("→ ", "dim"),
            (exit_data['recommendation'], score_style),
        )
        lines.append(rec_line)
        lines.append(Text("─" * 36, style="dim"))

        # Conditions
        for cond in exit_data['conditions']:
            icon = "⚠" if cond['triggered'] else "○"
            icon_style = "bold red" if cond['triggered'] else "dim"
            z = cond['z_score']
            z_str = f"{z:+.2f}σ" if pd.notna(z) else "N/A"

            line = Text.assemble(
                (f" {icon} ", icon_style),
                (f"{cond['label']:<18}", "bold" if cond['triggered'] else "dim"),
                (f"{z_str:>7}", "red" if cond['triggered'] else "dim"),
            )
            lines.append(line)

        combined = Text("\n").join(lines)
        self.query_one("#exit-panel").update(combined)

    def update_display(self) -> None:
        if self.df.empty:
            return
        self.update_price_display()
        self.update_action_bar()
        self.update_price_zones()
        self.update_btd_panel()
        self.update_exit_panel()
        self.update_position_panel()

        # Signals
        latest = self.latest_row
        tbl = self.query_one("#signals-table", DataTable)
        tbl.clear(columns=True)
        tbl.add_columns("Metric", "Value", "Pct", "Bar")
        for name, key, unit in [('SIP', 'sip', '%'), ('STH-MVRV', 'mvrv_sth', ''),
                                 ('SOPR', 'sopr', ''), ('STH-SOPR', 'sopr_sth', ''),
                                 ('LTH-SOPR', 'sopr_lth', ''), ('MVRV-Z', 'mvrv_z', ''),
                                 ('NUPL', 'nupl', ''), ('RL Z', 'rl_z', '')]:
            val = latest.get(key)
            if pd.isna(val): continue
            pct = pctile(self.df[key].dropna(), val) if key in self.df.columns else np.nan
            if not np.isnan(pct):
                filled = int(pct / 100 * 15)
                bar = '█' * filled + '░' * (15 - filled)
                bar_style = "red" if pct < 20 else "dark_orange" if pct < 40 else "yellow" if pct < 60 else "green" if pct < 80 else "bright_green"
                tbl.add_row(name, f"{val:.2f}{unit}", f"P{pct:.0f}", Text(bar, style=bar_style))
            else:
                tbl.add_row(name, f"{val:.2f}{unit}", "", "")
        
        # History
        n = 30 if self.show_30d else 7
        self.query_one("#history-title").update(f"HISTORY ({n}d)")
        tbl = self.query_one("#history-table", DataTable)
        tbl.clear(columns=True)
        tbl.add_columns("Date", "Price", "Δ", "Zone", "Act")
        for idx, row in self.df.iloc[-n:].iterrows():
            sig = compute_signal(row)
            ret = row.get('returns', 0)
            _, z_icon = ZONE_STYLES.get(sig['zone'], ('', ''))
            act = "W" if sig['action'] == "WAIT" else sig['action'].split()[0][0]
            tbl.add_row(idx.strftime('%m/%d'), f"${row['price']:,.0f}",
                       Text(f"{ret*100:+.1f}%", style="green" if ret >= 0 else "red"), z_icon, act)
        
        # Sparkline
        self.query_one("#price-spark", Sparkline).data = self.df['price'].iloc[-90:].tolist()

    def action_refresh(self) -> None:
        self.refresh_data()
        self.notify("Refreshed")

    def action_toggle_history(self) -> None:
        self.show_30d = not self.show_30d
        self.update_display()

    def action_toggle_resolution(self) -> None:
        idx = RESOLUTIONS.index(self.resolution)
        self.resolution = RESOLUTIONS[(idx + 1) % len(RESOLUTIONS)]
        self.refresh_data()
        self.notify(f"Switched to {self.resolution.upper()}")

    def action_toggle_alerts(self) -> None:
        self.alerts_enabled = not self.alerts_enabled
        status = "ON" if self.alerts_enabled else "OFF"
        self.notify(f"Price alerts: {status}")

    def action_set_position(self) -> None:
        """Sync position from Coinbase or toggle manual position."""
        if coinbase_api and coinbase_api.is_configured:
            # Fetch from Coinbase
            self.sync_coinbase_position()
        else:
            # Manual toggle for testing
            if self.position_btc == 0:
                self.position_btc = 0.1
                self.position_entry = self.live_price if self.live_price > 0 else self.latest_row.get('price', 0)
                self.notify(f"Manual position: 0.1 BTC @ ${self.position_entry:,.0f}")
            else:
                self.position_btc = 0.0
                self.position_entry = 0.0
                self.notify("Position cleared")
        self.update_position_panel()

    def sync_coinbase_position(self) -> None:
        """Fetch position from Coinbase API."""
        if not coinbase_api or not coinbase_api.is_configured:
            self.notify("Coinbase API not configured", severity="warning")
            return

        try:
            # Fetch all balances at once
            all_balances = coinbase_api.get_all_balances()
            self.all_balances = all_balances  # Store for display

            btc_balance = all_balances.get('BTC', 0.0)
            # Cash is USDC + USD
            self.cash_balance = all_balances.get('USDC', 0.0) + all_balances.get('USD', 0.0)

            if btc_balance > 0:
                self.position_btc = btc_balance
                # Try to get average entry price from order history
                avg_entry = coinbase_api.calculate_avg_entry()
                if avg_entry > 0:
                    self.position_entry = avg_entry
                else:
                    # Fallback to current price if no order history
                    self.position_entry = self.live_price if self.live_price > 0 else self.latest_row.get('price', 0)
                self.notify(f"Synced: {btc_balance:.6f} BTC from Coinbase")
            else:
                self.position_btc = 0.0
                self.position_entry = 0.0
                if self.cash_balance > 0:
                    self.notify(f"No BTC — ${self.cash_balance:,.2f} cash available")
                elif all_balances:
                    # Show what we found
                    summary = ", ".join(f"{k}: {v:.4f}" for k, v in list(all_balances.items())[:3])
                    self.notify(f"Balances: {summary}")
                else:
                    self.notify("No balances found on Coinbase")
        except Exception as e:
            self.notify(f"Coinbase sync error: {e}", severity="error")

    def update_position_panel(self) -> None:
        # Check if Coinbase is configured
        cb_status = ""
        if coinbase_api and coinbase_api.is_configured:
            cb_status = " [CB]"

        if self.position_btc <= 0:
            # No BTC position - show all balances if available
            balances = getattr(self, 'all_balances', {}) or {}

            if balances:
                price = self.live_price if self.live_price > 0 else self.latest_row.get('price', 0)

                lines = [
                    Text.assemble(
                        ("💵 Coinbase Balances", "bold cyan"),
                        (cb_status, "dim green") if cb_status else ("", ""),
                    ),
                    Text("─" * 28, style="dim"),
                ]

                # Show all balances
                total_usd_value = 0.0
                for currency, amount in sorted(balances.items()):
                    if amount <= 0:
                        continue

                    # Format based on currency type
                    if currency in ('USD', 'USDC', 'USDT', 'DAI', 'GUSD'):
                        # Stablecoin - show as USD
                        val_str = f"${amount:,.2f}"
                        total_usd_value += amount
                        lines.append(Text.assemble(
                            (f"{currency:<6}", ""),
                            (f"{val_str:>14}", "bold green"),
                        ))
                    elif currency == 'BTC':
                        # BTC - show amount and USD value
                        usd_val = amount * price if price > 0 else 0
                        total_usd_value += usd_val
                        lines.append(Text.assemble(
                            (f"{currency:<6}", ""),
                            (f"{amount:>14.6f}", "bold yellow"),
                            (f" (${usd_val:,.0f})", "dim"),
                        ))
                    else:
                        # Other crypto - just show amount
                        lines.append(Text.assemble(
                            (f"{currency:<6}", ""),
                            (f"{amount:>14.6f}", "cyan"),
                        ))

                lines.append(Text("─" * 28, style="dim"))

                # Show total and BTC equivalent
                if total_usd_value > 0 and price > 0:
                    btc_equiv = total_usd_value / price
                    lines.append(Text.assemble(
                        ("Total: ", "dim"),
                        (f"${total_usd_value:,.2f}", "bold"),
                        (f" ({btc_equiv:.6f} BTC)", "dim cyan"),
                    ))

                lines.append(Text.assemble(
                    ("(p=refresh)", "dim italic"),
                ))

                combined = Text("\n").join(lines)
                self.query_one("#position-panel").update(combined)
                return

            # No balances synced yet
            if coinbase_api and coinbase_api.is_configured:
                msg = Text.assemble(
                    ("No position ", "dim"),
                    ("(p=sync Coinbase)", "dim italic"),
                )
            else:
                msg = Text.assemble(
                    ("No position ", "dim"),
                    ("(p=manual, set .env for CB)", "dim italic"),
                )
            self.query_one("#position-panel").update(msg)
            return

        price = self.live_price if self.live_price > 0 else self.latest_row.get('price', 0)
        entry = self.position_entry
        btc = self.position_btc

        value = btc * price
        cost = btc * entry
        pnl = value - cost
        pnl_pct = (price / entry - 1) * 100 if entry > 0 else 0

        pnl_style = "bold green" if pnl >= 0 else "bold red"
        pnl_sign = "+" if pnl >= 0 else ""

        lines = [
            Text.assemble(
                ("Position: ", "dim"),
                (f"{btc:.6f} BTC", "bold cyan"),
                (cb_status, "dim green") if cb_status else ("", ""),
            ),
            Text.assemble(
                ("Entry: ", "dim"),
                (f"${entry:,.0f}", ""),
                ("  →  ", "dim"),
                ("Now: ", "dim"),
                (f"${price:,.0f}", "bold"),
            ),
            Text.assemble(
                ("Value: ", "dim"),
                (f"${value:,.2f}", "bold"),
            ),
            Text.assemble(
                ("P&L: ", "dim"),
                (f"{pnl_sign}${abs(pnl):,.2f} ({pnl_pct:+.1f}%)", pnl_style),
            ),
        ]

        combined = Text("\n").join(lines)
        self.query_one("#position-panel").update(combined)


if __name__ == '__main__':
    TightZoneDashboard().run()
