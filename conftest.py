"""
pytest configuration — ensures the project root is on sys.path
so all absolute imports (scenarios, runner, metrics, etc.) resolve
correctly on every platform and CI environment.
"""

import sys
from pathlib import Path

# Insert project root at front of path if not already present
_root = str(Path(__file__).parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
