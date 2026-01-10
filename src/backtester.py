"""
Backtester Module (v2)
======================
Backtest threshold-based signals with proper exit strategies.

Exit Modes:
- SIGNAL_EXIT: Exit when signal condition no longer true
- REGIME_EXIT: Exit when market regime changes
- COMBINED: Exit on signal OR regime change (recommended)
- FIXED_HOLD: Exit after N days (legacy, not recommended)

Usage:
    from src.backtester import Backtester, Signal, ExitMode
    
    signal = Signal(
        metric='mvrv',
        direction='below',
        threshold=1.2,
        regime='bull'
    )
    
    bt = Backtester(exit_mode=ExitMode.COMBINED)
    result = bt.run(df, signal)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Literal, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

from src.config import BULL_MARKETS, BEAR_MARKETS, RAW_DATA_DIR, get_regime_for_date


# =============================================================================
# ENUMS
# =============================================================================

class ExitMode(Enum):
    """Exit strategy modes."""
    SIGNAL_EXIT = "signal_exit"     # Exit when signal condition ends
    REGIME_EXIT = "regime_exit"     # Exit when regime changes
    COMBINED = "combined"           # Exit on signal OR regime change
    FIXED_HOLD = "fixed_hold"       # Exit after N days (legacy)


class SignalDirection(Enum):
    ABOVE = "above"
    BELOW = "below"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Signal:
    """Signal definition for backtesting."""
    metric: str
    direction: str              # "above" or "below"
    threshold: float
    regime: Optional[str] = None  # "bull", "bear", or None for all
    name: Optional[str] = None
    
    def __post_init__(self):
        if self.name is None:
            symbol = ">" if self.direction == "above" else "<"
            regime_str = f"_{self.regime}" if self.regime else ""
            self.name = f"{self.metric}{symbol}{self.threshold:.3f}{regime_str}"
    
    @property
    def condition(self) -> str:
        symbol = ">" if self.direction == "above" else "<"
        return f"{self.metric} {symbol} {self.threshold:.3f}"
    
    def is_active(self, value: float) -> bool:
        """Check if signal condition is met."""
        if pd.isna(value):
            return False
        
        if self.direction == "above":
            return value > self.threshold
        else:
            return value < self.threshold


@dataclass
class Trade:
    """Record of a single trade."""
    entry_date: pd.Timestamp
    entry_price: float
    entry_metric_value: float
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_metric_value: Optional[float] = None
    exit_reason: Optional[str] = None  # "signal_exit", "regime_exit", "stop_loss", etc.
    
    @property
    def is_open(self) -> bool:
        return self.exit_date is None
    
    @property
    def return_pct(self) -> Optional[float]:
        if self.exit_price is None:
            return None
        return (self.exit_price - self.entry_price) / self.entry_price
    
    @property
    def duration_days(self) -> Optional[int]:
        if self.exit_date is None:
            return None
        return (self.exit_date - self.entry_date).days
    
    def to_dict(self) -> dict:
        return {
            'entry_date': str(self.entry_date.date()) if self.entry_date else None,
            'entry_price': self.entry_price,
            'entry_metric_value': self.entry_metric_value,
            'exit_date': str(self.exit_date.date()) if self.exit_date else None,
            'exit_price': self.exit_price,
            'exit_metric_value': self.exit_metric_value,
            'exit_reason': self.exit_reason,
            'return_pct': self.return_pct,
            'duration_days': self.duration_days,
        }


@dataclass
class BacktestConfig:
    """Configuration for backtest parameters."""
    # Exit mode
    exit_mode: ExitMode = ExitMode.COMBINED
    
    # Fixed hold (only used if exit_mode == FIXED_HOLD)
    hold_days: Optional[int] = 30
    
    # Risk management
    stop_loss: Optional[float] = None       # e.g., 0.15 = 15% stop
    take_profit: Optional[float] = None     # e.g., 0.50 = 50% take profit
    trailing_stop: Optional[float] = None   # e.g., 0.20 = 20% trailing stop
    max_hold_days: Optional[int] = None     # Maximum days to hold (safety)
    
    # Entry rules
    reentry_delay: int = 1                  # Days to wait before re-entering
    
    # Costs
    commission: float = 0.001               # 0.1% per trade
    slippage: float = 0.001                 # 0.1% slippage


@dataclass 
class BacktestResult:
    """Results from a backtest run."""
    signal: Signal
    config: BacktestConfig
    trades: List[Trade]
    equity_curve: pd.Series
    
    # Performance metrics
    total_return: float = 0.0
    cagr: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_hold_days: float = 0.0
    n_trades: int = 0
    
    # Exit analysis
    exits_by_reason: Dict[str, int] = field(default_factory=dict)
    
    def summary(self) -> str:
        """Generate text summary."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"BACKTEST: {self.signal.name}")
        lines.append("=" * 60)
        lines.append(f"\nSignal: {self.signal.condition}")
        lines.append(f"Regime: {self.signal.regime or 'all'}")
        lines.append(f"Exit Mode: {self.config.exit_mode.value}")
        
        lines.append(f"\n--- Performance ---")
        lines.append(f"Total Return:    {self.total_return:>+8.1%}")
        lines.append(f"CAGR:            {self.cagr:>+8.1%}")
        lines.append(f"Sharpe Ratio:    {self.sharpe_ratio:>8.2f}")
        lines.append(f"Max Drawdown:    {self.max_drawdown:>8.1%}")
        
        lines.append(f"\n--- Trades ---")
        lines.append(f"Total Trades:    {self.n_trades:>8}")
        lines.append(f"Win Rate:        {self.win_rate:>8.1%}")
        lines.append(f"Profit Factor:   {self.profit_factor:>8.2f}")
        lines.append(f"Avg Trade:       {self.avg_trade_return:>+8.1%}")
        lines.append(f"Avg Hold Days:   {self.avg_hold_days:>8.1f}")
        
        if self.exits_by_reason:
            lines.append(f"\n--- Exit Reasons ---")
            for reason, count in sorted(self.exits_by_reason.items()):
                pct = count / self.n_trades * 100 if self.n_trades > 0 else 0
                lines.append(f"  {reason:<20} {count:>4} ({pct:.0f}%)")
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        return {
            'signal_name': self.signal.name,
            'metric': self.signal.metric,
            'direction': self.signal.direction,
            'threshold': self.signal.threshold,
            'regime': self.signal.regime,
            'exit_mode': self.config.exit_mode.value,
            'n_trades': self.n_trades,
            'total_return': self.total_return,
            'cagr': self.cagr,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'avg_trade_return': self.avg_trade_return,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'avg_hold_days': self.avg_hold_days,
            'exits_by_reason': self.exits_by_reason,
        }
    
    def get_trades_df(self) -> pd.DataFrame:
        """Get trades as DataFrame."""
        return pd.DataFrame([t.to_dict() for t in self.trades])


