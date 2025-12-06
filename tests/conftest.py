#!/usr/bin/env python3
"""
Pytest configuration and fixtures.
"""

import sys
import pathlib

# Add parent directory to path so we can import the modules
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

