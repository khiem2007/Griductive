"""Brute-force schema, truth, uniqueness, and no-guess checks for Step 1."""

from __future__ import annotations

import itertools
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.models import (
    Clue,
    ClueType,
    Puzzle,
    Region,
    RegionType,
    Verdict,
    load_puzzle,
    puzzle_from_dict,
    puzzle_to_dict,
)
from core.regions import cell_ids, evaluate_clue_directly


@dataclass(frozen=True)
class BruteForceResult:
    """Result of the Step 1 no-guess simulation."""

    solved: bool
    waves: int
    revealed: tuple[str, ...]


def all_assignments(size: int) -> list[dict[str, bool]]:
    """Enumerate every complete Boolean board assignment."""

    ids = cell_ids(size)
    return [
        dict(zip(ids, values, strict=True))
        for values in itertools.product((False, True), repeat=len(ids))
    ]


def satisfying_assignments(
    size: int,
    clues: Sequence[Clue],
    known_statuses: dict[str, bool] | None = None,
) -> list[dict[str, bool]]:
    """Enumerate models of direct clue semantics and optional status units."""

    known = known_statuses or {}
    return [
        assignment
        for assignment in all_assignments(size)
        if all(assignment[cell] == value for cell, value in known.items())
        and all(evaluate_clue_directly(clue, assignment, size) for clue in clues)
    ]


def simulate_no_guess(puzzle: Puzzle) -> BruteForceResult:
    """Reveal only statuses shared by every model of current public knowledge."""

    by_id = {cell.id: cell for cell in puzzle.cells}
    revealed = {cell.id for cell in puzzle.cells if cell.revealed}
    known = {
        cell.id: cell.status is Verdict.CRIMINAL
        for cell in puzzle.cells
        if cell.revealed
    }
    active_clues = [cell.clue for cell in puzzle.cells if cell.revealed]
    waves = 0

    while len(revealed) < puzzle.size * puzzle.size:
        models = satisfying_assignments(puzzle.size, active_clues, known)
        if not models:
            return BruteForceResult(False, waves, tuple(sorted(revealed)))
        forced = [
            cell_id
            for cell_id in cell_ids(puzzle.size)
            if cell_id not in revealed
            and len({model[cell_id] for model in models}) == 1
        ]
        if not forced:
            return BruteForceResult(False, waves, tuple(sorted(revealed)))
        waves += 1
        for cell_id in forced:
            cell = by_id[cell_id]
            forced_value = next(iter({model[cell_id] for model in models}))
            if forced_value is not (cell.status is Verdict.CRIMINAL):
                raise AssertionError(f"forced verdict for {cell_id} disagrees with stored solution")
            revealed.add(cell_id)
            known[cell_id] = forced_value
            active_clues.append(cell.clue)

    return BruteForceResult(True, waves, tuple(cell_ids(puzzle.size)))


class PuzzleVerificationTests(unittest.TestCase):
    """Verify every shipped Step 1 puzzle without a SAT solver."""

    def test_all_puzzles(self) -> None:
        puzzle_paths = sorted(Path("puzzles").glob("*.json"))
        self.assertTrue(puzzle_paths, "no puzzle JSON files were found")
        for path in puzzle_paths:
            with self.subTest(puzzle=str(path)):
                puzzle = load_puzzle(path)
                self.assertEqual(puzzle.size, 3, "Step 1 supports only 3x3 puzzles")

                for cell in puzzle.cells:
                    self.assertTrue(
                        evaluate_clue_directly(cell.clue, puzzle.solution, puzzle.size),
                        f"{cell.clue.id} is false under the stored solution",
                    )

                models = satisfying_assignments(
                    puzzle.size, [cell.clue for cell in puzzle.cells]
                )
                self.assertEqual(len(models), 1, "complete clue set is not unique")
                self.assertEqual(models[0], puzzle.solution)

                result = simulate_no_guess(puzzle)
                self.assertTrue(result.solved, "puzzle requires a guess")

    def test_easy_target(self) -> None:
        puzzle = load_puzzle(Path("puzzles") / "3x3_easy.json")
        self.assertGreaterEqual(sum(cell.revealed for cell in puzzle.cells), 2)
        self.assertEqual(
            {cell.clue.type for cell in puzzle.cells},
            {
                ClueType.FACT,
                ClueType.SAME,
                ClueType.DIFFERENT,
                ClueType.EXACTLY,
                ClueType.AT_LEAST,
                ClueType.AT_MOST,
            },
        )
        self.assertLessEqual(simulate_no_guess(puzzle).waves, 2)

    def test_loader_rejects_invalid_clue_data(self) -> None:
        puzzle = load_puzzle(Path("puzzles") / "3x3_easy.json")
        invalid_cases: list[dict[str, object]] = []

        unknown_type = puzzle_to_dict(puzzle)
        unknown_type["cells"][0]["clue"]["type"] = "MYSTERY"
        invalid_cases.append(unknown_type)

        out_of_range_k = puzzle_to_dict(puzzle)
        out_of_range_k["cells"][0]["clue"]["k"] = 10
        invalid_cases.append(out_of_range_k)

        outside_cell = puzzle_to_dict(puzzle)
        outside_cell["cells"][0]["clue"]["region"]["cells"] = ["Z9"]
        outside_cell["cells"][0]["clue"]["k"] = 0
        invalid_cases.append(outside_cell)

        duplicate_cells = puzzle_to_dict(puzzle)
        duplicate_cells["cells"][0]["clue"]["region"]["cells"] = ["A1", "A1"]
        duplicate_cells["cells"][0]["clue"]["k"] = 0
        invalid_cases.append(duplicate_cells)

        for invalid in invalid_cases:
            with self.subTest(case=invalid_cases.index(invalid)):
                with self.assertRaises(ValueError):
                    puzzle_from_dict(invalid)

    def test_empty_region_and_overlapping_compare_semantics(self) -> None:
        assignment = {cell: False for cell in cell_ids(3)}
        assignment.update({"A1": True, "B1": True})
        empty = Region(
            type=RegionType.INTERSECTION,
            regions=(
                Region(type=RegionType.ROW, index=1),
                Region(type=RegionType.ROW, index=2),
            ),
        )
        exactly_zero = Clue(
            id="empty_exactly_zero",
            type=ClueType.EXACTLY,
            region=empty,
            k=0,
        )
        even_empty = Clue(
            id="empty_even",
            type=ClueType.PARITY,
            region=empty,
            parity="EVEN",
        )
        overlap = Clue(
            id="overlap_compare",
            type=ClueType.COMPARE,
            left=Region(type=RegionType.ROW, index=1),
            right=Region(type=RegionType.EXPLICIT, cells=("A1", "C3")),
            op=">",
        )
        self.assertTrue(evaluate_clue_directly(exactly_zero, assignment, 3))
        self.assertTrue(evaluate_clue_directly(even_empty, assignment, 3))
        self.assertTrue(evaluate_clue_directly(overlap, assignment, 3))


if __name__ == "__main__":
    unittest.main()
