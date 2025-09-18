"""
Configuration settings for the codebase module.
"""

import os
import getpass
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class CodebaseConfig:
    """Configuration class for codebase indexing."""
    
    # Vector database settings (for backward compatibility)
    db_path: str = "./codebase_db"
    
    # PostgreSQL settings
    database_url: str = None
    
    # Supported file extensions
    SUPPORTED_EXTENSIONS: List[str] = None
    
    # Blacklisted directories
    BLACKLIST_DIRS: List[str] = None
    
    # Language-specific settings
    LANGUAGE_MAPPING: Dict[str, str] = None
    
    # Embedding settings
    embedding_model: str = "gemini"  # or "openai"
    embedding_dimensions: int = 768  # Default for Gemini, will be auto-detected
    chunk_size: int = 1000
    chunk_overlap: int = 100
    
    # Search settings
    default_top_k: int = 5
    max_context_tokens: int = 8000
    
    def __post_init__(self):
        """Initialize default values after instance creation."""
        # Set up PostgreSQL database URL from environment variables
        if self.database_url is None:
            host = os.getenv('POSTGRES_HOST', 'localhost')
            port = os.getenv('POSTGRES_PORT', '5432')
            db = os.getenv('POSTGRES_DB', 'codebase_db')
            user = os.getenv('POSTGRES_USER', getpass.getuser())  # Use system user as default
            password = os.getenv('POSTGRES_PASSWORD', '')
            
            if password:
                self.database_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
            else:
                self.database_url = f"postgresql://{user}@{host}:{port}/{db}"
        
        if self.SUPPORTED_EXTENSIONS is None:
            self.SUPPORTED_EXTENSIONS = [
                '.py', '.js', '.jsx', '.ts', '.tsx', '.java', 
                '.go', '.rs', '.cpp', '.c', '.h', '.hpp',
                '.rb', '.php', '.swift', '.kt', '.scala'
            ]
        
        if self.BLACKLIST_DIRS is None:
            self.BLACKLIST_DIRS = [
                '.git', '.svn', '.hg',
                'node_modules', '__pycache__', '.pytest_cache',
                '.venv', 'venv', 'env',
                '.idea', '.vscode', '.vs',
                'build', 'dist', 'target',
                '.next', '.nuxt',
                'coverage', '.coverage',
                'logs', 'log'
            ]
        
        if self.LANGUAGE_MAPPING is None:
            self.LANGUAGE_MAPPING = {
                '.py': 'python',
                '.js': 'javascript',
                '.jsx': 'javascript',
                '.ts': 'typescript',
                '.tsx': 'typescript',
                '.java': 'java',
                '.go': 'go',
                '.rs': 'rust',
                '.cpp': 'cpp',
                '.c': 'c',
                '.h': 'c',
                '.hpp': 'cpp',
                '.rb': 'ruby',
                '.php': 'php',
                '.swift': 'swift',
                '.kt': 'kotlin',
                '.scala': 'scala'
            }


# Default configuration instance
default_config = CodebaseConfig()