"""
Supabase database configuration and connection management.
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator, Optional, Dict, Any
from supabase import create_client, Client
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from .models import Base

logger = logging.getLogger(__name__)


class SupabaseDatabaseManager:
    """Manages Supabase PostgreSQL database connections and operations."""
    
    def __init__(self):
        """Initialize Supabase database manager."""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.database_url = self._build_database_url()
        self.supabase_client: Optional[Client] = None
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
    
    def _build_database_url(self) -> str:
        """Build database URL from environment variables for SQLAlchemy."""
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "postgres")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        
        print(f"host: {host}, port: {port}, database: {database}, user: {user}, password: {password}")
        
        if password:
            return f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode=require"
        else:
            logger.warning("POSTGRES_PASSWORD not set")
            return f"postgresql://{user}@{host}:{port}/{database}?sslmode=require"
    
    def initialize(self):
        """Initialize Supabase client and database engine."""
        if self._initialized:
            return
        
        try:
            # Initialize Supabase client
            if self.supabase_url and self.supabase_key:
                self.supabase_client = create_client(self.supabase_url, self.supabase_key)
                logger.info("Supabase client initialized successfully")
            else:
                logger.warning("SUPABASE_URL or SUPABASE_KEY not provided")
                raise Exception("Supabase credentials missing")
            
            # Initialize SQLAlchemy engine for direct database operations
            # This is needed for pgvector and complex queries
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                echo=False
            )
            
            self.SessionLocal = sessionmaker(
                autocommit=False, 
                autoflush=False, 
                bind=self.engine
            )
            
            self._initialized = True
            logger.info("Supabase database connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase database: {e}")
            raise
    
    def create_database_if_not_exists(self):
        """Supabase databases are pre-created, so this validates the connection."""
        try:
            # Test connection to the database
            temp_engine = create_engine(self.database_url)
            with temp_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                if result.fetchone():
                    logger.info("Successfully connected to Supabase PostgreSQL database")
            temp_engine.dispose()
            
        except Exception as e:
            logger.error(f"Error connecting to Supabase database: {e}")
            logger.error("Make sure your Supabase connection details are correct")
            raise
    
    def setup_pgvector(self):
        """Set up pgvector extension."""
        try:
            with self.get_session() as session:
                # Create pgvector extension
                session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                session.commit()
                logger.info("pgvector extension enabled in Supabase")
                
        except Exception as e:
            logger.error(f"Error setting up pgvector in Supabase: {e}")
            logger.info("Note: pgvector may already be enabled in Supabase")
            raise
    
    def create_tables(self):
        """Create all database tables."""
        try:
            self.initialize()
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully in Supabase")
            
        except Exception as e:
            logger.error(f"Error creating tables in Supabase: {e}")
            raise
    
    def drop_tables(self):
        """Drop all database tables."""
        try:
            self.initialize()
            Base.metadata.drop_all(bind=self.engine)
            logger.info("Database tables dropped successfully in Supabase")
            
        except Exception as e:
            logger.error(f"Error dropping tables in Supabase: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        if not self._initialized:
            self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            if not self._initialized:
                self.initialize()
                
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                logger.info("Supabase database connection test successful")
                return True
                
        except Exception as e:
            logger.error(f"Supabase database connection test failed: {e}")
            return False
    
    def get_connection_info(self) -> dict:
        """Get database connection information."""
        try:
            if not self._initialized:
                self.initialize()
                
            with self.get_session() as session:
                # Get PostgreSQL version
                version = session.execute(text("SELECT version()")).scalar()
                
                # Get current database name
                db_name = session.execute(text("SELECT current_database()")).scalar()
                
                # Get current user
                user = session.execute(text("SELECT current_user")).scalar()
                
                # Check if pgvector extension is available
                pgvector_info = None
                try:
                    pgvector_version = session.execute(
                        text("SELECT extversion FROM pg_extension WHERE extname='vector'")
                    ).scalar()
                    if pgvector_version:
                        pgvector_info = f"v{pgvector_version}"
                    else:
                        # Check if extension is available but not installed
                        available = session.execute(
                            text("SELECT name FROM pg_available_extensions WHERE name='vector'")
                        ).scalar()
                        pgvector_info = "available but not installed" if available else "not available"
                except Exception:
                    pgvector_info = "unknown"
                
                return {
                    "provider": "Supabase",
                    "postgresql_version": version.split(',')[0] if version else "unknown",
                    "database_name": db_name,
                    "user": user,
                    "pgvector": pgvector_info,
                    "supabase_client": "initialized" if self.supabase_client else "not initialized",
                    "connection_url_masked": self.database_url.replace(
                        self.database_url.split('@')[0].split('//')[1], 
                        "***:***"
                    ) if '@' in self.database_url else self.database_url
                }
                
        except Exception as e:
            logger.error(f"Error getting connection info: {e}")
            return {"error": str(e)}
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        try:
            with self.get_session() as session:
                # Get table counts
                codebases_count = session.execute(
                    text("SELECT COUNT(*) FROM codebases")
                ).scalar()
                
                chunks_count = session.execute(
                    text("SELECT COUNT(*) FROM code_chunks")
                ).scalar()
                
                # Get database size
                db_size = session.execute(
                    text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                ).scalar()
                
                return {
                    "provider": "Supabase",
                    "codebases_count": codebases_count,
                    "chunks_count": chunks_count,
                    "database_size": db_size,
                    "connection_url": self.database_url.replace(
                        self.database_url.split('@')[0].split('//')[1], 
                        "***:***"
                    )  # Hide credentials
                }
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {"error": str(e)}
    
    def close(self):
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
            logger.info("Supabase database connections closed")


# Global Supabase database manager instance
supabase_db_manager = SupabaseDatabaseManager()