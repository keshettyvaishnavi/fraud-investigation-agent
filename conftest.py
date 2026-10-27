import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import build_database
build_database()
