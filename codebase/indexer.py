"""
Main codebase indexer class that orchestrates the indexing process.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import asdict
from tqdm import tqdm

from .config import CodebaseConfig, default_config
from .core import CodeParser, FilePreprocessor, EmbeddingGenerator, VectorStore, VectorRecord
from .sources import GitHubSource, ZipSource, LocalSource
from .retrieval import SemanticSearch, ContextManager

logger = logging.getLogger(__name__)


class CodebaseIndexer:
    """Main class for indexing and searching codebases."""
    
    def __init__(self, config: CodebaseConfig = None):
        """
        Initialize the codebase indexer.
        
        Args:
            config: Configuration object
        """
        self.config = config or default_config
        
        # Initialize core components
        self.parser = CodeParser()
        self.preprocessor = FilePreprocessor(self.config)
        self.embedding_generator = EmbeddingGenerator(self.config.embedding_model)
        self.vector_store = VectorStore(self.config.database_url)
        
        # Initialize retrieval components
        self.search_engine = SemanticSearch(self.vector_store, self.embedding_generator)
        self.context_manager = ContextManager(self.config.max_context_tokens)
        
        # Initialize source handlers
        self.github_source = GitHubSource()
        self.zip_source = ZipSource()
        self.local_source = LocalSource()
        
        logger.info("CodebaseIndexer initialized")
    
    def index_github_repository(self, url: str, name: str = None) -> Dict[str, Any]:
        """
        Index a GitHub repository.
        
        Args:
            url: GitHub repository URL
            name: Custom name for the codebase (optional)
            
        Returns:
            Dictionary with indexing results
        """
        try:
            logger.info(f"Starting GitHub repository indexing: {url}")
            
            # Download and prepare repository
            repo_result = self.github_source.download_and_prepare(url)
            if repo_result['status'] != 'success':
                return repo_result
            
            # Use provided name or extract from repo info
            if not name:
                name = repo_result['repo_info']['full_name'].replace('/', '-')
            
            # Index the local path
            indexing_result = self._index_directory(
                repo_result['local_path'], 
                name,
                source_type='github',
                source_url=url,
                metadata=repo_result
            )
            
            # Cleanup temporary files
            try:
                self.github_source.cleanup(repo_result['local_path'])
            except Exception as e:
                logger.warning(f"Cleanup warning: {e}")
            
            return indexing_result
            
        except Exception as e:
            logger.error(f"Error indexing GitHub repository: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'name': name or 'unknown'
            }
    
    def index_zip_file(self, zip_path: str, name: str = None) -> Dict[str, Any]:
        """
        Index a ZIP file containing code.
        
        Args:
            zip_path: Path to ZIP file
            name: Custom name for the codebase (optional)
            
        Returns:
            Dictionary with indexing results
        """
        try:
            logger.info(f"Starting ZIP file indexing: {zip_path}")
            
            # Extract and prepare ZIP file
            zip_result = self.zip_source.extract_and_prepare(zip_path)
            if zip_result['status'] != 'success':
                return zip_result
            
            # Use provided name or extract from ZIP
            if not name:
                name = Path(zip_path).stem
            
            # Index the extracted path
            indexing_result = self._index_directory(
                zip_result['local_path'],
                name,
                source_type='zip',
                source_path=zip_path,
                metadata=zip_result
            )
            
            # Cleanup temporary files
            try:
                self.zip_source.cleanup(zip_result['local_path'])
            except Exception as e:
                logger.warning(f"Cleanup warning: {e}")
            
            return indexing_result
            
        except Exception as e:
            logger.error(f"Error indexing ZIP file: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'name': name or 'unknown'
            }
    
    def index_local_directory(self, path: str, name: str = None, copy_to_temp: bool = False) -> Dict[str, Any]:
        """
        Index a local directory.
        
        Args:
            path: Path to local directory
            name: Custom name for the codebase (optional)
            copy_to_temp: Whether to copy directory to temp location
            
        Returns:
            Dictionary with indexing results
        """
        try:
            logger.info(f"Starting local directory indexing: {path}")
            
            # Prepare local directory
            local_result = self.local_source.prepare_and_analyze(path, copy_to_temp)
            if local_result['status'] != 'success':
                return local_result
            
            # Use provided name or extract from directory
            if not name:
                name = Path(path).name
            
            # Index the directory
            indexing_result = self._index_directory(
                local_result['local_path'],
                name,
                source_type='local',
                source_path=path,
                metadata=local_result
            )
            
            # Cleanup if we copied to temp
            if copy_to_temp:
                try:
                    self.local_source.cleanup(local_result['local_path'])
                except Exception as e:
                    logger.warning(f"Cleanup warning: {e}")
            
            return indexing_result
            
        except Exception as e:
            logger.error(f"Error indexing local directory: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'name': name or 'unknown'
            }
    
    def _index_directory(
        self, 
        directory_path: str, 
        codebase_name: str,
        source_type: str,
        source_url: str = None,
        source_path: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Internal method to index a directory.
        
        Args:
            directory_path: Path to directory to index
            codebase_name: Name for the codebase
            source_type: Type of source ('github', 'zip', 'local')
            source_url: Source URL (for GitHub)
            source_path: Source path (for local/zip)
            metadata: Additional metadata
            
        Returns:
            Dictionary with indexing results
        """
        try:
            # Scan directory for files
            logger.info("Scanning directory for files...")
            files = self.preprocessor.scan_directory(directory_path)
            
            if not files:
                return {
                    'status': 'error',
                    'error': 'No supported files found in directory',
                    'name': codebase_name
                }
            
            # Create vector store table
            logger.info(f"Creating vector store table for: {codebase_name}")
            self.vector_store.create_codebase_table(codebase_name)
            
            # Process files and generate embeddings
            all_records = []
            total_chunks = 0
            processed_files = 0
            
            for file_info in tqdm(files, desc="Processing files"):
                try:
                    records = self._process_file(file_info, codebase_name)
                    all_records.extend(records)
                    total_chunks += len(records)
                    processed_files += 1
                except Exception as e:
                    logger.warning(f"Error processing {file_info.path}: {e}")
                    continue
            
            # Insert records into vector store
            if all_records:
                logger.info(f"Inserting {len(all_records)} records into vector store...")
                success = self.vector_store.insert_records(codebase_name, all_records)
                
                if not success:
                    return {
                        'status': 'error',
                        'error': 'Failed to insert records into vector store',
                        'name': codebase_name
                    }
            
            # Generate final statistics
            stats = {
                'total_files': len(files),
                'processed_files': processed_files,
                'total_chunks': total_chunks,
                'successful_embeddings': len(all_records),
                'file_types': self.preprocessor.get_file_stats(files),
                'source_type': source_type,
                'source_url': source_url,
                'source_path': source_path,
                'metadata': metadata
            }
            
            logger.info(f"Successfully indexed codebase: {codebase_name}")
            logger.info(f"Statistics: {stats}")
            
            return {
                'status': 'success',
                'name': codebase_name,
                'statistics': stats
            }
            
        except Exception as e:
            logger.error(f"Error in _index_directory: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'name': codebase_name
            }
    
    def _process_file(self, file_info, codebase_name: str) -> List[VectorRecord]:
        """
        Process a single file and generate vector records.
        
        Args:
            file_info: FileInfo object
            codebase_name: Name of the codebase
            
        Returns:
            List of VectorRecord objects
        """
        # Read file content
        content, encoding = self.preprocessor.read_file_content(file_info.path)
        if not content.strip():
            return []
        
        # Parse file into code chunks
        chunks = self.parser.parse_file(file_info.path, content, file_info.language)
        
        if not chunks:
            # If no structured chunks found, create text chunks
            text_chunks = self.preprocessor.chunk_content(content)
            for i, chunk_content in enumerate(text_chunks):
                chunk = type('CodeChunk', (), {
                    'content': chunk_content,
                    'language': file_info.language,
                    'chunk_type': 'text',
                    'name': f'chunk_{i}',
                    'file_path': file_info.relative_path,
                    'line_start': 1,
                    'line_end': len(chunk_content.split('\n')),
                    'parent_name': None,
                    'description': None
                })()
                chunks.append(chunk)
        
        # Generate embeddings and create vector records
        records = []
        for chunk in chunks:
            try:
                # Generate code embedding
                embedding_result = self.embedding_generator.generate_embedding(
                    chunk.content,
                    metadata={
                        'chunk_type': chunk.chunk_type,
                        'name': chunk.name,
                        'file_path': chunk.file_path,
                        'language': chunk.language
                    }
                )

                # Generate description embedding if description exists
                description_embedding = None
                if chunk.description:
                    description_embedding_result = self.embedding_generator.generate_embedding(
                        chunk.description,
                        for_query=True,  # Description is natural language
                        metadata={
                            'chunk_type': 'description',
                            'name': chunk.name,
                            'file_path': chunk.file_path
                        }
                    )
                    if description_embedding_result:
                        description_embedding = description_embedding_result.embedding

                if embedding_result:
                    # Create vector record
                    record = VectorRecord(
                        id=str(uuid.uuid4()),
                        text=chunk.content,
                        vector=embedding_result.embedding,
                        chunk_type=chunk.chunk_type,
                        name=chunk.name,
                        file_path=chunk.file_path,
                        language=chunk.language,
                        line_start=chunk.line_start,
                        line_end=chunk.line_end,
                        parent_name=chunk.parent_name,
                        description=chunk.description,
                        description_embedding=description_embedding,
                        metadata={
                            'file_hash': file_info.hash,
                            'file_size': file_info.size,
                            'encoding': encoding
                        }
                    )
                    records.append(record)

            except Exception as e:
                logger.warning(f"Error creating record for chunk in {file_info.path}: {e}")
                continue
        
        return records
    
    def search(
        self,
        query: str,
        codebase_name: str,
        top_k: int = None,
        search_type: str = "semantic",
        filters: Dict[str, Any] = None,
        include_context: bool = True,
        use_hyde: bool = False,
        use_reranking: bool = False
    ) -> Dict[str, Any]:
        """
        Search the indexed codebase.

        Args:
            query: Search query
            codebase_name: Name of codebase to search
            top_k: Number of results to return
            search_type: Type of search ("semantic", "hybrid", "keyword", "hyde")
            filters: Optional filters
            include_context: Whether to include formatted context
            use_hyde: Whether to use HyDE for query enhancement
            use_reranking: Whether to apply reranking to results

        Returns:
            Dictionary with search results
        """
        top_k = top_k or self.config.default_top_k

        try:
            # Perform search
            results = self.search_engine.search(
                query=query,
                codebase_name=codebase_name,
                top_k=top_k,
                filters=filters,
                search_type=search_type,
                use_hyde=use_hyde
            )

            # Apply reranking if requested
            if use_reranking and results:
                from .retrieval.reranker import CodeReranker, ConfidenceFilter, DiversityFilter

                # Rerank results
                reranker = CodeReranker()
                results = reranker.rerank(results, query, top_k=top_k * 2)

                # Apply confidence filter
                confidence_filter = ConfidenceFilter(min_score=0.3)
                results = confidence_filter.filter(results)

                # Apply diversity filter
                diversity_filter = DiversityFilter(max_per_file=2)
                results = diversity_filter.filter(results)

                # Limit to top_k after filtering
                results = results[:top_k]

            response = {
                'query': query,
                'codebase_name': codebase_name,
                'results': [asdict(result) for result in results],
                'total_results': len(results),
                'search_type': search_type,
                'use_hyde': use_hyde,
                'use_reranking': use_reranking
            }

            # Add formatted context if requested
            if include_context and results:
                response['context'] = self.context_manager.build_context_from_results(
                    results, query
                )
                response['summary'] = self.context_manager.format_search_summary(
                    query, results
                )

            return response

        except Exception as e:
            logger.error(f"Error in search: {e}")
            return {
                'error': str(e),
                'query': query,
                'codebase_name': codebase_name
            }
    
    def list_codebases(self) -> List[Dict[str, Any]]:
        """
        List all indexed codebases.
        
        Returns:
            List of codebase information
        """
        try:
            return self.vector_store.list_codebases()
        except Exception as e:
            logger.error(f"Error listing codebases: {e}")
            return []
    
    def delete_codebase(self, name: str) -> bool:
        """
        Delete a codebase.
        
        Args:
            name: Name of codebase to delete
            
        Returns:
            True if successful
        """
        try:
            return self.vector_store.delete_codebase(name)
        except Exception as e:
            logger.error(f"Error deleting codebase {name}: {e}")
            return False
    
    def get_codebase_stats(self, name: str) -> Dict[str, Any]:
        """
        Get statistics for a codebase.
        
        Args:
            name: Name of codebase
            
        Returns:
            Dictionary with statistics
        """
        try:
            return self.vector_store.get_codebase_stats(name)
        except Exception as e:
            logger.error(f"Error getting stats for {name}: {e}")
            return {}
    
    def cleanup(self):
        """Clean up resources."""
        try:
            self.vector_store.close()
            self.github_source.cleanup()
            self.zip_source.cleanup()
            logger.info("CodebaseIndexer cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")