#!/usr/bin/env python3
"""
Unified chat finder script.
Supports listing and exporting chats from Claude, Copilot, and Cursor.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from claude_chat_finder import ClaudeChatFinder
from copilot_chat_finder import CopilotChatFinder
from cursor_chats_finder import CursorChatFinder


def get_finder(finder_type: str):
    """Get the appropriate finder instance based on type.
    
    Args:
        finder_type: One of 'claude', 'copilot', 'cursor'
        
    Returns:
        Finder instance
        
    Raises:
        ValueError: If finder_type is invalid
    """
    finder_type = finder_type.lower()
    
    if finder_type == "claude":
        return ClaudeChatFinder()
    elif finder_type == "copilot":
        return CopilotChatFinder()
    elif finder_type == "cursor":
        return CursorChatFinder()
    else:
        raise ValueError(f"Unknown finder type: {finder_type}. Must be one of: claude, copilot, cursor")


def main():
    parser = argparse.ArgumentParser(
        description="Find and export chats from Claude, Copilot, or Cursor"
    )
    parser.add_argument(
        "--type",
        type=str,
        required=True,
        choices=["claude", "copilot", "cursor"],
        help="Type of chat finder to use"
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="Export a specific chat by ID"
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=None,
        help="Output JSON file for exporting all chats (only used with --out, not --export)"
    )
    
    args = parser.parse_args()
    
    try:
        finder = get_finder(args.type)
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    
    # Two-step approach: --export=chat_id exports specific chat
    if args.export:
        try:
            chat_data = finder.parse_chat_by_id(args.export)
            # Save single chat to results folder
            output_path = finder._get_default_output_path(f"{args.type}_chat_{args.export[:8]}.json")
            output_path.write_text(
                json.dumps(chat_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"Exported chat {args.export} to {output_path}")
        except ValueError as e:
            print(f"Error: {e}")
            return 1
    # List mode: no --export and no --out prints all chats with IDs
    elif args.out is None:
        metadata_list = finder.get_chat_metadata_list()
        print(f"Found {len(metadata_list)} chats:")
        for chat in metadata_list:
            print(f"  {chat['id']} - \"{chat['title']}\" ({chat['date']})")
    # Export all mode: --out specified exports all chats
    else:
        # Ensure parent directory exists
        finder._ensure_output_dir(args.out)
        
        # Use the export_chats method if available
        if hasattr(finder, 'export_chats'):
            result = finder.export_chats(args.out)
            print(f"Extracted {len(result)} {args.type} chat sessions to {args.out}")
        else:
            print(f"Error: {args.type} finder does not support bulk export")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


