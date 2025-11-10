from pydantic_ai.usage import RunUsage
from typing import Dict


def get_usage_stats(usage: RunUsage) -> Dict[str, int | float]:
    """Helper to safely extract usage statistics from RunUsage object"""
    return {
        "total_tokens": getattr(usage, 'total_tokens', 0),
        "prompt_tokens": getattr(usage, 'prompt_tokens', 0),
        "completion_tokens": getattr(usage, 'completion_tokens', 0),
        "total_duration": getattr(usage, 'total_duration', 0),
        "request_count": getattr(usage, 'request_count', 0)
    }