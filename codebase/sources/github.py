"""
GitHub repository source handler.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import logging
import re

logger = logging.getLogger(__name__)

try:
    import git
    from git import Repo
except ImportError:
    logger.error("GitPython not installed. Install with: pip install gitpython")
    raise


class GitHubSource:
    """Handles GitHub repository cloning and processing."""
    
    def __init__(self, temp_dir: str = None):
        """
        Initialize GitHub source handler.
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "codebase_github"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def validate_url(self, url: str) -> bool:
        """
        Validate GitHub repository URL.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            True if URL is valid
        """
        # Common GitHub URL patterns
        patterns = [
            r'^https://github\.com/[\w\.-]+/[\w\.-]+/?$',
            r'^https://github\.com/[\w\.-]+/[\w\.-]+\.git/?$',
            r'^git@github\.com:[\w\.-]+/[\w\.-]+\.git/?$',
            r'^https://www\.github\.com/[\w\.-]+/[\w\.-]+/?$'
        ]
        
        for pattern in patterns:
            if re.match(pattern, url):
                return True
        
        logger.warning(f"Invalid GitHub URL format: {url}")
        return False
    
    def extract_repo_info(self, url: str) -> Dict[str, str]:
        """
        Extract repository information from URL.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Dictionary with repo info (owner, name, full_name)
        """
        # Clean up URL
        url = url.rstrip('/')
        if url.endswith('.git'):
            url = url[:-4]
        
        # Extract owner and repo name
        if 'github.com/' in url:
            parts = url.split('github.com/')[-1].split('/')
            if len(parts) >= 2:
                owner = parts[0]
                repo_name = parts[1]
                
                return {
                    'owner': owner,
                    'name': repo_name,
                    'full_name': f"{owner}/{repo_name}",
                    'url': url
                }
        
        raise ValueError(f"Could not extract repository info from URL: {url}")
    
    def clone_repository(self, url: str, destination: str = None) -> str:
        """
        Clone GitHub repository to local directory.
        
        Args:
            url: GitHub repository URL
            destination: Destination directory (optional)
            
        Returns:
            Path to cloned repository
        """
        if not self.validate_url(url):
            raise ValueError(f"Invalid GitHub URL: {url}")
        
        repo_info = self.extract_repo_info(url)
        
        # Determine destination
        if destination is None:
            destination = self.temp_dir / repo_info['full_name'].replace('/', '_')
        else:
            destination = Path(destination)
        
        # Remove existing directory if it exists
        if destination.exists():
            shutil.rmtree(destination)
        
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            logger.info(f"Cloning repository: {url}")
            
            # Clone the repository
            repo = Repo.clone_from(
                url, 
                destination,
                depth=1,  # Shallow clone for faster download
                no_single_branch=False
            )
            
            logger.info(f"Successfully cloned to: {destination}")
            
            # Get some basic info about the repository
            try:
                commit = repo.head.commit
                logger.info(f"Latest commit: {commit.hexsha[:8]} - {commit.message.strip()}")
            except Exception as e:
                logger.warning(f"Could not get commit info: {e}")
            
            return str(destination)
            
        except git.exc.GitCommandError as e:
            logger.error(f"Git command failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error cloning repository: {e}")
            raise
    
    def get_repository_metadata(self, repo_path: str) -> Dict[str, Any]:
        """
        Get metadata about the cloned repository.
        
        Args:
            repo_path: Path to the cloned repository
            
        Returns:
            Dictionary with repository metadata
        """
        repo_path = Path(repo_path)
        metadata = {
            'path': str(repo_path),
            'name': repo_path.name,
            'size_mb': 0,
            'file_count': 0,
            'git_info': {}
        }
        
        try:
            # Calculate repository size
            total_size = sum(
                f.stat().st_size 
                for f in repo_path.rglob('*') 
                if f.is_file() and not f.is_symlink()
            )
            metadata['size_mb'] = total_size / (1024 * 1024)
            
            # Count files
            metadata['file_count'] = sum(
                1 for f in repo_path.rglob('*') 
                if f.is_file() and not f.is_symlink()
            )
            
        except Exception as e:
            logger.warning(f"Error calculating repository size: {e}")
        
        try:
            # Get Git information
            repo = Repo(repo_path)
            if not repo.bare:
                commit = repo.head.commit
                metadata['git_info'] = {
                    'latest_commit': commit.hexsha,
                    'commit_message': commit.message.strip(),
                    'author': str(commit.author),
                    'committed_date': commit.committed_datetime.isoformat(),
                    'branch': repo.active_branch.name if repo.active_branch else 'unknown'
                }
        except Exception as e:
            logger.warning(f"Error getting Git info: {e}")
        
        return metadata
    
    def cleanup(self, repo_path: str = None):
        """
        Clean up temporary files.
        
        Args:
            repo_path: Specific repository path to clean (optional)
        """
        try:
            if repo_path:
                repo_path = Path(repo_path)
                if repo_path.exists():
                    shutil.rmtree(repo_path)
                    logger.info(f"Cleaned up: {repo_path}")
            else:
                # Clean up entire temp directory
                if self.temp_dir.exists():
                    shutil.rmtree(self.temp_dir)
                    logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def download_and_prepare(self, url: str) -> Dict[str, Any]:
        """
        Complete workflow to download and prepare a GitHub repository.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Dictionary with repository info and path
        """
        try:
            # Validate URL
            if not self.validate_url(url):
                raise ValueError(f"Invalid GitHub URL: {url}")
            
            # Extract repository info
            repo_info = self.extract_repo_info(url)
            
            # Clone repository
            repo_path = self.clone_repository(url)
            
            # Get metadata
            metadata = self.get_repository_metadata(repo_path)
            
            # Combine information
            result = {
                'repo_info': repo_info,
                'local_path': repo_path,
                'metadata': metadata,
                'status': 'success'
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in download_and_prepare: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }