"""
Walk-Forward Validation Module (v2)
===================================
Tests signals on truly out-of-sample data to detect overfitting.

Uses COMBINED exit mode (signal OR regime change) instead of fixed hold days.

Usage:
    from src.walk_forward import WalkForwardValidator, quick_validate
    
    validator = WalkForwardValidator()
    results = validator.validate_signals(df, signals)
    
    # View approved signals with full details
    validator.print_approved_details(results)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Literal
from datetime import datetime
from dataclasses import dataclass, field
import json
import warnings
warnings.filterwarnings('ignore')

from src.models import SignalSpec, WalkForwardFold, WalkForwardResult, ApprovalCriteria
from src.config import BULL_MARKETS, BEAR_MARKETS, RAW_DATA_DIR, RESULTS_DIR
from src.backtester import Backtester, BacktestConfig, Signal, ExitMode, load_data


# =============================================================================
# WALK-FORWARD VALIDATOR
# =============================================================================

class WalkForwardValidator:
    """
    Walk-forward validation to detect overfitting.
    
    Tests signals on out-of-sample data using cycle-based leave-one-out:
    - For each bull market cycle, train on all OTHER cycles
    - Test on the held-out cycle
    - Only OOS results count
    """
    
    def __init__(
        self,
        exit_mode: ExitMode = ExitMode.COMBINED,
        criteria: Optional[ApprovalCriteria] = None
    ):
        """
        Initialize validator.
        
        Args:
            exit_mode: Exit strategy for backtests
            criteria: Approval criteria for signals
        """
        self.exit_mode = exit_mode
        self.criteria = criteria or ApprovalCriteria()
    
    def generate_cycle_folds(self, regime: str = "bull") -> List[Dict]:
        """
        Generate cycle-based folds (leave-one-out).
        
        For each cycle, train on all OTHER cycles, test on THIS cycle.
        """
        cycles = BULL_MARKETS if regime == "bull" else BEAR_MARKETS
        
        folds = []
        for i, test_cycle in enumerate(cycles):
            train_cycles = [c for j, c in enumerate(cycles) if j != i]
            
            if len(train_cycles) < 2:
                continue
            
            folds.append({
                'fold_id': i,
                'test_cycle': test_cycle,
                'train_cycles': train_cycles,
            })
        
        return folds
    
    def _run_backtest(
        self,
        df: pd.DataFrame,
        signal: Signal,
        start_date: str,
        end_date: str
    ) -> Dict:
        """Run backtest on a period."""
        config = BacktestConfig(exit_mode=self.exit_mode)
        bt = Backtester(config)
        
        try:
            result = bt.run(df, signal, start_date=start_date, end_date=end_date)
            return {
                'n_trades': result.n_trades,
                'total_return': result.total_return,
                'sharpe': result.sharpe_ratio,
                'win_rate': result.win_rate,
                'max_dd': result.max_drawdown,
                'avg_hold_days': result.avg_hold_days,
                'exits': result.exits_by_reason,
                'trades': [t.to_dict() for t in result.trades],
            }
        except Exception as e:
            return {
                'n_trades': 0,
                'total_return': 0.0,
                'sharpe': 0.0,
                'win_rate': 0.0,
                'max_dd': 0.0,
                'avg_hold_days': 0.0,
                'exits': {},
                'trades': [],
                'error': str(e),
            }
    
    def _backtest_combined_periods(
        self,
        df: pd.DataFrame,
        signal: Signal,
        cycles: List[Dict]
    ) -> Dict:
        """Backtest across multiple periods (for training)."""
        all_trades = []
        total_days = 0
        
        for cycle in cycles:
            start = pd.Timestamp(cycle['start'], tz='UTC')
            end = pd.Timestamp(cycle['end'], tz='UTC')
            
            cycle_df = df[(df.index >= start) & (df.index < end)]
            if len(cycle_df) < 30:
                continue
            
            result = self._run_backtest(df, signal, cycle['start'], cycle['end'])
            all_trades.extend(result.get('trades', []))
            total_days += (end - start).days
        
        if not all_trades:
            return {'n_trades': 0, 'total_return': 0, 'sharpe': 0, 'win_rate': 0, 'max_dd': 0}
        
        # Calculate combined metrics
        returns = [t['return_pct'] for t in all_trades if t.get('return_pct') is not None]
        wins = [r for r in returns if r > 0]
        
        return {
            'n_trades': len(all_trades),
            'total_return': np.prod([1 + r for r in returns]) - 1 if returns else 0,
            'sharpe': np.mean(returns) / np.std(returns) * np.sqrt(12) if returns and np.std(returns) > 0 else 0,
            'win_rate': len(wins) / len(returns) if returns else 0,
            'max_dd': 0,  # Would need equity curve
            'trades': all_trades,
        }
    
    def validate(
        self,
        df: pd.DataFrame,
        signal: SignalSpec,
        method: str = 'cycle'
    ) -> WalkForwardResult:
        """
        Validate a signal using walk-forward testing.
        
        Args:
            df: DataFrame with price and metric data
            signal: SignalSpec to validate
            method: 'cycle' for leave-one-out by market cycle
            
        Returns:
            WalkForwardResult with OOS metrics
        """
        # Convert SignalSpec to Signal
        bt_signal = Signal(
            metric=signal.metric,
            direction=signal.direction,
            threshold=signal.threshold,
            regime=signal.regime,
            name=signal.name
        )
        
        regime = signal.regime or "bull"
        folds_config = self.generate_cycle_folds(regime)
        
        folds = []
        all_oos_trades = []
        
        for fold_cfg in folds_config:
            test_cycle = fold_cfg['test_cycle']
            train_cycles = fold_cfg['train_cycles']
            
            # In-sample: train on other cycles
            is_result = self._backtest_combined_periods(df, bt_signal, train_cycles)
            
            # Out-of-sample: test on this cycle
            oos_result = self._run_backtest(
                df, bt_signal,
                test_cycle['start'],
                test_cycle['end']
            )
            
            all_oos_trades.extend(oos_result.get('trades', []))
            
            fold = WalkForwardFold(
                fold_id=fold_cfg['fold_id'],
                train_start="multiple",
                train_end="multiple",
                test_start=test_cycle['start'],
                test_end=test_cycle['end'],
                is_n_trades=is_result['n_trades'],
                is_total_return=is_result['total_return'],
                is_sharpe=is_result['sharpe'],
                is_win_rate=is_result['win_rate'],
                is_max_dd=is_result['max_dd'],
                oos_n_trades=oos_result['n_trades'],
                oos_total_return=oos_result['total_return'],
                oos_sharpe=oos_result['sharpe'],
                oos_win_rate=oos_result['win_rate'],
                oos_max_dd=oos_result['max_dd'],
            )
            folds.append(fold)
        
        return self._aggregate_results(signal, folds, all_oos_trades)
    
    def _aggregate_results(
        self,
        signal: SignalSpec,
        folds: List[WalkForwardFold],
        all_oos_trades: List[Dict]
    ) -> WalkForwardResult:
        """Aggregate fold results."""
        
        if not folds:
            return WalkForwardResult(
                signal=signal,
                method='cycle',
                n_folds=0,
                folds=[],
                passed=False,
                failure_reasons=["No valid folds"]
            )
        
        n_folds = len(folds)
        
        # OOS metrics from folds
        oos_returns = [f.oos_total_return for f in folds]
        oos_sharpes = [f.oos_sharpe for f in folds if f.oos_n_trades > 0]
        oos_win_rates = [f.oos_win_rate for f in folds if f.oos_n_trades > 0]
        oos_dds = [f.oos_max_dd for f in folds if f.oos_n_trades > 0]
        
        # IS metrics
        is_sharpes = [f.is_sharpe for f in folds if f.is_n_trades > 0]
        
        # Combined OOS return
        oos_total = np.prod([1 + r for r in oos_returns]) - 1 if oos_returns else 0
        
        # Consistency
        profitable_folds = sum(1 for r in oos_returns if r > 0)
        consistency = profitable_folds / n_folds if n_folds > 0 else 0
        
        # Degradation
        degradations = [f.degradation for f in folds if f.is_sharpe != 0]
        avg_degradation = np.mean(degradations) if degradations else 0
        
        # Calculate OOS trade stats
        oos_trade_returns = [t['return_pct'] for t in all_oos_trades if t.get('return_pct') is not None]
        oos_avg_hold = np.mean([t['duration_days'] for t in all_oos_trades if t.get('duration_days')]) if all_oos_trades else 0
        
        result = WalkForwardResult(
            signal=signal,
            method='cycle',
            n_folds=n_folds,
            folds=folds,
            oos_total_return=oos_total,
            oos_avg_return=np.mean(oos_returns) if oos_returns else 0,
            oos_sharpe=np.mean(oos_sharpes) if oos_sharpes else 0,
            oos_win_rate=np.mean(oos_win_rates) if oos_win_rates else 0,
            oos_max_dd=min(oos_dds) if oos_dds else 0,
            is_sharpe=np.mean(is_sharpes) if is_sharpes else 0,
            consistency=consistency,
            avg_degradation=avg_degradation,
        )
        
        # Store extra data
        result.oos_n_trades = sum(f.oos_n_trades for f in folds)
        result.oos_avg_hold_days = oos_avg_hold
        result.all_oos_trades = all_oos_trades
        
        # Evaluate approval
        passed, failures = self.criteria.evaluate(result)
        result.passed = passed
        result.failure_reasons = failures
        
        return result
    
    def validate_signals(
        self,
        df: pd.DataFrame,
        signals: List[SignalSpec],
        verbose: bool = True
    ) -> List[WalkForwardResult]:
        """Validate multiple signals."""
        results = []
        
        for i, signal in enumerate(signals):
            if verbose:
                print(f"[{i+1}/{len(signals)}] {signal.name}...", end=" ")
            
            result = self.validate(df, signal)
            results.append(result)
            
            if verbose:
                status = "✅" if result.passed else "❌"
                print(f"{status} Sharpe={result.oos_sharpe:.2f} Win={result.oos_win_rate:.0%} "
                      f"Consist={result.consistency:.0%} ({result.oos_n_trades} trades)")
        
        return results
    
    def get_approved(self, results: List[WalkForwardResult]) -> List[WalkForwardResult]:
        return [r for r in results if r.passed]
    
    def get_rejected(self, results: List[WalkForwardResult]) -> List[WalkForwardResult]:
        return [r for r in results if not r.passed]
    
    # -------------------------------------------------------------------------
    # DETAILED REPORTING
    # -------------------------------------------------------------------------
    
    def print_approved_details(self, results: List[WalkForwardResult]):
        """Print detailed results for approved signals."""
        approved = self.get_approved(results)
        
        if not approved:
            print("\n⚠️  No signals passed validation!")
            return
        
        print("\n" + "=" * 90)
        print("✅ APPROVED SIGNALS - DETAILED RESULTS")
        print("=" * 90)
        
        for result in sorted(approved, key=lambda r: r.oos_sharpe, reverse=True):
            self._print_signal_detail(result)
    
    def _print_signal_detail(self, result: WalkForwardResult):
        """Print detailed results for one signal."""
        print(f"\n{'─' * 90}")
        print(f"📊 {result.signal.name}")
        print(f"{'─' * 90}")
        print(f"   Condition: {result.signal.condition}")
        print(f"   Regime: {result.signal.regime}")
        print(f"   Exit Mode: {self.exit_mode.value}")
        
        print(f"\n   OUT-OF-SAMPLE PERFORMANCE (what you'll actually get):")
        print(f"   ├─ Total Return:  {result.oos_total_return:>+8.1%}")
        print(f"   ├─ Sharpe Ratio:  {result.oos_sharpe:>8.2f}")
        print(f"   ├─ Win Rate:      {result.oos_win_rate:>8.0%}")
        print(f"   ├─ Total Trades:  {result.oos_n_trades:>8}")
        print(f"   └─ Avg Hold Days: {getattr(result, 'oos_avg_hold_days', 0):>8.0f}")
        
        print(f"\n   VALIDATION METRICS:")
        print(f"   ├─ Consistency:   {result.consistency:>8.0%} ({int(result.consistency * result.n_folds)}/{result.n_folds} cycles profitable)")
        print(f"   ├─ Degradation:   {result.avg_degradation:>8.0%} (IS→OOS drop)")
        print(f"   └─ IS Sharpe:     {result.is_sharpe:>8.2f} (for comparison)")
        
        print(f"\n   CYCLE-BY-CYCLE RESULTS:")
        cycles = BULL_MARKETS if result.signal.regime == "bull" else BEAR_MARKETS
        
        print(f"   {'Cycle':<20} {'Return':>10} {'Sharpe':>8} {'Win%':>8} {'Trades':>8}")
        print(f"   {'-'*60}")
        
        for fold, cycle in zip(result.folds, cycles):
            status = "✅" if fold.oos_total_return > 0 else "❌"
            print(f"   {cycle['name']:<20} {fold.oos_total_return:>+9.1%} "
                  f"{fold.oos_sharpe:>8.2f} {fold.oos_win_rate:>7.0%} "
                  f"{fold.oos_n_trades:>8} {status}")
    
    def print_rejected_summary(self, results: List[WalkForwardResult]):
        """Print why signals were rejected."""
        rejected = self.get_rejected(results)
        
        if not rejected:
            print("\n✅ All signals passed!")
            return
        
        print("\n" + "=" * 90)
        print("❌ REJECTED SIGNALS")
        print("=" * 90)
        
        # Sort by IS sharpe to show "looked good but failed"
        rejected = sorted(rejected, key=lambda r: r.is_sharpe, reverse=True)
        
        print(f"\n{'Signal':<35} {'IS':>8} {'OOS':>8} {'Consist':>10} {'Reason'}")
        print("-" * 90)
        
        for r in rejected[:15]:
            reason = r.failure_reasons[0][:30] if r.failure_reasons else "Unknown"
            print(f"{r.signal.name:<35} {r.is_sharpe:>8.2f} {r.oos_sharpe:>8.2f} "
                  f"{r.consistency:>9.0%} {reason}")
    
    def print_summary(self, results: List[WalkForwardResult]):
        """Print full summary."""
        approved = self.get_approved(results)
        rejected = self.get_rejected(results)
        
        print("\n" + "=" * 90)
        print("WALK-FORWARD VALIDATION SUMMARY")
        print("=" * 90)
        print(f"\nExit Mode: {self.exit_mode.value}")
        print(f"Total signals: {len(results)}")
        print(f"Approved: {len(approved)} ({len(approved)/len(results)*100:.0f}%)")
        print(f"Rejected: {len(rejected)} ({len(rejected)/len(results)*100:.0f}%)")
        
        self.print_approved_details(results)
        self.print_rejected_summary(results)
    
    # -------------------------------------------------------------------------
    # SAVE RESULTS
    # -------------------------------------------------------------------------
    
    def save_results(self, results: List[WalkForwardResult], filename: Optional[str] = None) -> Path:
        """Save all results to JSON."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wf_results_{timestamp}.json"
        
        output_path = RESULTS_DIR / "walk_forward" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'exit_mode': self.exit_mode.value,
            'n_signals': len(results),
            'n_approved': len([r for r in results if r.passed]),
            'results': [r.to_dict() for r in results]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        return output_path
    
    def save_approved(self, results: List[WalkForwardResult]) -> Path:
        """Save approved signals for paper trading."""
        approved = self.get_approved(results)
        
        output_path = RESULTS_DIR.parent / "signals" / "approved_signals.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'exit_mode': self.exit_mode.value,
            'n_approved': len(approved),
            'signals': [
                {
                    'name': r.signal.name,
                    'metric': r.signal.metric,
                    'direction': r.signal.direction,
                    'threshold': r.signal.threshold,
                    'regime': r.signal.regime,
                    'oos_sharpe': r.oos_sharpe,
                    'oos_return': r.oos_total_return,
                    'oos_win_rate': r.oos_win_rate,
                    'consistency': r.consistency,
                    'n_trades': r.oos_n_trades,
                    'avg_hold_days': getattr(r, 'oos_avg_hold_days', 0),
                }
                for r in approved
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return output_path


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
    print(f"Date range: {df.index.min().date()} to {df.index.max().date()}")
    
    # Define signals to validate (top consistent signals from screener)
    signals = [
        # High consistency (5/5 cycles from earlier analysis)
        SignalSpec('liveliness', 'below', df['liveliness'].quantile(0.10), 'bull', name='liveliness<10th'),
        SignalSpec('vaultedness', 'above', df['vaultedness'].quantile(0.90), 'bull', name='vaultedness>90th'),
        SignalSpec('sopr', 'above', df['sopr'].quantile(0.90), 'bull', name='sopr>90th'),
        SignalSpec('sopr', 'above', df['sopr'].quantile(0.95), 'bull', name='sopr>95th'),
        SignalSpec('nvt', 'below', df['nvt'].quantile(0.20), 'bull', name='nvt<20th'),
        SignalSpec('mvrv_sth', 'below', df['mvrv_sth'].quantile(0.05), 'bull', name='mvrv_sth<5th'),
        SignalSpec('mvrv', 'below', df['mvrv'].quantile(0.20), 'bull', name='mvrv<20th'),
        SignalSpec('mvrv_lth', 'below', df['mvrv_lth'].quantile(0.20), 'bull', name='mvrv_lth<20th'),
        
        # Previously looked good but inconsistent (likely to fail)
        SignalSpec('supply_lth_sth_ratio', 'below', df['supply_lth_sth_ratio'].quantile(0.05), 'bull', name='lth_sth<5th'),
        SignalSpec('mvrv_lth', 'above', df['mvrv_lth'].quantile(0.95), 'bull', name='mvrv_lth>95th'),
    ]
    
    print(f"\n{'='*90}")
    print("WALK-FORWARD VALIDATION (Cycle-Based Leave-One-Out)")
    print(f"{'='*90}")
    print(f"Exit Mode: COMBINED (exit on signal OR regime change)")
    print(f"Testing {len(signals)} signals...\n")
    
    validator = WalkForwardValidator(exit_mode=ExitMode.COMBINED)
    results = validator.validate_signals(df, signals)
    
    # Print detailed summary
    validator.print_summary(results)
    
    # Save results
    results_path = validator.save_results(results)
    print(f"\n📁 Full results: {results_path}")
    
    approved = validator.get_approved(results)
    if approved:
        signals_path = validator.save_approved(results)
        print(f"📁 Approved signals: {signals_path}")
