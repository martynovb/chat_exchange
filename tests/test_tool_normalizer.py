#!/usr/bin/env python3
"""
Unit tests for tool_normalizer.
"""

import pytest
from src.domain.tool_normalizer import tool_name_normalization


class TestToolNormalizer:
    """Test cases for tool_normalizer."""
    
    def test_unknown_ai_type(self):
        """Test tool normalization with unknown AI type."""
        result = tool_name_normalization("unknown_ai", "some_tool")
        assert result is None
    
    def test_explicitly_skipped_tool(self):
        """Test tool normalization with explicitly skipped tool (mapped to None)."""
        # copilot_applyPatch is explicitly mapped to None
        result = tool_name_normalization("copilot", "copilot_applyPatch")
        assert result is None
    
    def test_cursor_tool_mapping(self):
        """Test cursor tool normalization."""
        result = tool_name_normalization("cursor", "read_file")
        assert result == "read"
    
    def test_claude_tool_mapping(self):
        """Test claude tool normalization."""
        result = tool_name_normalization("claude", "Read")
        assert result == "read"
    
    def test_copilot_tool_mapping(self):
        """Test copilot tool normalization."""
        result = tool_name_normalization("copilot", "copilot_readFile")
        assert result == "read"
    
    def test_unmapped_tool(self):
        """Test tool normalization with unmapped tool."""
        result = tool_name_normalization("cursor", "unknown_tool")
        assert result is None

