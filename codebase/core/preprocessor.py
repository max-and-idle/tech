"""
File preprocessing for codebase indexing.
"""

import os
import hashlib
from pathlib import Path
from typing import List, Dict, Generator, Tuple, Optional
from dataclasses import dataclass
import logging
from tqdm import tqdm

from ..config import CodebaseConfig

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Information about a file in the codebase."""
    path: str
    relative_path: str
    language: str
    size: int
    hash: str


class FilePreprocessor:
    """Handles file traversal, filtering, and preprocessing."""
    
    def __init__(self, config: CodebaseConfig = None):
        """Initialize preprocessor with configuration."""
        self.config = config or CodebaseConfig()
    
    def scan_directory(self, root_path: str) -> List[FileInfo]:
        """
        Scan directory and return information about all supported files.
        
        Args:
            root_path: Root directory to scan
            
        Returns:
            List of FileInfo objects for supported files
        """
        root_path = Path(root_path).resolve()
        files = []
        
        logger.info(f"Scanning directory: {root_path}")
        
        # Collect all files first to show progress
        all_files = []
        for file_path in root_path.rglob('*'):
            if file_path.is_file():
                all_files.append(file_path)
        
        # Process files with progress bar
        for file_path in tqdm(all_files, desc="Processing files"):
            try:
                file_info = self._process_file(file_path, root_path)
                if file_info:
                    files.append(file_info)
            except Exception as e:
                logger.warning(f"Error processing {file_path}: {e}")
        
        logger.info(f"Found {len(files)} supported files")
        return files
    
    def _process_file(self, file_path: Path, root_path: Path) -> Optional[FileInfo]:
        """
        Process a single file and return FileInfo if supported.
        
        Args:
            file_path: Path to the file
            root_path: Root path of the codebase
            
        Returns:
            FileInfo if file is supported, None otherwise
        """
        # Skip if file is in blacklisted directory
        if self._is_blacklisted_path(file_path, root_path):
            return None
        
        # Check file extension
        extension = file_path.suffix.lower()
        if extension not in self.config.SUPPORTED_EXTENSIONS:
            return None
        
        # Get language
        language = self.config.LANGUAGE_MAPPING.get(extension, 'unknown')
        
        # Calculate file hash and size
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                file_hash = hashlib.md5(content).hexdigest()
                size = len(content)
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return None
        
        # Create relative path
        relative_path = str(file_path.relative_to(root_path))
        
        return FileInfo(
            path=str(file_path),
            relative_path=relative_path,
            language=language,
            size=size,
            hash=file_hash
        )
    
    def _is_blacklisted_path(self, file_path: Path, root_path: Path) -> bool:
        """
        Check if a file path contains any blacklisted directories.
        
        Args:
            file_path: Path to check
            root_path: Root path of the codebase
            
        Returns:
            True if path should be blacklisted
        """
        relative_path = file_path.relative_to(root_path)
        path_parts = relative_path.parts
        
        for part in path_parts:
            if part in self.config.BLACKLIST_DIRS:
                return True
            
            # Check for hidden directories (starting with .)
            if part.startswith('.') and part not in ['.', '..']:
                # Allow some common config files
                if part not in ['.env', '.env.example', '.gitignore', '.dockerignore']:
                    return True
        
        return False
    
    def read_file_content(self, file_path: str) -> Tuple[str, str]:
        """
        Read file content and detect encoding.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (content, encoding)
        """
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                return content, encoding
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")
                break
        
        # If all encodings fail, try binary mode
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            # Try to decode as utf-8 with error handling
            text_content = content.decode('utf-8', errors='ignore')
            return text_content, 'utf-8-fallback'
        except Exception as e:
            logger.error(f"Could not read {file_path} in any encoding: {e}")
            return "", "unknown"
    
    def chunk_content(self, content: str, max_chunk_size: int = None) -> List[str]:
        """
        Split content into chunks for processing.
        
        Args:
            content: Text content to chunk
            max_chunk_size: Maximum size of each chunk
            
        Returns:
            List of content chunks
        """
        max_chunk_size = max_chunk_size or self.config.chunk_size
        
        if len(content) <= max_chunk_size:
            return [content]
        
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            
            # If adding this line would exceed chunk size, save current chunk
            if current_size + line_size > max_chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        # Add remaining chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def get_file_stats(self, files: List[FileInfo]) -> Dict[str, any]:
        """
        Generate statistics about the processed files.
        
        Args:
            files: List of FileInfo objects
            
        Returns:
            Dictionary containing statistics
        """
        stats = {
            'total_files': len(files),
            'total_size': sum(f.size for f in files),
            'languages': {},
            'largest_file': None,
            'file_size_distribution': {
                'small': 0,    # < 10KB
                'medium': 0,   # 10KB - 100KB
                'large': 0,    # 100KB - 1MB
                'huge': 0      # > 1MB
            }
        }
        
        # Language distribution
        for file_info in files:
            lang = file_info.language
            if lang not in stats['languages']:
                stats['languages'][lang] = {'count': 0, 'total_size': 0}
            stats['languages'][lang]['count'] += 1
            stats['languages'][lang]['total_size'] += file_info.size
        
        # Find largest file
        if files:
            stats['largest_file'] = max(files, key=lambda f: f.size)
        
        # Size distribution
        for file_info in files:
            size = file_info.size
            if size < 10 * 1024:  # 10KB
                stats['file_size_distribution']['small'] += 1
            elif size < 100 * 1024:  # 100KB
                stats['file_size_distribution']['medium'] += 1
            elif size < 1024 * 1024:  # 1MB
                stats['file_size_distribution']['large'] += 1
            else:
                stats['file_size_distribution']['huge'] += 1
        
        return stats