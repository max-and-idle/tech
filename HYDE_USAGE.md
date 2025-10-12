# HyDE (Hypothetical Document Embeddings) Usage Guide

HyDE has been successfully integrated into the codebase search system to improve semantic search quality by bridging the gap between natural language queries and code embeddings.

## Overview

**Problem**: Natural language queries like "user authentication function" are semantically distant from actual code in the embedding space, leading to poor search results.

**Solution**: HyDE generates hypothetical code from your natural language query, which is then used for embedding search. Since code embeddings are closer to code than natural language embeddings, this significantly improves search accuracy.

## How It Works

### Two-Stage HyDE Process

1. **Stage 1: Initial Code Generation**
   - User query: "Find the function that handles user authentication"
   - LLM generates hypothetical code:
     ```python
     def authenticate_user(username: str, password: str) -> bool:
         # Validate credentials against database
         user = database.get_user(username)
         if user and verify_password(password, user.password_hash):
             return True
         return False
     ```
   - Initial search with this code retrieves top 5 results for context

2. **Stage 2: Context-Enhanced Generation**
   - Using the context from Stage 1, LLM generates improved code that matches the actual codebase style
   - Final search with enhanced code returns the most accurate results

## Environment Setup

Add these variables to your `.env` file:

```bash
# HyDE Configuration
HYDE_MODEL=gemini          # or "openai"
HYDE_ENABLED=true          # Enable/disable HyDE
GEMINI_API_KEY=your_key    # For Gemini (recommended)
# or
OPENAI_API_KEY=your_key    # For OpenAI (gpt-4o-mini)
```

## API Usage

### Basic Search (Without HyDE)

```bash
curl -X POST "http://127.0.0.1:8000/api/codebase/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication function",
    "codebase_name": "my_project",
    "top_k": 5,
    "search_type": "semantic"
  }'
```

### HyDE-Enhanced Search

```bash
curl -X POST "http://127.0.0.1:8000/api/codebase/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Find the function that validates user credentials and creates a session",
    "codebase_name": "my_project",
    "top_k": 5,
    "search_type": "semantic",
    "use_hyde": true
  }'
```

### HyDE with Reranking (Best Quality)

```bash
curl -X POST "http://127.0.0.1:8000/api/codebase/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "user authentication logic",
    "codebase_name": "my_project",
    "top_k": 5,
    "use_hyde": true,
    "use_reranking": true
  }'
```

### HyDE Search Type (Shorthand)

```bash
curl -X POST "http://127.0.0.1:8000/api/codebase/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection pool",
    "codebase_name": "my_project",
    "top_k": 5,
    "search_type": "hyde"
  }'
```

## Python Client Usage

```python
import requests

def search_with_hyde(query: str, codebase_name: str, use_reranking: bool = False):
    """Search codebase with HyDE enhancement."""
    response = requests.post(
        "http://127.0.0.1:8000/api/codebase/search",
        json={
            "query": query,
            "codebase_name": codebase_name,
            "top_k": 10,
            "use_hyde": True,
            "use_reranking": use_reranking,
            "include_context": True
        }
    )
    return response.json()

# Example usage
results = search_with_hyde(
    query="function that sends email notifications",
    codebase_name="backend_api",
    use_reranking=True
)

print(f"Found {results['total_results']} results")
for result in results['results']:
    print(f"- {result['name']} in {result['file_path']} (score: {result['score']:.3f})")
```

## Search Options Comparison

| Feature | Basic Semantic | HyDE | HyDE + Reranking |
|---------|---------------|------|------------------|
| Speed | ⚡⚡⚡ Fast | ⚡⚡ Moderate | ⚡ Slower |
| Accuracy | 🎯 Good | 🎯🎯 Better | 🎯🎯🎯 Best |
| Natural Language Queries | ❌ Poor | ✅ Good | ✅ Excellent |
| Code-like Queries | ✅ Good | ✅ Good | ✅ Excellent |
| LLM API Calls | 0 | 2 | 2 |

## When to Use HyDE

### ✅ Best For:
- Natural language queries ("Find the code that handles...")
- Conceptual searches ("error handling logic")
- Cross-language searches (query in English, code in any language)
- Fuzzy searches when you don't know exact function names

### ❌ Not Needed For:
- Exact function/class name searches
- Keyword searches with specific identifiers
- When you need maximum speed
- Very large result sets (top_k > 20)

## Reranking Options

Reranking applies code-specific heuristics to improve result quality:

### Features:
1. **Name Matching**: Boosts results where function/class names match query keywords
2. **Docstring Relevance**: Considers docstring content
3. **Chunk Type Preference**: Prioritizes functions/classes over text chunks
4. **File Path Relevance**: Considers file/directory names
5. **Confidence Filtering**: Removes low-confidence results (score < 0.3)
6. **Diversity**: Limits results per file to avoid clustering

