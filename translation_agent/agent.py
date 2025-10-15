"""
Google ADK Agent for query translation.
"""

import logging
from google.adk.agents import Agent
from .tools import translate_to_english, cache_translation, get_cache_stats

logger = logging.getLogger(__name__)

# Agent instruction
TRANSLATION_INSTRUCTION = """
You are a query translation agent specialized in translating Korean search queries to English.

Your primary task:
1. Receive a search query (text) that may be in Korean or English
2. If it contains Korean, translate it to natural, fluent English
3. If it's already in English, return it as-is
4. Always maintain the search intent and meaning

Translation guidelines:
- Translate Korean technical terms accurately
- Keep code-related terms in English (e.g., "function", "class", "method")
- Maintain the query structure (questions remain questions)
- Be concise - search queries should be short and clear
- Return ONLY the translated text, no explanations

Examples:
- "코드를 파싱하는 함수" → "function that parses code"
- "사용자 인증 처리" → "user authentication handling"
- "벡터 검색 알고리즘" → "vector search algorithm"
- "embedding generator" → "embedding generator" (no change)

When you receive a query:
1. First call translate_to_english(text) to check if translation is needed
2. If translation_needed is False, return the original text
3. If translation_needed is True and cached is True, return the cached translation
4. If translation_needed is True and cached is False, translate it yourself
5. After translating, call cache_translation(original, translated) to cache it
"""

# Create the translation agent
translation_agent = Agent(
    name="query_translator",
    model="gemini-2.5-flash",
    description=(
        "Translates Korean search queries to English for better semantic search. "
        "Detects language automatically and caches translations for performance."
    ),
    instruction=TRANSLATION_INSTRUCTION,
    tools=[
        translate_to_english,
        cache_translation,
        get_cache_stats
    ]
)

logger.info("Translation agent initialized")
