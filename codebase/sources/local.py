"""
Local directory source handler.
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class LocalSource:
    """Handles local directory processing."""
    
    def __init__(self):
        """Initialize local source handler."""
        pass
    
    def validate_path(self, path: str) -> bool:
        """
        Validate local directory path.
        
        Args:
            path: Path to local directory
            
        Returns:
            True if path is valid
        """
        path = Path(path)
        
        if not path.exists():
            logger.error(f"Path does not exist: {path}")
            return False
        
        if not path.is_dir():
            logger.error(f"Path is not a directory: {path}")
            return False
        
        # Check if directory is readable
        try:
            list(path.iterdir())
        except PermissionError:
            logger.error(f"No permission to read directory: {path}")
            return False
        except Exception as e:
            logger.error(f"Error accessing directory {path}: {e}")
            return False
        
        return True
    
    def get_directory_info(self, path: str) -> Dict[str, Any]:
        """
        Get information about local directory.
        
        Args:
            path: Path to local directory
            
        Returns:
            Dictionary with directory information
        """
        path = Path(path).resolve()
        
        info = {
            'path': str(path),
            'name': path.name,
            'absolute_path': str(path),
            'size_mb': 0,
            'file_count': 0,
            'directory_count': 0,
            'file_types': {},
            'hidden_files': 0,
            'symlinks': 0,
            'largest_files': [],
            'contains_git': False,
            'contains_code': False
        }
        
        try:
            files = []
            code_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.h'}
            
            for item in path.rglob('*'):
                try:
                    if item.is_file():
                        if item.is_symlink():
                            info['symlinks'] += 1
                            continue
                        
                        size = item.stat().st_size
                        files.append((str(item), size))
                        
                        info['file_count'] += 1
                        info['size_mb'] += size / (1024 * 1024)
                        
                        # File type analysis
                        ext = item.suffix.lower()
                        info['file_types'][ext] = info['file_types'].get(ext, 0) + 1
                        
                        # Check for code files
                        if ext in code_extensions:
                            info['contains_code'] = True
                        
                        # Check for hidden files
                        if item.name.startswith('.'):
                            info['hidden_files'] += 1
                        
                        # Check for Git repository
                        if '.git' in item.parts:
                            info['contains_git'] = True
                    
                    elif item.is_dir():
                        info['directory_count'] += 1
                        
                        # Check for Git repository
                        if item.name == '.git':
                            info['contains_git'] = True
                
                except (PermissionError, OSError) as e:
                    logger.warning(f"Cannot access {item}: {e}")
                    continue
            
            # Find largest files
            files.sort(key=lambda x: x[1], reverse=True)
            info['largest_files'] = [
                {'path': path, 'size_mb': size / (1024 * 1024)}
                for path, size in files[:10]
            ]
            
        except Exception as e:
            logger.error(f"Error analyzing directory {path}: {e}")
            info['error'] = str(e)
        
        return info
    
    def prepare_directory(self, path: str, copy_to_temp: bool = False, temp_dir: str = None) -> str:
        """
        Prepare local directory for indexing.
        
        Args:
            path: Path to local directory
            copy_to_temp: Whether to copy to temp directory
            temp_dir: Temporary directory path (if copying)
            
        Returns:
            Path to prepared directory
        """
        path = Path(path).resolve()
        
        if not self.validate_path(path):
            raise ValueError(f"Invalid directory path: {path}")
        
        if not copy_to_temp:
            # Use directory as-is
            logger.info(f"Using directory directly: {path}")
            return str(path)
        
        # Copy to temporary directory
        import tempfile
        
        if temp_dir is None:
            temp_base = Path(tempfile.gettempdir()) / "codebase_local"
            temp_base.mkdir(parents=True, exist_ok=True)
            temp_dir = temp_base / path.name
        else:
            temp_dir = Path(temp_dir)
        
        # Remove existing temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        try:
            logger.info(f"Copying directory to temp location: {temp_dir}")
            
            # Copy directory, excluding some common large/unnecessary directories
            def ignore_patterns(dir, files):
                ignore = set()
                for f in files:
                    if f in {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env', 
                            '.idea', '.vscode', 'build', 'dist', 'target', '.next'}:
                        ignore.add(f)
                    elif f.startswith('.') and f.endswith('.tmp'):
                        ignore.add(f)
                return ignore
            
            shutil.copytree(path, temp_dir, ignore=ignore_patterns)
            logger.info(f"Successfully copied to: {temp_dir}")
            return str(temp_dir)
            
        except Exception as e:
            logger.error(f"Error copying directory: {e}")
            raise
    
    def get_git_info(self, path: str) -> Dict[str, Any]:
        """
        Get Git repository information if available.
        
        Args:
            path: Path to directory
            
        Returns:
            Dictionary with Git information
        """
        path = Path(path)
        git_info = {'is_git_repo': False}
        
        try:
            import git
            from git import Repo
            
            repo = Repo(path)
            if not repo.bare:
                commit = repo.head.commit
                git_info = {
                    'is_git_repo': True,
                    'latest_commit': commit.hexsha,
                    'commit_message': commit.message.strip(),
                    'author': str(commit.author),
                    'committed_date': commit.committed_datetime.isoformat(),
                    'branch': repo.active_branch.name if repo.active_branch else 'unknown',
                    'remotes': [remote.name for remote in repo.remotes],
                    'is_dirty': repo.is_dirty(),
                    'untracked_files': len(repo.untracked_files)
                }
                
                # Get remote URLs
                if repo.remotes:
                    git_info['remote_urls'] = {}
                    for remote in repo.remotes:
                        git_info['remote_urls'][remote.name] = list(remote.urls)
        
        except ImportError:
            logger.warning("GitPython not available for Git info")
        except Exception as e:
            logger.debug(f"Not a Git repository or error getting Git info: {e}")
        
        return git_info
    
    def cleanup(self, temp_path: str):
        """
        Clean up temporary directory (only if it was created by prepare_directory).
        
        Args:
            temp_path: Path to temporary directory
        """
        temp_path = Path(temp_path)
        
        # Only clean up if it's in a temp location
        if 'codebase_local' in str(temp_path) or 'tmp' in str(temp_path):
            try:
                if temp_path.exists():
                    shutil.rmtree(temp_path)
                    logger.info(f"Cleaned up temp directory: {temp_path}")
            except Exception as e:
                logger.error(f"Error cleaning up temp directory: {e}")
        else:
            logger.info(f"Skipping cleanup of non-temp directory: {temp_path}")
    
    def prepare_and_analyze(self, path: str, copy_to_temp: bool = False) -> Dict[str, Any]:
        """
        Complete workflow to prepare and analyze local directory.
        
        Args:
            path: Path to local directory
            copy_to_temp: Whether to copy to temp directory
            
        Returns:
            Dictionary with directory info and prepared path
        """
        try:
            # Validate path
            if not self.validate_path(path):
                raise ValueError(f"Invalid directory path: {path}")
            
            # Get directory info
            dir_info = self.get_directory_info(path)
            
            # Get Git info
            git_info = self.get_git_info(path)
            
            # Prepare directory
            prepared_path = self.prepare_directory(path, copy_to_temp)
            
            # Combine information
            result = {
                'original_path': path,
                'local_path': prepared_path,
                'directory_info': dir_info,
                'git_info': git_info,
                'was_copied': copy_to_temp,
                'status': 'success'
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in prepare_and_analyze: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }