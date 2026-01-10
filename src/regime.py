"""
Regime Filter Module
====================
Identifies bull/bear market regimes based on configured periods.

Usage:
    from src.regime import RegimeFilter
    
    rf = RegimeFilter()
    
    # Single date
    regime = rf.get_regime("2021-05-15")  # "bull"
    
    # Add regime column to DataFrame
    df = rf.add_regime(df)  # Adds 'regime' and 'regime_name' columns
    
    # Get regime-filtered data
    bull_df = rf.filter_bull(df)
    bear_df = rf.filter_bear(df)
    
    # Current regime
    print(rf.current_regime())
"""

import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime, date
from typing import Union, Optional, Literal

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
REGIMES_FILE = CONFIG_DIR / "regimes.yaml"


# =============================================================================
# REGIME FILTER CLASS
# =============================================================================

class RegimeFilter:
    """
    Filter and classify market regimes based on configured periods.
    
    Regimes are defined in config/regimes.yaml with start/end dates.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize regime filter.
        
        Args:
            config_path: Path to regimes.yaml (default: config/regimes.yaml)
        """
        self.config_path = config_path or REGIMES_FILE
        self.regimes = self._load_regimes()
        self._build_lookup()
    
    def _load_regimes(self) -> list[dict]:
        """Load regime definitions from YAML."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Regimes config not found: {self.config_path}")
        
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        
        return config.get("regimes", [])
    
    def _build_lookup(self):
        """Build internal lookup structures for fast regime detection."""
        self._periods = []
        
        for regime in self.regimes:
            start = pd.Timestamp(regime["start"], tz="UTC")
            end = pd.Timestamp(regime["end"], tz="UTC")
            
            self._periods.append({
                "name": regime["name"],
                "type": regime["type"],
                "start": start,
                "end": end,
                "notes": regime.get("notes", "")
            })
        
        # Sort by start date
        self._periods.sort(key=lambda x: x["start"])
    
    def _normalize_date(self, dt: Union[str, datetime, date, pd.Timestamp]) -> pd.Timestamp:
        """Convert various date formats to UTC Timestamp."""
        if isinstance(dt, str):
            ts = pd.Timestamp(dt)
        elif isinstance(dt, (datetime, date)):
            ts = pd.Timestamp(dt)
        elif isinstance(dt, pd.Timestamp):
            ts = dt
        else:
            raise TypeError(f"Cannot convert {type(dt)} to Timestamp")
        
        # Ensure UTC
        if ts.tz is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        
        return ts
    
    # -------------------------------------------------------------------------
    # CORE API
    # -------------------------------------------------------------------------
    
    def get_regime(self, dt: Union[str, datetime, date, pd.Timestamp]) -> Optional[str]:
        """
        Get regime type for a specific date.
        
        Args:
            dt: Date to check (string, datetime, or Timestamp)
            
        Returns:
            "bull", "bear", or None if date not in any defined period
        """
        ts = self._normalize_date(dt)
        
        for period in self._periods:
            if period["start"] <= ts < period["end"]:
                return period["type"]
        
        return None
    
    def get_regime_name(self, dt: Union[str, datetime, date, pd.Timestamp]) -> Optional[str]:
        """
        Get regime name for a specific date.
        
        Args:
            dt: Date to check
            
        Returns:
            Regime name (e.g., "2020-2021 Bull Run") or None
        """
        ts = self._normalize_date(dt)
        
        for period in self._periods:
            if period["start"] <= ts < period["end"]:
                return period["name"]
        
        return None
    
    def get_regime_info(self, dt: Union[str, datetime, date, pd.Timestamp]) -> Optional[dict]:
        """
        Get full regime info for a specific date.
        
        Returns:
            Dict with name, type, start, end, notes — or None
        """
        ts = self._normalize_date(dt)
        
        for period in self._periods:
            if period["start"] <= ts < period["end"]:
                return period.copy()
        
        return None
    
    def current_regime(self) -> dict:
        """
        Get current regime info.
        
        Returns:
            Dict with name, type, start, end, notes
        """
        now = pd.Timestamp.now(tz="UTC")
        info = self.get_regime_info(now)
        
        if info is None:
            return {
                "name": "undefined",
                "type": "undefined",
                "start": None,
                "end": None,
                "notes": "Current date not in any defined regime"
            }
        
        return info
    
    # -------------------------------------------------------------------------
    # DATAFRAME OPERATIONS
    # -------------------------------------------------------------------------
    
    def add_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add regime columns to DataFrame.
        
        Args:
            df: DataFrame with DatetimeIndex
            
        Returns:
            DataFrame with 'regime' and 'regime_name' columns added
        """
        df = df.copy()
        
        df["regime"] = df.index.map(lambda x: self.get_regime(x))
        df["regime_name"] = df.index.map(lambda x: self.get_regime_name(x))
        
        return df
    
    def classify_series(self, dates: pd.DatetimeIndex) -> pd.Series:
        """
        Classify a series of dates into regimes.
        
        Args:
            dates: DatetimeIndex to classify
            
        Returns:
            Series with regime types
        """
        return pd.Series([self.get_regime(d) for d in dates], index=dates, name="regime")
    
    def filter_bull(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return only bull market periods."""
        if "regime" not in df.columns:
            df = self.add_regime(df)
        return df[df["regime"] == "bull"]
    
    def filter_bear(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return only bear market periods."""
        if "regime" not in df.columns:
            df = self.add_regime(df)
        return df[df["regime"] == "bear"]
    
    def filter_regime(self, df: pd.DataFrame, regime: Literal["bull", "bear"]) -> pd.DataFrame:
        """Return data for specific regime."""
        if regime == "bull":
            return self.filter_bull(df)
        elif regime == "bear":
            return self.filter_bear(df)
        else:
            raise ValueError(f"Invalid regime: {regime}. Must be 'bull' or 'bear'")
    
    # -------------------------------------------------------------------------
    # SUMMARY & STATS
    # -------------------------------------------------------------------------
    
    def summary(self) -> pd.DataFrame:
        """
        Get summary of all defined regimes.
        
        Returns:
            DataFrame with regime periods
        """
        rows = []
        for p in self._periods:
            days = (p["end"] - p["start"]).days
            rows.append({
                "name": p["name"],
                "type": p["type"],
                "start": p["start"].strftime("%Y-%m-%d"),
                "end": p["end"].strftime("%Y-%m-%d"),
                "days": days
            })
        
        return pd.DataFrame(rows)
    
    def stats(self, df: pd.DataFrame = None) -> dict:
        """
        Get regime statistics.
        
        Args:
            df: Optional DataFrame to calculate stats on
            
        Returns:
            Dict with bull/bear day counts and percentages
        """
        if df is not None:
            if "regime" not in df.columns:
                df = self.add_regime(df)
            
            bull_days = (df["regime"] == "bull").sum()
            bear_days = (df["regime"] == "bear").sum()
            undefined = df["regime"].isna().sum()
        else:
            bull_days = sum((p["end"] - p["start"]).days for p in self._periods if p["type"] == "bull")
            bear_days = sum((p["end"] - p["start"]).days for p in self._periods if p["type"] == "bear")
            undefined = 0
        
        total = bull_days + bear_days + undefined
        
        return {
            "bull_days": bull_days,
            "bear_days": bear_days,
            "undefined_days": undefined,
            "total_days": total,
            "bull_pct": bull_days / total * 100 if total > 0 else 0,
            "bear_pct": bear_days / total * 100 if total > 0 else 0,
        }
    
    def __repr__(self) -> str:
        current = self.current_regime()
        return f"RegimeFilter({len(self._periods)} periods, current={current['type']})"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_default_filter: Optional[RegimeFilter] = None

def _get_default_filter() -> RegimeFilter:
    """Get or create default filter instance."""
    global _default_filter
    if _default_filter is None:
        _default_filter = RegimeFilter()
    return _default_filter


def get_regime(dt: Union[str, datetime, date, pd.Timestamp]) -> Optional[str]:
    """
    Get regime type for a date.
    
    Args:
        dt: Date to check
        
    Returns:
        "bull", "bear", or None
    """
    return _get_default_filter().get_regime(dt)


def get_regime_name(dt: Union[str, datetime, date, pd.Timestamp]) -> Optional[str]:
    """Get regime name for a date."""
    return _get_default_filter().get_regime_name(dt)


def current_regime() -> str:
    """Get current regime type."""
    return _get_default_filter().current_regime()["type"]


def is_bull(dt: Union[str, datetime, date, pd.Timestamp] = None) -> bool:
    """Check if date (or now) is in bull market."""
    if dt is None:
        dt = pd.Timestamp.now(tz="UTC")
    return get_regime(dt) == "bull"


def is_bear(dt: Union[str, datetime, date, pd.Timestamp] = None) -> bool:
    """Check if date (or now) is in bear market."""
    if dt is None:
        dt = pd.Timestamp.now(tz="UTC")
    return get_regime(dt) == "bear"


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    
    rf = RegimeFilter()
    
    print("=" * 60)
    print("REGIME FILTER")
    print("=" * 60)
    
    # Summary
    print("\nDefined Regimes:")
    print(rf.summary().to_string(index=False))
    
    # Stats
    stats = rf.stats()
    print(f"\nTotal: {stats['bull_days']:,} bull days ({stats['bull_pct']:.1f}%), "
          f"{stats['bear_days']:,} bear days ({stats['bear_pct']:.1f}%)")
    
    # Current
    current = rf.current_regime()
    print(f"\nCurrent Regime: {current['type'].upper()} ({current['name']})")
    
    # Check specific date if provided
    if len(sys.argv) > 1:
        check_date = sys.argv[1]
        regime = rf.get_regime(check_date)
        name = rf.get_regime_name(check_date)
        print(f"\n{check_date}: {regime} ({name})")
