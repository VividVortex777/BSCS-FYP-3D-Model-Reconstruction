"""Project root resolution shared by the backend.

FYP_ROOT is the repository root. It defaults to the clone this file lives in
and can be overridden with the FYP_ROOT environment variable (the shell
scripts export it via scripts/fyp_env.sh).
"""

import os
from pathlib import Path

FYP_ROOT = Path(
    os.environ.get("FYP_ROOT") or Path(__file__).resolve().parents[2]
).expanduser()
