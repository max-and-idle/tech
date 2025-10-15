"""
Translation Agent for query translation.
"""

from .agent import translation_agent
from .tools import translate_to_english, cache_translation, get_cache_stats, clear_translation_cache

# Google ADK requires root_agent
root_agent = translation_agent

__all__ = [
    'translation_agent',
    'root_agent',
    'translate_to_english',
    'cache_translation',
    'get_cache_stats',
    'clear_translation_cache'
]
