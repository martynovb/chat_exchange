#!/usr/bin/env python3
"""
Find GitHub Copilot chat histories in VS Code workspaceStorage and export them.

Info:
GitHub Copilot Chat histories are stored per workspace—even if you didn't create one
manually, VS Code will generate one for you automatically.

Normally, you can transfer histories between workspaces (and machines) using the
Chat: Export Chat… and Chat: Import Chat… commands. If you can't restore your
previous workspace, however, you can still retrieve the JSON history files
directly from VS Code's workspace root directory, workspaceStorage.

The workspaceStorage directory is located at:

    C:/Users/<username>/AppData/Roaming/Code/User/workspaceStorage on Windows;
    /Users/<username>/Library/Application Support/Code/User/workspaceStorage on macOS.

Inside workspaceStorage, each subfolder—named by a hash—corresponds to a workspace
(including those automatically created by VS Code). To identify which is which,
open a folder and inspect its workspace.json: it lists the associated project path.
Note that a single project can have multiple workspace entries. Within the
correct workspace folder, look for a chatSessions directory, where your Copilot
Chat histories are saved as JSON files. You can copy those files elsewhere and
then use Chat: Import Chat… to load them into another workspace.
"""

from __future__ import annotations

import json
import pathlib
import platform
import datetime
from typing import List, Optional

from base_chat_finder import ChatFinder, ChatSession, ChatMessage, ProjectInfo
from chat_message_parser import parse_copilot_messages


class CopilotChatFinder(ChatFinder):
    """Find and extract GitHub Copilot chat histories from VS Code."""

    @property
    def name(self) -> str:
        return "Copilot"

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

    def _extract_workspace_path_from_json(self, ws_json_path: pathlib.Path) -> Optional[str]:
        """Extract a file system path from workspace.json if present.

        Looks for strings starting with file:// or common keys that contain paths.
        """
        try:
            raw = json.loads(ws_json_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        def walk(obj) -> Optional[str]:
            if isinstance(obj, str):
                if obj.startswith("file://"):
                    return obj.split("file://", 1)[1]
                # sometimes paths may be plain strings
                if obj.startswith("/") or (len(obj) > 1 and obj[1] == ':'):
                    return obj
                return None
            if isinstance(obj, dict):
                for v in obj.values():
                    p = walk(v)
                    if p:
                        return p
            if isinstance(obj, list):
                for v in obj:
                    p = walk(v)
                    if p:
                        return p
            return None

        return walk(raw)

    def find_chat_sessions(self) -> List[ChatSession]:
        """Scan workspaceStorage and return list of Copilot chat sessions."""
        storage_root = self.storage_root
        if not storage_root or not storage_root.exists():
            return []

        results: List[ChatSession] = []

        for ws_dir in storage_root.iterdir():
            if not ws_dir.is_dir():
                continue

            # Extract project info from workspace.json
            project_info = ProjectInfo(name="(unknown)", root_path="(unknown)")
            workspace_json = ws_dir / "workspace.json"
            if workspace_json.exists():
                path_found = self._extract_workspace_path_from_json(workspace_json)
                if path_found:
                    project_info = ProjectInfo(
                        name=pathlib.Path(path_found).name,
                        root_path=path_found
                    )

            # Look for chat sessions directory
            chat_dir = ws_dir / "chatSessions"
            if not chat_dir.exists() or not chat_dir.is_dir():
                continue

            # Process each JSON file in chatSessions
            for jf in sorted(chat_dir.glob("*.json")):
                try:
                    raw = json.loads(jf.read_text(encoding="utf-8"))
                except Exception:
                    continue

                # Extract messages using the parser
                # This will extract from both simple messages and detailed requests/responses
                messages: List[ChatMessage] = parse_copilot_messages(raw)

                session = ChatSession(
                    project=project_info,
                    session_id=jf.stem,
                    messages=messages,
                    date=datetime.datetime.fromtimestamp(jf.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    file_path=str(jf),
                    workspace_id=ws_dir.name,
                    raw_data=raw
                )

                results.append(session)

        return results

    def extract_chats(self) -> List[dict]:
        """Extract chats with copilot-specific raw data field name."""
        sessions = self.find_chat_sessions()
        chats = []
        for session in sessions:
            chat_dict = session.to_dict()
            # Rename raw_data to copilot_raw for consistency with original format
            if "raw_data" in chat_dict:
                chat_dict["copilot_raw"] = chat_dict.pop("raw_data")
            chats.append(chat_dict)
        return chats


def find_copilot_chats() -> List[dict]:
    """Legacy function for backwards compatibility."""
    finder = CopilotChatFinder()
    return finder.extract_chats()


def save_copilot_chats(output_path: pathlib.Path) -> List[dict]:
    """Legacy function for backwards compatibility."""
    finder = CopilotChatFinder()
    return finder.save_to_file(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract GitHub Copilot chatSessions from VS Code workspaceStorage")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("copilot_chats.json"), help="Output JSON file")
    args = parser.parse_args()

    finder = CopilotChatFinder()
    chats = finder.save_to_file(args.out)
    print(f"Extracted {len(chats)} copilot chat sessions to {args.out}")
