"""
Configuration Module
====================
Single source of truth for all pipeline configuration.
"""

import yaml
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass


# =============================================================================
# PATHS
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
RESULTS_DIR = DATA_DIR / "results"
SIGNALS_DIR = DATA_DIR / "signals"

# Ensure directories exist
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
(RESULTS_DIR / "screens").mkdir(exist_ok=True)
(RESULTS_DIR / "backtests").mkdir(exist_ok=True)
(RESULTS_DIR / "walk_forward").mkdir(exist_ok=True)


# =============================================================================
# LOAD YAML CONFIGS
# =============================================================================

def load_yaml(filename: str) -> dict:
    """Load a YAML config file."""
    path = CONFIG_DIR / filename
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_regimes() -> List[Dict]:
    """Load regime definitions from regimes.yaml."""
    config = load_yaml("regimes.yaml")
    return config.get("regimes", [])


# =============================================================================
# REGIME DEFINITIONS
# =============================================================================

REGIMES = load_regimes()

BULL_MARKETS = [
    {
        "name": r["name"],
        "start": r["start"],
        "end": r["end"]
    }
    for r in REGIMES if r.get("type") == "bull"
]

BEAR_MARKETS = [
    {
        "name": r["name"],
        "start": r["start"],
        "end": r["end"]
    }
    for r in REGIMES if r.get("type") == "bear"
]

# If no regimes.yaml, use defaults
if not BULL_MARKETS:
    BULL_MARKETS = [
        {"name": "2015-2017", "start": "2015-10-01", "end": "2017-12-17"},
        {"name": "2019", "start": "2018-12-15", "end": "2019-06-26"},
        {"name": "2020-2021", "start": "2020-03-13", "end": "2021-11-10"},
        {"name": "2023-2024", "start": "2022-11-21", "end": "2024-03-14"},
        {"name": "2024-Present", "start": "2024-09-01", "end": "2026-12-31"},
    ]

if not BEAR_MARKETS:
    BEAR_MARKETS = [
        {"name": "2015 Bottom", "start": "2015-01-01", "end": "2015-10-01"},
        {"name": "2018", "start": "2017-12-17", "end": "2018-12-15"},
        {"name": "2019 Correction", "start": "2019-06-26", "end": "2020-03-13"},
        {"name": "2022", "start": "2021-11-10", "end": "2022-11-21"},
        {"name": "2024 Consolidation", "start": "2024-03-14", "end": "2024-09-01"},
    ]


# =============================================================================
# DEFAULT METRICS
# =============================================================================

DEFAULT_METRICS = [
    'mvrv', 'mvrv_z', 'mvrv_lth', 'mvrv_sth',
    'nupl', 'nupl_lth', 'nupl_sth',
    'sopr', 'sopr_lth', 'sopr_sth',
    'nvt', 'supply_in_profit_percent',
    'supply_lth_sth_ratio',
    'liveliness', 'vaultedness',
    'coindays_destroyed', 'velocity'
]


# =============================================================================
# DEFAULT PARAMETERS
# =============================================================================

DEFAULT_PERCENTILES = [5, 10, 20, 80, 90, 95]
DEFAULT_HOLD_PERIODS = [7, 14, 30, 60, 90]


# =============================================================================
# WALK-FORWARD DEFAULTS
# =============================================================================

@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward validation."""
    # Anchored (expanding window)
    anchored_min_train_years: float = 2.0
    anchored_test_years: float = 1.0
    
    # Rolling window
    rolling_train_years: float = 3.0
    rolling_test_years: float = 1.0
    rolling_step_years: float = 1.0
    
    # Cycle-based (leave-one-out)
    use_cycles: bool = True
    
    # Approval thresholds
    min_oos_sharpe: float = 0.3
    min_consistency: float = 0.6
    max_degradation: float = 0.5
    min_oos_win_rate: float = 0.45
    max_oos_drawdown: float = 0.4


DEFAULT_WF_CONFIG = WalkForwardConfig()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_regime_for_date(date) -> str:
    """Get regime type for a specific date."""
    import pandas as pd
    
    if isinstance(date, str):
        date = pd.Timestamp(date)
    if date.tz is None:
        date = date.tz_localize("UTC")
    
    for r in REGIMES:
        start = pd.Timestamp(r["start"], tz="UTC")
        end = pd.Timestamp(r["end"], tz="UTC")
        if start <= date < end:
            return r["type"]
    
    return "undefined"


def get_cycles(regime: str = "bull") -> List[Dict]:
    """Get market cycles for a regime type."""
    if regime == "bull":
        return BULL_MARKETS
    elif regime == "bear":
        return BEAR_MARKETS
    else:
        return BULL_MARKETS + BEAR_MARKETS
