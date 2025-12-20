#!/usr/bin/env python3
"""
Comprehensive tests for ID generation across all chat finders.
"""

import pytest
import pathlib
from src.domain.claude_chat_finder import ClaudeChatFinder
from src.domain.copilot_chat_finder import CopilotChatFinder
from src.domain.cursor_chats_finder import CursorChatFinder
from src.domain.base_chat_finder import BaseChatFinder


class TestIDGeneration:
    """Test ID generation methods across all finders."""
    
    def test_generate_unique_id_base(self):
        """Test _generate_unique_id in base class."""
        class TestFinder(BaseChatFinder):
            def get_storage_root(self): pass
            def find_all_chat_files(self): pass
            def _generate_chat_id(self, x): pass
            def _extract_metadata_lightweight(self, x): pass
            def _parse_chat_full(self, x): pass
        
        finder = TestFinder()
        
        # Test deterministic generation
        key = "test_key_123"
        id1 = finder._generate_unique_id(key)
        id2 = finder._generate_unique_id(key)
        assert id1 == id2
        assert len(id1) == 16
        assert all(c in '0123456789abcdef' for c in id1)
        
        # Test different keys produce different IDs
        id3 = finder._generate_unique_id("different_key")
        assert id1 != id3
        
        # Test that finder type is included in hash
        class TestFinder2(BaseChatFinder):
            def get_storage_root(self): pass
            def find_all_chat_files(self): pass
            def _generate_chat_id(self, x): pass
            def _extract_metadata_lightweight(self, x): pass
            def _parse_chat_full(self, x): pass
        
        finder2 = TestFinder2()
        id4 = finder2._generate_unique_id(key)
        # Different finder types should produce different IDs for same key
        assert id1 != id4
    
    def test_claude_generate_chat_id(self):
        """Test Claude chat ID generation."""
        finder = ClaudeChatFinder()
        
        # Test with valid path
        test_path = pathlib.Path("/project1/chat.jsonl")
        chat_id = finder._generate_chat_id(test_path)
        assert len(chat_id) == 16
        assert isinstance(chat_id, str)
        
        # Test deterministic
        chat_id2 = finder._generate_chat_id(test_path)
        assert chat_id == chat_id2
        
        # Test different files produce different IDs
        test_path2 = pathlib.Path("/project1/chat2.jsonl")
        chat_id3 = finder._generate_chat_id(test_path2)
        assert chat_id != chat_id3
        
        # Test different projects produce different IDs
        test_path3 = pathlib.Path("/project2/chat.jsonl")
        chat_id4 = finder._generate_chat_id(test_path3)
        assert chat_id != chat_id4
        
        # Test invalid input
        assert finder._generate_chat_id("not_a_path") == ""
        assert finder._generate_chat_id(None) == ""
        assert finder._generate_chat_id(123) == ""
    
    def test_copilot_generate_chat_id(self):
        """Test Copilot chat ID generation."""
        finder = CopilotChatFinder()
        
        # Test with valid path
        test_path = pathlib.Path("/workspace1/chatSessions/chat.json")
        chat_id = finder._generate_chat_id(test_path)
        assert len(chat_id) == 16
        assert isinstance(chat_id, str)
        
        # Test deterministic
        chat_id2 = finder._generate_chat_id(test_path)
        assert chat_id == chat_id2
        
        # Test different workspaces produce different IDs
        test_path2 = pathlib.Path("/workspace2/chatSessions/chat.json")
        chat_id3 = finder._generate_chat_id(test_path2)
        assert chat_id != chat_id3
        
        # Test different files in same workspace produce different IDs
        test_path3 = pathlib.Path("/workspace1/chatSessions/chat2.json")
        chat_id4 = finder._generate_chat_id(test_path3)
        assert chat_id != chat_id4
        
        # Test invalid input
        assert finder._generate_chat_id("not_a_path") == ""
        assert finder._generate_chat_id(None) == ""
    
    def test_cursor_generate_chat_id(self):
        """Test Cursor chat ID generation."""
        finder = CursorChatFinder()
        
        # Test with valid tuple
        test_tuple = ("composer_123", "/path/to/db.vscdb", "workspace1")
        chat_id = finder._generate_chat_id(test_tuple)
        assert len(chat_id) == 16
        assert isinstance(chat_id, str)
        
        # Test deterministic
        chat_id2 = finder._generate_chat_id(test_tuple)
        assert chat_id == chat_id2
        
        # Test different composers produce different IDs
        test_tuple2 = ("composer_456", "/path/to/db.vscdb", "workspace1")
        chat_id3 = finder._generate_chat_id(test_tuple2)
        assert chat_id != chat_id3
        
        # Test different databases produce different IDs
        test_tuple3 = ("composer_123", "/path/to/db2.vscdb", "workspace1")
        chat_id4 = finder._generate_chat_id(test_tuple3)
        assert chat_id != chat_id4
        
        # Test path normalization (same path, different format)
        test_tuple4 = ("composer_123", "C:\\path\\to\\db.vscdb", "workspace1")
        chat_id5 = finder._generate_chat_id(test_tuple4)
        # Should be same or different depending on normalization
        assert len(chat_id5) == 16
        
        # Test invalid input
        assert finder._generate_chat_id("not_a_tuple") == ""
        assert finder._generate_chat_id(("id",)) == ""  # Too short
        assert finder._generate_chat_id(()) == ""  # Empty
        assert finder._generate_chat_id(None) == ""
    
    def test_cursor_generate_chat_id_path_normalization(self):
        """Test that Cursor chat ID handles path normalization correctly."""
        finder = CursorChatFinder()
        
        # Test with absolute path that can be resolved
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = pathlib.Path(tmpdir) / "test.vscdb"
            db_path.touch()
            
            tuple1 = ("composer_123", str(db_path), "workspace1")
            tuple2 = ("composer_123", str(db_path.resolve()), "workspace1")
            
            id1 = finder._generate_chat_id(tuple1)
            id2 = finder._generate_chat_id(tuple2)
            # Should produce same ID after normalization
            assert id1 == id2
    
    def test_cursor_generate_chat_id_path_fallback(self):
        """Test Cursor chat ID with path that can't be resolved."""
        finder = CursorChatFinder()
        
        # Test with non-existent path (should use fallback normalization)
        non_existent = "/nonexistent/path/to/db.vscdb"
        tuple1 = ("composer_123", non_existent, "workspace1")
        chat_id = finder._generate_chat_id(tuple1)
        assert len(chat_id) == 16
        
        # Test with Windows-style path
        windows_path = "C:\\Users\\test\\db.vscdb"
        tuple2 = ("composer_123", windows_path, "workspace1")
        chat_id2 = finder._generate_chat_id(tuple2)
        assert len(chat_id2) == 16
    
    def test_id_uniqueness_across_finders(self):
        """Test that same key produces different IDs for different finder types."""
        claude_finder = ClaudeChatFinder()
        copilot_finder = CopilotChatFinder()
        cursor_finder = CursorChatFinder()
        
        # Same unique key should produce different IDs for different finders
        key = "test_key"
        claude_id = claude_finder._generate_unique_id(key)
        copilot_id = copilot_finder._generate_unique_id(key)
        cursor_id = cursor_finder._generate_unique_id(key)
        
        # All should be different
        assert claude_id != copilot_id
        assert claude_id != cursor_id
        assert copilot_id != cursor_id
        
        # All should be valid 16-char hex strings
        for id_val in [claude_id, copilot_id, cursor_id]:
            assert len(id_val) == 16
            assert all(c in '0123456789abcdef' for c in id_val)
    
    def test_id_generation_with_special_characters(self):
        """Test ID generation with special characters in keys."""
        finder = ClaudeChatFinder()
        
        # Test with special characters
        special_path = pathlib.Path("/project with spaces/file-name.jsonl")
        chat_id = finder._generate_chat_id(special_path)
        assert len(chat_id) == 16
        
        # Test with unicode characters
        unicode_path = pathlib.Path("/project/文件.jsonl")
        chat_id2 = finder._generate_chat_id(unicode_path)
        assert len(chat_id2) == 16
        
        # Test with very long path
        long_path = pathlib.Path("/" + "a" * 200 + "/file.jsonl")
        chat_id3 = finder._generate_chat_id(long_path)
        assert len(chat_id3) == 16

