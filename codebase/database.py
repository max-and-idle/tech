"""
Database configuration and connection management for PostgreSQL.
"""

import os
import logging
import getpass
from contextlib import contextmanager
from typing import Generator
from urllib.parse import urlparse, urlunparse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL database connections and operations."""
    
    def __init__(self, database_url: str = None):
        """
        Initialize database manager.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url or self._build_database_url()
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
    
    def _build_database_url(self) -> str:
        """Build database URL from environment variables."""
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "codebase_db")
        user = os.getenv("POSTGRES_USER", getpass.getuser())  # Use system user as default
        password = os.getenv("POSTGRES_PASSWORD", "")

        print(f"host: {host}, port: {port}, database: {database}, user: {user}, password: {password}")
        
        if password:
            return f"postgresql://{user}:{password}@{host}:{port}/{database}"
        else:
            logger.info(f"POSTGRES_PASSWORD not set. Using peer authentication for user '{user}'.")
            return f"postgresql://{user}@{host}:{port}/{database}"
    
    def initialize(self):
        """Initialize database engine and session factory."""
        if self._initialized:
            return
        
        try:
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                echo=False  # Set to True for SQL debugging
            )
            
            self.SessionLocal = sessionmaker(
                autocommit=False, 
                autoflush=False, 
                bind=self.engine
            )
            
            self._initialized = True
            logger.info("Database connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def create_database_if_not_exists(self):
        """Create the database if it doesn't exist."""
        try:
            # Parse database URL properly
            parsed_url = urlparse(self.database_url)
            database_name = parsed_url.path.lstrip('/')
            
            # Create URL for connecting to default database (postgres or template1)
            default_db_url = urlunparse(parsed_url._replace(path='/postgres'))
            
            # Try connecting to postgres first, then template1 if postgres doesn't exist
            temp_engine = None
            for default_db in ['postgres', 'template1']:
                try:
                    test_url = urlunparse(parsed_url._replace(path=f'/{default_db}'))
                    temp_engine = create_engine(test_url, isolation_level='AUTOCOMMIT')
                    
                    # Test connection
                    with temp_engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    break
                    
                except Exception as e:
                    if temp_engine:
                        temp_engine.dispose()
                    temp_engine = None
                    logger.debug(f"Failed to connect to {default_db}: {e}")
                    continue
            
            if not temp_engine:
                raise Exception("Could not connect to any default PostgreSQL database")
            
            with temp_engine.connect() as conn:
                # Check if database exists
                result = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :dbname"), 
                    {"dbname": database_name}
                )
                
                if not result.fetchone():
                    # Database doesn't exist, create it
                    conn.execute(text(f'CREATE DATABASE "{database_name}"'))
                    logger.info(f"Created database: {database_name}")
                else:
                    logger.info(f"Database {database_name} already exists")
            
            temp_engine.dispose()
            
        except Exception as e:
            logger.error(f"Error creating database: {e}")
            logger.error("Make sure PostgreSQL is running and accessible")
            # Re-raise to make database creation issues visible
            raise
    
    def setup_pgvector(self):
        """Set up pgvector extension."""
        try:
            with self.get_session() as session:
                # Create pgvector extension
                session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                session.commit()
                logger.info("pgvector extension enabled")
                
        except Exception as e:
            logger.error(f"Error setting up pgvector: {e}")
            raise
    
    def create_tables(self):
        """Create all database tables."""
        try:
            self.initialize()
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
            
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    def drop_tables(self):
        """Drop all database tables."""
        try:
            self.initialize()
            Base.metadata.drop_all(bind=self.engine)
            logger.info("Database tables dropped successfully")
            
        except Exception as e:
            logger.error(f"Error dropping tables: {e}")
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
                logger.info("Database connection test successful")
                return True
                
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
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
                    "postgresql_version": version.split(',')[0] if version else "unknown",
                    "database_name": db_name,
                    "user": user,
                    "pgvector": pgvector_info,
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
            logger.info("Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()