"""
Test suite for parser encoding and byte offset handling.

This test file verifies that the parser correctly handles multi-byte UTF-8 characters
and properly extracts code chunks using tree-sitter's byte offsets.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from codebase.core.parser import CodeParser


# Test cases with multi-byte characters

TEST_CODE_KOREAN = '''
# 한글 주석이 포함된 코드
def calculate_sum(numbers):
    """숫자 리스트의 합계를 계산합니다."""
    total = 0
    for num in numbers:
        total += num
    return total

class 계산기:
    """간단한 계산기 클래스"""

    def 더하기(self, a, b):
        """두 숫자를 더합니다."""
        return a + b
'''

TEST_CODE_CHINESE = '''
# 中文注释
def process_data(data):
    """处理数据并返回结果"""
    result = []
    for item in data:
        # 处理每个项目
        result.append(item * 2)
    return result

class 数据处理器:
    """数据处理类"""

    def 转换(self, value):
        """转换数值"""
        return str(value)
'''

TEST_CODE_EMOJI = '''
def send_notification(message):
    """Send notification with emoji support! 🚀"""
    prefix = "📢 Alert: "
    return prefix + message

class NotificationHandler:
    """Handler for notifications 📬"""

    def broadcast(self, msg):
        """Broadcast message to all users 📡"""
        return f"Broadcasting: {msg} ✅"
'''

TEST_CODE_MIXED = '''
# Mix of ASCII, Korean (한글), Chinese (中文), and Emoji 🎉
def authenticate_user(username, password):
    """
    Authenticate user credentials.
    사용자 인증을 수행합니다.
    验证用户凭据.
    🔐 Security check!
    """
    if username == "admin":
        return True
    return False

class AuthService:
    """
    Authentication service.
    인증 서비스
    认证服务
    🔑
    """

    def login(self, user):
        """Log in user - 로그인 - 登录 - 🚪"""
        return authenticate_user(user.name, user.password)
'''

# The specific example from the bug report
TEST_CODE_MIDDLEWARE = '''
from datetime import datetime
from fastapi import FastAPI, Request

app = FastAPI()

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests."""
    start_time = datetime.now()

    # Log request
    logger.info(f"{request.method} {request.url.path} - Client: {request.client.host}")

    response = await call_next(request)

    # Log response
    process_time = datetime.now() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time.total_seconds():.3f}s"
    )

    return response


# Include routers
app.include_router(
    codebase_router.router,
    prefix="/api/codebase",
    tags=["codebase"]
)
'''

# Edge cases
TEST_CODE_LONG_UNICODE = '''
def process_text(text):
    """
    Process text with various Unicode characters.

    Examples:
    - Mathematical symbols: ∑ ∫ ∂ √ ∞
    - Greek letters: α β γ δ ε
    - Arrows: → ← ↑ ↓ ↔
    - Box drawing: ┌─┐│└┘
    - Currency: € £ ¥ ₹ ₽
    """
    symbols = "∑∫∂√∞αβγδε→←↑↓↔┌─┐│└┘€£¥₹₽"
    return text + symbols
