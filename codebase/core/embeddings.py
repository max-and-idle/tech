"""
Embedding generation for code chunks.
"""

import os
from typing import List, Dict, Optional, Any
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]
    hash: str


class EmbeddingGenerator:
    """Generates embeddings for code chunks."""
    
    def __init__(self, model: str = "gemini", cache_dir: str = ".embedding_cache"):
        """
        Initialize embedding generator.
        
        Args:
            model: Model to use ("gemini" or "openai")
            cache_dir: Directory to cache embeddings
        """
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.dimensions = None  # Will be detected from first embedding
        
        # Initialize model-specific components
        if model == "gemini":
            self._init_gemini()
        elif model == "openai":
            self._init_openai()
        else:
            raise ValueError(f"Unsupported model: {model}")
    
    def _init_gemini(self):
        """Initialize Gemini embeddings."""
        try:
            import google.generativeai as genai
            
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GEMINI_API_KEY not found in environment variables. Embeddings will not work until configured.")
                self.client = None
                return
            
            genai.configure(api_key=api_key)
            self.client = genai
            logger.info("Initialized Gemini embeddings")
        except ImportError:
            logger.error("google-generativeai not installed. Install with: pip install google-generativeai")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.client = None
    
    def _init_openai(self):
        """Initialize OpenAI embeddings."""
        try:
            from openai import OpenAI
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OPENAI_API_KEY not found in environment variables. Embeddings will not work until configured.")
                self.client = None
                return
            
            self.client = OpenAI(api_key=api_key)
            self.embedding_model = "text-embedding-3-small"
            logger.info("Initialized OpenAI embeddings")
        except ImportError:
            logger.error("openai not installed. Install with: pip install openai")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {e}")
            self.client = None
    
    def generate_embedding(self, text: str, metadata: Dict[str, Any] = None, for_query: bool = False) -> Optional[EmbeddingResult]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            metadata: Additional metadata
            for_query: If True, optimize for query (uses retrieval_query task type for Gemini)

        Returns:
            EmbeddingResult or None if failed
        """
        if not text.strip():
            return None

        # Check if client is available
        if self.client is None:
            logger.warning("No embedding client available. Please configure API keys.")
            return None

        # Generate hash for caching (include query flag in hash)
        cache_key = f"{text}_{for_query}"
        text_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()

        # Check cache first
        cached_result = self._load_from_cache(text_hash)
        if cached_result:
            return cached_result

        try:
            if self.model == "gemini":
                # Use different task_type for queries vs documents
                task_type = "retrieval_query" if for_query else "retrieval_document"
                embedding = self._generate_gemini_embedding(text, task_type=task_type)
            elif self.model == "openai":
                embedding = self._generate_openai_embedding(text)
            else:
                logger.error(f"Unknown model: {self.model}")
                return None

            if not embedding:
                return None

            # Auto-detect dimensions from first embedding
            if self.dimensions is None:
                self.dimensions = len(embedding)
                logger.info(f"Auto-detected embedding dimensions: {self.dimensions}")

            result = EmbeddingResult(
                text=text,
                embedding=embedding,
                metadata=metadata or {},
                hash=text_hash
            )

            # Cache the result
            self._save_to_cache(result)

            return result

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def generate_batch_embeddings(
        self, 
        texts: List[str], 
        metadata_list: List[Dict[str, Any]] = None,
        batch_size: int = 10
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            metadata_list: List of metadata dictionaries
            batch_size: Number of texts to process at once
            
        Returns:
            List of EmbeddingResult objects
        """
        if not texts:
            return []
        
        if metadata_list is None:
            metadata_list = [{}] * len(texts)
        
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_metadata = metadata_list[i:i + batch_size]
            
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            
            for text, metadata in zip(batch_texts, batch_metadata):
                result = self.generate_embedding(text, metadata)
                if result:
                    results.append(result)
        
        return results
    
    def _generate_gemini_embedding(self, text: str, task_type: str = "retrieval_document") -> Optional[List[float]]:
        """Generate embedding using Gemini."""
        try:
            # Use embed_content method
            result = self.client.embed_content(
                model="models/text-embedding-004",  # Latest embedding model
                content=text,
                task_type=task_type
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            return None
    
    def _generate_openai_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using OpenAI."""
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            return None
    
    def _load_from_cache(self, text_hash: str) -> Optional[EmbeddingResult]:
        """Load embedding from cache."""
        cache_file = self.cache_dir / f"{text_hash}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            return EmbeddingResult(
                text=data['text'],
                embedding=data['embedding'],
                metadata=data['metadata'],
                hash=data['hash']
            )
        except Exception as e:
            logger.warning(f"Error loading cache file {cache_file}: {e}")
            return None
    
    def _save_to_cache(self, result: EmbeddingResult):
        """Save embedding to cache."""
        cache_file = self.cache_dir / f"{result.hash}.json"
        
        try:
            data = {
                'text': result.text,
                'embedding': result.embedding,
                'metadata': result.metadata,
                'hash': result.hash
            }
            
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Error saving to cache: {e}")
    
    def clear_cache(self):
        """Clear embedding cache."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Embedding cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cache_files = list(self.cache_dir.glob("*.json"))
        
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'cache_dir': str(self.cache_dir),
            'num_cached_embeddings': len(cache_files),
            'total_cache_size_mb': total_size / (1024 * 1024)
        }