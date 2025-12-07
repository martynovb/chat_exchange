#!/usr/bin/env python3
"""
Tests for helper functions in cursor_chats_finder.py
"""

import pytest
import json
import pathlib
import sqlite3
import tempfile
from cursor_chats_finder import (
    j,
    extract_text_from_richtext,
    extract_tool_info,
    cursor_root,
    global_storage_path
)
from unittest.mock import patch


class TestHelperFunctions:
    """Test helper functions in cursor_chats_finder."""
    
    def test_j_function_with_valid_data(self):
        """Test j() helper function with valid JSON data."""
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT PRIMARY KEY, value TEXT)")
                test_data = {"test": "value", "number": 123}
                cur.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                           ("test.key", json.dumps(test_data)))
                con.commit()
                
                result = j(cur, "ItemTable", "test.key")
                assert result == test_data
            finally:
                con.close()
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_j_function_with_invalid_json(self):
        """Test j() helper function with invalid JSON."""
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT PRIMARY KEY, value TEXT)")
                cur.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                           ("test.key", "invalid json"))
                con.commit()
                
                result = j(cur, "ItemTable", "test.key")
                assert result is None
            finally:
                con.close()
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_j_function_with_missing_key(self):
        """Test j() helper function with missing key."""
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT PRIMARY KEY, value TEXT)")
                con.commit()
                
                result = j(cur, "ItemTable", "nonexistent.key")
                assert result is None
            finally:
                con.close()
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_extract_text_from_richtext_string(self):
        """Test extract_text_from_richtext with plain string."""
        result = extract_text_from_richtext("Hello world")
        assert result == "Hello world"
    
    def test_extract_text_from_richtext_json_string(self):
        """Test extract_text_from_richtext with JSON string."""
        richtext_json = json.dumps({"root": {"children": [{"text": "Hello"}]}})
        result = extract_text_from_richtext(richtext_json)
        assert "Hello" in result
    
    def test_extract_text_from_richtext_dict(self):
        """Test extract_text_from_richtext with dict format."""
        richtext = {
            "root": {
                "children": [
                    {"text": "Hello"},
                    {"text": "World"}
                ]
            }
        }
        result = extract_text_from_richtext(richtext)
        assert "Hello" in result
        assert "World" in result
    
    def test_extract_text_from_richtext_nested_children(self):
        """Test extract_text_from_richtext with nested children."""
        richtext = {
            "root": {
                "children": [
                    {
                        "text": "Parent",
                        "children": [
                            {"text": "Child1"},
                            {"text": "Child2"}
                        ]
                    }
                ]
            }
        }
        result = extract_text_from_richtext(richtext)
        assert "Parent" in result
        assert "Child1" in result
        assert "Child2" in result
    
    def test_extract_text_from_richtext_invalid_json_string(self):
        """Test extract_text_from_richtext with invalid JSON string."""
        result = extract_text_from_richtext("not valid json {")
        assert result == "not valid json {"
    
    def test_extract_text_from_richtext_empty(self):
        """Test extract_text_from_richtext with empty/None values."""
        assert extract_text_from_richtext(None) == ""
        assert extract_text_from_richtext("") == ""
        assert extract_text_from_richtext({}) == ""
    
    def test_extract_tool_info_with_tool_former_data(self):
        """Test extract_tool_info with toolFormerData."""
        bubble = {
            "toolFormerData": {
                "name": "test_tool",
                "params": {"arg1": "value1"},
                "result": "Tool output"
            }
        }
        result = extract_tool_info(bubble)
        assert result is not None
        assert result["toolName"] == "test_tool"
        assert result["toolInput"] == {"arg1": "value1"}
        assert result["toolOutput"] == "Tool output"
    
    def test_extract_tool_info_with_string_params(self):
        """Test extract_tool_info with string params."""
        bubble = {
            "toolFormerData": {
                "name": "test_tool",
                "params": '{"arg1": "value1"}',
                "result": "output"
            }
        }
        result = extract_tool_info(bubble)
        assert result["toolInput"] == {"arg1": "value1"}
    
    def test_extract_tool_info_with_invalid_json_params(self):
        """Test extract_tool_info with invalid JSON in params."""
        bubble = {
            "toolFormerData": {
                "name": "test_tool",
                "params": "invalid json {",
                "result": "output"
            }
        }
        result = extract_tool_info(bubble)
        assert result["toolInput"] == {"raw": "invalid json {"}
    
    def test_extract_tool_info_with_raw_args(self):
        """Test extract_tool_info with rawArgs."""
        bubble = {
            "toolFormerData": {
                "name": "test_tool",
                "rawArgs": {"arg1": "value1"},
                "result": "output"
            }
        }
        result = extract_tool_info(bubble)
        assert result["toolInput"] == {"arg1": "value1"}
    
    def test_extract_tool_info_with_dict_result(self):
        """Test extract_tool_info with dict result."""
        bubble = {
            "toolFormerData": {
                "name": "test_tool",
                "result": {"key": "value"}
            }
        }
        result = extract_tool_info(bubble)
        assert isinstance(result["toolOutput"], str)
        assert "key" in result["toolOutput"]
    
    def test_extract_tool_info_with_legacy_fields(self):
        """Test extract_tool_info with legacy tool fields."""
        bubble = {
            "tool": "test_tool",
            "toolName": "test_tool",
            "toolInput": {"arg": "value"},
            "toolOutput": "output"
        }
        result = extract_tool_info(bubble)
        assert result is not None
        assert result["toolName"] == "test_tool"
    
    def test_extract_tool_info_no_tool(self):
        """Test extract_tool_info with no tool data."""
        bubble = {"text": "Just text"}
        result = extract_tool_info(bubble)
        assert result is None
    
    def test_cursor_root_windows(self):
        """Test cursor_root on Windows."""
        with patch('platform.system', return_value='Windows'), \
             patch('pathlib.Path.home', return_value=pathlib.Path("C:/Users/test")):
            result = cursor_root()
            expected = pathlib.Path("C:/Users/test/AppData/Roaming/Cursor")
            assert result == expected
    
    def test_cursor_root_darwin(self):
        """Test cursor_root on macOS."""
        with patch('platform.system', return_value='Darwin'), \
             patch('pathlib.Path.home', return_value=pathlib.Path("/Users/test")):
            result = cursor_root()
            expected = pathlib.Path("/Users/test/Library/Application Support/Cursor")
            assert result == expected
    
    def test_cursor_root_linux(self):
        """Test cursor_root on Linux."""
        with patch('platform.system', return_value='Linux'), \
             patch('pathlib.Path.home', return_value=pathlib.Path("/home/test")):
            result = cursor_root()
            expected = pathlib.Path("/home/test/.config/Cursor")
            assert result == expected
    
    def test_cursor_root_unsupported(self):
        """Test cursor_root on unsupported OS."""
        with patch('platform.system', return_value='Unknown'):
            with pytest.raises(RuntimeError, match="Unsupported OS"):
                cursor_root()
    
    def test_global_storage_path(self):
        """Test global_storage_path function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = pathlib.Path(tmpdir)
            user_dir = base / "User"
            user_dir.mkdir()
            global_storage = user_dir / "globalStorage"
            global_storage.mkdir()
            db_file = global_storage / "state.vscdb"
            db_file.touch()
            
            result = global_storage_path(base)
            assert result == db_file
    
    def test_timestamp_to_iso_milliseconds(self):
        """Test timestamp_to_iso with milliseconds."""
        from cursor_chats_finder import timestamp_to_iso
        import datetime
        
        # Test with milliseconds (> 1e10)
        timestamp_ms = 1609459200000  # 2021-01-01 00:00:00 UTC in milliseconds
        result = timestamp_to_iso(timestamp_ms)
        assert result.endswith('Z')
        assert '2021-01-01' in result
    
    def test_timestamp_to_iso_seconds(self):
        """Test timestamp_to_iso with seconds."""
        from cursor_chats_finder import timestamp_to_iso
        
        # Test with seconds (< 1e10)
        timestamp_sec = 1609459200  # 2021-01-01 00:00:00 UTC in seconds
        result = timestamp_to_iso(timestamp_sec)
        assert result.endswith('Z')
        assert '2021-01-01' in result
    
    def test_timestamp_to_iso_none(self):
        """Test timestamp_to_iso with None."""
        from cursor_chats_finder import timestamp_to_iso
        import datetime
        
        default_time = datetime.datetime(2021, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = timestamp_to_iso(None, default_time)
        assert result.endswith('Z')
        assert '2021-01-01' in result
    
    def test_timestamp_to_iso_invalid(self):
        """Test timestamp_to_iso with invalid type."""
        from cursor_chats_finder import timestamp_to_iso
        import datetime
        
        default_time = datetime.datetime(2021, 1, 1, 12, 0, 0)
        result = timestamp_to_iso("invalid", default_time)
        assert result.endswith('Z')
    
    def test_get_timezone_offset(self):
        """Test get_timezone_offset function."""
        from cursor_chats_finder import get_timezone_offset
        
        result = get_timezone_offset()
        assert result.startswith("UTC")
        assert result[3] in ['+', '-']
    
    def test_transform_chat_to_export_format(self):
        """Test transform_chat_to_export_format function."""
        from cursor_chats_finder import transform_chat_to_export_format
        
        chat = {
            "session": {
                "composerId": "test_composer_123",
                "title": "Test Chat",
                "createdAt": 1609459200000
            },
            "project": {
                "name": "Test Project"
            },
            "messages": [
                {"role": "user", "type": "text", "content": "Hello"},
                {"role": "assistant", "type": "text", "content": "Hi there"}
            ]
        }
        
        result = transform_chat_to_export_format(chat)
        assert "title" in result
        assert result["title"] == "Test Chat"
        assert "metadata" in result
        assert "createdAt" in result
        assert "messages" in result
        assert len(result["messages"]) == 2
    
    def test_transform_chat_to_export_format_no_title(self):
        """Test transform_chat_to_export_format with no title."""
        from cursor_chats_finder import transform_chat_to_export_format
        
        chat = {
            "session": {
                "composerId": "test_composer_123",
                "createdAt": 1609459200000
            },
            "project": {"name": "Test Project"},
            "messages": [{"role": "user", "type": "text", "content": "Hello"}]
        }
        
        result = transform_chat_to_export_format(chat)
        assert "Chat test_com" in result["title"]
    
    def test_transform_chat_to_export_format_with_tool(self):
        """Test transform_chat_to_export_format with tool message."""
        from cursor_chats_finder import transform_chat_to_export_format
        
        chat = {
            "session": {
                "composerId": "test_composer_123",
                "createdAt": 1609459200000
            },
            "project": {"name": "Test Project"},
            "messages": [
                {
                    "role": "assistant",
                    "type": "tool",
                    "content": {
                        "toolName": "test_tool",
                        "toolInput": {"arg": "value"},
                        "toolOutput": "result"
                    }
                }
            ]
        }
        
        result = transform_chat_to_export_format(chat)
        assert len(result["messages"]) == 1
        assert result["messages"][0]["type"] == "tool"
        assert result["messages"][0]["content"]["toolName"] == "test_tool"
    
    def test_transform_chat_to_export_format_skip_invalid_content(self):
        """Test transform_chat_to_export_format skips invalid content."""
        from cursor_chats_finder import transform_chat_to_export_format
        
        chat = {
            "session": {
                "composerId": "test_composer_123",
                "createdAt": 1609459200000
            },
            "project": {"name": "Test Project"},
            "messages": [
                {"role": "user", "type": "text", "content": ""},  # Empty
                {"role": "user", "type": "text", "content": None},  # None
                {"role": "user", "type": "text", "content": 123},  # Not string
                {"role": "user", "type": "text", "content": "Valid"}
            ]
        }
        
        result = transform_chat_to_export_format(chat)
        # Should only have one valid message
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "Valid"
    
    def test_transform_chat_to_export_format_seconds_timestamp(self):
        """Test transform_chat_to_export_format with seconds timestamp."""
        from cursor_chats_finder import transform_chat_to_export_format
        
        chat = {
            "session": {
                "composerId": "test_composer_123",
                "createdAt": 1609459200  # seconds, not milliseconds
            },
            "project": {"name": "Test Project"},
            "messages": [{"role": "user", "type": "text", "content": "Hello"}]
        }
        
        result = transform_chat_to_export_format(chat)
        assert "createdAt" in result
        assert result["createdAt"].endswith('Z')
    
    def test_transform_chat_to_export_format_unknown_project(self):
        """Test transform_chat_to_export_format with unknown project."""
        from cursor_chats_finder import transform_chat_to_export_format
        
        chat = {
            "session": {
                "composerId": "test_composer_123",
                "createdAt": 1609459200000
            },
            "project": {"name": "(unknown)"},
            "messages": [{"role": "user", "type": "text", "content": "Hello"}]
        }
        
        result = transform_chat_to_export_format(chat)
        assert result["metadata"]["Project"] == "Unknown Project"
    
    def test_global_storage_path_not_found(self):
        """Test global_storage_path when not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = pathlib.Path(tmpdir)
            result = global_storage_path(base)
            assert result is None
    
    def test_extract_tool_info_with_non_string_result(self):
        """Test extract_tool_info with non-string result."""
        bubble = {
            "toolFormerData": {
                "name": "test_tool",
                "result": 12345  # Not a string or dict
            }
        }
        result = extract_tool_info(bubble)
        assert result is not None
        assert result["toolOutput"] == "12345"

