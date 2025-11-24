#!/usr/bin/env python3
"""
Find and extract all Cursor chat histories from a user's system.

This script locates all workspace and session databases and extracts chat data
from Cursor's SQLite storage.
"""

from __future__ import annotations

import json
import pathlib
import platform
import datetime
import sqlite3
import logging
import os
from typing import List, Optional, Dict, Any, Iterable, Tuple
from collections import defaultdict

from base_chat_finder import ChatFinder, ChatSession, ChatMessage, ProjectInfo
from chat_message_parser import parse_cursor_messages

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CursorChatFinder(ChatFinder):
    """Find and extract Cursor chat histories from SQLite databases."""

    @property
    def name(self) -> str:
        return "Cursor"

    def get_storage_root(self) -> Optional[pathlib.Path]:
        """Return the path to Cursor's storage directory."""
        home = pathlib.Path.home()
        system = platform.system()

        if system == "Darwin":
            return home / "Library" / "Application Support" / "Cursor"
        elif system == "Windows":
            return home / "AppData" / "Roaming" / "Cursor"
        elif system == "Linux":
            return home / ".config" / "Cursor"
        else:
            raise RuntimeError(f"Unsupported OS: {system}")

    def _load_json_from_db(self, cur: sqlite3.Cursor, table: str, key: str) -> Optional[Any]:
        """Load and parse JSON value from a database table."""
        cur.execute(f"SELECT value FROM {table} WHERE key=?", (key,))
        row = cur.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except Exception as e:
                logger.debug(f"Failed to parse JSON for {key}: {e}")
        return None

    def _iter_bubbles_from_disk_kv(self, db: pathlib.Path) -> Iterable[Tuple[str, str, str, str]]:
        """Yield (composerId, role, text, db_path) from cursorDiskKV table."""
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            cur = con.cursor()
            # Check if table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'")
            if not cur.fetchone():
                con.close()
                return

            cur.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'bubbleId:%'")
        except sqlite3.DatabaseError as e:
            logger.debug(f"Database error with {db}: {e}")
            return

        db_path_str = str(db)

        for k, v in cur.fetchall():
            try:
                if v is None:
                    continue

                b = json.loads(v)
            except Exception as e:
                logger.debug(f"Failed to parse bubble JSON for key {k}: {e}")
                continue

            txt = (b.get("text") or b.get("richText") or "").strip()
            if not txt:
                continue
            role = "user" if b.get("type") == 1 else "assistant"
            composerId = k.split(":")[1]  # Format is bubbleId:composerId:bubbleId
            yield composerId, role, txt, db_path_str

        con.close()

    def _iter_composer_data(self, db: pathlib.Path) -> Iterable[Tuple[str, dict, str]]:
        """Yield (composerId, composerData, db_path) from cursorDiskKV table."""
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            cur = con.cursor()
            # Check if table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'")
            if not cur.fetchone():
                con.close()
                return

            cur.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'")
        except sqlite3.DatabaseError as e:
            logger.debug(f"Database error with {db}: {e}")
            return

        db_path_str = str(db)

        for k, v in cur.fetchall():
            try:
                if v is None:
                    continue

                composer_data = json.loads(v)
                composer_id = k.split(":")[1]
                yield composer_id, composer_data, db_path_str

            except Exception as e:
                logger.debug(f"Failed to parse composer data for key {k}: {e}")
                continue

        con.close()

    def _extract_project_info(self, db: pathlib.Path) -> ProjectInfo:
        """Extract project information from workspace database."""
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            cur = con.cursor()

            # Get file paths from history entries
            ents = self._load_json_from_db(cur, "ItemTable", "history.entries") or []

            # Extract file paths from history entries
            paths = []
            for e in ents:
                resource = e.get("editor", {}).get("resource", "")
                if resource and resource.startswith("file:///"):
                    paths.append(resource[len("file:///"):])

            # If we found file paths, extract the project name
            if paths:
                common_prefix = os.path.commonprefix(paths)
                last_separator_index = common_prefix.rfind('/')
                if last_separator_index > 0:
                    project_root = common_prefix[:last_separator_index]
                    project_name = pathlib.Path(project_root).name
                    con.close()
                    return ProjectInfo(name=project_name, root_path="/" + project_root.lstrip('/'))

            con.close()
        except Exception as e:
            logger.debug(f"Error extracting project info from {db}: {e}")

        return ProjectInfo(name="(unknown)", root_path="(unknown)")

    def _iter_workspaces(self) -> Iterable[Tuple[str, pathlib.Path]]:
        """Yield (workspace_id, db_path) for each workspace."""
        base = self.storage_root
        if not base:
            return

        ws_root = base / "User" / "workspaceStorage"
        if not ws_root.exists():
            return

        for folder in ws_root.iterdir():
            db = folder / "state.vscdb"
            if db.exists():
                yield folder.name, db

    def _get_global_storage_path(self) -> Optional[pathlib.Path]:
        """Return path to the global storage state.vscdb."""
        base = self.storage_root
        if not base:
            return None

        global_db = base / "User" / "globalStorage" / "state.vscdb"
        if global_db.exists():
            return global_db

        # Legacy paths
        g_dirs = [
            base / "User" / "globalStorage" / "cursor.cursor",
            base / "User" / "globalStorage" / "cursor"
        ]
        for d in g_dirs:
            if d.exists():
                for file in d.glob("*.sqlite"):
                    return file

        return None

    def find_chat_sessions(self) -> List[ChatSession]:
        """Find and extract all Cursor chat sessions."""
        # Maps to track workspaces, composers, and sessions
        ws_proj: Dict[str, ProjectInfo] = {}
        comp_meta: Dict[str, Dict[str, Any]] = {}
        comp2ws: Dict[str, str] = {}
        sessions: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"messages": []})

        # 1. Process workspace DBs first
        logger.debug("Processing workspace databases...")
        for ws_id, db in self._iter_workspaces():
            logger.debug(f"Processing workspace {ws_id} - {db}")
            ws_proj[ws_id] = self._extract_project_info(db)

            # Extract composer metadata
            try:
                con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                cur = con.cursor()
                cd = self._load_json_from_db(cur, "ItemTable", "composer.composerData") or {}
                for c in cd.get("allComposers", []):
                    cid = c["composerId"]
                    comp_meta[cid] = {
                        "title": c.get("name", "(untitled)"),
                        "createdAt": c.get("createdAt"),
                        "lastUpdatedAt": c.get("lastUpdatedAt")
                    }
                    comp2ws[cid] = ws_id

                # Extract messages from composer data in ItemTable
                for comp in cd.get("allComposers", []):
                    cid = comp.get("composerId")
                    messages = comp.get("messages", [])
                    for msg in messages:
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role and content:
                            sessions[cid]["messages"].append({"role": role, "content": content})
                            if "db_path" not in sessions[cid]:
                                sessions[cid]["db_path"] = str(db)

                con.close()
            except Exception as e:
                logger.debug(f"Error processing workspace {ws_id}: {e}")

        # 2. Process global storage
        global_db = self._get_global_storage_path()
        if global_db:
            logger.debug(f"Processing global storage: {global_db}")

            # Extract bubbles from cursorDiskKV
            for cid, role, text, db_path in self._iter_bubbles_from_disk_kv(global_db):
                sessions[cid]["messages"].append({"role": role, "content": text})
                if "db_path" not in sessions[cid]:
                    sessions[cid]["db_path"] = db_path
                if cid not in comp_meta:
                    comp_meta[cid] = {"title": f"Chat {cid[:8]}", "createdAt": None, "lastUpdatedAt": None}
                    comp2ws[cid] = "(global)"

            # Extract composer data
            for cid, data, db_path in self._iter_composer_data(global_db):
                if cid not in comp_meta:
                    created_at = data.get("createdAt")
                    comp_meta[cid] = {
                        "title": f"Chat {cid[:8]}",
                        "createdAt": created_at,
                        "lastUpdatedAt": created_at
                    }
                    comp2ws[cid] = "(global)"

                if "db_path" not in sessions[cid]:
                    sessions[cid]["db_path"] = db_path

                # Extract conversation from composer data
                conversation = data.get("conversation", [])
                for msg in conversation:
                    msg_type = msg.get("type")
                    if msg_type is None:
                        continue

                    # Type 1 = user, Type 2 = assistant
                    role = "user" if msg_type == 1 else "assistant"
                    content = msg.get("text", "")
                    if content and isinstance(content, str):
                        sessions[cid]["messages"].append({"role": role, "content": content})

        # 3. Build final list of ChatSession objects
        results: List[ChatSession] = []
        for cid, data in sessions.items():
            if not data["messages"]:
                continue

            ws_id = comp2ws.get(cid, "(unknown)")
            project = ws_proj.get(ws_id, ProjectInfo(name="(unknown)", root_path="(unknown)"))
            meta = comp_meta.get(cid, {"title": "(untitled)", "createdAt": None, "lastUpdatedAt": None})

            # Convert messages to ChatMessage objects using the parser
            messages = parse_cursor_messages(data["messages"])

            # Format date
            created_at = meta.get("createdAt")
            if created_at and isinstance(created_at, (int, float)):
                date = datetime.datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d %H:%M:%S")
            else:
                date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            session = ChatSession(
                project=project,
                session_id=cid,
                messages=messages,
                date=date,
                file_path=data.get("db_path", ""),
                workspace_id=ws_id
            )

            results.append(session)

        # Sort by last updated time if available
        results.sort(
            key=lambda s: comp_meta.get(s.session_id, {}).get("lastUpdatedAt") or 0,
            reverse=True
        )

        return results


def extract_all_chats() -> List[Dict[str, Any]]:
    """Legacy function for backwards compatibility."""
    finder = CursorChatFinder()
    return finder.extract_chats()


def save_all_chats(output_path: pathlib.Path) -> List[Dict[str, Any]]:
    """Legacy function for backwards compatibility."""
    finder = CursorChatFinder()
    return finder.save_to_file(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract all Cursor chat histories")
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path("cursor_chats.json"),
        help="Output JSON file (default: cursor_chats.json)"
    )
    args = parser.parse_args()

    finder = CursorChatFinder()
    chats = finder.save_to_file(args.out)
    print(f"Extracted {len(chats)} chat sessions to {args.out}")
