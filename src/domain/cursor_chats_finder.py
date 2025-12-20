#!/usr/bin/env python3
"""
Export Cursor chat data to JSON format.
Extracts all chat conversations from Cursor's storage and exports them to a JSON file.
"""

import json
import logging
import datetime
import os
import platform
import sqlite3
import argparse
import pathlib
import time
from collections import defaultdict
from typing import Dict, Any, Iterable, List, Optional
from pathlib import Path

from .base_chat_finder import BaseChatFinder
from .tool_normalizer import tool_name_normalization

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

################################################################################
# CursorChatFinder class
################################################################################
class CursorChatFinder(BaseChatFinder):
    """Find and extract Cursor chat histories from SQLite databases."""
    
    def __init__(self):
        """Initialize the Cursor chat finder."""
        super().__init__()
    
    def get_storage_root(self) -> Optional[pathlib.Path]:
        """Return the path to Cursor's storage directory.
        
        Returns:
            Path to Cursor storage directory.
        """
        h = pathlib.Path.home()
        s = platform.system()
        if s == "Darwin":
            return h / "Library" / "Application Support" / "Cursor"
        if s == "Windows":
            return h / "AppData" / "Roaming" / "Cursor"
        if s == "Linux":
            return h / ".config" / "Cursor"
        return None
    
    def find_all_chat_files(self) -> List[Any]:
        """Find all chat database files and composer IDs.
        
        Returns:
            List of tuples (composer_id, db_path, workspace_id) for each chat.
        """
        root = self.get_storage_root()
        if not root:
            return []
        
        chat_identifiers = []
        
        # 1. Process workspace DBs
        ws_root = root / "User" / "workspaceStorage"
        if ws_root.exists():
            for folder in ws_root.iterdir():
                db = folder / "state.vscdb"
                if db.exists():
                    ws_id = folder.name
                    try:
                        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                        cur = con.cursor()
                        
                        # Get composer data from ItemTable
                        composer_data = j(cur, "ItemTable", "composer.composerData")
                        if composer_data:
                            for comp in composer_data.get("allComposers", []):
                                comp_id = comp.get("composerId")
                                if comp_id:
                                    chat_identifiers.append((comp_id, str(db), ws_id))
                        
                        # Get chat tabs from chatdata
                        chat_data = j(cur, "ItemTable", "workbench.panel.aichat.view.aichat.chatdata")
                        if chat_data and "tabs" in chat_data:
                            for tab in chat_data.get("tabs", []):
                                tab_id = tab.get("tabId")
                                if tab_id:
                                    chat_identifiers.append((tab_id, str(db), ws_id))
                        
                        con.close()
                    except Exception:
                        continue
        
        # 2. Process global storage
        global_db = global_storage_path(root)
        if global_db:
            try:
                con = sqlite3.connect(f"file:{global_db}?mode=ro", uri=True)
                cur = con.cursor()
                
                # Get composer data from cursorDiskKV
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'")
                if cur.fetchone():
                    cur.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'")
                    for k, v in cur.fetchall():
                        try:
                            composer_id = k.split(":")[1]
                            chat_identifiers.append((composer_id, str(global_db), "(global)"))
                        except Exception:
                            continue
                
                # Get bubbles (which have composer IDs)
                cur.execute("SELECT key FROM cursorDiskKV WHERE key LIKE 'bubbleId:%'")
                for (k,) in cur.fetchall():
                    try:
                        composer_id = k.split(":")[1]
                        # Only add if not already in list
                        if not any(cid == composer_id for cid, _, _ in chat_identifiers):
                            chat_identifiers.append((composer_id, str(global_db), "(global)"))
                    except Exception:
                        continue
                
                # Get chat tabs from global ItemTable
                chat_data = j(cur, "ItemTable", "workbench.panel.aichat.view.aichat.chatdata")
                if chat_data and "tabs" in chat_data:
                    for tab in chat_data.get("tabs", []):
                        tab_id = tab.get("tabId")
                        if tab_id and not any(cid == tab_id for cid, _, _ in chat_identifiers):
                            chat_identifiers.append((tab_id, str(global_db), "(global)"))
                
                con.close()
            except Exception:
                pass
        
        return chat_identifiers
    
    def _generate_chat_id(self, file_path_or_key: Any) -> str:
        """Generate unique chat ID from composer ID or database key.
        
        Args:
            file_path_or_key: Tuple (composer_id, db_path, workspace_id)
            
        Returns:
            Unique chat ID string.
        """
        if not isinstance(file_path_or_key, tuple) or len(file_path_or_key) < 2:
            return ""
        
        composer_id = file_path_or_key[0]
        db_path = file_path_or_key[1]
        
        # Normalize the path to ensure consistent ID generation across different calls
        # This handles Windows path case sensitivity and separator differences
        try:
            path_obj = pathlib.Path(db_path)
            # Resolve to absolute path (normalizes case on Windows, resolves symlinks)
            # This ensures the same file always produces the same normalized path string
            db_path_normalized = str(path_obj.resolve())
        except (OSError, ValueError, TypeError):
            # If path resolution fails (e.g., path doesn't exist), normalize separators
            # This should rarely happen since we only process existing database files
            db_path_normalized = str(pathlib.Path(db_path)).replace('\\', '/')
        
        # Create unique key from composer_id and normalized db_path
        unique_key = f"{composer_id}:{db_path_normalized}"
        
        return self._generate_unique_id(unique_key)
    
    def _extract_metadata_lightweight(self, file_path_or_key: Any) -> Optional[Dict[str, Any]]:
        """Extract minimal metadata without parsing full content.
        
        Args:
            file_path_or_key: Tuple (composer_id, db_path, workspace_id)
            
        Returns:
            Dict with keys: id, title, date, file_path
            Returns None if metadata cannot be extracted.
        """
        if not isinstance(file_path_or_key, tuple) or len(file_path_or_key) < 3:
            return None
        
        composer_id = file_path_or_key[0]
        db_path_str = file_path_or_key[1]
        workspace_id = file_path_or_key[2]
        
        try:
            chat_id = self._generate_chat_id(file_path_or_key)
            db_path = pathlib.Path(db_path_str)
            
            if not db_path.exists():
                return None
            
            title = f"Chat {composer_id[:8]}"
            date_str = ""
            
            # Try to get metadata from database
            try:
                con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                cur = con.cursor()
                
                # Try to get composer data
                if workspace_id != "(global)":
                    composer_data = j(cur, "ItemTable", "composer.composerData")
                    if composer_data:
                        for comp in composer_data.get("allComposers", []):
                            if comp.get("composerId") == composer_id:
                                comp_title = comp.get("name", "")
                                if comp_title:
                                    title = comp_title
                                created_at = comp.get("createdAt")
                                if created_at:
                                    if isinstance(created_at, (int, float)):
                                        if created_at > 1e10:  # milliseconds
                                            dt = datetime.datetime.fromtimestamp(created_at / 1000, tz=datetime.timezone.utc)
                                        else:  # seconds
                                            dt = datetime.datetime.fromtimestamp(created_at, tz=datetime.timezone.utc)
                                        date_str = dt.strftime("%Y-%m-%d")
                                break
                else:
                    # Global storage - check cursorDiskKV
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'")
                    if cur.fetchone():
                        cur.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (f"composerData:{composer_id}",))
                        row = cur.fetchone()
                        if row:
                            try:
                                composer_data = json.loads(row[0])
                                comp_title = composer_data.get("name", "")
                                if comp_title:
                                    title = comp_title
                                created_at = composer_data.get("createdAt")
                                if created_at:
                                    if isinstance(created_at, (int, float)):
                                        if created_at > 1e10:  # milliseconds
                                            dt = datetime.datetime.fromtimestamp(created_at / 1000, tz=datetime.timezone.utc)
                                        else:  # seconds
                                            dt = datetime.datetime.fromtimestamp(created_at, tz=datetime.timezone.utc)
                                        date_str = dt.strftime("%Y-%m-%d")
                            except Exception:
                                pass
                
                con.close()
            except Exception:
                pass
            
            # If no date found, use current date
            if not date_str:
                date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            
            return {
                "id": chat_id,
                "title": title,
                "date": date_str,
                "file_path": db_path_str
            }
        except Exception:
            return None
    
    def _parse_chat_full(self, file_path_or_key: Any) -> Optional[Dict[str, Any]]:
        """Parse full chat content.
        
        Args:
            file_path_or_key: Tuple (composer_id, db_path, workspace_id)
            
        Returns:
            Full chat dict with title, metadata, createdAt, messages.
            Returns None if chat cannot be parsed.
        """
        if not isinstance(file_path_or_key, tuple) or len(file_path_or_key) < 3:
            return None
        
        composer_id = file_path_or_key[0]
        db_path_str = file_path_or_key[1]
        workspace_id = file_path_or_key[2]
        
        try:
            db_path = pathlib.Path(db_path_str)
            if not db_path.exists():
                return None
            
            # Extract messages for this composer
            # Check ALL possible sources regardless of workspace type
            messages = []
            
            # 1. Try to get messages from ItemTable (workspace chats)
            try:
                for bubble_data in iter_chat_from_item_table(db_path):
                    cid = bubble_data["composerId"]
                    if cid == composer_id:
                        role = bubble_data["role"]
                        text = bubble_data["text"]
                        tool_data = bubble_data["tool_data"]
                        timestamp = bubble_data.get("timestamp")
                        
                        if tool_data:
                            messages.append({
                                "role": role,
                                "type": "tool",
                                "content": tool_data,
                                "_timestamp": timestamp
                            })
                        
                        if text:
                            messages.append({
                                "role": role,
                                "type": "text",
                                "content": text,
                                "_timestamp": timestamp
                            })
            except Exception as e:
                logger.debug(f"Error iterating ItemTable: {e}")
            
            # 2. Try to get messages from cursorDiskKV bubbles (global chats, but check for all)
            try:
                for bubble_data in iter_bubbles_from_disk_kv(db_path):
                    cid = bubble_data["composerId"]
                    if cid == composer_id:
                        role = bubble_data["role"]
                        text = bubble_data["text"]
                        tool_data = bubble_data["tool_data"]
                        timestamp = bubble_data.get("timestamp")
                        
                        if tool_data:
                            messages.append({
                                "role": role,
                                "type": "tool",
                                "content": tool_data,
                                "_timestamp": timestamp
                            })
                        
                        if text:
                            messages.append({
                                "role": role,
                                "type": "text",
                                "content": text,
                                "_timestamp": timestamp
                            })
            except Exception as e:
                logger.debug(f"Error iterating cursorDiskKV bubbles: {e}")
            
            # 3. Try composer data from cursorDiskKV
            try:
                for cid, data, _ in iter_composer_data(db_path):
                    if cid == composer_id:
                        # Extract conversation from composer data
                        conversation = data.get("conversation", [])
                        for msg in conversation:
                            msg_type = msg.get("type")
                            if msg_type is None:
                                continue
                            
                            # Type 1 = user, Type 2 = assistant
                            role = "user" if msg_type == 1 else "assistant"
                            content = msg.get("text", "")
                            
                            # Check for tool data
                            tool_info = extract_tool_info(msg)
                            
                            if tool_info:
                                messages.append({
                                    "role": role,
                                    "type": "tool",
                                    "content": tool_info,
                                    "_timestamp": None
                                })
                            
                            if content and isinstance(content, str):
                                messages.append({
                                    "role": role,
                                    "type": "text",
                                    "content": content,
                                    "_timestamp": None
                                })
            except Exception as e:
                logger.debug(f"Error iterating composer data: {e}")
            
            # 4. Also check composer data directly from ItemTable (for workspace chats)
            try:
                con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                cur = con.cursor()
                composer_data = j(cur, "ItemTable", "composer.composerData")
                if composer_data:
                    for comp in composer_data.get("allComposers", []):
                        comp_id = comp.get("composerId")
                        if comp_id == composer_id:
                            comp_messages = comp.get("messages", [])
                            for msg in comp_messages:
                                msg_role = msg.get("role", "")
                                msg_content = msg.get("content", "")
                                if msg_content:
                                    messages.append({
                                        "role": msg_role,
                                        "type": "text",
                                        "content": str(msg_content).strip(),
                                        "_timestamp": None
                                    })
                con.close()
            except Exception as e:
                logger.debug(f"Error checking ItemTable composer data: {e}")
            
            # Sort messages by timestamp
            messages.sort(key=lambda m: m.get("_timestamp") or 0)
            # Remove internal timestamp after sorting
            for msg in messages:
                if "_timestamp" in msg:
                    del msg["_timestamp"]
            
            # Allow chats with no messages - they might have metadata only
            # Return empty messages array instead of None
            
            # Get project info
            project_name = "Unknown Project"
            if workspace_id != "(global)":
                try:
                    proj, _ = workspace_info(db_path)
                    project_name = proj.get("name", "Unknown Project")
                except Exception:
                    pass
            
            # Get metadata
            title = f"Chat {composer_id[:8]}"
            created_at_ms = None
            
            try:
                con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                cur = con.cursor()
                
                if workspace_id != "(global)":
                    composer_data = j(cur, "ItemTable", "composer.composerData")
                    if composer_data:
                        for comp in composer_data.get("allComposers", []):
                            if comp.get("composerId") == composer_id:
                                comp_title = comp.get("name", "")
                                if comp_title:
                                    title = comp_title
                                created_at_ms = comp.get("createdAt")
                                break
                else:
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'")
                    if cur.fetchone():
                        cur.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (f"composerData:{composer_id}",))
                        row = cur.fetchone()
                        if row:
                            try:
                                composer_data = json.loads(row[0])
                                comp_title = composer_data.get("name", "")
                                if comp_title:
                                    title = comp_title
                                created_at_ms = composer_data.get("createdAt")
                            except Exception:
                                pass
                
                con.close()
            except Exception:
                pass
            
            
            # Sort messages by timestamp
            messages.sort(key=lambda m: m.get("_timestamp") or 0)
            # Remove internal timestamp after sorting
            for msg in messages:
                if "_timestamp" in msg:
                    del msg["_timestamp"]
            
            # Build chat dict in the format expected by transform_chat_to_export_format
            chat_dict = {
                "project": {"name": project_name, "rootPath": "(unknown)"},
                "session": {
                    "composerId": composer_id,
                    "title": title,
                    "createdAt": created_at_ms,
                    "lastUpdatedAt": created_at_ms
                },
                "messages": messages,
                "workspace_id": workspace_id
            }
            
            # Transform to export format
            transformed = transform_chat_to_export_format(chat_dict)
            return transformed
        except Exception:
            return None
    
    # get_chat_metadata_list and parse_chat_by_id are inherited from base class
    
    def extract_chats(self) -> list[Dict[str, Any]]:
        """Extract all chats from Cursor storage.
        
        Returns:
            List of chat dictionaries.
        """
        pass
    
    def export_chats_to_json(self, output_file: str = None):
        """Extract all chats and export them to JSON file."""
        pass

