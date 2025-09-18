"""
ZIP file source handler.
"""

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class ZipSource:
    """Handles ZIP file extraction and processing."""
    
    def __init__(self, temp_dir: str = None):
        """
        Initialize ZIP source handler.
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "codebase_zip"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def validate_zip_file(self, zip_path: str) -> bool:
        """
        Validate ZIP file.
        
        Args:
            zip_path: Path to ZIP file
            
        Returns:
            True if ZIP file is valid
        """
        zip_path = Path(zip_path)
        
        if not zip_path.exists():
            logger.error(f"ZIP file does not exist: {zip_path}")
            return False
        
        if not zip_path.is_file():
            logger.error(f"Path is not a file: {zip_path}")
            return False
        
        if zip_path.suffix.lower() not in ['.zip']:
            logger.warning(f"File extension is not .zip: {zip_path}")
            # Still try to process it, might be a valid ZIP
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Test the ZIP file
                zip_ref.testzip()
            return True
        except zipfile.BadZipFile:
            logger.error(f"Invalid ZIP file: {zip_path}")
            return False
        except Exception as e:
            logger.error(f"Error validating ZIP file {zip_path}: {e}")
            return False
    
    def get_zip_info(self, zip_path: str) -> Dict[str, Any]:
        """
        Get information about ZIP file contents.
        
        Args:
            zip_path: Path to ZIP file
            
        Returns:
            Dictionary with ZIP file information
        """
        zip_path = Path(zip_path)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_list = zip_ref.filelist
                
                info = {
                    'file_path': str(zip_path),
                    'file_size_mb': zip_path.stat().st_size / (1024 * 1024),
                    'total_files': len(file_list),
                    'compressed_size': sum(f.compress_size for f in file_list),
                    'uncompressed_size': sum(f.file_size for f in file_list),
                    'compression_ratio': 0,
                    'file_types': {},
                    'top_level_dirs': set(),
                    'contains_code': False
                }
                
                # Calculate compression ratio
                if info['uncompressed_size'] > 0:
                    info['compression_ratio'] = info['compressed_size'] / info['uncompressed_size']
                
                # Analyze file types and structure
                code_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.h'}
                
                for file_info in file_list:
                    if not file_info.is_dir():
                        # File extension analysis
                        ext = Path(file_info.filename).suffix.lower()
                        info['file_types'][ext] = info['file_types'].get(ext, 0) + 1
                        
                        # Check for code files
                        if ext in code_extensions:
                            info['contains_code'] = True
                        
                        # Top-level directories
                        parts = Path(file_info.filename).parts
                        if len(parts) > 0:
                            info['top_level_dirs'].add(parts[0])
                
                info['top_level_dirs'] = list(info['top_level_dirs'])
                
                return info
                
        except Exception as e:
            logger.error(f"Error getting ZIP info: {e}")
            return {'error': str(e)}
    
    def extract_zip(self, zip_path: str, destination: str = None) -> str:
        """
        Extract ZIP file to destination directory.
        
        Args:
            zip_path: Path to ZIP file
            destination: Destination directory (optional)
            
        Returns:
            Path to extracted contents
        """
        zip_path = Path(zip_path)
        
        if not self.validate_zip_file(zip_path):
            raise ValueError(f"Invalid ZIP file: {zip_path}")
        
        # Determine destination
        if destination is None:
            zip_name = zip_path.stem
            destination = self.temp_dir / zip_name
        else:
            destination = Path(destination)
        
        # Remove existing directory if it exists
        if destination.exists():
            shutil.rmtree(destination)
        
        destination.mkdir(parents=True, exist_ok=True)
        
        try:
            logger.info(f"Extracting ZIP file: {zip_path}")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Security check: prevent directory traversal
                for member in zip_ref.infolist():
                    if self._is_safe_path(member.filename):
                        zip_ref.extract(member, destination)
                    else:
                        logger.warning(f"Skipping unsafe path: {member.filename}")
            
            logger.info(f"Successfully extracted to: {destination}")
            
            # Check if there's a single top-level directory
            top_level_items = list(destination.iterdir())
            if len(top_level_items) == 1 and top_level_items[0].is_dir():
                # If there's only one top-level directory, return that instead
                actual_root = top_level_items[0]
                logger.info(f"Using nested directory as root: {actual_root}")
                return str(actual_root)
            
            return str(destination)
            
        except zipfile.BadZipFile as e:
            logger.error(f"Bad ZIP file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error extracting ZIP file: {e}")
            raise
    
    def _is_safe_path(self, filename: str) -> bool:
        """
        Check if a path is safe for extraction (no directory traversal).
        
        Args:
            filename: Filename from ZIP archive
            
        Returns:
            True if path is safe
        """
        # Normalize the path
        normalized = os.path.normpath(filename)
        
        # Check for directory traversal attempts
        if normalized.startswith('/') or normalized.startswith('\\'):
            return False
        
        if '..' in normalized:
            return False
        
        if ':' in normalized:  # Windows drive letters
            return False
        
        return True
    
    def get_extracted_metadata(self, extracted_path: str) -> Dict[str, Any]:
        """
        Get metadata about extracted contents.
        
        Args:
            extracted_path: Path to extracted contents
            
        Returns:
            Dictionary with metadata
        """
        extracted_path = Path(extracted_path)
        
        metadata = {
            'path': str(extracted_path),
            'name': extracted_path.name,
            'size_mb': 0,
            'file_count': 0,
            'directory_count': 0,
            'file_types': {},
            'largest_files': []
        }
        
        try:
            files = []
            
            for item in extracted_path.rglob('*'):
                if item.is_file():
                    size = item.stat().st_size
                    files.append((str(item), size))
                    
                    metadata['file_count'] += 1
                    metadata['size_mb'] += size / (1024 * 1024)
                    
                    # File type analysis
                    ext = item.suffix.lower()
                    metadata['file_types'][ext] = metadata['file_types'].get(ext, 0) + 1
                    
                elif item.is_dir():
                    metadata['directory_count'] += 1
            
            # Find largest files
            files.sort(key=lambda x: x[1], reverse=True)
            metadata['largest_files'] = [
                {'path': path, 'size_mb': size / (1024 * 1024)}
                for path, size in files[:5]
            ]
            
        except Exception as e:
            logger.warning(f"Error calculating metadata: {e}")
        
        return metadata
    
    def cleanup(self, extracted_path: str = None):
        """
        Clean up extracted files.
        
        Args:
            extracted_path: Specific path to clean (optional)
        """
        try:
            if extracted_path:
                extracted_path = Path(extracted_path)
                if extracted_path.exists():
                    shutil.rmtree(extracted_path)
                    logger.info(f"Cleaned up: {extracted_path}")
            else:
                # Clean up entire temp directory
                if self.temp_dir.exists():
                    shutil.rmtree(self.temp_dir)
                    logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def extract_and_prepare(self, zip_path: str) -> Dict[str, Any]:
        """
        Complete workflow to extract and prepare ZIP file.
        
        Args:
            zip_path: Path to ZIP file
            
        Returns:
            Dictionary with extraction info and path
        """
        try:
            # Validate ZIP file
            if not self.validate_zip_file(zip_path):
                raise ValueError(f"Invalid ZIP file: {zip_path}")
            
            # Get ZIP info
            zip_info = self.get_zip_info(zip_path)
            
            # Extract ZIP
            extracted_path = self.extract_zip(zip_path)
            
            # Get extracted metadata
            metadata = self.get_extracted_metadata(extracted_path)
            
            # Combine information
            result = {
                'zip_info': zip_info,
                'local_path': extracted_path,
                'metadata': metadata,
                'status': 'success'
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in extract_and_prepare: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }