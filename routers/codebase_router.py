"""
FastAPI router for codebase operations.
"""

import os
import logging
from typing import List, Dict, Any
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, status
from fastapi.responses import JSONResponse

from codebase import CodebaseIndexer
from models.codebase_models import (
    # Request models
    GitHubIndexRequest,
    ZipIndexRequest,
    LocalIndexRequest,
    SearchRequest,
    SearchByTypeRequest,
    SearchByLanguageRequest,
    SimilarFunctionsRequest,
    ClassMethodsRequest,
    ValidationRequest,
    
    # Response models
    IndexingResponse,
    SearchResponse,
    CodebaseListResponse,
    DeleteResponse,
    CodebaseStats,
    ValidationResponse,
    ErrorResponse,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# Initialize codebase indexer (global instance)
indexer = CodebaseIndexer()

# Background indexing tasks
background_tasks = {}


@router.post(
    "/index/github",
    response_model=IndexingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Index GitHub Repository",
    description="Index a GitHub repository for semantic search"
)
async def index_github_repository(request: GitHubIndexRequest):
    """Index a GitHub repository."""
    try:
        logger.info(f"Received GitHub indexing request: {request.url}")
        
        result = indexer.index_github_repository(
            url=request.url,
            name=request.name
        )
        
        if result['status'] == 'error':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get('error', 'Unknown error')
            )
        
        return IndexingResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing GitHub repository: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/index/zip",
    response_model=IndexingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Index ZIP File",
    description="Upload and index a ZIP file containing code"
)
async def index_zip_file(
    file: UploadFile = File(..., description="ZIP file to index"),
    name: str = None
):
    """Index an uploaded ZIP file."""
    try:
        # Validate file
        if not file.filename.endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a ZIP archive"
            )
        
        # Save uploaded file temporarily
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        
        temp_file_path = temp_dir / file.filename
        
        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        logger.info(f"Saved uploaded file: {temp_file_path}")
        
        # Index the file
        result = indexer.index_zip_file(
            zip_path=str(temp_file_path),
            name=name or Path(file.filename).stem
        )
        
        # Cleanup temp file
        try:
            temp_file_path.unlink()
        except Exception as e:
            logger.warning(f"Could not delete temp file: {e}")
        
        if result['status'] == 'error':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get('error', 'Unknown error')
            )
        
        return IndexingResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing ZIP file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/index/local",
    response_model=IndexingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Index Local Directory",
    description="Index a local directory (server-side path)"
)
async def index_local_directory(request: LocalIndexRequest):
    """Index a local directory."""
    try:
        # Validate path exists
        if not Path(request.path).exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Path does not exist: {request.path}"
            )
        
        logger.info(f"Received local directory indexing request: {request.path}")
        
        result = indexer.index_local_directory(
            path=request.path,
            name=request.name,
            copy_to_temp=request.copy_to_temp
        )
        
        if result['status'] == 'error':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get('error', 'Unknown error')
            )
        
        return IndexingResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing local directory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search Codebase",
    description="Perform semantic search on an indexed codebase"
)
async def search_codebase(request: SearchRequest):
    """Search an indexed codebase."""
    try:
        logger.info(f"Search request: '{request.query}' in {request.codebase_name}")
        
        result = indexer.search(
            query=request.query,
            codebase_name=request.codebase_name,
            top_k=request.top_k,
            search_type=request.search_type,
            filters=request.filters,
            include_context=request.include_context
        )
        
        if 'error' in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['error']
            )
        
        return SearchResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/search/by-type",
    response_model=SearchResponse,
    summary="Search by Chunk Type",
    description="Search for specific types of code chunks (functions, classes, etc.)"
)
async def search_by_type(request: SearchByTypeRequest):
    """Search for specific chunk types."""
    try:
        result = indexer.search(
            query=request.query,
            codebase_name=request.codebase_name,
            top_k=request.top_k,
            filters={'chunk_type': request.chunk_type}
        )
        
        if 'error' in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['error']
            )
        
        return SearchResponse(**result)
        
    except Exception as e:
        logger.error(f"Error in search by type: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/search/by-language",
    response_model=SearchResponse,
    summary="Search by Language",
    description="Search within a specific programming language"
)
async def search_by_language(request: SearchByLanguageRequest):
    """Search within a specific programming language."""
    try:
        result = indexer.search(
            query=request.query,
            codebase_name=request.codebase_name,
            top_k=request.top_k,
            filters={'language': request.language}
        )
        
        if 'error' in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['error']
            )
        
        return SearchResponse(**result)
        
    except Exception as e:
        logger.error(f"Error in search by language: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/list",
    response_model=CodebaseListResponse,
    summary="List Codebases",
    description="Get a list of all indexed codebases"
)
async def list_codebases():
    """List all indexed codebases."""
    try:
        codebases = indexer.list_codebases()
        
        return CodebaseListResponse(
            codebases=codebases,
            total_count=len(codebases)
        )
        
    except Exception as e:
        logger.error(f"Error listing codebases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/stats/{codebase_name}",
    response_model=CodebaseStats,
    summary="Get Codebase Statistics",
    description="Get detailed statistics for a specific codebase"
)
async def get_codebase_stats(codebase_name: str):
    """Get statistics for a specific codebase."""
    try:
        stats = indexer.get_codebase_stats(codebase_name)
        
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Codebase '{codebase_name}' not found"
            )
        
        return CodebaseStats(**stats)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting codebase stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete(
    "/{codebase_name}",
    response_model=DeleteResponse,
    summary="Delete Codebase",
    description="Delete an indexed codebase"
)
async def delete_codebase(codebase_name: str):
    """Delete an indexed codebase."""
    try:
        success = indexer.delete_codebase(codebase_name)
        
        if success:
            return DeleteResponse(
                status="success",
                name=codebase_name,
                success=True,
                message=f"Codebase '{codebase_name}' deleted successfully"
            )
        else:
            return DeleteResponse(
                status="error",
                name=codebase_name,
                success=False,
                message=f"Codebase '{codebase_name}' not found or could not be deleted"
            )
        
    except Exception as e:
        logger.error(f"Error deleting codebase: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="Validate Source",
    description="Validate a source before indexing"
)
async def validate_source(request: ValidationRequest):
    """Validate a source before indexing."""
    try:
        if request.source_type == "github" and request.url:
            valid = indexer.github_source.validate_url(request.url)
            message = "Valid GitHub URL" if valid else "Invalid GitHub URL"
            metadata = indexer.github_source.extract_repo_info(request.url) if valid else None
            
        elif request.source_type == "zip" and request.path:
            valid = indexer.zip_source.validate_zip_file(request.path)
            message = "Valid ZIP file" if valid else "Invalid ZIP file"
            metadata = indexer.zip_source.get_zip_info(request.path) if valid else None
            
        elif request.source_type == "local" and request.path:
            valid = indexer.local_source.validate_path(request.path)
            message = "Valid local directory" if valid else "Invalid local directory"
            metadata = indexer.local_source.get_directory_info(request.path) if valid else None
            
        else:
            valid = False
            message = "Invalid request: missing required parameters"
            metadata = None
        
        return ValidationResponse(
            valid=valid,
            source_type=request.source_type,
            message=message,
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Error validating source: {e}")
        return ValidationResponse(
            valid=False,
            source_type=request.source_type,
            message=f"Validation error: {str(e)}",
            metadata=None
        )


# Note: Exception handlers are defined in the main app.py file