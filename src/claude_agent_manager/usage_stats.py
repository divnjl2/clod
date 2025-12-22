"""
Usage statistics reader for Claude Code.

Reads stats-cache.json to get current session/daily usage info.
Provides formatted data for dashboard display.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


# Default plan settings
DEFAULT_PLAN = "Max"
DEFAULT_DAILY_LIMIT = 100000  # 100k tokens estimate for Max plan


@dataclass
class UsageStats:
    """Current usage statistics."""
    # Today's stats
    today_tokens: int = 0
    today_messages: int = 0
    today_tools: int = 0
    today_sessions: int = 0

    # Model breakdown
    tokens_by_model: Dict[str, int] = None

    # Cumulative stats
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read: int = 0
    total_cache_write: int = 0

    # Plan info
    plan_name: str = DEFAULT_PLAN
    daily_limit: int = DEFAULT_DAILY_LIMIT

    # Meta
    last_updated: Optional[datetime] = None

    def __post_init__(self):
        if self.tokens_by_model is None:
            self.tokens_by_model = {}

    @property
    def usage_percent(self) -> float:
        """Calculate usage percentage based on daily limit."""
        if self.daily_limit <= 0:
            return 0.0
        return min(100.0, (self.today_tokens / self.daily_limit) * 100)

    @property
    def tokens_formatted(self) -> str:
        """Format tokens as human readable (1.2k, 3.5M)."""
        return format_tokens(self.today_tokens)

    @property
    def primary_model(self) -> str:
        """Get the primary model used today."""
        if not self.tokens_by_model:
            return "claude"
        # Return model with most tokens
        max_model = max(self.tokens_by_model.items(), key=lambda x: x[1], default=("claude", 0))
        # Shorten model name
        name = max_model[0]
        if "opus" in name.lower():
            return "opus"
        elif "sonnet" in name.lower():
            return "sonnet"
        elif "haiku" in name.lower():
            return "haiku"
        return name.split("-")[0] if "-" in name else name[:10]


def format_tokens(n: int) -> str:
    """Format token count as human readable string."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}k"
    else:
        return str(n)


def get_claude_stats_path() -> Path:
    """Get path to Claude stats-cache.json."""
    claude_dir = Path.home() / ".claude"
    return claude_dir / "stats-cache.json"


def read_usage_stats(plan_name: str = DEFAULT_PLAN, daily_limit: int = DEFAULT_DAILY_LIMIT) -> UsageStats:
    """
    Read current usage stats from Claude's stats-cache.json.

    Args:
        plan_name: Plan name to display
        daily_limit: Daily token limit for percentage calculation

    Returns:
        UsageStats object with current data
    """
    stats = UsageStats(plan_name=plan_name, daily_limit=daily_limit)
    stats_path = get_claude_stats_path()

    if not stats_path.exists():
        return stats

    try:
        with open(stats_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        stats.last_updated = datetime.now()
        today = datetime.now().strftime("%Y-%m-%d")

        # Get today's activity
        daily_activity = data.get("dailyActivity", [])
        for day in daily_activity:
            if day.get("date") == today:
                stats.today_messages = day.get("messageCount", 0)
                stats.today_sessions = day.get("sessionCount", 0)
                stats.today_tools = day.get("toolCallCount", 0)
                break

        # Get today's tokens by model
        daily_tokens = data.get("dailyModelTokens", [])
        for day in daily_tokens:
            if day.get("date") == today:
                tokens_by_model = day.get("tokensByModel", {})
                stats.tokens_by_model = tokens_by_model
                stats.today_tokens = sum(tokens_by_model.values())
                break

        # Get cumulative model usage
        model_usage = data.get("modelUsage", {})
        for model, usage in model_usage.items():
            stats.total_input_tokens += usage.get("inputTokens", 0)
            stats.total_output_tokens += usage.get("outputTokens", 0)
            stats.total_cache_read += usage.get("cacheReadInputTokens", 0)
            stats.total_cache_write += usage.get("cacheCreationInputTokens", 0)

        return stats

    except (json.JSONDecodeError, IOError, KeyError):
        return stats


def get_usage_display(plan_name: str = DEFAULT_PLAN, daily_limit: int = DEFAULT_DAILY_LIMIT) -> Dict[str, Any]:
    """
    Get formatted usage data for display.

    Returns dict with:
        - percent: usage percentage
        - plan: plan name
        - model: primary model name
        - messages: message count
        - tools: tool call count
    """
    stats = read_usage_stats(plan_name, daily_limit)

    return {
        "percent": stats.usage_percent,
        "plan": stats.plan_name,
        "model": stats.primary_model,
        "messages": stats.today_messages,
        "tools": stats.today_tools,
        "sessions": stats.today_sessions,
        "raw_tokens": stats.today_tokens,
    }


# Quick test
if __name__ == "__main__":
    stats = read_usage_stats()
    print(f"Plan: {stats.plan_name}")
    print(f"Usage: {stats.usage_percent:.1f}%")
    print(f"Model: {stats.primary_model}")
    print(f"Messages: {stats.today_messages}, Tools: {stats.today_tools}")