### Weights (Configurable):
```python
weights = {
    'vector': 0.4,        # Vector similarity
    'name_match': 0.25,   # Function/class name matching
    'docstring': 0.15,    # Docstring relevance
    'chunk_type': 0.1,    # Chunk type preference
    'file_path': 0.1      # File path relevance
}
```

## Response Metadata

HyDE-enhanced searches include additional metadata:

```json
{
  "query": "user authentication",
  "use_hyde": true,
  "use_reranking": true,
  "results": [
    {
      "name": "authenticate_user",
      "score": 0.92,
      "metadata": {
        "search_method": "hyde",
        "hyde_v1_length": 245,
        "hyde_v2_length": 318,
        "rerank_score": 0.92,
        "vector_score": 0.85,
        "name_match_score": 0.95,
        "reranked": true
      }
    }
  ]
}
```

## Performance Considerations

### Latency:
- **Basic Search**: ~100-200ms
- **HyDE Search**: ~1-2 seconds (2 LLM calls + 2 vector searches)
- **HyDE + Reranking**: ~1.5-2.5 seconds

### Cost (Gemini):
- HyDE Stage 1: ~0.5-1k tokens (input) + 100-300 tokens (output)
- HyDE Stage 2: ~3-4k tokens (input) + 200-500 tokens (output)
- Total: ~0.001-0.003 USD per search (with Gemini Flash)

### Optimization Tips:
1. Cache frequent queries at application level
2. Use HyDE only for natural language queries
3. Set reasonable `top_k` limits (5-10 recommended)
4. Consider async processing for batch searches

## Troubleshooting

### HyDE Not Working

1. Check environment variables:
   ```bash
   echo $HYDE_ENABLED
   echo $GEMINI_API_KEY  # or OPENAI_API_KEY
   ```

2. Check logs for HyDE initialization:
   ```
   INFO - HyDE generator initialized with model: gemini, enabled: True
   ```

3. Verify in search response:
   ```json
   {"use_hyde": true}  // Should be true if enabled
   ```

### Poor Results with HyDE

1. Try adjusting search type:
   - Use `"search_type": "hybrid"` for better keyword matching
   - Combine with `"use_reranking": true`

2. Check generated HyDE queries in logs:
   ```
   INFO - HyDE query v1 generated (length: 245)
   INFO - HyDE query v2 generated (length: 318)
   ```

3. Ensure your query is descriptive:
   - ❌ "auth"
   - ✅ "function that authenticates users with email and password"

## Examples

### Example 1: Find Error Handling
```bash
curl -X POST "http://127.0.0.1:8000/api/codebase/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me how errors are caught and logged in the API",
    "codebase_name": "api_server",
    "use_hyde": true,
    "use_reranking": true,
    "top_k": 5
  }'
```

### Example 2: Find Database Operations
```bash
curl -X POST "http://127.0.0.1:8000/api/codebase/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "code that queries the user table and returns user objects",
    "codebase_name": "backend",
    "use_hyde": true,
    "filters": {"language": "python"}
  }'
```

### Example 3: Find Configuration
```bash
curl -X POST "http://127.0.0.1:8000/api/codebase/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "where is the database connection configured",
    "codebase_name": "myapp",
    "use_hyde": true,
    "use_reranking": true
  }'
```

## Architecture

```
User Query (Natural Language)
    ↓
[HyDE Generator - Stage 1]
    ↓
Hypothetical Code v1
    ↓
[Vector Search - Initial]
    ↓
Top 5 Context Results
    ↓
[HyDE Generator - Stage 2]
    ↓
Enhanced Hypothetical Code v2
    ↓
[Vector Search - Final]
    ↓
Top K Results
    ↓
[Optional: Reranking]
    ↓
[Optional: Filtering & Diversity]
    ↓
Final Results
```

## Implementation Details

- **HyDE Model**: Gemini 1.5 Flash (fast, cost-effective) or GPT-4o-mini
- **Embedding Model**: Gemini text-embedding-004
- **Task Types**:
  - User queries: `retrieval_query`
  - HyDE-generated code: `retrieval_document`
  - Indexed code: `retrieval_document`
- **Reranking**: Multi-signal approach with configurable weights
- **Caching**: Embeddings cached by MD5 hash

## Future Enhancements

Potential improvements for future versions:

1. **Query Classification**: Auto-detect when to use HyDE vs. regular search
2. **Streaming HyDE**: Stream LLM responses for faster perceived latency
3. **Cross-Encoder Reranking**: Use dedicated reranking models
4. **Query Expansion**: Generate multiple HyDE variations and combine results
5. **Feedback Loop**: Learn from user interactions to improve HyDE prompts

## Support

For issues or questions:
1. Check application logs for detailed error messages
2. Verify API endpoint: `http://127.0.0.1:8000/docs`
3. Test with simple queries first before complex ones
4. Monitor LLM API usage and quotas
