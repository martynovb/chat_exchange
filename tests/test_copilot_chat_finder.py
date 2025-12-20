#!/usr/bin/env python3
"""
Unit tests for CopilotChatFinder.
"""

import pytest
import json
import pathlib
import tempfile
import platform
from unittest.mock import Mock, patch
from src.domain.copilot_chat_finder import CopilotChatFinder


class TestCopilotChatFinder:
    """Test cases for CopilotChatFinder."""
    
    def test_init(self):
        """Test CopilotChatFinder initialization."""
        finder = CopilotChatFinder()
        assert finder._finder_type == "copilot"
        assert isinstance(finder, CopilotChatFinder)
    
    def test_get_storage_root_windows(self):
        """Test getting Copilot storage root on Windows."""
        finder = CopilotChatFinder()
        with patch('platform.system', return_value='Windows'), \
             patch('pathlib.Path.home', return_value=pathlib.Path("C:/Users/test")):
            result = finder.get_storage_root()
            expected = pathlib.Path("C:/Users/test/AppData/Roaming/Code/User/workspaceStorage")
            assert result == expected
    
    def test_get_storage_root_darwin(self):
        """Test getting Copilot storage root on macOS."""
        finder = CopilotChatFinder()
        with patch('platform.system', return_value='Darwin'), \
             patch('pathlib.Path.home', return_value=pathlib.Path("/Users/test")):
            result = finder.get_storage_root()
            expected = pathlib.Path("/Users/test/Library/Application Support/Code/User/workspaceStorage")
            assert result == expected
    
    def test_get_storage_root_linux(self):
        """Test getting Copilot storage root on Linux."""
        finder = CopilotChatFinder()
        with patch('platform.system', return_value='Linux'), \
             patch('pathlib.Path.home', return_value=pathlib.Path("/home/test")):
            result = finder.get_storage_root()
            expected = pathlib.Path("/home/test/.config/Code/User/workspaceStorage")
            assert result == expected
    
    def test_get_storage_root_unsupported(self):
        """Test getting storage root on unsupported platform."""
        finder = CopilotChatFinder()
        with patch('platform.system', return_value='Unknown'):
            result = finder.get_storage_root()
            assert result is None
    
    def test_get_storage_root_prefers_existing(self):
        """Test that existing storage path is preferred."""
        finder = CopilotChatFinder()
        with patch('platform.system', return_value='Windows'), \
             patch('pathlib.Path.home', return_value=pathlib.Path("C:/Users/test")):
            # Create a mock that returns True for Insiders path
            def mock_exists(self):
                return "Code - Insiders" in str(self)
            
            with patch.object(pathlib.Path, 'exists', mock_exists):
                result = finder.get_storage_root()
                expected = pathlib.Path("C:/Users/test/AppData/Roaming/Code - Insiders/User/workspaceStorage")
                assert result == expected
    
    def test_find_all_chat_files_no_storage(self):
        """Test finding chat files when storage doesn't exist."""
        finder = CopilotChatFinder()
        with patch.object(finder, 'get_storage_root', return_value=None):
            result = finder.find_all_chat_files()
            assert result == []
    
    def test_find_all_chat_files_empty_storage(self):
        """Test finding chat files in empty storage."""
        finder = CopilotChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            with patch.object(finder, 'get_storage_root', return_value=storage_path):
                result = finder.find_all_chat_files()
                assert result == []
    
    def test_find_all_chat_files_with_chats(self):
        """Test finding chat files in workspace storage."""
        finder = CopilotChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            chat_dir = workspace_dir / "chatSessions"
            chat_dir.mkdir()
            
            # Create a chat JSON file
            chat_file = chat_dir / "chat1.json"
            chat_file.write_text('{"sessionId": "123", "customTitle": "Test Chat"}')
            
            with patch.object(finder, 'get_storage_root', return_value=storage_path):
                result = finder.find_all_chat_files()
                assert len(result) == 1
                assert result[0].name == "chat1.json"
    
    def test_timestamp_ms_to_iso(self):
        """Test converting milliseconds timestamp to ISO format."""
        finder = CopilotChatFinder()
        timestamp_ms = 1609459200000  # 2021-01-01 00:00:00 UTC
        result = finder._timestamp_ms_to_iso(timestamp_ms)
        assert result.endswith('Z')
        assert '2021-01-01' in result
    
    def test_timestamp_ms_to_iso_none(self):
        """Test converting None timestamp to ISO format."""
        finder = CopilotChatFinder()
        result = finder._timestamp_ms_to_iso(None)
        assert result.endswith('Z')
    
    def test_get_timezone_offset(self):
        """Test timezone offset from base class."""
        finder = CopilotChatFinder()
        offset = finder._get_timezone_offset()
        assert offset.startswith("UTC")
    
    def test_generate_chat_id(self):
        """Test that _generate_chat_id generates a unique ID."""
        finder = CopilotChatFinder()
        test_path = pathlib.Path("/test/workspace/chat.json")
        result = finder._generate_chat_id(test_path)
        assert isinstance(result, str)
        assert len(result) == 16  # Should be 16 hex characters
        # Should be deterministic
        result2 = finder._generate_chat_id(test_path)
        assert result == result2
    
    def test_extract_metadata_lightweight_not_implemented(self):
        """Test that _extract_metadata_lightweight is not yet implemented."""
        finder = CopilotChatFinder()
        result = finder._extract_metadata_lightweight(pathlib.Path("/test"))
        assert result is None
    
    def test_parse_chat_full_not_implemented(self):
        """Test that _parse_chat_full is not yet implemented."""
        finder = CopilotChatFinder()
        result = finder._parse_chat_full(pathlib.Path("/test"))
        assert result is None
    
    def test_get_chat_metadata_list(self):
        """Test that get_chat_metadata_list returns a list."""
        finder = CopilotChatFinder()
        result = finder.get_chat_metadata_list()
        assert isinstance(result, list)
        # May be empty if no chats found, or contain items if chats exist
    
    def test_parse_chat_by_id_not_found(self):
        """Test that parse_chat_by_id raises ValueError for non-existent chat."""
        finder = CopilotChatFinder()
        with pytest.raises(ValueError, match="Chat ID 'test_id' not found"):
            finder.parse_chat_by_id("test_id")
    
    def test_extract_text_from_value_string(self):
        """Test extracting text from string value."""
        finder = CopilotChatFinder()
        result = finder._extract_text_from_value("Hello")
        assert result == "Hello"
    
    def test_extract_text_from_value_dict(self):
        """Test extracting text from dict with value field."""
        finder = CopilotChatFinder()
        result = finder._extract_text_from_value({"value": "Hello"})
        assert result == "Hello"
    
    def test_extract_text_from_value_invalid(self):
        """Test extracting text from invalid value."""
        finder = CopilotChatFinder()
        result = finder._extract_text_from_value(None)
        assert result == ""
        result = finder._extract_text_from_value({})
        assert result == ""
    
    def test_extract_workspace_path_from_json_file_url(self):
        """Test extracting workspace path from JSON with file:// URL."""
        finder = CopilotChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_data = {"folder": "file:///C:/Users/test/project"}
            json.dump(json_data, f)
            f.flush()
            f.close()
            
            result = finder._extract_workspace_path_from_json(pathlib.Path(f.name))
            assert result == "/C:/Users/test/project"
            
            pathlib.Path(f.name).unlink()
    
    def test_extract_workspace_path_from_json_plain_path(self):
        """Test extracting workspace path from JSON with plain path."""
        finder = CopilotChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_data = {"folder": "C:/Users/test/project"}
            json.dump(json_data, f)
            f.flush()
            f.close()
            
            result = finder._extract_workspace_path_from_json(pathlib.Path(f.name))
            assert result == "C:/Users/test/project"
            
            pathlib.Path(f.name).unlink()
    
    def test_extract_workspace_path_from_json_nested(self):
        """Test extracting workspace path from nested JSON structure."""
        finder = CopilotChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_data = {"config": {"workspace": {"path": "file:///home/user/project"}}}
            json.dump(json_data, f)
            f.flush()
            f.close()
            
            result = finder._extract_workspace_path_from_json(pathlib.Path(f.name))
            assert result == "/home/user/project"
            
            pathlib.Path(f.name).unlink()
    
    def test_extract_workspace_path_from_json_invalid(self):
        """Test extracting workspace path from invalid JSON."""
        finder = CopilotChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json")
            f.flush()
            f.close()
            
            result = finder._extract_workspace_path_from_json(pathlib.Path(f.name))
            assert result is None
            
            pathlib.Path(f.name).unlink()
    
    def test_extract_project_name(self):
        """Test extracting project name from workspace."""
        finder = CopilotChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace123"
            workspace_dir.mkdir()
            workspace_json = workspace_dir / "workspace.json"
            
            json_data = {"folder": "file:///C:/Users/test/myproject"}
            json.dump(json_data, workspace_json.open('w'))
            
            result = finder._extract_project_name("workspace123", storage_path)
            assert result == "myproject"
    
    def test_extract_project_name_no_workspace_json(self):
        """Test extracting project name when workspace.json doesn't exist."""
        finder = CopilotChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace123"
            workspace_dir.mkdir()
            
            result = finder._extract_project_name("workspace123", storage_path)
            assert result == "Unknown Project"
    
    def test_extract_metadata_lightweight_with_file(self):
        """Test extracting metadata from actual chat file."""
        finder = CopilotChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            chat_dir = workspace_dir / "chatSessions"
            chat_dir.mkdir()
            
            # Create a chat JSON file
            chat_file = chat_dir / "chat1.json"
            chat_data = {
                "sessionId": "12345",
                "customTitle": "Test Chat",
                "creationDate": 1609459200000  # 2021-01-01
            }
            json.dump(chat_data, chat_file.open('w'))
            
            result = finder._extract_metadata_lightweight(chat_file)
            assert result is not None
            assert result["title"] == "Test Chat"
            assert "2021-01-01" in result["date"]
            assert "id" in result
    
    def test_parse_chat_full(self):
        """Test parsing full chat content."""
        finder = CopilotChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            chat_dir = workspace_dir / "chatSessions"
            chat_dir.mkdir()
            
            # Create a minimal chat JSON file
            chat_file = chat_dir / "chat1.json"
            chat_data = {
                "sessionId": "12345",
                "customTitle": "Test Chat",
                "creationDate": 1609459200000,
                "requests": [{
                    "message": {"text": "Hello"},
                    "response": [{"value": "Hi there"}]
                }]
            }
            json.dump(chat_data, chat_file.open('w'))
            
            with patch.object(finder, 'get_storage_root', return_value=storage_path):
                result = finder._parse_chat_full(chat_file)
                # Should return a dict with messages
                assert result is not None
                assert isinstance(result, dict)
                assert "messages" in result
                assert len(result["messages"]) > 0
    
    def test_parse_chat_full_no_storage(self):
        """Test parsing chat when storage root is None."""
        finder = CopilotChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"sessionId": "123"}, f)
            f.flush()
            f.close()
            
            with patch.object(finder, 'get_storage_root', return_value=None):
                result = finder._parse_chat_full(pathlib.Path(f.name))
                assert result is None
            
            pathlib.Path(f.name).unlink()
    
    def test_parse_chat_full_invalid_path(self):
        """Test parsing chat with invalid path."""
        finder = CopilotChatFinder()
        result = finder._parse_chat_full("not_a_path")
        assert result is None
    
    def test_extract_metadata_lightweight(self):
        """Test extracting metadata from chat file."""
        finder = CopilotChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            chat_dir = workspace_dir / "chatSessions"
            chat_dir.mkdir()
            
            chat_file = chat_dir / "chat1.json"
            chat_data = {
                "sessionId": "12345",
                "customTitle": "Test Chat",
                "creationDate": 1609459200000
            }
            json.dump(chat_data, chat_file.open('w'))
            
            result = finder._extract_metadata_lightweight(chat_file)
            assert result is not None
            assert result["title"] == "Test Chat"
            assert "2021-01-01" in result["date"]
    
    def test_extract_metadata_lightweight_no_title(self):
        """Test extracting metadata when no custom title."""
        finder = CopilotChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            chat_dir = workspace_dir / "chatSessions"
            chat_dir.mkdir()
            
            chat_file = chat_dir / "chat1.json"
            chat_data = {
                "sessionId": "12345678",
                "creationDate": 1609459200000
            }
            json.dump(chat_data, chat_file.open('w'))
            
            result = finder._extract_metadata_lightweight(chat_file)
            assert result is not None
            assert "Chat 12345678" in result["title"]
    
    def test_transform_chat_to_new_format(self):
        """Test transforming chat to new format."""
        finder = CopilotChatFinder()
        raw_data = {
            "sessionId": "12345",
            "customTitle": "Test Chat",
            "creationDate": 1609459200000,
            "responderUsername": "GitHub Copilot",
            "requests": [{
                "message": {"text": "Hello"},
                "response": [{"value": "Hi there"}]
            }]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            workspace_json = workspace_dir / "workspace.json"
            json.dump({"folder": "file:///C:/Users/test/myproject"}, workspace_json.open('w'))
            
            result = finder._transform_chat_to_new_format(raw_data, "workspace1", storage_path)
            assert result is not None
            assert result["title"] == "Test Chat"
            assert "messages" in result
            assert len(result["messages"]) > 0
            assert result["metadata"]["Project"] == "myproject"
    
    def test_transform_chat_to_new_format_no_messages(self):
        """Test transforming chat with no messages."""
        finder = CopilotChatFinder()
        raw_data = {
            "sessionId": "12345",
            "creationDate": 1609459200000,
            "requests": []
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            
            result = finder._transform_chat_to_new_format(raw_data, "workspace1", storage_path)
            assert result is None  # Should return None when no messages
    
    def test_transform_chat_to_new_format_with_code_block(self):
        """Test transforming chat with code blocks."""
        finder = CopilotChatFinder()
        raw_data = {
            "sessionId": "12345",
            "creationDate": 1609459200000,
            "requests": [{
                "message": {"text": "Show me code"},
                "response": [
                    {"value": "```"},
                    {"kind": "codeblockUri", "uri": {"fsPath": "/path/to/file.py"}},
                    {"kind": "textEditGroup", "edits": [[{"text": "print('hello')"}]], "value": ""},
                    {"value": "```"}
                ]
            }]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            
            result = finder._transform_chat_to_new_format(raw_data, "workspace1", storage_path)
            assert result is not None
            # Should have tool message for code block
            tool_messages = [m for m in result["messages"] if m.get("type") == "tool"]
            assert len(tool_messages) > 0
    
    def test_transform_chat_to_new_format_with_tool_invocation(self):
        """Test transforming chat with tool invocations."""
        finder = CopilotChatFinder()
        raw_data = {
            "sessionId": "12345",
            "creationDate": 1609459200000,
            "requests": [{
                "message": {"text": "Search files"},
                "response": [{
                    "kind": "toolInvocationSerialized",
                    "toolId": "copilot_findFiles",
                    "invocationMessage": {"value": "Searching for `*.py`"},
                    "toolSpecificData": "file1.py, file2.py"
                }]
            }]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            
            result = finder._transform_chat_to_new_format(raw_data, "workspace1", storage_path)
            assert result is not None
            tool_messages = [m for m in result["messages"] if m.get("type") == "tool"]
            assert len(tool_messages) > 0
            assert tool_messages[0]["content"]["toolName"] == "copilot_findFiles"
    
    def test_extract_tool_input(self):
        """Test extracting tool input."""
        finder = CopilotChatFinder()
        tool_invocation = {
            "invocationMessage": {
                "value": "Searching for files matching `**/*.py`",
                "uris": {
                    "uri1": {"fsPath": "/path/to/file1.py"},
                    "uri2": {"fsPath": "/path/to/file2.py"}
                }
            }
        }
        result = finder._extract_tool_input(tool_invocation, "copilot_findFiles")
        assert "query" in result
        assert "files" in result
    
    def test_extract_tool_output(self):
        """Test extracting tool output."""
        finder = CopilotChatFinder()
        tool_invocation = {
            "toolSpecificData": "Result data"
        }
        result = finder._extract_tool_output(tool_invocation)
        assert result == "Result data"
    
    def test_extract_tool_output_past_tense(self):
        """Test extracting tool output from pastTenseMessage."""
        finder = CopilotChatFinder()
        tool_invocation = {
            "pastTenseMessage": {"value": "Found files"}
        }
        result = finder._extract_tool_output(tool_invocation)
        assert result == "Found files"
    
    def test_convert_inline_reference_to_markdown(self):
        """Test converting inline reference to markdown."""
        finder = CopilotChatFinder()
        inline_ref = {
            "fsPath": "/path/to/file.py"
        }
        result = finder._convert_inline_reference_to_markdown(inline_ref)
        assert result == "`/path/to/file.py`"
    
    def test_export_chats(self):
        """Test exporting all chats."""
        finder = CopilotChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            chat_dir = workspace_dir / "chatSessions"
            chat_dir.mkdir()
            
            chat_file = chat_dir / "chat1.json"
            chat_data = {
                "sessionId": "12345",
                "customTitle": "Test Chat",
                "creationDate": 1609459200000,
                "requests": [{
                    "message": {"text": "Hello"},
                    "response": [{"value": "Hi"}]
                }]
            }
            json.dump(chat_data, chat_file.open('w'))
            
            output_path = pathlib.Path(tmpdir) / "output.json"
            
            with patch.object(finder, 'get_storage_root', return_value=storage_path):
                result = finder.export_chats(output_path)
                assert len(result) == 1
                assert output_path.exists()
                data = json.loads(output_path.read_text())
                assert len(data) == 1
    
    def test_export_chats_empty(self):
        """Test exporting chats when no files found."""
        finder = CopilotChatFinder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.close()
            output_path = pathlib.Path(f.name)
            
            with patch.object(finder, 'find_all_chat_files', return_value=[]), \
                 patch.object(finder, 'get_storage_root', return_value=None):
                result = finder.export_chats(output_path)
                assert result == []
                assert output_path.exists()
            
            output_path.unlink()
    
    def test_extract_tool_input_with_result_details(self):
        """Test extracting tool input from resultDetails."""
        finder = CopilotChatFinder()
        tool_invocation = {
            "resultDetails": [
                {"fsPath": "/path/to/file1.py"},
                {"path": "/path/to/file2.py"}
            ]
        }
        result = finder._extract_tool_input(tool_invocation, "test_tool")
        assert "files" in result
        assert len(result["files"]) == 2
    
    def test_extract_tool_input_single_file(self):
        """Test extracting tool input with single file."""
        finder = CopilotChatFinder()
        tool_invocation = {
            "resultDetails": [{"fsPath": "/path/to/file.py"}]
        }
        result = finder._extract_tool_input(tool_invocation, "test_tool")
        assert "files" in result
        assert result["files"] == "/path/to/file.py"  # Single file, not list
    
    def test_extract_tool_input_with_uris(self):
        """Test extracting tool input from uris."""
        finder = CopilotChatFinder()
        tool_invocation = {
            "invocationMessage": {
                "uris": {
                    "uri1": {"fsPath": "/path/to/file1.py"},
                    "uri2": {"path": "/path/to/file2.py"}
                }
            }
        }
        result = finder._extract_tool_input(tool_invocation, "test_tool")
        assert "files" in result
        assert len(result["files"]) == 2
    
    def test_extract_file_path_from_inline_reference_location_uri(self):
        """Test extracting file path from inline reference with location.uri."""
        finder = CopilotChatFinder()
        inline_ref = {
            "location": {
                "uri": {
                    "fsPath": "/path/to/file.py"
                }
            }
        }
        result = finder._extract_file_path_from_inline_reference(inline_ref)
        assert result == "/path/to/file.py"
    
    def test_convert_inline_reference_to_markdown_with_name(self):
        """Test converting inline reference using name when no path."""
        finder = CopilotChatFinder()
        inline_ref = {
            "name": "file.py"
        }
        result = finder._convert_inline_reference_to_markdown(inline_ref)
        assert result == "`file.py`"
    
    def test_transform_chat_to_new_format_with_inline_reference(self):
        """Test transforming chat with inline references."""
        finder = CopilotChatFinder()
        raw_data = {
            "sessionId": "12345",
            "creationDate": 1609459200000,
            "requests": [{
                "response": [
                    {"value": "Here's the code"},
                    {"kind": "inlineReference", "inlineReference": {"fsPath": "/path/to/file.py"}},
                    {"value": " in this file"}
                ]
            }]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            
            result = finder._transform_chat_to_new_format(raw_data, "workspace1", storage_path)
            assert result is not None
            # Should combine text and inline reference
            text_messages = [m for m in result["messages"] if m.get("type") == "text"]
            assert len(text_messages) > 0
            # Check that inline reference is included in the message
            content = text_messages[0]["content"]
            assert "/path/to/file.py" in content or "`/path/to/file.py`" in content or "file.py" in content
    
    def test_export_chats_skip_invalid_files(self):
        """Test that export_chats skips files that can't be parsed."""
        finder = CopilotChatFinder()
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = pathlib.Path(tmpdir)
            workspace_dir = storage_path / "workspace1"
            workspace_dir.mkdir()
            chat_dir = workspace_dir / "chatSessions"
            chat_dir.mkdir()
            
            chat_file = chat_dir / "chat1.json"
            chat_file.write_text('invalid json')
            
            output_path = pathlib.Path(tmpdir) / "output.json"
            
            with patch.object(finder, 'get_storage_root', return_value=storage_path):
                result = finder.export_chats(output_path)
                # Should skip invalid file
                assert len(result) == 0

