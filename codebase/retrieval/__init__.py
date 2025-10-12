"""
Search and retrieval functionality.

This module provides semantic search capabilities, HyDE-enhanced queries,
reranking, and context management for code retrieval.
"""

from .search import SemanticSearch
from .context import ContextManager
from .hyde import HyDEGenerator
from .reranker import CodeReranker, ConfidenceFilter, DiversityFilter

__all__ = [
    "SemanticSearch",
    "ContextManager",
    "HyDEGenerator",
    "CodeReranker",
    "ConfidenceFilter",
    "DiversityFilter"
]