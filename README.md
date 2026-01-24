# Bitcoin Lab Data Pipeline

A comprehensive data pipeline for downloading, analyzing, and generating Bitcoin on-chain trading signals using the James Check framework.

## 📚 Documentation

**New here?** Check the [complete documentation →](docs/README.md)

| Guide | Description |
|-------|-------------|
| **[Setup Guide](docs/setup/API_KEYS_SETUP.md)** | Configure API keys and get started |
| **[Dashboard Workflow](docs/guides/DASHBOARD_WORKFLOW.md)** | Daily trading signal generation |
| **[Quick Reference](docs/guides/QUICK_REFERENCE.md)** | Common commands cheat sheet |
| **[Strategy Framework](docs/research/STRATEGY_FRAMEWORK.md)** | James Check implementation |

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DISCOVERY PIPELINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. DOWNLOAD         2. DATA MINING       3. WALK-FORWARD       │
│  ───────────    →   ───────────────   →   ───────────────       │
│  run.py sync        miner.py              walk_forward.py       │
│                     • OLS regression      • Cycle validation    │
│                     • Grid search         • OOS testing         │
│                     • Smoothness check    • Approval gates      │
│                                                                 │
│                              ↓                                  │
│                     signals/approved.json                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                       EXECUTION PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   4. PAPER TRADE              5. LIVE TRADE                     │
│   ──────────────────     →    ──────────────────                │
│   paper_trader.py             live_trader.py                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Daily Trading Workflow (Recommended)

```bash
# 1. One-command dashboard generation
python run.py dashboard

# Syncs all data → checks quality → calculates signals → opens dashboards
```

**See**: [Dashboard Workflow Guide](docs/guides/DASHBOARD_WORKFLOW.md)

### First-Time Setup

```bash
# 1. Clone and install
git clone <repo-url>
cd bitcoin-lab-btc-data-pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
nano .env  # Add your Bitcoin Lab and Glassnode API keys

# 3. Verify setup
python src/secrets.py

# 4. Run first sync
python run.py dashboard
```

**See**: [API Keys Setup Guide](docs/setup/API_KEYS_SETUP.md)

### Advanced: Data Mining & Strategy Development

```bash
# Data mining (find signals)
python -m src.miner

# Walk-forward validation (test signals)
python -m src.walk_forward

# Custom backtests
jupyter notebook research/
```

**See**: [Strategy Framework](docs/research/STRATEGY_FRAMEWORK.md)

## Data Mining (Key Module)

The miner follows analyst best practices:

### 1. OLS Regression (not just correlation)

```python
from src.miner import DataMiner

miner = DataMiner()
df = miner.load_data()

# Get proper statistics: coefficient, p-value, R²
result = miner.regression_analysis(df, 'mvrv', regime='bull')
print(f"p-value: {result.p_value}")  # Is it statistically significant?
print(f"R²: {result.r_squared}")      # How much variance explained?
```

### 2. Grid Search with Smoothness Check

```python
# Test across threshold range
gs = miner.grid_search(df, 'mvrv', direction='below', regime='bull')

print(f"Best Sharpe: {gs.best_sharpe}")
print(f"Smoothness: {gs.smoothness_score}")  # Lower = better
print(f"Is smooth: {gs.is_smooth}")          # Must be True!
```

**Why smoothness matters:**
```
OVERFIT (spiky):                ROBUST (smooth):

Sharpe                          Sharpe
  │    *                          │   ****
  │   * *                         │  *    *
  │  *   *                        │ *      *
  │ *     *                       │*        *
  └──────────→ threshold          └──────────→ threshold

Only works at ONE threshold     Works across a RANGE
= random noise                  = real signal
```

### 3. Cycle-by-Cycle Validation

```python
# Must work in multiple bull markets, not just one
cycle_results = miner.cycle_regression(df, 'mvrv', regime='bull')

# Check how many cycles it's significant in
robustness = miner.metric_robustness(df, regime='bull')
```

### 4. Find Passing Signals

```python
# Signals that pass ALL tests
candidates = miner.find_signals(df, regime='bull')

for signal in candidates:
    print(f"{signal.name}")
    print(f"  p-value: {signal.p_value}")
    print(f"  Sharpe: {signal.sharpe}")
    print(f"  Smoothness: {signal.smoothness}")
```

### CLI

```bash
python -m src.miner
```

**Example Output:**
```
==========================================================================================
DATA MINING REPORT
==========================================================================================
Data: 4024 total rows, 2580 bull market rows

──────────────────────────────────────────────────────────────────────────────────────────
1. OLS REGRESSION: fwd_return ~ metric
──────────────────────────────────────────────────────────────────────────────────────────

Metric                         Coef    t-stat    p-value       R² Sig
--------------------------------------------------------------------------
nvt                        -0.00179     -7.84     0.0000   0.0236 ***
supply_lth_sth_ratio       -0.04721     -8.36     0.0000   0.0267 ***
mvrv_lth                   +0.00850     +6.70     0.0000   0.0173 ***

──────────────────────────────────────────────────────────────────────────────────────────
2. GRID SEARCH - SHARPE CURVE SMOOTHNESS
──────────────────────────────────────────────────────────────────────────────────────────

Metric               Dir    Sharpe   Smooth   OK?
--------------------------------------------------
supply_lth_sth_ratio above     3.71     0.08    ✓
nvt                  below     2.33     0.03    ✓
sopr                 above     2.47     0.04    ✓

🏆 RECOMMENDED SIGNALS:

  supply_lth_sth_ratio<4.448
    Regression: coef=-0.04721, p=0.0000
    Grid: Sharpe=3.71, smoothness=0.08

  nvt<29.251
    Regression: coef=-0.00179, p=0.0000
    Grid: Sharpe=2.33, smoothness=0.03
```