################################################################################
# Cursor storage roots (backward compatibility)
################################################################################
def cursor_root() -> pathlib.Path:
    h = pathlib.Path.home()
    s = platform.system()
    if s == "Darwin":   return h / "Library" / "Application Support" / "Cursor"
    if s == "Windows":  return h / "AppData" / "Roaming" / "Cursor"
    if s == "Linux":    return h / ".config" / "Cursor"
    raise RuntimeError(f"Unsupported OS: {s}")

################################################################################
# Helpers
################################################################################
def j(cur: sqlite3.Cursor, table: str, key: str):
    cur.execute(f"SELECT value FROM {table} WHERE key=?", (key,))
    row = cur.fetchone()
    if row:
        try:    return json.loads(row[0])
        except Exception as e: 
            logger.debug(f"Failed to parse JSON for {key}: {e}")
    return None

def extract_text_from_richtext(richtext):
    """Extract plain text from Lexical editor format (richText)."""
    if isinstance(richtext, str):
        try:
            # Try to parse as JSON
            richtext = json.loads(richtext)
        except (json.JSONDecodeError, ValueError):
            # If not JSON, return as-is
            return richtext
    
    if isinstance(richtext, dict):
        # Lexical editor format - extract text from root
        root = richtext.get("root", {})
        if isinstance(root, dict):
            children = root.get("children", [])
            text_parts = []
            for child in children:
                if isinstance(child, dict):
                    text = child.get("text", "")
                    if text:
                        text_parts.append(text)
                    # Also check nested children
                    nested_children = child.get("children", [])
                    for nested in nested_children:
                        if isinstance(nested, dict):
                            nested_text = nested.get("text", "")
                            if nested_text:
                                text_parts.append(nested_text)
            return "\n".join(text_parts)
    
    return str(richtext) if richtext else ""

