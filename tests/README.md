# Chat Finder Unit Tests

This directory contains unit tests for all chat finder classes.

## Running Tests

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_claude_chat_finder.py
pytest tests/test_copilot_chat_finder.py
pytest tests/test_cursor_chat_finder.py
pytest tests/test_base_chat_finder.py
```

### Run with Coverage

```bash
pytest --cov=. --cov-report=html
```

### Run Verbose

```bash
pytest -v
```

## Test Structure

- `test_base_chat_finder.py` - Tests for the base abstract class
- `test_claude_chat_finder.py` - Tests for ClaudeChatFinder
- `test_copilot_chat_finder.py` - Tests for CopilotChatFinder
- `test_cursor_chat_finder.py` - Tests for CursorChatFinder

## Test Coverage

The tests cover:
- Class initialization
- Storage root detection (platform-specific)
- File discovery methods
- Abstract method implementations
- Utility methods
- Error handling
- Edge cases (empty files, invalid data, etc.)

## Notes

- Tests use temporary directories and mock file systems to avoid modifying real data
- Database operations are mocked for Cursor tests
- Platform-specific tests use mocking to test different OS behaviors