# =============================================================================
# REGIME HELPERS
# =============================================================================

REGIMES_CONFIG = []
for r in BULL_MARKETS:
    REGIMES_CONFIG.append({"type": "bull", **r})
for r in BEAR_MARKETS:
    REGIMES_CONFIG.append({"type": "bear", **r})


def get_regime(date: pd.Timestamp) -> Optional[str]:
    """Get regime for a date."""
    if date.tz is None:
        date = date.tz_localize("UTC")
    
    for r in REGIMES_CONFIG:
        start = pd.Timestamp(r["start"], tz="UTC")
        end = pd.Timestamp(r["end"], tz="UTC")
        if start <= date < end:
            return r["type"]
    
    return None


def add_regime_column(df: pd.DataFrame) -> pd.DataFrame:
    """Add regime column to DataFrame."""
    if 'regime' in df.columns:
        return df
    
    df = df.copy()
    df['regime'] = df.index.map(get_regime)
    return df


# =============================================================================
# BACKTESTER CLASS
# =============================================================================

class Backtester:
    """
    Backtest threshold-based signals with proper exit strategies.
    """
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
    
    def run(
        self,
        df: pd.DataFrame,
        signal: Signal,
        price_col: str = "price",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> BacktestResult:
        """
        Run backtest for a signal.
        
        Args:
            df: DataFrame with price and metric data
            signal: Signal to test
            price_col: Price column name
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            BacktestResult with metrics and trades
        """
        # Prepare data
        df = add_regime_column(df)
        
        if start_date:
            df = df[df.index >= pd.Timestamp(start_date, tz="UTC")]
        if end_date:
            df = df[df.index <= pd.Timestamp(end_date, tz="UTC")]
        
        if signal.metric not in df.columns:
            raise ValueError(f"Metric '{signal.metric}' not found in data")
        
        if price_col not in df.columns:
            raise ValueError(f"Price column '{price_col}' not found")
        
        # Run simulation
        trades, equity = self._simulate(df, signal, price_col)
        
        # Build equity curve
        equity_curve = pd.Series(equity, index=df.index[:len(equity)], name='equity')
        
        # Calculate metrics
        return self._calculate_metrics(signal, trades, equity_curve)
    
    def _simulate(
        self,
        df: pd.DataFrame,
        signal: Signal,
        price_col: str
    ) -> tuple[List[Trade], List[float]]:
        """Run the backtest simulation."""
        
        trades: List[Trade] = []
        current_trade: Optional[Trade] = None
        
        equity = [1.0]
        position = False
        entry_price = 0.0
        entry_regime = None
        highest_since_entry = 0.0
        days_since_exit = self.config.reentry_delay + 1
        days_in_trade = 0
        
        cfg = self.config
        
        for i, (date, row) in enumerate(df.iterrows()):
            price = row[price_col]
            metric_value = row[signal.metric]
            regime = row.get('regime')
            
            if pd.isna(price):
                equity.append(equity[-1])
                continue
            
            # ─────────────────────────────────────────────────────────────
            # CHECK EXIT CONDITIONS (if in position)
            # ─────────────────────────────────────────────────────────────
            if position and current_trade is not None:
                exit_reason = None
                days_in_trade += 1
                highest_since_entry = max(highest_since_entry, price)
                
                # 1. Signal exit: metric condition no longer true
                if cfg.exit_mode in [ExitMode.SIGNAL_EXIT, ExitMode.COMBINED]:
                    if not signal.is_active(metric_value):
                        exit_reason = "signal_exit"
                
                # 2. Regime exit: regime changed from entry regime
                if cfg.exit_mode in [ExitMode.REGIME_EXIT, ExitMode.COMBINED]:
                    if signal.regime is not None and regime != signal.regime:
                        exit_reason = "regime_exit"
                
                # 3. Fixed hold period (legacy mode)
                if cfg.exit_mode == ExitMode.FIXED_HOLD:
                    if cfg.hold_days and days_in_trade >= cfg.hold_days:
                        exit_reason = "hold_period"
                
                # 4. Stop loss
                if cfg.stop_loss is not None:
                    pnl = (price - entry_price) / entry_price
                    if pnl <= -cfg.stop_loss:
                        exit_reason = "stop_loss"
                
                # 5. Take profit
                if cfg.take_profit is not None:
                    pnl = (price - entry_price) / entry_price
                    if pnl >= cfg.take_profit:
                        exit_reason = "take_profit"
                
                # 6. Trailing stop
                if cfg.trailing_stop is not None:
                    drawdown = (highest_since_entry - price) / highest_since_entry
                    if drawdown >= cfg.trailing_stop:
                        exit_reason = "trailing_stop"
                
                # 7. Max hold days (safety)
                if cfg.max_hold_days is not None:
                    if days_in_trade >= cfg.max_hold_days:
                        exit_reason = "max_hold"
                
                # Execute exit
                if exit_reason is not None:
                    exit_price = price * (1 - cfg.slippage - cfg.commission)
                    
                    current_trade.exit_date = date
                    current_trade.exit_price = exit_price
                    current_trade.exit_metric_value = metric_value
                    current_trade.exit_reason = exit_reason
                    trades.append(current_trade)
                    
                    # Update equity
                    trade_return = (exit_price - entry_price) / entry_price
                    equity.append(equity[-1] * (1 + trade_return))
                    
                    position = False
                    current_trade = None
                    days_since_exit = 0
                    days_in_trade = 0
                    continue
                
                # Still in position - mark to market
                current_pnl = (price - entry_price) / entry_price
                equity.append(equity[-2] * (1 + current_pnl) if len(equity) > 1 else 1 + current_pnl)
                continue
            
            # ─────────────────────────────────────────────────────────────
            # CHECK ENTRY CONDITIONS (if not in position)
            # ─────────────────────────────────────────────────────────────
            days_since_exit += 1
            
            # Check if we can enter
            can_enter = (
                days_since_exit > cfg.reentry_delay and
                signal.is_active(metric_value) and
                (signal.regime is None or regime == signal.regime)
            )
            
            if can_enter:
                entry_price = price * (1 + cfg.slippage + cfg.commission)
                highest_since_entry = price
                entry_regime = regime
                position = True
                days_in_trade = 0
                
                current_trade = Trade(
                    entry_date=date,
                    entry_price=entry_price,
                    entry_metric_value=metric_value,
                )
            
            equity.append(equity[-1])
        
        # Close any open trade at end of data
        if current_trade is not None:
            last_price = df[price_col].iloc[-1]
            exit_price = last_price * (1 - cfg.slippage - cfg.commission)
            
            current_trade.exit_date = df.index[-1]
            current_trade.exit_price = exit_price
            current_trade.exit_metric_value = df[signal.metric].iloc[-1]
            current_trade.exit_reason = "end_of_data"
            trades.append(current_trade)
        
        return trades, equity
    
    def _calculate_metrics(
        self,
        signal: Signal,
        trades: List[Trade],
        equity_curve: pd.Series
    ) -> BacktestResult:
        """Calculate performance metrics."""
        
        n_trades = len(trades)
        
        # Total return
        total_return = equity_curve.iloc[-1] / equity_curve.iloc[0] - 1 if len(equity_curve) > 0 else 0
        
        # CAGR
        if len(equity_curve) > 1:
            years = (equity_curve.index[-1] - equity_curve.index[0]).days / 365.25
            if years > 0 and equity_curve.iloc[-1] > 0:
                cagr = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1 / years) - 1
            else:
                cagr = 0.0
        else:
            cagr = 0.0
        
        # Daily returns for Sharpe
        daily_returns = equity_curve.pct_change().dropna()
        
        if len(daily_returns) > 0 and daily_returns.std() > 0:
            sharpe_ratio = daily_returns.mean() / daily_returns.std() * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
        
        # Sortino
        downside = daily_returns[daily_returns < 0]
        if len(downside) > 0 and downside.std() > 0:
            sortino_ratio = daily_returns.mean() / downside.std() * np.sqrt(252)
        else:
            sortino_ratio = 0.0
        
        # Max drawdown
        rolling_max = equity_curve.cummax()
        drawdowns = (equity_curve - rolling_max) / rolling_max
        max_drawdown = drawdowns.min() if len(drawdowns) > 0 else 0.0
        
        # Trade statistics
        if n_trades > 0:
            returns = [t.return_pct for t in trades if t.return_pct is not None]
            wins = [r for r in returns if r > 0]
            losses = [r for r in returns if r <= 0]
            
            win_rate = len(wins) / len(returns) if returns else 0.0
            avg_trade_return = np.mean(returns) if returns else 0.0
            avg_win = np.mean(wins) if wins else 0.0
            avg_loss = np.mean(losses) if losses else 0.0
            
            gross_profit = sum(wins) if wins else 0.0
            gross_loss = abs(sum(losses)) if losses else 0.0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
            
            durations = [t.duration_days for t in trades if t.duration_days is not None]
            avg_hold_days = np.mean(durations) if durations else 0.0
            
            # Exit reasons
            exits_by_reason = {}
            for t in trades:
                reason = t.exit_reason or "unknown"
                exits_by_reason[reason] = exits_by_reason.get(reason, 0) + 1
        else:
            win_rate = 0.0
            avg_trade_return = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            profit_factor = 0.0
            avg_hold_days = 0.0
            exits_by_reason = {}
        
        return BacktestResult(
            signal=signal,
            config=self.config,
            trades=trades,
            equity_curve=equity_curve,
            total_return=total_return,
            cagr=cagr,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade_return=avg_trade_return,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_hold_days=avg_hold_days,
            n_trades=n_trades,
            exits_by_reason=exits_by_reason,
        )
    
    # -------------------------------------------------------------------------
    # BATCH TESTING
    # -------------------------------------------------------------------------
    
    def batch_test(
        self,
        df: pd.DataFrame,
        signals: List[Signal],
        price_col: str = "price"
    ) -> pd.DataFrame:
        """Test multiple signals."""
        results = []
        
        for signal in signals:
            try:
                result = self.run(df, signal, price_col)
                results.append(result.to_dict())
            except Exception as e:
                print(f"Error testing {signal.name}: {e}")
        
        return pd.DataFrame(results)
    
    def compare_exit_modes(
        self,
        df: pd.DataFrame,
        signal: Signal,
        price_col: str = "price"
    ) -> pd.DataFrame:
        """Compare different exit modes for a signal."""
        results = []
        
        for mode in ExitMode:
            config = BacktestConfig(exit_mode=mode, hold_days=30)
            bt = Backtester(config)
            
            try:
                result = bt.run(df, signal, price_col)
                result_dict = result.to_dict()
                result_dict['exit_mode'] = mode.value
                results.append(result_dict)
            except Exception as e:
                print(f"Error with {mode.value}: {e}")
        
        return pd.DataFrame(results)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def load_data(data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Load all metrics from parquet files."""
    data_dir = data_dir or RAW_DATA_DIR
    
    dfs = {}
    for f in sorted(data_dir.glob("*.parquet")):
        metric_name = f.stem
        temp = pd.read_parquet(f)
        temp = temp.set_index("time")
        temp = temp.rename(columns={"value": metric_name})
        dfs[metric_name] = temp
    
    combined = pd.concat(dfs.values(), axis=1)
    return combined.sort_index()


def quick_backtest(
    metric: str,
    direction: str,
    threshold: float,
    regime: Optional[str] = None,
    exit_mode: ExitMode = ExitMode.COMBINED,
    df: Optional[pd.DataFrame] = None
) -> BacktestResult:
    """Quick backtest for a single signal."""
    if df is None:
        df = load_data()
    
    signal = Signal(
        metric=metric,
        direction=direction,
        threshold=threshold,
        regime=regime
    )
    
    config = BacktestConfig(exit_mode=exit_mode)
    bt = Backtester(config)
    
    return bt.run(df, signal)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    print("Loading data...")
    df = load_data()
    
    if df.empty:
        print("No data found. Run 'python run.py sync' first.")
        exit(1)
    
    print(f"Loaded {len(df.columns)} metrics, {len(df)} rows")
    
    # Test signal
    signal = Signal(
        metric='mvrv',
        direction='below',
        threshold=df['mvrv'].quantile(0.20),
        regime='bull',
        name='mvrv<20th_bull'
    )
    
    print(f"\nTesting: {signal.name}")
    print(f"Condition: {signal.condition}")
    print(f"Regime: {signal.regime}")
    
    # Compare exit modes
    print("\n" + "=" * 70)
    print("COMPARING EXIT MODES")
    print("=" * 70)
    
    for mode in [ExitMode.COMBINED, ExitMode.SIGNAL_EXIT, ExitMode.REGIME_EXIT, ExitMode.FIXED_HOLD]:
        config = BacktestConfig(exit_mode=mode, hold_days=30)
        bt = Backtester(config)
        result = bt.run(df, signal)
        
        print(f"\n{mode.value.upper()}")
        print(f"  Trades: {result.n_trades}")
        print(f"  Total Return: {result.total_return:+.1%}")
        print(f"  Sharpe: {result.sharpe_ratio:.2f}")
        print(f"  Win Rate: {result.win_rate:.1%}")
        print(f"  Avg Hold: {result.avg_hold_days:.0f} days")
        print(f"  Max DD: {result.max_drawdown:.1%}")
        
        if result.exits_by_reason:
            print(f"  Exits: {result.exits_by_reason}")
