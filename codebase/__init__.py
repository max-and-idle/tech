"""
Codebase indexing and search module.

This module provides functionality to index codebases from various sources
(GitHub, ZIP files, local directories) and perform semantic search on them.
"""

from .indexer import CodebaseIndexer
from .config import CodebaseConfig

__version__ = "1.0.0"
__all__ = ["CodebaseIndexer", "CodebaseConfig"]