def _normalize_cursor_tool_input(tool_name: str, normalized_tool_name: str, tool_input: Any) -> Any:
    """
    Normalize tool input for Cursor-specific tools.
    
    Args:
        tool_name: Original tool name from Cursor
        normalized_tool_name: Normalized tool name
        tool_input: Original tool input
        
    Returns:
        Normalized tool input
    """
    # Dispatch to tool-specific normalization functions
    if tool_name == "web_search" or normalized_tool_name == "web_request":
        return _normalize_cursor_web_request_input(tool_input)
    elif normalized_tool_name == "read":
        return _normalize_cursor_read_input(tool_input)
    elif normalized_tool_name == "terminal":
        return _normalize_cursor_terminal_input(tool_input)
    elif normalized_tool_name == "todo":
        return _normalize_cursor_todo_input(tool_input)
    elif normalized_tool_name == "create":
        return _normalize_cursor_create_input(tool_input)
    elif normalized_tool_name == "update":
        return _normalize_cursor_update_input(tool_input)
    elif normalized_tool_name == "delete":
        return _normalize_cursor_delete_input(tool_input)
    
    # General rule: if tool_input is a dict with relativeWorkspacePath, extract it
    # (but skip this for read operations which have special handling)
    if normalized_tool_name != "read":
        if isinstance(tool_input, dict) and "relativeWorkspacePath" in tool_input:
            return tool_input["relativeWorkspacePath"]
    
    return tool_input


def _normalize_cursor_web_request_input(tool_input: Any) -> Any:
    """Normalize web_request tool input for Cursor."""
    result = {}
    if isinstance(tool_input, dict):
        # Extract searchTerm as request
        if "searchTerm" in tool_input:
            result["request"] = tool_input["searchTerm"]
        # Extract url if it exists
        if "url" in tool_input:
            result["url"] = tool_input["url"]
    elif isinstance(tool_input, str):
        # If it's just a string, use it as the request
        result["request"] = tool_input
    
    # Return the result object (only if we have at least a request)
    if "request" in result:
        return result
    return tool_input


def _normalize_cursor_read_input(tool_input: Any) -> Any:
    """Normalize read tool input for Cursor."""
    if isinstance(tool_input, dict):
        # Check if it has codeResults structure (codebase_search result)
        if "codeResults" in tool_input and isinstance(tool_input["codeResults"], list):
            # Extract relativeWorkspacePath from each codeBlock
            file_paths = []
            for code_result in tool_input["codeResults"]:
                if isinstance(code_result, dict):
                    code_block = code_result.get("codeBlock")
                    if isinstance(code_block, dict):
                        relative_path = code_block.get("relativeWorkspacePath")
                        if relative_path:
                            file_paths.append(relative_path)
            if file_paths:
                return file_paths
        
        # Check if it has path (grep/search operations)
        elif "path" in tool_input:
            path_value = tool_input["path"]
            # Return as array
            return [path_value] if path_value else []
        
        # Check if it has targetFile (simple read_file)
        elif "targetFile" in tool_input:
            target_file = tool_input["targetFile"]
            # Return as array
            return [target_file] if target_file else []
    
    # If it's already a string, wrap in array
    elif isinstance(tool_input, str):
        return [tool_input] if tool_input else []
    
    # If it's already a list, return as-is
    elif isinstance(tool_input, list):
        return tool_input
    
    return tool_input


def _normalize_cursor_terminal_input(tool_input: Any) -> Any:
    """Normalize terminal tool input for Cursor."""
    if isinstance(tool_input, dict):
        # Check for parsingResult -> executableCommands structure
        parsing_result = tool_input.get("parsingResult", {})
        if isinstance(parsing_result, dict):
            executable_commands = parsing_result.get("executableCommands", [])
            if isinstance(executable_commands, list) and len(executable_commands) > 0:
                first_command = executable_commands[0]
                if isinstance(first_command, dict):
                    full_text = first_command.get("fullText", "")
                    if full_text:
                        return full_text
        # Fallback: if it's already a string, return as-is
        if isinstance(tool_input, str):
            return tool_input
    return tool_input


def _normalize_cursor_todo_input(tool_input: Any) -> Any:
    """Normalize todo tool input for Cursor."""
    if isinstance(tool_input, dict):
        # Extract overview as description (skip if empty)
        description = tool_input.get("overview", "")
        if not description or not description.strip():
            description = None
        
        # Extract todos array and simplify (skip todos with empty names)
        todos = []
        todos_raw = tool_input.get("todos", [])
        if isinstance(todos_raw, list):
            for todo_item in todos_raw:
                if isinstance(todo_item, dict):
                    todo_name = todo_item.get("content", "")
                    # Skip todos with empty names
                    if todo_name and todo_name.strip():
                        simplified_todo = {
                            "name": todo_name,
                            "status": todo_item.get("status", "")
                        }
                        todos.append(simplified_todo)
        
        # If no description and no valid todos, skip this tool entirely
        if description is None and not todos:
            return None
        
        # Build result, only include description if it's not empty
        result = {"todos": todos}
        if description is not None:
            result["description"] = description
        
        return result
    return tool_input


def _normalize_cursor_create_input(tool_input: Any) -> Any:
    """Normalize create tool input for Cursor."""
    if isinstance(tool_input, dict) and "relativeWorkspacePath" in tool_input:
        return tool_input["relativeWorkspacePath"]
    elif isinstance(tool_input, str):
        return tool_input
    return tool_input