## Key Rules

| Rule | Why |
|------|-----|
| **Use regression p-values** | Correlation doesn't tell you if it's statistically significant |
| **Sharpe curve must be smooth** | Spiky = overfit to one threshold |
| **Must work in multiple cycles** | Not just one lucky period |
| **Single digit metrics** | Max 9 parameters to avoid overfitting |

## Walk-Forward Validation

After mining, validate with out-of-sample testing:

```python
from src.walk_forward import WalkForwardValidator
from src.models import SignalSpec

validator = WalkForwardValidator()
df = validator.load_data()

signal = SignalSpec(
    metric='nvt',
    direction='below',
    threshold=29.3,
    regime='bull'
)

result = validator.validate(df, signal)
print(f"OOS Sharpe: {result.oos_sharpe}")    # Real performance
print(f"Consistency: {result.consistency}")  # % of cycles profitable
print(f"Passed: {result.passed}")
```

## Exit Modes

The backtester supports proper exit strategies (not arbitrary hold periods):

| Mode | Logic |
|------|-------|
| **COMBINED** (default) | Exit when signal OR regime ends |
| SIGNAL_EXIT | Exit when metric leaves threshold |
| REGIME_EXIT | Exit when bull → bear |
| FIXED_HOLD | Legacy: exit after N days |

## Project Structure

```
bitcoin-lab-btc-data-pipeline/
├── config/
│   ├── metrics.yaml           # Metric definitions
│   └── regimes.yaml           # Bull/bear periods
├── data/
│   ├── raw/                   # Downloaded parquet files
│   ├── results/               # Analysis outputs
│   │   ├── screens/           # Miner outputs
│   │   ├── backtests/         
│   │   └── walk_forward/      
│   └── signals/
│       └── approved.json      # Signals that passed validation
├── src/
│   ├── config.py              # Shared configuration
│   ├── models.py              # Shared dataclasses
│   ├── downloader.py          # Data ingestion
│   ├── miner.py               # Data mining (regression + grid search)
│   ├── backtester.py          # Strategy backtester
│   └── walk_forward.py        # Walk-forward validation
└── run.py
```

## 📊 Generated Dashboards

The pipeline generates dashboards in the `dashboards/` folder:

1. **`dashboards/dashboard.html`** - 6-pillar on-chain analysis
   - Valuation, Profitability, Spending, Supply, Activity, Miner Health

2. **`dashboards/dashboard_signals.html`** - Trading signals
   - Entry signals (Checkmate, Buy The Dip)
   - Exit signals (8-Metric Detector, LTH Distribution)

## 🔑 API Requirements

- **Bitcoin Lab** - Primary on-chain data source
- **Glassnode** - Derivatives data (funding, liquidations)
- **BRK** (FREE) - Backup on-chain data source

**See**: [Data Source Configuration](docs/setup/DATA_SOURCE_CONFIG.md)

## 📂 Repository Structure

```
bitcoin-lab-btc-data-pipeline/
├── docs/                  # 📚 All documentation
│   ├── setup/             # Configuration guides
│   ├── guides/            # Usage workflows
│   ├── research/          # Strategy development
│   └── archive/           # Historical reports
├── data/                  # Data storage
│   ├── brk/daily/         # BRK on-chain metrics (FREE)
│   ├── glassnode/daily/   # Derivatives data
│   └── signals/           # Computed trading signals
├── scripts/               # Executable utilities
│   ├── calculate.py       # Signal computation
│   ├── dashboard_new.py   # Main dashboard generator
│   ├── dashboard_signals.py  # Signals dashboard
│   └── sync_and_dashboard.py # Full pipeline wrapper
├── src/                   # Core library
│   ├── downloader.py      # Bitcoin Lab API
│   ├── brk_downloader.py  # BRK API (FREE)
│   ├── data_loader.py     # Unified data loader
│   ├── secrets.py         # Secrets management
│   └── trading_system.py  # Signal calculation
├── research/              # Jupyter notebooks
├── config/                # Configuration files
├── run.py                 # CLI entry point
├── CLAUDE.md              # Project instructions
└── README.md              # This file
```

## 🆘 Need Help?

- 📖 [Documentation Index](docs/README.md)
- 🔑 [API Keys Setup](docs/setup/API_KEYS_SETUP.md)
- 📊 [Dashboard Workflow](docs/guides/DASHBOARD_WORKFLOW.md)
- 📋 [Quick Reference](docs/guides/QUICK_REFERENCE.md)

## License

MIT
