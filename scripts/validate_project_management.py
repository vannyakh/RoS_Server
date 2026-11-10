"""Validate the agent registry and the project-control registries."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.project_tracker.validate_registry import main

if __name__ == "__main__":
    sys.exit(main())
