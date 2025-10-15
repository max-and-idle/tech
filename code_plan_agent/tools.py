"""
Tools for the code plan agent.
"""

import logging
from typing import Dict, Any, List, Optional
from codebase import CodebaseIndexer
from codebase.core import RelationshipStore

logger = logging.getLogger(__name__)

# Global indexer instance
_indexer = None
_relationship_store = None


def get_indexer() -> CodebaseIndexer:
    """Get or create global indexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = CodebaseIndexer()
    return _indexer


def get_relationship_store() -> RelationshipStore:
    """Get or create global relationship store instance."""
    global _relationship_store
    if _relationship_store is None:
        _relationship_store = RelationshipStore()
    return _relationship_store


def search_related_code(
    requirement: str,
    codebase_name: str,
    top_k: int = 10
) -> dict:
    """
    Search for code related to the requirement using semantic search.

    Args:
        requirement: Natural language description of what to search for
        codebase_name: Name of the codebase to search in
        top_k: Number of results to return

    Returns:
        Search results with code chunks
    """
    try:
        logger.info(f"Searching for code related to: {requirement}")

        indexer = get_indexer()
        results = indexer.search(
            query=requirement,
            codebase_name=codebase_name,
            top_k=top_k,
            search_type="hybrid",
            use_hyde=True,
            use_reranking=True,
            include_context=False
        )

        if 'error' in results:
            logger.error(f"Search error: {results['error']}")
            return {
                "status": "error",
                "error": results['error'],
                "results": []
            }

        logger.info(f"Found {len(results.get('results', []))} related code chunks")

        return {
            "status": "success",
            "results": results.get('results', []),
            "total": results.get('total_results', 0)
        }

    except Exception as e:
        logger.error(f"Error searching related code: {e}")
        return {
            "status": "error",
            "error": str(e),
            "results": []
        }


def find_similar_patterns(
    code_pattern: str,
    codebase_name: str,
    top_k: int = 5
) -> dict:
    """
    Find similar implementation patterns in the codebase.

    Args:
        code_pattern: Description of the pattern to find
        codebase_name: Name of the codebase
        top_k: Number of results

    Returns:
        Similar code patterns
    """
    try:
        logger.info(f"Finding similar patterns for: {code_pattern}")

        indexer = get_indexer()
        results = indexer.search(
            query=f"implementation example: {code_pattern}",
            codebase_name=codebase_name,
            top_k=top_k,
            search_type="semantic",
            use_hyde=True,
            include_context=False
        )

        if 'error' in results:
            return {
                "status": "error",
                "error": results['error'],
                "patterns": []
            }

        return {
            "status": "success",
            "patterns": results.get('results', []),
            "total": len(results.get('results', []))
        }

    except Exception as e:
        logger.error(f"Error finding similar patterns: {e}")
        return {
            "status": "error",
            "error": str(e),
            "patterns": []
        }


def analyze_dependencies(
    target_components: List[str],
    codebase_name: str
) -> dict:
    """
    Analyze dependencies of target components using relationship graph.

    Args:
        target_components: List of component names to analyze
        codebase_name: Name of the codebase

    Returns:
        Dependency information
    """
    try:
        logger.info(f"Analyzing dependencies for: {target_components}")

        relationship_store = get_relationship_store()
        all_dependencies = {}

        for component_name in target_components:
            deps = relationship_store.find_dependencies(component_name, codebase_name)
            all_dependencies[component_name] = deps

        # Summarize dependencies
        total_imports = sum(len(d.get('imports', [])) for d in all_dependencies.values())
        total_calls = sum(len(d.get('calls', [])) for d in all_dependencies.values())
        total_inherits = sum(len(d.get('inherits', [])) for d in all_dependencies.values())

        logger.info(f"Found {total_imports} imports, {total_calls} calls, {total_inherits} inheritance")

        return {
            "status": "success",
            "dependencies": all_dependencies,
            "summary": {
                "total_imports": total_imports,
                "total_calls": total_calls,
                "total_inherits": total_inherits,
                "total_components": len(target_components)
            }
        }

    except Exception as e:
        logger.error(f"Error analyzing dependencies: {e}")
        return {
            "status": "error",
            "error": str(e),
            "dependencies": {}
        }


def analyze_impact(
    target_components: List[Dict[str, Any]],
    codebase_name: str
) -> dict:
    """
    Analyze the impact of modifying target components.

    Args:
        target_components: List of components with their chunk_ids
        codebase_name: Name of the codebase

    Returns:
        Impact analysis results
    """
    try:
        logger.info(f"Analyzing impact for {len(target_components)} components")

        relationship_store = get_relationship_store()
        all_impacts = []
        all_affected_files = set()
        total_affected_components = 0

        for component in target_components:
            chunk_id = component.get('id')
            if not chunk_id:
                continue

            impact = relationship_store.find_impact_scope(
                chunk_id=chunk_id,
                codebase_name=codebase_name,
                max_depth=2
            )

            if impact:
                all_impacts.append(impact)
                all_affected_files.update(impact.get('affected_files', []))
                total_affected_components += impact.get('total_affected_components', 0)

        # Calculate risk level
        if total_affected_components > 20:
            risk_level = "high"
        elif total_affected_components > 10:
            risk_level = "medium"
        else:
            risk_level = "low"

        logger.info(
            f"Impact analysis: {total_affected_components} components affected, "
            f"{len(all_affected_files)} files, risk: {risk_level}"
        )

        return {
            "status": "success",
            "impacts": all_impacts,
            "summary": {
                "total_affected_components": total_affected_components,
                "total_affected_files": len(all_affected_files),
                "affected_files": list(all_affected_files),
                "risk_level": risk_level,
                "breaking_changes": risk_level in ["high", "medium"]
            }
        }

    except Exception as e:
        logger.error(f"Error analyzing impact: {e}")
        return {
            "status": "error",
            "error": str(e),
            "impacts": []
        }


def get_component_callers(
    component_name: str,
    codebase_name: str
) -> dict:
    """
    Find all components that call/use the specified component.

    Args:
        component_name: Name of the component
        codebase_name: Name of the codebase

    Returns:
        List of callers
    """
    try:
        relationship_store = get_relationship_store()
        callers = relationship_store.find_callers(component_name, codebase_name)

        return {
            "status": "success",
            "component_name": component_name,
            "callers": callers,
            "total_callers": len(callers)
        }

    except Exception as e:
        logger.error(f"Error getting callers: {e}")
        return {
            "status": "error",
            "error": str(e),
            "callers": []
        }
