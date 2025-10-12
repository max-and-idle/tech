"""
FastAPI application for the Tech API.
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

# Load environment variables early
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

from routers import codebase_router
from models.codebase_models import HealthResponse, ErrorResponse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def initialize_database():
    """Initialize and test database connection."""
    logger.info("🔄 Initializing database connection...")

    try:
        from database import test_connection, engine
        from sqlalchemy import text

        # Test basic connection
        logger.info("🔌 Testing database connection...")
        if not test_connection():
            raise Exception("Database connection test failed")

        # Setup pgvector extension
        logger.info("🧩 Setting up pgvector extension...")
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                logger.info("pgvector extension enabled")
        except Exception as e:
            logger.warning(f"Could not setup pgvector: {e}")

        # Create tables if they don't exist
        logger.info("📋 Creating database tables...")
        try:
            from database import Base
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.warning(f"Could not create tables: {e}")

        # Get database information
        logger.info("📊 Getting database information...")
        try:
            with engine.connect() as conn:
                version = conn.execute(text("SELECT version()")).scalar()
                db_name = conn.execute(text("SELECT current_database()")).scalar()
                user = conn.execute(text("SELECT current_user")).scalar()

                logger.info(f"✅ Database initialized successfully!")
                logger.info(f"   - PostgreSQL version: {version.split(',')[0] if version else 'unknown'}")
                logger.info(f"   - Database: {db_name}")
                logger.info(f"   - User: {user}")
                logger.info(f"   - Connection: {os.getenv('DATABASE_URL', 'Not set')[:50]}...")

        except Exception as e:
            logger.warning(f"Could not get database info: {e}")
            logger.info("✅ Database connection established (info unavailable)")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.error("💡 Please check your DATABASE_URL configuration:")
        logger.error(f"   - DATABASE_URL: {os.getenv('DATABASE_URL', 'Not set')[:50]}...")
        logger.error("   - Make sure PostgreSQL server is running")
        logger.error("   - Check your .env file configuration")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Tech API server...")
    
    # Create necessary directories
    directories = ["temp_uploads", "codebase_db", ".embedding_cache"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    # Initialize and test PostgreSQL database connection
    await initialize_database()
    
    # Log configuration
    logger.info(f"Database path: {os.getenv('CODEBASE_DB_PATH', './codebase_db')}")
    logger.info(f"Embedding model: {os.getenv('EMBEDDING_MODEL', 'gemini')}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Tech API server...")
    
    # Cleanup
    try:
        from routers.codebase_router import indexer
        indexer.cleanup()
        logger.info("Cleanup completed")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


# Create FastAPI app
app = FastAPI(
    title="Tech API",
    description="API for codebase indexing and semantic search",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests."""
    start_time = datetime.now()
    
    # Log request
    logger.info(f"{request.method} {request.url.path} - Client: {request.client.host}")
    
    response = await call_next(request)
    
    # Log response
    process_time = datetime.now() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time.total_seconds():.3f}s"
    )
    
    return response


# Include routers
app.include_router(
    codebase_router.router, 
    prefix="/api/codebase", 
    tags=["codebase"]
)


# Root endpoints
@app.get("/", summary="Root Endpoint")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Tech API",
        "version": "1.0.0",
        "description": "API for codebase indexing and semantic search",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "endpoints": {
            "codebase": "/api/codebase"
        }
    }


@app.get("/health", response_model=HealthResponse, summary="Health Check")
async def health_check():
    """Health check endpoint with PostgreSQL database status."""
    try:
        from database import test_connection, engine
        from sqlalchemy import text

        # Test database connection
        db_healthy = test_connection()

        # Get database info if connection is healthy
        db_info = {}
        if db_healthy:
            try:
                with engine.connect() as conn:
                    version = conn.execute(text("SELECT version()")).scalar()
                    db_name = conn.execute(text("SELECT current_database()")).scalar()
                    user = conn.execute(text("SELECT current_user")).scalar()

                    # Check pgvector extension
                    pgvector_version = conn.execute(
                        text("SELECT extversion FROM pg_extension WHERE extname='vector'")
                    ).scalar()

                    db_info = {
                        "postgresql_version": version.split(',')[0] if version else 'unknown',
                        "database": db_name,
                        "user": user,
                        "pgvector": f"v{pgvector_version}" if pgvector_version else "not installed"
                    }
            except Exception as e:
                db_info = {"info_error": str(e)}

        # Determine overall status
        status = "healthy" if db_healthy else "degraded"
        message = "All systems operational" if db_healthy else "Database connection failed"

        return HealthResponse(
            status=status,
            message=message,
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            details={
                "database": {
                    "status": "connected" if db_healthy else "disconnected",
                    **db_info
                },
                "components": {
                    "codebase_indexer": "available",
                    "embeddings": "available",
                    "vector_store": "postgresql"
                }
            }
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            message=f"Health check failed: {str(e)}",
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            details={"error": str(e)}
        )


# Error handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.warning(f"Validation error for {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "detail": exc.errors(),
            "body": exc.body
        }
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not found",
            "detail": f"The endpoint {request.url.path} was not found",
            "suggestion": "Check the API documentation at /docs"
        }
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred",
            "request_id": str(datetime.now().timestamp())
        }
    )


# Optional: Serve static files for a simple frontend
if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


# Development server configuration
if __name__ == "__main__":
    import uvicorn
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run development server
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )