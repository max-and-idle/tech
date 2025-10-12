"""
AI-powered docstring generation for code chunks without docstrings.
"""

import os
import hashlib
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DocstringGenerator:
    """Generates docstrings for code using AI models."""

    def __init__(self, model: str = "gemini", cache_dir: str = ".docstring_cache"):
        """
        Initialize docstring generator.

        Args:
            model: Model to use ("gemini" or "openai")
            cache_dir: Directory to cache generated docstrings
        """
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Initialize model-specific components
        if model == "gemini":
            self._init_gemini()
        elif model == "openai":
            self._init_openai()
        else:
            raise ValueError(f"Unsupported model: {model}")

    def _init_gemini(self):
        """Initialize Gemini for text generation."""
        try:
            import google.generativeai as genai

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GEMINI_API_KEY not found. AI docstring generation disabled.")
                self.client = None
                return

            genai.configure(api_key=api_key)
            self.client = genai
            logger.info("Initialized Gemini for docstring generation")
        except ImportError:
            logger.error("google-generativeai not installed. AI docstring generation disabled.")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.client = None

    def _init_openai(self):
        """Initialize OpenAI for text generation."""
        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OPENAI_API_KEY not found. AI docstring generation disabled.")
                self.client = None
                return

            self.client = OpenAI(api_key=api_key)
            self.generation_model = "gpt-3.5-turbo"
            logger.info("Initialized OpenAI for docstring generation")
        except ImportError:
            logger.error("openai not installed. AI docstring generation disabled.")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {e}")
            self.client = None

    def generate_docstring(
        self,
        code: str,
        chunk_type: str = "function",
        name: str = "unknown",
        language: str = "python"
    ) -> Optional[str]:
        """
        Generate a docstring for a code chunk.

        Args:
            code: The code to analyze
            chunk_type: Type of code chunk ('function', 'class', 'method')
            name: Name of the function/class
            language: Programming language

        Returns:
            Generated docstring or None if failed
        """
        if not code.strip():
            return None

        # Check if client is available
        if self.client is None:
            logger.debug("AI client not available for docstring generation")
            return None

        # Generate cache key
        cache_key = self._generate_cache_key(code, chunk_type, name)

        # Check cache first
        cached_docstring = self._load_from_cache(cache_key)
        if cached_docstring:
            logger.debug(f"Using cached docstring for {name}")
            return cached_docstring

        try:
            # Generate docstring using AI
            if self.model == "gemini":
                docstring = self._generate_with_gemini(code, chunk_type, name, language)
            elif self.model == "openai":
                docstring = self._generate_with_openai(code, chunk_type, name, language)
            else:
                logger.error(f"Unknown model: {self.model}")
                return None

            if docstring:
                # Cache the result
                self._save_to_cache(cache_key, docstring)
                logger.debug(f"Generated and cached docstring for {name}")
                return docstring

            return None

        except Exception as e:
            logger.warning(f"Error generating docstring for {name}: {e}")
            return None

    def _generate_with_gemini(
        self,
        code: str,
        chunk_type: str,
        name: str,
        language: str
    ) -> Optional[str]:
        """Generate docstring using Gemini."""
        try:
            prompt = self._create_prompt(code, chunk_type, name, language)

            # Create a GenerativeModel instance and use it
            model = self.client.GenerativeModel("models/gemini-2.0-flash-exp")
            response = model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'max_output_tokens': 150,
                }
            )

            if response and response.text:
                # Clean up the response
                docstring = response.text.strip()
                # Remove markdown code blocks if present
                if docstring.startswith('```') or docstring.startswith('`'):
                    lines = docstring.split('\n')
                    # Remove first and last line if they're markdown markers
                    if lines[0].startswith('```') or lines[0].startswith('`'):
                        lines = lines[1:]
                    if lines and (lines[-1].startswith('```') or lines[-1].startswith('`')):
                        lines = lines[:-1]
                    docstring = '\n'.join(lines).strip()

                return docstring

            return None

        except Exception as e:
            logger.warning(f"Gemini generation error: {e}")
            return None

    def _generate_with_openai(
        self,
        code: str,
        chunk_type: str,
        name: str,
        language: str
    ) -> Optional[str]:
        """Generate docstring using OpenAI."""
        try:
            prompt = self._create_prompt(code, chunk_type, name, language)

            response = self.client.chat.completions.create(
                model=self.generation_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that writes concise, clear documentation for code."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )

            if response.choices and response.choices[0].message.content:
                docstring = response.choices[0].message.content.strip()
                # Clean up markdown if present
                if docstring.startswith('```') or docstring.startswith('`'):
                    lines = docstring.split('\n')
                    if lines[0].startswith('```') or lines[0].startswith('`'):
                        lines = lines[1:]
                    if lines and (lines[-1].startswith('```') or lines[-1].startswith('`')):
                        lines = lines[:-1]
                    docstring = '\n'.join(lines).strip()

                return docstring

            return None

        except Exception as e:
            logger.warning(f"OpenAI generation error: {e}")
            return None

    def _create_prompt(self, code: str, chunk_type: str, name: str, language: str) -> str:
        """Create a prompt for docstring generation."""
        # Limit code length to avoid token limits
        max_code_length = 2000
        if len(code) > max_code_length:
            code = code[:max_code_length] + "\n... (truncated)"

        if chunk_type == "class":
            return f"""Analyze the following {language} class and write a concise one-line docstring (maximum 100 characters) that describes what this class does.

Class name: {name}

Code:
```{language}
{code}
```

Respond with ONLY the docstring text, without quotes or markdown. Keep it brief and clear."""

        elif chunk_type in ["function", "method"]:
            return f"""Analyze the following {language} {chunk_type} and write a concise one-line docstring (maximum 100 characters) that describes what this {chunk_type} does.

{chunk_type.capitalize()} name: {name}

Code:
```{language}
{code}
```

Respond with ONLY the docstring text, without quotes or markdown. Keep it brief and clear."""

        else:
            return f"""Analyze the following {language} code and write a concise one-line description (maximum 100 characters).

Code:
```{language}
{code}
```

Respond with ONLY the description text, without quotes or markdown. Keep it brief and clear."""

    def _generate_cache_key(self, code: str, chunk_type: str, name: str) -> str:
        """Generate a cache key for a code chunk."""
        content = f"{chunk_type}:{name}:{code}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[str]:
        """Load docstring from cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('docstring')
        except Exception as e:
            logger.warning(f"Error loading cache file {cache_file}: {e}")
            return None

    def _save_to_cache(self, cache_key: str, docstring: str):
        """Save docstring to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            data = {
                'docstring': docstring,
                'generated_at': str(Path(__file__).stat().st_mtime)
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Error saving to cache: {e}")

    def clear_cache(self):
        """Clear docstring cache."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Docstring cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            'cache_dir': str(self.cache_dir),
            'num_cached_docstrings': len(cache_files),
            'total_cache_size_kb': total_size / 1024
        }
