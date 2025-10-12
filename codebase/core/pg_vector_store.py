"""
PostgreSQL vector store with pgvector for code embeddings.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy import text, func, desc
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..models import Codebase, CodeChunk, IndexingHistory
from database import SessionLocal, engine

logger = logging.getLogger(__name__)


@dataclass
class VectorRecord:
    """Record in the vector database - keeping same interface as LanceDB version."""
    id: str
    text: str
    vector: List[float]
    chunk_type: str
    name: str
    file_path: str
    language: str
    line_start: int
    line_end: int
    parent_name: Optional[str] = None
    description: Optional[str] = None
    description_embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None


class PostgreSQLVectorStore:
    """PostgreSQL-based vector store for code embeddings using pgvector."""
    
    def __init__(self, database_url: str = None):
        """
        Initialize PostgreSQL vector store.

        Args:
            database_url: PostgreSQL connection URL (ignored - uses DATABASE_URL from env)
        """
        self._initialized = False
        logger.info("PostgreSQL vector store initialized")
    
    def initialize(self):
        """Initialize database and create tables if needed."""
        if self._initialized:
            return

        try:
            from database import Base, test_connection
            from sqlalchemy import text

            # Test connection
            if not test_connection():
                raise Exception("Database connection failed")

            # Setup pgvector extension
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()

            # Create tables
            Base.metadata.create_all(bind=engine)

            # Create indexes for better performance
            self._create_indexes()

            self._initialized = True
            logger.info("PostgreSQL vector store setup completed")

        except Exception as e:
            logger.error(f"Error initializing PostgreSQL vector store: {e}")
            raise
    
    def _create_indexes(self):
        """Create additional indexes for performance."""
        try:
            session = SessionLocal()
            try:
                # Check if we have enough data for IVFFlat index
                row_count = session.execute(text("SELECT COUNT(*) FROM code_chunks")).scalar()
                
                if row_count >= 1000:  # Only create IVFFlat if we have enough data
                    # Calculate appropriate number of lists (roughly sqrt of rows, capped between 10 and 1000)
                    lists = max(10, min(int(row_count ** 0.5), 1000))
                    
                    index_sql = f"""
                    CREATE INDEX IF NOT EXISTS idx_code_chunks_embedding_cosine 
                    ON code_chunks USING ivfflat (embedding vector_cosine_ops) 
                    WITH (lists = {lists})
                    """
                    session.execute(text(index_sql))
                    session.commit()
                    logger.info(f"Created IVFFlat index with {lists} lists for {row_count} rows")
                else:
                    logger.info(f"Skipping IVFFlat index creation - only {row_count} rows (need at least 1000)")

                # Additional indexes for common queries
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_code_chunks_language ON code_chunks(language)",
                    "CREATE INDEX IF NOT EXISTS idx_code_chunks_chunk_type ON code_chunks(chunk_type)",
                    "CREATE INDEX IF NOT EXISTS idx_code_chunks_name ON code_chunks(name)",
                    "CREATE INDEX IF NOT EXISTS idx_code_chunks_parent_name ON code_chunks(parent_name)",
                ]

                for index_sql in indexes:
                    session.execute(text(index_sql))

                session.commit()
                logger.info("Created vector and query indexes")
            finally:
                session.close()
                
        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")
    
    def create_codebase_table(self, codebase_name: str) -> str:
        """
        Create a codebase entry (equivalent to table in LanceDB).
        
        Args:
            codebase_name: Name of the codebase
            
        Returns:
            Table name (for compatibility)
        """
        if not self._initialized:
            self.initialize()
        
        try:
            session = SessionLocal()
            try:
                # Check if codebase already exists
                existing = session.query(Codebase).filter(Codebase.name == codebase_name).first()

                if existing:
                    # Delete existing codebase and all chunks
                    logger.info(f"Deleting existing codebase: {codebase_name}")
                    session.delete(existing)
                    session.commit()

                # Create new codebase entry
                codebase = Codebase(name=codebase_name)
                session.add(codebase)
                session.commit()

                logger.info(f"Created codebase: {codebase_name}")
                return f"codebase_{codebase_name}"
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error creating codebase {codebase_name}: {e}")
            raise
    
    def insert_records(self, codebase_name: str, records: List[VectorRecord], batch_size: int = 1000) -> bool:
        """
        Insert records into the codebase in batches.
        
        Args:
            codebase_name: Name of the codebase
            records: List of VectorRecord objects
            batch_size: Number of records to insert per batch
            
        Returns:
            True if successful
        """
        if not records:
            logger.warning("No records to insert")
            return True
        
        if not self._initialized:
            self.initialize()
        
        total_inserted = 0
        
        try:
            session = SessionLocal()
            try:
                # Get codebase
                codebase = session.query(Codebase).filter(Codebase.name == codebase_name).first()
                if not codebase:
                    # Create codebase if it doesn't exist
                    codebase = Codebase(name=codebase_name)
                    session.add(codebase)
                    session.flush()  # Get the ID
                
                # Process records in batches
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    
                    try:
                        # Convert VectorRecord objects to CodeChunk models
                        chunks = []
                        for record in batch:
                            chunk = CodeChunk(
                                codebase_id=codebase.id,
                                text=record.text,
                                embedding=record.vector,
                                chunk_type=record.chunk_type,
                                name=record.name,
                                file_path=record.file_path,
                                language=record.language,
                                line_start=record.line_start,
                                line_end=record.line_end,
                                parent_name=record.parent_name,
                                description=record.description,
                                description_embedding=record.description_embedding,
                                meta_info=record.metadata
                            )
                            chunks.append(chunk)
                        
                        # Insert batch
                        session.add_all(chunks)
                        session.commit()
                        
                        total_inserted += len(batch)
                        logger.debug(f"Inserted batch {i//batch_size + 1}: {len(batch)} records")
                        
                    except Exception as batch_error:
                        logger.error(f"Error inserting batch {i//batch_size + 1}: {batch_error}")
                        session.rollback()
                        
                        # Try inserting records one by one if batch fails
                        for record in batch:
                            try:
                                chunk = CodeChunk(
                                    codebase_id=codebase.id,
                                    text=record.text,
                                    embedding=record.vector,
                                    chunk_type=record.chunk_type,
                                    name=record.name,
                                    file_path=record.file_path,
                                    language=record.language,
                                    line_start=record.line_start,
                                    line_end=record.line_end,
                                    parent_name=record.parent_name,
                                    description=record.description,
                                    description_embedding=record.description_embedding,
                                    meta_info=record.metadata
                                )
                                session.add(chunk)
                                session.commit()
                                total_inserted += 1
                                
                            except Exception as record_error:
                                logger.warning(f"Failed to insert single record {record.id}: {record_error}")
                                session.rollback()
                                continue
                
                logger.info(f"Inserted {total_inserted}/{len(records)} records into {codebase_name}")

                # Update indexes after bulk insert if we have enough data
                if total_inserted >= 1000:
                    logger.info("Updating vector indexes after bulk insert...")
                    self._create_indexes()

                return total_inserted > 0
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error inserting records: {e}")
            return False
    
    def search(
        self,
        codebase_name: str,
        query_vector: List[float],
        top_k: int = 5,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in a codebase.

        Args:
            codebase_name: Name of the codebase
            query_vector: Query vector
            top_k: Number of results to return
            filters: Optional filters to apply

        Returns:
            List of search results
        """
        # Note: No initialization needed for search - tables should already exist
        
        try:
            session = SessionLocal()
            try:
                # Get codebase
                codebase = session.query(Codebase).filter(Codebase.name == codebase_name).first()
                if not codebase:
                    logger.warning(f"Codebase {codebase_name} not found")
                    return []
                
                # Build query
                query = session.query(CodeChunk).filter(CodeChunk.codebase_id == codebase.id)
                
                # Apply filters
                if filters:
                    if 'chunk_type' in filters:
                        query = query.filter(CodeChunk.chunk_type == filters['chunk_type'])
                    if 'language' in filters:
                        query = query.filter(CodeChunk.language == filters['language'])
                    if 'parent_name' in filters:
                        query = query.filter(CodeChunk.parent_name == filters['parent_name'])
                
                # Add vector similarity search with distance
                query = query.add_columns(
                    CodeChunk.embedding.cosine_distance(query_vector).label('distance')
                ).order_by(CodeChunk.embedding.cosine_distance(query_vector)).limit(top_k)
                
                results = query.all()
                
                # Convert to result format
                search_results = []
                for chunk, distance in results:
                    result = {
                        'id': str(chunk.id),
                        'text': chunk.text,
                        'chunk_type': chunk.chunk_type,
                        'name': chunk.name,
                        'file_path': chunk.file_path,
                        'language': chunk.language,
                        'line_start': chunk.line_start,
                        'line_end': chunk.line_end,
                        'parent_name': chunk.parent_name,
                        'description': chunk.description,
                        'score': float(distance)  # Cosine distance
                    }
                    search_results.append(result)

                return search_results
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error searching in {codebase_name}: {e}")
            return []

    def search_by_description(
        self,
        codebase_name: str,
        query_vector: List[float],
        top_k: int = 5,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors using description embeddings.

        Args:
            codebase_name: Name of the codebase
            query_vector: Query vector (natural language embedding)
            top_k: Number of results to return
            filters: Optional filters to apply

        Returns:
            List of search results
        """
        try:
            session = SessionLocal()
            try:
                # Get codebase
                codebase = session.query(Codebase).filter(Codebase.name == codebase_name).first()
                if not codebase:
                    logger.warning(f"Codebase {codebase_name} not found")
                    return []

                # Build query - only search chunks with description_embedding
                query = session.query(CodeChunk).filter(
                    CodeChunk.codebase_id == codebase.id,
                    CodeChunk.description_embedding.isnot(None)
                )

                # Apply filters
                if filters:
                    if 'chunk_type' in filters:
                        query = query.filter(CodeChunk.chunk_type == filters['chunk_type'])
                    if 'language' in filters:
                        query = query.filter(CodeChunk.language == filters['language'])
                    if 'parent_name' in filters:
                        query = query.filter(CodeChunk.parent_name == filters['parent_name'])

                # Add vector similarity search with distance
                query = query.add_columns(
                    CodeChunk.description_embedding.cosine_distance(query_vector).label('distance')
                ).order_by(CodeChunk.description_embedding.cosine_distance(query_vector)).limit(top_k)

                results = query.all()

                # Convert to result format
                search_results = []
                for chunk, distance in results:
                    result = {
                        'id': str(chunk.id),
                        'text': chunk.text,
                        'chunk_type': chunk.chunk_type,
                        'name': chunk.name,
                        'file_path': chunk.file_path,
                        'language': chunk.language,
                        'line_start': chunk.line_start,
                        'line_end': chunk.line_end,
                        'parent_name': chunk.parent_name,
                        'description': chunk.description,
                        'score': float(distance)  # Cosine distance
                    }
                    search_results.append(result)

                logger.info(f"Description search found {len(search_results)} results in {codebase_name}")
                return search_results
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error in description search for {codebase_name}: {e}")
            return []

    def list_codebases(self) -> List[Dict[str, Any]]:
        """
        List all indexed codebases.
        
        Returns:
            List of codebase information
        """
        if not self._initialized:
            self.initialize()
        
        try:
            session = SessionLocal()
            try:
                # Get codebases with statistics
                codebases = session.query(Codebase).all()
                
                results = []
                for codebase in codebases:
                    # Get chunk statistics
                    chunk_stats = session.query(
                        CodeChunk.language,
                        CodeChunk.chunk_type,
                        func.count(CodeChunk.id).label('count')
                    ).filter(
                        CodeChunk.codebase_id == codebase.id
                    ).group_by(CodeChunk.language, CodeChunk.chunk_type).all()
                    
                    # Organize stats
                    languages = {}
                    chunk_types = {}
                    total_chunks = 0
                    
                    for lang, chunk_type, count in chunk_stats:
                        languages[lang] = languages.get(lang, 0) + count
                        chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + count
                        total_chunks += count
                    
                    codebase_info = {
                        'name': codebase.name,
                        'table_name': f"codebase_{codebase.name}",
                        'total_chunks': total_chunks,
                        'languages': languages,
                        'chunk_types': chunk_types
                    }
                    results.append(codebase_info)

                return results
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error listing codebases: {e}")
            return []
    
    def delete_codebase(self, codebase_name: str) -> bool:
        """
        Delete a codebase and all its chunks.
        
        Args:
            codebase_name: Name of the codebase to delete
            
        Returns:
            True if successful
        """
        if not self._initialized:
            self.initialize()
        
        try:
            session = SessionLocal()
            try:
                codebase = session.query(Codebase).filter(Codebase.name == codebase_name).first()
                if codebase:
                    session.delete(codebase)  # Cascading delete will remove chunks
                    session.commit()
                    logger.info(f"Deleted codebase: {codebase_name}")
                    return True
                else:
                    logger.warning(f"Codebase {codebase_name} not found")
                    return False
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error deleting codebase {codebase_name}: {e}")
            return False
    
    def get_codebase_stats(self, codebase_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific codebase.
        
        Args:
            codebase_name: Name of the codebase
            
        Returns:
            Dictionary containing statistics
        """
        if not self._initialized:
            self.initialize()
        
        try:
            session = SessionLocal()
            try:
                codebase = session.query(Codebase).filter(Codebase.name == codebase_name).first()
                if not codebase:
                    return {}
                
                # Get detailed statistics
                stats_query = session.query(
                    func.count(CodeChunk.id).label('total_chunks'),
                    func.count(func.distinct(CodeChunk.file_path)).label('files'),
                    func.avg(func.length(CodeChunk.text)).label('avg_chunk_size')
                ).filter(CodeChunk.codebase_id == codebase.id)
                
                stats_result = stats_query.first()
                
                # Get language distribution
                lang_stats = session.query(
                    CodeChunk.language,
                    func.count(CodeChunk.id).label('count')
                ).filter(
                    CodeChunk.codebase_id == codebase.id
                ).group_by(CodeChunk.language).all()
                
                languages = {lang: count for lang, count in lang_stats}
                
                # Get chunk type distribution
                type_stats = session.query(
                    CodeChunk.chunk_type,
                    func.count(CodeChunk.id).label('count')
                ).filter(
                    CodeChunk.codebase_id == codebase.id
                ).group_by(CodeChunk.chunk_type).all()
                
                chunk_types = {chunk_type: count for chunk_type, count in type_stats}
                
                # Get largest file
                largest_file_query = session.query(
                    CodeChunk.file_path
                ).filter(
                    CodeChunk.codebase_id == codebase.id
                ).order_by(desc(func.length(CodeChunk.text))).first()
                
                stats = {
                    'name': codebase_name,
                    'total_chunks': stats_result.total_chunks or 0,
                    'languages': languages,
                    'chunk_types': chunk_types,
                    'files': stats_result.files or 0,
                    'avg_chunk_size': float(stats_result.avg_chunk_size) if stats_result.avg_chunk_size else 0,
                    'largest_file': largest_file_query[0] if largest_file_query else None
                }

                return stats
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error getting stats for {codebase_name}: {e}")
            return {}
    
    def close(self):
        """Close the database connection."""
        try:
            self.db.close()
            logger.info("PostgreSQL vector store closed")
        except Exception as e:
            logger.error(f"Error closing PostgreSQL vector store: {e}")


# Create alias for backward compatibility
VectorStore = PostgreSQLVectorStore