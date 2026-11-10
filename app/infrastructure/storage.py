"""Local asset and log directories."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
LOGS = ROOT / "logs"
CONFIGURATIONS = ASSETS / "configurations"
