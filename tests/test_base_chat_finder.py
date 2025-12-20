#!/usr/bin/env python3
"""
Unit tests for BaseChatFinder.
"""

import pytest
import pathlib
from unittest.mock import Mock, patch
from src.domain.base_chat_finder import BaseChatFinder


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
    
    def test_get_chat_metadata_list(self):
        """Test that get_chat_metadata_list returns list of metadata."""
        finder = ConcreteChatFinder()
        result = finder.get_chat_metadata_list()
        assert isinstance(result, list)
        assert len(result) == 2  # Should have 2 items from find_all_chat_files
        assert all("id" in item and "title" in item for item in result)
    
    def test_get_chat_metadata_list_with_errors(self):
        """Test that get_chat_metadata_list handles errors gracefully."""
        class ErrorChatFinder(ConcreteChatFinder):
            def _extract_metadata_lightweight(self, file_path_or_key):
                # Raise error for first file, return metadata for second
                if str(file_path_or_key).endswith("file1.json"):
                    raise Exception("Test error")
                return super()._extract_metadata_lightweight(file_path_or_key)
        
        finder = ErrorChatFinder()
        result = finder.get_chat_metadata_list()
        # Should still return metadata for files that didn't error
        assert isinstance(result, list)
        assert len(result) == 1  # Only one file should succeed
    
    def test_parse_chat_by_id_not_found(self):
        """Test that parse_chat_by_id raises ValueError for non-existent chat."""
        finder = ConcreteChatFinder()
        with pytest.raises(ValueError, match="Chat ID 'test_id' not found"):
            finder.parse_chat_by_id("test_id")
    
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
    
    def test_get_result_dir(self):
        """Test that _get_result_dir returns correct path."""
        finder = ConcreteChatFinder()
        result = finder._get_result_dir()
        assert isinstance(result, pathlib.Path)
        assert result.name == "results"
    
    def test_get_default_output_path(self):
        """Test that _get_default_output_path creates correct path."""
        finder = ConcreteChatFinder()
        result = finder._get_default_output_path("test_file.json")
        assert isinstance(result, pathlib.Path)
        assert result.name == "test_file.json"
        assert result.parent.name == "results"
    
    def test_ensure_output_dir(self):
        """Test that _ensure_output_dir creates parent directories."""
        finder = ConcreteChatFinder()
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = pathlib.Path(tmpdir) / "subdir" / "file.json"
            finder._ensure_output_dir(output_path)
            assert output_path.parent.exists()
    
    def test_parse_chat_by_id_success(self):
        """Test that parse_chat_by_id returns chat when found."""
        finder = ConcreteChatFinder()
        # The chat ID format is "test_id_<path>"
        test_path = pathlib.Path("/test/file1.json")
        chat_id = finder._generate_chat_id(test_path)
        result = finder.parse_chat_by_id(chat_id)
        assert isinstance(result, dict)
        assert "title" in result
        assert "messages" in result
    
    def test_get_timezone_offset_exception(self):
        """Test _get_timezone_offset exception handling."""
        finder = ConcreteChatFinder()
        with patch('time.timezone', side_effect=Exception("Test error")):
            result = finder._get_timezone_offset()
            assert result == "UTC+0"

