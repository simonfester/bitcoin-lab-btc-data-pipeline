"""
Quota Tracking Module for Bitcoin Lab API
==========================================

Tracks API quota usage, estimates costs, and provides forecasting.

Usage:
    from src.quota import QuotaTracker, estimate_quota_cost
    
    tracker = QuotaTracker()
    tracker.log_usage("price", "d1", data_points=365)
    tracker.get_summary()
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
import requests

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"

QUOTA_LOG_FILE = LOGS_DIR / "quota_usage.json"
QUOTA_WEEKLY_LIMIT = 1_000_000  # Tier 2 limit

# Resolution to data points per day
RESOLUTION_POINTS_PER_DAY = {
    "d1": 1,
    "h12": 2,
    "h8": 3,
    "h6": 4,
    "h4": 6,
    "h2": 12,
    "h1": 24,
    "m30": 48,
    "m15": 96,
    "block": 144,  # ~144 blocks per day average
}


# =============================================================================
# QUOTA ESTIMATION
# =============================================================================

def estimate_quota_cost(
    days: int,
    resolution: str = "d1",
    bins: int = 1,
    metrics: int = 1
) -> int:
    """
    Estimate quota cost (data points) for an API request.
    
    Args:
        days: Number of days of data
        resolution: Data resolution (d1, h1, h4, etc.)
        bins: Number of bins for binned data (default 1 for simple series)
        metrics: Number of metrics to fetch
    
    Returns:
        Estimated data points (quota cost)
    
    Examples:
        >>> estimate_quota_cost(365, "d1")  # 1 year daily
        365
        >>> estimate_quota_cost(30, "h1")   # 30 days hourly
        720
        >>> estimate_quota_cost(30, "d1", bins=7)  # 30 days daily with 7 bins
        210
    """
    points_per_day = RESOLUTION_POINTS_PER_DAY.get(resolution, 1)
    timestamps = days * points_per_day
    data_points = timestamps * bins * metrics
    return int(data_points)


def estimate_sync_cost(
    metrics_config: list,
    resolution: str = "d1",
    days: int = 1
) -> dict:
    """
    Estimate total quota cost for syncing multiple metrics.
    
    Returns dict with per-metric and total estimates.
    """
    estimates = {}
    total = 0
    
    for metric in metrics_config:
        # Check if metric supports this resolution
        if hasattr(metric, 'supports_resolution'):
            if not metric.supports_resolution(resolution):
                continue
        
        # Default bins to 1 (simple series)
        bins = getattr(metric, 'bins', 1)
        cost = estimate_quota_cost(days, resolution, bins)
        estimates[metric.name] = cost
        total += cost
    
    return {
        "metrics": estimates,
        "total": total,
        "resolution": resolution,
        "days": days
    }


# =============================================================================
# QUOTA TRACKER
# =============================================================================

@dataclass
class UsageRecord:
    """Single usage record."""
    timestamp: str
    metric: str
    resolution: str
    data_points: int
    from_time: Optional[str] = None
    to_time: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class QuotaTracker:
    """
    Tracks API quota usage over time.
    
    Stores usage history in a JSON file and provides summaries/forecasts.
    """
    
    def __init__(self, log_file: Path = QUOTA_LOG_FILE):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_history()
    
    def _load_history(self):
        """Load usage history from file."""
        if self.log_file.exists():
            with open(self.log_file) as f:
                data = json.load(f)
                self.history = data.get("history", [])
                self.weekly_limit = data.get("weekly_limit", QUOTA_WEEKLY_LIMIT)
        else:
            self.history = []
            self.weekly_limit = QUOTA_WEEKLY_LIMIT
    
    def _save_history(self):
        """Save usage history to file."""
        with open(self.log_file, "w") as f:
            json.dump({
                "weekly_limit": self.weekly_limit,
                "history": self.history
            }, f, indent=2)
    
    def log_usage(
        self,
        metric: str,
        resolution: str,
        data_points: int,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Log a single API usage record."""
        record = UsageRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            metric=metric,
            resolution=resolution,
            data_points=data_points,
            from_time=from_time,
            to_time=to_time,
            success=success,
            error=error
        )
        self.history.append(asdict(record))
        self._save_history()
    
    def get_usage_since(self, since: datetime) -> int:
        """Get total data points used since a given datetime."""
        total = 0
        since_str = since.isoformat()
        
        for record in self.history:
            if record["timestamp"] >= since_str and record["success"]:
                total += record["data_points"]
        
        return total
    
    def get_weekly_usage(self) -> int:
        """Get data points used in the current week (rolling 7 days)."""
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        return self.get_usage_since(week_ago)
    
    def get_daily_usage(self, days: int = 7) -> list[dict]:
        """Get daily usage breakdown for the last N days."""
        daily = {}
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        for record in self.history:
            ts = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
            if ts < cutoff:
                continue
            
            day = ts.strftime("%Y-%m-%d")
            if day not in daily:
                daily[day] = {"date": day, "data_points": 0, "requests": 0, "errors": 0}
            
            daily[day]["data_points"] += record["data_points"]
            daily[day]["requests"] += 1
            if not record["success"]:
                daily[day]["errors"] += 1
        
        return sorted(daily.values(), key=lambda x: x["date"], reverse=True)
    
    def get_metric_usage(self, days: int = 7) -> dict:
        """Get usage breakdown by metric for the last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        metrics = {}
        
        for record in self.history:
            ts = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
            if ts < cutoff or not record["success"]:
                continue
            
            metric = record["metric"]
            if metric not in metrics:
                metrics[metric] = {"metric": metric, "data_points": 0, "requests": 0}
            
            metrics[metric]["data_points"] += record["data_points"]
            metrics[metric]["requests"] += 1
        
        return dict(sorted(metrics.items(), key=lambda x: x[1]["data_points"], reverse=True))
    
    def get_summary(self) -> dict:
        """Get comprehensive usage summary."""
        weekly_used = self.get_weekly_usage()
        weekly_remaining = max(0, self.weekly_limit - weekly_used)
        weekly_pct = (weekly_used / self.weekly_limit) * 100 if self.weekly_limit > 0 else 0
        
        # Calculate daily average
        daily_usage = self.get_daily_usage(7)
        if daily_usage:
            avg_daily = sum(d["data_points"] for d in daily_usage) / len(daily_usage)
        else:
            avg_daily = 0
        
        # Forecast days until quota exhausted
        if avg_daily > 0:
            days_remaining = weekly_remaining / avg_daily
        else:
            days_remaining = float('inf')
        
        return {
            "weekly_limit": self.weekly_limit,
            "weekly_used": weekly_used,
            "weekly_remaining": weekly_remaining,
            "weekly_pct_used": round(weekly_pct, 1),
            "avg_daily_usage": round(avg_daily),
            "days_at_current_rate": round(days_remaining, 1) if days_remaining != float('inf') else None,
            "daily_breakdown": daily_usage[:7],
            "top_metrics": list(self.get_metric_usage(7).values())[:10]
        }
    
    def clear_old_history(self, days: int = 90):
        """Remove history older than N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        old_count = len(self.history)
        self.history = [r for r in self.history if r["timestamp"] >= cutoff_str]
        removed = old_count - len(self.history)
        
        self._save_history()
        return removed