def _normalize_cursor_update_input(tool_input: Any) -> Any:
    """Normalize update tool input for Cursor."""
    # Extract only the file name from path (similar to Claude)
    if isinstance(tool_input, dict) and "relativeWorkspacePath" in tool_input:
        relative_path = tool_input["relativeWorkspacePath"]
        if isinstance(relative_path, str):
            return os.path.basename(relative_path)
    elif isinstance(tool_input, str):
        # If it's already a string, extract filename if it looks like a path
        return os.path.basename(tool_input)
    return tool_input


def _normalize_cursor_delete_input(tool_input: Any) -> Any:
    """Normalize delete tool input for Cursor."""
    return tool_input


def _normalize_cursor_tool_output(tool_name: str, normalized_tool_name: str, tool_output: Any, tool_input: Any = None) -> Any:
    """
    Normalize tool output for Cursor-specific tools.
    
    Args:
        tool_name: Original tool name from Cursor
        normalized_tool_name: Normalized tool name
        tool_output: Original tool output
        
    Returns:
        Normalized tool output
    """
    # Dispatch to tool-specific normalization functions
    if normalized_tool_name == "web_request":
        return _normalize_cursor_web_request_output(tool_output)
    elif normalized_tool_name == "read":
        return _normalize_cursor_read_output(tool_output)
    elif normalized_tool_name == "todo":
        return _normalize_cursor_todo_output(tool_output)
    elif normalized_tool_name == "terminal":
        return _normalize_cursor_terminal_output(tool_output)
    elif normalized_tool_name == "create":
        return _normalize_cursor_create_output(tool_output)
    elif normalized_tool_name == "update":
        return _normalize_cursor_update_output(tool_output, tool_input)
    elif normalized_tool_name == "delete":
        return _normalize_cursor_delete_output(tool_output)
    
    return tool_output


def _normalize_cursor_web_request_output(tool_output: Any) -> Any:
    """Normalize web_request tool output for Cursor."""
    return ""


def _normalize_cursor_read_output(tool_output: Any) -> Any:
    """Normalize read tool output for Cursor."""
    return ""


def _normalize_cursor_todo_output(tool_output: Any) -> Any:
    """Normalize todo tool output for Cursor."""
    return ""


def _normalize_cursor_terminal_output(tool_output: Any) -> Any:
    """Normalize terminal tool output for Cursor."""
    return ""


def _normalize_cursor_create_output(tool_output: Any) -> Any:
    """Normalize create tool output for Cursor."""
    return ""


def _normalize_cursor_update_output(tool_output: Any, tool_input: Any = None) -> Any:
    """Normalize update tool output for Cursor."""
    # Extract diff from Cursor's JSON output structure
    if isinstance(tool_output, str):
        try:
            import json
            parsed = json.loads(tool_output)
            if isinstance(parsed, dict):
                # Extract diffString from diff.chunks[0].diffString
                diff = parsed.get("diff", {})
                if isinstance(diff, dict):
                    chunks = diff.get("chunks", [])
                    if chunks and isinstance(chunks, list) and len(chunks) > 0:
                        first_chunk = chunks[0]
                        if isinstance(first_chunk, dict):
                            diff_string = first_chunk.get("diffString", "")
                            if diff_string:
                                # Clean up the diff string (remove \r\n escape sequences)
                                return diff_string.replace("\\r\\n", "\n").replace("\\n", "\n")
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    
    # If no diff can be extracted, return empty string
    return ""


def _normalize_cursor_delete_output(tool_output: Any) -> Any:
    """Normalize delete tool output for Cursor."""
    return tool_output


