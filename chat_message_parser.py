#!/usr/bin/env python3
"""
Message parsers for different AI chat systems.

This module contains specialized parsers for extracting detailed message information
from Claude Code, GitHub Copilot, and Cursor chat data.
"""

from __future__ import annotations

import json
import ast
from typing import List, Dict, Any, Optional

from base_chat_finder import (
    ChatMessage,
    create_user_message,
    create_assistant_message,
    create_thinking_message,
    create_tool_use_message,
    create_tool_result_message,
    create_code_diff_message,
)


class ClaudeMessageParser:
    """Parser for Claude Code JSONL transcript messages."""

    @staticmethod
    def parse_transcript_objects(transcript_objects: List[Dict[str, Any]]) -> List[ChatMessage]:
        """Parse Claude Code transcript objects into structured messages.

        Claude stores messages in JSONL format where each object can be:
        - A message with role and content (content can be a list of typed blocks)
        - Each content block can be: text, thinking, tool_use, or tool_result
        """
        messages = []

        for obj in transcript_objects:
            if not isinstance(obj, dict):
                continue

            # Handle nested message structure (Claude JSONL format)
            if "message" in obj and isinstance(obj["message"], dict):
                obj = obj["message"]

            role = obj.get("role")
            content = obj.get("content")

            if not role or not content:
                continue

            # Normalize role
            if role in ["user", "human", "User"]:
                role = "user"
            elif role in ["assistant", "ai", "Assistant", "claude"]:
                role = "assistant"
            else:
                continue

            # Content can be a string, list, or dict
            if isinstance(content, str):
                # Try to parse if it looks like a stringified list
                if content.strip().startswith("["):
                    try:
                        content = ast.literal_eval(content)
                    except (ValueError, SyntaxError):
                        # If parsing fails, treat as regular text
                        if role == "user":
                            messages.append(create_user_message(content))
                        else:
                            messages.append(create_assistant_message(content))
                        continue
                else:
                    # Regular text content
                    if role == "user":
                        messages.append(create_user_message(content))
                    else:
                        messages.append(create_assistant_message(content))
                    continue

            # Content is a list of blocks
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type")

                        if block_type == "text":
                            text_content = block.get("text", "")
                            if text_content:
                                if role == "user":
                                    messages.append(create_user_message(text_content))
                                else:
                                    messages.append(create_assistant_message(text_content))

                        elif block_type == "thinking":
                            thinking_content = block.get("thinking", "")
                            if thinking_content:
                                messages.append(create_thinking_message(thinking_content))

                        elif block_type == "tool_use":
                            tool_name = block.get("name", "unknown")
                            tool_id = block.get("id")
                            tool_input = block.get("input", {})
                            messages.append(create_tool_use_message(
                                tool_name=tool_name,
                                tool_input=tool_input,
                                tool_id=tool_id
                            ))

                            # Check if this is a file modification tool
                            if tool_name in ["Write", "Edit"]:
                                file_path = tool_input.get("file_path", "")
                                if file_path:
                                    operation = "write" if tool_name == "Write" else "edit"
                                    new_content = tool_input.get("content") or tool_input.get("new_string")
                                    old_content = tool_input.get("old_string")
                                    messages.append(create_code_diff_message(
                                        file_path=file_path,
                                        operation=operation,
                                        new_content=new_content,
                                        old_content=old_content
                                    ))

                        elif block_type == "tool_result":
                            tool_use_id = block.get("tool_use_id", "")
                            result_content = block.get("content", "")
                            if isinstance(result_content, list):
                                # Join multiple content parts
                                result_parts = []
                                for part in result_content:
                                    if isinstance(part, dict):
                                        result_parts.append(part.get("text", "") or str(part))
                                    else:
                                        result_parts.append(str(part))
                                result_content = "\n".join(result_parts)
                            elif isinstance(result_content, dict):
                                result_content = str(result_content)

                            messages.append(create_tool_result_message(
                                tool_use_id=tool_use_id,
                                result_content=str(result_content)
                            ))

                    elif isinstance(block, str):
                        # Simple string in the list
                        if role == "user":
                            messages.append(create_user_message(block))
                        else:
                            messages.append(create_assistant_message(block))

            # Content is a dict
            elif isinstance(content, dict):
                content_str = content.get("text", "") or content.get("content", "") or str(content)
                if role == "user":
                    messages.append(create_user_message(content_str))
                else:
                    messages.append(create_assistant_message(content_str))

        return messages


