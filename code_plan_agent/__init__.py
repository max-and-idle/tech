"""
Code Plan Agent - AI agent for generating code modification plans.
"""

from .tools import (
    search_related_code,
    analyze_dependencies,
    analyze_impact,
    find_similar_patterns
)
from .agent import code_plan_agent

# Google ADK requires root_agent
root_agent = code_plan_agent

__all__ = [
    "code_plan_agent",
    "root_agent",
    "search_related_code",
    "analyze_dependencies",
    "analyze_impact",
    "find_similar_patterns"
]