def _normalize_cursor_tool_usage(tool_name: str, tool_input: Any, tool_output: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize a complete tool usage entry for Cursor.
    
    Args:
        tool_name: Original tool name from Cursor
        tool_input: Original tool input
        tool_output: Original tool output
        
    Returns:
        Normalized tool usage dict with keys: tool_name, tool_input, tool_output
        Returns None if tool should be skipped
    """
    # Normalize tool name using common function
    normalized_name = tool_name_normalization("cursor", tool_name)
    
    if normalized_name is None:
        return None
    
    # Apply Cursor-specific input/output normalization
    normalized_input = _normalize_cursor_tool_input(tool_name, normalized_name, tool_input)
    
    # If input normalization returns None, skip this tool entirely
    if normalized_input is None:
        return None
    
    normalized_output = _normalize_cursor_tool_output(tool_name, normalized_name, tool_output, tool_input)
    
    return {
        "tool_name": normalized_name,
        "tool_input": normalized_input,
        "tool_output": normalized_output
    }


def extract_tool_info(bubble):
    """Extract tool usage information from a bubble.
    
    Returns dict with tool_name, tool_input, tool_output if tool usage is found, None otherwise.
    """
    # Check toolFormerData first (primary location for tool usage)
    tool_data = bubble.get("toolFormerData")
    if tool_data and isinstance(tool_data, dict):
        tool_name = tool_data.get("name", "")
        if tool_name:
            # Extract tool input
            tool_input = {}
            params = tool_data.get("params")
            raw_args = tool_data.get("rawArgs")
            
            if params:
                if isinstance(params, str):
                    try:
                        tool_input = json.loads(params)
                    except (json.JSONDecodeError, ValueError):
                        tool_input = {"raw": params}
                elif isinstance(params, dict):
                    tool_input = params
            elif raw_args:
                if isinstance(raw_args, str):
                    try:
                        tool_input = json.loads(raw_args)
                    except (json.JSONDecodeError, ValueError):
                        tool_input = {"raw": raw_args}
                elif isinstance(raw_args, dict):
                    tool_input = raw_args
            
            # Extract tool output
            tool_output = tool_data.get("result", "")
            if isinstance(tool_output, dict):
                tool_output = json.dumps(tool_output, indent=2)
            elif not isinstance(tool_output, str):
                tool_output = str(tool_output)
            
            # Normalize tool usage using Cursor-specific logic
            normalized = _normalize_cursor_tool_usage(tool_name, tool_input, tool_output)
            return normalized
    
    # Check for legacy tool fields
    if bubble.get("tool"):
        tool_name = bubble.get("toolName") or bubble.get("tool", "")
        tool_input = bubble.get("toolInput") or bubble.get("tool_input", {})
        tool_output = bubble.get("toolOutput") or bubble.get("tool_output") or bubble.get("tool_response", "")
        
        if tool_name:
            # Normalize tool usage using Cursor-specific logic
            normalized = _normalize_cursor_tool_usage(tool_name, tool_input, tool_output)
            return normalized
    
    return None

def iter_bubbles_from_disk_kv(db: pathlib.Path) -> Iterable[Dict[str, Any]]:
    """Yield message dicts with (composerId, role, content, type, tool_data, timestamp, db_path) from cursorDiskKV table."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = con.cursor()
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'")
        if not cur.fetchone():
            con.close()
            return
        
        cur.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'bubbleId:%'")
    except sqlite3.DatabaseError as e:
        logger.debug(f"Database error with {db}: {e}")
        return
    
    db_path_str = str(db)
    bubbles = []
    
    for k, v in cur.fetchall():
        try:
            if v is None:
                continue
                
            b = json.loads(v)
        except Exception as e:
            logger.debug(f"Failed to parse bubble JSON for key {k}: {e}")
            continue
        
        composerId = k.split(":")[1]  # Format is bubbleId:composerId:bubbleId
        role = "user" if b.get("type") == 1 else "assistant"
        timestamp = b.get("createdAt")
        
        # Extract text content
        text = b.get("text", "")
        if not text and b.get("richText"):
            text = extract_text_from_richtext(b.get("richText"))
        
        # Extract tool information
        tool_info = extract_tool_info(b)
        
        # Skip if no text and no tool data
        if not text and not tool_info:
            continue
        
        bubbles.append({
            "composerId": composerId,
            "role": role,
            "text": text.strip() if text else "",
            "tool_data": tool_info,
            "timestamp": timestamp,
            "db_path": db_path_str
        })
    
    # Sort by timestamp to preserve chronological order
    bubbles.sort(key=lambda x: x.get("timestamp") or 0)
    
    for bubble in bubbles:
        yield bubble
    
    con.close()

def iter_chat_from_item_table(db: pathlib.Path) -> Iterable[Dict[str, Any]]:
    """Yield message dicts with (composerId, role, content, type, tool_data, timestamp, db_path) from ItemTable."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = con.cursor()
        
        bubbles = []
        
        # Try to get chat data from workbench.panel.aichat.view.aichat.chatdata
        chat_data = j(cur, "ItemTable", "workbench.panel.aichat.view.aichat.chatdata")
        if chat_data and "tabs" in chat_data:
            for tab in chat_data.get("tabs", []):
                tab_id = tab.get("tabId", "unknown")
                for bubble in tab.get("bubbles", []):
                    bubble_type = bubble.get("type")
                    if not bubble_type:
                        continue
                    
                    # Extract text from various possible fields
                    text = ""
                    if "text" in bubble:
                        text = bubble["text"]
                    elif "content" in bubble:
                        text = bubble["content"]
                    elif "richText" in bubble:
                        text = extract_text_from_richtext(bubble["richText"])
                    
                    # Extract tool information
                    tool_info = extract_tool_info(bubble)
                    
                    # Skip if no text and no tool data
                    if not text and not tool_info:
                        continue
                    
                    role = "user" if bubble_type == "user" else "assistant"
                    timestamp = bubble.get("createdAt")
                    
                    bubbles.append({
                        "composerId": tab_id,
                        "role": role,
                        "text": text.strip() if text else "",
                        "tool_data": tool_info,
                        "timestamp": timestamp,
                        "db_path": str(db)
                    })
        
        # Check for composer data
        composer_data = j(cur, "ItemTable", "composer.composerData")
        if composer_data:
            for comp in composer_data.get("allComposers", []):
                comp_id = comp.get("composerId", "unknown")
                messages = comp.get("messages", [])
                for msg in messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if content:
                        # For composer messages, we don't have tool data structure
                        bubbles.append({
                            "composerId": comp_id,
                            "role": role,
                            "text": str(content).strip() if content else "",
                            "tool_data": None,
                            "timestamp": None,
                            "db_path": str(db)
                        })
        
        # Also check for aiService entries
        for key_prefix in ["aiService.prompts", "aiService.generations"]:
            try:
                cur.execute("SELECT key, value FROM ItemTable WHERE key LIKE ?", (f"{key_prefix}%",))
                for k, v in cur.fetchall():
                    try:
                        data = json.loads(v)
                        if isinstance(data, list):
                            for item in data:
                                if "id" in item and "text" in item:
                                    role = "user" if "prompts" in key_prefix else "assistant"
                                    bubbles.append({
                                        "composerId": item.get("id", "unknown"),
                                        "role": role,
                                        "text": str(item.get("text", "")).strip(),
                                        "tool_data": None,
                                        "timestamp": None,
                                        "db_path": str(db)
                                    })
                    except json.JSONDecodeError:
                        continue
            except sqlite3.Error:
                continue
        
        # Sort by timestamp to preserve chronological order
        bubbles.sort(key=lambda x: x.get("timestamp") or 0)
        
        for bubble in bubbles:
            yield bubble
    
    except sqlite3.DatabaseError as e:
        logger.debug(f"Database error in ItemTable with {db}: {e}")
        return
    finally:
        if 'con' in locals():
            con.close()

def iter_composer_data(db: pathlib.Path) -> Iterable[tuple[str,dict,str]]:
    """Yield (composerId, composerData, db_path) from cursorDiskKV table."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = con.cursor()
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'")
        if not cur.fetchone():
            con.close()
            return
        
        cur.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'")
    except sqlite3.DatabaseError as e:
        logger.debug(f"Database error with {db}: {e}")
        return
    
    db_path_str = str(db)
    
    for k, v in cur.fetchall():
        try:
            if v is None:
                continue
                
            composer_data = json.loads(v)
            composer_id = k.split(":")[1]
            yield composer_id, composer_data, db_path_str
            
        except Exception as e:
            logger.debug(f"Failed to parse composer data for key {k}: {e}")
            continue
    
    con.close()

################################################################################
# Workspace discovery
################################################################################
def workspaces(base: pathlib.Path):
    ws_root = base / "User" / "workspaceStorage"
    if not ws_root.exists():
        return
    for folder in ws_root.iterdir():
        db = folder / "state.vscdb"
        if db.exists():
            yield folder.name, db

def extract_project_name_from_path(root_path, debug=False):
    """
    Extract a project name from a path, skipping user directories.
    """
    if not root_path or root_path == '/':
        return "Root"
        
    path_parts = [p for p in root_path.split('/') if p]
    
    # Skip common user directory patterns
    project_name = None
    home_dir_patterns = ['Users', 'home']
    
    # Get current username for comparison
    current_username = os.path.basename(os.path.expanduser('~'))
    
    # Find user directory in path
    username_index = -1
    for i, part in enumerate(path_parts):
        if part in home_dir_patterns:
            username_index = i + 1
            break
    
    # If this is just /Users/username with no deeper path, don't use username as project
    if username_index >= 0 and username_index < len(path_parts) and path_parts[username_index] == current_username:
        if len(path_parts) <= username_index + 1:
            return "Home Directory"
    
    if username_index >= 0 and username_index + 1 < len(path_parts):
        # First try specific project directories we know about by name
        known_projects = ['genaisf', 'cursor-view', 'cursor', 'cursor-apps', 'universal-github', 'inquiry']
        
        # Look at the most specific/deepest part of the path first
        for i in range(len(path_parts)-1, username_index, -1):
            if path_parts[i] in known_projects:
                project_name = path_parts[i]
                if debug:
                    logger.debug(f"Found known project name from specific list: {project_name}")
                break
        
        # If no known project found, use the last part of the path as it's likely the project directory
        if not project_name and len(path_parts) > username_index + 1:
            # Check if we have a structure like /Users/username/Documents/codebase/project_name
            if 'Documents' in path_parts and 'codebase' in path_parts:
                doc_index = path_parts.index('Documents')
                codebase_index = path_parts.index('codebase')
                
                # If there's a path component after 'codebase', use that as the project name
                if codebase_index + 1 < len(path_parts):
                    project_name = path_parts[codebase_index + 1]
                    if debug:
                        logger.debug(f"Found project name in Documents/codebase structure: {project_name}")
            
            # If no specific structure found, use the last component of the path
            if not project_name:
                project_name = path_parts[-1]
                if debug:
                    logger.debug(f"Using last path component as project name: {project_name}")
        
        # Skip username as project name
        if project_name == current_username:
            project_name = 'Home Directory'
            if debug:
                logger.debug(f"Avoided using username as project name")
        
        # Skip common project container directories
        project_containers = ['Documents', 'Projects', 'Code', 'workspace', 'repos', 'git', 'src', 'codebase']
        if project_name in project_containers:
            # Don't use container directories as project names
            # Try to use the next component if available
            container_index = path_parts.index(project_name)
            if container_index + 1 < len(path_parts):
                project_name = path_parts[container_index + 1]
                if debug:
                    logger.debug(f"Skipped container dir, using next component as project name: {project_name}")
        
        # If we still don't have a project name, use the first non-system directory after username
        if not project_name and username_index + 1 < len(path_parts):
            system_dirs = ['Library', 'Applications', 'System', 'var', 'opt', 'tmp']
            for i in range(username_index + 1, len(path_parts)):
                if path_parts[i] not in system_dirs and path_parts[i] not in project_containers:
                    project_name = path_parts[i]
                    if debug:
                        logger.debug(f"Using non-system dir as project name: {project_name}")
                    break
    else:
        # If not in a user directory, use the basename
        project_name = path_parts[-1] if path_parts else "Root"
        if debug:
            logger.debug(f"Using basename as project name: {project_name}")
    
    # Final check: don't return username as project name
    if project_name == current_username:
        project_name = "Home Directory"
        if debug:
            logger.debug(f"Final check: replaced username with 'Home Directory'")
    
    return project_name if project_name else "Unknown Project"

def workspace_info(db: pathlib.Path):
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = con.cursor()

        # Get file paths from history entries to extract the project name
        proj = {"name": "(unknown)", "rootPath": "(unknown)"}
        ents = j(cur,"ItemTable","history.entries") or []
        
        # Extract file paths from history entries, stripping the file:/// scheme
        paths = []
        for e in ents:
            resource = e.get("editor", {}).get("resource", "")
            if resource and resource.startswith("file:///"):
                paths.append(resource[len("file:///"):])
        
        # If we found file paths, extract the project name using the longest common prefix
        if paths:
            logger.debug(f"Found {len(paths)} paths in history entries")
            
            # Get the longest common prefix
            common_prefix = os.path.commonprefix(paths)
            logger.debug(f"Common prefix: {common_prefix}")
            
            # Find the last directory separator in the common prefix
            last_separator_index = common_prefix.rfind('/')
            if last_separator_index > 0:
                project_root = common_prefix[:last_separator_index]
                logger.debug(f"Project root from common prefix: {project_root}")
                
                # Extract the project name using the helper function
                project_name = extract_project_name_from_path(project_root, debug=True)
                
                proj = {"name": project_name, "rootPath": "/" + project_root.lstrip('/')}
        
        # Try backup methods if we didn't get a project name
        if proj["name"] == "(unknown)":
            logger.debug("Trying backup methods for project name")
            
            # Check debug.selectedroot as a fallback
            selected_root = j(cur, "ItemTable", "debug.selectedroot")
            if selected_root and isinstance(selected_root, str) and selected_root.startswith("file:///"):
                path = selected_root[len("file:///"):]
                if path:
                    root_path = "/" + path.strip("/")
                    logger.debug(f"Project root from debug.selectedroot: {root_path}")
                    
                    # Extract the project name using the helper function
                    project_name = extract_project_name_from_path(root_path, debug=True)
                    
                    if project_name:
                        proj = {"name": project_name, "rootPath": root_path}

        # composers meta
        comp_meta={}
        cd = j(cur,"ItemTable","composer.composerData") or {}
        for c in cd.get("allComposers",[]):
            comp_meta[c["composerId"]] = {
                "title": c.get("name","(untitled)"),
                "createdAt": c.get("createdAt"),
                "lastUpdatedAt": c.get("lastUpdatedAt")
            }
        
        # Try to get composer info from workbench.panel.aichat.view.aichat.chatdata
        chat_data = j(cur, "ItemTable", "workbench.panel.aichat.view.aichat.chatdata") or {}
        for tab in chat_data.get("tabs", []):
            tab_id = tab.get("tabId")
            if tab_id and tab_id not in comp_meta:
                comp_meta[tab_id] = {
                    "title": f"Chat {tab_id[:8]}",
                    "createdAt": None,
                    "lastUpdatedAt": None
                }
    except sqlite3.DatabaseError as e:
        logger.debug(f"Error getting workspace info from {db}: {e}")
        proj = {"name": "(unknown)", "rootPath": "(unknown)"}
        comp_meta = {}
    finally:
        if 'con' in locals():
            con.close()
            
    return proj, comp_meta

################################################################################
# GlobalStorage
################################################################################
def global_storage_path(base: pathlib.Path) -> pathlib.Path:
    """Return path to the global storage state.vscdb."""
    global_db = base / "User" / "globalStorage" / "state.vscdb"
    if global_db.exists():
        return global_db
    
    # Legacy paths
    g_dirs = [base/"User"/"globalStorage"/"cursor.cursor",
              base/"User"/"globalStorage"/"cursor"]
    for d in g_dirs:
        if d.exists():
            for file in d.glob("*.sqlite"):
                return file
    
    return None

################################################################################
# Extraction pipeline
################################################################################
def extract_chats() -> list[Dict[str,Any]]:
    root = cursor_root()
    logger.debug(f"Using Cursor root: {root}")

    # Diagnostic: Check for AI-related keys in the first workspace
    if os.environ.get("CURSOR_CHAT_DIAGNOSTICS"):
        try:
            first_ws = next(workspaces(root))
            if first_ws:
                ws_id, db = first_ws
                logger.debug(f"\n--- DIAGNOSTICS for workspace {ws_id} ---")
                con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                cur = con.cursor()
                
                # List all tables
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cur.fetchall()]
                logger.debug(f"Tables in workspace DB: {tables}")
                
                # Search for AI-related keys
                if "ItemTable" in tables:
                    for pattern in ['%ai%', '%chat%', '%composer%', '%prompt%', '%generation%']:
                        cur.execute("SELECT key FROM ItemTable WHERE key LIKE ?", (pattern,))
                        keys = [row[0] for row in cur.fetchall()]
                        if keys:
                            logger.debug(f"Keys matching '{pattern}': {keys}")
                
                con.close()
                
            # Check global storage
            global_db = global_storage_path(root)
            if global_db:
                logger.debug(f"\n--- DIAGNOSTICS for global storage ---")
                con = sqlite3.connect(f"file:{global_db}?mode=ro", uri=True)
                cur = con.cursor()
                
                # List all tables
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cur.fetchall()]
                logger.debug(f"Tables in global DB: {tables}")
                
                # Search for AI-related keys in ItemTable
                if "ItemTable" in tables:
                    for pattern in ['%ai%', '%chat%', '%composer%', '%prompt%', '%generation%']:
                        cur.execute("SELECT key FROM ItemTable WHERE key LIKE ?", (pattern,))
                        keys = [row[0] for row in cur.fetchall()]
                        if keys:
                            logger.debug(f"Keys matching '{pattern}': {keys}")
                
                # Check for keys in cursorDiskKV
                if "cursorDiskKV" in tables:
                    cur.execute("SELECT DISTINCT substr(key, 1, instr(key, ':') - 1) FROM cursorDiskKV")
                    prefixes = [row[0] for row in cur.fetchall()]
                    logger.debug(f"Key prefixes in cursorDiskKV: {prefixes}")
                
                con.close()
            
            logger.debug("\n--- END DIAGNOSTICS ---\n")
        except Exception as e:
            logger.debug(f"Error in diagnostics: {e}")

    # map lookups
    ws_proj  : Dict[str,Dict[str,Any]] = {}
    comp_meta: Dict[str,Dict[str,Any]] = {}
    comp2ws  : Dict[str,str]           = {}
    sessions : Dict[str,Dict[str,Any]] = defaultdict(lambda: {"messages":[]})

    # 1. Process workspace DBs first
    logger.debug("Processing workspace databases...")
    ws_count = 0
    for ws_id, db in workspaces(root):
        ws_count += 1
        logger.debug(f"Processing workspace {ws_id} - {db}")
        proj, meta = workspace_info(db)
        ws_proj[ws_id] = proj
        for cid, m in meta.items():
            comp_meta[cid] = m
            comp2ws[cid] = ws_id
        
        # Extract chat data from workspace's state.vscdb
        msg_count = 0
        for bubble_data in iter_chat_from_item_table(db):
            cid = bubble_data["composerId"]
            role = bubble_data["role"]
            text = bubble_data["text"]
            tool_data = bubble_data["tool_data"]
            db_path = bubble_data["db_path"]
            timestamp = bubble_data.get("timestamp")
            
            # Build message(s) - can have both tool and text
            if tool_data:
                # Create tool message
                sessions[cid]["messages"].append({
                    "role": role,
                    "type": "tool",
                    "content": tool_data,
                    "_timestamp": timestamp
                })
            
            if text:
                # Create text message
                sessions[cid]["messages"].append({
                    "role": role,
                    "type": "text",
                    "content": text,
                    "_timestamp": timestamp
                })
            
            # Make sure to record the database path
            if "db_path" not in sessions[cid]:
                sessions[cid]["db_path"] = db_path
            msg_count += 1
            if cid not in comp_meta:
                comp_meta[cid] = {"title": f"Chat {cid[:8]}", "createdAt": None, "lastUpdatedAt": None}
                comp2ws[cid] = ws_id
        
        # Sort messages by timestamp
        for cid in sessions:
            if sessions[cid]["messages"]:
                sessions[cid]["messages"].sort(key=lambda m: m.get("_timestamp") or 0)
                # Remove internal timestamp after sorting
                for msg in sessions[cid]["messages"]:
                    if "_timestamp" in msg:
                        del msg["_timestamp"]
        
        logger.debug(f"  - Extracted {msg_count} messages from workspace {ws_id}")
    
    logger.debug(f"Processed {ws_count} workspaces")

    # 2. Process global storage
    global_db = global_storage_path(root)
    if global_db:
        logger.debug(f"Processing global storage: {global_db}")
        # Extract bubbles from cursorDiskKV
        msg_count = 0
        for bubble_data in iter_bubbles_from_disk_kv(global_db):
            cid = bubble_data["composerId"]
            role = bubble_data["role"]
            text = bubble_data["text"]
            tool_data = bubble_data["tool_data"]
            db_path = bubble_data["db_path"]
            timestamp = bubble_data.get("timestamp")
            
            # Build message(s) - can have both tool and text
            if tool_data:
                # Create tool message
                sessions[cid]["messages"].append({
                    "role": role,
                    "type": "tool",
                    "content": tool_data,
                    "_timestamp": timestamp
                })
            
            if text:
                # Create text message
                sessions[cid]["messages"].append({
                    "role": role,
                    "type": "text",
                    "content": text,
                    "_timestamp": timestamp
                })
            
            # Record the database path
            if "db_path" not in sessions[cid]:
                sessions[cid]["db_path"] = db_path
            msg_count += 1
            if cid not in comp_meta:
                comp_meta[cid] = {"title": f"Chat {cid[:8]}", "createdAt": None, "lastUpdatedAt": None}
                comp2ws[cid] = "(global)"
        
        # Sort messages by timestamp
        for cid in sessions:
            if sessions[cid]["messages"]:
                sessions[cid]["messages"].sort(key=lambda m: m.get("_timestamp") or 0)
                # Remove internal timestamp after sorting
                for msg in sessions[cid]["messages"]:
                    if "_timestamp" in msg:
                        del msg["_timestamp"]
        
        logger.debug(f"  - Extracted {msg_count} messages from global cursorDiskKV bubbles")
        
        # Extract composer data
        comp_count = 0
        for cid, data, db_path in iter_composer_data(global_db):
            if cid not in comp_meta:
                created_at = data.get("createdAt")
                comp_meta[cid] = {
                    "title": f"Chat {cid[:8]}",
                    "createdAt": created_at,
                    "lastUpdatedAt": created_at
                }
                comp2ws[cid] = "(global)"
            
            # Record the database path
            if "db_path" not in sessions[cid]:
                sessions[cid]["db_path"] = db_path
                
            # Extract conversation from composer data
            conversation = data.get("conversation", [])
            if conversation:
                msg_count = 0
                for msg in conversation:
                    msg_type = msg.get("type")
                    if msg_type is None:
                        continue
                    
                    # Type 1 = user, Type 2 = assistant
                    role = "user" if msg_type == 1 else "assistant"
                    content = msg.get("text", "")
                    
                    # Check for tool data in message
                    tool_info = extract_tool_info(msg)
                    
                    if tool_info:
                        # Create tool message
                        sessions[cid]["messages"].append({
                            "role": role,
                            "type": "tool",
                            "content": tool_info
                        })
                        msg_count += 1
                    
                    if content and isinstance(content, str):
                        # Create text message
                        sessions[cid]["messages"].append({
                            "role": role,
                            "type": "text",
                            "content": content
                        })
                        msg_count += 1
                
                if msg_count > 0:
                    comp_count += 1
                    logger.debug(f"  - Added {msg_count} messages from composer {cid[:8]}")
        
        if comp_count > 0:
            logger.debug(f"  - Extracted data from {comp_count} composers in global cursorDiskKV")
        
        # Also try ItemTable in global DB
        try:
            con = sqlite3.connect(f"file:{global_db}?mode=ro", uri=True)
            chat_data = j(con.cursor(), "ItemTable", "workbench.panel.aichat.view.aichat.chatdata")
            if chat_data:
                msg_count = 0
                for tab in chat_data.get("tabs", []):
                    tab_id = tab.get("tabId")
                    if tab_id and tab_id not in comp_meta:
                        comp_meta[tab_id] = {
                            "title": f"Global Chat {tab_id[:8]}",
                            "createdAt": None,
                            "lastUpdatedAt": None
                        }
                        comp2ws[tab_id] = "(global)"
                    
                    for bubble in tab.get("bubbles", []):
                        content = ""
                        if "text" in bubble:
                            content = bubble["text"]
                        elif "content" in bubble:
                            content = bubble["content"]
                        
                        if content and isinstance(content, str):
                            role = "user" if bubble.get("type") == "user" else "assistant"
                            tool_info = extract_tool_info(bubble)
                            
                            if tool_info:
                                sessions[tab_id]["messages"].append({
                                    "role": role,
                                    "type": "tool",
                                    "content": tool_info
                                })
                                msg_count += 1
                            
                            sessions[tab_id]["messages"].append({
                                "role": role,
                                "type": "text",
                                "content": content
                            })
                            msg_count += 1
                logger.debug(f"  - Extracted {msg_count} messages from global chat data")
            con.close()
        except Exception as e:
            logger.debug(f"Error processing global ItemTable: {e}")

    # 3. Build final list
    out = []
    for cid, data in sessions.items():
        if not data["messages"]:
            continue
        ws_id = comp2ws.get(cid, "(unknown)")
        project = ws_proj.get(ws_id, {"name": "(unknown)", "rootPath": "(unknown)"})
        meta = comp_meta.get(cid, {"title": "(untitled)", "createdAt": None, "lastUpdatedAt": None})
        
        # Create the output object with the db_path included
        chat_data = {
            "project": project,
            "session": {"composerId": cid, **meta},
            "messages": data["messages"],
            "workspace_id": ws_id,
        }
        
        # Add the database path if available
        if "db_path" in data:
            chat_data["db_path"] = data["db_path"]
            
        out.append(chat_data)
    
    # Sort by last updated time if available
    out.sort(key=lambda s: s["session"].get("lastUpdatedAt") or 0, reverse=True)
    logger.debug(f"Total chat sessions extracted: {len(out)}")
    return out

