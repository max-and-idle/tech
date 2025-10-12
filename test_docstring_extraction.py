"""
Test script for docstring extraction and AI generation.
"""

from codebase.core.parser import CodeParser

# Test code samples
TEST_CODE_WITH_DOCSTRING = '''
def authenticate(user, password):
    """Authenticate user credentials."""
    if check_db(user):
        return True
    return False

class AuthHandler:
    """Handle authentication operations."""

    def login(self, user):
        """Log in a user."""
        return authenticate(user.name, user.password)
'''

TEST_CODE_WITHOUT_DOCSTRING = '''
def calculate_total(items):
    total = 0
    for item in items:
        total += item.price
    return total

class ShoppingCart:
    def add_item(self, item):
        self.items.append(item)
'''

TEST_CODE_TRIPLE_QUOTES = '''
def example1():
    """This is a triple-quoted docstring."""
    pass

def example2():
    \'\'\'Single triple quotes.\'\'\'
    pass

def example3():
    "Double quotes"
    pass

def example4():
    'Single quotes'
    pass
'''

TEST_CODE_WITH_UNICODE = '''
def greet_user(name):
    """Greet user with emoji 👋 and multilingual support."""
    greetings = {
        'ko': '안녕하세요',
        'zh': '你好',
        'ja': 'こんにちは',
        'emoji': '🌍🎉'
    }
    return f"Hello {name}! {greetings['emoji']}"

class MultilingualApp:
    """Application with multilingual support 🌐"""

    def translate(self, text, lang):
        """Translate text to target language 🔤"""
        # Translation logic here
        return text
'''


def test_docstring_extraction():
    """Test docstring extraction with different quote styles."""
    print("=" * 60)
    print("TEST 1: Docstring Extraction (Triple Quotes)")
    print("=" * 60)

    # Test with AI disabled to test only extraction
    parser = CodeParser(ai_docstring_enabled=False)
    chunks = parser.parse_file("test.py", TEST_CODE_TRIPLE_QUOTES, "python")

    for chunk in chunks:
        print(f"\n{chunk.chunk_type.upper()}: {chunk.name}")
        print(f"Docstring: {repr(chunk.docstring)}")
        print(f"Lines: {chunk.line_start}-{chunk.line_end}")


def test_with_docstrings():
    """Test parsing code that already has docstrings."""
    print("\n" + "=" * 60)
    print("TEST 2: Code with Existing Docstrings")
    print("=" * 60)

    parser = CodeParser(ai_docstring_enabled=True)
    chunks = parser.parse_file("test.py", TEST_CODE_WITH_DOCSTRING, "python")

    for chunk in chunks:
        print(f"\n{chunk.chunk_type.upper()}: {chunk.name}")
        print(f"Docstring: {chunk.docstring}")
        if chunk.parent_name:
            print(f"Parent: {chunk.parent_name}")


def test_ai_generation():
    """Test AI docstring generation for code without docstrings."""
    print("\n" + "=" * 60)
    print("TEST 3: AI Docstring Generation")
    print("=" * 60)

    parser = CodeParser(ai_docstring_enabled=True, ai_model="gemini")
    chunks = parser.parse_file("test.py", TEST_CODE_WITHOUT_DOCSTRING, "python")

    for chunk in chunks:
        print(f"\n{chunk.chunk_type.upper()}: {chunk.name}")
        print(f"Docstring: {chunk.docstring}")
        print(f"Source: {'AI-generated' if chunk.docstring else 'None'}")
        if chunk.parent_name:
            print(f"Parent: {chunk.parent_name}")


def test_ai_disabled():
    """Test with AI disabled - should have no docstrings."""
    print("\n" + "=" * 60)
    print("TEST 4: AI Disabled (No Docstrings)")
    print("=" * 60)

    parser = CodeParser(ai_docstring_enabled=False)
    chunks = parser.parse_file("test.py", TEST_CODE_WITHOUT_DOCSTRING, "python")

    for chunk in chunks:
        print(f"\n{chunk.chunk_type.upper()}: {chunk.name}")
        print(f"Docstring: {chunk.docstring or 'None'}")


def test_unicode_characters():
    """Test parsing code with Unicode characters (emojis, Korean, Chinese, Japanese)."""
    print("\n" + "=" * 60)
    print("TEST 5: Unicode Characters (Emoji + Multilingual)")
    print("=" * 60)

    parser = CodeParser(ai_docstring_enabled=False)
    chunks = parser.parse_file("test_unicode.py", TEST_CODE_WITH_UNICODE, "python")

    for chunk in chunks:
        print(f"\n{chunk.chunk_type.upper()}: {chunk.name}")
        if chunk.docstring:
            print(f"Docstring: {chunk.docstring}")
            # Verify Unicode characters are preserved
            if '👋' in chunk.docstring or '🌐' in chunk.docstring or '🔤' in chunk.docstring:
                print("   ✅ Emoji preserved in docstring")
        if chunk.parent_name:
            print(f"Parent: {chunk.parent_name}")

        # Verify content has Unicode characters
        if '안녕하세요' in chunk.content or '你好' in chunk.content:
            print("   ✅ Multi-byte characters preserved in content")


if __name__ == "__main__":
    print("\n🧪 DOCSTRING EXTRACTION & AI GENERATION TESTS\n")

    try:
        # Test 1: Docstring extraction with different quote styles
        test_docstring_extraction()

        # Test 2: Code with existing docstrings
        test_with_docstrings()

        # Test 3: AI generation for code without docstrings
        test_ai_generation()

        # Test 4: AI disabled
        test_ai_disabled()

        # Test 5: Unicode characters (NEW)
        test_unicode_characters()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
