"""
LLM-based relevance judgment for search results.

Determines if a code chunk is relevant to user's query.
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Simplified search result for relevance judgment."""
    content: str
    description: Optional[str]
    name: str
    chunk_type: str


class RelevanceJudge:
    """Uses LLM to judge if search results are relevant to query."""

    def __init__(self, model: str = "gemini"):
        """
        Initialize relevance judge.

        Args:
            model: LLM model to use ("gemini" or "openai")
        """
        self.model = model

        if model == "gemini":
            self._init_gemini()
        elif model == "openai":
            self._init_openai()
        else:
            raise ValueError(f"Unsupported model: {model}")

        logger.info(f"RelevanceJudge initialized with model: {model}")

    def _init_gemini(self):
        """Initialize Gemini for relevance judgment."""
        try:
            import google.generativeai as genai

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GEMINI_API_KEY not found. Relevance judgment disabled.")
                self.client = None
                return

            genai.configure(api_key=api_key)
            self.client = genai
            self.generation_model = "gemini-2.5-flash"
            logger.info(f"Initialized Gemini for relevance judgment: {self.generation_model}")

        except ImportError:
            logger.error("google-generativeai not installed. Relevance judgment disabled.")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.client = None

    def _init_openai(self):
        """Initialize OpenAI for relevance judgment."""
        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OPENAI_API_KEY not found. Relevance judgment disabled.")
                self.client = None
                return

            self.client = OpenAI(api_key=api_key)
            self.generation_model = "gpt-4o-mini"
            logger.info(f"Initialized OpenAI for relevance judgment: {self.generation_model}")

        except ImportError:
            logger.error("openai not installed. Relevance judgment disabled.")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {e}")
            self.client = None

    def is_relevant(self, query: str, result: SearchResult) -> bool:
        """
        Judge if result is relevant to query.

        Args:
            query: User's natural language query
            result: Search result to judge

        Returns:
            True if relevant, False otherwise
        """
        if not self.client:
            logger.warning("LLM client not available, assuming not relevant")
            return False

        try:
            # Build prompt
            prompt = self._create_prompt(query, result)

            # Get judgment from LLM
            if self.model == "gemini":
                judgment = self._judge_with_gemini(prompt)
            else:
                judgment = self._judge_with_openai(prompt)

            # Parse judgment
            is_relevant = self._parse_judgment(judgment)
            logger.info(f"Relevance judgment for '{result.name}': {is_relevant}")
            return is_relevant

        except Exception as e:
            logger.error(f"Error judging relevance: {e}")
            return False

    def _create_prompt(self, query: str, result: SearchResult) -> str:
        """Create prompt for relevance judgment."""
        description_text = f"\n\nDescription: {result.description}" if result.description else ""

        prompt = f"""You are a code search relevance judge. Determine if the following code is relevant to the user's query.

User Query: {query}

Code Type: {result.chunk_type}
Code Name: {result.name}{description_text}

Code:
```
{result.content[:500]}
```

Question: Does this code satisfy the user's query? Would this code be useful for answering their question?

Answer with ONLY "Yes" or "No". No explanation needed."""

        return prompt

    def _judge_with_gemini(self, prompt: str) -> str:
        """Get judgment from Gemini."""
        try:
            model = self.client.GenerativeModel(
                model_name=self.generation_model
            )

            response = model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.1,
                    'max_output_tokens': 10,
                }
            )

            if response and response.text:
                return response.text.strip()
            return "No"

        except Exception as e:
            logger.error(f"Gemini judgment error: {e}")
            return "No"

    def _judge_with_openai(self, prompt: str) -> str:
        """Get judgment from OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model=self.generation_model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=10
            )

            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
            return "No"

        except Exception as e:
            logger.error(f"OpenAI judgment error: {e}")
            return "No"

    def _parse_judgment(self, judgment: str) -> bool:
        """Parse LLM judgment to boolean."""
        judgment_lower = judgment.lower().strip()

        # Check for Yes
        if "yes" in judgment_lower:
            return True

        # Default to No
        return False

    def is_enabled(self) -> bool:
        """Check if relevance judgment is available."""
        return self.client is not None
