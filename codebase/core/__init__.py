"""
Core functionality for codebase processing.

This module contains the core components for parsing, preprocessing,
embedding generation, vector storage, and relationship extraction.
"""

from .parser import CodeParser
from .preprocessor import FilePreprocessor
from .embeddings import EmbeddingGenerator
from .relationship_extractor import CodeRelationshipExtractor
from .relationship_store import RelationshipStore

# Import PostgreSQL vector store as the default
from .pg_vector_store import PostgreSQLVectorStore as VectorStore, VectorRecord

# Keep old LanceDB version available for backward compatibility (if available)
try:
    from .vector_store import VectorStore as LanceDBVectorStore
except ImportError:
    # LanceDB not available, skip import
    LanceDBVectorStore = None

__all__ = [
    "CodeParser",
    "FilePreprocessor",
    "EmbeddingGenerator",
    "VectorStore",
    "VectorRecord",
    "LanceDBVectorStore",
    "CodeRelationshipExtractor",
    "RelationshipStore"
]