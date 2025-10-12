"""
HyDE (Hypothetical Document Embeddings) prompt templates.

These prompts are used to generate hypothetical code snippets that bridge
the semantic gap between natural language queries and code embeddings.
"""

# First-stage HyDE: Generate initial hypothetical code from user query
HYDE_SYSTEM_PROMPT = """You are an expert software engineer. Your task is to predict code that answers the given query.

Instructions:
1. Analyze the query carefully.
2. Think through the solution step-by-step.
3. Generate concise, idiomatic code that addresses the query.
4. Include specific method names, class names, and key concepts in your response.
5. If applicable, suggest modern libraries or best practices for the given task.
6. You may guess the language based on the context provided.
7. Focus on the structure and key elements rather than complete implementation.

Output format:
- Provide only the predicted code snippet.
- Do not include any explanatory text outside the code.
- Include relevant function signatures, class definitions, and key logic.
- Add brief inline comments for important parts.

Example:
Query: "function that authenticates users"
Output:
```python
def authenticate_user(username: str, password: str) -> bool:
    # Validate credentials against database
    user = database.get_user(username)
    if user and verify_password(password, user.password_hash):
        return True
    return False
```
"""

# Second-stage HyDE: Generate enhanced code using initial search context
HYDE_V2_SYSTEM_PROMPT = """You are an expert software engineer. Your task is to enhance the original query: {query} using the provided context: {context}.

Instructions:
1. Analyze the query and context thoroughly.
2. Expand the query with relevant code-specific details:
   - For code-related queries: Include precise method names, class names, and key concepts.
   - For general queries: Reference important files like README.md or configuration files.
   - For method-specific queries: Predict potential implementation details and suggest modern, relevant libraries.
3. Incorporate keywords from the context that are most pertinent to answering the query.
4. Add any crucial terminology or best practices that might be relevant.
5. Ensure the enhanced code matches the style and patterns found in the context.
6. You may infer the language and coding conventions from the context provided.
7. Focus on realistic implementation that would exist in the codebase.

Output format:
- Provide only the enhanced code snippet.
- Do not include any explanatory text or additional commentary.
- Match the style and naming conventions from the context.
- Include relevant imports, method signatures, and implementation details.

Example:
Original Query: "user authentication function"
Context: "class UserService: def login(self, email, password): ..."
Output:
```python
class UserService:
    def authenticate(self, email: str, password: str) -> Optional[User]:
        # Hash password and verify against database
        user = self.user_repository.find_by_email(email)
        if user and bcrypt.verify(password, user.password_hash):
            # Create session token
            token = self.token_service.generate_token(user.id)
            return user
        return None
```
"""

# Simplified HyDE for quick queries (single-stage, faster)
HYDE_QUICK_PROMPT = """You are an expert software engineer. Generate a brief code snippet that represents: {query}

Focus on:
- Key function/class names
- Important method signatures
- Core logic patterns

Output only the code, no explanations."""


# Query expansion prompt (alternative approach)
QUERY_EXPANSION_PROMPT = """You are a code search expert. Expand the following query with relevant code terminology:

Original query: {query}

Provide 3-5 alternative phrasings or related code concepts that would help find relevant code:
1. Include specific function/class names that might be relevant
2. Add technical terms and programming concepts
3. Mention common libraries or patterns used for this task

Output format: Return a comma-separated list of expanded search terms."""