'''


def test_korean_parsing():
    """Test parsing code with Korean characters."""
    print("\n" + "=" * 70)
    print("TEST: Korean Characters Parsing")
    print("=" * 70)

    parser = CodeParser(ai_docstring_enabled=False)
    chunks = parser.parse_file("test_korean.py", TEST_CODE_KOREAN, "python")

    # Verify we got the expected chunks
    assert len(chunks) == 3, f"Expected 3 chunks, got {len(chunks)}"

    # Check function
    func_chunk = chunks[0]
    assert func_chunk.chunk_type == 'function', f"Expected function, got {func_chunk.chunk_type}"
    assert func_chunk.name == 'calculate_sum', f"Expected 'calculate_sum', got {func_chunk.name}"
    assert '숫자 리스트의 합계를 계산합니다' in func_chunk.docstring, "Korean docstring not extracted"
    assert 'def calculate_sum(numbers):' in func_chunk.content, "Function definition not in content"

    # Check class
    class_chunk = chunks[1]
    assert class_chunk.chunk_type == 'class', f"Expected class, got {class_chunk.chunk_type}"
    assert class_chunk.name == '계산기', f"Expected '계산기', got {class_chunk.name}"
    assert '간단한 계산기 클래스' in class_chunk.docstring, "Korean class docstring not extracted"

    # Check method
    method_chunk = chunks[2]
    assert method_chunk.chunk_type == 'method', f"Expected method, got {method_chunk.chunk_type}"
    assert method_chunk.name == '더하기', f"Expected '더하기', got {method_chunk.name}"
    assert method_chunk.parent_name == '계산기', f"Expected parent '계산기', got {method_chunk.parent_name}"

    print("✅ Korean parsing test passed")
    print(f"   - Function: {func_chunk.name}")
    print(f"   - Class: {class_chunk.name}")
    print(f"   - Method: {method_chunk.name} (parent: {method_chunk.parent_name})")


def test_chinese_parsing():
    """Test parsing code with Chinese characters."""
    print("\n" + "=" * 70)
    print("TEST: Chinese Characters Parsing")
    print("=" * 70)

    parser = CodeParser(ai_docstring_enabled=False)
    chunks = parser.parse_file("test_chinese.py", TEST_CODE_CHINESE, "python")

    assert len(chunks) == 3, f"Expected 3 chunks, got {len(chunks)}"

    # Check function
    func_chunk = chunks[0]
    assert func_chunk.name == 'process_data', f"Expected 'process_data', got {func_chunk.name}"
    assert '处理数据并返回结果' in func_chunk.docstring, "Chinese docstring not extracted"

    # Check class
    class_chunk = chunks[1]
    assert class_chunk.name == '数据处理器', f"Expected '数据处理器', got {class_chunk.name}"

    # Check method
    method_chunk = chunks[2]
    assert method_chunk.name == '转换', f"Expected '转换', got {method_chunk.name}"

    print("✅ Chinese parsing test passed")
    print(f"   - Function: {func_chunk.name}")
    print(f"   - Class: {class_chunk.name}")
    print(f"   - Method: {method_chunk.name}")


def test_emoji_parsing():
    """Test parsing code with emoji characters."""
    print("\n" + "=" * 70)
    print("TEST: Emoji Characters Parsing")
    print("=" * 70)

    parser = CodeParser(ai_docstring_enabled=False)
    chunks = parser.parse_file("test_emoji.py", TEST_CODE_EMOJI, "python")

    assert len(chunks) == 3, f"Expected 3 chunks, got {len(chunks)}"

    # Check function
    func_chunk = chunks[0]
    assert func_chunk.name == 'send_notification', f"Expected 'send_notification', got {func_chunk.name}"
    assert '🚀' in func_chunk.docstring, "Emoji not preserved in docstring"
    assert '📢' in func_chunk.content, "Emoji not preserved in function content"

    # Check class
    class_chunk = chunks[1]
    assert class_chunk.name == 'NotificationHandler', f"Expected 'NotificationHandler', got {class_chunk.name}"
    assert '📬' in class_chunk.docstring, "Emoji not preserved in class docstring"

    # Check method
    method_chunk = chunks[2]
    assert method_chunk.name == 'broadcast', f"Expected 'broadcast', got {method_chunk.name}"
    assert '📡' in method_chunk.docstring, "Emoji not preserved in method docstring"

    print("✅ Emoji parsing test passed")
    print(f"   - Function: {func_chunk.name} (with 🚀)")
    print(f"   - Class: {class_chunk.name} (with 📬)")
    print(f"   - Method: {method_chunk.name} (with 📡)")


def test_mixed_unicode_parsing():
    """Test parsing code with mixed Unicode characters."""
    print("\n" + "=" * 70)
    print("TEST: Mixed Unicode Characters Parsing")
    print("=" * 70)

    parser = CodeParser(ai_docstring_enabled=False)
    chunks = parser.parse_file("test_mixed.py", TEST_CODE_MIXED, "python")

    assert len(chunks) == 3, f"Expected 3 chunks, got {len(chunks)}"

    # Check function
    func_chunk = chunks[0]
    assert func_chunk.name == 'authenticate_user', f"Expected 'authenticate_user', got {func_chunk.name}"
    docstring = func_chunk.docstring
    assert '사용자 인증을 수행합니다' in docstring, "Korean not in docstring"
    assert '验证用户凭据' in docstring, "Chinese not in docstring"
    assert '🔐' in docstring, "Emoji not in docstring"

    # Check class
    class_chunk = chunks[1]
    assert class_chunk.name == 'AuthService', f"Expected 'AuthService', got {class_chunk.name}"
    class_docstring = class_chunk.docstring
    assert '인증 서비스' in class_docstring, "Korean not in class docstring"
    assert '认证服务' in class_docstring, "Chinese not in class docstring"
    assert '🔑' in class_docstring, "Emoji not in class docstring"

    print("✅ Mixed Unicode parsing test passed")
    print(f"   - Function docstring contains: Korean, Chinese, Emoji")
    print(f"   - Class docstring contains: Korean, Chinese, Emoji")


def test_middleware_example():
    """Test the specific middleware example from the bug report."""
    print("\n" + "=" * 70)
    print("TEST: Middleware Example (Bug Report)")
    print("=" * 70)

    parser = CodeParser(ai_docstring_enabled=False)
    chunks = parser.parse_file("app.py", TEST_CODE_MIDDLEWARE, "python")

    # Find the log_requests function
    log_requests_chunk = None
    for chunk in chunks:
        if chunk.name == 'log_requests':
            log_requests_chunk = chunk
            break

    assert log_requests_chunk is not None, "Could not find 'log_requests' function"

    # Verify the function content is correct
    content = log_requests_chunk.content

    # The bug was that the decorator was being cut off
    assert '@app.middleware("http")' in content, "Decorator missing or truncated"
    assert 'async def log_requests(request: Request, call_next):' in content, "Function signature incorrect"

    # Verify it doesn't have the truncation issue
    assert not content.startswith('t: Request'), "Content is truncated (bug still present)"

    # Check line numbers
    assert log_requests_chunk.line_start > 0, "Invalid line start"
    assert log_requests_chunk.line_end > log_requests_chunk.line_start, "Invalid line end"

    print("✅ Middleware example test passed")
    print(f"   - Function: {log_requests_chunk.name}")
    print(f"   - Lines: {log_requests_chunk.line_start}-{log_requests_chunk.line_end}")
    print(f"   - Decorator preserved: @app.middleware(\"http\")")
    print(f"   - Content preview: {content[:80]}...")


def test_long_unicode_symbols():
    """Test parsing code with long sequences of Unicode symbols."""
    print("\n" + "=" * 70)
    print("TEST: Long Unicode Symbol Sequences")
    print("=" * 70)

    parser = CodeParser(ai_docstring_enabled=False)
    chunks = parser.parse_file("test_unicode.py", TEST_CODE_LONG_UNICODE, "python")

    assert len(chunks) == 1, f"Expected 1 chunk, got {len(chunks)}"

    func_chunk = chunks[0]
    assert func_chunk.name == 'process_text', f"Expected 'process_text', got {func_chunk.name}"

    # Check that all symbol categories are preserved
    docstring = func_chunk.docstring
    assert '∑' in docstring, "Mathematical symbols not preserved"
    assert 'α' in docstring, "Greek letters not preserved"
    assert '→' in docstring, "Arrows not preserved"
    assert '┌' in docstring, "Box drawing not preserved"
    assert '€' in docstring, "Currency symbols not preserved"

    content = func_chunk.content
    assert 'symbols = "∑∫∂√∞αβγδε→←↑↓↔┌─┐│└┘€£¥₹₽"' in content, "Symbol string not preserved in content"

    print("✅ Long Unicode symbol test passed")
    print(f"   - All symbol categories preserved")
    print(f"   - Function: {func_chunk.name}")


def test_byte_offset_correctness():
    """Test that byte offsets align correctly with character positions."""
    print("\n" + "=" * 70)
    print("TEST: Byte Offset Correctness")
    print("=" * 70)

    # Create code where byte offsets != character offsets
    test_code = '''# Comment with emoji 🔥 and Korean 한글
