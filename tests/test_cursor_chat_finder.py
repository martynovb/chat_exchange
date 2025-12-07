#!/usr/bin/env python3
"""
Unit tests for CursorChatFinder.
"""

import pytest
import json
import pathlib
import tempfile
import sqlite3
import platform
from unittest.mock import Mock, patch, MagicMock
from cursor_chats_finder import CursorChatFinder


class TestCursorChatFinder:
    """Test cases for CursorChatFinder."""
    
    def test_init(self):
        """Test CursorChatFinder initialization."""
        finder = CursorChatFinder()
        assert finder._finder_type == "cursor"
        assert isinstance(finder, CursorChatFinder)
    
    def test_get_storage_root_windows(self):
        """Test getting Cursor storage root on Windows."""
        finder = CursorChatFinder()
        with patch('platform.system', return_value='Windows'), \
             patch('pathlib.Path.home', return_value=pathlib.Path("C:/Users/test")):
            result = finder.get_storage_root()
            expected = pathlib.Path("C:/Users/test/AppData/Roaming/Cursor")
            assert result == expected
    
    def test_get_storage_root_darwin(self):
        """Test getting Cursor storage root on macOS."""
        finder = CursorChatFinder()
        with patch('platform.system', return_value='Darwin'), \
             patch('pathlib.Path.home', return_value=pathlib.Path("/Users/test")):
            result = finder.get_storage_root()
            expected = pathlib.Path("/Users/test/Library/Application Support/Cursor")
            assert result == expected
    
    def test_get_storage_root_linux(self):
        """Test getting Cursor storage root on Linux."""
        finder = CursorChatFinder()
        with patch('platform.system', return_value='Linux'), \
             patch('pathlib.Path.home', return_value=pathlib.Path("/home/test")):
            result = finder.get_storage_root()
            expected = pathlib.Path("/home/test/.config/Cursor")
            assert result == expected
    
    def test_get_storage_root_unsupported(self):
        """Test getting storage root on unsupported platform."""
        finder = CursorChatFinder()
        with patch('platform.system', return_value='Unknown'):
            result = finder.get_storage_root()
            assert result is None
    
    def test_find_all_chat_files(self):
        """Test that find_all_chat_files returns a list."""
        finder = CursorChatFinder()
        result = finder.find_all_chat_files()
        assert isinstance(result, list)
        # May be empty if no chats found, or contain items if chats exist
    
    def test_generate_chat_id(self):
        """Test that _generate_chat_id generates a unique ID."""
        finder = CursorChatFinder()
        test_tuple = ("test_composer_id", "/test/db.vscdb", "workspace_id")
        result = finder._generate_chat_id(test_tuple)
        assert isinstance(result, str)
        # Should be deterministic
        result2 = finder._generate_chat_id(test_tuple)
        assert result == result2
        # Invalid input should return empty string
        result3 = finder._generate_chat_id("not_a_tuple")
        assert result3 == ""
    
    def test_extract_metadata_lightweight_not_implemented(self):
        """Test that _extract_metadata_lightweight is not yet implemented."""
        finder = CursorChatFinder()
        result = finder._extract_metadata_lightweight("test_composer_id")
        assert result is None
    
    def test_parse_chat_full_not_implemented(self):
        """Test that _parse_chat_full is not yet implemented."""
        finder = CursorChatFinder()
        result = finder._parse_chat_full("test_composer_id")
        assert result is None
    
    def test_get_chat_metadata_list(self):
        """Test that get_chat_metadata_list returns a list."""
        finder = CursorChatFinder()
        result = finder.get_chat_metadata_list()
        assert isinstance(result, list)
        # May be empty if no chats found, or contain items if chats exist
    
    def test_parse_chat_by_id_not_found(self):
        """Test that parse_chat_by_id raises ValueError for non-existent chat."""
        finder = CursorChatFinder()
        with pytest.raises(ValueError, match="Chat ID 'test_id' not found"):
            finder.parse_chat_by_id("test_id")
    
    def test_extract_chats_not_implemented(self):
        """Test that extract_chats is not yet implemented."""
        finder = CursorChatFinder()
        result = finder.extract_chats()
        assert result is None
    
    def test_export_chats_to_json_not_implemented(self):
        """Test that export_chats_to_json is not yet implemented."""
        finder = CursorChatFinder()
        result = finder.export_chats_to_json()
        assert result is None
    
    def test_get_timezone_offset(self):
        """Test timezone offset from base class."""
        finder = CursorChatFinder()
        offset = finder._get_timezone_offset()
        assert offset.startswith("UTC")
    
    def test_generate_unique_id(self):
        """Test unique ID generation from base class."""
        finder = CursorChatFinder()
        unique_key = "test_composer_123"
        chat_id = finder._generate_unique_id(unique_key)
        
        assert len(chat_id) == 16
        assert isinstance(chat_id, str)
        # Should be deterministic
        chat_id2 = finder._generate_unique_id(unique_key)
        assert chat_id == chat_id2
    
    def test_generate_chat_id_invalid_input(self):
        """Test _generate_chat_id with various invalid inputs."""
        finder = CursorChatFinder()
        # Not a tuple
        assert finder._generate_chat_id("not_a_tuple") == ""
        # Too short tuple
        assert finder._generate_chat_id(("id",)) == ""
        # Empty tuple
        assert finder._generate_chat_id(()) == ""
    
    def test_extract_metadata_lightweight_invalid_input(self):
        """Test _extract_metadata_lightweight with invalid inputs."""
        finder = CursorChatFinder()
        # Not a tuple
        assert finder._extract_metadata_lightweight("not_a_tuple") is None
        # Too short tuple
        assert finder._extract_metadata_lightweight(("id", "path")) is None
        # Non-existent database
        result = finder._extract_metadata_lightweight(("composer_id", "/nonexistent/path.db", "workspace"))
        assert result is None
    
    def test_parse_chat_full_invalid_input(self):
        """Test _parse_chat_full with invalid inputs."""
        finder = CursorChatFinder()
        # Not a tuple
        assert finder._parse_chat_full("not_a_tuple") is None
        # Too short tuple
        assert finder._parse_chat_full(("id", "path")) is None
        # Non-existent database
        result = finder._parse_chat_full(("composer_id", "/nonexistent/path.db", "workspace"))
        assert result is None
    
    def test_get_storage_root_returns_none_for_unsupported_platform(self):
        """Test that get_storage_root returns None for unsupported platform."""
        finder = CursorChatFinder()
        with patch('platform.system', return_value='Unknown'):
            result = finder.get_storage_root()
            assert result is None

