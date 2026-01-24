"""
Smart Data Loader - Intelligent source selection based on quality analysis
==========================================================================
Uses Bitcoin Lab as primary, BRK for price, with automatic fallback.

Based on investigation (2026-01-23):
- Bitcoin Lab: Best for NUPL, most metrics (correct formulas, 56 metrics)
- BRK: Best for price (12x more accurate), FREE
- Glassnode: Validation via MCP

Usage:
    from src.smart_loader import load_metric, load_metrics

    # Load single metric (auto source selection)
    price = load_metric('price')  # Uses BRK (most accurate)
    nupl = load_metric('nupl')    # Uses Bitcoin Lab (correct metric)

    # Load multiple metrics
    data = load_metrics(['price', 'nupl', 'mvrv'])
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# =============================================================================
# SOURCE PRIORITY CONFIGURATION
# =============================================================================

# Metric-specific source priority (based on quality analysis)
METRIC_SOURCES = {
    'price': ['brk', 'bl'],  # BRK: $83 MAE vs BL: $972 MAE
    'nupl': ['bl'],          # BL only - BRK has wrong metric
    'nupl_lth': ['bl'],
    'nupl_sth': ['bl'],
}

# Default priority for all other metrics
DEFAULT_SOURCES = ['bl', 'brk']

# Path templates
PATHS = {
    'bl': DATA_DIR / 'bl' / 'daily',
    'brk': DATA_DIR / 'brk' / 'daily',
}

# BRK metrics that need unit conversion (satoshis → BTC)
SATOSHI_METRICS = {
    'supply_total', 'supply_lth', 'supply_sth',
    'supply_in_profit', 'supply_in_loss',
}


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def load_metric(
    metric: str,
    source: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None
) -> pd.DataFrame:
    """
    Load a single metric with intelligent source selection.

    Args:
        metric: Metric name (e.g., 'price', 'nupl', 'mvrv')
        source: Force specific source ('bl' or 'brk'), None for auto
        start: Start date 'YYYY-MM-DD' (optional)
        end: End date 'YYYY-MM-DD' (optional)

    Returns:
        DataFrame with columns ['time', 'value']

    Example:
        >>> price = load_metric('price')
        >>> print(f"Loaded from: {price.attrs.get('source')}")
        Loaded from: brk
    """
    # Determine source priority
    if source:
        sources = [source]
    else:
        sources = METRIC_SOURCES.get(metric, DEFAULT_SOURCES)

    # Try each source
    for src in sources:
        path = PATHS.get(src) / f"{metric}.parquet"

        if not path.exists():
            continue

        try:
            df = pd.read_parquet(path)

            if df.empty:
                continue

            # Ensure columns
            if 'time' not in df.columns:
                if df.index.name == 'time':
                    df = df.reset_index()
                else:
                    continue

            # Convert BRK satoshi metrics
            if src == 'brk' and metric in SATOSHI_METRICS:
                if df['value'].max() > 1e12:  # Still in satoshis
                    df['value'] = df['value'] / 1e8

            # Filter dates
            if start or end:
                df['time'] = pd.to_datetime(df['time'])
                if start:
                    df = df[df['time'] >= start]
                if end:
                    df = df[df['time'] <= end]

            # Add metadata
            df.attrs['source'] = src
            df.attrs['metric'] = metric

            logger.info(f"Loaded {metric} from {src}: {len(df)} rows")
            return df

        except Exception as e:
            logger.debug(f"Failed {src}/{metric}: {e}")
            continue

    raise FileNotFoundError(f"Metric '{metric}' not found in any source")


def load_metrics(
    metrics: List[str],
    align: bool = True,
    **kwargs
) -> pd.DataFrame:
    """
    Load multiple metrics and optionally merge on time.

    Args:
        metrics: List of metric names
        align: Merge all on common timestamps (default: True)
        **kwargs: Passed to load_metric (start, end, source)

    Returns:
        Single DataFrame with all metrics, or dict if align=False

    Example:
        >>> data = load_metrics(['price', 'nupl', 'mvrv'])
        >>> data.columns
        Index(['time', 'price', 'nupl', 'mvrv'], dtype='object')
    """
    results = {}

    for metric in metrics:
        try:
            df = load_metric(metric, **kwargs)
            results[metric] = df
        except FileNotFoundError:
            logger.warning(f"Skipping {metric}: not found")

    if not results:
        raise FileNotFoundError(f"No metrics found: {metrics}")

    if not align:
        return results

    # Merge on time
    merged = None
    for metric, df in results.items():
        df = df.rename(columns={'value': metric})[['time', metric]]

        if merged is None:
            merged = df
        else:
            merged = merged.merge(df, on='time', how='outer')

    merged = merged.sort_values('time').reset_index(drop=True)
    return merged


def get_source_for_metric(metric: str) -> str:
    """
    Get which source will be used for a metric.

    Returns:
        Source name ('bl' or 'brk')
    """
    sources = METRIC_SOURCES.get(metric, DEFAULT_SOURCES)

    for src in sources:
        path = PATHS.get(src) / f"{metric}.parquet"
        if path.exists():
            return src

    return 'not_found'


def print_source_map(metrics: List[str]):
    """Print which source will be used for each metric"""
    print("Source Mapping:")
    print("-" * 50)
    for metric in metrics:
        src = get_source_for_metric(metric)
        reason = ""
        if metric == 'price':
            reason = " (most accurate)"
        elif metric in ['nupl', 'nupl_lth', 'nupl_sth']:
            reason = " (correct formula)"

        print(f"  {metric:<20} → {src}{reason}")


# =============================================================================
# CONVENIENCE SHORTCUTS
# =============================================================================

def load_price(**kwargs) -> pd.DataFrame:
    """Load price (uses BRK - most accurate)"""
    return load_metric('price', **kwargs)


def load_nupl(**kwargs) -> pd.DataFrame:
    """Load NUPL (uses Bitcoin Lab - correct metric)"""
    return load_metric('nupl', **kwargs)


def load_mvrv(**kwargs) -> pd.DataFrame:
    """Load MVRV"""
    return load_metric('mvrv', **kwargs)


def load_sopr(cohort: Optional[str] = None, **kwargs) -> pd.DataFrame:
    """
    Load SOPR

    Args:
        cohort: 'lth', 'sth', or None for all
    """
    metric = f'sopr_{cohort}' if cohort else 'sopr'
    return load_metric(metric, **kwargs)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("SMART DATA LOADER - Source Priority Test")
    print("=" * 60)
    print()

    test_metrics = ['price', 'nupl', 'mvrv', 'sopr', 'supply_total']

    print_source_map(test_metrics)
    print()

    print("Loading metrics...")
    print("-" * 60)

    for metric in test_metrics:
        try:
            df = load_metric(metric)
            src = df.attrs.get('source', 'unknown')
            last_date = df['time'].max()
            last_value = df['value'].iloc[-1]

            print(f"{metric:<20} {src:>5}  {len(df):>6} rows  "
                  f"last: {pd.to_datetime(last_date).strftime('%Y-%m-%d')}  "
                  f"value: {last_value:.4f}")
        except Exception as e:
            print(f"{metric:<20} ERROR: {str(e)[:40]}")

    print()
    print("=" * 60)
