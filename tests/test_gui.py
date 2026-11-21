"""Headless Pygame checks for manual UI behavior and mode dispatch."""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.engine import GameEngine
from core.models import (
    Cell,
    Clue,
    ClueType,
    ManualResult,
    MoveResult,
    PublicState,
    Puzzle,
    Verdict,
    load_puzzle,
)
from core.regions import cell_ids, clue_cells
from gui.app import GriductiveApp


class AcceptingReferee:
    """Proof-path test double that accepts every submitted claim."""

    def judge(
        self, state: PublicState, cell: str, claimed: Verdict
    ) -> MoveResult:
        return MoveResult.ACCEPTED


def _fixture_puzzle(size: int) -> Puzzle:
    cells: list[Cell] = []
    for index, cell_id in enumerate(cell_ids(size)):
        status = Verdict.CRIMINAL if index % 2 else Verdict.INNOCENT
        clue = Clue(
            id=f"clue_{cell_id}",
            type=ClueType.FACT,
            cell=cell_id,
            status=status,
        )
        cells.append(
            Cell(
                id=cell_id,
                name=f"Person {cell_id}",
                job=f"Job {index + 1}",
                status=status,
                revealed=index == 0,
                clue=clue,
            )
        )
    return Puzzle(size=size, cells=tuple(cells))


class GriductiveGuiTests(unittest.TestCase):
    """Exercise GUI logic with the SDL dummy video driver."""

    def tearDown(self) -> None:
        pygame.quit()

    def _app_for(self, engine: GameEngine, mapping: dict[str, Puzzle] | None = None) -> GriductiveApp:
        puzzles = mapping or {}

        def load_callback(path: str) -> None:
            if path == "invalid.json":
                raise ValueError("cells[2].status is invalid")
            if path not in puzzles:
                raise ValueError("unknown fixture path")
            engine.load(puzzles[path])

        return GriductiveApp(engine, load_callback, window_size=(1100, 720))

    def test_empty_start_screen(self) -> None:
        engine = GameEngine()
        app = self._app_for(engine)
        app.draw()
        self.assertEqual(engine.get_public_state().size, 0)
        self.assertEqual(app._card_rects, {})
        self.assertIsNone(app.submit_selected(Verdict.CRIMINAL))

    def test_manual_dispatch_wrong_then_correct(self) -> None:
        puzzle = load_puzzle("puzzles/3x3_easy.json")
        engine = GameEngine(puzzle)
        app = self._app_for(engine)
        target = next(cell for cell in puzzle.cells if not cell.revealed)
        wrong = Verdict.INNOCENT if target.status is Verdict.CRIMINAL else Verdict.CRIMINAL

        app.select_cell(target.id)
        self.assertIs(app.submit_selected(wrong), ManualResult.WRONG)
        self.assertEqual(app.selected_cell, target.id)
        self.assertIs(app.submit_selected(target.status), ManualResult.CORRECT)
        self.assertIsNone(app.selected_cell)

    def test_proof_mode_dispatch_uses_submit_verdict(self) -> None:
        puzzle = load_puzzle("puzzles/3x3_easy.json")
        engine = GameEngine(puzzle, AcceptingReferee())
        app = self._app_for(engine)
        target = next(cell for cell in puzzle.cells if not cell.revealed)

        app.select_cell(target.id)
        self.assertIs(app.submit_selected(target.status), MoveResult.ACCEPTED)
        self.assertIn(target.id, engine.get_public_state().revealed)

    def test_revealed_clue_highlighting_and_repeated_selection(self) -> None:
        puzzle = load_puzzle("puzzles/3x3_easy.json")
        engine = GameEngine(puzzle)
        app = self._app_for(engine)
        face_up = next(cell for cell in puzzle.cells if cell.revealed)
        face_down = next(cell for cell in puzzle.cells if not cell.revealed)

        app.select_cell(face_down.id)
        app.select_cell(face_down.id)
        self.assertEqual(app.selected_cell, face_down.id)
        app.select_cell(face_up.id)
        self.assertEqual(
            app.highlighted_cells, frozenset(clue_cells(face_up.clue, puzzle.size))
        )

    def test_restart_valid_load_invalid_load_and_cancel(self) -> None:
        first = _fixture_puzzle(3)
        second_cell = replace(_fixture_puzzle(4).cells[0], name="Second Board")
        base_second = _fixture_puzzle(4)
        second = replace(base_second, cells=(second_cell, *base_second.cells[1:]))
        engine = GameEngine(first)
        app = self._app_for(engine, {"second.json": second})
        target = next(cell for cell in first.cells if not cell.revealed)
        app.select_cell(target.id)
        app.submit_selected(target.status)
        app.restart_game()
        self.assertNotIn(target.id, engine.get_public_state().revealed)

        self.assertTrue(app.load_from_path("second.json"))
        self.assertEqual(engine.get_public_state().size, 4)
        self.assertEqual(engine.get_public_state().names["A1"], "Second Board")
        before_invalid = engine.get_public_state()
        self.assertFalse(app.load_from_path("invalid.json"))
        self.assertEqual(engine.get_public_state(), before_invalid)
        self.assertFalse(app.load_from_path(""))
        self.assertEqual(engine.get_public_state(), before_invalid)

    def test_malformed_json_mid_game_preserves_current_state(self) -> None:
        puzzle = load_puzzle("puzzles/3x3_easy.json")
        engine = GameEngine(puzzle)

        def real_load_callback(path: str) -> None:
            engine.load(load_puzzle(path))

        app = GriductiveApp(engine, real_load_callback, window_size=(1100, 720))
        target = next(cell for cell in puzzle.cells if not cell.revealed)
        app.select_cell(target.id)
        app.submit_selected(target.status)
        before = engine.get_public_state()
        with tempfile.TemporaryDirectory() as temporary_directory:
            invalid_path = Path(temporary_directory) / "invalid.json"
            invalid_path.write_text('{"size": 3, "cells": [', encoding="utf-8")
            self.assertFalse(app.load_from_path(str(invalid_path)))
        self.assertEqual(engine.get_public_state(), before)

    def test_draws_all_supported_sizes_and_handles_synthetic_click(self) -> None:
        for size in (3, 4, 5):
            with self.subTest(size=size):
                engine = GameEngine(_fixture_puzzle(size))
                app = self._app_for(engine)
                app.draw()
                self.assertEqual(len(app._card_rects), size * size)
                target = next(
                    cell_id
                    for cell_id in cell_ids(size)
                    if cell_id not in engine.get_public_state().revealed
                )
                event = pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    {"button": 1, "pos": app._card_rects[target].center},
                )
                app.handle_event(event)
                self.assertEqual(app.selected_cell, target)
                app.run(max_frames=1)
                pygame.display.quit()


if __name__ == "__main__":
    unittest.main()
