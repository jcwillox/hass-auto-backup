import sys
from pathlib import Path

# make the `custom_components` package importable when running pytest from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
