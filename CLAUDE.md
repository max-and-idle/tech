# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

AI-powered codebase indexing and semantic search system using Google ADK, PostgreSQL, and tree-sitter. The system indexes codebases from multiple sources (GitHub, ZIP, local), parses them into structured chunks, generates embeddings, and stores them in a PostgreSQL vector database for semantic search.

## Development Commands

```bash
# Install dependencies and setup virtual environment
uv sync

# Run FastAPI server (development mode with auto-reload)
uv run uvicorn app:app --reload --host 127.0.0.1 --port 8000

# Run server (production mode)
uv run uvicorn app:app --host 127.0.0.1 --port 8000

# Access API documentation
# http://127.0.0.1:8000/docs (Swagger UI)
# http://127.0.0.1:8000/redoc (ReDoc)
```

## Environment Configuration

Required environment variables in `.env`:

```bash
# Database connection (PostgreSQL with pgvector)
DATABASE_URL=postgresql://user:password@host:port/database

# Embedding API key (Gemini or OpenAI)
GEMINI_API_KEY=your_api_key_here
# or
OPENAI_API_KEY=your_api_key_here

# Optional: Embedding model selection
EMBEDDING_MODEL=gemini  # or "openai"
```

## Architecture Overview

### Three-Tier System Architecture

1. **API Layer** (`app.py`, `routers/`)
   - FastAPI application with RESTful endpoints
   - Health checks and lifecycle management via lifespan context manager
   - Background database initialization at startup

2. **Core Processing Layer** (`codebase/core/`)
   - **Parser** (`parser.py`): Tree-sitter based multi-language code parsing
   - **Embeddings** (`embeddings.py`): Vector generation with caching
   - **Vector Store** (`pg_vector_store.py`): PostgreSQL + pgvector operations
   - **Preprocessor** (`preprocessor.py`): File scanning and chunking

3. **Source Handlers** (`codebase/sources/`)
   - GitHub repository downloader
   - ZIP file extractor
   - Local directory scanner

### Database Architecture

Uses PostgreSQL with pgvector extension and SQLAlchemy ORM:

- **Codebase** table: Metadata about indexed projects
- **CodeChunk** table: Code pieces with vector embeddings (dynamic dimensions)
- **IndexingHistory** table: Operation tracking and debugging

Database setup happens automatically at application startup in `app.py:initialize_database()`:
1. Test connection
2. Create pgvector extension
3. Create tables via SQLAlchemy
4. Create indexes (IVFFlat for vectors, B-tree for queries)

### Indexing Flow

```
Source (GitHub/ZIP/Local)
  → FilePreprocessor.scan_directory()
  → CodeParser.parse_file() [tree-sitter]
  → EmbeddingGenerator.generate_embedding() [cached]
  → VectorStore.insert_records() [batched]
```

**Key Implementation Details:**
- File scanning respects blacklist directories (node_modules, .git, etc.)
- Parsing uses tree-sitter for structured extraction (functions, classes, methods)
- Fallback to plain text chunking for unsupported languages
- Embeddings are cached by MD5 hash in `.embedding_cache/`
- Batch inserts (1000 records) for performance
- IVFFlat index created only when 1000+ vectors exist

### Search Flow

```
Query
  → EmbeddingGenerator.generate_embedding()
  → VectorStore.search() [cosine distance]
  → ContextManager.build_context_from_results()
```

**Search Capabilities:**
- Semantic search via vector similarity (cosine distance)
- Filter by: chunk_type, language, parent_name
- Configurable top_k results
- Context building for LLM consumption

## Multi-Language Support

Supported via tree-sitter parsers:
- **Python**: Functions, classes, methods, docstrings
- **JavaScript/TypeScript**: Functions, classes, arrow functions
- **Java, Go, Rust**: Basic function/class extraction

Language detection based on file extensions in `codebase/config.py:LANGUAGE_MAPPING`.

Unsupported files fall back to 50-line text chunks.

## Vector Store Implementation

PostgreSQL-specific optimizations in `codebase/core/pg_vector_store.py`:
- Dynamic embedding dimensions (auto-detected from first embedding)
- IVFFlat indexing with adaptive list count: `max(10, min(sqrt(row_count), 1000))`
- B-tree indexes on: language, chunk_type, name, parent_name
- Batch insert with fallback to individual inserts on error
- Cascading deletes from Codebase to CodeChunk

## Important Patterns

### Database Connection Management
- Two connection patterns coexist:
  1. `database.py`: Simple SQLAlchemy engine using DATABASE_URL
  2. `codebase/supabase_database.py`: Supabase-specific manager (optional)
- Application uses `database.py` by default
- Startup initialization in `app.py:initialize_database()`

### Embedding Cache
- Embeddings cached as JSON files in `.embedding_cache/`
- Hash-based lookup: `{md5(text)}.json`
- Includes text, embedding vector, metadata, hash
- Shared across indexing sessions for performance

### Error Handling
- Graceful degradation: files/chunks that fail parsing continue processing
- Batch insert with single-record fallback on error
- Validation endpoints for pre-indexing source checks

### Code Chunk Types
- `function`: Top-level functions
- `class`: Class definitions
- `method`: Class methods (with parent_name reference)
- `text`: Fallback for unsupported content

## Testing the System

```bash
# Index a local directory
curl -X POST "http://127.0.0.1:8000/api/codebase/index/local" \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/code", "name": "my_project"}'

# Search the codebase
curl -X POST "http://127.0.0.1:8000/api/codebase/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication function", "codebase_name": "my_project", "top_k": 5}'

# List all indexed codebases
curl http://127.0.0.1:8000/api/codebase/list

# Get health status (includes database connection info)
curl http://127.0.0.1:8000/health
```

## Development Notes

- FastAPI auto-generates OpenAPI docs at `/docs`
- Logging configured at INFO level in `app.py` and individual modules
- Request/response logging via middleware
- Temporary files stored in `temp_uploads/` (cleaned after processing)
- Vector database in PostgreSQL (not local files)
- Tree-sitter parsers initialized lazily in CodeParser