# =============================================================================
# API INFO WITH QUOTA
# =============================================================================

def get_api_quota_status(base_url: str, token: str) -> dict:
    """
    Get current quota status from API.
    
    Returns dict with quota info and calculated fields.
    """
    headers = {"X-API-Token": token, "Accept": "application/json"}
    
    resp = requests.get(f"{base_url}/v2/info/user_info", headers=headers)
    resp.raise_for_status()
    
    data = resp.json().get("data", {})
    
    # Parse and enrich the data
    quota_remaining = data.get("quota_remaining", 0)
    quota_reset_value = data.get("quota_reset_value", 1_000_000)
    quota_used = quota_reset_value - quota_remaining
    
    # Parse reset time
    reset_time_str = data.get("quota_last_reset_time")
    if reset_time_str:
        reset_time = datetime.fromisoformat(reset_time_str.replace("Z", "+00:00"))
        next_reset = reset_time + timedelta(days=7)
        days_until_reset = (next_reset - datetime.now(timezone.utc)).total_seconds() / 86400
    else:
        next_reset = None
        days_until_reset = None
    
    return {
        "quota_limit": quota_reset_value,
        "quota_used": quota_used,
        "quota_remaining": quota_remaining,
        "quota_pct_used": round((quota_used / quota_reset_value) * 100, 1) if quota_reset_value > 0 else 0,
        "last_reset": reset_time_str,
        "next_reset": next_reset.isoformat() if next_reset else None,
        "days_until_reset": round(days_until_reset, 1) if days_until_reset else None,
        "tier": data.get("user_tier"),
        "subscription_expiry": data.get("subscription_expiry_time"),
        "token_expiry": data.get("token_expiry_time"),
    }


# =============================================================================
# CLI COMMANDS
# =============================================================================

