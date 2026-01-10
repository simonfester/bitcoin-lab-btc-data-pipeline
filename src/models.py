"""
Shared Models
=============
Dataclasses used across all pipeline modules.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
import json


@dataclass
class SignalSpec:
    """
    Signal specification - the common format passed between modules.
    
    Created by: screener
    Used by: backtester, walk_forward, paper_trader, live_trader
    """
    metric: str
    direction: str              # "above" or "below"
    threshold: float
    regime: Optional[str] = None  # "bull", "bear", or None for all
    
    # Optional name override
    name: Optional[str] = None
    
    # Metadata added by each stage
    percentile: Optional[float] = None
    
    # Screener results
    screen_fwd_return: Optional[float] = None
    screen_win_rate: Optional[float] = None
    screen_n_signals: Optional[int] = None
    
    # Backtest results
    backtest_sharpe: Optional[float] = None
    backtest_total_return: Optional[float] = None
    backtest_max_dd: Optional[float] = None
    backtest_win_rate: Optional[float] = None
    
    # Walk-forward results
    wf_oos_sharpe: Optional[float] = None
    wf_oos_return: Optional[float] = None
    wf_consistency: Optional[float] = None  # % of periods profitable
    wf_degradation: Optional[float] = None  # IS vs OOS performance drop
    
    # Approval status
    approved: bool = False
    approval_date: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    def __post_init__(self):
        if self.name is None:
            symbol = ">" if self.direction == "above" else "<"
            regime_str = f"_{self.regime}" if self.regime else ""
            self.name = f"{self.metric}{symbol}{self.threshold:.3f}{regime_str}"
    
    @property
    def condition(self) -> str:
        symbol = ">" if self.direction == "above" else "<"
        return f"{self.metric} {symbol} {self.threshold:.3f}"
    
    def is_active(self, row: pd.Series, current_regime: Optional[str] = None) -> bool:
        """Check if signal is active for a given data row."""
        if self.metric not in row.index:
            return False
        
        if self.regime is not None and current_regime != self.regime:
            return False
        
        value = row[self.metric]
        if pd.isna(value):
            return False
        
        if self.direction == "above":
            return value > self.threshold
        else:
            return value < self.threshold
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> 'SignalSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_json(cls, s: str) -> 'SignalSpec':
        return cls.from_dict(json.loads(s))


@dataclass
class WalkForwardFold:
    """Results from a single walk-forward fold."""
    fold_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    
    # In-sample (training) metrics
    is_n_trades: int = 0
    is_total_return: float = 0.0
    is_sharpe: float = 0.0
    is_win_rate: float = 0.0
    is_max_dd: float = 0.0
    
    # Out-of-sample (test) metrics
    oos_n_trades: int = 0
    oos_total_return: float = 0.0
    oos_sharpe: float = 0.0
    oos_win_rate: float = 0.0
    oos_max_dd: float = 0.0
    
    @property
    def degradation(self) -> float:
        """Performance degradation from IS to OOS."""
        if self.is_sharpe == 0:
            return 0.0
        return (self.is_sharpe - self.oos_sharpe) / abs(self.is_sharpe)


@dataclass 
class WalkForwardResult:
    """Aggregated walk-forward validation results."""
    signal: SignalSpec
    method: str  # "anchored", "rolling", "cycle"
    n_folds: int
    folds: List[WalkForwardFold]
    
    # Aggregated OOS metrics (THE REAL PERFORMANCE)
    oos_total_return: float = 0.0
    oos_avg_return: float = 0.0
    oos_sharpe: float = 0.0
    oos_win_rate: float = 0.0
    oos_max_dd: float = 0.0
    oos_n_trades: int = 0
    oos_avg_hold_days: float = 0.0
    
    # Aggregated IS metrics (for comparison)
    is_avg_return: float = 0.0
    is_sharpe: float = 0.0
    
    # Quality metrics
    consistency: float = 0.0      # % of folds profitable OOS
    avg_degradation: float = 0.0  # Average IS→OOS performance drop
    
    # Approval
    passed: bool = False
    failure_reasons: List[str] = field(default_factory=list)
    
    # Extra data (trades, not serialized)
    all_oos_trades: List[Dict] = field(default_factory=list)
    
    def summary(self) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append(f"WALK-FORWARD RESULTS: {self.signal.name}")
        lines.append("=" * 70)
        lines.append(f"Method: {self.method}, Folds: {self.n_folds}")
        lines.append(f"\n--- Out-of-Sample (REAL) Performance ---")
        lines.append(f"Total Return:  {self.oos_total_return:>+8.1%}")
        lines.append(f"Avg Return:    {self.oos_avg_return:>+8.1%}")
        lines.append(f"Sharpe Ratio:  {self.oos_sharpe:>8.2f}")
        lines.append(f"Win Rate:      {self.oos_win_rate:>8.1%}")
        lines.append(f"Max Drawdown:  {self.oos_max_dd:>8.1%}")
        lines.append(f"Total Trades:  {self.oos_n_trades:>8}")
        lines.append(f"Avg Hold Days: {self.oos_avg_hold_days:>8.1f}")
        lines.append(f"\n--- Validation Metrics ---")
        lines.append(f"Consistency:   {self.consistency:>8.1%} ({int(self.consistency * self.n_folds)}/{self.n_folds} profitable)")
        lines.append(f"Degradation:   {self.avg_degradation:>8.1%} (IS→OOS drop)")
        lines.append(f"IS Sharpe:     {self.is_sharpe:>8.2f} (for comparison)")
        lines.append(f"\n--- Verdict ---")
        if self.passed:
            lines.append("✅ PASSED - Signal approved for paper trading")
        else:
            lines.append("❌ FAILED")
            for reason in self.failure_reasons:
                lines.append(f"   • {reason}")
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        return {
            'signal_name': self.signal.name,
            'signal': self.signal.to_dict(),
            'method': self.method,
            'n_folds': self.n_folds,
            'oos_total_return': self.oos_total_return,
            'oos_avg_return': self.oos_avg_return,
            'oos_sharpe': self.oos_sharpe,
            'oos_win_rate': self.oos_win_rate,
            'oos_max_dd': self.oos_max_dd,
            'oos_n_trades': self.oos_n_trades,
            'oos_avg_hold_days': self.oos_avg_hold_days,
            'is_sharpe': self.is_sharpe,
            'consistency': self.consistency,
            'avg_degradation': self.avg_degradation,
            'passed': self.passed,
            'failure_reasons': self.failure_reasons,
        }


@dataclass
class ApprovalCriteria:
    """Criteria for approving signals after walk-forward validation."""
    min_oos_sharpe: float = 0.3
    min_consistency: float = 0.6      # 60% of folds profitable
    max_degradation: float = 0.5      # Max 50% IS→OOS drop
    min_oos_win_rate: float = 0.45
    max_oos_drawdown: float = 0.4     # Max 40% drawdown
    min_n_trades: int = 10            # Min trades per fold
    
    def evaluate(self, result: WalkForwardResult) -> tuple[bool, List[str]]:
        """Evaluate if result passes criteria. Returns (passed, reasons)."""
        failures = []
        
        if result.oos_sharpe < self.min_oos_sharpe:
            failures.append(f"OOS Sharpe {result.oos_sharpe:.2f} < {self.min_oos_sharpe}")
        
        if result.consistency < self.min_consistency:
            failures.append(f"Consistency {result.consistency:.1%} < {self.min_consistency:.0%}")
        
        if result.avg_degradation > self.max_degradation:
            failures.append(f"Degradation {result.avg_degradation:.1%} > {self.max_degradation:.0%}")
        
        if result.oos_win_rate < self.min_oos_win_rate:
            failures.append(f"OOS Win Rate {result.oos_win_rate:.1%} < {self.min_oos_win_rate:.0%}")
        
        if result.oos_max_dd < -self.max_oos_drawdown:
            failures.append(f"OOS Max DD {result.oos_max_dd:.1%} > {self.max_oos_drawdown:.0%}")
        
        passed = len(failures) == 0
        return passed, failures
