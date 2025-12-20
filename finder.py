#!/usr/bin/env python3
"""
Entry point for the chat finder CLI.
This script is a convenience wrapper that calls the main finder module.
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the main function
from src.presentation.finder import main

if __name__ == "__main__":
    sys.exit(main())

