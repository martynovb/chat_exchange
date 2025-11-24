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
import datetime
from typing import List, Optional, Dict, Any

from base_chat_finder import ChatFinder, ChatSession, ChatMessage, ProjectInfo
from chat_message_parser import parse_claude_messages


class ClaudeChatFinder(ChatFinder):
    """Find and extract Claude Code chat histories."""

    @property
    def name(self) -> str:
        return "Claude"

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
                for line_num, line in enumerate(f, 1):
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

    def _extract_messages_from_transcript(self, transcript_objects: List[Dict[str, Any]]) -> List[ChatMessage]:
        """Extract user and assistant messages from transcript objects.

        Uses the Claude message parser to extract detailed message types including
        thinking, tool usage, and code diffs.
        """
        return parse_claude_messages(transcript_objects)

    def find_chat_sessions(self) -> List[ChatSession]:
        """Scan ~/.claude/projects and return list of Claude Code chat sessions."""
        projects_root = self.storage_root
        if not projects_root or not projects_root.exists():
            return []

        results: List[ChatSession] = []

        for project_dir in projects_root.iterdir():
            if not project_dir.is_dir():
                continue

            # Skip cache directories
            if project_dir.name.startswith("."):
                continue

            project_info = ProjectInfo(
                name=project_dir.name,
                root_path=str(project_dir)
            )

            # Find all JSONL transcript files in the project directory
            for transcript_file in project_dir.glob("*.jsonl"):
                try:
                    transcript_objects = self._parse_jsonl_file(transcript_file)
                    if not transcript_objects:
                        continue

                    messages = self._extract_messages_from_transcript(transcript_objects)

                    session = ChatSession(
                        project=project_info,
                        session_id=transcript_file.stem,
                        messages=messages,
                        date=datetime.datetime.fromtimestamp(
                            transcript_file.stat().st_mtime
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                        file_path=str(transcript_file),
                        raw_data=transcript_objects
                    )

                    results.append(session)

                except Exception:
                    continue

            # Also check for plain JSON files that might contain chat data
            for json_file in project_dir.glob("*.json"):
                # Skip cache files and metadata
                if json_file.parent.name == ".cache" or json_file.name.startswith("."):
                    continue

                try:
                    raw = json.loads(json_file.read_text(encoding="utf-8"))

                    # Check if this looks like a chat session
                    messages = []
                    if isinstance(raw, dict):
                        if "messages" in raw and isinstance(raw["messages"], list):
                            for msg in raw["messages"]:
                                if isinstance(msg, dict):
                                    role = msg.get("role", "")
                                    content = msg.get("content", "")
                                    if role and content:
                                        messages.append(ChatMessage(type=role, content=content))
                        elif "transcript" in raw:
                            messages = self._extract_messages_from_transcript([raw["transcript"]])
                    elif isinstance(raw, list):
                        messages = self._extract_messages_from_transcript(raw)

                    if messages:
                        session = ChatSession(
                            project=project_info,
                            session_id=json_file.stem,
                            messages=messages,
                            date=datetime.datetime.fromtimestamp(
                                json_file.stat().st_mtime
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                            file_path=str(json_file),
                            raw_data=raw
                        )

                        results.append(session)

                except Exception:
                    continue

        return results

    def extract_chats(self) -> List[dict]:
        """Extract chats with claude-specific raw data field name."""
        sessions = self.find_chat_sessions()
        chats = []
        for session in sessions:
            chat_dict = session.to_dict()
            # Rename raw_data to claude_raw for consistency with original format
            if "raw_data" in chat_dict:
                chat_dict["claude_raw"] = chat_dict.pop("raw_data")
            chats.append(chat_dict)
        return chats


def find_claude_chats() -> List[dict]:
    """Legacy function for backwards compatibility."""
    finder = ClaudeChatFinder()
    return finder.extract_chats()


def save_claude_chats(output_path: pathlib.Path) -> List[dict]:
    """Legacy function for backwards compatibility."""
    finder = ClaudeChatFinder()
    return finder.save_to_file(output_path)


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
    chats = finder.save_to_file(args.out)
    print(f"Extracted {len(chats)} Claude Code chat sessions to {args.out}")
