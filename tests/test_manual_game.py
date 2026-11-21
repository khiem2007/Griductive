"""Engine tests for manual practice and the future referee boundary."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from core.engine import GameEngine
from core.models import (
    Cell,
    ManualResult,
    MoveResult,
    PublicState,
    Puzzle,
    Verdict,
    load_puzzle,
)


class CountingReferee:
    """Configurable proof-based referee test double."""

    def __init__(self, result: MoveResult) -> None:
        self.result = result
        self.calls = 0

    def judge(
        self, state: PublicState, cell: str, claimed: Verdict
    ) -> MoveResult:
        self.calls += 1
        return self.result


class ErrorReferee:
    """Referee test double that fails before any reveal can occur."""

    def judge(
        self, state: PublicState, cell: str, claimed: Verdict
    ) -> MoveResult:
        raise RuntimeError("referee failure")


def _sample_puzzle() -> Puzzle:
    return load_puzzle(Path("puzzles") / "3x3_easy.json")


def _first_face_down(puzzle: Puzzle) -> Cell:
    return next(cell for cell in puzzle.cells if not cell.revealed)


class ManualGameEngineTests(unittest.TestCase):
    """Verify answer checking without importing or running solver code."""

    def test_wrong_correct_repeated_restart_and_completion(self) -> None:
        puzzle = _sample_puzzle()
        engine = GameEngine(puzzle)
        target = _first_face_down(puzzle)
        wrong = (
            Verdict.INNOCENT
            if target.status is Verdict.CRIMINAL
            else Verdict.CRIMINAL
        )

        self.assertIs(engine.submit_manual(target.id, wrong), ManualResult.WRONG)
        self.assertNotIn(target.id, engine.get_public_state().revealed)
        self.assertIs(engine.submit_manual(target.id, target.status), ManualResult.CORRECT)
        self.assertIn(target.id, engine.get_public_state().revealed)
        self.assertIs(
            engine.submit_manual(target.id, target.status),
            ManualResult.ALREADY_REVEALED,
        )

        engine.restart()
        self.assertEqual(
            set(engine.get_public_state().revealed),
            {cell.id for cell in puzzle.cells if cell.revealed},
        )
        for cell in puzzle.cells:
            if cell.id not in engine.get_public_state().revealed:
                self.assertIs(
                    engine.submit_manual(cell.id, cell.status), ManualResult.CORRECT
                )
        self.assertTrue(engine.is_solved())

    def test_loading_second_fixture_resets_public_state(self) -> None:
        first = _sample_puzzle()
        renamed_first = replace(first.cells[0], name="Second Puzzle Person")
        second = replace(first, cells=(renamed_first, *first.cells[1:]))
        engine = GameEngine(first)
        target = _first_face_down(first)
        engine.submit_manual(target.id, target.status)

        engine.load(second)
        state = engine.get_public_state()
        self.assertEqual(state.names["A1"], "Second Puzzle Person")
        self.assertEqual(
            set(state.revealed), {cell.id for cell in second.cells if cell.revealed}
        )

    def test_wrong_mode_calls_never_reveal(self) -> None:
        puzzle = _sample_puzzle()
        target = _first_face_down(puzzle)
        manual_engine = GameEngine(puzzle)
        before_manual = manual_engine.get_public_state()
        with self.assertRaises(RuntimeError):
            manual_engine.submit_verdict(target.id, target.status)
        self.assertEqual(manual_engine.get_public_state(), before_manual)

        referee_engine = GameEngine(puzzle, CountingReferee(MoveResult.ACCEPTED))
        before_referee = referee_engine.get_public_state()
        with self.assertRaises(RuntimeError):
            referee_engine.submit_manual(target.id, target.status)
        self.assertEqual(referee_engine.get_public_state(), before_referee)

    def test_face_up_claim_skips_referee(self) -> None:
        puzzle = _sample_puzzle()
        face_up = next(cell for cell in puzzle.cells if cell.revealed)
        referee = CountingReferee(MoveResult.ACCEPTED)
        engine = GameEngine(puzzle, referee)
        before = engine.get_public_state()

        result = engine.submit_verdict(face_up.id, face_up.status)

        self.assertIs(result, MoveResult.ALREADY_REVEALED)
        self.assertEqual(referee.calls, 0)
        self.assertEqual(engine.get_public_state(), before)

    def test_rejection_timeout_and_referee_error_leave_card_hidden(self) -> None:
        puzzle = _sample_puzzle()
        target = _first_face_down(puzzle)
        for result in (MoveResult.NOT_PROVABLE, MoveResult.CONTRADICTED, MoveResult.TIMEOUT):
            with self.subTest(result=result):
                engine = GameEngine(puzzle, CountingReferee(result))
                self.assertIs(engine.submit_verdict(target.id, target.status), result)
                self.assertNotIn(target.id, engine.get_public_state().revealed)

        engine = GameEngine(puzzle, ErrorReferee())
        with self.assertRaisesRegex(RuntimeError, "referee failure"):
            engine.submit_verdict(target.id, target.status)
        self.assertNotIn(target.id, engine.get_public_state().revealed)

    def test_manual_move_does_not_import_solver_or_modify_puzzle_file(self) -> None:
        puzzle_path = Path("puzzles") / "3x3_easy.json"
        before_hash = hashlib.sha256(puzzle_path.read_bytes()).hexdigest()
        code = """
import sys
from pathlib import Path
import main
from core.engine import GameEngine
from core.models import load_puzzle
puzzle = load_puzzle(Path('puzzles') / '3x3_easy.json')
engine = GameEngine(puzzle)
target = next(cell for cell in puzzle.cells if not cell.revealed)
engine.submit_manual(target.id, target.status)
assert not any(name == 'solver' or name.startswith('solver.') for name in sys.modules)
"""
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        after_hash = hashlib.sha256(puzzle_path.read_bytes()).hexdigest()
        self.assertEqual(after_hash, before_hash)


if __name__ == "__main__":
    unittest.main()
