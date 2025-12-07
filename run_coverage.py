#!/usr/bin/env python3
"""
Run tests with coverage reporting.

Usage:
    python run_coverage.py              # Run tests with coverage
    python run_coverage.py --min=80     # Fail if coverage < 80%
    python run_coverage.py --html       # Open HTML report after running
"""

import argparse
import subprocess
import sys
import webbrowser
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run tests with coverage")
    parser.add_argument(
        "--min",
        type=float,
        default=None,
        help="Minimum coverage percentage required (0-100). Fails if coverage is below this."
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Open HTML coverage report in browser after running"
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Alias for --min (pytest-cov option)"
    )
    args = parser.parse_args()
    
    # Build pytest command
    cmd = ["pytest"]
    
    # Add fail-under if specified
    fail_under = args.fail_under or args.min
    if fail_under is not None:
        cmd.extend(["--cov-fail-under", str(fail_under)])
    
    # Run pytest
    result = subprocess.run(cmd)
    
    # Open HTML report if requested
    if args.html and result.returncode == 0:
        html_path = Path("htmlcov/index.html")
        if html_path.exists():
            print(f"\nOpening coverage report: {html_path.absolute()}")
            webbrowser.open(f"file://{html_path.absolute()}")
        else:
            print("Warning: HTML coverage report not found")
    
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

