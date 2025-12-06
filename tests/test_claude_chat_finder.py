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
from claude_chat_finder import ClaudeChatFinder


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
    
    def test_generate_chat_id_not_implemented(self):
        """Test that _generate_chat_id is not yet implemented."""
        finder = ClaudeChatFinder()
        # Method exists but has pass implementation, so returns None
        result = finder._generate_chat_id(pathlib.Path("/test"))
        assert result is None
    
    def test_extract_metadata_lightweight_not_implemented(self):
        """Test that _extract_metadata_lightweight is not yet implemented."""
        finder = ClaudeChatFinder()
        result = finder._extract_metadata_lightweight(pathlib.Path("/test"))
        assert result is None
    
    def test_parse_chat_full_not_implemented(self):
        """Test that _parse_chat_full is not yet implemented."""
        finder = ClaudeChatFinder()
        result = finder._parse_chat_full(pathlib.Path("/test"))
        assert result is None
    
    def test_get_chat_metadata_list_not_implemented(self):
        """Test that get_chat_metadata_list is not yet implemented."""
        finder = ClaudeChatFinder()
        result = finder.get_chat_metadata_list()
        assert result is None
    
    def test_parse_chat_by_id_not_implemented(self):
        """Test that parse_chat_by_id is not yet implemented."""
        finder = ClaudeChatFinder()
        result = finder.parse_chat_by_id("test_id")
        assert result is None
    
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

