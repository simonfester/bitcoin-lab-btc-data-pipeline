"""
Momentum Filter Module
======================
Calculates price momentum to determine if market is trending up or down.

Usage:
    from src.momentum import MomentumFilter, get_momentum
    
    mf = MomentumFilter()
    
    # Get momentum for latest data
    momentum = mf.get_momentum(df)  # "up", "down", or "neutral"
    
    # Add momentum columns to DataFrame
    df = mf.add_momentum(df)
    
    # Combine with regime for full market state
    from src.regime import RegimeFilter
    rf = RegimeFilter()
    
    df = rf.add_regime(df)
    df = mf.add_momentum(df)
    # Now df has 'regime' and 'momentum' columns
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Literal, Union
from dataclasses import dataclass


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class MomentumConfig:
    """Configuration for momentum calculation."""
    # ROC (Rate of Change) periods
    roc_short: int = 7       # 7-day momentum
    roc_medium: int = 30     # 30-day momentum
    roc_long: int = 90       # 90-day momentum
    
    # Moving averages
    ma_fast: int = 20        # Fast MA period
    ma_slow: int = 50        # Slow MA period
    ma_trend: int = 200      # Trend MA period
    
    # Thresholds
    roc_threshold: float = 0.0      # ROC above this = up momentum
    neutral_band: float = 0.02      # ±2% considered neutral
    
    # Scoring weights
    weight_roc_short: float = 0.2
    weight_roc_medium: float = 0.3
    weight_roc_long: float = 0.2
    weight_ma_cross: float = 0.15
    weight_ma_trend: float = 0.15


DEFAULT_CONFIG = MomentumConfig()


# =============================================================================
# MOMENTUM FILTER CLASS
# =============================================================================

class MomentumFilter:
    """
    Calculate and classify price momentum.
    
    Combines multiple signals:
    - Rate of Change (ROC) at different timeframes
    - Moving average crossovers
    - Price vs trend MA
    """
    
    def __init__(self, config: Optional[MomentumConfig] = None):
        """
        Initialize momentum filter.
        
        Args:
            config: MomentumConfig with parameters (uses defaults if None)
        """
        self.config = config or DEFAULT_CONFIG
    
    # -------------------------------------------------------------------------
    # INDICATOR CALCULATIONS
    # -------------------------------------------------------------------------
    
    def calc_roc(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Rate of Change.
        
        ROC = (price - price_n_periods_ago) / price_n_periods_ago
        """
        return prices.pct_change(period)
    
    def calc_ma(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average."""
        return prices.rolling(period).mean()
    
    def calc_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return prices.ewm(span=period, adjust=False).mean()
    
    # -------------------------------------------------------------------------
    # MOMENTUM SCORING
    # -------------------------------------------------------------------------
    
    def calc_momentum_score(self, df: pd.DataFrame, price_col: str = "price") -> pd.Series:
        """
        Calculate composite momentum score from -1 (strong down) to +1 (strong up).
        
        Components:
        - Short-term ROC (7d)
        - Medium-term ROC (30d)
        - Long-term ROC (90d)
        - Fast/Slow MA crossover
        - Price vs 200 MA
        
        Returns:
            Series with momentum scores
        """
        prices = df[price_col]
        cfg = self.config
        
        scores = pd.DataFrame(index=df.index)
        
        # ROC scores (normalized to roughly -1 to +1 range)
        # Divide by typical volatility (~10% monthly)
        scores["roc_short"] = np.clip(self.calc_roc(prices, cfg.roc_short) / 0.05, -1, 1)
        scores["roc_medium"] = np.clip(self.calc_roc(prices, cfg.roc_medium) / 0.15, -1, 1)
        scores["roc_long"] = np.clip(self.calc_roc(prices, cfg.roc_long) / 0.30, -1, 1)
        
        # MA crossover score
        ma_fast = self.calc_ma(prices, cfg.ma_fast)
        ma_slow = self.calc_ma(prices, cfg.ma_slow)
        ma_diff = (ma_fast - ma_slow) / ma_slow
        scores["ma_cross"] = np.clip(ma_diff / 0.10, -1, 1)
        
        # Price vs trend MA
        ma_trend = self.calc_ma(prices, cfg.ma_trend)
        trend_diff = (prices - ma_trend) / ma_trend
        scores["ma_trend"] = np.clip(trend_diff / 0.20, -1, 1)
        
        # Weighted composite score
        composite = (
            scores["roc_short"] * cfg.weight_roc_short +
            scores["roc_medium"] * cfg.weight_roc_medium +
            scores["roc_long"] * cfg.weight_roc_long +
            scores["ma_cross"] * cfg.weight_ma_cross +
            scores["ma_trend"] * cfg.weight_ma_trend
        )
        
        return composite
    
    def classify_momentum(self, score: float) -> str:
        """
        Classify momentum score into category.
        
        Args:
            score: Momentum score from -1 to +1
            
        Returns:
            "up", "down", or "neutral"
        """
        if pd.isna(score):
            return "neutral"
        
        if score > self.config.neutral_band:
            return "up"
        elif score < -self.config.neutral_band:
            return "down"
        else:
            return "neutral"
    
    def classify_momentum_detailed(self, score: float) -> str:
        """
        Classify momentum with more granularity.
        
        Returns:
            "strong_up", "up", "neutral", "down", "strong_down"
        """
        if pd.isna(score):
            return "neutral"
        
        if score > 0.5:
            return "strong_up"
        elif score > self.config.neutral_band:
            return "up"
        elif score < -0.5:
            return "strong_down"
        elif score < -self.config.neutral_band:
            return "down"
        else:
            return "neutral"
    
    # -------------------------------------------------------------------------
    # CORE API
    # -------------------------------------------------------------------------
    
    def get_momentum(
        self, 
        df: pd.DataFrame, 
        price_col: str = "price",
        date: Optional[Union[str, pd.Timestamp]] = None
    ) -> str:
        """
        Get momentum classification for a specific date or latest.
        
        Args:
            df: DataFrame with price data
            price_col: Column name for prices
            date: Specific date (default: latest)
            
        Returns:
            "up", "down", or "neutral"
        """
        scores = self.calc_momentum_score(df, price_col)
        
        if date is not None:
            if isinstance(date, str):
                date = pd.Timestamp(date)
            if date.tz is None:
                date = date.tz_localize("UTC")
            score = scores.loc[date] if date in scores.index else np.nan
        else:
            score = scores.iloc[-1]
        
        return self.classify_momentum(score)
    
    def get_momentum_score(
        self, 
        df: pd.DataFrame, 
        price_col: str = "price",
        date: Optional[Union[str, pd.Timestamp]] = None
    ) -> float:
        """
        Get raw momentum score for a specific date or latest.
        
        Returns:
            Score from -1 (strong down) to +1 (strong up)
        """
        scores = self.calc_momentum_score(df, price_col)
        
        if date is not None:
            if isinstance(date, str):
                date = pd.Timestamp(date)
            if date.tz is None:
                date = date.tz_localize("UTC")
            return scores.loc[date] if date in scores.index else np.nan
        else:
            return scores.iloc[-1]
    
    # -------------------------------------------------------------------------
    # DATAFRAME OPERATIONS
    # -------------------------------------------------------------------------
    
    def add_momentum(
        self, 
        df: pd.DataFrame, 
        price_col: str = "price",
        detailed: bool = False
    ) -> pd.DataFrame:
        """
        Add momentum columns to DataFrame.
        
        Args:
            df: DataFrame with price data
            price_col: Column name for prices
            detailed: If True, use 5-level classification
            
        Returns:
            DataFrame with added columns:
            - momentum_score: Raw score (-1 to +1)
            - momentum: Classification (up/down/neutral)
        """
        df = df.copy()
        
        df["momentum_score"] = self.calc_momentum_score(df, price_col)
        
        if detailed:
            df["momentum"] = df["momentum_score"].apply(self.classify_momentum_detailed)
        else:
            df["momentum"] = df["momentum_score"].apply(self.classify_momentum)
        
        return df
    
    def add_indicators(self, df: pd.DataFrame, price_col: str = "price") -> pd.DataFrame:
        """
        Add all momentum indicators to DataFrame.
        
        Adds: ROC columns, MA columns, momentum score, momentum classification
        """
        df = df.copy()
        prices = df[price_col]
        cfg = self.config
        
        # ROC
        df["roc_7d"] = self.calc_roc(prices, cfg.roc_short)
        df["roc_30d"] = self.calc_roc(prices, cfg.roc_medium)
        df["roc_90d"] = self.calc_roc(prices, cfg.roc_long)
        
        # Moving averages
        df["ma_20"] = self.calc_ma(prices, cfg.ma_fast)
        df["ma_50"] = self.calc_ma(prices, cfg.ma_slow)
        df["ma_200"] = self.calc_ma(prices, cfg.ma_trend)
        
        # Derived
        df["price_vs_ma200"] = (prices - df["ma_200"]) / df["ma_200"]
        df["ma_20_vs_50"] = (df["ma_20"] - df["ma_50"]) / df["ma_50"]
        
        # Score and classification
        df["momentum_score"] = self.calc_momentum_score(df, price_col)
        df["momentum"] = df["momentum_score"].apply(self.classify_momentum)
        
        return df
    
    def filter_up(self, df: pd.DataFrame, price_col: str = "price") -> pd.DataFrame:
        """Return only periods with up momentum."""
        if "momentum" not in df.columns:
            df = self.add_momentum(df, price_col)
        return df[df["momentum"] == "up"]
    
    def filter_down(self, df: pd.DataFrame, price_col: str = "price") -> pd.DataFrame:
        """Return only periods with down momentum."""
        if "momentum" not in df.columns:
            df = self.add_momentum(df, price_col)
        return df[df["momentum"] == "down"]
    
    # -------------------------------------------------------------------------
    # ANALYSIS
    # -------------------------------------------------------------------------
    
    def stats(self, df: pd.DataFrame, price_col: str = "price") -> dict:
        """
        Get momentum statistics for the dataset.
        """
        if "momentum" not in df.columns:
            df = self.add_momentum(df, price_col)
        
        total = len(df)
        up_days = (df["momentum"] == "up").sum()
        down_days = (df["momentum"] == "down").sum()
        neutral_days = (df["momentum"] == "neutral").sum()
        
        return {
            "up_days": up_days,
            "down_days": down_days,
            "neutral_days": neutral_days,
            "total_days": total,
            "up_pct": up_days / total * 100 if total > 0 else 0,
            "down_pct": down_days / total * 100 if total > 0 else 0,
            "neutral_pct": neutral_days / total * 100 if total > 0 else 0,
            "current_score": df["momentum_score"].iloc[-1],
            "current_momentum": df["momentum"].iloc[-1],
        }
    
    def __repr__(self) -> str:
        return f"MomentumFilter(neutral_band={self.config.neutral_band})"


# =============================================================================
# COMBINED MARKET STATE
# =============================================================================

@dataclass
class MarketState:
    """Complete market state combining regime and momentum."""
    regime: str           # "bull" or "bear"
    regime_name: str      # e.g., "2020-2021 Bull Run"
    momentum: str         # "up", "down", "neutral"
    momentum_score: float # -1 to +1
    
    @property
    def state(self) -> str:
        """Combined state string."""
        return f"{self.regime}_{self.momentum}"
    
    @property
    def signal(self) -> str:
        """Trading signal interpretation."""
        signals = {
            ("bull", "up"): "strong_trend",      # Ride it
            ("bull", "down"): "buy_dip",         # Opportunity
            ("bull", "neutral"): "hold",         # Wait
            ("bear", "up"): "bear_rally",        # Caution
            ("bear", "down"): "capitulation",    # Stay out
            ("bear", "neutral"): "wait",         # Wait
        }
        return signals.get((self.regime, self.momentum), "unknown")


def get_market_state(
    df: pd.DataFrame,
    date: Optional[Union[str, pd.Timestamp]] = None,
    price_col: str = "price"
) -> MarketState:
    """
    Get complete market state for a date.
    
    Args:
        df: DataFrame with price data
        date: Date to check (default: latest)
        price_col: Column name for prices
        
    Returns:
        MarketState with regime and momentum
    """
    from src.regime import RegimeFilter
    
    rf = RegimeFilter()
    mf = MomentumFilter()
    
    if date is None:
        date = df.index[-1]
    
    if isinstance(date, str):
        date = pd.Timestamp(date, tz="UTC")
    
    regime = rf.get_regime(date) or "unknown"
    regime_name = rf.get_regime_name(date) or "unknown"
    momentum = mf.get_momentum(df, price_col, date)
    momentum_score = mf.get_momentum_score(df, price_col, date)
    
    return MarketState(
        regime=regime,
        regime_name=regime_name,
        momentum=momentum,
        momentum_score=momentum_score
    )


def add_market_state(df: pd.DataFrame, price_col: str = "price") -> pd.DataFrame:
    """
    Add both regime and momentum columns to DataFrame.
    
    Adds:
    - regime
    - regime_name
    - momentum_score
    - momentum
    - market_state (combined)
    """
    from src.regime import RegimeFilter
    
    rf = RegimeFilter()
    mf = MomentumFilter()
    
    df = rf.add_regime(df)
    df = mf.add_momentum(df, price_col)
    
    # Combined state
    df["market_state"] = df["regime"] + "_" + df["momentum"]
    
    return df


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_default_filter: Optional[MomentumFilter] = None

def _get_default_filter() -> MomentumFilter:
    global _default_filter
    if _default_filter is None:
        _default_filter = MomentumFilter()
    return _default_filter


def get_momentum(df: pd.DataFrame, price_col: str = "price") -> str:
    """Get current momentum classification."""
    return _get_default_filter().get_momentum(df, price_col)


def get_momentum_score(df: pd.DataFrame, price_col: str = "price") -> float:
    """Get current momentum score."""
    return _get_default_filter().get_momentum_score(df, price_col)


def is_up(df: pd.DataFrame, price_col: str = "price") -> bool:
    """Check if momentum is up."""
    return get_momentum(df, price_col) == "up"


def is_down(df: pd.DataFrame, price_col: str = "price") -> bool:
    """Check if momentum is down."""
    return get_momentum(df, price_col) == "down"


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Load price data
    project_root = Path(__file__).parent.parent
    price_path = project_root / "data" / "raw" / "price.parquet"
    
    if not price_path.exists():
        print(f"Price data not found at {price_path}")
        print("Run 'python run.py sync' first to download data.")
        sys.exit(1)
    
    df = pd.read_parquet(price_path)
    df = df.set_index("time")
    df = df.rename(columns={"value": "price"})
    
    mf = MomentumFilter()
    df = mf.add_indicators(df)
    
    print("=" * 60)
    print("MOMENTUM FILTER")
    print("=" * 60)
    
    # Current state
    latest = df.iloc[-1]
    print(f"\nCurrent Date: {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"Price: ${latest['price']:,.0f}")
    print(f"\nMomentum Score: {latest['momentum_score']:+.3f}")
    print(f"Momentum: {latest['momentum'].upper()}")
    
    print(f"\nIndicators:")
    print(f"  ROC 7d:  {latest['roc_7d']*100:+.1f}%")
    print(f"  ROC 30d: {latest['roc_30d']*100:+.1f}%")
    print(f"  ROC 90d: {latest['roc_90d']*100:+.1f}%")
    print(f"  Price vs MA200: {latest['price_vs_ma200']*100:+.1f}%")
    print(f"  MA20 vs MA50: {latest['ma_20_vs_50']*100:+.1f}%")
    
    # Stats
    stats = mf.stats(df)
    print(f"\nHistorical Distribution:")
    print(f"  Up:      {stats['up_days']:,} days ({stats['up_pct']:.1f}%)")
    print(f"  Down:    {stats['down_days']:,} days ({stats['down_pct']:.1f}%)")
    print(f"  Neutral: {stats['neutral_days']:,} days ({stats['neutral_pct']:.1f}%)")
    
    # Combined with regime
    try:
        from src.regime import RegimeFilter
        rf = RegimeFilter()
        current_regime = rf.current_regime()
        
        print(f"\n" + "=" * 60)
        print("COMBINED MARKET STATE")
        print("=" * 60)
        print(f"\nRegime: {current_regime['type'].upper()} ({current_regime['name']})")
        print(f"Momentum: {latest['momentum'].upper()}")
        
        state = f"{current_regime['type']}_{latest['momentum']}"
        signals = {
            "bull_up": "🚀 Strong trend - ride it",
            "bull_down": "🛒 Pullback - buy the dip",
            "bull_neutral": "⏸️  Consolidation - hold",
            "bear_up": "⚠️  Bear rally - be cautious",
            "bear_down": "🔴 Capitulation - stay out",
            "bear_neutral": "⏸️  Wait for clarity",
        }
        print(f"\nMarket State: {state.upper()}")
        print(f"Signal: {signals.get(state, 'Unknown')}")
        
    except ImportError:
        pass
