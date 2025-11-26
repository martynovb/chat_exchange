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
from typing import List, Optional, Dict, Any

"""This module exports Claude chat JSON/JSONL files as-is, merging multiple files."""


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

    def export_chats(self, output_path: pathlib.Path) -> Dict[str, Any]:
        """Export all Claude chat files, merging them into a single JSON structure.
        
        Args:
            output_path: Path to save the merged JSON file.
            
        Returns:
            Dictionary containing the merged chat data.
        """
        chat_files = self.find_all_chat_files()
        
        if not chat_files:
            result = {"chats": []}
            output_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            return result

        # Read all files and merge them
        merged_chats: List[Dict[str, Any]] = []
        
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
                
                # Add metadata about the source file
                chat_entry = {
                    "file_path": str(chat_file),
                    "file_name": chat_file.name,
                    "project_name": chat_file.parent.name,
                    "data": raw_data
                }
                merged_chats.append(chat_entry)
            except Exception:
                # Skip files that can't be read/parsed
                continue

        result = {"chats": merged_chats, "total_count": len(merged_chats)}
        
        # Save to file
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        return result


def find_claude_chats() -> Dict[str, Any]:
    """Find all Claude chat files and return merged data."""
    finder = ClaudeChatFinder()
    chat_files = finder.find_all_chat_files()
    
    merged_chats: List[Dict[str, Any]] = []
    for chat_file in chat_files:
        try:
            if chat_file.suffix == ".jsonl":
                raw_data = finder._parse_jsonl_file(chat_file)
                if not raw_data:
                    continue
            else:
                raw_data = json.loads(chat_file.read_text(encoding="utf-8"))
            
            chat_entry = {
                "file_path": str(chat_file),
                "file_name": chat_file.name,
                "project_name": chat_file.parent.name,
                "data": raw_data
            }
            merged_chats.append(chat_entry)
        except Exception:
            continue
    
    return {"chats": merged_chats, "total_count": len(merged_chats)}


def save_claude_chats(output_path: pathlib.Path) -> Dict[str, Any]:
    """Export and save all Claude chats to a JSON file."""
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
    print(f"Extracted {result['total_count']} Claude Code chat sessions to {args.out}")
