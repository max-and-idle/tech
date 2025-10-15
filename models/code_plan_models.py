"""
Pydantic models for code plan API.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# Request Models

class CodePlanRequest(BaseModel):
    """Request to generate a code modification plan."""
    codebase_name: str = Field(..., description="Name of the codebase to analyze")
    requirement: str = Field(..., description="Natural language description of the requirement")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class CodePlanRefineRequest(BaseModel):
    """Request to refine an existing plan."""
    feedback: str = Field(..., description="User feedback on the plan")
    additional_requirements: Optional[List[str]] = Field(None, description="Additional requirements")


# Response Models

class RequirementAnalysis(BaseModel):
    """Analysis of the requirement."""
    summary: str
    feature_type: str  # "enhancement", "bugfix", "refactoring", "new_feature"
    complexity: str  # "low", "medium", "high"
    estimated_effort: str


class ComponentChange(BaseModel):
    """Details of a component that needs to be changed."""
    file_path: str
    component_name: str
    component_type: str  # "function", "class", "method", "module"
    modification_type: str  # "ADD", "UPDATE", "DELETE"
    current_code: Optional[str] = None
    proposed_changes: List[str]
    proposed_code: Optional[str] = None
    rationale: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None


class ImplementationStep(BaseModel):
    """A step in the implementation plan."""
    step: int
    action: str
    details: str
    code_snippet: Optional[str] = None
    files: Optional[List[str]] = None


class DependencyInfo(BaseModel):
    """Information about dependencies."""
    existing_code: List[Dict[str, str]]
    external_libraries: List[str]
    database_changes: Optional[str] = None


class ImpactAnalysis(BaseModel):
    """Analysis of the impact of changes."""
    affected_files: List[str]
    affected_components: List[str]
    breaking_changes: bool
    risk_level: str  # "low", "medium", "high"
    test_coverage_needed: List[str]


class SimilarImplementation(BaseModel):
    """Reference to a similar implementation."""
    file: str
    component: str
    similarity: str
    note: str


class TestingStrategy(BaseModel):
    """Testing strategy for the changes."""
    unit_tests: List[str]
    integration_tests: List[str]
    test_files: List[str]


class CodePlanResponse(BaseModel):
    """Response containing the code modification plan."""
    plan_id: str
    requirement_analysis: RequirementAnalysis
    affected_components: List[ComponentChange]
    implementation_steps: List[ImplementationStep]
    dependencies: DependencyInfo
    impact_analysis: ImpactAnalysis
    similar_implementations: List[SimilarImplementation]
    testing_strategy: Optional[TestingStrategy] = None
    agent_reasoning: str
    created_at: str


class CodePlanHistoryItem(BaseModel):
    """Item in the code plan history."""
    plan_id: str
    codebase_name: str
    requirement: str
    created_at: str
    summary: str


class CodePlanHistoryResponse(BaseModel):
    """Response containing code plan history."""
    codebase_name: str
    plans: List[CodePlanHistoryItem]
    total_count: int


# Relationship API Models

class CallersRequest(BaseModel):
    """Request to find callers of a component."""
    component_name: str
    codebase_name: str


class CallersResponse(BaseModel):
    """Response with caller information."""
    component_name: str
    callers: List[Dict[str, Any]]
    total_callers: int


class DependenciesRequest(BaseModel):
    """Request to get dependencies of a component."""
    component_name: str
    codebase_name: str


class DependenciesResponse(BaseModel):
    """Response with dependency information."""
    component_name: str
    dependencies: Dict[str, List[Dict[str, Any]]]
    summary: Dict[str, int]


class ImpactScopeRequest(BaseModel):
    """Request to get impact scope of a component."""
    chunk_id: str
    codebase_name: str
    max_depth: int = 2


class ImpactScopeResponse(BaseModel):
    """Response with impact scope information."""
    target: Dict[str, Any]
    direct_impact: List[Dict[str, Any]]
    indirect_impact: List[Dict[str, Any]]
    affected_files: List[str]
    total_affected_components: int
    total_affected_files: int
