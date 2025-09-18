"""
Semantic search functionality for codebase queries.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from semantic search."""
    id: str
    content: str
    chunk_type: str
    name: str
    file_path: str
    language: str
    line_start: int
    line_end: int
    parent_name: Optional[str]
    docstring: Optional[str]
    score: float
    metadata: Dict[str, Any]


class SemanticSearch:
    """Handles semantic search operations on codebase vector store."""
    
    def __init__(self, vector_store, embedding_generator):
        """
        Initialize semantic search.
        
        Args:
            vector_store: Vector store instance
            embedding_generator: Embedding generator instance
        """
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
    
    def search(
        self, 
        query: str, 
        codebase_name: str, 
        top_k: int = 5,
        filters: Dict[str, Any] = None,
        search_type: str = "semantic"
    ) -> List[SearchResult]:
        """
        Perform search on codebase.
        
        Args:
            query: Search query
            codebase_name: Name of codebase to search
            top_k: Number of results to return
            filters: Optional filters (language, chunk_type, etc.)
            search_type: Type of search ("semantic", "hybrid", "keyword")
            
        Returns:
            List of SearchResult objects
        """
        try:
            if search_type == "semantic":
                return self._semantic_search(query, codebase_name, top_k, filters)
            elif search_type == "hybrid":
                return self._hybrid_search(query, codebase_name, top_k, filters)
            elif search_type == "keyword":
                return self._keyword_search(query, codebase_name, top_k, filters)
            else:
                logger.warning(f"Unknown search type: {search_type}, using semantic")
                return self._semantic_search(query, codebase_name, top_k, filters)
                
        except Exception as e:
            logger.error(f"Error in search: {e}")
            return []
    
    def _semantic_search(
        self, 
        query: str, 
        codebase_name: str, 
        top_k: int,
        filters: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """Perform pure semantic search using embeddings."""
        # Generate query embedding
        embedding_result = self.embedding_generator.generate_embedding(query)
        if not embedding_result:
            logger.error("Failed to generate query embedding")
            return []
        
        # Search vector store
        raw_results = self.vector_store.search(
            codebase_name=codebase_name,
            query_vector=embedding_result.embedding,
            top_k=top_k,
            filters=filters
        )
        
        # Convert to SearchResult objects
        search_results = []
        for result in raw_results:
            search_result = SearchResult(
                id=result['id'],
                content=result['text'],
                chunk_type=result['chunk_type'],
                name=result['name'],
                file_path=result['file_path'],
                language=result['language'],
                line_start=result['line_start'],
                line_end=result['line_end'],
                parent_name=result['parent_name'],
                docstring=result['docstring'],
                score=1.0 - result['score'],  # Convert distance to similarity
                metadata={}
            )
            search_results.append(search_result)
        
        return search_results
    
    def _keyword_search(
        self, 
        query: str, 
        codebase_name: str, 
        top_k: int,
        filters: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """Perform keyword-based search (simulated using text matching)."""
        # This is a simplified implementation
        # In a real system, you might use a full-text search engine like Elasticsearch
        
        # Get all records from vector store and filter by text content
        all_results = self.vector_store.search(
            codebase_name=codebase_name,
            query_vector=[0.0] * 768,  # Dummy vector
            top_k=1000,  # Get many results to filter
            filters=filters
        )
        
        # Score based on keyword matches
        query_words = query.lower().split()
        scored_results = []
        
        for result in all_results:
            content_lower = result['text'].lower()
            name_lower = result['name'].lower()
            
            # Calculate keyword match score
            content_score = sum(1 for word in query_words if word in content_lower)
            name_score = sum(2 for word in query_words if word in name_lower)  # Name matches are worth more
            
            total_score = content_score + name_score
            
            if total_score > 0:
                search_result = SearchResult(
                    id=result['id'],
                    content=result['text'],
                    chunk_type=result['chunk_type'],
                    name=result['name'],
                    file_path=result['file_path'],
                    language=result['language'],
                    line_start=result['line_start'],
                    line_end=result['line_end'],
                    parent_name=result['parent_name'],
                    docstring=result['docstring'],
                    score=total_score,
                    metadata={'keyword_matches': total_score}
                )
                scored_results.append(search_result)
        
        # Sort by score and return top_k
        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:top_k]
    
    def _hybrid_search(
        self, 
        query: str, 
        codebase_name: str, 
        top_k: int,
        filters: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """Perform hybrid search combining semantic and keyword approaches."""
        # Get both semantic and keyword results
        semantic_results = self._semantic_search(query, codebase_name, top_k * 2, filters)
        keyword_results = self._keyword_search(query, codebase_name, top_k * 2, filters)
        
        # Combine and rerank
        combined_results = {}
        
        # Add semantic results
        for i, result in enumerate(semantic_results):
            semantic_score = result.score * (1.0 - i / len(semantic_results))  # Position-based decay
            combined_results[result.id] = {
                'result': result,
                'semantic_score': semantic_score,
                'keyword_score': 0.0
            }
        
        # Add keyword results
        for i, result in enumerate(keyword_results):
            keyword_score = result.score * (1.0 - i / len(keyword_results))  # Position-based decay
            if result.id in combined_results:
                combined_results[result.id]['keyword_score'] = keyword_score
            else:
                combined_results[result.id] = {
                    'result': result,
                    'semantic_score': 0.0,
                    'keyword_score': keyword_score
                }
        
        # Calculate hybrid scores
        final_results = []
        for item in combined_results.values():
            # Combine scores with weights
            hybrid_score = 0.7 * item['semantic_score'] + 0.3 * item['keyword_score']
            
            result = item['result']
            result.score = hybrid_score
            result.metadata.update({
                'semantic_score': item['semantic_score'],
                'keyword_score': item['keyword_score'],
                'search_type': 'hybrid'
            })
            final_results.append(result)
        
        # Sort by hybrid score and return top_k
        final_results.sort(key=lambda x: x.score, reverse=True)
        return final_results[:top_k]
    
    def search_by_type(
        self, 
        query: str, 
        codebase_name: str, 
        chunk_type: str,
        top_k: int = 5
    ) -> List[SearchResult]:
        """
        Search for specific types of code chunks.
        
        Args:
            query: Search query
            codebase_name: Name of codebase
            chunk_type: Type of chunk ('function', 'class', 'method', etc.)
            top_k: Number of results
            
        Returns:
            List of SearchResult objects
        """
        filters = {'chunk_type': chunk_type}
        return self.search(query, codebase_name, top_k, filters)
    
    def search_by_language(
        self, 
        query: str, 
        codebase_name: str, 
        language: str,
        top_k: int = 5
    ) -> List[SearchResult]:
        """
        Search within specific programming language.
        
        Args:
            query: Search query
            codebase_name: Name of codebase
            language: Programming language
            top_k: Number of results
            
        Returns:
            List of SearchResult objects
        """
        filters = {'language': language}
        return self.search(query, codebase_name, top_k, filters)
    
    def find_similar_functions(
        self, 
        function_name: str, 
        codebase_name: str,
        top_k: int = 5
    ) -> List[SearchResult]:
        """
        Find functions similar to the given function name.
        
        Args:
            function_name: Name of function to find similar functions for
            codebase_name: Name of codebase
            top_k: Number of results
            
        Returns:
            List of SearchResult objects
        """
        query = f"function {function_name}"
        filters = {'chunk_type': 'function'}
        return self.search(query, codebase_name, top_k, filters, search_type="hybrid")
    
    def find_class_methods(
        self, 
        class_name: str, 
        codebase_name: str,
        top_k: int = 10
    ) -> List[SearchResult]:
        """
        Find methods within a specific class.
        
        Args:
            class_name: Name of the class
            codebase_name: Name of codebase
            top_k: Number of results
            
        Returns:
            List of SearchResult objects
        """
        filters = {'parent_name': class_name}
        return self.search("", codebase_name, top_k, filters)
    
    def search_with_context(
        self, 
        query: str, 
        codebase_name: str,
        context_window: int = 5,
        top_k: int = 3
    ) -> Dict[str, Any]:
        """
        Search and return results with surrounding context.
        
        Args:
            query: Search query
            codebase_name: Name of codebase
            context_window: Lines of context to include
            top_k: Number of results
            
        Returns:
            Dictionary with results and context
        """
        results = self.search(query, codebase_name, top_k)
        
        # Group results by file for context
        files_with_context = {}
        for result in results:
            file_path = result.file_path
            if file_path not in files_with_context:
                files_with_context[file_path] = []
            
            files_with_context[file_path].append({
                'result': result,
                'context_start': max(1, result.line_start - context_window),
                'context_end': result.line_end + context_window
            })
        
        return {
            'query': query,
            'results': results,
            'files_with_context': files_with_context,
            'total_matches': len(results)
        }