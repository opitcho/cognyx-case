"""The agent layer: the tools, the agent, its entry points and the Claims page of the app.

The agent and the app come from the jean-code submodule, whose modules (`agent`, `llm`, `usage`, ...) are plain
files under `jean-code/src`, with no package around them. Importing this package puts that folder on the path.
"""

import sys
from pathlib import Path

JEAN_CODE = Path(__file__).resolve().parent.parent / "jean-code" / "src"
if str(JEAN_CODE) not in sys.path:
    sys.path.insert(0, str(JEAN_CODE))
