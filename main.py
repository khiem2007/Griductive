"""Launch the Griductive manual-practice GUI."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.engine import GameEngine
from core.models import load_puzzle
from gui.app import GriductiveApp


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Play a user-authored Griductive JSON puzzle in manual practice mode."
    )
    parser.add_argument(
        "puzzle",
        nargs="?",
        type=Path,
        help="optional path to a 3x3, 4x4, or 5x5 puzzle JSON file",
    )
    return parser.parse_args()


def main() -> int:
    """Create the engine, wire safe loading, and run the Pygame app."""

    args = _parse_args()
    engine = GameEngine(puzzle=None, referee=None)
    initial_message = "Load a puzzle JSON file to begin."
    if args.puzzle is not None:
        try:
            engine.load(load_puzzle(args.puzzle))
            initial_message = f"Loaded {args.puzzle.name}."
        except ValueError as exc:
            initial_message = f"Startup load failed: {exc}"

    def load_into_engine(path: str) -> None:
        engine.load(load_puzzle(path))

    app = GriductiveApp(
        game=engine,
        load_puzzle=load_into_engine,
        initial_message=initial_message,
    )
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
