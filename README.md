# Bitcoin Lab Data Pipeline

A data pipeline for downloading, analysing, and validating Bitcoin on-chain trading signals.

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

## Quick Start

```bash
# Setup
cd bitcoin-lab-btc-data-pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Download data
export BITCOIN_LAB_TOKEN="your-token"
python run.py backfill

# Data mining (find signals)
python -m src.miner

# Walk-forward validation (test signals)
python -m src.walk_forward
```

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

## API Requirements

- **Tier 2** Bitcoin Lab subscription
- Rate limit: 60 requests/minute
- Weekly quota: 40M data points

## License

MIT
