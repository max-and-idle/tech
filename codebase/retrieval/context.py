"""
Context management for code retrieval and display.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass
from pathlib import Path
import textwrap

from .search import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class CodeContext:
    """Context information for a code chunk."""
    file_path: str
    content: str
    line_start: int
    line_end: int
    language: str
    surrounding_context: Optional[str] = None
    imports: List[str] = None
    related_chunks: List[str] = None


class ContextManager:
    """Manages context building and optimization for code retrieval."""
    
    def __init__(self, max_context_tokens: int = 8000):
        """
        Initialize context manager.
        
        Args:
            max_context_tokens: Maximum context window size in tokens
        """
        self.max_context_tokens = max_context_tokens
    
    def build_context_from_results(
        self, 
        search_results: List[SearchResult], 
        query: str = "",
        include_metadata: bool = True
    ) -> str:
        """
        Build formatted context from search results.
        
        Args:
            search_results: List of search results
            query: Original query for context
            include_metadata: Whether to include metadata in context
            
        Returns:
            Formatted context string
        """
        if not search_results:
            return "No relevant code found."
        
        context_parts = []
        
        # Add query information
        if query:
            context_parts.append(f"Query: {query}\n")
        
        # Group results by file for better organization
        results_by_file = {}
        for result in search_results:
            file_path = result.file_path
            if file_path not in results_by_file:
                results_by_file[file_path] = []
            results_by_file[file_path].append(result)
        
        # Build context for each file
        for file_path, file_results in results_by_file.items():
            context_parts.append(f"\n## File: {file_path}\n")
            
            # Sort results by line number within file
            file_results.sort(key=lambda x: x.line_start)
            
            for i, result in enumerate(file_results):
                # Add result header
                if include_metadata:
                    header_parts = [
                        f"**{result.chunk_type.title()}**: `{result.name}`",
                        f"Lines {result.line_start}-{result.line_end}",
                        f"Language: {result.language}",
                        f"Score: {result.score:.3f}"
                    ]
                    
                    if result.parent_name:
                        header_parts.insert(1, f"Parent: `{result.parent_name}`")
                    
                    context_parts.append(" | ".join(header_parts))
                    context_parts.append("")
                
                # Add description if available
                if result.description:
                    context_parts.append(f"*Description: {result.description}*")
                    context_parts.append("")
                
                # Add code content
                formatted_code = self._format_code_block(
                    result.content, 
                    result.language, 
                    result.line_start
                )
                context_parts.append(formatted_code)
                context_parts.append("")
        
        # Join all parts
        context = "\n".join(context_parts)
        
        # Optimize for token limit
        optimized_context = self.optimize_context_window(context)
        
        return optimized_context
    
    def build_focused_context(
        self, 
        primary_result: SearchResult,
        related_results: List[SearchResult] = None,
        file_content: str = None
    ) -> Dict[str, Any]:
        """
        Build focused context around a primary result with related code.
        
        Args:
            primary_result: Main search result to focus on
            related_results: Additional related results
            file_content: Full file content if available
            
        Returns:
            Dictionary with focused context information
        """
        context = {
            'primary': primary_result,
            'file_path': primary_result.file_path,
            'language': primary_result.language,
            'main_content': primary_result.content,
            'related': related_results or [],
            'surrounding_context': None,
            'imports': [],
            'summary': ""
        }
        
        # If we have full file content, extract surrounding context
        if file_content:
            context['surrounding_context'] = self._extract_surrounding_context(
                primary_result, file_content
            )
            context['imports'] = self._extract_imports(file_content, primary_result.language)
        
        # Generate summary
        context['summary'] = self._generate_context_summary(primary_result, related_results)
        
        return context
    
    def _format_code_block(
        self, 
        code: str, 
        language: str, 
        start_line: int = 1
    ) -> str:
        """
        Format code with syntax highlighting and line numbers.
        
        Args:
            code: Code content
            language: Programming language
            start_line: Starting line number
            
        Returns:
            Formatted code block
        """
        # Clean up code
        code = code.strip()
        
        # Add line numbers
        lines = code.split('\n')
        numbered_lines = []
        for i, line in enumerate(lines):
            line_num = start_line + i
            numbered_lines.append(f"{line_num:4d} | {line}")
        
        # Wrap in code block with language
        formatted = f"```{language}\n" + "\n".join(numbered_lines) + "\n```"
        
        return formatted
    
    def _extract_surrounding_context(
        self, 
        result: SearchResult, 
        file_content: str,
        context_lines: int = 5
    ) -> str:
        """
        Extract surrounding context from file content.
        
        Args:
            result: Search result
            file_content: Full file content
            context_lines: Lines of context to include
            
        Returns:
            Surrounding context
        """
        lines = file_content.split('\n')
        
        start_idx = max(0, result.line_start - 1 - context_lines)
        end_idx = min(len(lines), result.line_end + context_lines)
        
        context_lines = lines[start_idx:end_idx]
        
        # Add line numbers
        numbered_context = []
        for i, line in enumerate(context_lines):
            line_num = start_idx + i + 1
            prefix = ">>> " if result.line_start <= line_num <= result.line_end else "    "
            numbered_context.append(f"{prefix}{line_num:4d} | {line}")
        
        return "\n".join(numbered_context)
    
    def _extract_imports(self, file_content: str, language: str) -> List[str]:
        """
        Extract import statements from file content.
        
        Args:
            file_content: Full file content
            language: Programming language
            
        Returns:
            List of import statements
        """
        imports = []
        lines = file_content.split('\n')
        
        if language == 'python':
            import_keywords = ['import ', 'from ']
        elif language in ['javascript', 'typescript']:
            import_keywords = ['import ', 'require(', 'const ', 'let ', 'var ']
        elif language == 'java':
            import_keywords = ['import ']
        else:
            return imports
        
        for line in lines:
            line = line.strip()
            for keyword in import_keywords:
                if line.startswith(keyword):
                    imports.append(line)
                    break
        
        return imports[:10]  # Limit to first 10 imports
    
    def _generate_context_summary(
        self, 
        primary_result: SearchResult,
        related_results: List[SearchResult] = None
    ) -> str:
        """Generate a summary of the context."""
        summary_parts = [
            f"Primary result: {primary_result.chunk_type} '{primary_result.name}' in {primary_result.file_path}"
        ]
        
        if primary_result.parent_name:
            summary_parts.append(f"Part of: {primary_result.parent_name}")
        
        if related_results:
            related_names = [r.name for r in related_results[:3]]
            summary_parts.append(f"Related: {', '.join(related_names)}")
        
        return " | ".join(summary_parts)
    
    def optimize_context_window(
        self, 
        context: str, 
        max_tokens: int = None
    ) -> str:
        """
        Optimize context to fit within token limit.
        
        Args:
            context: Context string to optimize
            max_tokens: Maximum tokens (uses instance default if None)
            
        Returns:
            Optimized context string
        """
        max_tokens = max_tokens or self.max_context_tokens
        
        # Simple token estimation (roughly 4 characters per token)
        estimated_tokens = len(context) // 4
        
        if estimated_tokens <= max_tokens:
            return context
        
        logger.info(f"Context too large ({estimated_tokens} tokens), optimizing...")
        
        # Split context into sections
        sections = context.split('\n## ')
        
        if len(sections) <= 1:
            # Single section, truncate from the end
            char_limit = max_tokens * 4
            truncated = context[:char_limit]
            truncated += "\n\n[... Content truncated due to length ...]"
            return truncated
        
        # Multiple sections, keep the most important ones
        optimized_sections = ['## ' + sections[0]]  # Keep header
        
        current_length = len(sections[0])
        char_limit = max_tokens * 4
        
        for section in sections[1:]:
            section_with_header = '\n## ' + section
            if current_length + len(section_with_header) < char_limit:
                optimized_sections.append(section_with_header)
                current_length += len(section_with_header)
            else:
                optimized_sections.append(
                    "\n\n[... Additional results truncated due to length ...]"
                )
                break
        
        return ''.join(optimized_sections)
    
    def format_search_summary(
        self, 
        query: str, 
        results: List[SearchResult],
        total_matches: int = None
    ) -> str:
        """
        Create a formatted summary of search results.
        
        Args:
            query: Search query
            results: Search results
            total_matches: Total number of matches
            
        Returns:
            Formatted summary
        """
        if not results:
            return f"No results found for query: '{query}'"
        
        summary_parts = [
            f"Search Results for: '{query}'",
            f"Found {len(results)} relevant code chunks"
        ]
        
        if total_matches and total_matches > len(results):
            summary_parts.append(f"(showing top {len(results)} of {total_matches} total matches)")
        
        # Group by file and type
        files = set(r.file_path for r in results)
        types = {}
        for result in results:
            types[result.chunk_type] = types.get(result.chunk_type, 0) + 1
        
        summary_parts.extend([
            f"Files: {len(files)}",
            f"Types: {', '.join(f'{k}({v})' for k, v in types.items())}"
        ])
        
        return " | ".join(summary_parts)