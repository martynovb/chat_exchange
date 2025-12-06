#!/usr/bin/env python3
"""
Unit tests for BaseChatFinder.
"""

import pytest
import pathlib
from unittest.mock import Mock, patch
from base_chat_finder import BaseChatFinder


class ConcreteChatFinder(BaseChatFinder):
    """Concrete implementation for testing abstract base class."""
    
    def get_storage_root(self):
        return pathlib.Path("/test/storage")
    
    def find_all_chat_files(self):
        return [pathlib.Path("/test/file1.json"), pathlib.Path("/test/file2.json")]
    
    def _generate_chat_id(self, file_path_or_key):
        return f"test_id_{file_path_or_key}"
    
    def _extract_metadata_lightweight(self, file_path_or_key):
        return {
            "id": f"test_id_{file_path_or_key}",
            "title": "Test Chat",
            "date": "2024-01-01T00:00:00Z",
            "file_path": str(file_path_or_key)
        }
    
    def _parse_chat_full(self, file_path_or_key):
        return {
            "title": "Test Chat",
            "metadata": {"model": "Test Model"},
            "createdAt": "2024-01-01T00:00:00Z",
            "messages": []
        }


class TestBaseChatFinder:
    """Test cases for BaseChatFinder."""
    
    def test_init(self):
        """Test BaseChatFinder initialization."""
        finder = ConcreteChatFinder()
        assert finder._finder_type == "concrete"
    
    def test_get_timezone_offset(self):
        """Test timezone offset calculation."""
        finder = ConcreteChatFinder()
        offset = finder._get_timezone_offset()
        assert offset.startswith("UTC")
        assert offset[3] in ['+', '-']
        assert offset[4:].isdigit()
    
    def test_generate_unique_id(self):
        """Test unique ID generation."""
        finder = ConcreteChatFinder()
        unique_key = "test_key_123"
        chat_id = finder._generate_unique_id(unique_key)
        
        assert len(chat_id) == 16
        assert isinstance(chat_id, str)
        # Should be deterministic
        chat_id2 = finder._generate_unique_id(unique_key)
        assert chat_id == chat_id2
        
        # Different keys should produce different IDs
        chat_id3 = finder._generate_unique_id("different_key")
        assert chat_id != chat_id3
    
    def test_get_chat_metadata_list_not_implemented(self):
        """Test that get_chat_metadata_list has pass implementation."""
        finder = ConcreteChatFinder()
        result = finder.get_chat_metadata_list()
        assert result is None
    
    def test_parse_chat_by_id_not_implemented(self):
        """Test that parse_chat_by_id has pass implementation."""
        finder = ConcreteChatFinder()
        result = finder.parse_chat_by_id("test_id")
        assert result is None
    
    def test_abstract_methods_must_be_implemented(self):
        """Test that abstract methods must be implemented in subclasses."""
        # Cannot instantiate abstract class directly
        # This will raise TypeError because abstract methods are not implemented
        try:
            finder = BaseChatFinder()
            pytest.fail("Should not be able to instantiate abstract class")
        except TypeError:
            pass  # Expected
    
    def test_finder_type_extraction(self):
        """Test that finder type is correctly extracted from class name."""
        finder = ConcreteChatFinder()
        assert finder._finder_type == "concrete"
        
        # Test with different class name pattern
        class TestChatFinder(BaseChatFinder):
            def get_storage_root(self): pass
            def find_all_chat_files(self): pass
            def _generate_chat_id(self, x): pass
            def _extract_metadata_lightweight(self, x): pass
            def _parse_chat_full(self, x): pass
        
        finder2 = TestChatFinder()
        assert finder2._finder_type == "test"

