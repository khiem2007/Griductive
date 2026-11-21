"""Headless integration checks for lazy level selection and startup."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import main
from core.models import ManualResult, Verdict


class LevelSelectionTests(unittest.TestCase):
    """Drive real catalog/loading callbacks with temporary authored fixtures."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "puzzles"
        self.directory.mkdir()

    def tearDown(self) -> None:
        pygame.quit()

    def _write_board(self, name: str, size: int, revealed: str) -> Path:
        """Write a small test fixture, never a repository puzzle."""

        cells = []
        for row in range(1, size + 1):
            for col in range(size):
                cell = f"{chr(65 + col)}{row}"
                cells.append({
                    "id": cell,
                    "name": f"{name} {cell}",
                    "job": "Tester",
                    "status": "INNOCENT",
                    "revealed": cell == revealed,
                    "clue": {
                        "id": f"clue_{cell}", "type": "FACT",
                        "cell": cell, "status": "INNOCENT",
                    },
                })
        path = self.directory / f"{name}.json"
        path.write_text(json.dumps({"size": size, "cells": cells}), encoding="utf-8")
        return path

    def _click(self, app: main.GriductiveApp, rect: pygame.Rect) -> None:
        app.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": rect.center}
        ))

    def test_second_then_first_level_restart_and_rescan(self) -> None:
        first = self._write_board("01_first", 3, "A1")
        second = self._write_board("02_second", 4, "D4")
        before_bytes = {path: path.read_bytes() for path in (first, second)}
        app = main.create_app(puzzle_directory=self.directory)
        self.assertTrue(app.choosing_level)
        self.assertEqual(app.level_names, ("01_first", "02_second"))
        app.draw()
        self._click(app, app._level_rects["02_second"])
        self._click(app, app._buttons["play"])
        self.assertFalse(app.choosing_level)
        self.assertEqual(app.current_level_name, "02_second")
        state = app._game.get_public_state()
        self.assertEqual(state.size, 4)
        self.assertEqual(state.names["A1"], "02_second A1")
        self.assertEqual(set(state.revealed), {"D4"})

        # Re-enter using the actual in-game button, and discover a new file.
        app.draw()
        self._write_board("03_new", 3, "C3")
        self._click(app, app._buttons["levels"])
        self.assertIn("03_new", app.level_names)
        app.draw()
        self._click(app, app._level_rects["01_first"])
        self._click(app, app._buttons["play"])
        initial = app._game.get_public_state()
        self.assertEqual(initial.size, 3)
        self.assertEqual(initial.names["A1"], "01_first A1")
        self.assertEqual(set(initial.revealed), {"A1"})
        app.select_cell("B1")
        self.assertIs(app.submit_selected(Verdict.INNOCENT), ManualResult.CORRECT)
        app.draw()
        self._click(app, app._buttons["restart"])
        self.assertEqual(app._game.get_public_state(), initial)
        self.assertEqual(app.current_level_name, "01_first")
        for path, data in before_bytes.items():
            self.assertEqual(path.read_bytes(), data)

    def test_bad_and_deleted_levels_preserve_active_game_and_can_resume(self) -> None:
        self._write_board("good", 3, "B2")
        deleted = self._write_board("deleted", 4, "A1")
        (self.directory / "bad.json").write_text('{"size":', encoding="utf-8")
        (self.directory / "invalid.json").write_text('{"size": 2, "cells": []}', encoding="utf-8")
        app = main.create_app(puzzle_directory=self.directory)
        # Listing and selecting do not invoke the loader, even for invalid JSON.
        with patch("main.load_puzzle", side_effect=AssertionError("eager load")):
            app.show_level_selector()
            app.select_level("bad")
            app.draw()
        app.select_level("good")
        self.assertTrue(app.play_selected_level())
        app.select_cell("A1")
        app.submit_selected(Verdict.INNOCENT)
        before = app._game.get_public_state()
        app.show_level_selector()
        deleted.unlink()
        for name in ("bad", "invalid", "deleted"):
            app.select_level(name)
            self.assertFalse(app.play_selected_level())
            self.assertIn(f"{name}.json", app.message)
            self.assertTrue(app.choosing_level)
            self.assertEqual(app.current_level_name, "good")
            self.assertEqual(app._game.get_public_state(), before)
            app.draw()
        self._click(app, app._buttons["resume"])
        self.assertFalse(app.choosing_level)
        self.assertEqual(app._game.get_public_state(), before)
        app.show_level_selector()
        self.assertNotIn("deleted", app.level_names)
        app.select_level("good")
        self.assertTrue(app.play_selected_level())

    def test_empty_missing_and_nonrecursive_catalogs(self) -> None:
        for directory in (self.directory, self.root / "missing"):
            with self.subTest(directory=directory):
                app = main.create_app(puzzle_directory=directory)
                self.assertTrue(app.choosing_level)
                self.assertEqual(app.level_names, ())
                app.draw()
                app.run(max_frames=1)
                self.assertIn("load", app._buttons)
                self.assertFalse(app.play_selected_level())
                self.assertEqual(app._game.get_public_state().size, 0)
        nested = self.directory / "nested"
        nested.mkdir()
        (nested / "nested.json").write_text("{}", encoding="utf-8")
        (self.directory / "folder.json").mkdir()
        (self.directory / "notes.txt").write_text("ignored", encoding="utf-8")
        self.assertEqual(main.create_app(puzzle_directory=self.directory).level_names, ())

    def test_pagination_reaches_every_level_and_clamps_after_resize(self) -> None:
        # Content is intentionally invalid: browsing must not parse any file.
        names = tuple(f"level_{index:02}" for index in range(30))
        for name in reversed(names):
            (self.directory / f"{name}.json").write_text("invalid", encoding="utf-8")
        app = main.create_app(puzzle_directory=self.directory)
        app.draw()
        visited = set(app._level_rects)
        while len(visited) < len(names):
            page = app._level_page
            self._click(app, app._buttons["next"])
            self.assertGreater(app._level_page, page)
            app.draw()
            visited.update(app._level_rects)
        self.assertEqual(visited, set(names))
        self._click(app, app._level_rects[names[-1]])
        self.assertEqual(app._selected_level, names[-1])
        app.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, {"y": 100}))
        app.draw()
        self.assertEqual(app._level_page, 0)
        app.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_PAGEDOWN}))
        app.draw()
        self.assertGreater(app._level_page, 0)
        app.handle_event(pygame.event.Event(pygame.VIDEORESIZE, {"w": 960, "h": 680}))
        app.draw()
        self.assertTrue(app._level_rects)

    def test_external_load_cancel_and_path_entry_fallback(self) -> None:
        external = self._write_board("external", 3, "C3")
        app = main.create_app(puzzle_directory=self.root / "missing")
        app.draw()
        with patch.object(app, "_pick_file_in_child_process", return_value=(None, True)):
            self._click(app, app._buttons["load"])
        self.assertTrue(app.choosing_level)
        self.assertEqual(app._game.get_public_state().size, 0)
        with patch.object(app, "_pick_file_in_child_process", return_value=(None, False)):
            self._click(app, app._buttons["load"])
        self.assertTrue(app._path_entry_active)
        app._path_text = str(external)
        app.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN}))
        self.assertFalse(app.choosing_level)
        self.assertEqual(app.current_level_name, "external")
        self.assertEqual(set(app._game.get_public_state().revealed), {"C3"})
        before = app._game.get_public_state()
        self.assertFalse(app.load_from_path(""))
        self.assertFalse(app.load_from_path(str(self.root / "missing.json")))
        self.assertEqual(app._game.get_public_state(), before)

    def test_cli_default_direct_and_invalid_path_from_another_cwd(self) -> None:
        direct = self._write_board("direct", 4, "B4")
        real_app_class = main.GriductiveApp
        captured = []

        def run_one_frame(**kwargs: object) -> main.GriductiveApp:
            app = real_app_class(**kwargs)
            captured.append(app)
            app.run = lambda: real_app_class.run(app, max_frames=1)
            return app

        old_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            with patch("main.GriductiveApp", side_effect=run_one_frame):
                with patch.object(sys, "argv", ["main.py"]):
                    self.assertEqual(main.main(), 0)
                self.assertTrue(captured[-1].choosing_level)
                self.assertIn("3x3_easy", captured[-1].level_names)
                with patch.object(sys, "argv", ["main.py", str(direct)]):
                    self.assertEqual(main.main(), 0)
                self.assertFalse(captured[-1].choosing_level)
                self.assertEqual(captured[-1].current_level_name, "direct")
                self.assertEqual(captured[-1]._game.get_public_state().size, 4)
                with patch.object(sys, "argv", ["main.py", "absent.json"]):
                    self.assertEqual(main.main(), 0)
                self.assertTrue(captured[-1].choosing_level)
                self.assertIn("absent.json", captured[-1].message)
        finally:
            os.chdir(old_cwd)

    def test_fresh_process_catalog_and_play_do_not_import_solver_or_write_files(self) -> None:
        path = self._write_board("only", 3, "A1")
        before = hashlib.sha256(path.read_bytes()).digest()
        code = """
import sys
import pygame
import main
from pathlib import Path
app = main.create_app(puzzle_directory=Path(sys.argv[1]))
assert app.choosing_level
app.select_level('only')
assert app.play_selected_level()
assert not any(m == 'solver' or m.startswith('solver.') for m in sys.modules)
pygame.quit()
"""
        completed = subprocess.run(
            [sys.executable, "-B", "-c", code, str(self.directory)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), before)
        self.assertEqual(list(self.directory.iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
