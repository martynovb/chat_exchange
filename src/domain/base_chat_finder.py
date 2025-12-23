#!/usr/bin/env python3
"""
Base class for chat finders.
Provides unified interface for extracting chat metadata and parsing chats.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import time
from abc import ABC, abstractmethod
from datetime import datetime
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
        # Get the src directory (parent of domain)
        src_dir = pathlib.Path(__file__).parent.parent
        return src_dir / "data" / "results"
    
    def _get_default_output_path(self, filename: str) -> pathlib.Path:
        """Get the default output path in the result folder.
        
        Args:
            filename: Name of the output file (e.g., "claude_chats.json")
            
        Returns:
            Path to the default output file in result folder.
        """
        result_dir = self._get_result_dir()
        # Save single chats to results/chats subdirectory
        chats_dir = result_dir / "chats"
        chats_dir.mkdir(parents=True, exist_ok=True)
        return chats_dir / filename
    
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
        chat_files = self.find_all_chat_files()
        metadata_list = []
        
        for file_path_or_key in chat_files:
            try:
                metadata = self._extract_metadata_lightweight(file_path_or_key)
                if metadata:
                    metadata_list.append(metadata)
            except Exception:
                # Skip files that can't be read
                continue
        
        return metadata_list
    
    def parse_chat_by_id(self, chat_id: str) -> Dict[str, Any]:
        """Parse a specific chat into full format.
        
        Args:
            chat_id: Unique chat ID returned by get_chat_metadata_list()
            
        Returns:
            Full chat dict with title, metadata, createdAt, messages
            
        Raises:
            ValueError: If chat_id is not found
        """
        # Find the chat file/key that matches this ID
        chat_files = self.find_all_chat_files()
        
        for file_path_or_key in chat_files:
            try:
                chat_id_for_file = self._generate_chat_id(file_path_or_key)
                if chat_id_for_file == chat_id:
                    # Found the matching chat, parse it fully
                    parsed = self._parse_chat_full(file_path_or_key)
                    if parsed:
                        return parsed
            except Exception:
                continue
        
        raise ValueError(f"Chat ID '{chat_id}' not found")
    
    def save_chat_list(self, metadata_list: List[Dict[str, Any]], ai_type: str) -> pathlib.Path:
        """Save chat list to results/chat_list directory.
        
        Args:
            metadata_list: List of chat metadata dicts with keys: id, title, date, file_path
            ai_type: Type of AI (e.g., "cursor", "claude", "copilot")
            
        Returns:
            Path to the saved file
        """
        # Get result directory and create chat_list subdirectory
        result_dir = self._get_result_dir()
        chat_list_dir = result_dir / "chat_list"
        chat_list_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename: [ai_type_name]_list_date.json
        current_date = datetime.now().strftime("%Y%m%d")
        filename = f"{ai_type}_list_{current_date}.json"
        output_path = chat_list_dir / filename
        
        # Format the chat list JSON
        # Convert date string to ISO format for createdAt
        chat_list = []
        for chat in metadata_list:
            # Convert date string (e.g., "2025-12-20") to ISO format
            date_str = chat.get('date', '')
            createdAt = ""
            if date_str:
                try:
                    # Try to parse the date and convert to ISO format
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    createdAt = dt.strftime("%Y-%m-%dT00:00:00.000000Z")
                except ValueError:
                    # If parsing fails, use the date string as is or empty
                    createdAt = date_str if date_str else ""
            
            chat_list.append({
                "id": chat['id'],
                "title": chat['title'],
                "createdAt": createdAt
            })
        
        # Create the output JSON structure
        output_data = {
            "type": ai_type,
            "createdAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "list": chat_list
        }
        
        # Save to file
        output_path.write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        return output_path

