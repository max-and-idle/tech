"""
Reranking utilities for improving search result quality.

Implements code-specific heuristics to rerank search results based on
relevance signals beyond vector similarity.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)


@dataclass
class RerankScore:
    """Detailed scoring breakdown for a search result."""
    vector_score: float
    name_match_score: float
    description_score: float
    chunk_type_score: float
    file_path_score: float
    total_score: float
    weights: Dict[str, float]


class CodeReranker:
    """Reranks code search results using multiple relevance signals."""

    def __init__(self, weights: Dict[str, float] = None):
        """
        Initialize code reranker.

        Args:
            weights: Custom weights for different scoring components.
                     Defaults to balanced weights.
        """
        self.weights = weights or {
            'vector': 0.4,        # Base vector similarity
            'name_match': 0.25,   # Function/class name matching
            'description': 0.15,  # Description relevance
            'chunk_type': 0.1,    # Preference for certain chunk types
            'file_path': 0.1      # File path relevance
        }

        logger.info(f"CodeReranker initialized with weights: {self.weights}")

    def rerank(
        self,
        results: List[Any],  # SearchResult objects
        query: str,
        top_k: Optional[int] = None
    ) -> List[Any]:
        """
        Rerank search results using code-specific heuristics.

        Args:
            results: List of SearchResult objects
            query: Original query string
            top_k: Number of results to return (None = all)

        Returns:
            Reranked list of SearchResult objects
        """
        if not results:
            return results

        # Extract query keywords
        query_keywords = self._extract_keywords(query)

        # Score each result
        scored_results = []
        for result in results:
            rerank_score = self._compute_score(result, query, query_keywords)

            # Update result score and metadata
            result.score = rerank_score.total_score
            result.metadata.update({
                'rerank_score': rerank_score.total_score,
                'vector_score': rerank_score.vector_score,
                'name_match_score': rerank_score.name_match_score,
                'description_score': rerank_score.description_score,
                'chunk_type_score': rerank_score.chunk_type_score,
                'file_path_score': rerank_score.file_path_score,
                'reranked': True
            })

            scored_results.append(result)

        # Sort by total score
        scored_results.sort(key=lambda x: x.score, reverse=True)

        # Return top_k if specified
        if top_k:
            return scored_results[:top_k]
        return scored_results

    def _compute_score(
        self,
        result: Any,
        query: str,
        query_keywords: List[str]
    ) -> RerankScore:
        """
        Compute comprehensive score for a search result.

        Args:
            result: SearchResult object
            query: Original query
            query_keywords: Extracted keywords from query

        Returns:
            RerankScore with detailed breakdown
        """
        # 1. Vector similarity score (already computed)
        vector_score = result.score

        # 2. Name matching score
        name_match_score = self._compute_name_match_score(
            result.name,
            query_keywords
        )

        # 3. Description relevance score
        description_score = self._compute_description_score(
            result.description,
            query_keywords
        )

        # 4. Chunk type preference score
        chunk_type_score = self._compute_chunk_type_score(
            result.chunk_type,
            query
        )

        # 5. File path relevance score
        file_path_score = self._compute_file_path_score(
            result.file_path,
            query_keywords
        )

        # Combine scores with weights
        total_score = (
            self.weights['vector'] * vector_score +
            self.weights['name_match'] * name_match_score +
            self.weights['description'] * description_score +
            self.weights['chunk_type'] * chunk_type_score +
            self.weights['file_path'] * file_path_score
        )

        return RerankScore(
            vector_score=vector_score,
            name_match_score=name_match_score,
            description_score=description_score,
            chunk_type_score=chunk_type_score,
            file_path_score=file_path_score,
            total_score=total_score,
            weights=self.weights
        )

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract meaningful keywords from query.

        Args:
            query: Search query

        Returns:
            List of keywords
        """
        # Convert to lowercase
        query_lower = query.lower()

        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'can', 'that', 'this',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'find', 'show', 'get', 'search', 'look', 'where', 'what', 'how'
        }

        # Extract words (alphanumeric + underscore)
        words = re.findall(r'\b\w+\b', query_lower)

        # Filter stop words and short words
        keywords = [
            word for word in words
            if word not in stop_words and len(word) > 2
        ]

        return keywords

    def _compute_name_match_score(
        self,
        name: str,
        query_keywords: List[str]
    ) -> float:
        """
        Compute score based on function/class name matching.

        Higher scores for exact matches, partial matches, and camelCase/snake_case awareness.
        """
        if not name or not query_keywords:
            return 0.0

        name_lower = name.lower()
        score = 0.0

        # Split camelCase and snake_case into parts
        name_parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', name)
        name_parts = [part.lower() for part in name_parts]

        # Also split by underscore
        name_parts.extend(name_lower.split('_'))

        for keyword in query_keywords:
            keyword_lower = keyword.lower()

            # Exact match in name
            if keyword_lower == name_lower:
                score += 1.0
            # Exact match in name parts
            elif keyword_lower in name_parts:
                score += 0.8
            # Substring match
            elif keyword_lower in name_lower:
                score += 0.5
            # Fuzzy match (edit distance)
            elif self._fuzzy_match(keyword_lower, name_lower):
                score += 0.3

        # Normalize by number of keywords
        if query_keywords:
            score = score / len(query_keywords)

        return min(score, 1.0)  # Cap at 1.0

    def _compute_description_score(
        self,
        description: Optional[str],
        query_keywords: List[str]
    ) -> float:
        """
        Compute score based on description relevance.
        """
        if not description or not query_keywords:
            return 0.0

        description_lower = description.lower()
        score = 0.0

        for keyword in query_keywords:
            # Count occurrences
            count = description_lower.count(keyword.lower())
            if count > 0:
                # Logarithmic scoring to avoid over-weighting frequent words
                score += min(0.3 * (1 + 0.5 * count), 0.5)

        # Normalize by number of keywords
        if query_keywords:
            score = score / len(query_keywords)

        return min(score, 1.0)

    def _compute_chunk_type_score(
        self,
        chunk_type: str,
        query: str
    ) -> float:
        """
        Compute score based on chunk type preferences.

        Certain queries imply preference for specific chunk types.
        """
        query_lower = query.lower()

        # Define preferences based on query patterns
        preferences = {
            'function': ['function', 'method', 'def', 'func'],
            'class': ['class', 'object', 'type'],
            'method': ['method', 'member function']
        }

        # Check if query suggests a chunk type
        for chunk_type_key, keywords in preferences.items():
            if any(keyword in query_lower for keyword in keywords):
                if chunk_type == chunk_type_key:
                    return 1.0
                elif chunk_type in ['function', 'method'] and chunk_type_key in ['function', 'method']:
                    return 0.7  # Functions and methods are similar

        # Default preference: function > class > method > text
        type_scores = {
            'function': 0.8,
            'class': 0.7,
            'method': 0.6,
            'text': 0.3
        }

        return type_scores.get(chunk_type, 0.5)

    def _compute_file_path_score(
        self,
        file_path: str,
        query_keywords: List[str]
    ) -> float:
        """
        Compute score based on file path relevance.

        Higher scores if keywords appear in path.
        """
        if not file_path or not query_keywords:
            return 0.0

        file_path_lower = file_path.lower()
        score = 0.0

        for keyword in query_keywords:
            if keyword.lower() in file_path_lower:
                score += 0.5

        # Normalize by number of keywords
        if query_keywords:
            score = score / len(query_keywords)

        return min(score, 1.0)

    def _fuzzy_match(self, s1: str, s2: str, threshold: float = 0.8) -> bool:
        """
        Simple fuzzy matching based on character overlap.

        Args:
            s1: First string
            s2: Second string
            threshold: Similarity threshold (0-1)

        Returns:
            True if strings are similar enough
        """
        if not s1 or not s2:
            return False

        # Simple character-based similarity
        set1 = set(s1)
        set2 = set(s2)

        intersection = set1.intersection(set2)
        union = set1.union(set2)

        if not union:
            return False

        similarity = len(intersection) / len(union)
        return similarity >= threshold


