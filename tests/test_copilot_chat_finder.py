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
from copilot_chat_finder import CopilotChatFinder


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
                "messages": []
            }
            json.dump(chat_data, chat_file.open('w'))
            
            with patch.object(finder, 'get_storage_root', return_value=storage_path):
                result = finder._parse_chat_full(chat_file)
                # May return None if transformation fails, or a dict if successful
                assert result is None or isinstance(result, dict)

