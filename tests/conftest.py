import sys
from pathlib import Path

# Make `wc2026` importable no matter where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
