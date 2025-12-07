#!/usr/bin/env python3
"""
Unit tests for finder.py CLI script.
"""

import pytest
import json
import pathlib
import tempfile
import sys
from unittest.mock import patch, MagicMock
from finder import get_finder, main


class TestGetFinder:
    """Test cases for get_finder function."""
    
    def test_get_finder_claude(self):
        """Test getting Claude finder."""
        finder = get_finder("claude")
        assert finder._finder_type == "claude"
    
    def test_get_finder_copilot(self):
        """Test getting Copilot finder."""
        finder = get_finder("copilot")
        assert finder._finder_type == "copilot"
    
    def test_get_finder_cursor(self):
        """Test getting Cursor finder."""
        finder = get_finder("cursor")
        assert finder._finder_type == "cursor"
    
    def test_get_finder_case_insensitive(self):
        """Test that finder type is case insensitive."""
        finder1 = get_finder("CLAUDE")
        finder2 = get_finder("Claude")
        finder3 = get_finder("claude")
        assert finder1._finder_type == "claude"
        assert finder2._finder_type == "claude"
        assert finder3._finder_type == "claude"
    
    def test_get_finder_invalid_type(self):
        """Test that invalid finder type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown finder type"):
            get_finder("invalid")


class TestMain:
    """Test cases for main function."""
    
    def test_main_list_mode(self, capsys):
        """Test main function in list mode (no --export, no --out)."""
        with patch('sys.argv', ['finder.py', '--type', 'claude']), \
             patch('finder.get_finder') as mock_get_finder:
            mock_finder = MagicMock()
            mock_finder.get_chat_metadata_list.return_value = [
                {'id': '123', 'title': 'Test Chat', 'date': '2024-01-01'}
            ]
            mock_get_finder.return_value = mock_finder
            
            result = main()
            assert result == 0
            
            captured = capsys.readouterr()
            assert "Found 1 chats:" in captured.out
            assert "123" in captured.out
            assert "Test Chat" in captured.out
    
    def test_main_export_mode(self, capsys):
        """Test main function in export mode (--export specified)."""
        with patch('sys.argv', ['finder.py', '--type', 'claude', '--export', 'test_id']), \
             patch('finder.get_finder') as mock_get_finder:
            mock_finder = MagicMock()
            mock_finder.parse_chat_by_id.return_value = {'title': 'Test Chat', 'messages': []}
            mock_finder._get_default_output_path.return_value = pathlib.Path('/tmp/test.json')
            mock_get_finder.return_value = mock_finder
            
            with patch('pathlib.Path.write_text') as mock_write:
                result = main()
                assert result == 0
                mock_write.assert_called_once()
                
                captured = capsys.readouterr()
                assert "Exported chat test_id" in captured.out
    
    def test_main_export_mode_error(self, capsys):
        """Test main function in export mode with error."""
        with patch('sys.argv', ['finder.py', '--type', 'claude', '--export', 'test_id']), \
             patch('finder.get_finder') as mock_get_finder:
            mock_finder = MagicMock()
            mock_finder.parse_chat_by_id.side_effect = ValueError("Chat not found")
            mock_get_finder.return_value = mock_finder
            
            result = main()
            assert result == 1
            
            captured = capsys.readouterr()
            assert "Error:" in captured.out
    
    def test_main_export_all_mode(self, capsys):
        """Test main function in export all mode (--out specified)."""
        with patch('sys.argv', ['finder.py', '--type', 'claude', '--out', '/tmp/output.json']), \
             patch('finder.get_finder') as mock_get_finder:
            mock_finder = MagicMock()
            mock_finder.export_chats.return_value = [{'title': 'Chat 1'}, {'title': 'Chat 2'}]
            mock_get_finder.return_value = mock_finder
            
            with patch('pathlib.Path') as mock_path:
                mock_path.return_value.exists.return_value = False
                result = main()
                assert result == 0
                
                captured = capsys.readouterr()
                assert "Extracted 2 claude chat sessions" in captured.out
    
    def test_main_export_all_mode_no_export_chats(self, capsys):
        """Test main function when finder doesn't support export_chats."""
        with patch('sys.argv', ['finder.py', '--type', 'claude', '--out', '/tmp/output.json']), \
             patch('finder.get_finder') as mock_get_finder:
            mock_finder = MagicMock()
            del mock_finder.export_chats  # Remove the method
            mock_get_finder.return_value = mock_finder
            
            result = main()
            assert result == 1
            
            captured = capsys.readouterr()
            assert "does not support bulk export" in captured.out
    
    def test_main_invalid_finder_type(self, capsys):
        """Test main function with invalid finder type."""
        # argparse validates choices before we can catch it, so it exits with SystemExit
        with patch('sys.argv', ['finder.py', '--type', 'invalid']):
            with pytest.raises(SystemExit):
                main()

