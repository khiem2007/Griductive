
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


def create_app(
    initial_path: Path | None = None, puzzle_directory: Path | None = None
) -> GriductiveApp:
    """Wire lazy level discovery and validated loading without exposing answers."""

    directory = (
        puzzle_directory if puzzle_directory is not None
        else Path(__file__).resolve().parent / "puzzles"
    )
    engine = GameEngine(puzzle=None, referee=None)
    catalog: dict[str, Path] = {}

    def list_levels() -> tuple[str, ...]:
        if not directory.exists():
            catalog.clear()
            return ()
        paths = sorted(
            (path for path in directory.iterdir() if path.is_file() and path.suffix == ".json"),
            key=lambda path: path.stem,
        )
        catalog.clear()
        catalog.update((path.stem, path) for path in paths)
        return tuple(catalog)

    def load_into_engine(path: str) -> None:
        source = Path(path)
        if not source.is_file():
            raise ValueError("Không tìm thấy file. Hãy chọn màn khác hoặc kiểm tra đường dẫn.")
        # Validate completely before replacing the current game.
        engine.load(load_puzzle(source))

    def load_level(name: str) -> None:
        if name not in catalog:
            raise ValueError("Màn chơi không còn trong danh sách. Hãy mở lại Chọn màn.")
        load_into_engine(str(catalog[name]))

    initial_message = "Chọn một màn rồi bấm Chơi."
    if initial_path is not None:
        try:
            load_into_engine(str(initial_path))
            initial_message = f"Loaded {initial_path.name}."
        except ValueError as exc:
            initial_message = f"Không thể mở {initial_path.name}: {exc}"

    return GriductiveApp(
        game=engine,
        load_puzzle=load_into_engine,
        initial_message=initial_message,
        list_levels=list_levels,
        load_level=load_level,
        initial_level_name=initial_path.stem if initial_path and engine.has_puzzle else None,
    )


def main() -> int:

    args = _parse_args()
    app = create_app(args.puzzle)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
