#!/usr/bin/env python3
"""
Backtest Results Database
=========================
SQLite database for indexing backtest runs with JSON files for full details.

Schema:
- backtest_runs: Summary metrics + parameters for fast querying
- Full details (equity curves, trades, charts) stored in JSON files

Usage:
    from src.backtest_db import BacktestDB

    db = BacktestDB()

    # Save a run
    run_id = db.save_run(strategy_id, strategy_name, params, metrics, json_path)

    # Query runs
    runs = db.get_runs(strategy_id='STRAT-005', min_sharpe=1.0)

    # Get best runs
    best = db.get_top_runs(metric='sharpe', limit=10)
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import hashlib


# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "backtest_results.db"
RUNS_DIR = PROJECT_ROOT / "data" / "backtest_runs"

# Ensure directories exist
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# DATABASE CLASS
# =============================================================================

class BacktestDB:
    """SQLite database for backtest results indexing."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backtest_runs (
                run_id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                strategy_name TEXT,
                run_date TEXT NOT NULL,

                -- Parameters (stored as JSON for flexibility)
                parameters TEXT,
                param_hash TEXT,

                -- Configuration
                resolution TEXT DEFAULT 'daily',
                train_start TEXT,
                train_end TEXT,
                train_days INTEGER,
                test_start TEXT,
                test_end TEXT,
                test_days INTEGER,

                -- Position sizing
                position_size_pct REAL,
                risk_per_trade_pct REAL,
                stop_loss_pct REAL,

                -- Performance metrics (test period)
                return_pct REAL,
                sharpe REAL,
                sortino REAL,
                calmar REAL,
                omega REAL,
                max_dd REAL,
                max_dd_days INTEGER,
                win_rate REAL,
                num_trades INTEGER,
                profit_factor REAL,
                expectancy REAL,
                avg_hold_days REAL,

                -- Train metrics (for comparison)
                train_return_pct REAL,
                train_sharpe REAL,

                -- Benchmark
                benchmark_return_pct REAL,

                -- File reference
                json_file TEXT,

                -- Metadata
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        ''')

        # Create indexes for common queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategy_id ON backtest_runs(strategy_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_run_date ON backtest_runs(run_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sharpe ON backtest_runs(sharpe)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_return ON backtest_runs(return_pct)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_param_hash ON backtest_runs(param_hash)')

        conn.commit()
        conn.close()

    def generate_run_id(self) -> str:
        """Generate unique run ID based on timestamp."""
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]

    def generate_param_hash(self, params: dict) -> str:
        """Generate hash of parameters for duplicate detection."""
        # Sort keys for consistent hashing
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()[:12]

    def save_run(
        self,
        strategy_id: str,
        strategy_name: str,
        results: dict,
        parameters: dict = None,
        notes: str = None
    ) -> str:
        """
        Save a backtest run to database and JSON file.

        Args:
            strategy_id: Strategy identifier (e.g., 'STRAT-005')
            strategy_name: Human-readable name
            results: Full results dict from backtest
            parameters: Strategy parameters used
            notes: Optional notes about this run

        Returns:
            run_id: Unique identifier for this run
        """
        run_id = self.generate_run_id()
        run_date = datetime.now().isoformat()

        # Extract metrics from results
        test = results.get('test', {})
        train = results.get('train', {})
        benchmark = results.get('benchmark', {})
        train_period = results.get('train_period', {})
        test_period = results.get('test_period', {})
        pos_sizing = results.get('position_sizing', {})

        # Generate parameter hash
        param_hash = self.generate_param_hash(parameters) if parameters else None

        # Save full results to JSON file
        json_filename = f"run_{run_id}.json"
        json_path = RUNS_DIR / json_filename

        full_results = {
            'run_id': run_id,
            'strategy_id': strategy_id,
            'strategy_name': strategy_name,
            'run_date': run_date,
            'parameters': parameters,
            **results
        }

        with open(json_path, 'w') as f:
            json.dump(full_results, f, indent=2)

        # Insert into database
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO backtest_runs (
                run_id, strategy_id, strategy_name, run_date,
                parameters, param_hash, resolution,
                train_start, train_end, train_days,
                test_start, test_end, test_days,
                position_size_pct, risk_per_trade_pct, stop_loss_pct,
                return_pct, sharpe, sortino, calmar, omega,
                max_dd, max_dd_days, win_rate, num_trades,
                profit_factor, expectancy, avg_hold_days,
                train_return_pct, train_sharpe,
                benchmark_return_pct,
                json_file, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            run_id,
            strategy_id,
            strategy_name,
            run_date,
            json.dumps(parameters) if parameters else None,
            param_hash,
            results.get('resolution', 'daily'),
            train_period.get('start'),
            train_period.get('end'),
            train_period.get('days'),
            test_period.get('start'),
            test_period.get('end'),
            test_period.get('days'),
            pos_sizing.get('position_size_pct'),
            pos_sizing.get('risk_per_trade_pct'),
            pos_sizing.get('stop_loss_pct'),
            test.get('return_pct'),
            test.get('sharpe'),
            test.get('sortino'),
            test.get('calmar'),
            test.get('omega'),
            test.get('max_dd'),
            test.get('max_dd_days'),
            test.get('win_rate'),
            test.get('num_trades'),
            test.get('profit_factor'),
            test.get('expectancy'),
            test.get('avg_hold_days'),
            train.get('return_pct'),
            train.get('sharpe'),
            benchmark.get('test_return'),
            json_filename,
            notes
        ))

        conn.commit()
        conn.close()

        return run_id

    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get a single run by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM backtest_runs WHERE run_id = ?', (run_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_run_details(self, run_id: str) -> Optional[Dict]:
        """Get full run details from JSON file."""
        run = self.get_run(run_id)
        if not run or not run.get('json_file'):
            return None

        json_path = RUNS_DIR / run['json_file']
        if not json_path.exists():
            return None

        with open(json_path, 'r') as f:
            return json.load(f)

    def get_runs(
        self,
        strategy_id: str = None,
        min_sharpe: float = None,
        min_return: float = None,
        max_dd: float = None,
        min_trades: int = None,
        limit: int = 100,
        order_by: str = 'run_date',
        order_desc: bool = True
    ) -> List[Dict]:
        """
        Query runs with optional filters.

        Args:
            strategy_id: Filter by strategy
            min_sharpe: Minimum Sharpe ratio
            min_return: Minimum return percentage
            max_dd: Maximum drawdown (absolute value)
            min_trades: Minimum number of trades
            limit: Maximum results to return
            order_by: Column to sort by
            order_desc: Sort descending if True

        Returns:
            List of run dicts
        """
        conditions = []
        params = []

        if strategy_id:
            conditions.append('strategy_id = ?')
            params.append(strategy_id)

        if min_sharpe is not None:
            conditions.append('sharpe >= ?')
            params.append(min_sharpe)

        if min_return is not None:
            conditions.append('return_pct >= ?')
            params.append(min_return)

        if max_dd is not None:
            conditions.append('ABS(max_dd) <= ?')
            params.append(abs(max_dd))

        if min_trades is not None:
            conditions.append('num_trades >= ?')
            params.append(min_trades)

        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        order_dir = 'DESC' if order_desc else 'ASC'

        query = f'''
            SELECT * FROM backtest_runs
            WHERE {where_clause}
            ORDER BY {order_by} {order_dir}
            LIMIT ?
        '''
        params.append(limit)

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_top_runs(
        self,
        metric: str = 'sharpe',
        strategy_id: str = None,
        limit: int = 10
    ) -> List[Dict]:
        """Get top performing runs by a specific metric."""
        return self.get_runs(
            strategy_id=strategy_id,
            limit=limit,
            order_by=metric,
            order_desc=True
        )

    def get_strategies(self) -> List[Dict]:
        """Get list of unique strategies with run counts."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                strategy_id,
                strategy_name,
                COUNT(*) as run_count,
                MAX(return_pct) as best_return,
                MAX(sharpe) as best_sharpe,
                MIN(max_dd) as worst_dd,
                MAX(run_date) as last_run
            FROM backtest_runs
            GROUP BY strategy_id
            ORDER BY strategy_id
        ''')
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_parameter_variations(self, strategy_id: str) -> List[Dict]:
        """Get all parameter variations for a strategy with their performance."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                param_hash,
                parameters,
                COUNT(*) as run_count,
                AVG(return_pct) as avg_return,
                AVG(sharpe) as avg_sharpe,
                MAX(return_pct) as best_return,
                MAX(sharpe) as best_sharpe
            FROM backtest_runs
            WHERE strategy_id = ? AND param_hash IS NOT NULL
            GROUP BY param_hash
            ORDER BY avg_sharpe DESC
        ''', (strategy_id,))
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            d = dict(row)
            if d['parameters']:
                d['parameters'] = json.loads(d['parameters'])
            results.append(d)

        return results

    def delete_run(self, run_id: str) -> bool:
        """Delete a run and its JSON file."""
        run = self.get_run(run_id)
        if not run:
            return False

        # Delete JSON file
        if run.get('json_file'):
            json_path = RUNS_DIR / run['json_file']
            if json_path.exists():
                json_path.unlink()

        # Delete from database
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM backtest_runs WHERE run_id = ?', (run_id,))
        conn.commit()
        conn.close()

        return True

    def delete_strategy_runs(self, strategy_id: str) -> int:
        """Delete all runs for a strategy."""
        runs = self.get_runs(strategy_id=strategy_id, limit=10000)
        count = 0
        for run in runs:
            if self.delete_run(run['run_id']):
                count += 1
        return count

    def get_stats(self) -> Dict:
        """Get database statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM backtest_runs')
        total_runs = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT strategy_id) FROM backtest_runs')
        total_strategies = cursor.fetchone()[0]

        cursor.execute('SELECT MIN(run_date), MAX(run_date) FROM backtest_runs')
        row = cursor.fetchone()

        conn.close()

        return {
            'total_runs': total_runs,
            'total_strategies': total_strategies,
            'first_run': row[0],
            'last_run': row[1],
            'db_path': str(self.db_path),
            'runs_dir': str(RUNS_DIR)
        }

    def check_duplicate(self, strategy_id: str, param_hash: str) -> Optional[str]:
        """Check if a run with same strategy and parameters already exists."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT run_id FROM backtest_runs
            WHERE strategy_id = ? AND param_hash = ?
            ORDER BY run_date DESC
            LIMIT 1
        ''', (strategy_id, param_hash))
        row = cursor.fetchone()
        conn.close()

        return row['run_id'] if row else None


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Command-line interface for backtest database."""
    import argparse

    parser = argparse.ArgumentParser(description='Backtest Results Database')
    parser.add_argument('command', choices=['stats', 'list', 'top', 'strategies', 'delete'],
                        help='Command to run')
    parser.add_argument('--strategy', '-s', help='Filter by strategy ID')
    parser.add_argument('--metric', '-m', default='sharpe', help='Metric for top command')
    parser.add_argument('--limit', '-n', type=int, default=10, help='Number of results')
    parser.add_argument('--run-id', '-r', help='Run ID for delete command')

    args = parser.parse_args()

    db = BacktestDB()

    if args.command == 'stats':
        stats = db.get_stats()
        print("\n=== Backtest Database Stats ===")
        print(f"Total runs:       {stats['total_runs']}")
        print(f"Total strategies: {stats['total_strategies']}")
        print(f"First run:        {stats['first_run']}")
        print(f"Last run:         {stats['last_run']}")
        print(f"Database:         {stats['db_path']}")
        print(f"Runs directory:   {stats['runs_dir']}")

    elif args.command == 'list':
        runs = db.get_runs(strategy_id=args.strategy, limit=args.limit)
        print(f"\n{'Run ID':<22} {'Strategy':<12} {'Return':>10} {'Sharpe':>8} {'DD':>8} {'Trades':>7}")
        print("-" * 75)
        for run in runs:
            print(f"{run['run_id']:<22} {run['strategy_id']:<12} "
                  f"{run['return_pct']:>+9.1f}% {run['sharpe']:>8.2f} "
                  f"{run['max_dd']:>7.1f}% {run['num_trades']:>7}")

    elif args.command == 'top':
        runs = db.get_top_runs(metric=args.metric, strategy_id=args.strategy, limit=args.limit)
        print(f"\n=== Top {args.limit} by {args.metric} ===")
        print(f"{'Run ID':<22} {'Strategy':<12} {'Return':>10} {'Sharpe':>8} {'DD':>8}")
        print("-" * 65)
        for run in runs:
            print(f"{run['run_id']:<22} {run['strategy_id']:<12} "
                  f"{run['return_pct']:>+9.1f}% {run['sharpe']:>8.2f} {run['max_dd']:>7.1f}%")

    elif args.command == 'strategies':
        strategies = db.get_strategies()
        print(f"\n{'Strategy':<15} {'Runs':>6} {'Best Return':>12} {'Best Sharpe':>12} {'Last Run':<20}")
        print("-" * 75)
        for s in strategies:
            print(f"{s['strategy_id']:<15} {s['run_count']:>6} "
                  f"{s['best_return']:>+11.1f}% {s['best_sharpe']:>12.2f} {s['last_run'][:19]}")

    elif args.command == 'delete':
        if args.run_id:
            if db.delete_run(args.run_id):
                print(f"Deleted run: {args.run_id}")
            else:
                print(f"Run not found: {args.run_id}")
        elif args.strategy:
            count = db.delete_strategy_runs(args.strategy)
            print(f"Deleted {count} runs for strategy: {args.strategy}")
        else:
            print("Specify --run-id or --strategy to delete")


if __name__ == "__main__":
    main()
