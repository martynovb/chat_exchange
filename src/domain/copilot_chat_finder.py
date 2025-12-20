from __future__ import annotations

import json
import os
import pathlib
import platform
import datetime
import time
import re
from typing import List, Optional, Dict, Any

from .base_chat_finder import BaseChatFinder
from .tool_normalizer import tool_name_normalization

"""This module exports Copilot chat JSON files in the new standardized format."""


class CopilotChatFinder(BaseChatFinder):
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

    def _generate_chat_id(self, file_path_or_key: Any) -> str:
        """Generate unique chat ID from file path or database key.
        
        Args:
            file_path_or_key: File path (pathlib.Path) for Copilot chats
            
        Returns:
            Unique chat ID string.
        """
        if not isinstance(file_path_or_key, pathlib.Path):
            return ""
        
        # Create unique key from workspace_id and file name
        workspace_id = file_path_or_key.parent.parent.name
        file_name = file_path_or_key.name
        unique_key = f"{workspace_id}/{file_name}"
        
        return self._generate_unique_id(unique_key)

    def _extract_metadata_lightweight(self, file_path_or_key: Any) -> Optional[Dict[str, Any]]:
        """Extract minimal metadata without parsing full content.
        
        Args:
            file_path_or_key: File path (pathlib.Path) to JSON chat file
            
        Returns:
            Dict with keys: id, title, date, file_path
            Returns None if metadata cannot be extracted.
        """
        if not isinstance(file_path_or_key, pathlib.Path):
            return None
        
        try:
            chat_id = self._generate_chat_id(file_path_or_key)
            
            # Read JSON file but only extract metadata fields
            raw_data = json.loads(file_path_or_key.read_text(encoding="utf-8"))
            
            # Extract title
            title = raw_data.get("customTitle", "(untitled)")
            if not title or title == "(untitled)":
                session_id = raw_data.get("sessionId", "unknown")
                title = f"Chat {session_id[:8]}"
            
            # Extract creation date
            creation_date_ms = raw_data.get("creationDate")
            if creation_date_ms:
                timestamp_sec = creation_date_ms / 1000.0
                dt = datetime.datetime.fromtimestamp(timestamp_sec, tz=datetime.timezone.utc)
                date_str = dt.strftime("%Y-%m-%d")
            else:
                # Use file modification time as fallback
                try:
                    mtime = file_path_or_key.stat().st_mtime
                    dt = datetime.datetime.fromtimestamp(mtime)
                    date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            
            return {
                "id": chat_id,
                "title": title,
                "date": date_str,
                "file_path": str(file_path_or_key)
            }
        except Exception:
            return None

    def _parse_chat_full(self, file_path_or_key: Any) -> Optional[Dict[str, Any]]:
        """Parse full chat content.
        
        Args:
            file_path_or_key: File path (pathlib.Path) to JSON chat file
            
        Returns:
            Full chat dict with title, metadata, createdAt, messages.
            Returns None if chat cannot be parsed.
        """
        if not isinstance(file_path_or_key, pathlib.Path):
            return None
        
        try:
            raw_data = json.loads(file_path_or_key.read_text(encoding="utf-8"))
            workspace_id = file_path_or_key.parent.parent.name
            storage_root = self.get_storage_root()
            
            if not storage_root:
                return None
            
            transformed_chat = self._transform_chat_to_new_format(raw_data, workspace_id, storage_root)
            return transformed_chat
        except Exception:
            return None

    # get_chat_metadata_list and parse_chat_by_id are inherited from base class

    def _timestamp_ms_to_iso(self, timestamp_ms: Optional[int]) -> str:
        """Convert milliseconds timestamp to ISO format string."""
        if not timestamp_ms:
            return datetime.datetime.now(tz=datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Convert milliseconds to seconds
        timestamp_sec = timestamp_ms / 1000.0
        dt = datetime.datetime.fromtimestamp(timestamp_sec, tz=datetime.timezone.utc)
        return dt.isoformat().replace('+00:00', 'Z')

    def _extract_workspace_path_from_json(self, ws_json_path: pathlib.Path) -> Optional[str]:
        """Extract a file system path from workspace.json if present."""
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

    def _extract_project_name(self, workspace_id: str, storage_root: pathlib.Path) -> str:
        """Extract project name from workspace directory."""
        ws_dir = storage_root / workspace_id
        workspace_json = ws_dir / "workspace.json"
        
        if workspace_json.exists():
            path_found = self._extract_workspace_path_from_json(workspace_json)
            if path_found:
                return pathlib.Path(path_found).name
        
        return "Unknown Project"

    def _extract_text_from_value(self, value_obj: Any) -> str:
        """Extract text content from a value object (can be string or dict with value field)."""
        if isinstance(value_obj, str):
            return value_obj
        elif isinstance(value_obj, dict):
            return value_obj.get("value", "")
        return ""

    def _extract_file_path_from_inline_reference(self, inline_ref: Dict[str, Any]) -> Optional[str]:
        """Extract file path from inlineReference entity."""
        if not isinstance(inline_ref, dict):
            return None
        
        # Check for direct fsPath
        fs_path = inline_ref.get("fsPath")
        if fs_path:
            return fs_path
        
        # Check for path
        path = inline_ref.get("path")
        if path:
            return path
        
        # Check for location.uri.fsPath (for code references)
        location = inline_ref.get("location", {})
        if isinstance(location, dict):
            uri = location.get("uri", {})
            if isinstance(uri, dict):
                fs_path = uri.get("fsPath")
                if fs_path:
                    return fs_path
                path = uri.get("path")
                if path:
                    return path
        
        return None

    def _convert_inline_reference_to_markdown(self, inline_ref: Dict[str, Any]) -> str:
        """Convert inlineReference to markdown file reference format."""
        file_path = self._extract_file_path_from_inline_reference(inline_ref)
        if file_path:
            return f"`{file_path}`"
        
        # If no file path, try to use name
        name = inline_ref.get("name", "")
        if name:
            return f"`{name}`"
        
        return ""

    def _extract_tool_input(self, tool_invocation: Dict[str, Any], tool_id: str) -> Dict[str, Any]:
        """Extract tool input from tool invocation."""
        tool_input: Dict[str, Any] = {}
        
        # Extract from invocationMessage
        invocation_msg = tool_invocation.get("invocationMessage")
        if isinstance(invocation_msg, dict):
            # Extract query/pattern from value for search tools
            value = invocation_msg.get("value", "")
            if tool_id == "copilot_findFiles" and value:
                # Try to extract pattern from message like "Searching for files matching `**/*.{py,json,md}`"
                pattern_match = re.search(r'`([^`]+)`', value)
                if pattern_match:
                    tool_input["query"] = pattern_match.group(1)
                else:
                    tool_input["query"] = value
            
            # Extract file paths from uris
            uris = invocation_msg.get("uris", {})
            if uris:
                file_paths = []
                for uri_obj in uris.values():
                    if isinstance(uri_obj, dict):
                        path = uri_obj.get("fsPath") or uri_obj.get("path", "")
                        if path:
                            file_paths.append(path)
                if file_paths:
                    tool_input["files"] = file_paths if len(file_paths) > 1 else file_paths[0]
            
            # For copilot_readFile, try to extract file path from value if it contains a file reference
            if tool_id == "copilot_readFile" and value:
                # Try to extract file path from value (might be in format like "Reading file: path/to/file")
                # Or check if value itself is a file path
                if "/" in value or "\\" in value or value.endswith((".py", ".js", ".ts", ".json", ".md", ".txt", ".yaml", ".yml")):
                    # Might be a file path, try to extract it
                    # Look for common patterns
                    path_match = re.search(r'([a-zA-Z]:[\\/][^\s`]+|[\\/][^\s`]+\.\w+)', value)
                    if path_match:
                        tool_input["files"] = [path_match.group(1)]
                    else:
                        # If value looks like a path, use it directly
                        tool_input["files"] = [value]
        
        # Extract from resultDetails (for tools that return file lists)
        result_details = tool_invocation.get("resultDetails", [])
        if result_details:
            file_paths = []
            for item in result_details:
                if isinstance(item, dict):
                    path = item.get("fsPath") or item.get("path", "")
                    if path:
                        file_paths.append(path)
            if file_paths and "files" not in tool_input:
                tool_input["files"] = file_paths if len(file_paths) > 1 else file_paths[0]
        
        # For read operations, also check toolSpecificData or other fields that might contain file info
        if tool_id in ["copilot_readFile", "copilot_getErrors"] and not tool_input:
            # Check if toolSpecificData contains file information
            tool_specific = tool_invocation.get("toolSpecificData")
            if isinstance(tool_specific, dict):
                # Look for file paths in toolSpecificData
                if "file" in tool_specific:
                    file_path = tool_specific.get("file")
                    if file_path:
                        tool_input["files"] = [file_path] if isinstance(file_path, str) else file_path
                elif "path" in tool_specific:
                    file_path = tool_specific.get("path")
                    if file_path:
                        tool_input["files"] = [file_path] if isinstance(file_path, str) else file_path
        
        return tool_input

    def _extract_tool_output(self, tool_invocation: Dict[str, Any]) -> Any:
        """Extract tool output from tool invocation."""
        # If toolSpecificData exists, use it
        if "toolSpecificData" in tool_invocation:
            return tool_invocation["toolSpecificData"]
        
        # Otherwise use pastTenseMessage or invocationMessage
        past_tense = tool_invocation.get("pastTenseMessage")
        if isinstance(past_tense, dict):
            return past_tense.get("value", "")
        elif isinstance(past_tense, str):
            return past_tense
        
        invocation_msg = tool_invocation.get("invocationMessage")
        if isinstance(invocation_msg, str):
            return invocation_msg
        elif isinstance(invocation_msg, dict):
            return invocation_msg.get("value", "")
        
        return ""
    
    def _normalize_copilot_tool_input(self, tool_name: str, normalized_tool_name: str, tool_input: Any, tool_output: Any = None) -> Any:
        """
        Normalize tool input for Copilot-specific tools.
        
        Args:
            tool_name: Original tool name from Copilot
            normalized_tool_name: Normalized tool name
            tool_input: Original tool input
            tool_output: Original tool output (optional, needed for todo/terminal transformation)
            
        Returns:
            Normalized tool input
        """
        # Dispatch to tool-specific normalization methods
        if normalized_tool_name == "read":
            return self._normalize_copilot_read_input(tool_input)
        elif normalized_tool_name == "terminal":
            return self._normalize_copilot_terminal_input(tool_input, tool_output)
        elif normalized_tool_name == "update":
            return self._normalize_copilot_update_input(tool_input)
        elif normalized_tool_name == "todo":
            return self._normalize_copilot_todo_input(tool_input, tool_output)
        elif normalized_tool_name == "create":
            return self._normalize_copilot_create_input(tool_input)
        elif normalized_tool_name == "delete":
            return self._normalize_copilot_delete_input(tool_input)
        elif normalized_tool_name == "web_request":
            return self._normalize_copilot_web_request_input(tool_input)
        
        return tool_input
    
    def _normalize_copilot_read_input(self, tool_input: Any) -> Any:
        """Normalize read tool input for Copilot."""
        if isinstance(tool_input, dict):
            # Check if it has files array (Copilot format)
            if "files" in tool_input:
                files_value = tool_input["files"]
                # If it's already a list, return as-is
                if isinstance(files_value, list):
                    return files_value
                # If it's a single file path string, wrap in array
                elif isinstance(files_value, str):
                    return [files_value] if files_value else []
            # Check if it has query (for search operations)
            elif "query" in tool_input:
                # For search operations, we might not have files yet
                # Return empty array or handle query differently
                return []
            # Check if it has file_path (single file read)
            elif "file_path" in tool_input:
                file_path = tool_input["file_path"]
                return [file_path] if file_path else []
            # Check for relativeWorkspacePath (for consistency)
            elif "relativeWorkspacePath" in tool_input:
                relative_path = tool_input["relativeWorkspacePath"]
                return [relative_path] if relative_path else []
        
        # If it's already a string, wrap in array
        elif isinstance(tool_input, str):
            return [tool_input] if tool_input else []
        
        # If it's already a list, return as-is
        elif isinstance(tool_input, list):
            return tool_input
        
        return tool_input
    
    def _normalize_copilot_terminal_input(self, tool_input: Any, tool_output: Any) -> Any:
        """Normalize terminal tool input for Copilot."""
        if tool_output and isinstance(tool_output, dict):
            command_line = tool_output.get("commandLine", {})
            if isinstance(command_line, dict):
                original_command = command_line.get("original", "")
                if original_command:
                    return original_command
        # Fallback: if it's already a string, return as-is
        if isinstance(tool_input, str):
            return tool_input
        return tool_input
    
    def _normalize_copilot_update_input(self, tool_input: Any) -> Any:
        """Normalize update tool input for Copilot."""
        # Extract only the file name from path (similar to Claude/Cursor)
        if isinstance(tool_input, dict):
            # Check for file_path (Copilot format)
            if "file_path" in tool_input:
                file_path = tool_input["file_path"]
                if isinstance(file_path, str):
                    return os.path.basename(file_path)
            # Also check for relativeWorkspacePath (for consistency)
            elif "relativeWorkspacePath" in tool_input:
                relative_path = tool_input["relativeWorkspacePath"]
                if isinstance(relative_path, str):
                    return os.path.basename(relative_path)
        elif isinstance(tool_input, str):
            # If it's already a string, extract filename if it looks like a path
            return os.path.basename(tool_input)
        return tool_input
    
    def _normalize_copilot_todo_input(self, tool_input: Any, tool_output: Any) -> Any:
        """Normalize todo tool input for Copilot."""
        # Copilot stores todos in tool_output, so we need to transform it
        if tool_output and isinstance(tool_output, dict):
            todo_list = tool_output.get("todoList", [])
            if isinstance(todo_list, list) and len(todo_list) > 0:
                # Transform todoList to the normalized format
                todos = []
                for todo_item in todo_list:
                    if isinstance(todo_item, dict):
                        # Copilot uses "title" for the name, "description" for description
                        todo_name = todo_item.get("title", "")
                        # Skip todos with empty names
                        if todo_name and todo_name.strip():
                            # Map status: "not-started" -> "pending", others keep as-is
                            status = todo_item.get("status", "pending")
                            if status == "not-started":
                                status = "pending"
                            
                            todos.append({
                                "name": todo_name,
                                "status": status
                            })
                
                # If no valid todos, skip this tool entirely
                if not todos:
                    return None
                
                # Build result (no description for Copilot todos)
                return {
                    "todos": todos
                }
        
        # If tool_input has todo structure, normalize it like Cursor
        if isinstance(tool_input, dict):
            # Extract overview as description (skip if empty)
            description = tool_input.get("overview", "")
            if not description or not description.strip():
                description = None
            
            # Extract todos array and simplify (skip todos with empty names)
            todos = []
            todos_raw = tool_input.get("todos", [])
            if isinstance(todos_raw, list):
                for todo_item in todos_raw:
                    if isinstance(todo_item, dict):
                        todo_name = todo_item.get("content", "")
                        # Skip todos with empty names
                        if todo_name and todo_name.strip():
                            simplified_todo = {
                                "name": todo_name,
                                "status": todo_item.get("status", "")
                            }
                            todos.append(simplified_todo)
            
            # If no description and no valid todos, skip this tool entirely
            if description is None and not todos:
                return None
            
            # Build result, only include description if it's not empty
            result = {"todos": todos}
            if description is not None:
                result["description"] = description
            
            return result
        
        return tool_input
    
    def _normalize_copilot_create_input(self, tool_input: Any) -> Any:
        """Normalize create tool input for Copilot."""
        return tool_input
    
    def _normalize_copilot_delete_input(self, tool_input: Any) -> Any:
        """Normalize delete tool input for Copilot."""
        return tool_input
    
    def _normalize_copilot_web_request_input(self, tool_input: Any) -> Any:
        """Normalize web_request tool input for Copilot."""
        return tool_input
    
    def _normalize_copilot_tool_output(self, tool_name: str, normalized_tool_name: str, tool_output: Any, tool_input: Any = None) -> Any:
        """
        Normalize tool output for Copilot-specific tools.
        
        Args:
            tool_name: Original tool name from Copilot
            normalized_tool_name: Normalized tool name
            tool_output: Original tool output
            
        Returns:
            Normalized tool output
        """
        # Dispatch to tool-specific normalization methods
        if normalized_tool_name == "web_request":
            return self._normalize_copilot_web_request_output(tool_output)
        elif normalized_tool_name == "read":
            return self._normalize_copilot_read_output(tool_output)
        elif normalized_tool_name == "create":
            return self._normalize_copilot_create_output(tool_output)
        elif normalized_tool_name == "todo":
            return self._normalize_copilot_todo_output(tool_output)
        elif normalized_tool_name == "terminal":
            return self._normalize_copilot_terminal_output(tool_output)
        elif normalized_tool_name == "update":
            return self._normalize_copilot_update_output(tool_output, tool_input)
        elif normalized_tool_name == "delete":
            return self._normalize_copilot_delete_output(tool_output)
        
        return tool_output
    
    def _normalize_copilot_web_request_output(self, tool_output: Any) -> Any:
        """Normalize web_request tool output for Copilot."""
        return ""
    
    def _normalize_copilot_read_output(self, tool_output: Any) -> Any:
        """Normalize read tool output for Copilot."""
        return ""
    
    def _normalize_copilot_create_output(self, tool_output: Any) -> Any:
        """Normalize create tool output for Copilot."""
        return ""
    
    def _normalize_copilot_todo_output(self, tool_output: Any) -> Any:
        """Normalize todo tool output for Copilot."""
        return ""
    
    def _normalize_copilot_terminal_output(self, tool_output: Any) -> Any:
        """Normalize terminal tool output for Copilot."""
        return ""
    
    def _normalize_copilot_update_output(self, tool_output: Any, tool_input: Any = None) -> Any:
        """Normalize update tool output for Copilot."""
        # Copilot doesn't provide old content or diff information like Claude/Cursor
        # Since we can't generate a diff, return empty string to avoid showing full file content
        # (consistent with create tool behavior)
        return ""
    
    def _normalize_copilot_delete_output(self, tool_output: Any) -> Any:
        """Normalize delete tool output for Copilot."""
        return tool_output
    
    def _normalize_copilot_tool_usage(self, tool_name: str, tool_input: Any, tool_output: Any) -> Optional[Dict[str, Any]]:
        """
        Normalize a complete tool usage entry for Copilot.
        
        Args:
            tool_name: Original tool name from Copilot
            tool_input: Original tool input
            tool_output: Original tool output
            
        Returns:
            Normalized tool usage dict with keys: tool_name, tool_input, tool_output
            Returns None if tool should be skipped
        """
        # Normalize tool name using common function
        normalized_name = tool_name_normalization("copilot", tool_name)
        
        if normalized_name is None:
            return None
        
        # Apply Copilot-specific input/output normalization
        # For todo and terminal, pass tool_output to input normalization since Copilot stores data in output
        normalized_input = self._normalize_copilot_tool_input(tool_name, normalized_name, tool_input, tool_output)
        
        # If input normalization returns None, skip this tool entirely
        if normalized_input is None:
            return None
        
        normalized_output = self._normalize_copilot_tool_output(tool_name, normalized_name, tool_output, tool_input)
        
        return {
            "tool_name": normalized_name,
            "tool_input": normalized_input,
            "tool_output": normalized_output
        }

    def _transform_chat_to_new_format(self, raw_data: Dict[str, Any], workspace_id: str, storage_root: pathlib.Path) -> Optional[Dict[str, Any]]:
        """Transform a single chat from raw format to new standardized format."""
        # Extract title
        title = raw_data.get("customTitle", "(untitled)")
        if not title or title == "(untitled)":
            session_id = raw_data.get("sessionId", "unknown")
            title = f"Chat {session_id[:8]}"

        # Extract creation date
        creation_date_ms = raw_data.get("creationDate")
        created_at = self._timestamp_ms_to_iso(creation_date_ms)

        # Extract metadata
        responder_username = raw_data.get("responderUsername", "GitHub Copilot")
        project_name = self._extract_project_name(workspace_id, storage_root)
        
        metadata = {
            "model": responder_username,
            "chat_timezone": self._get_timezone_offset(),
            "Project": project_name
        }

        # Extract messages from requests
        messages: List[Dict[str, Any]] = []
        requests = raw_data.get("requests", [])
        
        # Base time for estimating message timestamps
        base_time_ms = creation_date_ms or int(time.time() * 1000)
        message_interval_ms = 15000  # 15 seconds between messages
        current_time_ms = base_time_ms

        for request in requests:
            # Extract user message
            user_message = request.get("message", {})
            user_text = user_message.get("text", "")
            if user_text:
                request_timestamp_ms = request.get("timestamp")
                if request_timestamp_ms:
                    current_time_ms = request_timestamp_ms
                
                user_timestamp = self._timestamp_ms_to_iso(current_time_ms)
                
                # Extract inputs (like attachments) from variableData
                inputs: Dict[str, Any] = {}
                variable_data = request.get("variableData", {})
                variables = variable_data.get("variables", [])
                if variables:
                    attachments = []
                    for var in variables:
                        if var.get("kind") == "file":
                            file_path = var.get("value", {})
                            if isinstance(file_path, dict):
                                fs_path = file_path.get("fsPath") or file_path.get("path", "")
                                if fs_path:
                                    attachments.append(fs_path)
                    if attachments:
                        inputs["attachment"] = attachments[0] if len(attachments) == 1 else attachments
                
                messages.append({
                    "role": "user",
                    "type": "text",
                    "content": user_text,
                    "timestamp": user_timestamp,
                    **({"inputs": inputs} if inputs else {})
                })

            # Extract assistant responses
            response = request.get("response", [])
            if response:
                i = 0
                while i < len(response):
                    entity = response[i]
                    
                    # Check for code block markers (```)
                    value = entity.get("value", "")
                    if isinstance(value, str) and "```" in value and "kind" not in entity:
                        # Start of code block - collect all entities until the closing ```
                        code_block_entities = []
                        i += 1  # Skip the opening marker
                        
                        # Collect all entities until the closing ```
                        while i < len(response):
                            next_entity = response[i]
                            next_value = next_entity.get("value", "")
                            
                            # Check if this is the closing ```
                            if isinstance(next_value, str) and "```" in next_value and "kind" not in next_entity:
                                # Found closing marker, skip it and process the code block
                                i += 1
                                break
                            
                            code_block_entities.append(next_entity)
                            i += 1
                        
                        # Extract code block information
                        file_path = None
                        code_content = None
                        
                        for code_entity in code_block_entities:
                            # Extract file path from codeblockUri
                            if code_entity.get("kind") == "codeblockUri":
                                uri = code_entity.get("uri", {})
                                if isinstance(uri, dict):
                                    file_path = uri.get("fsPath") or uri.get("path", "")
                            
                            # Extract code from textEditGroup
                            elif code_entity.get("kind") == "textEditGroup":
                                edits = code_entity.get("edits", [])
                                if edits and isinstance(edits, list) and len(edits) > 0:
                                    # Get the first edit group
                                    first_edit_group = edits[0]
                                    if isinstance(first_edit_group, list) and len(first_edit_group) > 0:
                                        first_edit = first_edit_group[0]
                                        if isinstance(first_edit, dict):
                                            code_content = first_edit.get("text", "")
                        
                        # Create codeBlock tool message if we have code
                        if code_content or file_path:
                            tool_input: Dict[str, Any] = {}
                            if file_path:
                                tool_input["file_path"] = file_path
                            
                            tool_output = code_content or ""
                            
                            # Normalize tool usage using Copilot-specific logic
                            normalized = self._normalize_copilot_tool_usage("codeBlock", tool_input, tool_output)
                            
                            if normalized:
                                # Increment timestamp for tool message
                                current_time_ms += message_interval_ms
                                tool_timestamp = self._timestamp_ms_to_iso(current_time_ms)
                                
                                messages.append({
                                    "role": "assistant",
                                    "type": "tool",
                                    "content": normalized,
                                    "timestamp": tool_timestamp
                                })
                        
                        continue
                    
                    # Skip entities with kind (except toolInvocationSerialized)
                    if "kind" in entity:
                        if entity.get("kind") == "toolInvocationSerialized":
                            # Extract tool invocation
                            tool_id = entity.get("toolId", "")
                            if tool_id:
                                tool_output = self._extract_tool_output(entity)
                                tool_input = self._extract_tool_input(entity, tool_id)
                                
                                # Normalize tool usage using Copilot-specific logic
                                normalized = self._normalize_copilot_tool_usage(tool_id, tool_input if tool_input else {}, tool_output)
                                
                                if normalized:
                                    # Increment timestamp for tool message
                                    current_time_ms += message_interval_ms
                                    tool_timestamp = self._timestamp_ms_to_iso(current_time_ms)
                                    
                                    messages.append({
                                        "role": "assistant",
                                        "type": "tool",
                                        "content": normalized,
                                        "timestamp": tool_timestamp
                                    })
                        # Skip other kinds (thinking, progressTaskSerialized, etc.)
                        i += 1
                        continue
                    
                    # Collect text blocks and inlineReferences together
                    # Entity without kind but with value - this is assistant text response
                    # Or inlineReference kind
                    if ("value" in entity and "kind" not in entity) or entity.get("kind") == "inlineReference":
                        # Start collecting a sequence of text and inlineReference entities
                        text_parts: List[str] = []
                        j = i
                        
                        # Collect consecutive text blocks and inlineReferences
                        while j < len(response):
                            current_entity = response[j]
                            current_kind = current_entity.get("kind")
                            
                            # Check if it's a text block (no kind, has value, not code block marker)
                            if "value" in current_entity and "kind" not in current_entity:
                                text_value = self._extract_text_from_value(current_entity.get("value"))
                                # Skip code block markers
                                if "```" in text_value:
                                    break
                                if text_value:
                                    text_parts.append(text_value)
                                j += 1
                            
                            # Check if it's an inlineReference
                            elif current_kind == "inlineReference":
                                inline_ref = current_entity.get("inlineReference", {})
                                if inline_ref:
                                    ref_markdown = self._convert_inline_reference_to_markdown(inline_ref)
                                    if ref_markdown:
                                        text_parts.append(ref_markdown)
                                j += 1
                            
                            # Stop if we hit something else (unless it's a kind we should skip)
                            else:
                                # Allow skipping certain kinds that don't break text flow
                                if current_kind in ["undoStop"]:
                                    j += 1
                                    continue
                                break
                        
                        # If we collected any text parts, create a message
                        if text_parts:
                            combined_text = "".join(text_parts)
                            # Increment timestamp for assistant message
                            current_time_ms += message_interval_ms
                            assistant_timestamp = self._timestamp_ms_to_iso(current_time_ms)
                            
                            messages.append({
                                "role": "assistant",
                                "type": "text",
                                "content": combined_text,
                                "timestamp": assistant_timestamp
                            })
                        
                        # Move past all collected entities
                        i = j
                        continue
                    
                    i += 1

        # Skip chats with no messages
        if not messages:
            return None

        return {
            "title": title,
            "metadata": metadata,
            "createdAt": created_at,
            "messages": messages
        }

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

    def export_chats(self, output_path: pathlib.Path) -> List[Dict[str, Any]]:
        """Export all Copilot chat JSON files in the new standardized format.
        
        Args:
            output_path: Path to save the merged JSON file.
            
        Returns:
            List of transformed chat dictionaries.
        """
        chat_files = self.find_all_chat_files()
        storage_root = self.get_storage_root()
        
        if not chat_files or not storage_root:
            result: List[Dict[str, Any]] = []
            output_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            return result

        # Transform all chats to new format
        transformed_chats: List[Dict[str, Any]] = []
        
        for chat_file in chat_files:
            try:
                raw_data = json.loads(chat_file.read_text(encoding="utf-8"))
                workspace_id = chat_file.parent.parent.name
                
                transformed_chat = self._transform_chat_to_new_format(raw_data, workspace_id, storage_root)
                if transformed_chat:
                    transformed_chats.append(transformed_chat)
            except Exception:
                # Skip files that can't be read/parsed
                continue

        # Save to file
        output_path.write_text(
            json.dumps(transformed_chats, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        return transformed_chats


def find_copilot_chats() -> List[Dict[str, Any]]:
    """Find all Copilot chat files and return transformed data."""
    finder = CopilotChatFinder()
    output_path = finder._get_default_output_path("copilot_chats.json")
    return finder.export_chats(output_path)


def save_copilot_chats(output_path: pathlib.Path) -> List[Dict[str, Any]]:
    """Export and save all Copilot chats to a JSON file in new format."""
    finder = CopilotChatFinder()
    return finder.export_chats(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract GitHub Copilot chatSessions from VS Code workspaceStorage")
    parser.add_argument("--out", type=pathlib.Path, default=None, help="Output JSON file for exporting all chats (default: result/copilot_chats.json)")
    parser.add_argument("--export", type=str, default=None, help="Export a specific chat by ID")
    args = parser.parse_args()

    finder = CopilotChatFinder()
    
    # Two-step approach: --export=chat_id exports specific chat
    if args.export:
        try:
            chat_data = finder.parse_chat_by_id(args.export)
            # Save single chat to results folder
            output_path = finder._get_default_output_path(f"copilot_chat_{args.export[:8]}.json")
            output_path.write_text(
                json.dumps(chat_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"Exported chat {args.export} to {output_path}")
        except ValueError as e:
            print(f"Error: {e}")
            exit(1)
    # List mode: no arguments prints all chats with IDs
    elif args.out is None:
        metadata_list = finder.get_chat_metadata_list()
        print(f"Found {len(metadata_list)} chats:")
        for chat in metadata_list:
            print(f"  {chat['id']} - \"{chat['title']}\" ({chat['date']})")
    # Export all mode: --out specified exports all chats
    else:
        # Ensure parent directory exists
        finder._ensure_output_dir(args.out)
        result = finder.export_chats(args.out)
        print(f"Extracted {len(result)} copilot chat sessions to {args.out}")
