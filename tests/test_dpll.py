"""Characterization tests for the deterministic DPLL solver."""

from __future__ import annotations

import itertools
import random
import time
import unittest
from collections.abc import Sequence

from solver.dpll import Clause, SolveResult, solve

Outcome = tuple[
    bool | None,
    dict[int, bool] | None,
    bool,
    int,
    int,
    int,
]


def _outcome(result: SolveResult) -> Outcome:
    """Return every deterministic observable except runtime."""

    return (
        result.satisfiable,
        result.model,
        result.timed_out,
        result.statistics.decisions,
        result.statistics.propagations,
        result.statistics.backtracks,
    )


def _brute_force_satisfiable(clauses: Sequence[Clause], num_vars: int) -> bool:
    """Return SAT status by enumerating every complete assignment."""

    for values in itertools.product((False, True), repeat=num_vars):
        if all(
            any(
                values[abs(literal) - 1]
                if literal > 0
                else not values[abs(literal) - 1]
                for literal in clause
            )
            for clause in clauses
        ):
            return True
    return False


class DPLLCharacterizationTests(unittest.TestCase):
    """Freeze result, model, traversal order, and counter behavior."""

    def test_baseline_cases(self) -> None:
        cases: tuple[tuple[str, list[Clause], int, tuple[int, ...], Outcome], ...] = (
            (
                "simple SAT",
                [[1, 2], [-1, 2]],
                2,
                (),
                (True, {1: True, 2: True}, False, 1, 1, 0),
            ),
            (
                "UNSAT units",
                [[1], [-1]],
                1,
                (),
                (False, None, False, 0, 1, 0),
            ),
            (
                "empty formula",
                [],
                3,
                (),
                (True, {1: False, 2: False, 3: False}, False, 0, 0, 0),
            ),
            (
                "empty clause",
                [[]],
                2,
                (),
                (False, None, False, 0, 0, 0),
            ),
            (
                "valid assumption",
                [[1, 2], [-1, 2]],
                2,
                (-1,),
                (True, {1: False, 2: True}, False, 0, 1, 0),
            ),
            (
                "contradictory assumptions",
                [],
                2,
                (1, -1),
                (False, None, False, 0, 0, 0),
            ),
            (
                "backtracking UNSAT",
                [[1, 2], [1, -2], [-1, 2], [-1, -2]],
                2,
                (),
                (False, None, False, 1, 2, 2),
            ),
            (
                "free variables default false",
                [[1]],
                3,
                (),
                (True, {1: True, 2: False, 3: False}, False, 0, 1, 0),
            ),
        )

        for name, clauses, num_vars, assumptions, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(
                    _outcome(solve(clauses, num_vars, assumptions)), expected
                )

    def test_expired_deadline(self) -> None:
        result = solve([[1]], 1, deadline=time.monotonic() - 1.0)
        self.assertEqual(_outcome(result), (None, None, True, 0, 0, 0))

    def test_seeded_random_cases_match_baseline_and_brute_force(self) -> None:
        expected: tuple[Outcome, ...] = (
            (True, {1: False, 2: False}, False, 0, 0, 0),
            (True, {1: True}, False, 0, 1, 0),
            (True, {1: False, 2: False, 3: False, 4: False, 5: False}, False, 0, 0, 0),
            (False, None, False, 0, 2, 0),
            (False, None, False, 0, 1, 0),
            (False, None, False, 0, 0, 0),
            (True, {1: True, 2: False, 3: False, 4: False, 5: False}, False, 1, 1, 0),
            (True, {1: True, 2: True}, False, 0, 2, 0),
            (False, None, False, 0, 0, 0),
            (True, {1: True, 2: False, 3: False, 4: False}, False, 1, 0, 0),
            (False, None, False, 0, 1, 0),
            (True, {1: False, 2: False, 3: False, 4: False}, False, 0, 1, 0),
        )
        rng = random.Random(20261124)

        for case_index, expected_outcome in enumerate(expected):
            num_vars = rng.randint(1, 5)
            literals = tuple(range(1, num_vars + 1)) + tuple(range(-num_vars, 0))
            clauses = [
                [rng.choice(literals) for _ in range(rng.randint(0, 4))]
                for _ in range(rng.randint(0, 7))
            ]
            with self.subTest(case=case_index, clauses=clauses):
                result = solve(clauses, num_vars)
                self.assertEqual(_outcome(result), expected_outcome)
                self.assertIs(
                    result.satisfiable,
                    _brute_force_satisfiable(clauses, num_vars),
                )


if __name__ == "__main__":
    unittest.main()
