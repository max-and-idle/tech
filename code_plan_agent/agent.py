"""
Google ADK Agent for code modification planning.
"""

import logging
from google.adk.agents import Agent
from .tools import (
    search_related_code,
    find_similar_patterns,
    analyze_dependencies,
    analyze_impact,
    get_component_callers
)
from .prompts import AGENT_INSTRUCTION

logger = logging.getLogger(__name__)

# Create the code plan agent
code_plan_agent = Agent(
    name="code_modification_planner",
    model="gemini-2.5-flash",
    description=(
        "Analyzes codebases and generates detailed code modification plans based on requirements. "
        "Uses semantic search and relationship graphs to understand code dependencies and impact."
    ),
    instruction=AGENT_INSTRUCTION,
    tools=[
        search_related_code,
        find_similar_patterns,
        analyze_dependencies,
        analyze_impact,
        get_component_callers
    ]
)

logger.info("Code modification planner agent initialized")
