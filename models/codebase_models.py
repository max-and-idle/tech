"""
Pydantic models for the codebase API.
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class SearchType(str, Enum):
    """Types of search available."""
    semantic = "semantic"
    hybrid = "hybrid" 
    keyword = "keyword"


class SourceType(str, Enum):
    """Types of codebase sources."""
    github = "github"
    zip = "zip"
    local = "local"


# Request Models

class GitHubIndexRequest(BaseModel):
    """Request model for indexing GitHub repositories."""
    url: str = Field(..., description="GitHub repository URL")
    name: Optional[str] = Field(None, description="Custom name for the codebase")
    
    @validator('url')
    def validate_github_url(cls, v):
        if not any(domain in v.lower() for domain in ['github.com', 'github']):
            raise ValueError('Must be a GitHub URL')
        return v


class ZipIndexRequest(BaseModel):
    """Request model for indexing ZIP files."""
    name: Optional[str] = Field(None, description="Custom name for the codebase")


class LocalIndexRequest(BaseModel):
    """Request model for indexing local directories."""
    path: str = Field(..., description="Path to local directory")
    name: Optional[str] = Field(None, description="Custom name for the codebase")
    copy_to_temp: bool = Field(False, description="Whether to copy directory to temp location")


class SearchRequest(BaseModel):
    """Request model for searching codebases."""
    query: str = Field(..., description="Search query")
    codebase_name: str = Field(..., description="Name of codebase to search")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to return")
    search_type: SearchType = Field(SearchType.semantic, description="Type of search")
    filters: Optional[Dict[str, str]] = Field(None, description="Optional filters")
    include_context: bool = Field(True, description="Whether to include formatted context")


# Response Models

class FileInfo(BaseModel):
    """Information about a processed file."""
    path: str
    relative_path: str
    language: str
    size: int
    hash: str


class SearchResultItem(BaseModel):
    """Individual search result item."""
    id: str
    content: str
    chunk_type: str
    name: str
    file_path: str
    language: str
    line_start: int
    line_end: int
    parent_name: Optional[str] = None
    docstring: Optional[str] = None
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IndexingStatistics(BaseModel):
    """Statistics from indexing operation."""
    total_files: int
    processed_files: int
    total_chunks: int
    successful_embeddings: int
    file_types: Dict[str, Any]
    source_type: str
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class IndexingResponse(BaseModel):
    """Response model for indexing operations."""
    status: str
    name: str
    statistics: Optional[IndexingStatistics] = None
    error: Optional[str] = None


class SearchResponse(BaseModel):
    """Response model for search operations."""
    query: str
    codebase_name: str
    results: List[SearchResultItem]
    total_results: int
    search_type: str
    context: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None


class CodebaseInfo(BaseModel):
    """Information about an indexed codebase."""
    name: str
    table_name: str
    total_chunks: int
    languages: Dict[str, int] = Field(default_factory=dict)
    chunk_types: Dict[str, int] = Field(default_factory=dict)


class CodebaseListResponse(BaseModel):
    """Response model for listing codebases."""
    codebases: List[CodebaseInfo]
    total_count: int


class CodebaseStats(BaseModel):
    """Detailed statistics for a codebase."""
    name: str
    total_chunks: int
    languages: Dict[str, int] = Field(default_factory=dict)
    chunk_types: Dict[str, int] = Field(default_factory=dict)
    files: int
    avg_chunk_size: float
    largest_file: Optional[str] = None


class DeleteResponse(BaseModel):
    """Response model for delete operations."""
    status: str
    name: str
    success: bool
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    message: str
    timestamp: str
    version: str = "1.0.0"
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Generic error response."""
    error: str
    detail: Optional[str] = None
    status_code: int = 400


# Context Models

class CodeContext(BaseModel):
    """Context information for code chunks."""
    file_path: str
    content: str
    line_start: int
    line_end: int
    language: str
    surrounding_context: Optional[str] = None
    imports: List[str] = Field(default_factory=list)
    related_chunks: List[str] = Field(default_factory=list)


class FocusedContextResponse(BaseModel):
    """Response with focused context around search results."""
    query: str
    primary_result: SearchResultItem
    context: CodeContext
    related_results: List[SearchResultItem] = Field(default_factory=list)
    summary: str


# Specialized Search Models

class SearchByTypeRequest(BaseModel):
    """Search request for specific chunk types."""
    query: str = Field(..., description="Search query")
    codebase_name: str = Field(..., description="Name of codebase")
    chunk_type: str = Field(..., description="Type of chunk to search for")
    top_k: int = Field(5, ge=1, le=50, description="Number of results")


class SearchByLanguageRequest(BaseModel):
    """Search request for specific programming languages."""
    query: str = Field(..., description="Search query")
    codebase_name: str = Field(..., description="Name of codebase")
    language: str = Field(..., description="Programming language")
    top_k: int = Field(5, ge=1, le=50, description="Number of results")


class SimilarFunctionsRequest(BaseModel):
    """Request to find similar functions."""
    function_name: str = Field(..., description="Function name to find similar functions for")
    codebase_name: str = Field(..., description="Name of codebase")
    top_k: int = Field(5, ge=1, le=20, description="Number of results")


class ClassMethodsRequest(BaseModel):
    """Request to find methods in a class."""
    class_name: str = Field(..., description="Class name")
    codebase_name: str = Field(..., description="Name of codebase")
    top_k: int = Field(10, ge=1, le=50, description="Number of results")


# Configuration Models

class CodebaseConfig(BaseModel):
    """Configuration for codebase indexing."""
    db_path: str = Field("./codebase_db", description="Vector database path")
    embedding_model: str = Field("gemini", description="Embedding model to use")
    chunk_size: int = Field(1000, ge=100, le=10000, description="Maximum chunk size")
    chunk_overlap: int = Field(100, ge=0, le=500, description="Chunk overlap size")
    default_top_k: int = Field(5, ge=1, le=100, description="Default number of search results")
    max_context_tokens: int = Field(8000, ge=1000, le=50000, description="Maximum context tokens")


# Validation Models

class ValidationRequest(BaseModel):
    """Request to validate a source before indexing."""
    source_type: SourceType
    url: Optional[str] = None
    path: Optional[str] = None


class ValidationResponse(BaseModel):
    """Response from source validation."""
    valid: bool
    source_type: str
    message: str
    metadata: Optional[Dict[str, Any]] = None


# Batch Operation Models

class BatchIndexRequest(BaseModel):
    """Request to index multiple sources."""
    sources: List[Dict[str, Any]] = Field(..., description="List of sources to index")
    concurrent_limit: int = Field(3, ge=1, le=10, description="Maximum concurrent operations")


class BatchIndexResponse(BaseModel):
    """Response from batch indexing."""
    total_requested: int
    successful: int
    failed: int
    results: List[IndexingResponse]
    errors: List[Dict[str, str]] = Field(default_factory=list)