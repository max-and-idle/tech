"""
Translation tools for the query translator agent.
"""

import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Translation cache
_translation_cache: Dict[str, str] = {}


def translate_to_english(text: str) -> dict:
    """
    Translate text to English if it contains Korean.

    This tool is used by the translation agent to provide translation services.
    It includes caching to avoid repeated translations of the same text.

    Args:
        text: Input text (Korean or English)

    Returns:
        Dictionary with translation result and metadata
    """
    if not text or not text.strip():
        return {
            "original_text": text,
            "translated_text": text,
            "language_detected": "empty",
            "translation_needed": False,
            "cached": False
        }

    # Check cache first
    if text in _translation_cache:
        logger.debug(f"Using cached translation for: {text[:50]}...")
        return {
            "original_text": text,
            "translated_text": _translation_cache[text],
            "language_detected": "korean",
            "translation_needed": True,
            "cached": True
        }

    # Detect if text contains Korean
    contains_korean = bool(re.search(r'[가-힣]', text))

    if not contains_korean:
        # Already in English or no Korean detected
        return {
            "original_text": text,
            "translated_text": text,
            "language_detected": "english",
            "translation_needed": False,
            "cached": False
        }

    # Return info that translation is needed
    # The actual translation will be done by the agent's LLM
    return {
        "original_text": text,
        "translated_text": None,  # Will be filled by agent
        "language_detected": "korean",
        "translation_needed": True,
        "cached": False,
        "instruction": "Please translate the Korean text to English. Return only the English translation without any explanations."
    }


def cache_translation(original: str, translated: str) -> dict:
    """
    Cache a translation result.

    Args:
        original: Original text
        translated: Translated text

    Returns:
        Confirmation message
    """
    global _translation_cache

    _translation_cache[original] = translated

    # Limit cache size
    if len(_translation_cache) > 1000:
        # Remove oldest entries
        keys_to_remove = list(_translation_cache.keys())[:500]
        for key in keys_to_remove:
            del _translation_cache[key]
        logger.info("Translation cache pruned to 500 entries")

    return {
        "status": "cached",
        "cache_size": len(_translation_cache)
    }


def clear_translation_cache() -> dict:
    """
    Clear the translation cache.

    Returns:
        Confirmation message
    """
    global _translation_cache

    previous_size = len(_translation_cache)
    _translation_cache.clear()

    logger.info(f"Translation cache cleared ({previous_size} entries removed)")

    return {
        "status": "cleared",
        "previous_size": previous_size,
        "current_size": 0
    }


def get_cache_stats() -> dict:
    """
    Get translation cache statistics.

    Returns:
        Cache statistics
    """
    return {
        "total_cached": len(_translation_cache),
        "cached_queries": list(_translation_cache.keys())[:10]  # Show first 10
    }