class ConfidenceFilter:
    """Filters search results based on confidence thresholds."""

    def __init__(self, min_score: float = 0.3):
        """
        Initialize confidence filter.

        Args:
            min_score: Minimum score threshold (0-1)
        """
        self.min_score = min_score

    def filter(self, results: List[Any]) -> List[Any]:
        """
        Filter results below confidence threshold.

        Args:
            results: List of SearchResult objects

        Returns:
            Filtered list
        """
        filtered = [r for r in results if r.score >= self.min_score]

        logger.info(
            f"Filtered {len(results)} results to {len(filtered)} "
            f"(threshold: {self.min_score})"
        )

        return filtered


class DiversityFilter:
    """Ensures diversity in search results."""

    def __init__(self, max_per_file: int = 2):
        """
        Initialize diversity filter.

        Args:
            max_per_file: Maximum results per file
        """
        self.max_per_file = max_per_file

    def filter(self, results: List[Any]) -> List[Any]:
        """
        Filter to ensure diversity across files.

        Args:
            results: List of SearchResult objects

        Returns:
            Diversified list
        """
        file_counts = {}
        diverse_results = []

        for result in results:
            file_path = result.file_path
            count = file_counts.get(file_path, 0)

            if count < self.max_per_file:
                diverse_results.append(result)
                file_counts[file_path] = count + 1

        logger.info(
            f"Diversified {len(results)} results to {len(diverse_results)} "
            f"(max per file: {self.max_per_file})"
        )

        return diverse_results