def test():
    """Docstring 📝"""
    pass
'''

    parser = CodeParser(ai_docstring_enabled=False)
    chunks = parser.parse_file("test.py", test_code, "python")

    assert len(chunks) == 1, f"Expected 1 chunk, got {len(chunks)}"

    func_chunk = chunks[0]

    # Verify the function definition is complete and correct
    assert func_chunk.content.startswith('def test():'), "Function definition incomplete"
    assert '"""Docstring 📝"""' in func_chunk.content, "Docstring with emoji not preserved"
    assert func_chunk.content.strip().endswith('pass'), "Function body incomplete"

    print("✅ Byte offset correctness test passed")
    print(f"   - Function extracted correctly despite multi-byte chars in comments")


def run_all_tests():
    """Run all encoding tests."""
    print("\n" + "🧪" * 35)
    print("PARSER ENCODING TEST SUITE")
    print("🧪" * 35)

    tests = [
        ("Korean Characters", test_korean_parsing),
        ("Chinese Characters", test_chinese_parsing),
        ("Emoji Characters", test_emoji_parsing),
        ("Mixed Unicode", test_mixed_unicode_parsing),
        ("Middleware Example", test_middleware_example),
        ("Long Unicode Symbols", test_long_unicode_symbols),
        ("Byte Offset Correctness", test_byte_offset_correctness),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"\n❌ {test_name} FAILED:")
            print(f"   {str(e)}")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name} ERROR:")
            print(f"   {str(e)}")
            import traceback
            traceback.print_exc()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total:  {passed + failed}")
    print("=" * 70)

    if failed == 0:
        print("\n🎉 All tests passed! The parser correctly handles multi-byte UTF-8 characters.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")

    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
