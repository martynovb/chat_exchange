#!/usr/bin/env python3
"""
Base class for chat finders.
Provides unified interface for extracting chat metadata and parsing chats.
"""

from __future__ import annotations

import hashlib
import pathlib
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class BaseChatFinder(ABC):
    """Abstract base class for all chat finders."""
    
    def __init__(self):
        """Initialize the chat finder."""
        self._finder_type = self.__class__.__name__.replace("ChatFinder", "").lower()
    
    @abstractmethod
    def get_storage_root(self) -> Optional[pathlib.Path]:
        """Return the path to the storage directory for this chat finder.
        
        Returns:
            Path to storage directory, or None if not found.
        """
        pass
    
    @abstractmethod
    def find_all_chat_files(self) -> List[Any]:
        """Find all chat files or database keys.
        
        Returns:
            List of file paths or database keys that represent chats.
        """
        pass
    
    @abstractmethod
    def _generate_chat_id(self, file_path_or_key: Any) -> str:
        """Generate unique chat ID from file path or database key.
        
        Args:
            file_path_or_key: File path (pathlib.Path) or database key (str/dict)
            
        Returns:
            Unique chat ID string.
        """
        pass
    
    @abstractmethod
    def _extract_metadata_lightweight(self, file_path_or_key: Any) -> Optional[Dict[str, Any]]:
        """Extract minimal metadata without parsing full content.
        
        Args:
            file_path_or_key: File path (pathlib.Path) or database key (str/dict)
            
        Returns:
            Dict with keys: id, title, date, file_path
            Returns None if metadata cannot be extracted.
        """
        pass
    
    @abstractmethod
    def _parse_chat_full(self, file_path_or_key: Any) -> Optional[Dict[str, Any]]:
        """Parse full chat content.
        
        Args:
            file_path_or_key: File path (pathlib.Path) or database key (str/dict)
            
        Returns:
            Full chat dict with title, metadata, createdAt, messages.
            Returns None if chat cannot be parsed.
        """
        pass
    
    def _get_timezone_offset(self) -> str:
        """Get timezone offset string like 'UTC+4'.
        
        Returns:
            Timezone offset string.
        """
        try:
            # Get local timezone offset
            offset_seconds = time.timezone if (time.daylight == 0) else time.altzone
            offset_hours = abs(offset_seconds) // 3600
            sign = '+' if offset_seconds <= 0 else '-'
            return f"UTC{sign}{offset_hours}"
        except Exception:
            return "UTC+0"  # Default fallback
    
    def _generate_unique_id(self, unique_key: str) -> str:
        """Generate a unique hash-based ID for a chat.
        
        Args:
            unique_key: Unique identifier string (e.g., "claude:project/file.jsonl")
            
        Returns:
            Short unique ID (16 hex characters).
        """
        full_key = f"{self._finder_type}:{unique_key}"
        return hashlib.sha256(full_key.encode('utf-8')).hexdigest()[:16]
    
    def _get_result_dir(self) -> pathlib.Path:
        """Get the result directory path.
        
        Returns:
            Path to the result directory.
        """
        return pathlib.Path("results")
    
    def _get_default_output_path(self, filename: str) -> pathlib.Path:
        """Get the default output path in the result folder.
        
        Args:
            filename: Name of the output file (e.g., "claude_chats.json")
            
        Returns:
            Path to the default output file in result folder.
        """
        result_dir = self._get_result_dir()
        result_dir.mkdir(exist_ok=True)
        return result_dir / filename
    
    def _ensure_output_dir(self, output_path: pathlib.Path) -> None:
        """Ensure the parent directory of the output path exists.
        
        Args:
            output_path: Path to the output file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_chat_metadata_list(self) -> List[Dict[str, Any]]:
        """Return list of chats with minimal metadata (title, date, file_path).
        
        Only reads enough to extract title and basic info.
        Does not parse full message content.
        
        Returns:
            List of dicts with keys: id, title, date, file_path
        """
        pass
    
    def parse_chat_by_id(self, chat_id: str) -> Dict[str, Any]:
        """Parse a specific chat into full format.
        
        Args:
            chat_id: Unique chat ID returned by get_chat_metadata_list()
            
        Returns:
            Full chat dict with title, metadata, createdAt, messages
            
        Raises:
            ValueError: If chat_id is not found
        """
        pass

