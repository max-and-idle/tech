"""
Vector database operations using LanceDB.
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass, asdict
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import lancedb
    import pyarrow as pa
except ImportError:
    logger.error("lancedb and pyarrow are required. Install with: pip install lancedb pyarrow")
    raise


@dataclass
class VectorRecord:
    """Record in the vector database."""
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
    docstring: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class VectorStore:
    """LanceDB-based vector store for code embeddings."""
    
    def __init__(self, db_path: str = "./codebase_db"):
        """
        Initialize vector store.
        
        Args:
            db_path: Path to the LanceDB database
        """
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        try:
            self.db = lancedb.connect(str(self.db_path))
            logger.info(f"Connected to LanceDB at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to LanceDB: {e}")
            raise
        
        self.tables = {}
    
    def create_codebase_table(self, codebase_name: str) -> str:
        """
        Create a table for a specific codebase.
        
        Args:
            codebase_name: Name of the codebase
            
        Returns:
            Table name
        """
        table_name = f"codebase_{codebase_name.replace('-', '_').replace(' ', '_').lower()}"
        
        # Create table without predefined schema - let LanceDB infer it
        # This avoids PyArrow version compatibility issues
        empty_data = []
        
        # Create empty table
        try:
            # Drop existing table if it exists
            if table_name in self.db.table_names():
                self.db.drop_table(table_name)
                logger.info(f"Dropped existing table: {table_name}")
            
            # Create new table - we'll add schema when inserting data
            # This is a placeholder that will be replaced when data is added
            self.tables[codebase_name] = None
            logger.info(f"Prepared table creation: {table_name}")
            return table_name
            
        except Exception as e:
            logger.error(f"Error creating table {table_name}: {e}")
            raise
    
    def insert_records(self, codebase_name: str, records: List[VectorRecord]) -> bool:
        """
        Insert records into a codebase table.
        
        Args:
            codebase_name: Name of the codebase
            records: List of VectorRecord objects
            
        Returns:
            True if successful
        """
        if not records:
            logger.warning("No records to insert")
            return True
        
        table_name = f"codebase_{codebase_name.replace('-', '_').replace(' ', '_').lower()}"
        
        try:
            # Get or create table
            if table_name not in self.db.table_names():
                # Table doesn't exist, create it with data
                df = self._records_to_dataframe(records)
                table = self.db.create_table(table_name, df)
                self.tables[codebase_name] = table
                logger.info(f"Created new table {table_name} with {len(records)} records")
                return True
            else:
                # Table exists, open it
                if codebase_name not in self.tables or self.tables[codebase_name] is None:
                    self.tables[codebase_name] = self.db.open_table(table_name)
                table = self.tables[codebase_name]
            
            # Add records to existing table
            df = self._records_to_dataframe(records)
            table.add(df)
            logger.info(f"Inserted {len(records)} records into {table_name}")
            return True
            
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
        table_name = f"codebase_{codebase_name.replace('-', '_').replace(' ', '_').lower()}"
        
        try:
            if table_name not in self.db.table_names():
                logger.warning(f"Table {table_name} not found")
                return []
            
            table = self.db.open_table(table_name)
            
            # Build search query
            search_query = table.search(query_vector).limit(top_k)
            
            # Apply filters if provided
            if filters:
                for key, value in filters.items():
                    if key in ['chunk_type', 'language', 'parent_name']:
                        search_query = search_query.where(f"{key} = '{value}'")
            
            # Execute search
            results = search_query.to_pandas()
            
            # Convert to list of dictionaries
            search_results = []
            for _, row in results.iterrows():
                result = {
                    'id': row['id'],
                    'text': row['text'],
                    'chunk_type': row['chunk_type'],
                    'name': row['name'],
                    'file_path': row['file_path'],
                    'language': row['language'],
                    'line_start': row['line_start'],
                    'line_end': row['line_end'],
                    'parent_name': row['parent_name'] if row['parent_name'] else None,
                    'docstring': row['docstring'] if row['docstring'] else None,
                    'score': row.get('_distance', 0.0)  # Distance score from LanceDB
                }
                search_results.append(result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching in {table_name}: {e}")
            return []
    
    def list_codebases(self) -> List[Dict[str, Any]]:
        """
        List all indexed codebases.
        
        Returns:
            List of codebase information
        """
        try:
            codebases = []
            
            for table_name in self.db.table_names():
                if table_name.startswith('codebase_'):
                    codebase_name = table_name.replace('codebase_', '').replace('_', '-')
                    
                    table = self.db.open_table(table_name)
                    count = table.count_rows()
                    
                    # Get some basic stats
                    if count > 0:
                        df = table.to_pandas()
                        languages = df['language'].value_counts().to_dict()
                        chunk_types = df['chunk_type'].value_counts().to_dict()
                    else:
                        languages = {}
                        chunk_types = {}
                    
                    codebase_info = {
                        'name': codebase_name,
                        'table_name': table_name,
                        'total_chunks': count,
                        'languages': languages,
                        'chunk_types': chunk_types
                    }
                    codebases.append(codebase_info)
            
            return codebases
            
        except Exception as e:
            logger.error(f"Error listing codebases: {e}")
            return []
    
    def delete_codebase(self, codebase_name: str) -> bool:
        """
        Delete a codebase and its table.
        
        Args:
            codebase_name: Name of the codebase to delete
            
        Returns:
            True if successful
        """
        table_name = f"codebase_{codebase_name.replace('-', '_').replace(' ', '_').lower()}"
        
        try:
            if table_name in self.db.table_names():
                self.db.drop_table(table_name)
                
                # Remove from cached tables
                if codebase_name in self.tables:
                    del self.tables[codebase_name]
                
                logger.info(f"Deleted codebase: {codebase_name}")
                return True
            else:
                logger.warning(f"Codebase {codebase_name} not found")
                return False
                
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
        table_name = f"codebase_{codebase_name.replace('-', '_').replace(' ', '_').lower()}"
        
        try:
            if table_name not in self.db.table_names():
                return {}
            
            table = self.db.open_table(table_name)
            df = table.to_pandas()
            
            if len(df) == 0:
                return {'name': codebase_name, 'total_chunks': 0}
            
            stats = {
                'name': codebase_name,
                'total_chunks': len(df),
                'languages': df['language'].value_counts().to_dict(),
                'chunk_types': df['chunk_type'].value_counts().to_dict(),
                'files': df['file_path'].nunique(),
                'avg_chunk_size': df['text'].str.len().mean(),
                'largest_file': df.loc[df['text'].str.len().idxmax(), 'file_path'] if len(df) > 0 else None
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting stats for {codebase_name}: {e}")
            return {}
    
    def _records_to_dataframe(self, records: List[VectorRecord]) -> pd.DataFrame:
        """Convert VectorRecord objects to pandas DataFrame."""
        data = []
        for record in records:
            row = {
                'id': record.id,
                'text': record.text,
                'vector': record.vector,
                'chunk_type': record.chunk_type,
                'name': record.name,
                'file_path': record.file_path,
                'language': record.language,
                'line_start': record.line_start,
                'line_end': record.line_end,
                'parent_name': record.parent_name or "",
                'docstring': record.docstring or "",
                'metadata': str(record.metadata or {})
            }
            data.append(row)
        
        return pd.DataFrame(data)
    
    def close(self):
        """Close the database connection."""
        try:
            # LanceDB doesn't have an explicit close method
            self.tables.clear()
            logger.info("Closed vector store")
        except Exception as e:
            logger.error(f"Error closing vector store: {e}")