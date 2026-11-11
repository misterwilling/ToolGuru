"""Put `code/` on sys.path so tests can import production modules.

Pytest discovers this file automatically via conftest resolution and runs
it before any test modules load.
"""

import os
import sys

_CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _CODE_DIR not in sys.path:
    sys.path.insert(0, _CODE_DIR)
