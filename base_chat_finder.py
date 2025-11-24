#!/usr/bin/env python3
"""
Base abstract class for chat finder implementations.

Defines the common interface that all chat finders must implement.
"""

from __future__ import annotations

import json
import pathlib
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field


MessageType = Literal["user", "assistant", "thinking", "tool_use", "tool_result", "code_diff"]


@dataclass
class ChatMessage:
    """Represents a single message or action in a chat session.

    Supports multiple message types:
    - user: User input text
    - assistant: AI text response
    - thinking: AI reasoning/planning
    - tool_use: AI using a tool (Read, Write, Edit, etc.)
    - tool_result: Result from tool execution
    - code_diff: When AI modifies a file
    """
    type: MessageType
    content: str
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {
            "type": self.type,
            "content": self.content
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class ProjectInfo:
    """Represents project/workspace information."""
    name: str
    root_path: str

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "rootPath": self.root_path}


@dataclass
class ChatSession:
    """Represents a complete chat session."""
    project: ProjectInfo
    session_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    date: str = ""
    file_path: str = ""
    workspace_id: str = ""
    raw_data: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format matching the existing API."""
        result = {
            "project": self.project.to_dict(),
            "session_id": self.session_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "date": self.date,
        }

        if self.file_path:
            result["file_path"] = self.file_path
        if self.workspace_id:
            result["workspace_id"] = self.workspace_id
        if self.raw_data is not None:
            # Name the raw data field based on the finder type
            # This will be customized by subclasses
            result["raw_data"] = self.raw_data

        return result


class ChatFinder(ABC):
    """Abstract base class for chat history finders.

    All chat finder implementations should inherit from this class
    and implement the required abstract methods.
    """

    def __init__(self):
        """Initialize the chat finder."""
        self._storage_root: Optional[pathlib.Path] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this finder (e.g., 'Copilot', 'Cursor', 'Claude')."""
        pass

    @abstractmethod
    def get_storage_root(self) -> Optional[pathlib.Path]:
        """Return the root directory where chat data is stored.

        Returns:
            Path to the storage directory, or None if not found.
        """
        pass

    @abstractmethod
    def find_chat_sessions(self) -> List[ChatSession]:
        """Find and extract all chat sessions from storage.

        Returns:
            List of ChatSession objects.
        """
        pass

    def extract_chats(self) -> List[Dict[str, Any]]:
        """Main entry point: extract all chats and return as dictionaries.

        Returns:
            List of chat dictionaries matching the existing API format.
        """
        sessions = self.find_chat_sessions()
        return [session.to_dict() for session in sessions]

    def save_to_file(self, output_path: pathlib.Path) -> List[Dict[str, Any]]:
        """Extract chats and save them to a JSON file.

        Args:
            output_path: Path to the output JSON file.

        Returns:
            List of extracted chat dictionaries.
        """
        chats = self.extract_chats()
        output_path.write_text(
            json.dumps(chats, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return chats

    @property
    def storage_root(self) -> Optional[pathlib.Path]:
        """Cached storage root path."""
        if self._storage_root is None:
            self._storage_root = self.get_storage_root()
        return self._storage_root

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, storage_root={self.storage_root})"


# Helper functions for creating specific message types

def create_user_message(content: str) -> ChatMessage:
    """Create a user message."""
    return ChatMessage(type="user", content=content)


def create_assistant_message(content: str) -> ChatMessage:
    """Create an assistant text message."""
    return ChatMessage(type="assistant", content=content)


def create_thinking_message(content: str) -> ChatMessage:
    """Create a thinking/reasoning message."""
    return ChatMessage(type="thinking", content=content)


def create_tool_use_message(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_id: Optional[str] = None,
    content: Optional[str] = None
) -> ChatMessage:
    """Create a tool use message."""
    return ChatMessage(
        type="tool_use",
        content=content or f"Using {tool_name}",
        metadata={
            "tool_name": tool_name,
            "tool_id": tool_id,
            "input": tool_input
        }
    )


def create_tool_result_message(
    tool_use_id: str,
    result_content: str,
    tool_name: Optional[str] = None
) -> ChatMessage:
    """Create a tool result message."""
    metadata = {"tool_use_id": tool_use_id}
    if tool_name:
        metadata["tool_name"] = tool_name

    return ChatMessage(
        type="tool_result",
        content=result_content,
        metadata=metadata
    )


def create_code_diff_message(
    file_path: str,
    operation: Literal["write", "edit", "delete"],
    new_content: Optional[str] = None,
    old_content: Optional[str] = None
) -> ChatMessage:
    """Create a code diff message."""
    metadata = {
        "file_path": file_path,
        "operation": operation
    }
    if new_content is not None:
        metadata["new_content"] = new_content
    if old_content is not None:
        metadata["old_content"] = old_content

    content_desc = f"{operation.capitalize()} file: {file_path}"
    return ChatMessage(
        type="code_diff",
        content=content_desc,
        metadata=metadata
    )
