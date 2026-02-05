# TUI Dashboard

A real-time terminal dashboard for Bitcoin trading signals built with [Textual](https://textual.textualize.io/).

## Features

### Live Price Feed
- Real-time BTC price via Coinbase Advanced Trade websocket
- 24h high/low/volume stats
- Price change percentage from daily close

### On-Chain Signals (6 Pillars)
- **Price Zones Ladder**: Visual display of key support/resistance levels
  - Resistance: Overheated (+1σ), Local Top, Warming (based on STH-MVRV)
  - Support: STH Cost Basis, True Market Mean, Realized Price, Deep Value (-1.5σ)
- **Signal Percentiles**: SIP, STH-MVRV, SOPR, STH-SOPR, LTH-SOPR, MVRV-Z, NUPL, RL-Z with historical percentile bars

### Buy The Dip Checklist
5 conditions based on James Check's framework:
1. STH-MVRV < 1.0 (short-term holders underwater)
2. STH-SOPR < 1.0 (short-term holders selling at loss)
3. Realized P/L Ratio < 1.0 (losses exceed profits)
4. NUPL < 0.25 (fear/capitulation zone)
5. Supply in Profit < 60% (majority underwater)

Signal strength: 4-5 = STRONG DIP, 3 = DIP FORMING, 2 = EARLY DIP

### 8-Metric Exit Detector
Z-score based cycle top detection:
- MVRV-Z > 1.5σ
- STH-MVRV-Z > 1.25σ
- SOPR-Z > 1.5σ
- STH-SOPR-Z > 1.0σ
- Mayer Multiple-Z > 1.0σ
- NUPL-Z > 1.5σ
- LTH-SOPR-Z > 1.5σ

Risk levels: 5+ = HIGH RISK (exit), 3-4 = CAUTION (reduce), 2 = WARMING (monitor)

### Position Tracking (Coinbase Integration)
- Real-time balance display from Coinbase Advanced Trade API
- Shows all account balances (BTC, USDC, USD, etc.)
- Calculates USD value and BTC equivalent at current price
- Auto-syncs on startup and every 5 minutes

### Authenticated Websocket
- Real-time order fill notifications
- Bell alert when orders execute
- Auto-refresh balances after fills
- Status indicator: AUTH (authenticated), LIVE (price only), ○ (disconnected)

### Price Level Alerts
- Bell notification when price crosses key levels
- Alerts for STH Cost Basis, True Market Mean, Realized Price crossings

## Usage

```bash
python research/112_tui_dashboard.py
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `r` | Refresh on-chain data |
| `t` | Toggle history (7d/30d) |
| `f` | Cycle timeframe (daily/hourly/h4/h8/h12) |
| `a` | Toggle price alerts on/off |
| `p` | Sync position from Coinbase |
| `q` | Quit |

## Requirements

```
textual>=1.0.0
websockets>=12.0
PyJWT>=2.8.0
cryptography>=41.0.0
python-dotenv>=1.0.0
```

## Configuration

### Environment Variables (.env)

```bash
# Coinbase CDP API (for position tracking and authenticated websocket)
COINBASE_API_KEY=organizations/xxx/apiKeys/yyy
COINBASE_API_SECRET=-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----\n
```

Get your API keys from: https://portal.cdp.coinbase.com/

### Data Sources

The dashboard loads on-chain data from local parquet files:
- `data/bl/daily/` - Daily resolution (default)
- `data/bl/hourly/` - Hourly resolution
- `data/bl/h4/` - 4-hour resolution
- `data/bl/h8/` - 8-hour resolution
- `data/bl/h12/` - 12-hour resolution

Run `python scripts/calculate.py` to refresh signal calculations.

## Layout

```
┌─────────────────────────────────────────────────────────────┐
│ ● AUTH    $XXX,XXX                              +X.XX%      │
│           24h High: $XXX,XXX · Low: $XXX,XXX · Vol: $X.XB   │
├─────────────────────────────────────────────────────────────┤
│ BULL                    NORMAL                  ✅ BUY 2x   │
├───────────────────┬───────────────────┬─────────────────────┤
│ PRICE ZONES       │ BUY THE DIP       │ POSITION            │
│ $XXX,XXX Overheat │ 2/5 [NO DIP]      │ 💵 Coinbase [CB]    │
│ $XXX,XXX Local Top│ ○ STH-MVRV < 1.0  │ USDC    $XX,XXX.XX  │
│ ═══ YOU ARE HERE ═│ ○ STH-SOPR < 1.0  │ ──────────────────  │
│ $XXX,XXX STH Cost │ ...               │ Total: $XX,XXX      │
│ $XXX,XXX TMM      │                   │                     │
│ $XXX,XXX Realized │ EXIT DETECTOR     │ HISTORY (7d)        │
│ $XXX,XXX Deep Val │ 0/7 [NORMAL]      │ Date  Price  Δ Zone │
│                   │ → Continue DCA    │ ...                 │
│ SIGNALS           │ ○ MVRV-Z > 1.5σ   │                     │
│ SIP      75.2% P75│ ○ STH-MVRV-Z...   │ [90-day sparkline]  │
│ STH-MVRV 1.05  P55│ ...               │                     │
│ ...               │                   │                     │
└───────────────────┴───────────────────┴─────────────────────┘
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    TUI Dashboard                         │
│                  (Textual App)                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌────────────┐  │
│  │  Websocket  │    │  REST API   │    │  Parquet   │  │
│  │  (async)    │    │  (sync)     │    │  Files     │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬─────┘  │
│         │                  │                  │        │
│         ▼                  ▼                  ▼        │
│  ┌─────────────┐    ┌─────────────┐    ┌────────────┐  │
│  │ ticker ch.  │    │ /accounts   │    │ data/bl/   │  │
│  │ (price)     │    │ /orders     │    │ *.parquet  │  │
│  │             │    │ /fills      │    │            │  │
│  │ user ch.    │    │             │    │            │  │
│  │ (orders)    │    │             │    │            │  │
│  └─────────────┘    └─────────────┘    └────────────┘  │
│         │                  │                  │        │
│         └──────────────────┼──────────────────┘        │
│                            ▼                           │
│                   ┌─────────────┐                      │
│                   │  Messages   │                      │
│                   │ TickerUpdate│                      │
│                   │ OrderUpdate │                      │
│                   │ BalanceUpd. │                      │
│                   └─────────────┘                      │
│                            │                           │
│                            ▼                           │
│                   ┌─────────────┐                      │
│                   │   Display   │                      │
│                   │  (reactive) │                      │
│                   └─────────────┘                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Coinbase API Authentication

The dashboard uses Coinbase CDP (Cloud Developer Platform) API with JWT/ES256 authentication:

1. **REST API**: Used for fetching account balances on startup and periodic refresh
2. **Websocket**: Authenticated `user` channel for real-time order updates

JWT tokens include:
- `sub`: API key (organizations/xxx/apiKeys/yyy)
- `iss`: "cdp"
- `kid`: API key in header
- `nonce`: Random hex for replay protection
- `uri`: Request URI (REST only)

## Future Enhancements

- [ ] Place orders directly from TUI
- [ ] Order book display
- [ ] Multiple product support (ETH-USD, etc.)
- [ ] Historical trade log
- [ ] P&L tracking over time
- [ ] Custom alert thresholds
