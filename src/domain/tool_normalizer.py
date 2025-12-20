#!/usr/bin/env python3
"""
Tool normalization module for standardizing tool usage across different AI types.
Provides unified tool name, input, and output normalization.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Tool name mappings for each AI type
TOOL_NAME_MAPPINGS = {
    "cursor": {
        # Read operations
        "read_file": "read",
        "codebase_search": "read",
        "grep": "read",
        "read_lints": "read",
        "list_dir": "read",
        "glob_file_search": "read",
        # Delete operations
        "delete_file": "delete",
        # Update operations
        "search_replace": "update",
        # Create operations
        "write": "create",
        # Terminal operations
        "run_terminal_cmd": "terminal",
        "terminal_command": "terminal",
        # Todo operations
        "todo_write": "todo",
        "create_plan": "todo",
        # Web operations
        "web_search": "web_request",
        # Test tools
        "test_tool": "read",
        "file_search": "read",
        "code_execution": "terminal",
        "test_runner": "terminal",
        "api_call": "read",
        "command": "terminal",
        "search": "read",
        "legacy_tool": "read",
        "empty_tool": "read",
        "helper_tool": "read",
    },
    "copilot": {
        # Update operations
        "codeBlock": "update",
        # Read operations
        "copilot_readFile": "read",
        "copilot_getErrors": "read",
        "copilot_findFiles": "read",
        "copilot_findTextInFiles": "read",
        # Todo operations
        "manage_todo_list": "todo",
        # Terminal operations
        "run_in_terminal": "terminal",
        # Skip these
        "copilot_applyPatch": None,
    },
    "claude": {
        # Create operations
        "Write": "create",
        # Todo operations
        "Task": "todo",
        "TodoWrite": "todo",
        # Terminal operations
        "Bash": "terminal",
        # Read operations
        "Read": "read",
        "Grep": "read",
        "Glob": "read",
        # Glob operations
        "Edit": "update",
        # Web operations
        "WebFetch": "web_request",
        # Test tools
        "test_tool": "read"
    }
}


def tool_name_normalization(ai_type: str, tool_name: str) -> Optional[str]:
    """
    Normalize tool name from AI-specific format to common format.
    
    Args:
        ai_type: Type of AI (cursor, copilot, or claude)
        tool_name: Original tool name from the AI
        
    Returns:
        Normalized tool name, or None if tool should be skipped
    """
    ai_type = ai_type.lower()
    
    if ai_type not in TOOL_NAME_MAPPINGS:
        logger.warning(f"Unknown AI type: {ai_type}, skipping tool: {tool_name}")
        return None
    
    mapping = TOOL_NAME_MAPPINGS[ai_type]
    normalized_name = mapping.get(tool_name)
    
    if normalized_name is None:
        # Check if it's explicitly mapped to None (should skip)
        if tool_name in mapping:
            logger.info(f"Skipped tool: {tool_name} (AI type: {ai_type})")
            return None
        # Tool not in mapping at all
        logger.warning(f"Skipped tool: {tool_name} (AI type: {ai_type}) - no mapping found")
        return None
    
    return normalized_name


# Tool input/output normalization is now handled by each finder's specific methods.
# Each finder should implement its own _normalize_tool_input and _normalize_tool_output methods
# and call tool_name_normalization from this module.

