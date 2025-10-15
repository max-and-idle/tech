"""
Code relationship storage and query operations.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session
from database import SessionLocal
from codebase.models import CodeRelationship, CodeChunk, Codebase

logger = logging.getLogger(__name__)


class RelationshipStore:
    """Manages code relationship storage and queries."""

    def __init__(self):
        """Initialize relationship store."""
        logger.info("RelationshipStore initialized")

    def insert_relationships(
        self,
        codebase_name: str,
        relationships: List[Dict[str, Any]]
    ) -> bool:
        """
        Insert relationships into the database.

        Args:
            codebase_name: Name of the codebase
            relationships: List of relationship dictionaries

        Returns:
            True if successful
        """
        if not relationships:
            logger.info("No relationships to insert")
            return True

        db = SessionLocal()
        try:
            # Get codebase
            codebase = db.query(Codebase).filter(Codebase.name == codebase_name).first()
            if not codebase:
                logger.error(f"Codebase '{codebase_name}' not found")
                return False

            # Insert relationships in batch
            inserted = 0
            for rel_data in relationships:
                try:
                    # Ensure codebase_id is set
                    rel_data['codebase_id'] = codebase.id

                    relationship = CodeRelationship(**rel_data)
                    db.add(relationship)
                    inserted += 1

                    # Commit in batches
                    if inserted % 1000 == 0:
                        db.commit()
                        logger.info(f"Inserted {inserted} relationships...")

                except Exception as e:
                    logger.warning(f"Error inserting relationship: {e}")
                    continue

            # Final commit
            db.commit()
            logger.info(f"Successfully inserted {inserted} relationships for '{codebase_name}'")
            return True

        except Exception as e:
            logger.error(f"Error inserting relationships: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def find_callers(
        self,
        target_name: str,
        codebase_name: str,
        relationship_type: str = 'calls'
    ) -> List[Dict[str, Any]]:
        """
        Find all code that calls/uses a specific function or method.

        Args:
            target_name: Name of the target function/method
            codebase_name: Name of the codebase
            relationship_type: Type of relationship ('calls', 'imports', etc.)

        Returns:
            List of caller information
        """
        db = SessionLocal()
        try:
            codebase = db.query(Codebase).filter(Codebase.name == codebase_name).first()
            if not codebase:
                return []

            relationships = db.query(CodeRelationship).filter(
                and_(
                    CodeRelationship.codebase_id == codebase.id,
                    CodeRelationship.target_name == target_name,
                    CodeRelationship.relationship_type == relationship_type
                )
            ).all()

            results = []
            for rel in relationships:
                results.append({
                    'source_name': rel.source_name,
                    'source_type': rel.source_type,
                    'source_file': rel.source_file,
                    'line_number': rel.line_number,
                    'context': rel.context,
                    'relationship_type': rel.relationship_type
                })

            logger.info(f"Found {len(results)} callers for '{target_name}'")
            return results

        except Exception as e:
            logger.error(f"Error finding callers: {e}")
            return []
        finally:
            db.close()

    def find_callers_by_chunk_id(
        self,
        chunk_id: str,
        codebase_name: str
    ) -> List[Dict[str, Any]]:
        """
        Find all code that references a specific chunk.

        Args:
            chunk_id: Target chunk ID
            codebase_name: Name of the codebase

        Returns:
            List of caller information
        """
        db = SessionLocal()
        try:
            codebase = db.query(Codebase).filter(Codebase.name == codebase_name).first()
            if not codebase:
                return []

            relationships = db.query(CodeRelationship).filter(
                and_(
                    CodeRelationship.codebase_id == codebase.id,
                    CodeRelationship.target_chunk_id == chunk_id
                )
            ).all()

            results = []
            for rel in relationships:
                results.append({
                    'chunk_id': str(rel.source_chunk_id),
                    'source_name': rel.source_name,
                    'source_type': rel.source_type,
                    'source_file': rel.source_file,
                    'line_number': rel.line_number,
                    'context': rel.context,
                    'relationship_type': rel.relationship_type
                })

            return results

        except Exception as e:
            logger.error(f"Error finding callers by chunk ID: {e}")
            return []
        finally:
            db.close()

    def find_dependencies(
        self,
        source_name: str,
        codebase_name: str
    ) -> Dict[str, Any]:
        """
        Find dependencies for a specific code component.

        Args:
            source_name: Name of the source component
            codebase_name: Name of the codebase

        Returns:
            Dictionary with dependencies grouped by type
        """
        db = SessionLocal()
        try:
            codebase = db.query(Codebase).filter(Codebase.name == codebase_name).first()
            if not codebase:
                return {}

            relationships = db.query(CodeRelationship).filter(
                and_(
                    CodeRelationship.codebase_id == codebase.id,
                    CodeRelationship.source_name == source_name
                )
            ).all()

            # Group by relationship type
            dependencies = {
                'imports': [],
                'calls': [],
                'inherits': [],
                'uses': []
            }

            for rel in relationships:
                dep_info = {
                    'target_name': rel.target_name,
                    'target_type': rel.target_type,
                    'target_file': rel.target_file,
                    'line_number': rel.line_number,
                    'context': rel.context
                }

                if rel.relationship_type in dependencies:
                    dependencies[rel.relationship_type].append(dep_info)

            logger.info(f"Found dependencies for '{source_name}': {sum(len(v) for v in dependencies.values())} total")
            return dependencies

        except Exception as e:
            logger.error(f"Error finding dependencies: {e}")
            return {}
        finally:
            db.close()

    def find_impact_scope(
        self,
        chunk_id: str,
        codebase_name: str,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Find the impact scope of modifying a specific code chunk.

        Args:
            chunk_id: Chunk ID to analyze
            codebase_name: Name of the codebase
            max_depth: Maximum depth for transitive dependencies

        Returns:
            Dictionary with impact analysis
        """
        db = SessionLocal()
        try:
            # Get the chunk info
            chunk = db.query(CodeChunk).filter(CodeChunk.id == chunk_id).first()
            if not chunk:
                return {}

            # Find direct callers (depth 1)
            direct_impact = self.find_callers_by_chunk_id(chunk_id, codebase_name)

            # Find indirect callers (depth 2) if needed
            indirect_impact = []
            if max_depth > 1:
                for caller in direct_impact:
                    caller_chunk_id = caller['chunk_id']
                    indirect = self.find_callers_by_chunk_id(caller_chunk_id, codebase_name)
                    indirect_impact.extend(indirect)

            # Calculate affected files
            affected_files = set()
            for impact in direct_impact + indirect_impact:
                affected_files.add(impact['source_file'])

            return {
                'target': {
                    'chunk_id': str(chunk_id),
                    'name': chunk.name,
                    'type': chunk.chunk_type,
                    'file': chunk.file_path
                },
                'direct_impact': direct_impact,
                'indirect_impact': indirect_impact,
                'affected_files': list(affected_files),
                'total_affected_components': len(direct_impact) + len(indirect_impact),
                'total_affected_files': len(affected_files)
            }

        except Exception as e:
            logger.error(f"Error finding impact scope: {e}")
            return {}
        finally:
            db.close()

    def get_relationship_stats(
        self,
        codebase_name: str
    ) -> Dict[str, Any]:
        """
        Get statistics about relationships in a codebase.

        Args:
            codebase_name: Name of the codebase

        Returns:
            Statistics dictionary
        """
        db = SessionLocal()
        try:
            codebase = db.query(Codebase).filter(Codebase.name == codebase_name).first()
            if not codebase:
                return {}

            # Count by relationship type
            type_counts = db.query(
                CodeRelationship.relationship_type,
                func.count(CodeRelationship.id)
            ).filter(
                CodeRelationship.codebase_id == codebase.id
            ).group_by(
                CodeRelationship.relationship_type
            ).all()

            stats = {
                'total_relationships': 0,
                'by_type': {}
            }

            for rel_type, count in type_counts:
                stats['by_type'][rel_type] = count
                stats['total_relationships'] += count

            return stats

        except Exception as e:
            logger.error(f"Error getting relationship stats: {e}")
            return {}
        finally:
            db.close()

    def delete_relationships(
        self,
        codebase_name: str
    ) -> bool:
        """
        Delete all relationships for a codebase.

        Args:
            codebase_name: Name of the codebase

        Returns:
            True if successful
        """
        db = SessionLocal()
        try:
            codebase = db.query(Codebase).filter(Codebase.name == codebase_name).first()
            if not codebase:
                return False

            deleted = db.query(CodeRelationship).filter(
                CodeRelationship.codebase_id == codebase.id
            ).delete()

            db.commit()
            logger.info(f"Deleted {deleted} relationships for '{codebase_name}'")
            return True

        except Exception as e:
            logger.error(f"Error deleting relationships: {e}")
            db.rollback()
            return False
        finally:
            db.close()
