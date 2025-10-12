"""
SQLAlchemy models for PostgreSQL database.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Codebase(Base):
    """Codebase model for storing metadata about indexed codebases."""
    
    __tablename__ = "codebases"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    source_type = Column(String(50))  # 'github', 'zip', 'local'
    source_url = Column(Text)
    source_path = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    meta_info = Column(JSON)
    
    # Relationships
    chunks = relationship("CodeChunk", back_populates="codebase", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Codebase(name='{self.name}', source_type='{self.source_type}')>"


class CodeChunk(Base):
    """Code chunk model for storing code pieces with embeddings."""
    
    __tablename__ = "code_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codebase_id = Column(Integer, ForeignKey("codebases.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Text content
    text = Column(Text, nullable=False)
    
    # Vector embedding (dimension will be determined by actual embedding data)
    embedding = Column(Vector())
    
    # Code metadata
    chunk_type = Column(String(50), index=True)  # 'function', 'class', 'method', etc.
    name = Column(String(255), index=True)
    file_path = Column(Text, nullable=False)
    language = Column(String(50), index=True)
    line_start = Column(Integer)
    line_end = Column(Integer)
    parent_name = Column(String(255))
    description = Column(Text)
    description_embedding = Column(Vector())
    
    # Additional metadata as JSON
    meta_info = Column(JSON)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    codebase = relationship("Codebase", back_populates="chunks")
    
    def __repr__(self):
        return f"<CodeChunk(name='{self.name}', type='{self.chunk_type}', language='{self.language}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'id': str(self.id),
            'text': self.text,
            'chunk_type': self.chunk_type,
            'name': self.name,
            'file_path': self.file_path,
            'language': self.language,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'parent_name': self.parent_name,
            'description': self.description,
            'metadata': self.meta_info or {},
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class IndexingHistory(Base):
    """Track indexing operations for debugging and monitoring."""
    
    __tablename__ = "indexing_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    codebase_id = Column(Integer, ForeignKey("codebases.id", ondelete="CASCADE"))
    operation = Column(String(50))  # 'create', 'update', 'delete'
    status = Column(String(50))     # 'success', 'error', 'in_progress'
    details = Column(JSON)
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    codebase = relationship("Codebase")
    
    def __repr__(self):
        return f"<IndexingHistory(operation='{self.operation}', status='{self.status}')>"