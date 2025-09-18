"""
Tree-sitter based code parser for extracting code structures.
"""

from typing import List, Dict, Optional, Tuple, Any
import tree_sitter
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


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
    docstring: Optional[str] = None


class CodeParser:
    """Tree-sitter based code parser for multiple languages."""
    
    def __init__(self):
        """Initialize the code parser with supported languages."""
        self.parsers = {}
        self.languages = {}
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
        """Extract text from a tree-sitter node."""
        return source_code[node.start_byte:node.end_byte]
    
    def _parse_python(self, root_node, content: str, file_path: str) -> List[CodeChunk]:
        """Parse Python code using tree-sitter."""
        chunks = []
        
        def traverse_node(node, parent_name: str = None):
            if node.type == 'function_definition':
                func_name = None
                docstring = None
                
                # Find function name
                for child in node.children:
                    if child.type == 'identifier':
                        func_name = self._get_node_text(child, content)
                        break
                
                # Find docstring
                if len(node.children) > 0:
                    body = node.children[-1]  # function body
                    if body.type == 'block':
                        for stmt in body.children:
                            if stmt.type == 'expression_statement':
                                expr = stmt.children[0] if stmt.children else None
                                if expr and expr.type == 'string':
                                    docstring = self._get_node_text(expr, content).strip('"\'')
                                    break
                
                chunk = CodeChunk(
                    content=self._get_node_text(node, content),
                    language='python',
                    chunk_type='function',
                    name=func_name or 'unknown_function',
                    file_path=file_path,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    parent_name=parent_name,
                    docstring=docstring
                )
                chunks.append(chunk)
            
            elif node.type == 'class_definition':
                class_name = None
                
                # Find class name
                for child in node.children:
                    if child.type == 'identifier':
                        class_name = self._get_node_text(child, content)
                        break
                
                chunk = CodeChunk(
                    content=self._get_node_text(node, content),
                    language='python',
                    chunk_type='class',
                    name=class_name or 'unknown_class',
                    file_path=file_path,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    parent_name=parent_name
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