class CopilotMessageParser:
    """Parser for GitHub Copilot chat messages."""

    @staticmethod
    def parse_chat_session(copilot_raw: Dict[str, Any]) -> List[ChatMessage]:
        """Parse Copilot chat session from raw data.

        Copilot stores chat data in a `requests` array where each request has:
        - message: The user's input
        - response: Array of response items with `kind` field (thinking, text, tool_use, etc.)
        """
        messages = []

        if not isinstance(copilot_raw, dict):
            return messages

        requests = copilot_raw.get("requests", [])

        for request in requests:
            if not isinstance(request, dict):
                continue

            # Parse user message
            user_message = request.get("message", {})
            if isinstance(user_message, dict):
                user_text = user_message.get("text", "")
                if user_text:
                    messages.append(create_user_message(user_text))

            # Parse response items
            response_items = request.get("response", [])
            if not isinstance(response_items, list):
                continue

            for item in response_items:
                if not isinstance(item, dict):
                    continue

                kind = item.get("kind", "")

                if kind == "thinking":
                    thinking_text = item.get("value", "")
                    if thinking_text:
                        messages.append(create_thinking_message(thinking_text))

                elif kind == "text":
                    text_content = item.get("value", "")
                    if text_content:
                        messages.append(create_assistant_message(text_content))

                elif kind == "markdownContent":
                    markdown = item.get("value", "")
                    if markdown:
                        messages.append(create_assistant_message(markdown))

                elif kind == "toolUse":
                    tool_name = item.get("toolName", "unknown")
                    tool_id = item.get("id")
                    tool_input = item.get("input", {})
                    messages.append(create_tool_use_message(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        tool_id=tool_id
                    ))

                elif kind == "editResponse":
                    # Code edit/diff
                    edits = item.get("edits", [])
                    for edit in edits:
                        if isinstance(edit, dict):
                            file_path = edit.get("filePath", "")
                            if file_path:
                                messages.append(create_code_diff_message(
                                    file_path=file_path,
                                    operation="edit",
                                    new_content=edit.get("newText"),
                                    old_content=edit.get("oldText")
                                ))

                elif kind == "codeBlockResponse":
                    # Code generation response
                    code_content = item.get("value", "")
                    language = item.get("language", "")
                    if code_content:
                        content = f"```{language}\n{code_content}\n```" if language else code_content
                        messages.append(create_assistant_message(content))

        return messages


class CursorMessageParser:
    """Parser for Cursor chat messages."""

    @staticmethod
    def parse_messages(raw_messages: List[Dict[str, str]]) -> List[ChatMessage]:
        """Parse Cursor messages.

        Cursor stores simple role/content messages. We'll try to detect
        tool usage patterns in the content if they exist.
        """
        messages = []

        for msg in raw_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if not role or not content:
                continue

            # Check if content contains tool usage patterns
            # (Cursor might embed this in the text)
            if "```" in content and role == "assistant":
                # This might be a code block - could be a code diff
                # For now, treat as assistant message
                messages.append(create_assistant_message(content))
            elif role == "user":
                messages.append(create_user_message(content))
            elif role == "assistant":
                messages.append(create_assistant_message(content))

        return messages


# Convenience functions for use in finders

def parse_claude_messages(transcript_objects: List[Dict[str, Any]]) -> List[ChatMessage]:
    """Parse Claude Code transcript objects into structured messages."""
    return ClaudeMessageParser.parse_transcript_objects(transcript_objects)


def parse_copilot_messages(copilot_raw: Dict[str, Any]) -> List[ChatMessage]:
    """Parse Copilot chat session from raw data."""
    return CopilotMessageParser.parse_chat_session(copilot_raw)


def parse_cursor_messages(raw_messages: List[Dict[str, str]]) -> List[ChatMessage]:
    """Parse Cursor messages."""
    return CursorMessageParser.parse_messages(raw_messages)
