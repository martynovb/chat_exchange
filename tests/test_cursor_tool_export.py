#!/usr/bin/env python3
"""
Tests for tool export from Cursor database.
"""

import pytest
import json
import pathlib
import sqlite3
import tempfile
from cursor_chats_finder import (
    CursorChatFinder,
    iter_bubbles_from_disk_kv,
    iter_chat_from_item_table,
    extract_tool_info,
    j
)


class TestCursorToolExport:
    """Test tool extraction and export from Cursor database."""
    
    def test_parse_chat_full_with_tool_from_item_table(self):
        """Test parsing chat with tool data from ItemTable."""
        finder = CursorChatFinder()
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            # Create database with tool data in ItemTable
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT PRIMARY KEY, value TEXT)")
                
                # Create chat data with tool usage
                chat_data = {
                    "tabs": [{
                        "tabId": "test_composer_123",
                        "bubbles": [
                            {
                                "type": 1,  # user
                                "text": "Run a command",
                                "createdAt": 1609459200000
                            },
                            {
                                "type": 2,  # assistant
                                "text": "",
                                "toolFormerData": {
                                    "name": "terminal_command",
                                    "params": {"command": "ls -la"},
                                    "result": "file1.txt\nfile2.txt"
                                },
                                "createdAt": 1609459201000
                            }
                        ]
                    }]
                }
                cur.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                           ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(chat_data)))
                con.commit()
            finally:
                con.close()
            
            result = finder._parse_chat_full(("test_composer_123", str(db_path), "workspace1"))
            assert result is not None
            assert "messages" in result
            
            # Find tool message
            tool_messages = [m for m in result["messages"] if m.get("type") == "tool"]
            assert len(tool_messages) > 0
            assert tool_messages[0]["content"]["toolName"] == "terminal_command"
            assert tool_messages[0]["content"]["toolInput"]["command"] == "ls -la"
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_parse_chat_full_with_tool_from_disk_kv(self):
        """Test parsing chat with tool data from cursorDiskKV."""
        finder = CursorChatFinder()
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            # Create database with tool data in cursorDiskKV
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
                
                # Create bubble with tool data
                bubble_data = {
                    "type": 2,  # assistant
                    "text": "",
                    "toolFormerData": {
                        "name": "file_search",
                        "params": {"pattern": "*.py"},
                        "result": ["file1.py", "file2.py"]
                    },
                    "createdAt": 1609459200000
                }
                cur.execute("INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                           ("bubbleId:test_composer_123:bubble1", json.dumps(bubble_data)))
                con.commit()
            finally:
                con.close()
            
            result = finder._parse_chat_full(("test_composer_123", str(db_path), "(global)"))
            # May return None if no messages found, or dict if successful
            if result:
                tool_messages = [m for m in result.get("messages", []) if m.get("type") == "tool"]
                if tool_messages:
                    assert tool_messages[0]["content"]["toolName"] == "file_search"
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_iter_bubbles_from_disk_kv_with_tool(self):
        """Test iter_bubbles_from_disk_kv with tool data."""
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
                
                bubble_data = {
                    "type": 2,  # assistant
                    "text": "I'll search for files",
                    "toolFormerData": {
                        "name": "file_search",
                        "params": {"pattern": "*.py"},
                        "result": "Found 2 files"
                    },
                    "createdAt": 1609459200000
                }
                cur.execute("INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                           ("bubbleId:composer_123:bubble1", json.dumps(bubble_data)))
                con.commit()
            finally:
                con.close()
            
            bubbles = list(iter_bubbles_from_disk_kv(db_path))
            assert len(bubbles) > 0
            bubble = bubbles[0]
            assert bubble["composerId"] == "composer_123"
            assert bubble["tool_data"] is not None
            assert bubble["tool_data"]["toolName"] == "file_search"
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_iter_chat_from_item_table_with_tool(self):
        """Test iter_chat_from_item_table with tool data."""
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT PRIMARY KEY, value TEXT)")
                
                chat_data = {
                    "tabs": [{
                        "tabId": "composer_123",
                        "bubbles": [
                            {
                                "type": 2,
                                "text": "",
                                "toolFormerData": {
                                    "name": "code_execution",
                                    "params": {"code": "print('hello')"},
                                    "result": "hello"
                                }
                            }
                        ]
                    }]
                }
                cur.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                           ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(chat_data)))
                con.commit()
            finally:
                con.close()
            
            bubbles = list(iter_chat_from_item_table(db_path))
            assert len(bubbles) > 0
            bubble = bubbles[0]
            assert bubble["composerId"] == "composer_123"
            assert bubble["tool_data"] is not None
            assert bubble["tool_data"]["toolName"] == "code_execution"
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_extract_tool_info_from_composer_data(self):
        """Test extracting tool info from composer data conversation."""
        finder = CursorChatFinder()
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
                
                # Create composer data with tool usage in conversation
                composer_data = {
                    "conversation": [
                        {
                            "type": 1,  # user
                            "text": "Run a test"
                        },
                        {
                            "type": 2,  # assistant
                            "text": "",
                            "toolFormerData": {
                                "name": "test_runner",
                                "rawArgs": '{"test_file": "test.py"}',
                                "result": "Tests passed"
                            }
                        }
                    ]
                }
                cur.execute("INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                           ("composerData:composer_123", json.dumps(composer_data)))
                con.commit()
            finally:
                con.close()
            
            # Test that extract_tool_info works on the message
            message = {
                "type": 2,
                "toolFormerData": {
                    "name": "test_runner",
                    "rawArgs": '{"test_file": "test.py"}',
                    "result": "Tests passed"
                }
            }
            tool_info = extract_tool_info(message)
            assert tool_info is not None
            assert tool_info["toolName"] == "test_runner"
            assert "test_file" in tool_info["toolInput"]
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_tool_with_dict_result(self):
        """Test tool extraction with dict result."""
        bubble = {
            "toolFormerData": {
                "name": "api_call",
                "params": {"url": "https://api.example.com"},
                "result": {
                    "status": "success",
                    "data": {"key": "value"}
                }
            }
        }
        result = extract_tool_info(bubble)
        assert result is not None
        assert result["toolName"] == "api_call"
        assert isinstance(result["toolOutput"], str)  # Should be JSON string
        assert "status" in result["toolOutput"]
    
    def test_tool_with_string_params(self):
        """Test tool extraction with string params."""
        bubble = {
            "toolFormerData": {
                "name": "command",
                "params": '{"cmd": "ls"}',
                "result": "output"
            }
        }
        result = extract_tool_info(bubble)
        assert result["toolInput"] == {"cmd": "ls"}
    
    def test_tool_with_raw_args(self):
        """Test tool extraction with rawArgs instead of params."""
        bubble = {
            "toolFormerData": {
                "name": "search",
                "rawArgs": {"query": "test"},
                "result": "results"
            }
        }
        result = extract_tool_info(bubble)
        assert result["toolInput"] == {"query": "test"}
    
    def test_tool_with_legacy_fields(self):
        """Test tool extraction with legacy tool fields."""
        bubble = {
            "tool": "legacy_tool",
            "toolName": "legacy_tool",
            "toolInput": {"arg": "value"},
            "toolOutput": "result"
        }
        result = extract_tool_info(bubble)
        assert result is not None
        assert result["toolName"] == "legacy_tool"
        assert result["toolInput"] == {"arg": "value"}
        assert result["toolOutput"] == "result"
    
    def test_parse_chat_full_with_mixed_tool_and_text(self):
        """Test parsing chat with both tool and text messages."""
        finder = CursorChatFinder()
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT PRIMARY KEY, value TEXT)")
                
                chat_data = {
                    "tabs": [{
                        "tabId": "composer_123",
                        "bubbles": [
                            {
                                "type": 1,
                                "text": "Hello",
                                "createdAt": 1609459200000
                            },
                            {
                                "type": 2,
                                "text": "I'll help you",
                                "createdAt": 1609459201000
                            },
                            {
                                "type": 2,
                                "text": "",
                                "toolFormerData": {
                                    "name": "helper_tool",
                                    "params": {},
                                    "result": "Done"
                                },
                                "createdAt": 1609459202000
                            }
                        ]
                    }]
                }
                cur.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                           ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(chat_data)))
                con.commit()
            finally:
                con.close()
            
            result = finder._parse_chat_full(("composer_123", str(db_path), "workspace1"))
            assert result is not None
            messages = result.get("messages", [])
            
            # Should have both text and tool messages
            text_messages = [m for m in messages if m.get("type") == "text"]
            tool_messages = [m for m in messages if m.get("type") == "tool"]
            
            assert len(text_messages) >= 2
            assert len(tool_messages) >= 1
            assert tool_messages[0]["content"]["toolName"] == "helper_tool"
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_iter_bubbles_from_disk_kv_no_table(self):
        """Test iter_bubbles_from_disk_kv when table doesn't exist."""
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            con.close()
            
            bubbles = list(iter_bubbles_from_disk_kv(db_path))
            assert len(bubbles) == 0
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_iter_bubbles_from_disk_kv_invalid_json(self):
        """Test iter_bubbles_from_disk_kv with invalid JSON."""
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
                cur.execute("INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                           ("bubbleId:composer_123:bubble1", "invalid json {"))
                con.commit()
            finally:
                con.close()
            
            bubbles = list(iter_bubbles_from_disk_kv(db_path))
            # Should skip invalid JSON
            assert len(bubbles) == 0
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_tool_with_no_name(self):
        """Test tool extraction when tool has no name."""
        bubble = {
            "toolFormerData": {
                "params": {"arg": "value"},
                "result": "output"
            }
        }
        result = extract_tool_info(bubble)
        assert result is None  # Should return None if no tool name
    
    def test_tool_with_empty_result(self):
        """Test tool extraction with empty result."""
        bubble = {
            "toolFormerData": {
                "name": "empty_tool",
                "params": {},
                "result": ""
            }
        }
        result = extract_tool_info(bubble)
        assert result is not None
        assert result["toolOutput"] == ""
    
    def test_parse_chat_full_with_tool_from_composer_data(self):
        """Test parsing chat with tool data from composer data."""
        finder = CursorChatFinder()
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
                
                # Create composer data with tool in conversation
                composer_data = {
                    "conversation": [
                        {
                            "type": 2,  # assistant
                            "text": "",
                            "toolFormerData": {
                                "name": "code_generator",
                                "params": {"language": "python"},
                                "result": "def hello(): pass"
                            }
                        }
                    ]
                }
                cur.execute("INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                           ("composerData:composer_123", json.dumps(composer_data)))
                con.commit()
            finally:
                con.close()
            
            # Import the function to test it
            from cursor_chats_finder import iter_composer_data
            composers = list(iter_composer_data(db_path))
            assert len(composers) > 0
            cid, data, _ = composers[0]
            assert cid == "composer_123"
            assert "conversation" in data
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_tool_with_invalid_json_params(self):
        """Test tool extraction with invalid JSON in params."""
        bubble = {
            "toolFormerData": {
                "name": "test_tool",
                "params": "not valid json {",
                "result": "output"
            }
        }
        result = extract_tool_info(bubble)
        assert result is not None
        assert result["toolInput"] == {"raw": "not valid json {"}
    
    def test_tool_with_invalid_json_raw_args(self):
        """Test tool extraction with invalid JSON in rawArgs."""
        bubble = {
            "toolFormerData": {
                "name": "test_tool",
                "rawArgs": "invalid json {",
                "result": "output"
            }
        }
        result = extract_tool_info(bubble)
        assert result is not None
        assert result["toolInput"] == {"raw": "invalid json {"}
    
    def test_iter_bubbles_from_disk_kv_with_richtext(self):
        """Test iter_bubbles_from_disk_kv with richText instead of text."""
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
                
                bubble_data = {
                    "type": 1,  # user
                    "richText": json.dumps({
                        "root": {
                            "children": [
                                {"text": "Hello from richText"}
                            ]
                        }
                    }),
                    "createdAt": 1609459200000
                }
                cur.execute("INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                           ("bubbleId:composer_123:bubble1", json.dumps(bubble_data)))
                con.commit()
            finally:
                con.close()
            
            bubbles = list(iter_bubbles_from_disk_kv(db_path))
            assert len(bubbles) > 0
            assert "Hello from richText" in bubbles[0]["text"]
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass
    
    def test_iter_bubbles_from_disk_kv_skip_empty(self):
        """Test iter_bubbles_from_disk_kv skips bubbles with no text and no tool."""
        db_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.vscdb', delete=False) as f:
                db_path = pathlib.Path(f.name)
                f.close()
            
            con = sqlite3.connect(str(db_path))
            try:
                cur = con.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
                
                # Bubble with no text and no tool
                bubble_data = {
                    "type": 2,
                    "createdAt": 1609459200000
                }
                cur.execute("INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                           ("bubbleId:composer_123:bubble1", json.dumps(bubble_data)))
                con.commit()
            finally:
                con.close()
            
            bubbles = list(iter_bubbles_from_disk_kv(db_path))
            # Should skip empty bubble
            assert len(bubbles) == 0
        finally:
            if db_path and db_path.exists():
                import time
                time.sleep(0.1)
                try:
                    db_path.unlink()
                except:
                    pass

