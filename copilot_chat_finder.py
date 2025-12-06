from __future__ import annotations

import json
import pathlib
import platform
import datetime
import time
import re
from typing import List, Optional, Dict, Any

"""This module exports Copilot chat JSON files in the new standardized format."""


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

    def _get_timezone_offset(self) -> str:
        """Get timezone offset string like 'UTC+4'."""
        try:
            # Get local timezone offset
            offset_seconds = time.timezone if (time.daylight == 0) else time.altzone
            offset_hours = abs(offset_seconds) // 3600
            sign = '+' if offset_seconds <= 0 else '-'
            return f"UTC{sign}{offset_hours}"
        except Exception:
            return "UTC+0"  # Default fallback

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
            return f"```{file_path}```"
        
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
                            
                            # Increment timestamp for tool message
                            current_time_ms += message_interval_ms
                            tool_timestamp = self._timestamp_ms_to_iso(current_time_ms)
                            
                            messages.append({
                                "role": "assistant",
                                "type": "tool",
                                "content": {
                                    "toolName": "codeBlock",
                                    "toolInput": tool_input,
                                    "toolOutput": tool_output
                                },
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
                                
                                # Increment timestamp for tool message
                                current_time_ms += message_interval_ms
                                tool_timestamp = self._timestamp_ms_to_iso(current_time_ms)
                                
                                messages.append({
                                    "role": "assistant",
                                    "type": "tool",
                                    "content": {
                                        "toolName": tool_id,
                                        "toolInput": tool_input if tool_input else {},
                                        "toolOutput": tool_output
                                    },
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
    return finder.export_chats(pathlib.Path("copilot_chats.json"))


def save_copilot_chats(output_path: pathlib.Path) -> List[Dict[str, Any]]:
    """Export and save all Copilot chats to a JSON file in new format."""
    finder = CopilotChatFinder()
    return finder.export_chats(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract GitHub Copilot chatSessions from VS Code workspaceStorage")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("copilot_chats.json"), help="Output JSON file")
    args = parser.parse_args()

    finder = CopilotChatFinder()
    result = finder.export_chats(args.out)
    print(f"Extracted {len(result)} copilot chat sessions to {args.out}")
