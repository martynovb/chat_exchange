#!/usr/bin/env python3
"""
Unit tests for ClaudeChatFinder.
"""

import pytest
import json
import pathlib
import tempfile
import shutil
from unittest.mock import Mock, patch, mock_open
from src.domain.claude_chat_finder import ClaudeChatFinder


class TestClaudeChatFinder:
    """Test cases for ClaudeChatFinder."""
    
    def test_init(self):
        """Test ClaudeChatFinder initialization."""
        finder = ClaudeChatFinder()
        assert finder._finder_type == "claude"
        assert isinstance(finder, ClaudeChatFinder)
    
    def test_get_storage_root(self):
        """Test getting Claude storage root."""
        finder = ClaudeChatFinder()
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = pathlib.Path("/home/test")
            result = finder.get_storage_root()
            expected = pathlib.Path("/home/test/.claude/projects")
            assert result == expected
    
    def test_get_storage_root_returns_path_even_if_not_exists(self):
        """Test that storage root is returned even if it doesn't exist."""
        finder = ClaudeChatFinder()
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = pathlib.Path("/home/test")
            result = finder.get_storage_root()
            # Should return path even if it doesn't exist
            assert result == pathlib.Path("/home/test/.claude/projects")
    
    def test_find_all_chat_files_no_storage(self):
        """Test finding chat files when storage doesn't exist."""
        finder = ClaudeChatFinder()
        with patch.object(finder, 'get_storage_root', return_value=None):
            result = finder.find_all_chat_files()
            assert result == []
    
    def test_find_all_chat_files_empty_storage(self):
        """Test finding chat files in empty storage."""
        finder = ClaudeChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            with patch.object(finder, 'get_storage_root', return_value=storage_path):
                result = finder.find_all_chat_files()
                assert result == []
    
    def test_find_all_chat_files_with_jsonl(self):
        """Test finding JSONL chat files."""
        finder = ClaudeChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            project_dir = storage_path / "project1"
            project_dir.mkdir()
            
            # Create a JSONL file
            jsonl_file = project_dir / "chat1.jsonl"
            jsonl_file.write_text('{"type": "user", "message": {"content": "test"}}\n')
            
            with patch.object(finder, 'get_storage_root', return_value=storage_path):
                result = finder.find_all_chat_files()
                assert len(result) == 1
                assert result[0].name == "chat1.jsonl"
    
    def test_find_all_chat_files_skips_cache_dirs(self):
        """Test that cache directories are skipped."""
        finder = ClaudeChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            project_dir = storage_path / ".cache"
            project_dir.mkdir()
            
            jsonl_file = project_dir / "chat1.jsonl"
            jsonl_file.write_text('{"type": "user"}\n')
            
            with patch.object(finder, 'get_storage_root', return_value=storage_path):
                result = finder.find_all_chat_files()
                assert len(result) == 0
    
    def test_parse_jsonl_file(self):
        """Test parsing JSONL file."""
        finder = ClaudeChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type": "user", "message": {"content": "hello"}}\n')
            f.write('{"type": "assistant", "message": {"content": []}}\n')
            f.flush()
            f.close()  # Close file before reading/unlinking
            
            result = finder._parse_jsonl_file(pathlib.Path(f.name))
            assert len(result) == 2
            assert result[0]["type"] == "user"
            assert result[1]["type"] == "assistant"
            
            pathlib.Path(f.name).unlink()
    
    def test_parse_jsonl_file_empty(self):
        """Test parsing empty JSONL file."""
        finder = ClaudeChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('\n\n')
            f.flush()
            f.close()  # Close file before reading/unlinking
            
            result = finder._parse_jsonl_file(pathlib.Path(f.name))
            assert result == []
            
            pathlib.Path(f.name).unlink()
    
    def test_parse_jsonl_file_invalid_json(self):
        """Test parsing JSONL file with invalid JSON."""
        finder = ClaudeChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type": "user"}\n')
            f.write('invalid json line\n')
            f.write('{"type": "assistant"}\n')
            f.flush()
            f.close()  # Close file before reading/unlinking
            
            result = finder._parse_jsonl_file(pathlib.Path(f.name))
            assert len(result) == 2  # Invalid line should be skipped
            
            pathlib.Path(f.name).unlink()
    
    def test_get_timezone_offset(self):
        """Test timezone offset from base class."""
        finder = ClaudeChatFinder()
        offset = finder._get_timezone_offset()
        assert offset.startswith("UTC")
    
    def test_generate_chat_id(self):
        """Test that _generate_chat_id generates a unique ID."""
        finder = ClaudeChatFinder()
        test_path = pathlib.Path("/test/project/file.jsonl")
        result = finder._generate_chat_id(test_path)
        assert isinstance(result, str)
        assert len(result) == 16  # Should be 16 hex characters
        # Should be deterministic
        result2 = finder._generate_chat_id(test_path)
        assert result == result2
    
    def test_extract_metadata_lightweight_invalid_path(self):
        """Test that _extract_metadata_lightweight returns None for invalid path."""
        finder = ClaudeChatFinder()
        # Non-Path object should return None
        result = finder._extract_metadata_lightweight("not_a_path")
        assert result is None
    
    def test_parse_chat_full_not_implemented(self):
        """Test that _parse_chat_full is not yet implemented."""
        finder = ClaudeChatFinder()
        result = finder._parse_chat_full(pathlib.Path("/test"))
        assert result is None
    
    def test_get_chat_metadata_list(self):
        """Test that get_chat_metadata_list returns a list."""
        finder = ClaudeChatFinder()
        result = finder.get_chat_metadata_list()
        assert isinstance(result, list)
        # May be empty if no chats found, or contain items if chats exist
    
    def test_parse_chat_by_id_not_found(self):
        """Test that parse_chat_by_id raises ValueError for non-existent chat."""
        finder = ClaudeChatFinder()
        with pytest.raises(ValueError, match="Chat ID 'test_id' not found"):
            finder.parse_chat_by_id("test_id")
    
    def test_extract_text_content_string(self):
        """Test extracting text content from string."""
        finder = ClaudeChatFinder()
        result = finder._extract_text_content("Hello world")
        assert result == "Hello world"
    
    def test_extract_text_content_list(self):
        """Test extracting text content from list."""
        finder = ClaudeChatFinder()
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "World"}
        ]
        result = finder._extract_text_content(content)
        assert result == "Hello\nWorld"
    
    def test_extract_text_content_empty(self):
        """Test extracting text content from empty value."""
        finder = ClaudeChatFinder()
        assert finder._extract_text_content(None) == ""
        assert finder._extract_text_content("") == ""
        assert finder._extract_text_content([]) == ""
    
    def test_extract_text_content_dict_with_text(self):
        """Test extracting text content from dict with text field."""
        finder = ClaudeChatFinder()
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "image", "source": {"type": "url"}},
            {"text": "World"}
        ]
        result = finder._extract_text_content(content)
        assert "Hello" in result
        assert "World" in result
    
    def test_extract_text_content_mixed(self):
        """Test extracting text content from mixed types."""
        finder = ClaudeChatFinder()
        content = ["Hello", {"type": "text", "text": "World"}]
        result = finder._extract_text_content(content)
        assert "Hello" in result
        assert "World" in result
    
    def test_parse_iso_timestamp(self):
        """Test parsing ISO timestamp strings."""
        finder = ClaudeChatFinder()
        # Test with Z suffix
        dt = finder._parse_iso_timestamp("2024-01-01T12:00:00Z")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1
        
        # Test with timezone offset
        dt2 = finder._parse_iso_timestamp("2024-01-01T12:00:00+00:00")
        assert dt2 is not None
        
        # Test invalid timestamp
        dt3 = finder._parse_iso_timestamp("invalid")
        assert dt3 is None
    
    def test_find_all_chat_files_with_json(self):
        """Test finding JSON chat files."""
        finder = ClaudeChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            project_dir = storage_path / "project1"
            project_dir.mkdir()
            
            # Create a JSON file
            json_file = project_dir / "chat1.json"
            json_file.write_text('{"type": "user", "message": {"content": "test"}}')
            
            with patch.object(finder, 'get_storage_root', return_value=storage_path):
                result = finder.find_all_chat_files()
                assert len(result) == 1
                assert result[0].name == "chat1.json"
    
    def test_extract_metadata_lightweight_with_jsonl(self):
        """Test extracting metadata from JSONL file."""
        finder = ClaudeChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type": "user", "message": {"content": "Hello world"}, "timestamp": "2024-01-01T12:00:00Z"}\n')
            f.flush()
            f.close()
            
            result = finder._extract_metadata_lightweight(pathlib.Path(f.name))
            assert result is not None
            assert "id" in result
            assert "title" in result
            assert "date" in result
            assert "file_path" in result
            assert result["title"] == "Hello world"
            
            pathlib.Path(f.name).unlink()
    
    def test_parse_chat_full_jsonl(self):
        """Test parsing full chat from JSONL file."""
        finder = ClaudeChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = pathlib.Path(tmpdir) / "project1"
            project_dir.mkdir()
            jsonl_file = project_dir / "chat.jsonl"
            jsonl_file.write_text('{"type": "user", "message": {"content": "Hello"}, "timestamp": "2024-01-01T12:00:00Z"}\n{"type": "assistant", "message": {"content": [{"type": "text", "text": "Hi there"}]}, "timestamp": "2024-01-01T12:00:10Z"}\n')
            
            result = finder._parse_chat_full(jsonl_file)
            assert result is not None
            assert isinstance(result, dict)
            assert "title" in result
            assert "messages" in result
            assert "metadata" in result
            assert len(result["messages"]) > 0
            
    def test_parse_chat_full_json(self):
        """Test parsing full chat from JSON file."""
        finder = ClaudeChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = pathlib.Path(tmpdir) / "project1"
            project_dir.mkdir()
            json_file = project_dir / "chat.json"
            json_file.write_text(json.dumps([{"type": "user", "message": {"content": "Hello"}, "timestamp": "2024-01-01T12:00:00Z"}]))
            
            result = finder._parse_chat_full(json_file)
            assert result is not None
            assert isinstance(result, dict)
    
    def test_parse_chat_full_invalid_path(self):
        """Test parsing chat with invalid path."""
        finder = ClaudeChatFinder()
        result = finder._parse_chat_full("not_a_path")
        assert result is None
    
    def test_transform_messages_user(self):
        """Test transforming user messages."""
        finder = ClaudeChatFinder()
        data = [{
            "type": "user",
            "message": {"content": "Hello"},
            "timestamp": "2024-01-01T12:00:00Z"
        }]
        messages = finder._transform_messages(data)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
    
    def test_transform_messages_assistant_text(self):
        """Test transforming assistant text messages."""
        finder = ClaudeChatFinder()
        data = [{
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Hi there"}]},
            "timestamp": "2024-01-01T12:00:00Z"
        }]
        messages = finder._transform_messages(data)
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["type"] == "text"
        assert messages[0]["content"] == "Hi there"
    
    def test_transform_messages_tool_use(self):
        """Test transforming tool use messages."""
        finder = ClaudeChatFinder()
        data = [
            {
                "type": "user",
                "message": {"content": [{"type": "tool_result", "tool_use_id": "tool_123", "content": "Result"}]},
                "timestamp": "2024-01-01T12:00:00Z"
            },
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": "tool_123", "name": "test_tool", "input": {}}]},
                "timestamp": "2024-01-01T12:00:05Z"
            }
        ]
        messages = finder._transform_messages(data)
        # Should have one tool message
        tool_messages = [m for m in messages if m.get("type") == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0]["content"]["tool_name"] == "read"
    
    def test_transform_messages_skip_file_history(self):
        """Test that file-history-snapshot entries are skipped."""
        finder = ClaudeChatFinder()
        data = [
            {"type": "file-history-snapshot", "data": "..."},
            {"type": "user", "message": {"content": "Hello"}, "timestamp": "2024-01-01T12:00:00Z"}
        ]
        messages = finder._transform_messages(data)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
    
    def test_transform_chat_to_export_format(self):
        """Test transforming chat to export format."""
        finder = ClaudeChatFinder()
        data = [
            {"type": "user", "message": {"content": "Hello"}, "timestamp": "2024-01-01T12:00:00Z"},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hi"}], "model": "claude-sonnet-4-20250514"}, "timestamp": "2024-01-01T12:00:10Z"}
        ]
        result = finder._transform_chat_to_export_format(data, "project1", "chat.jsonl")
        assert "title" in result
        assert "metadata" in result
        assert "createdAt" in result
        assert "messages" in result
        assert result["metadata"]["model"] == "Claude Sonnet 4.0"
        assert result["metadata"]["Project"] == "project1"
    
    def test_transform_chat_to_export_format_no_timestamp(self):
        """Test transforming chat without timestamp."""
        finder = ClaudeChatFinder()
        data = [{"type": "user", "message": {"content": "Hello"}}]
        result = finder._transform_chat_to_export_format(data, "project1", "chat.jsonl")
        assert "createdAt" in result
        assert result["createdAt"] is not None
    
    def test_export_chats_empty(self):
        """Test exporting chats when no files found."""
        finder = ClaudeChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.close()
            output_path = pathlib.Path(f.name)
            
            with patch.object(finder, 'find_all_chat_files', return_value=[]):
                result = finder.export_chats(output_path)
                assert result == []
                assert output_path.exists()
                data = json.loads(output_path.read_text())
                assert data == []
            
            output_path.unlink()
    
    def test_export_chats_with_files(self):
        """Test exporting chats with actual files."""
        finder = ClaudeChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = pathlib.Path(tmpdir) / "project1"
            project_dir.mkdir()
            jsonl_file = project_dir / "chat.jsonl"
            jsonl_file.write_text('{"type": "user", "message": {"content": "Hello"}, "timestamp": "2024-01-01T12:00:00Z"}\n')
            
            output_path = pathlib.Path(tmpdir) / "output.json"
            
            with patch.object(finder, 'get_storage_root', return_value=pathlib.Path(tmpdir)):
                result = finder.export_chats(output_path)
                assert len(result) == 1
                assert output_path.exists()
                data = json.loads(output_path.read_text())
                assert len(data) == 1
    
    def test_extract_metadata_lightweight_with_json(self):
        """Test extracting metadata from JSON file."""
        finder = ClaudeChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_data = [{"type": "user", "message": {"content": "Hello"}, "timestamp": "2024-01-01T12:00:00Z"}]
            json.dump(json_data, f)
            f.flush()
            f.close()
            
            result = finder._extract_metadata_lightweight(pathlib.Path(f.name))
            assert result is not None
            assert "id" in result
            assert "title" in result
            assert "date" in result
            
            pathlib.Path(f.name).unlink()
    
    def test_extract_metadata_lightweight_fallback_to_filename(self):
        """Test that metadata falls back to filename when no title found."""
        finder = ClaudeChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type": "system", "message": {"content": "system message"}}\n')
            f.flush()
            f.close()
            
            result = finder._extract_metadata_lightweight(pathlib.Path(f.name))
            assert result is not None
            assert result["title"] != "Untitled Conversation"  # Should use filename stem
    
    def test_extract_metadata_lightweight_fallback_to_mtime(self):
        """Test that metadata falls back to file modification time."""
        finder = ClaudeChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type": "system", "message": {"content": "system"}}\n')
            f.flush()
            f.close()
            
            result = finder._extract_metadata_lightweight(pathlib.Path(f.name))
            assert result is not None
            assert "date" in result
            assert result["date"]  # Should have a date
            
            pathlib.Path(f.name).unlink()
    
    def test_transform_messages_tool_use_with_tool_use_result(self):
        """Test transforming tool use with toolUseResult."""
        finder = ClaudeChatFinder()
        data = [
            {
                "type": "user",
                "message": {"content": [{"type": "tool_result", "tool_use_id": "tool_123", "content": "Result"}]},
                "timestamp": "2024-01-01T12:00:00Z",
                "toolUseResult": {"stdout": "Tool output", "stderr": ""}
            },
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": "tool_123", "name": "test_tool", "input": {}}]},
                "timestamp": "2024-01-01T12:00:05Z"
            }
        ]
        messages = finder._transform_messages(data)
        tool_messages = [m for m in messages if m.get("type") == "tool"]
        assert len(tool_messages) == 1
        # Read tools return empty output for non-pattern reads
        assert tool_messages[0]["content"]["tool_output"] == ""
    
    def test_transform_messages_tool_use_with_stderr(self):
        """Test transforming tool use with stderr output."""
        finder = ClaudeChatFinder()
        data = [
            {
                "type": "user",
                "message": {"content": [{"type": "tool_result", "tool_use_id": "tool_123"}]},
                "timestamp": "2024-01-01T12:00:00Z",
                "toolUseResult": {"stdout": "", "stderr": "Error message"}
            },
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": "tool_123", "name": "test_tool", "input": {}}]},
                "timestamp": "2024-01-01T12:00:05Z"
            }
        ]
        messages = finder._transform_messages(data)
        tool_messages = [m for m in messages if m.get("type") == "tool"]
        assert len(tool_messages) == 1
        # Read tools return empty output for non-pattern reads
        assert tool_messages[0]["content"]["tool_output"] == ""
    
    def test_transform_messages_skip_thinking(self):
        """Test that thinking blocks are skipped."""
        finder = ClaudeChatFinder()
        data = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "thinking", "text": "..."}, {"type": "text", "text": "Hello"}]},
                "timestamp": "2024-01-01T12:00:00Z"
            }
        ]
        messages = finder._transform_messages(data)
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello"
    
    def test_transform_messages_empty_text_content(self):
        """Test that messages with empty text content are skipped."""
        finder = ClaudeChatFinder()
        data = [
            {"type": "user", "message": {"content": ""}, "timestamp": "2024-01-01T12:00:00Z"},
            {"type": "user", "message": {"content": "   "}, "timestamp": "2024-01-01T12:00:00Z"}
        ]
        messages = finder._transform_messages(data)
        assert len(messages) == 0
    
    def test_transform_chat_to_export_format_different_models(self):
        """Test transforming chat with different model names."""
        finder = ClaudeChatFinder()
        data = [
            {"type": "assistant", "message": {"content": [], "model": "claude-sonnet-3-20240229"}, "timestamp": "2024-01-01T12:00:00Z"}
        ]
        result = finder._transform_chat_to_export_format(data, "project1", "chat.jsonl")
        assert result["metadata"]["model"] == "Claude Sonnet 3.5"
        
        data2 = [
            {"type": "assistant", "message": {"content": [], "model": "claude-opus-20240229"}, "timestamp": "2024-01-01T12:00:00Z"}
        ]
        result2 = finder._transform_chat_to_export_format(data2, "project1", "chat.jsonl")
        assert result2["metadata"]["model"] == "Claude Opus"
    
    def test_export_chats_skip_invalid_files(self):
        """Test that export_chats skips files that can't be parsed."""
        finder = ClaudeChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = pathlib.Path(tmpdir) / "project1"
            project_dir.mkdir()
            jsonl_file = project_dir / "chat.jsonl"
            jsonl_file.write_text('invalid json\n')
            
            output_path = pathlib.Path(tmpdir) / "output.json"
            
            with patch.object(finder, 'get_storage_root', return_value=pathlib.Path(tmpdir)):
                result = finder.export_chats(output_path)
                # Should skip invalid file
                assert len(result) == 0
    
    def test_transform_chat_to_export_format_haiku_model(self):
        """Test transforming chat with Haiku model."""
        finder = ClaudeChatFinder()
        data = [
            {"type": "assistant", "message": {"content": [], "model": "claude-haiku-20240307"}, "timestamp": "2024-01-01T12:00:00Z"}
        ]
        result = finder._transform_chat_to_export_format(data, "project1", "chat.jsonl")
        assert result["metadata"]["model"] == "Claude Haiku"
    
    def test_transform_chat_to_export_format_opus_model(self):
        """Test transforming chat with Opus model."""
        finder = ClaudeChatFinder()
        data = [
            {"type": "assistant", "message": {"content": [], "model": "claude-opus-20240229"}, "timestamp": "2024-01-01T12:00:00Z"}
        ]
        result = finder._transform_chat_to_export_format(data, "project1", "chat.jsonl")
        assert result["metadata"]["model"] == "Claude Opus"
    
    def test_extract_metadata_lightweight_json_with_timestamp(self):
        """Test extracting metadata from JSON file with timestamp."""
        finder = ClaudeChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_data = [{"type": "user", "message": {"content": "Hello"}, "timestamp": "2024-01-01T12:00:00Z"}]
            json.dump(json_data, f)
            f.flush()
            f.close()
            
            result = finder._extract_metadata_lightweight(pathlib.Path(f.name))
            assert result is not None
            assert "2024-01-01" in result["date"]
            
            pathlib.Path(f.name).unlink()
    
    def test_extract_metadata_lightweight_long_title(self):
        """Test extracting metadata with long title that gets truncated."""
        finder = ClaudeChatFinder()
        long_title = "A" * 150
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(f'{{"type": "user", "message": {{"content": "{long_title}"}}, "timestamp": "2024-01-01T12:00:00Z"}}\n')
            f.flush()
            f.close()
            
            result = finder._extract_metadata_lightweight(pathlib.Path(f.name))
            assert result is not None
            assert len(result["title"]) <= 103  # 100 chars + "..."
            
            pathlib.Path(f.name).unlink()

