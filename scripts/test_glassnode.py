#!/usr/bin/env python3
"""
Test script for downloading Glassnode derivatives data.
"""

import sys
sys.path.insert(0, '/Users/fester/Documents/bitcoin-lab-btc-data-pipeline/src')

from glassnode_downloader import GlassnodeDownloader, GlassnodeClient

def test_connection():
    """Test API connection."""
    print("Testing Glassnode API connection...")
    
    client = GlassnodeClient()
    
    # Test with funding rate
    df = client.fetch_metric(
        endpoint="/v1/metrics/derivatives/futures_funding_rate_perpetual",
        since="2024-01-01"
    )
    
    if df is not None:
        print(f"✓ Connection successful!")
        print(f"  Funding rate data: {len(df)} rows")
        print(f"  Date range: {df.index.min()} to {df.index.max()}")
        print(f"  Latest value: {df['value'].iloc[-1]:.6f}")
        return True
    else:
        print("✗ Connection failed")
        return False


def download_all_derivatives():
    """Download all Buy-the-Dip derivatives metrics."""
    print("\nDownloading derivatives data...")
    
    downloader = GlassnodeDownloader()
    results = downloader.download_buy_the_dip_metrics(since="2019-01-01")
    
    print(f"\nDownloaded {len(results)} metrics:")
    for name, df in results.items():
        print(f"  {name}: {len(df)} rows ({df.index.min().date()} to {df.index.max().date()})")
    
    return results


def get_latest_values():
    """Get latest values for quick dashboard check."""
    print("\nLatest derivatives values:")
    
    downloader = GlassnodeDownloader()
    latest = downloader.get_latest_values()
    
    for metric, value in latest.items():
        print(f"  {metric}: {value:.6f}")


if __name__ == "__main__":
    if test_connection():
        download_all_derivatives()
        get_latest_values()
