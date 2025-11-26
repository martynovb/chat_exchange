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
import sqlite3
from typing import List, Optional, Dict, Any

"""This module exports Cursor chat data from vscdb/sqlite files as-is, merging multiple files."""


class CursorChatFinder:
    """Find and extract Cursor chat histories from SQLite databases."""

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
            return None

    def find_all_database_files(self) -> List[pathlib.Path]:
        """Find all vscdb and sqlite database files.
        
        Returns:
            List of paths to all database files (workspace and global storage).
        """
        base = self.get_storage_root()
        if not base or not base.exists():
            return []

        db_files: List[pathlib.Path] = []

        # Find workspace databases
        ws_root = base / "User" / "workspaceStorage"
        if ws_root.exists():
            for folder in ws_root.iterdir():
                db = folder / "state.vscdb"
                if db.exists():
                    db_files.append(db)

        # Find global storage database
        global_db = base / "User" / "globalStorage" / "state.vscdb"
        if global_db.exists():
            db_files.append(global_db)

        # Check legacy paths
        g_dirs = [
            base / "User" / "globalStorage" / "cursor.cursor",
            base / "User" / "globalStorage" / "cursor"
        ]
        for d in g_dirs:
            if d.exists():
                db_files.extend(d.glob("*.sqlite"))

        return sorted(db_files)

    def _extract_database_data(self, db_path: pathlib.Path) -> Dict[str, Any]:
        """Extract all relevant data from a database file.
        
        Args:
            db_path: Path to the database file.
            
        Returns:
            Dictionary containing all extracted data from the database.
        """
        data: Dict[str, Any] = {
            "tables": {}
        }

        try:
            # Use read-only mode to avoid locking issues
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = con.cursor()

            # Get all table names
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]

            # Extract data from each table
            for table_name in tables:
                try:
                    # Get table schema
                    cur.execute(f"PRAGMA table_info({table_name})")
                    columns = [row[1] for row in cur.fetchall()]

                    # Get all rows from the table
                    cur.execute(f"SELECT * FROM {table_name}")
                    rows = cur.fetchall()

                    # Convert rows to dictionaries
                    table_data = []
                    for row in rows:
                        row_dict = {}
                        for i, col_name in enumerate(columns):
                            value = row[i]
                            # Try to parse JSON values if they look like JSON
                            if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                                try:
                                    value = json.loads(value)
                                except (json.JSONDecodeError, ValueError):
                                    pass
                            row_dict[col_name] = value
                        table_data.append(row_dict)

                    data["tables"][table_name] = {
                        "columns": columns,
                        "rows": table_data,
                        "row_count": len(table_data)
                    }
                except Exception:
                    # Skip tables that can't be read
                    continue

            con.close()
        except Exception:
            # Return empty data if database can't be read
            pass

        return data

    def export_chats(self, output_path: pathlib.Path) -> Dict[str, Any]:
        """Export all Cursor chat databases, merging them into a single JSON structure.
        
        Args:
            output_path: Path to save the merged JSON file.
            
        Returns:
            Dictionary containing the merged chat data.
        """
        db_files = self.find_all_database_files()
        
        if not db_files:
            result = {"chats": []}
            output_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            return result

        # Extract data from all database files
        merged_chats: List[Dict[str, Any]] = []
        
        for db_file in db_files:
            try:
                # Extract raw data from the database
                db_data = self._extract_database_data(db_file)
                
                # Add metadata about the source file
                chat_entry = {
                    "file_path": str(db_file),
                    "file_name": db_file.name,
                    "workspace_id": db_file.parent.name if db_file.parent.name != "globalStorage" else "(global)",
                    "data": db_data
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


def extract_all_chats() -> Dict[str, Any]:
    """Find all Cursor chat database files and return merged data."""
    finder = CursorChatFinder()
    db_files = finder.find_all_database_files()
    
    merged_chats: List[Dict[str, Any]] = []
    for db_file in db_files:
        try:
            db_data = finder._extract_database_data(db_file)
            chat_entry = {
                "file_path": str(db_file),
                "file_name": db_file.name,
                "workspace_id": db_file.parent.name if db_file.parent.name != "globalStorage" else "(global)",
                "data": db_data
            }
            merged_chats.append(chat_entry)
        except Exception:
            continue
    
    return {"chats": merged_chats, "total_count": len(merged_chats)}


def save_all_chats(output_path: pathlib.Path) -> Dict[str, Any]:
    """Export and save all Cursor chats to a JSON file."""
    finder = CursorChatFinder()
    return finder.export_chats(output_path)


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
    result = finder.export_chats(args.out)
    print(f"Extracted {result['total_count']} chat database files to {args.out}")