################################################################################
# Format conversion
################################################################################
def timestamp_to_iso(timestamp_ms: Any, default_time: datetime.datetime = None) -> str:
    """Convert timestamp (milliseconds) to ISO 8601 format string."""
    if default_time is None:
        default_time = datetime.datetime.now()
    
    if timestamp_ms is None:
        dt = default_time
    elif isinstance(timestamp_ms, (int, float)):
        # Handle both milliseconds and seconds
        if timestamp_ms > 1e10:  # Likely milliseconds
            dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000, tz=datetime.timezone.utc)
        else:  # Likely seconds
            dt = datetime.datetime.fromtimestamp(timestamp_ms, tz=datetime.timezone.utc)
    else:
        dt = default_time.replace(tzinfo=datetime.timezone.utc)
    
    return dt.isoformat().replace('+00:00', 'Z')

def get_timezone_offset() -> str:
    """Get timezone offset string like 'UTC+4'."""
    try:
        # Get local timezone offset
        offset_seconds = time.timezone if (time.daylight == 0) else time.altzone
        offset_hours = abs(offset_seconds) // 3600
        sign = '+' if offset_seconds <= 0 else '-'
        return f"UTC{sign}{offset_hours}"
    except:
        return "UTC+4"  # Default fallback

def transform_chat_to_export_format(chat: Dict[str, Any]) -> Dict[str, Any]:
    """Transform extracted chat data to the requested export format."""
    session = chat.get("session", {})
    project = chat.get("project", {})
    messages = chat.get("messages", [])
    
    # Get title
    title = session.get("title", "(untitled)")
    if title == "(untitled)" or not title:
        composer_id = session.get("composerId", "unknown")
        title = f"Chat {composer_id[:8]}"
    
    # Get createdAt timestamp
    created_at_ms = session.get("createdAt")
    created_at_iso = timestamp_to_iso(created_at_ms)
    
    # Get project name
    project_name = project.get("name", "Unknown Project")
    if project_name in ["(unknown)", "Unknown Project"]:
        project_name = "Unknown Project"
    
    # Build metadata
    metadata = {
        "model": "Claude Sonnet 4.0",  # Default, as we don't have model info in extraction
        "chat_timezone": get_timezone_offset(),
        "Project": project_name
    }
    
    # Transform messages
    transformed_messages = []
    base_time = None
    
    # If we have createdAt, use it as base time
    if created_at_ms:
        if isinstance(created_at_ms, (int, float)):
            if created_at_ms > 1e10:  # milliseconds
                base_time = datetime.datetime.fromtimestamp(created_at_ms / 1000, tz=datetime.timezone.utc)
            else:  # seconds
                base_time = datetime.datetime.fromtimestamp(created_at_ms, tz=datetime.timezone.utc)
    
    if base_time is None:
        base_time = datetime.datetime.now(tz=datetime.timezone.utc)
    
    # Generate timestamps for messages (estimate based on order)
    # Assume ~15 seconds between messages
    message_interval = datetime.timedelta(seconds=15)
    current_time = base_time
    
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        msg_type = msg.get("type", "text")
        content = msg.get("content", "")
        
        # Generate timestamp for this message
        msg_timestamp = timestamp_to_iso(None, current_time)
        
        # Build message object based on type
        if msg_type == "tool" and isinstance(content, dict):
            # Tool message - use normalized format
            # Handle both snake_case and camelCase formats
            tool_name = content.get("tool_name") or content.get("toolName", "unknown")
            tool_input = content.get("tool_input") or content.get("toolInput", {})
            tool_output = content.get("tool_output") or content.get("toolOutput", "")
            
            # If we have a tool name (not "unknown"), normalize it
            if tool_name != "unknown":
                normalized = _normalize_cursor_tool_usage(tool_name, tool_input, tool_output)
                if normalized:
                    tool_name = normalized["tool_name"]
                    tool_input = normalized["tool_input"]
                    tool_output = normalized["tool_output"]
            
            message_obj = {
                "role": role,
                "type": "tool",
                "content": {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_output": tool_output
                },
                "timestamp": msg_timestamp
            }
        else:
            # Text message
            if not content or not isinstance(content, str):
                # Skip if content is invalid
                continue
            
            message_obj = {
                "role": role,
                "type": "text",
                "content": content,
                "timestamp": msg_timestamp
            }
        
        transformed_messages.append(message_obj)
        
        # Increment time for next message
        current_time += message_interval
    
    return {
        "title": title,
        "metadata": metadata,
        "createdAt": created_at_iso,
        "messages": transformed_messages
    }

