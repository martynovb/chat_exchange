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


@dataclass
class ProjectInfo:
    name: str
    root_path: str


@dataclass
class ChatMessage:
    """Minimal ChatMessage class used by finders.

    Keeping this minimal allows finders to operate without the parser.
    """
    type: str
    content: str


@dataclass
class ChatSession:
    project: ProjectInfo
    session_id: str
    messages: List[ChatMessage]
    date: str = ""
    file_path: str = ""
    workspace_id: Optional[str] = None
    raw_data: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "project": {"name": self.project.name, "root_path": self.project.root_path},
            "session_id": self.session_id,
            "messages": [ {"type": m.type, "content": m.content} for m in self.messages ],
            "date": self.date,
            "file_path": self.file_path,
        }
        if self.workspace_id:
            d["workspace_id"] = self.workspace_id
        if self.raw_data is not None:
            d["raw_data"] = self.raw_data
        return d