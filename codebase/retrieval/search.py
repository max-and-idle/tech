"""
Semantic search functionality for codebase queries.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)

# Import HyDE generator
try:
    from .hyde import HyDEGenerator
    HYDE_AVAILABLE = True
except ImportError:
    HYDE_AVAILABLE = False
    logger.warning("HyDE module not available")

# Import Translation Agent
try:
    from translation_agent import translation_agent
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False
    logger.warning("Translation agent not available")


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
    description: Optional[str]
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

        # Initialize HyDE generator if available
        self.hyde_generator = None
        if HYDE_AVAILABLE:
            try:
                self.hyde_generator = HyDEGenerator()
                logger.info("HyDE generator initialized for semantic search")
            except Exception as e:
                logger.warning(f"Failed to initialize HyDE generator: {e}")
                self.hyde_generator = None

        # Initialize Translation Agent if available
        self.translation_agent = None
        if TRANSLATION_AVAILABLE:
            try:
                self.translation_agent = translation_agent
                logger.info("Translation agent initialized for semantic search")
            except Exception as e:
                logger.warning(f"Failed to initialize translation agent: {e}")
                self.translation_agent = None
    
    def search(
        self,
        query: str,
        codebase_name: str,
        top_k: int = 5,
        filters: Dict[str, Any] = None,
        search_type: str = "semantic",
        use_hyde: bool = False
    ) -> List[SearchResult]:
        """
        Perform search on codebase.

        Args:
            query: Search query
            codebase_name: Name of codebase to search
            top_k: Number of results to return
            filters: Optional filters (language, chunk_type, etc.)
            search_type: Type of search ("semantic", "hybrid", "keyword", "hyde")
            use_hyde: Whether to use HyDE for semantic/hybrid search

        Returns:
            List of SearchResult objects
        """
        try:
            # Route search types
            if search_type == "hyde":
                # Quick HyDE (1-stage, fast) - default
                if self.hyde_generator and self.hyde_generator.is_enabled():
                    return self._hyde_quick_search(query, codebase_name, top_k, filters)
                else:
                    logger.warning("HyDE not available, falling back to semantic")
                    return self._semantic_search(query, codebase_name, top_k, filters)

            elif search_type == "hyde_full":
                # Full HyDE (2-stage, accurate)
                if self.hyde_generator and self.hyde_generator.is_enabled():
                    return self._hyde_search(query, codebase_name, top_k, filters)
                else:
                    logger.warning("HyDE not available, falling back to semantic")
                    return self._semantic_search(query, codebase_name, top_k, filters)

            elif search_type == "semantic":
                if use_hyde and self.hyde_generator and self.hyde_generator.is_enabled():
                    return self._hyde_quick_search(query, codebase_name, top_k, filters)
                else:
                    return self._semantic_search(query, codebase_name, top_k, filters)

            elif search_type == "hybrid":
                if use_hyde and self.hyde_generator and self.hyde_generator.is_enabled():
                    return self._hyde_hybrid_search(query, codebase_name, top_k, filters)
                else:
                    return self._hybrid_search(query, codebase_name, top_k, filters)

            elif search_type == "keyword":
                return self._keyword_search(query, codebase_name, top_k, filters)

            elif search_type == "description":
                return self._description_search(query, codebase_name, top_k, filters)

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
        filters: Dict[str, Any] = None,
        for_query: bool = True
    ) -> List[SearchResult]:
        """Perform pure semantic search using embeddings."""
        # Generate query embedding with proper task_type
        embedding_result = self.embedding_generator.generate_embedding(query, for_query=for_query)
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
                description=result['description'],
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
                    description=result['description'],
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

    def _hyde_search(
        self,
        query: str,
        codebase_name: str,
        top_k: int,
        filters: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """
        Perform HyDE-enhanced semantic search (2-stage).

        Stage 1: Generate hypothetical code from query → Initial search
        Stage 2: Use context to generate improved code → Final search

        Args:
            query: Natural language query
            codebase_name: Name of codebase to search
            top_k: Number of final results to return
            filters: Optional filters

        Returns:
            List of SearchResult objects
        """
        logger.info(f"Performing HyDE search for: {query}")

        # Stage 1: Generate initial HyDE query
        hyde_query_v1 = self.hyde_generator.generate_hyde_query(query)
        if not hyde_query_v1:
            logger.warning("HyDE generation failed, falling back to regular search")
            return self._semantic_search(query, codebase_name, top_k, filters)

        logger.info(f"HyDE query v1 generated (length: {len(hyde_query_v1)})")

        # Stage 1 search: Get initial results for context (top 5)
        initial_results = self._semantic_search(
            hyde_query_v1,
            codebase_name,
            5,  # Get more results for context
            filters,
            for_query=False  # HyDE query is code, not natural language
        )

        if not initial_results:
            logger.warning("No initial results from HyDE v1, returning empty")
            return []

        # Build context from initial results
        context = self._build_temp_context(initial_results)
        logger.info(f"Built context from {len(initial_results)} initial results")

        # Stage 2: Generate enhanced HyDE query with context
        hyde_query_v2 = self.hyde_generator.generate_hyde_query_v2(
            original_query=query,
            context=context,
            hyde_query_v1=hyde_query_v1
        )

        if not hyde_query_v2:
            logger.warning("HyDE v2 generation failed, using v1 results")
            return initial_results[:top_k]

        logger.info(f"HyDE query v2 generated (length: {len(hyde_query_v2)})")

        # Stage 2 search: Final search with enhanced query
        final_results = self._semantic_search(
            hyde_query_v2,
            codebase_name,
            top_k * 2,  # Get more for potential reranking
            filters,
            for_query=False  # HyDE query is code
        )

        # Add metadata about HyDE
        for result in final_results:
            result.metadata.update({
                'search_method': 'hyde',
                'hyde_v1_length': len(hyde_query_v1),
                'hyde_v2_length': len(hyde_query_v2)
            })

        return final_results[:top_k]

    def _hyde_quick_search(
        self,
        query: str,
        codebase_name: str,
        top_k: int,
        filters: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """
        Perform quick HyDE search (1-stage only, faster).

        Generates hypothetical code from query and searches directly,
        without the context-enhanced second stage.

        Args:
            query: Natural language query
            codebase_name: Name of codebase to search
            top_k: Number of final results to return
            filters: Optional filters

        Returns:
            List of SearchResult objects
        """
        logger.info(f"Performing quick HyDE search for: {query}")

        # Generate quick HyDE query (single stage)
        hyde_query = self.hyde_generator.generate_quick_hyde(query)
        if not hyde_query:
            logger.warning("Quick HyDE generation failed, falling back to regular search")
            return self._semantic_search(query, codebase_name, top_k, filters)

        logger.info(f"Quick HyDE query generated (length: {len(hyde_query)})")

        # Perform semantic search with HyDE query
        results = self._semantic_search(
            hyde_query,
            codebase_name,
            top_k,
            filters,
            for_query=False  # HyDE query is code, not natural language
        )

        # Add metadata about HyDE
        for result in results:
            result.metadata.update({
                'search_method': 'hyde_quick',
                'hyde_query_length': len(hyde_query)
            })

        return results

    def _hyde_hybrid_search(
        self,
        query: str,
        codebase_name: str,
        top_k: int,
        filters: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """
        Perform HyDE-enhanced hybrid search.

        Combines HyDE semantic search with description search.

        Args:
            query: Natural language query
            codebase_name: Name of codebase
            top_k: Number of results
            filters: Optional filters

        Returns:
            List of SearchResult objects
        """
        # Get HyDE results (60% weight)
        hyde_results = self._hyde_search(query, codebase_name, top_k, filters)

        # Get description results (40% weight) - using AI-generated descriptions
        description_results = self._description_search(query, codebase_name, top_k, filters)

        # Combine results using RRF (Reciprocal Rank Fusion)
        combined = self._reciprocal_rank_fusion(
            [hyde_results, description_results],
            weights=[0.6, 0.4]  # Balanced: HyDE accuracy + Description natural language matching
        )

        return combined[:top_k]

    def _build_temp_context(self, results: List[SearchResult]) -> str:
        """
        Build temporary context from search results for HyDE v2.

        Args:
            results: Initial search results

        Returns:
            Concatenated code context
        """
        context_parts = []

        for i, result in enumerate(results[:5]):  # Limit to top 5
            context_parts.append(f"# File: {result.file_path}")
            if result.name:
                context_parts.append(f"# Name: {result.name}")
            if result.description:
                context_parts.append(f"# Description: {result.description[:200]}")
            context_parts.append(result.content)
            context_parts.append("")  # Blank line separator

        return "\n".join(context_parts)

    def _reciprocal_rank_fusion(
        self,
        result_lists: List[List[SearchResult]],
        weights: List[float] = None,
        k: int = 60
    ) -> List[SearchResult]:
        """
        Combine multiple result lists using Reciprocal Rank Fusion.

        Args:
            result_lists: List of result lists to combine
            weights: Optional weights for each list
            k: RRF constant (default 60)

        Returns:
            Combined and reranked results
        """
        if weights is None:
            weights = [1.0] * len(result_lists)

        # Compute RRF scores
        rrf_scores = {}

        for results, weight in zip(result_lists, weights):
            for rank, result in enumerate(results, start=1):
                score = weight * (1.0 / (k + rank))
                if result.id in rrf_scores:
                    rrf_scores[result.id]['score'] += score
                else:
                    rrf_scores[result.id] = {
                        'result': result,
                        'score': score
                    }

        # Sort by RRF score
        ranked = sorted(
            rrf_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )

        # Update scores and return results
        final_results = []
        for item in ranked:
            result = item['result']
            result.score = item['score']
            result.metadata['rrf_score'] = item['score']
            final_results.append(result)

        return final_results

    def _description_search(
        self,
        query: str,
        codebase_name: str,
        top_k: int = 10,
        filters: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """
        Search using description embeddings (natural language).
        Automatically translates Korean queries to English using translation agent.

        Args:
            query: Natural language query (Korean or English)
            codebase_name: Name of codebase
            top_k: Number of results
            filters: Optional filters

        Returns:
            List of SearchResult objects
        """
        original_query = query
        translated_query = query

        # Translate query if translation agent is available
        if self.translation_agent:
            try:
                logger.info(f"Translating query with agent: {query}")
                # Call translation agent
                result = self.translation_agent.run(f"Translate this search query to English: {query}")

                # Extract translated text from agent response
                if hasattr(result, 'content') and result.content:
                    translated_query = result.content.strip()
                    logger.info(f"Query translated: '{original_query}' → '{translated_query}'")
                else:
                    logger.warning("Translation agent returned empty response")

            except Exception as e:
                logger.warning(f"Translation agent failed: {e}, using original query")

        # Generate query embedding (natural language) with translated query
        embedding_result = self.embedding_generator.generate_embedding(translated_query, for_query=True)
        if not embedding_result:
            logger.error("Failed to generate query embedding for description search")
            return []

        # Search using description_embedding
        raw_results = self.vector_store.search_by_description(
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
                description=result['description'],
                score=1.0 - result['score'],  # Convert distance to similarity
                metadata={
                    'search_method': 'description',
                    'original_query': original_query,
                    'translated_query': translated_query if original_query != translated_query else None
                }
            )
            search_results.append(search_result)

        return search_results

    def search_with_description_fallback(
        self,
        query: str,
        codebase_name: str,
        top_k: int = 5,
        description_top_k: int = 10,
        filters: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """
        Search using description first, fallback to HyDE if not relevant.

        Strategy:
        1. Search by description (fast, direct match)
        2. Rerank results
        3. Judge relevance of top result using LLM
        4. If relevant: return results
        5. If not relevant: fallback to HyDE search

        Args:
            query: Natural language query
            codebase_name: Name of codebase
            top_k: Final number of results to return
            description_top_k: Number to fetch from description search
            filters: Optional filters

        Returns:
            List of SearchResult objects
        """
        logger.info(f"Starting description-fallback search for: {query}")

        # Step 1: Description search
        description_results = self._description_search(
            query, codebase_name, description_top_k, filters
        )

        if not description_results:
            logger.info("No description results, falling back to HyDE")
            return self._hyde_search(query, codebase_name, top_k, filters)

        # Step 2: Re-rank description results
        try:
            from .reranker import CodeReranker
            reranker = CodeReranker()
            reranked_results = reranker.rerank(description_results, query, top_k=description_top_k)
        except Exception as e:
            logger.warning(f"Reranking failed: {e}, using original results")
            reranked_results = description_results

        # Step 3: Judge relevance of top result
        try:
            from .relevance_judge import RelevanceJudge, SearchResult as JudgeSearchResult

            judge = RelevanceJudge()
            if not judge.is_enabled():
                logger.warning("Relevance judge not available, falling back to HyDE")
                return self._hyde_search(query, codebase_name, top_k, filters)

            # Create simplified result for judgment
            top_result = reranked_results[0]
            judge_result = JudgeSearchResult(
                content=top_result.content,
                description=top_result.description,
                name=top_result.name,
                chunk_type=top_result.chunk_type
            )

            is_relevant = judge.is_relevant(query, judge_result)

            if is_relevant:
                logger.info("Description results are relevant, returning them")
                # Add metadata
                for result in reranked_results[:top_k]:
                    result.metadata['search_method'] = 'description_fallback'
                    result.metadata['relevance_judgment'] = 'relevant'
                return reranked_results[:top_k]
            else:
                logger.info("Description results not relevant, falling back to HyDE")
                # Fallback to HyDE
                hyde_results = self._hyde_search(query, codebase_name, top_k, filters)
                for result in hyde_results:
                    result.metadata['search_method'] = 'description_fallback_hyde'
                    result.metadata['relevance_judgment'] = 'not_relevant'
                return hyde_results

        except Exception as e:
            logger.error(f"Error in relevance judgment: {e}, falling back to HyDE")
            return self._hyde_search(query, codebase_name, top_k, filters)