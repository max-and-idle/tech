"""
Tree-sitter based code parser for extracting code structures.
"""

from typing import List, Dict, Optional, Tuple, Any
import tree_sitter
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Optional: AI docstring generator (lazily imported)
_docstring_generator = None


@dataclass
class CodeChunk:
    """Represents a chunk of code with metadata."""
    content: str
    language: str
    chunk_type: str  # 'function', 'class', 'method', 'variable', 'comment'
    name: str
    file_path: str
    line_start: int
    line_end: int
    parent_name: Optional[str] = None
    description: Optional[str] = None


class CodeParser:
    """Tree-sitter based code parser for multiple languages."""

    def __init__(self, ai_docstring_enabled: bool = True, ai_model: str = "gemini"):
        """
        Initialize the code parser with supported languages.

        Args:
            ai_docstring_enabled: Whether to generate docstrings using AI when not present
            ai_model: AI model to use for docstring generation ("gemini" or "openai")
        """
        self.parsers = {}
        self.languages = {}
        self.ai_docstring_enabled = ai_docstring_enabled
        self.ai_model = ai_model
        self._docstring_generator = None
        self._setup_languages()
    
    def _setup_languages(self):
        """Set up tree-sitter parsers for supported languages."""
        language_modules = {
            'python': 'tree_sitter_python',
            'javascript': 'tree_sitter_javascript', 
            'java': 'tree_sitter_java',
            'go': 'tree_sitter_go',
            'rust': 'tree_sitter_rust'
        }
        
        for lang_name, module_name in language_modules.items():
            try:
                # Import the language module
                lang_module = __import__(module_name)
                
                # Get language and create parser
                language = tree_sitter.Language(lang_module.language())
                parser = tree_sitter.Parser(language)
                
                self.languages[lang_name] = language
                self.parsers[lang_name] = parser
                logger.info(f"Initialized parser for {lang_name}")
            except ImportError as e:
                logger.warning(f"Could not import {module_name}: {e}")
            except Exception as e:
                logger.warning(f"Could not initialize parser for {lang_name}: {e}")
    
    def parse_file(self, file_path: str, content: str, language: str) -> List[CodeChunk]:
        """Parse a file and extract code chunks."""
        if language not in self.parsers:
            logger.warning(f"Language {language} not supported, treating as plain text")
            return self._parse_as_plain_text(file_path, content, language)
        
        try:
            parser = self.parsers[language]
            tree = parser.parse(bytes(content, 'utf8'))
            
            chunks = []
            if language == 'python':
                chunks.extend(self._parse_python(tree.root_node, content, file_path))
            elif language in ['javascript', 'typescript']:
                chunks.extend(self._parse_javascript(tree.root_node, content, file_path, language))
            elif language == 'java':
                chunks.extend(self._parse_java(tree.root_node, content, file_path))
            elif language == 'go':
                chunks.extend(self._parse_go(tree.root_node, content, file_path))
            elif language == 'rust':
                chunks.extend(self._parse_rust(tree.root_node, content, file_path))
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return self._parse_as_plain_text(file_path, content, language)
    
    def _parse_as_plain_text(self, file_path: str, content: str, language: str) -> List[CodeChunk]:
        """Fallback method to parse as plain text."""
        lines = content.split('\n')
        chunks = []
        
        # Split into chunks of ~50 lines
        chunk_size = 50
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i+chunk_size]
            chunk_content = '\n'.join(chunk_lines)
            
            chunk = CodeChunk(
                content=chunk_content,
                language=language,
                chunk_type='text',
                name=f"chunk_{i//chunk_size}",
                file_path=file_path,
                line_start=i + 1,
                line_end=min(i + chunk_size, len(lines))
            )
            chunks.append(chunk)
        
        return chunks
    
    def _get_node_text(self, node, source_code: str) -> str:
        """
        Extract text from a tree-sitter node.

        Args:
            node: Tree-sitter node with byte offsets
            source_code: Source code as string

        Returns:
            Extracted text from the node

        Note:
            Tree-sitter uses byte offsets, but Python strings use character indices.
            We need to convert to bytes, slice, then decode back to handle multi-byte
            UTF-8 characters correctly.
        """
        # Convert to bytes, extract using byte offsets, then decode back
        source_bytes = source_code.encode('utf-8')
        node_bytes = source_bytes[node.start_byte:node.end_byte]
        return node_bytes.decode('utf-8')

    def _extract_docstring(self, docstring_text: str) -> str:
        """
        Extract docstring content by removing quotes.

        Args:
            docstring_text: Raw docstring text with quotes

        Returns:
            Cleaned docstring without quotes
        """
        if not docstring_text:
            return ""

        text = docstring_text.strip()

        # Try to remove quotes in order of specificity
        for quote in ['"""', "'''", '"', "'"]:
            if text.startswith(quote) and text.endswith(quote) and len(text) >= 2 * len(quote):
                return text[len(quote):-len(quote)].strip()

        # If no quotes found, return as-is
        return text

    def _get_or_generate_description(
        self,
        node,
        content: str,
        chunk_type: str,
        name: str,
        language: str = "python"
    ) -> Optional[str]:
        """
        Extract description from node or generate using AI if not present.

        Args:
            node: Tree-sitter node
            content: Source code content
            chunk_type: Type of code chunk ('function', 'class', etc.)
            name: Name of the function/class
            language: Programming language

        Returns:
            Description text or None
        """
        # First, try to extract description from the code
        description = None

        if len(node.children) > 0:
            body = node.children[-1]  # function/class body
            if body.type == 'block':
                for stmt in body.children:
                    if stmt.type == 'expression_statement':
                        expr = stmt.children[0] if stmt.children else None
                        if expr and expr.type == 'string':
                            description_raw = self._get_node_text(expr, content)
                            description = self._extract_docstring(description_raw)
                            break

        # If description exists, return it
        if description:
            return description

        # If no description and AI is enabled, generate one
        if self.ai_docstring_enabled:
            return self._generate_ai_description(node, content, chunk_type, name, language)

        return None

    def _generate_ai_description(
        self,
        node,
        content: str,
        chunk_type: str,
        name: str,
        language: str
    ) -> Optional[str]:
        """
        Generate description using AI.

        Args:
            node: Tree-sitter node
            content: Source code content
            chunk_type: Type of code chunk
            name: Name of the function/class
            language: Programming language

        Returns:
            Generated description or None
        """
        # Lazy import and initialization
        if self._docstring_generator is None:
            try:
                from .docstring_generator import DocstringGenerator
                self._docstring_generator = DocstringGenerator(model=self.ai_model)
                logger.info("Initialized AI docstring generator")
            except Exception as e:
                logger.warning(f"Failed to initialize AI docstring generator: {e}")
                # Disable AI generation if initialization fails
                self.ai_docstring_enabled = False
                return None

        # Generate description
        try:
            code = self._get_node_text(node, content)
            description = self._docstring_generator.generate_docstring(
                code=code,
                chunk_type=chunk_type,
                name=name,
                language=language
            )
            return description
        except Exception as e:
            logger.warning(f"Error generating AI description for {name}: {e}")
            return None
    
    def _parse_python(self, root_node, content: str, file_path: str) -> List[CodeChunk]:
        """Parse Python code using tree-sitter."""
        chunks = []

        def traverse_node(node, parent_name: str = None):
            # Handle decorated definitions (functions/classes with decorators)
            if node.type == 'decorated_definition':
                # Find the actual function or class definition inside
                for child in node.children:
                    if child.type in ['function_definition', 'class_definition']:
                        # Process the inner definition but use the decorated_definition node
                        # for extracting content (to include decorators)
                        if child.type == 'function_definition':
                            func_name = None
                            # Find function name
                            for subchild in child.children:
                                if subchild.type == 'identifier':
                                    func_name = self._get_node_text(subchild, content)
                                    break

                            # Determine chunk type (function or method)
                            chunk_type = 'method' if parent_name else 'function'

                            # Extract or generate description from the function definition
                            description = self._get_or_generate_description(
                                node=child,
                                content=content,
                                chunk_type=chunk_type,
                                name=func_name or 'unknown_function',
                                language='python'
                            )

                            # Use decorated_definition node for content to include decorators
                            chunk = CodeChunk(
                                content=self._get_node_text(node, content),
                                language='python',
                                chunk_type=chunk_type,
                                name=func_name or 'unknown_function',
                                file_path=file_path,
                                line_start=node.start_point[0] + 1,
                                line_end=node.end_point[0] + 1,
                                parent_name=parent_name,
                                description=description
                            )
                            chunks.append(chunk)
                        elif child.type == 'class_definition':
                            # Handle decorated class similarly
                            traverse_node(child, parent_name)
                return  # Don't traverse children again

            if node.type == 'function_definition':
                func_name = None

                # Find function name
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = self._get_node_text(child, content)
                        break

                # Determine chunk type (function or method)
                chunk_type = 'method' if parent_name else 'function'

                # Extract or generate description
                description = self._get_or_generate_description(
                    node=node,
                    content=content,
                    chunk_type=chunk_type,
                    name=func_name or 'unknown_function',
                    language='python'
                )

                chunk = CodeChunk(
                    content=self._get_node_text(node, content),
                    language='python',
                    chunk_type=chunk_type,
                    name=func_name or 'unknown_function',
                    file_path=file_path,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    parent_name=parent_name,
                    description=description
                )
                chunks.append(chunk)

            elif node.type == 'class_definition':
                class_name = None

                # Find class name
                for child in node.children:
                    if child.type == 'identifier':
                        class_name = self._get_node_text(child, content)
                        break

                # Extract or generate description for class
                description = self._get_or_generate_description(
                    node=node,
                    content=content,
                    chunk_type='class',
                    name=class_name or 'unknown_class',
                    language='python'
                )

                chunk = CodeChunk(
                    content=self._get_node_text(node, content),
                    language='python',
                    chunk_type='class',
                    name=class_name or 'unknown_class',
                    file_path=file_path,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    parent_name=parent_name,
                    description=description
                )
                chunks.append(chunk)

                # Parse methods inside class
                for child in node.children:
                    traverse_node(child, class_name)
                return  # Don't traverse children again

            # Traverse children
            for child in node.children:
                traverse_node(child, parent_name)

        traverse_node(root_node)
        return chunks
    
    def _parse_javascript(self, root_node, content: str, file_path: str, language: str) -> List[CodeChunk]:
        """Parse JavaScript/TypeScript code."""
        chunks = []
        
        def traverse_node(node, parent_name: str = None):
            if node.type in ['function_declaration', 'method_definition', 'arrow_function']:
                func_name = 'anonymous_function'
                
                # Find function name
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = self._get_node_text(child, content)
                        break
                
                chunk = CodeChunk(
                    content=self._get_node_text(node, content),
                    language=language,
                    chunk_type='function',
                    name=func_name,
                    file_path=file_path,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    parent_name=parent_name
                )
                chunks.append(chunk)
            
            elif node.type == 'class_declaration':
                class_name = 'unknown_class'
                
                for child in node.children:
                    if child.type == 'identifier':
                        class_name = self._get_node_text(child, content)
                        break
                
                chunk = CodeChunk(
                    content=self._get_node_text(node, content),
                    language=language,
                    chunk_type='class',
                    name=class_name,
                    file_path=file_path,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    parent_name=parent_name
                )
                chunks.append(chunk)
                
                # Parse methods inside class
                for child in node.children:
                    traverse_node(child, class_name)
                return
            
            # Traverse children
            for child in node.children:
                traverse_node(child, parent_name)
        
        traverse_node(root_node)
        return chunks
    
    def _parse_java(self, root_node, content: str, file_path: str) -> List[CodeChunk]:
        """Parse Java code."""
        # Simplified Java parsing - similar structure to Python
        return self._parse_python(root_node, content, file_path)
    
    def _parse_go(self, root_node, content: str, file_path: str) -> List[CodeChunk]:
        """Parse Go code."""
        # Simplified Go parsing
        return self._parse_python(root_node, content, file_path)
    
    def _parse_rust(self, root_node, content: str, file_path: str) -> List[CodeChunk]:
        """Parse Rust code."""
        # Simplified Rust parsing
        return self._parse_python(root_node, content, file_path)