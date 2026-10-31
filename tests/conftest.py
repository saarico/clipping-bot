"""Shared test setup: the bot's modules import each other by bare name, so bot/ goes on the path."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot"))
sys.path.insert(0, str(ROOT / "tests"))

# the golden set measures the board's weight table, never the Analyst's tuned copy in data/
os.environ["STUDIO_BOARD_WEIGHTS"] = "1"
