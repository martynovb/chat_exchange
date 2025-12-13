#!/usr/bin/env python3
"""
Find and extract all Claude Code chat histories from a user's system.

Info:
Claude Code stores chat transcripts as JSONL (JSON Lines) files in the
~/.claude/projects/ directory. Each project folder contains transcript files
where each line is a separate JSON object representing messages, tool usage,
and other conversation data.

The storage directory is located at:
    C:/Users/<username>/.claude/projects on Windows;
    /Users/<username>/.claude/projects on macOS;
    /home/<username>/.claude/projects on Linux.

Each project subfolder contains JSONL transcript files that can be parsed
line-by-line to extract the conversation history.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
import datetime
from typing import List, Optional, Dict, Any

from base_chat_finder import BaseChatFinder
from tool_normalizer import tool_name_normalization

"""This module exports Claude chat JSON/JSONL files in a standardized format."""


class ClaudeChatFinder(BaseChatFinder):
    """Find and extract Claude Code chat histories."""

    def get_storage_root(self) -> Optional[pathlib.Path]:
        """Return the path to Claude Code's `projects` directory.

        Returns the standard ~/.claude/projects location for all platforms.
        """
        home = pathlib.Path.home()
        claude_projects = home / ".claude" / "projects"

        if claude_projects.exists():
            return claude_projects

        # Return the expected path even if it doesn't exist
        return claude_projects

    def _parse_jsonl_file(self, file_path: pathlib.Path) -> List[Dict[str, Any]]:
        """Parse a JSONL file and return a list of JSON objects.

        JSONL format has one JSON object per line.
        """
        objects = []
        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        objects.append(obj)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
        except Exception:
            return []

        return objects

    def find_all_chat_files(self) -> List[pathlib.Path]:
        """Find all JSONL and JSON chat files in ~/.claude/projects.
        
        Returns:
            List of paths to all chat files (both .jsonl and .json).
        """
        projects_root = self.get_storage_root()
        if not projects_root or not projects_root.exists():
            return []

        chat_files: List[pathlib.Path] = []

        for project_dir in projects_root.iterdir():
            if not project_dir.is_dir():
                continue

            # Skip cache directories
            if project_dir.name.startswith("."):
                continue

            # Find all JSONL transcript files
            chat_files.extend(sorted(project_dir.glob("*.jsonl")))

            # Also check for plain JSON files that might contain chat data
            for json_file in project_dir.glob("*.json"):
                # Skip cache files and metadata
                if json_file.parent.name == ".cache" or json_file.name.startswith("."):
                    continue
                chat_files.append(json_file)

        return sorted(chat_files)

    def _generate_chat_id(self, file_path_or_key: Any) -> str:
        """Generate unique chat ID from file path or database key.
        
        Args:
            file_path_or_key: File path (pathlib.Path) for Claude chats
            
        Returns:
            Unique chat ID string.
        """
        if not isinstance(file_path_or_key, pathlib.Path):
            return ""
        
        # Create unique key from project name and file name
        project_name = file_path_or_key.parent.name
        file_name = file_path_or_key.name
        unique_key = f"{project_name}/{file_name}"
        
        return self._generate_unique_id(unique_key)

    def _extract_metadata_lightweight(self, file_path_or_key: Any) -> Optional[Dict[str, Any]]:
        """Extract minimal metadata without parsing full content.
        
        Args:
            file_path_or_key: File path (pathlib.Path) to JSONL/JSON file
            
        Returns:
            Dict with keys: id, title, date, file_path
            Returns None if metadata cannot be extracted.
        """
        if not isinstance(file_path_or_key, pathlib.Path):
            return None
        
        try:
            chat_id = self._generate_chat_id(file_path_or_key)
            
            # Read first few lines to extract title and timestamp
            title = "Untitled Conversation"
            date_str = ""
            
            if file_path_or_key.suffix == ".jsonl":
                # Read first few lines of JSONL
                with file_path_or_key.open("r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        if i >= 10:  # Only read first 10 lines
                            break
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            # Look for user message to extract title
                            if obj.get("type") == "user" and title == "Untitled Conversation":
                                message = obj.get("message", {})
                                content = message.get("content", "")
                                text_content = self._extract_text_content(content)
                                if text_content.strip():
                                    title = text_content.strip()[:100]
                                    if len(text_content) > 100:
                                        title += "..."
                            
                            # Get first timestamp
                            if not date_str and obj.get("timestamp"):
                                timestamp = obj.get("timestamp")
                                dt = self._parse_iso_timestamp(timestamp)
                                if dt:
                                    date_str = dt.strftime("%Y-%m-%d")
                        except json.JSONDecodeError:
                            continue
            else:
                # Read JSON file (but don't parse fully)
                try:
                    raw_data = json.loads(file_path_or_key.read_text(encoding="utf-8"))
                    if isinstance(raw_data, dict):
                        raw_data = [raw_data]
                    
                    # Extract from first entry
                    if raw_data:
                        first_entry = raw_data[0]
                        if first_entry.get("type") == "user":
                            message = first_entry.get("message", {})
                            content = message.get("content", "")
                            text_content = self._extract_text_content(content)
                            if text_content.strip():
                                title = text_content.strip()[:100]
                                if len(text_content) > 100:
                                    title += "..."
                        
                        if first_entry.get("timestamp"):
                            timestamp = first_entry.get("timestamp")
                            dt = self._parse_iso_timestamp(timestamp)
                            if dt:
                                date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    pass
            
            # If no title found, use file name
            if title == "Untitled Conversation":
                title = file_path_or_key.stem
                if len(title) > 50:
                    title = title[:50] + "..."
            
            # If no date found, use file modification time
            if not date_str:
                try:
                    mtime = file_path_or_key.stat().st_mtime
                    dt = datetime.datetime.fromtimestamp(mtime)
                    date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            
            return {
                "id": chat_id,
                "title": title,
                "date": date_str,
                "file_path": str(file_path_or_key)
            }
        except Exception:
            return None

    def _parse_chat_full(self, file_path_or_key: Any) -> Optional[Dict[str, Any]]:
        """Parse full chat content.
        
        Args:
            file_path_or_key: File path (pathlib.Path) to JSONL/JSON file
            
        Returns:
            Full chat dict with title, metadata, createdAt, messages.
            Returns None if chat cannot be parsed.
        """
        if not isinstance(file_path_or_key, pathlib.Path):
            return None
        
        try:
            if file_path_or_key.suffix == ".jsonl":
                # Parse JSONL file
                raw_data = self._parse_jsonl_file(file_path_or_key)
                if not raw_data:
                    return None
            else:
                # Parse regular JSON file
                raw_data = json.loads(file_path_or_key.read_text(encoding="utf-8"))
                # If it's already a list, use it; if it's a dict, wrap it
                if isinstance(raw_data, dict):
                    raw_data = [raw_data]
            
            # Transform to export format
            project_name = file_path_or_key.parent.name
            transformed = self._transform_chat_to_export_format(
                raw_data,
                project_name,
                file_path_or_key.name
            )
            
            return transformed
        except Exception:
            return None

    # get_chat_metadata_list and parse_chat_by_id are inherited from base class

    def _parse_iso_timestamp(self, timestamp_str: str) -> Optional[datetime.datetime]:
        """Parse ISO timestamp string to datetime object."""
        try:
            # Handle various ISO formats
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except Exception:
            return None

    def _extract_text_content(self, content: Any) -> str:
        """Extract text content from message content (can be string or array)."""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text" and "text" in item:
                        text_parts.append(item["text"])
                    elif "text" in item:
                        text_parts.append(str(item["text"]))
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(text_parts)
        else:
            return str(content) if content else ""
    
    def _normalize_claude_tool_input(self, tool_name: str, normalized_tool_name: str, tool_input: Any, tool_output: Any = None) -> Any:
        """
        Normalize tool input for Claude-specific tools.
        
        Args:
            tool_name: Original tool name from Claude
            normalized_tool_name: Normalized tool name
            tool_input: Original tool input
            tool_output: Original tool output (optional, needed for terminal transformation)
            
        Returns:
            Normalized tool input
        """
        # Dispatch to tool-specific normalization methods
        if normalized_tool_name == "web_request":
            return self._normalize_claude_web_request_input(tool_input)
        elif normalized_tool_name == "read":
            return self._normalize_claude_read_input(tool_input)
        elif normalized_tool_name == "todo":
            return self._normalize_claude_todo_input(tool_input)
        elif normalized_tool_name == "create":
            return self._normalize_claude_create_input(tool_input)
        elif normalized_tool_name == "update":
            return self._normalize_claude_update_input(tool_input)
        elif normalized_tool_name == "delete":
            return self._normalize_claude_delete_input(tool_input)
        elif normalized_tool_name == "terminal":
            return self._normalize_claude_terminal_input(tool_input, tool_output)
        
        return tool_input
    
    def _normalize_claude_web_request_input(self, tool_input: Any) -> Any:
        """Normalize web_request tool input for Claude."""
        result = {}
        if isinstance(tool_input, dict):
            # Extract prompt as request (Claude uses "prompt" instead of "searchTerm")
            if "prompt" in tool_input:
                result["request"] = tool_input["prompt"]
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
    
    def _normalize_claude_read_input(self, tool_input: Any) -> Any:
        """Normalize read tool input for Claude."""
        if isinstance(tool_input, dict):
            # Check if it has file_path (Claude format)
            if "file_path" in tool_input:
                file_path = tool_input["file_path"]
                return [file_path] if file_path else []
            # Check if it has targetFile
            elif "targetFile" in tool_input:
                target_file = tool_input["targetFile"]
                return [target_file] if target_file else []
            # Check if it has pattern (glob pattern search - return the pattern)
            elif "pattern" in tool_input:
                pattern = tool_input["pattern"]
                return pattern if pattern else []
            # If it's an empty dict, return empty array
            elif not tool_input:
                return []
        
        # If it's already a string, wrap in array
        elif isinstance(tool_input, str):
            return [tool_input] if tool_input else []
        
        # If it's already a list, return as-is
        elif isinstance(tool_input, list):
            return tool_input
        
        return tool_input
    
    def _normalize_claude_todo_input(self, tool_input: Any) -> Any:
        """Normalize todo tool input for Claude."""
        # Handle null/None input - return None (will be kept as null in output)
        if tool_input is None:
            return None
        
        if isinstance(tool_input, dict):
            # Extract todos array and simplify (skip todos with empty names)
            todos = []
            todos_raw = tool_input.get("todos", [])
            if isinstance(todos_raw, list):
                for todo_item in todos_raw:
                    if isinstance(todo_item, dict):
                        # Claude uses "content" for the name, convert to "name"
                        todo_name = todo_item.get("content", "")
                        # Skip todos with empty names
                        if todo_name and todo_name.strip():
                            simplified_todo = {
                                "name": todo_name,
                                "status": todo_item.get("status", "")
                            }
                            todos.append(simplified_todo)
            
            # If no valid todos, skip this tool entirely (unless tool_output has content)
            if not todos:
                return None
            
            # Build result with just todos array
            return {
                "todos": todos
            }
        return tool_input
    
    def _normalize_claude_create_input(self, tool_input: Any) -> Any:
        """Normalize create tool input for Claude."""
        # Extract only the file name from file_path, ignore content
        if isinstance(tool_input, dict):
            if "file_path" in tool_input:
                file_path = tool_input["file_path"]
                # Extract just the filename from the path
                if isinstance(file_path, str):
                    return os.path.basename(file_path)
            # If no file_path, check for other path-related keys
            elif "path" in tool_input:
                path = tool_input["path"]
                if isinstance(path, str):
                    return os.path.basename(path)
        elif isinstance(tool_input, str):
            # If it's already a string, assume it's a path and extract filename
            return os.path.basename(tool_input)
        return tool_input
    
    def _normalize_claude_update_input(self, tool_input: Any) -> Any:
        """Normalize update tool input for Claude."""
        # Extract only the file name from file_path, ignore old_string/new_string
        if isinstance(tool_input, dict):
            if "file_path" in tool_input:
                file_path = tool_input["file_path"]
                # Extract just the filename from the path
                if isinstance(file_path, str):
                    return os.path.basename(file_path)
            # If no file_path, check for other path-related keys
            elif "path" in tool_input:
                path = tool_input["path"]
                if isinstance(path, str):
                    return os.path.basename(path)
        elif isinstance(tool_input, str):
            # If it's already a string, assume it's a path and extract filename
            return os.path.basename(tool_input)
        return tool_input
    
    def _normalize_claude_delete_input(self, tool_input: Any) -> Any:
        """Normalize delete tool input for Claude."""
        return tool_input
    
    def _normalize_claude_terminal_input(self, tool_input: Any, tool_output: Any = None) -> Any:
        """Normalize terminal tool input for Claude."""
        # Extract command from tool_input dict (similar to Copilot's logic)
        if isinstance(tool_input, dict):
            # Check for "command" key (Claude format)
            if "command" in tool_input:
                command = tool_input["command"]
                if isinstance(command, str):
                    return command
        # Fallback: if it's already a string, return as-is
        elif isinstance(tool_input, str):
            return tool_input
        return tool_input
    
    def _normalize_claude_tool_output(self, tool_name: str, normalized_tool_name: str, tool_output: Any, tool_input: Any = None) -> Any:
        """
        Normalize tool output for Claude-specific tools.
        
        Args:
            tool_name: Original tool name from Claude
            normalized_tool_name: Normalized tool name
            tool_output: Original tool output
            tool_input: Original tool input (optional, needed for read operations with pattern)
            
        Returns:
            Normalized tool output
        """
        # Dispatch to tool-specific normalization methods
        if normalized_tool_name == "web_request":
            return self._normalize_claude_web_request_output(tool_output)
        elif normalized_tool_name == "read":
            return self._normalize_claude_read_output(tool_output, tool_input)
        elif normalized_tool_name == "todo":
            return self._normalize_claude_todo_output(tool_output)
        elif normalized_tool_name == "create":
            return self._normalize_claude_create_output(tool_output, tool_input)
        elif normalized_tool_name == "update":
            return self._normalize_claude_update_output(tool_output, tool_input)
        elif normalized_tool_name == "delete":
            return self._normalize_claude_delete_output(tool_output)
        elif normalized_tool_name == "terminal":
            return self._normalize_claude_terminal_output(tool_output)
        
        return tool_output
    
    def _normalize_claude_web_request_output(self, tool_output: Any) -> Any:
        """Normalize web_request tool output for Claude."""
        return ""
    
    def _normalize_claude_read_output(self, tool_output: Any, tool_input: Any = None) -> Any:
        """Normalize read tool output for Claude."""
        # Check if the original input was a pattern search
        if tool_input:
            # Check if input was a pattern (dict with "pattern" key or string pattern)
            is_pattern = False
            if isinstance(tool_input, dict) and "pattern" in tool_input:
                is_pattern = True
            elif isinstance(tool_input, str) and ("*" in tool_input or "?" in tool_input):
                # Heuristic: if it's a string with glob characters, likely a pattern
                is_pattern = True
            
            if is_pattern and tool_output:
                # Try to extract file list from tool_output
                # tool_output might be a string with file paths, or a list, or a dict
                if isinstance(tool_output, list):
                    # If it's already a list, return it
                    return tool_output
                elif isinstance(tool_output, dict):
                    # Check for common keys that might contain file paths
                    if "files" in tool_output:
                        files = tool_output["files"]
                        return files if isinstance(files, list) else [files] if files else []
                    elif "paths" in tool_output:
                        paths = tool_output["paths"]
                        return paths if isinstance(paths, list) else [paths] if paths else []
                    elif "results" in tool_output:
                        results = tool_output["results"]
                        if isinstance(results, list):
                            # Extract file paths from results
                            file_paths = []
                            for result in results:
                                if isinstance(result, dict):
                                    if "path" in result:
                                        file_paths.append(result["path"])
                                    elif "file" in result:
                                        file_paths.append(result["file"])
                                    elif "file_path" in result:
                                        file_paths.append(result["file_path"])
                                elif isinstance(result, str):
                                    file_paths.append(result)
                            return file_paths if file_paths else []
                elif isinstance(tool_output, str) and tool_output.strip():
                    # Try to parse as JSON or extract file paths from string
                    try:
                        parsed = json.loads(tool_output)
                        if isinstance(parsed, list):
                            return parsed
                        elif isinstance(parsed, dict):
                            # Recursively check the parsed dict
                            if "files" in parsed:
                                files = parsed["files"]
                                return files if isinstance(files, list) else [files] if files else []
                    except (json.JSONDecodeError, ValueError):
                        # If not JSON, check if it's a newline-separated list of files
                        lines = [line.strip() for line in tool_output.split("\n") if line.strip()]
                        if lines:
                            return lines
        
        # For non-pattern reads, return empty string (as before)
        return ""
    
    def _normalize_claude_todo_output(self, tool_output: Any) -> Any:
        """Normalize todo tool output for Claude."""
        # Handle array of text objects (e.g., [{"type": "text", "text": "..."}])
        if isinstance(tool_output, list):
            # Extract text from text-type objects
            text_parts = []
            for item in tool_output:
                if isinstance(item, dict):
                    if item.get("type") == "text" and "text" in item:
                        text_parts.append(item["text"])
                    # Also check for direct "text" key
                    elif "text" in item:
                        text_parts.append(item["text"])
                elif isinstance(item, str):
                    text_parts.append(item)
            
            # If we found text parts, join them
            if text_parts:
                return "\n".join(text_parts)
        
        # If it's a string, return as-is
        elif isinstance(tool_output, str):
            return tool_output
        
        # For other types, return as-is
        return tool_output
    
    def _normalize_claude_create_output(self, tool_output: Any, tool_input: Any = None) -> Any:
        """Normalize create tool output for Claude."""
        # Use the file name from input as output (don't show content)
        if tool_input:
            if isinstance(tool_input, dict):
                if "file_path" in tool_input:
                    file_path = tool_input["file_path"]
                    if isinstance(file_path, str):
                        return os.path.basename(file_path)
                elif "path" in tool_input:
                    path = tool_input["path"]
                    if isinstance(path, str):
                        return os.path.basename(path)
            elif isinstance(tool_input, str):
                return os.path.basename(tool_input)
        return ""
    
    def _normalize_claude_update_output(self, tool_output: Any, tool_input: Any = None) -> Any:
        """Normalize update tool output for Claude."""
        # Generate diff from old_string and new_string in tool_input
        if tool_input and isinstance(tool_input, dict):
            old_string = tool_input.get("old_string")
            new_string = tool_input.get("new_string")
            
            if old_string is not None and new_string is not None:
                # Generate a simple unified diff format
                return self._generate_diff(old_string, new_string)
        
        # If no diff can be generated, return empty string
        return ""
    
    def _generate_diff(self, old_string: str, new_string: str) -> str:
        """Generate a simple unified diff from old and new strings."""
        # If strings are identical, return empty
        if old_string == new_string:
            return ""
        
        old_lines = old_string.splitlines()
        new_lines = new_string.splitlines()
        
        # Simple line-by-line diff
        diff_parts = []
        max_len = max(len(old_lines), len(new_lines))
        
        for i in range(max_len):
            old_line = old_lines[i] if i < len(old_lines) else None
            new_line = new_lines[i] if i < len(new_lines) else None
            
            if old_line == new_line:
                # Unchanged line - show with space prefix for context
                if old_line is not None:
                    diff_parts.append(f" {old_line}")
            else:
                # Changed or added/removed lines
                if old_line is not None:
                    diff_parts.append(f"-{old_line}")
                if new_line is not None:
                    diff_parts.append(f"+{new_line}")
        
        return "\n".join(diff_parts)
    
    def _normalize_claude_delete_output(self, tool_output: Any) -> Any:
        """Normalize delete tool output for Claude."""
        return tool_output
    
    def _normalize_claude_terminal_output(self, tool_output: Any) -> Any:
        """Normalize terminal tool output for Claude."""
        # Return empty string like Copilot (don't show command output)
        return ""
    
    def _normalize_claude_tool_usage(self, tool_name: str, tool_input: Any, tool_output: Any) -> Optional[Dict[str, Any]]:
        """
        Normalize a complete tool usage entry for Claude.
        
        Args:
            tool_name: Original tool name from Claude
            tool_input: Original tool input
            tool_output: Original tool output
            
        Returns:
            Normalized tool usage dict with keys: tool_name, tool_input, tool_output
            Returns None if tool should be skipped
        """
        # Normalize tool name using common function
        normalized_name = tool_name_normalization("claude", tool_name)
        
        if normalized_name is None:
            return None
        
        # Apply Claude-specific input/output normalization
        normalized_input = self._normalize_claude_tool_input(tool_name, normalized_name, tool_input, tool_output)
        normalized_output = self._normalize_claude_tool_output(tool_name, normalized_name, tool_output, tool_input)
        
        return {
            "tool_name": normalized_name,
            "tool_input": normalized_input,
            "tool_output": normalized_output
        }

    def _transform_messages(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform raw message data to the export format."""
        messages = []
        tool_results = {}  # Map tool_use_id to tool_result
        
        # First pass: collect tool results
        for entry in data:
            if entry.get("type") == "user" and isinstance(entry.get("message", {}).get("content"), list):
                content = entry["message"]["content"]
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        tool_use_id = item.get("tool_use_id")
                        if tool_use_id:
                            tool_results[tool_use_id] = {
                                "content": item.get("content", ""),
                                "is_error": item.get("is_error", False),
                                "timestamp": entry.get("timestamp")
                            }
                            # Also check toolUseResult if available
                            if "toolUseResult" in entry:
                                tool_results[tool_use_id]["toolUseResult"] = entry["toolUseResult"]

        # Second pass: transform messages
        for entry in data:
            entry_type = entry.get("type")
            timestamp = entry.get("timestamp", "")
            
            # Skip file-history-snapshot entries
            if entry_type == "file-history-snapshot":
                continue
            
            if entry_type == "user":
                message = entry.get("message", {})
                content = message.get("content", "")
                
                # Check if this is a tool result message (skip, we'll attach it to tool_use)
                if isinstance(content, list):
                    is_tool_result = any(
                        isinstance(item, dict) and item.get("type") == "tool_result"
                        for item in content
                    )
                    if is_tool_result:
                        continue
                
                text_content = self._extract_text_content(content)
                if not text_content.strip():
                    continue
                
                msg_obj = {
                    "role": "user",
                    "type": "text",
                    "content": text_content,
                    "timestamp": timestamp
                }
                
                # Add inputs if available (for attachments, etc.)
                # Note: Claude format doesn't seem to have explicit inputs field
                # but we can check for other metadata if needed
                
                messages.append(msg_obj)
            
            elif entry_type == "assistant":
                message = entry.get("message", {})
                content = message.get("content", [])
                
                if not isinstance(content, list):
                    continue
                
                # Process each content item
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    
                    item_type = item.get("type")
                    
                    if item_type == "text":
                        text_content = item.get("text", "")
                        if text_content.strip():
                            messages.append({
                                "role": "assistant",
                                "type": "text",
                                "content": text_content,
                                "timestamp": timestamp
                            })
                    
                    elif item_type == "tool_use":
                        tool_id = item.get("id")
                        tool_name = item.get("name", "")
                        tool_input = item.get("input", {})
                        
                        # Get tool result if available
                        tool_result = tool_results.get(tool_id, {})
                        tool_output = tool_result.get("content", "")
                        
                        # If toolUseResult exists, prefer that
                        if "toolUseResult" in tool_result:
                            tool_use_result = tool_result["toolUseResult"]
                            if isinstance(tool_use_result, dict):
                                stdout = tool_use_result.get("stdout", "")
                                stderr = tool_use_result.get("stderr", "")
                                if stdout:
                                    tool_output = stdout
                                elif stderr:
                                    tool_output = stderr
                        
                        # Normalize tool usage using Claude-specific logic
                        normalized = self._normalize_claude_tool_usage(tool_name, tool_input, tool_output)
                        
                        if normalized:
                            messages.append({
                                "role": "assistant",
                                "type": "tool",
                                "content": normalized,
                                "timestamp": timestamp
                            })
                    
                    # Skip thinking blocks
                    elif item_type == "thinking":
                        continue
        
        return messages

    def _transform_chat_to_export_format(
        self, 
        data: List[Dict[str, Any]], 
        project_name: str,
        file_name: str
    ) -> Dict[str, Any]:
        """Transform a single chat conversation to the export format."""
        # Find first timestamp for createdAt
        first_timestamp = None
        for entry in data:
            if entry.get("timestamp"):
                first_timestamp = entry.get("timestamp")
                break
        
        if not first_timestamp:
            first_timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Extract model from assistant messages
        model = "Claude Sonnet 4.0"  # Default
        for entry in data:
            if entry.get("type") == "assistant":
                msg_model = entry.get("message", {}).get("model", "")
                if msg_model:
                    # Convert model name to readable format
                    if "claude-sonnet-4" in msg_model or "sonnet-4" in msg_model:
                        model = "Claude Sonnet 4.0"
                    elif "claude-sonnet-3" in msg_model or "sonnet-3" in msg_model:
                        model = "Claude Sonnet 3.5"
                    elif "claude-opus" in msg_model:
                        model = "Claude Opus"
                    elif "claude-haiku" in msg_model:
                        model = "Claude Haiku"
                    else:
                        model = msg_model.replace("claude-", "Claude ").replace("-", " ").title()
                    break
        
        # Generate title from first user message
        title = "Untitled Conversation"
        for entry in data:
            if entry.get("type") == "user":
                message = entry.get("message", {})
                content = message.get("content", "")
                text_content = self._extract_text_content(content)
                if text_content.strip():
                    # Use first 100 chars as title
                    title = text_content.strip()[:100]
                    if len(text_content) > 100:
                        title += "..."
                    break
        
        # If no title found, use file name
        if title == "Untitled Conversation":
            # Remove .jsonl extension and use session ID or file name
            title = file_name.replace(".jsonl", "").replace(".json", "")
            if len(title) > 50:
                title = title[:50] + "..."
        
        # Transform messages
        messages = self._transform_messages(data)
        
        # Build metadata
        metadata = {
            "model": model,
            "chat_timezone": self._get_timezone_offset(),
            "Project": project_name
        }
        
        return {
            "title": title,
            "metadata": metadata,
            "createdAt": first_timestamp,
            "messages": messages
        }

    def export_chats(self, output_path: pathlib.Path) -> List[Dict[str, Any]]:
        """Export all Claude chat files in the standardized format.
        
        Args:
            output_path: Path to save the JSON file.
            
        Returns:
            List of transformed conversation objects.
        """
        chat_files = self.find_all_chat_files()
        
        if not chat_files:
            result: List[Dict[str, Any]] = []
            output_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            return result

        # Transform each chat file to the new format
        transformed_chats: List[Dict[str, Any]] = []
        
        for chat_file in chat_files:
            try:
                if chat_file.suffix == ".jsonl":
                    # Parse JSONL file (one JSON object per line)
                    raw_data = self._parse_jsonl_file(chat_file)
                    if not raw_data:
                        continue
                else:
                    # Parse regular JSON file
                    raw_data = json.loads(chat_file.read_text(encoding="utf-8"))
                    # If it's already a list, use it; if it's a dict, wrap it
                    if isinstance(raw_data, dict):
                        raw_data = [raw_data]
                
                # Transform to export format
                project_name = chat_file.parent.name
                transformed = self._transform_chat_to_export_format(
                    raw_data, 
                    project_name,
                    chat_file.name
                )
                transformed_chats.append(transformed)
            except Exception as e:
                # Skip files that can't be read/parsed
                continue
        
        # Save to file (as array, not wrapped in object)
        output_path.write_text(
            json.dumps(transformed_chats, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        return transformed_chats


def find_claude_chats() -> List[Dict[str, Any]]:
    """Find all Claude chat files and return transformed data."""
    finder = ClaudeChatFinder()
    output_path = finder._get_default_output_path("claude_chats.json")
    return finder.export_chats(output_path)


def save_claude_chats(output_path: pathlib.Path) -> List[Dict[str, Any]]:
    """Export and save all Claude chats to a JSON file in the new format."""
    finder = ClaudeChatFinder()
    return finder.export_chats(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract Claude Code chat transcripts from ~/.claude/projects"
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=None,
        help="Output JSON file for exporting all chats (default: result/claude_chats.json)"
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="Export a specific chat by ID"
    )
    args = parser.parse_args()

    finder = ClaudeChatFinder()
    
    # Two-step approach: --export=chat_id exports specific chat
    if args.export:
        try:
            chat_data = finder.parse_chat_by_id(args.export)
            # Save single chat to results folder
            output_path = finder._get_default_output_path(f"claude_chat_{args.export[:8]}.json")
            output_path.write_text(
                json.dumps(chat_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"Exported chat {args.export} to {output_path}")
        except ValueError as e:
            print(f"Error: {e}")
            exit(1)
    # List mode: no arguments prints all chats with IDs
    elif args.out is None:
        metadata_list = finder.get_chat_metadata_list()
        print(f"Found {len(metadata_list)} chats:")
        for chat in metadata_list:
            print(f"  {chat['id']} - \"{chat['title']}\" ({chat['date']})")
    # Export all mode: --out specified exports all chats
    else:
        # Ensure parent directory exists
        finder._ensure_output_dir(args.out)
        result = finder.export_chats(args.out)
        print(f"Extracted {len(result)} Claude Code chat sessions to {args.out}")
