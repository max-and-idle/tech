"""
HyDE (Hypothetical Document Embeddings) implementation for code search.

HyDE improves semantic search by generating hypothetical code snippets from
natural language queries, bridging the gap between user intent and code embeddings.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from .prompts import HYDE_SYSTEM_PROMPT, HYDE_V2_SYSTEM_PROMPT, HYDE_QUICK_PROMPT

logger = logging.getLogger(__name__)


class HyDEGenerator:
    """Generates hypothetical code documents for improved semantic search."""

    def __init__(self, model: str = None):
        """
        Initialize HyDE generator.

        Args:
            model: LLM model to use ("gemini" or "openai").
                   Defaults to HYDE_MODEL env var or "gemini"
        """
        self.model = model or os.getenv("HYDE_MODEL", "gemini")
        self.enabled = os.getenv("HYDE_ENABLED", "true").lower() == "true"

        if self.model == "gemini":
            self._init_gemini()
        elif self.model == "openai":
            self._init_openai()
        else:
            raise ValueError(f"Unsupported HyDE model: {self.model}")

        logger.info(f"HyDE generator initialized with model: {self.model}, enabled: {self.enabled}")

    def _init_gemini(self):
        """Initialize Gemini for HyDE generation."""
        try:
            import google.generativeai as genai

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GEMINI_API_KEY not found. HyDE will be disabled.")
                self.client = None
                self.enabled = False
                return

            genai.configure(api_key=api_key)
            self.client = genai
            # Use Gemini Flash for code generation (faster and cheaper)
            self.generation_model = "gemini-2.5-flash"
            logger.info(f"Initialized Gemini HyDE with model: {self.generation_model}")

        except ImportError:
            logger.error("google-generativeai not installed. HyDE disabled.")
            self.client = None
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Gemini for HyDE: {e}")
            self.client = None
            self.enabled = False

    def _init_openai(self):
        """Initialize OpenAI for HyDE generation."""
        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OPENAI_API_KEY not found. HyDE will be disabled.")
                self.client = None
                self.enabled = False
                return

            self.client = OpenAI(api_key=api_key)
            # Use GPT-4o-mini for cost-effectiveness (as per reference implementation)
            self.generation_model = "gpt-4o-mini"
            logger.info(f"Initialized OpenAI HyDE with model: {self.generation_model}")

        except ImportError:
            logger.error("openai not installed. HyDE disabled.")
            self.client = None
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI for HyDE: {e}")
            self.client = None
            self.enabled = False

    def generate_hyde_query(self, query: str) -> Optional[str]:
        """
        Generate first-stage HyDE query: Convert natural language to hypothetical code.

        Args:
            query: Natural language query from user

        Returns:
            Hypothetical code snippet or None if generation fails
        """
        if not self.enabled or not self.client:
            logger.warning("HyDE is disabled, returning original query")
            return query

        try:
            logger.info(f"Generating HyDE query (stage 1) for: {query}")

            if self.model == "gemini":
                hyde_query = self._generate_with_gemini(HYDE_SYSTEM_PROMPT, query)
            else:
                hyde_query = self._generate_with_openai(HYDE_SYSTEM_PROMPT, query)

            if hyde_query:
                logger.info(f"Generated HyDE query (stage 1): {hyde_query[:200]}...")
                return hyde_query
            else:
                logger.warning("HyDE generation failed, returning original query")
                return query

        except Exception as e:
            logger.error(f"Error generating HyDE query: {e}")
            return query

    def generate_hyde_query_v2(
        self,
        original_query: str,
        context: str,
        hyde_query_v1: str
    ) -> Optional[str]:
        """
        Generate second-stage HyDE query: Enhance with context from initial search.

        Args:
            original_query: Original natural language query
            context: Code snippets from initial search results
            hyde_query_v1: First-stage HyDE query

        Returns:
            Enhanced hypothetical code snippet
        """
        if not self.enabled or not self.client:
            logger.warning("HyDE is disabled, returning v1 query")
            return hyde_query_v1

        try:
            logger.info(f"Generating HyDE query (stage 2) with context")

            # Format the prompt with original query and context
            prompt = HYDE_V2_SYSTEM_PROMPT.format(
                query=original_query,
                context=context[:3000]  # Limit context size
            )

            user_message = f"Predict the answer to the query: {hyde_query_v1}"

            if self.model == "gemini":
                hyde_query_v2 = self._generate_with_gemini(prompt, user_message)
            else:
                hyde_query_v2 = self._generate_with_openai(prompt, user_message)

            if hyde_query_v2:
                logger.info(f"Generated HyDE query (stage 2): {hyde_query_v2[:200]}...")
                return hyde_query_v2
            else:
                logger.warning("HyDE v2 generation failed, returning v1 query")
                return hyde_query_v1

        except Exception as e:
            logger.error(f"Error generating HyDE query v2: {e}")
            return hyde_query_v1

    def generate_quick_hyde(self, query: str) -> Optional[str]:
        """
        Generate quick single-stage HyDE query for faster searches.

        Args:
            query: Natural language query

        Returns:
            Quick hypothetical code snippet
        """
        if not self.enabled or not self.client:
            return query

        try:
            prompt = HYDE_QUICK_PROMPT.format(query=query)

            if self.model == "gemini":
                return self._generate_with_gemini("", prompt)
            else:
                return self._generate_with_openai("", prompt)

        except Exception as e:
            logger.error(f"Error generating quick HyDE: {e}")
            return query

    def _generate_with_gemini(self, system_prompt: str, user_message: str) -> Optional[str]:
        """Generate text using Gemini."""
        try:
            model = self.client.GenerativeModel(
                model_name=self.generation_model,
                system_instruction=system_prompt if system_prompt else None
            )

            response = model.generate_content(user_message)

            if response and response.text:
                return self._clean_code_output(response.text)
            return None

        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            return None

    def _generate_with_openai(self, system_prompt: str, user_message: str) -> Optional[str]:
        """Generate text using OpenAI."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_message})

            response = self.client.chat.completions.create(
                model=self.generation_model,
                messages=messages,
                temperature=0.3,  # Lower temperature for more focused code generation
                max_tokens=500
            )

            if response.choices and response.choices[0].message:
                return self._clean_code_output(response.choices[0].message.content)
            return None

        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            return None

    def _clean_code_output(self, text: str) -> str:
        """
        Clean the generated code output.

        Removes markdown code blocks and extra whitespace.
        """
        # Remove markdown code blocks
        text = text.strip()

        # Remove ```language or ``` markers
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line with ```
            if lines:
                lines = lines[1:]
            # Remove last line with ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        return text.strip()

    def is_enabled(self) -> bool:
        """Check if HyDE is enabled and available."""
        return self.enabled and self.client is not None
