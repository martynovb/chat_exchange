from __future__ import annotations

import json
import pathlib
import platform
from typing import List, Optional, Dict, Any

"""This module exports Copilot chat JSON files as-is, merging multiple files."""


class CopilotChatFinder:
    """Find and extract GitHub Copilot chat histories from VS Code."""

    def get_storage_root(self) -> Optional[pathlib.Path]:
        """Return the path to VS Code's `workspaceStorage` directory.

        Tries standard Code and Code - Insiders locations on Windows/macOS/Linux.
        Returns None if platform is unsupported.
        """
        home = pathlib.Path.home()
        system = platform.system()

        candidates: List[pathlib.Path] = []
        if system == "Windows":
            base = home / "AppData" / "Roaming"
            candidates = [base / d / "User" / "workspaceStorage" for d in ("Code", "Code - Insiders")]
        elif system == "Darwin":
            base = home / "Library" / "Application Support"
            candidates = [base / d / "User" / "workspaceStorage" for d in ("Code", "Code - Insiders")]
        elif system == "Linux":
            base = home / ".config"
            candidates = [base / d / "User" / "workspaceStorage" for d in ("Code", "Code - Insiders")]
        else:
            return None

        for p in candidates:
            if p.exists():
                return p
        # Return first candidate even if missing so caller can inspect
        return candidates[0] if candidates else None

    def find_all_chat_files(self) -> List[pathlib.Path]:
        """Find all JSON chat session files in workspaceStorage.
        
        Returns:
            List of paths to all JSON chat session files.
        """
        storage_root = self.get_storage_root()
        if not storage_root or not storage_root.exists():
            return []

        chat_files: List[pathlib.Path] = []

        for ws_dir in storage_root.iterdir():
            if not ws_dir.is_dir():
                continue

            # Look for chat sessions directory
            chat_dir = ws_dir / "chatSessions"
            if not chat_dir.exists() or not chat_dir.is_dir():
                continue

            # Collect all JSON files
            chat_files.extend(sorted(chat_dir.glob("*.json")))

        return chat_files

    def export_chats(self, output_path: pathlib.Path) -> Dict[str, Any]:
        """Export all Copilot chat JSON files, merging them into a single JSON structure.
        
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

        # Read all JSON files and merge them
        merged_chats: List[Dict[str, Any]] = []
        
        for chat_file in chat_files:
            try:
                raw_data = json.loads(chat_file.read_text(encoding="utf-8"))
                # Add metadata about the source file
                chat_entry = {
                    "file_path": str(chat_file),
                    "file_name": chat_file.name,
                    "workspace_id": chat_file.parent.parent.name,
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


def find_copilot_chats() -> Dict[str, Any]:
    """Find all Copilot chat files and return merged data."""
    finder = CopilotChatFinder()
    chat_files = finder.find_all_chat_files()
    
    merged_chats: List[Dict[str, Any]] = []
    for chat_file in chat_files:
        try:
            raw_data = json.loads(chat_file.read_text(encoding="utf-8"))
            chat_entry = {
                "file_path": str(chat_file),
                "file_name": chat_file.name,
                "workspace_id": chat_file.parent.parent.name,
                "data": raw_data
            }
            merged_chats.append(chat_entry)
        except Exception:
            continue
    
    return {"chats": merged_chats, "total_count": len(merged_chats)}


def save_copilot_chats(output_path: pathlib.Path) -> Dict[str, Any]:
    """Export and save all Copilot chats to a JSON file."""
    finder = CopilotChatFinder()
    return finder.export_chats(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract GitHub Copilot chatSessions from VS Code workspaceStorage")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("copilot_chats.json"), help="Output JSON file")
    args = parser.parse_args()

    finder = CopilotChatFinder()
    result = finder.export_chats(args.out)
    print(f"Extracted {result['total_count']} copilot chat sessions to {args.out}")
