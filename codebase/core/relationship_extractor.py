"""
Code relationship extractor using tree-sitter.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node

logger = logging.getLogger(__name__)

# Common Python built-in functions to filter out
PYTHON_BUILTINS = {
    'print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple',
    'range', 'enumerate', 'zip', 'map', 'filter', 'sum', 'min', 'max', 'abs',
    'open', 'input', 'type', 'isinstance', 'hasattr', 'getattr', 'setattr',
    'property', 'staticmethod', 'classmethod', 'super', 'Exception'
}


class CodeRelationshipExtractor:
    """Extract code relationships using tree-sitter."""

    def __init__(self):
        """Initialize the relationship extractor."""
        try:
            self.parser = Parser(Language(tspython.language()))
            logger.info("CodeRelationshipExtractor initialized for Python")
        except Exception as e:
            logger.error(f"Failed to initialize tree-sitter parser: {e}")
            raise

    def extract_relationships(
        self,
        code: str,
        file_path: str,
        chunk_id: str,
        chunk_name: str,
        chunk_type: str,
        codebase_id: int
    ) -> List[Dict[str, Any]]:
        """
        Extract relationships from code.

        Args:
            code: Source code text
            file_path: File path
            chunk_id: Source chunk ID
            chunk_name: Source chunk name
            chunk_type: Source chunk type ('function', 'class', 'method')
            codebase_id: Codebase ID

        Returns:
            List of relationship dictionaries
        """
        try:
            tree = self.parser.parse(bytes(code, "utf8"))
            root_node = tree.root_node

            relationships = []

            # Extract different types of relationships
            relationships.extend(
                self._extract_imports(root_node, chunk_id, chunk_name, chunk_type, file_path, codebase_id)
            )
            relationships.extend(
                self._extract_function_calls(root_node, chunk_id, chunk_name, chunk_type, file_path, codebase_id)
            )
            relationships.extend(
                self._extract_inheritance(root_node, chunk_id, chunk_name, chunk_type, file_path, codebase_id)
            )

            logger.debug(f"Extracted {len(relationships)} relationships from {chunk_name}")
            return relationships

        except Exception as e:
            logger.warning(f"Error extracting relationships from {file_path}: {e}")
            return []

    def _extract_imports(
        self,
        root_node: Node,
        source_chunk_id: str,
        source_name: str,
        source_type: str,
        source_file: str,
        codebase_id: int
    ) -> List[Dict[str, Any]]:
        """Extract import relationships."""
        relationships = []

        # from X import Y pattern
        import_from_query = """
        (import_from_statement
          module_name: (dotted_name) @module
          name: (dotted_name) @imported
        )
        """

        try:
            for node in self._find_nodes_by_type(root_node, "import_from_statement"):
                module_name = None
                imported_names = []

                # Get module name
                for child in node.children:
                    if child.type == "dotted_name" and "module_name" in str(node.child_by_field_name):
                        module_name = child.text.decode() if hasattr(child.text, 'decode') else str(child.text)

                # Get imported names
                for child in node.children:
                    if child.type == "dotted_name" and child != node.child_by_field_name("module_name"):
                        name = child.text.decode() if hasattr(child.text, 'decode') else str(child.text)
                        imported_names.append(name)
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            name = name_node.text.decode() if hasattr(name_node.text, 'decode') else str(name_node.text)
                            imported_names.append(name)

                # Create relationships
                for imported in imported_names:
                    relationships.append({
                        'codebase_id': codebase_id,
                        'source_chunk_id': source_chunk_id,
                        'source_name': source_name,
                        'source_type': source_type,
                        'source_file': source_file,
                        'target_chunk_id': None,  # Will be resolved later
                        'target_name': imported,
                        'target_type': 'unknown',
                        'target_file': module_name,
                        'relationship_type': 'imports',
                        'line_number': node.start_point[0] + 1,
                        'context': node.text.decode()[:200] if hasattr(node.text, 'decode') else str(node.text)[:200],
                        'metadata': {'module': module_name}
                    })
        except Exception as e:
            logger.debug(f"Error extracting imports: {e}")

        # import X pattern
        try:
            for node in self._find_nodes_by_type(root_node, "import_statement"):
                for child in node.children:
                    if child.type == "dotted_name":
                        module = child.text.decode() if hasattr(child.text, 'decode') else str(child.text)
                        relationships.append({
                            'codebase_id': codebase_id,
                            'source_chunk_id': source_chunk_id,
                            'source_name': source_name,
                            'source_type': source_type,
                            'source_file': source_file,
                            'target_chunk_id': None,
                            'target_name': module,
                            'target_type': 'module',
                            'target_file': None,
                            'relationship_type': 'imports',
                            'line_number': node.start_point[0] + 1,
                            'context': node.text.decode()[:200] if hasattr(node.text, 'decode') else str(node.text)[:200],
                            'metadata': {}
                        })
        except Exception as e:
            logger.debug(f"Error extracting import statements: {e}")

        return relationships

    def _extract_function_calls(
        self,
        root_node: Node,
        source_chunk_id: str,
        source_name: str,
        source_type: str,
        source_file: str,
        codebase_id: int
    ) -> List[Dict[str, Any]]:
        """Extract function call relationships."""
        relationships = []

        # Find all function calls
        try:
            for node in self._find_nodes_by_type(root_node, "call"):
                function_node = node.child_by_field_name("function")
                if not function_node:
                    continue

                # Simple function call: func_name()
                if function_node.type == "identifier":
                    func_name = function_node.text.decode() if hasattr(function_node.text, 'decode') else str(function_node.text)

                    # Filter out builtins
                    if func_name in PYTHON_BUILTINS:
                        continue

                    relationships.append({
                        'codebase_id': codebase_id,
                        'source_chunk_id': source_chunk_id,
                        'source_name': source_name,
                        'source_type': source_type,
                        'source_file': source_file,
                        'target_chunk_id': None,
                        'target_name': func_name,
                        'target_type': 'function',
                        'target_file': None,
                        'relationship_type': 'calls',
                        'line_number': node.start_point[0] + 1,
                        'context': node.text.decode()[:100] if hasattr(node.text, 'decode') else str(node.text)[:100],
                        'metadata': {}
                    })

                # Method call: obj.method()
                elif function_node.type == "attribute":
                    obj_node = function_node.child_by_field_name("object")
                    attr_node = function_node.child_by_field_name("attribute")

                    if obj_node and attr_node:
                        obj_name = obj_node.text.decode() if hasattr(obj_node.text, 'decode') else str(obj_node.text)
                        method_name = attr_node.text.decode() if hasattr(attr_node.text, 'decode') else str(attr_node.text)

                        # Skip self calls
                        if obj_name == 'self':
                            continue

                        relationships.append({
                            'codebase_id': codebase_id,
                            'source_chunk_id': source_chunk_id,
                            'source_name': source_name,
                            'source_type': source_type,
                            'source_file': source_file,
                            'target_chunk_id': None,
                            'target_name': method_name,
                            'target_type': 'method',
                            'target_file': None,
                            'relationship_type': 'calls',
                            'line_number': node.start_point[0] + 1,
                            'context': f"{obj_name}.{method_name}(...)",
                            'metadata': {'object': obj_name}
                        })
        except Exception as e:
            logger.debug(f"Error extracting function calls: {e}")

        return relationships

    def _extract_inheritance(
        self,
        root_node: Node,
        source_chunk_id: str,
        source_name: str,
        source_type: str,
        source_file: str,
        codebase_id: int
    ) -> List[Dict[str, Any]]:
        """Extract class inheritance relationships."""
        relationships = []

        # Only extract if this is a class
        if source_type != 'class':
            return relationships

        try:
            for node in self._find_nodes_by_type(root_node, "class_definition"):
                # Check if this is the class we're analyzing
                name_node = node.child_by_field_name("name")
                if not name_node:
                    continue

                class_name = name_node.text.decode() if hasattr(name_node.text, 'decode') else str(name_node.text)
                if class_name != source_name:
                    continue

                # Get superclasses
                superclasses_node = node.child_by_field_name("superclasses")
                if superclasses_node:
                    for child in superclasses_node.children:
                        if child.type == "identifier":
                            parent = child.text.decode() if hasattr(child.text, 'decode') else str(child.text)
                            relationships.append({
                                'codebase_id': codebase_id,
                                'source_chunk_id': source_chunk_id,
                                'source_name': source_name,
                                'source_type': source_type,
                                'source_file': source_file,
                                'target_chunk_id': None,
                                'target_name': parent,
                                'target_type': 'class',
                                'target_file': None,
                                'relationship_type': 'inherits',
                                'line_number': node.start_point[0] + 1,
                                'context': f"class {class_name}({parent}):",
                                'metadata': {}
                            })
        except Exception as e:
            logger.debug(f"Error extracting inheritance: {e}")

        return relationships

    def _find_nodes_by_type(self, root: Node, node_type: str) -> List[Node]:
        """Find all nodes of a specific type in the tree."""
        nodes = []

        def traverse(node: Node):
            if node.type == node_type:
                nodes.append(node)
            for child in node.children:
                traverse(child)

        traverse(root)
        return nodes
