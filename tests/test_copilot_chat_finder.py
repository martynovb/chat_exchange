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
    
    def test_generate_chat_id_not_implemented(self):
        """Test that _generate_chat_id is not yet implemented."""
        finder = CopilotChatFinder()
        result = finder._generate_chat_id(pathlib.Path("/test"))
        assert result is None
    
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
    
    def test_get_chat_metadata_list_not_implemented(self):
        """Test that get_chat_metadata_list is not yet implemented."""
        finder = CopilotChatFinder()
        result = finder.get_chat_metadata_list()
        assert result is None
    
    def test_parse_chat_by_id_not_implemented(self):
        """Test that parse_chat_by_id is not yet implemented."""
        finder = CopilotChatFinder()
        result = finder.parse_chat_by_id("test_id")
        assert result is None
    
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