def export_chats_to_json(output_file: str = None):
    """Extract all chats and export them to JSON file."""
    try:
        # Use base class methods for result folder logic
        finder = CursorChatFinder()
        
        # Default to result folder if not specified
        if output_file is None:
            output_path = finder._get_default_output_path("cursor_chats_export.json")
            output_file = str(output_path)
        else:
            # Ensure parent directory exists
            output_path = pathlib.Path(output_file)
            finder._ensure_output_dir(output_path)
        
        logger.info("Starting chat extraction...")
        chats = extract_chats()
        logger.info(f"Extracted {len(chats)} chat sessions")
        
        if not chats:
            logger.warning("No chats found to export")
            return
        
        # Transform chats to export format
        logger.info("Transforming chats to export format...")
        exported_chats = []
        for chat in chats:
            try:
                transformed = transform_chat_to_export_format(chat)
                exported_chats.append(transformed)
            except Exception as e:
                logger.error(f"Error transforming chat {chat.get('session', {}).get('composerId', 'unknown')}: {e}")
                continue
        
        # Write to JSON file
        logger.info(f"Writing {len(exported_chats)} chats to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(exported_chats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully exported {len(exported_chats)} chats to {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error exporting chats: {e}", exc_info=True)
        raise

################################################################################
# Main execution
################################################################################
def main():
    parser = argparse.ArgumentParser(description='Export Cursor chat data to JSON')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output JSON file path (default: result/cursor_chats_export.json)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        output_file = export_chats_to_json(args.output)
        print(f"\n✓ Successfully exported chats to: {output_file}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Export Cursor chat data to JSON')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output JSON file for exporting all chats (default: result/cursor_chats_export.json)')
    parser.add_argument('--export', type=str, default=None,
                       help='Export a specific chat by ID')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    finder = CursorChatFinder()
    
    # Two-step approach: --export=chat_id exports specific chat
    if args.export:
        try:
            chat_data = finder.parse_chat_by_id(args.export)
            # Save single chat to results folder
            output_path = finder._get_default_output_path(f"cursor_chat_{args.export[:8]}.json")
            output_path.write_text(
                json.dumps(chat_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"Exported chat {args.export} to {output_path}")
        except ValueError as e:
            print(f"Error: {e}")
            exit(1)
    # List mode: no arguments prints all chats with IDs
    elif args.output is None:
        metadata_list = finder.get_chat_metadata_list()
        print(f"Found {len(metadata_list)} chats:")
        for chat in metadata_list:
            print(f"  {chat['id']} - \"{chat['title']}\" ({chat['date']})")
    # Export all mode: --output specified exports all chats
    else:
        try:
            output_file = export_chats_to_json(args.output)
            print(f"\n✓ Successfully exported chats to: {output_file}")
        except Exception as e:
            print(f"\n✗ Error: {e}")
            exit(1)
