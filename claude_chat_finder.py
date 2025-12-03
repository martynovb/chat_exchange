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
import pathlib
import time
import datetime
from typing import List, Optional, Dict, Any

"""This module exports Claude chat JSON/JSONL files in a standardized format."""


class ClaudeChatFinder:
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

    def _get_timezone_offset(self) -> str:
        """Get timezone offset string like 'UTC+4'."""
        try:
            # Get local timezone offset
            offset_seconds = time.timezone if (time.daylight == 0) else time.altzone
            offset_hours = abs(offset_seconds) // 3600
            sign = '+' if offset_seconds <= 0 else '-'
            return f"UTC{sign}{offset_hours}"
        except Exception:
            return "UTC+0"  # Default fallback

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
                        
                        messages.append({
                            "role": "assistant",
                            "type": "tool",
                            "content": {
                                "toolName": tool_name,
                                "toolInput": tool_input,
                                "toolOutput": tool_output
                            },
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
    return finder.export_chats(pathlib.Path("claude_chats.json"))


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
        default=pathlib.Path("claude_chats.json"),
        help="Output JSON file"
    )
    args = parser.parse_args()

    finder = ClaudeChatFinder()
    result = finder.export_chats(args.out)
    print(f"Extracted {len(result)} Claude Code chat sessions to {args.out}")
