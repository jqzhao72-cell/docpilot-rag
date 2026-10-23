"""Offline evaluation package; production code never imports this package."""
from pathlib import Path
import sys

# Reuse the existing backend package layout without moving the production code.
BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