def cmd_quota(base_url: str = None, token: str = None):
    """Display current quota status."""
    import yaml
    
    # Load config if not provided
    if not base_url or not token:
        config_path = CONFIG_DIR / "metrics.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        base_url = base_url or config["api"]["base_url"]
        token = token or os.environ.get(config["api"]["token_env"], "")
    
    if not token:
        print("Error: API token not found")
        return
    
    # Get API quota status
    api_status = get_api_quota_status(base_url, token)
    
    # Get local tracking
    tracker = QuotaTracker()
    local_summary = tracker.get_summary()
    
    # Display
    print("\n" + "=" * 60)
    print("QUOTA STATUS")
    print("=" * 60)
    
    print(f"\n📊 API Quota (from server):")
    print(f"   Used:      {api_status['quota_used']:>12,} / {api_status['quota_limit']:,} DPs")
    print(f"   Remaining: {api_status['quota_remaining']:>12,} DPs ({100 - api_status['quota_pct_used']:.1f}%)")
    print(f"   Resets in: {api_status['days_until_reset']:.1f} days")
    print(f"   Next reset: {api_status['next_reset'][:10] if api_status['next_reset'] else 'N/A'}")
    
    # Progress bar
    pct = api_status['quota_pct_used']
    bar_width = 40
    filled = int(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    color = "🟢" if pct < 50 else "🟡" if pct < 80 else "🔴"
    print(f"\n   {color} [{bar}] {pct:.1f}%")
    
    if local_summary["daily_breakdown"]:
        print(f"\n📈 Local Tracking (last 7 days):")
        print(f"   Avg daily: {local_summary['avg_daily_usage']:,} DPs")
        if local_summary['days_at_current_rate']:
            print(f"   At this rate, quota lasts: {local_summary['days_at_current_rate']:.1f} days")
        
        print(f"\n   Daily breakdown:")
        for day in local_summary["daily_breakdown"][:5]:
            print(f"      {day['date']}: {day['data_points']:>10,} DPs ({day['requests']} requests)")
    
    if local_summary["top_metrics"]:
        print(f"\n   Top metrics by usage:")
        for m in local_summary["top_metrics"][:5]:
            print(f"      {m['metric']:<25}: {m['data_points']:>10,} DPs")
    
    print("\n" + "=" * 60)
    return api_status


def cmd_quota_estimate(days: int = 1, resolution: str = "d1", metrics_count: int = None):
    """Estimate quota cost for a sync operation."""
    import yaml
    
    # Load metrics config
    config_path = CONFIG_DIR / "metrics.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    metrics = config.get("metrics", [])
    
    # Filter metrics by resolution
    supported = [m for m in metrics if resolution in m.get("resolutions", ["d1"])]
    
    if metrics_count:
        supported = supported[:metrics_count]
    
    # Calculate estimates
    total = 0
    print(f"\n📊 Quota Estimate: {days} days @ {resolution}")
    print("=" * 50)
    
    for m in supported:
        bins = m.get("bins", 1)
        cost = estimate_quota_cost(days, resolution, bins)
        total += cost
        print(f"   {m['name']:<30}: {cost:>10,} DPs")
    
    print("-" * 50)
    print(f"   {'TOTAL':<30}: {total:>10,} DPs")
    print(f"\n   Metrics: {len(supported)}")
    print(f"   Points/day @ {resolution}: {RESOLUTION_POINTS_PER_DAY.get(resolution, 1)}")
    
    return total


def cmd_quota_history(days: int = 30):
    """Show quota usage history."""
    tracker = QuotaTracker()
    
    print(f"\n📈 Quota Usage History (last {days} days)")
    print("=" * 60)
    
    daily = tracker.get_daily_usage(days)
    
    if not daily:
        print("   No usage recorded yet.")
        print("   Usage will be tracked after running sync commands.")
        return
    
    print(f"\n{'Date':<12} {'Data Points':>15} {'Requests':>10} {'Errors':>8}")
    print("-" * 50)
    
    total_dp = 0
    total_req = 0
    
    for day in daily:
        total_dp += day["data_points"]
        total_req += day["requests"]
        print(f"{day['date']:<12} {day['data_points']:>15,} {day['requests']:>10} {day['errors']:>8}")
    
    print("-" * 50)
    print(f"{'TOTAL':<12} {total_dp:>15,} {total_req:>10}")
    
    return daily


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python quota.py status       # Show quota status")
        print("  python quota.py estimate N   # Estimate N days sync cost")
        print("  python quota.py history      # Show usage history")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        cmd_quota()
    elif cmd == "estimate":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        resolution = sys.argv[3] if len(sys.argv) > 3 else "d1"
        cmd_quota_estimate(days, resolution)
    elif cmd == "history":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        cmd_quota_history(days)
    else:
        print(f"Unknown command: {cmd}")
