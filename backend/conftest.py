"""
Pytest configuration for the backend test suite.

Sets asyncio_mode to 'auto' so that async test functions
are automatically recognized without per-function markers.
"""

import sys
from pathlib import Path

# Ensure the backend app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

# pytest-asyncio configuration
pytest_plugins = []
