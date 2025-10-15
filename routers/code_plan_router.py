"""
FastAPI router for code plan operations.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from models.code_plan_models import (
    CodePlanRequest,
    CodePlanResponse,
    CallersRequest,
    CallersResponse,
    DependenciesRequest,
    DependenciesResponse,
    ImpactScopeRequest,
    ImpactScopeResponse
)
from code_plan_agent import code_plan_agent
from code_plan_agent.tools import get_relationship_store

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()


@router.post(
    "/generate",
    response_model=CodePlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Code Modification Plan",
    description="Generate a detailed code modification plan using AI agent"
)
async def generate_code_plan(request: CodePlanRequest):
    """Generate a code modification plan based on requirements."""
    try:
        logger.info(f"Generating code plan for: {request.requirement[:100]}...")

        # Prepare the prompt for the agent
        agent_prompt = f"""
Generate a code modification plan for the following requirement:

Codebase: {request.codebase_name}
Requirement: {request.requirement}

Follow these steps:
1. Use search_related_code() to find relevant code
2. Use find_similar_patterns() to find similar implementations
3. Use analyze_dependencies() to understand dependencies
4. Use analyze_impact() to assess impact
5. Generate a comprehensive plan

Provide your response in the structured JSON format specified in the instructions.
"""

        # Run the agent
        result = await code_plan_agent.run(agent_prompt)

        # Extract the agent's response
        agent_response = result.content if hasattr(result, 'content') else str(result)

        logger.info(f"Agent generated plan (length: {len(agent_response)})")

        # For now, return a structured response
        # In a real implementation, you would parse the agent's JSON response
        plan_id = str(uuid.uuid4())

        # Create response (this is a simplified version)
        # The agent should return proper JSON that matches CodePlanResponse
        response = {
            "plan_id": plan_id,
            "requirement_analysis": {
                "summary": f"Analysis of: {request.requirement[:100]}",
                "feature_type": "enhancement",
                "complexity": "medium",
                "estimated_effort": "2-4 hours"
            },
            "affected_components": [],
            "implementation_steps": [],
            "dependencies": {
                "existing_code": [],
                "external_libraries": [],
                "database_changes": None
            },
            "impact_analysis": {
                "affected_files": [],
                "affected_components": [],
                "breaking_changes": False,
                "risk_level": "low",
                "test_coverage_needed": []
            },
            "similar_implementations": [],
            "testing_strategy": None,
            "agent_reasoning": agent_response,
            "created_at": datetime.utcnow().isoformat()
        }

        return CodePlanResponse(**response)

    except Exception as e:
        logger.error(f"Error generating code plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/relationships/callers",
    response_model=CallersResponse,
    summary="Find Callers",
    description="Find all code that calls/uses a specific component"
)
async def get_callers(component_name: str, codebase_name: str):
    """Get callers of a specific component."""
    try:
        logger.info(f"Finding callers for: {component_name}")

        relationship_store = get_relationship_store()
        callers = relationship_store.find_callers(component_name, codebase_name)

        return CallersResponse(
            component_name=component_name,
            callers=callers,
            total_callers=len(callers)
        )

    except Exception as e:
        logger.error(f"Error finding callers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/relationships/dependencies",
    response_model=DependenciesResponse,
    summary="Get Dependencies",
    description="Get dependencies of a specific component"
)
async def get_dependencies(component_name: str, codebase_name: str):
    """Get dependencies of a component."""
    try:
        logger.info(f"Getting dependencies for: {component_name}")

        relationship_store = get_relationship_store()
        dependencies = relationship_store.find_dependencies(component_name, codebase_name)

        # Calculate summary
        summary = {
            "total_imports": len(dependencies.get('imports', [])),
            "total_calls": len(dependencies.get('calls', [])),
            "total_inherits": len(dependencies.get('inherits', [])),
            "total_uses": len(dependencies.get('uses', []))
        }

        return DependenciesResponse(
            component_name=component_name,
            dependencies=dependencies,
            summary=summary
        )

    except Exception as e:
        logger.error(f"Error getting dependencies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/relationships/impact",
    summary="Get Impact Scope",
    description="Get the impact scope of modifying a component"
)
async def get_impact_scope(chunk_id: str, codebase_name: str, max_depth: int = 2):
    """Get impact scope of modifying a component."""
    try:
        logger.info(f"Getting impact scope for chunk: {chunk_id}")

        relationship_store = get_relationship_store()
        impact = relationship_store.find_impact_scope(chunk_id, codebase_name, max_depth)

        if not impact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chunk '{chunk_id}' not found"
            )

        return impact

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting impact scope: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/relationships/stats",
    summary="Get Relationship Statistics",
    description="Get statistics about code relationships in a codebase"
)
async def get_relationship_stats(codebase_name: str):
    """Get relationship statistics for a codebase."""
    try:
        logger.info(f"Getting relationship stats for: {codebase_name}")

        relationship_store = get_relationship_store()
        stats = relationship_store.get_relationship_stats(codebase_name)

        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Codebase '{codebase_name}' not found"
            )

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting relationship stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
