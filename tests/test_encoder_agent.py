"""Check CNF against direct semantics and exercise proof-only game play."""

from __future__ import annotations

import itertools
import random
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core.engine import GameEngine
from core.models import (
    Clue,
    ClueType,
    MoveResult,
    PublicState,
    Region,
    RegionType,
    Verdict,
    load_puzzle,
)
from core.regions import cell_ids, evaluate_clue_directly
from solver.agent import LogicAgent, UniquenessStatus, check_uniqueness
from solver.dpll import SolveResult, SolveStatistics, solve
from solver.encoder import Encoder, build_kb


def fact(cell: str, criminal: bool = True) -> Clue:
    return Clue(
        f"fact_{cell}",
        ClueType.FACT,
        cell=cell,
        status=Verdict.CRIMINAL if criminal else Verdict.INNOCENT,
    )


def state_with(*clues: Clue) -> PublicState:
    return PublicState(
        3,
        {},
        {},
        {
            cell: (Verdict.INNOCENT, clue)
            for cell, clue in zip(("A3", "B3", "C3"), clues)
        },
    )


class EncoderTests(unittest.TestCase):
    def test_random_complete_assignments_on_larger_regions(self) -> None:
        rng = random.Random(20261125)
        for size in (3, 4, 5):
            ids = cell_ids(size)
            for _ in range(20):
                left = Region(
                    RegionType.EXPLICIT,
                    cells=tuple(rng.sample(ids, rng.randrange(len(ids) + 1))),
                )
                right = Region(
                    RegionType.EXPLICIT,
                    cells=tuple(rng.sample(ids, rng.randrange(len(ids) + 1))),
                )
                clues = [
                    Clue(
                        "compare",
                        ClueType.COMPARE,
                        left=left,
                        right=right,
                        op=rng.choice(("<", "<=", "=", ">=", ">")),
                    ),
                    Clue(
                        "count",
                        rng.choice(
                            (ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST)
                        ),
                        region=left,
                        k=rng.randrange(len(left.cells) + 1),
                    ),
                    Clue(
                        "parity",
                        ClueType.PARITY,
                        region=left,
                        parity=rng.choice(("EVEN", "ODD")),
                    ),
                ]
                assignment = {cell: rng.choice((False, True)) for cell in ids}
                encoder = Encoder(size)
                clauses = [
                    clause for clue in clues for clause in encoder.encode_clue(clue)
                ]
                assumptions = [i if assignment[c] else -i for i, c in enumerate(ids, 1)]
                self.assertEqual(
                    solve(clauses, encoder.num_vars, assumptions).satisfiable,
                    all(
                        evaluate_clue_directly(clue, assignment, size) for clue in clues
                    ),
                )

    def assert_encoding(self, clue: Clue, size: int = 3) -> None:
        encoder = Encoder(size)
        clauses = encoder.encode_clue(clue)
        ids = cell_ids(size)
        # Exhaust all assignments on the first row, fixing the rest to False.
        for bits in itertools.product((False, True), repeat=3):
            assignment = dict.fromkeys(ids, False)
            assignment.update(zip(ids, bits))
            assumptions = [i if assignment[c] else -i for i, c in enumerate(ids, 1)]
            result = solve(clauses, encoder.num_vars, assumptions)
            self.assertEqual(
                result.satisfiable,
                evaluate_clue_directly(clue, assignment, size),
                (clue, assignment),
            )

    def test_all_clue_types_and_count_boundaries(self) -> None:
        regions = [
            Region(RegionType.EXPLICIT, cells=()),
            Region(RegionType.EXPLICIT, cells=("A1",)),
            Region(RegionType.ROW, index=1),
        ]
        for region in regions:
            length = 3 if region.type is RegionType.ROW else len(region.cells)
            for kind in (ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST):
                for k in range(length + 1):
                    self.assert_encoding(Clue("count", kind, region=region, k=k))
            for parity in ("EVEN", "ODD"):
                self.assert_encoding(
                    Clue("parity", ClueType.PARITY, region=region, parity=parity)
                )
        for kind in (ClueType.SAME, ClueType.DIFFERENT):
            self.assert_encoding(Clue("binary", kind, cells=("A1", "C1")))
        self.assert_encoding(fact("B1"))
        self.assert_encoding(fact("B1", False))

    def test_comparisons_exhaustive_with_overlap_and_empty_regions(self) -> None:
        cells = ("A1", "B1", "C1")
        regions = [
            Region(
                RegionType.EXPLICIT,
                cells=tuple(c for c, enabled in zip(cells, bits) if enabled),
            )
            for bits in itertools.product((False, True), repeat=3)
        ]
        for left in regions:
            for right in regions:
                for op in ("<", "<=", "=", ">=", ">"):
                    self.assert_encoding(
                        Clue("compare", ClueType.COMPARE, left=left, right=right, op=op)
                    )

    def test_region_types_and_sizes(self) -> None:
        for size in (3, 4, 5):
            regions = [
                Region(RegionType.COL, col="B"),
                Region(RegionType.NEIGHBORS, of_cell="B2"),
                Region(RegionType.BOUNDARY),
                Region(
                    RegionType.INTERSECTION,
                    regions=(
                        Region(RegionType.ROW, index=1),
                        Region(RegionType.COL, col="B"),
                    ),
                ),
            ]
            for region in regions:
                self.assert_encoding(
                    Clue("region", ClueType.EXACTLY, region=region, k=1), size
                )

    def test_public_kb_and_fresh_auxiliary_variables(self) -> None:
        region = Region(RegionType.ROW, index=1)
        clue = Clue("two", ClueType.EXACTLY, region=region, k=2)
        state = state_with(clue, fact("A1", False))
        kb = build_kb(state)
        self.assertEqual(kb.statistics.primary_vars, 9)
        self.assertEqual(kb.statistics.aux_vars, kb.num_vars - 9)
        self.assertEqual(kb.statistics.clauses, len(kb.clauses))
        self.assertTrue(solve(kb.clauses, kb.num_vars, (2, 3)).satisfiable)
        self.assertFalse(solve(kb.clauses, kb.num_vars, (-2,)).satisfiable)
        with self.assertRaises(ValueError):
            Encoder(3).encode_clue(Clue("bad", ClueType.FACT, cell="Z9"))


class AgentTests(unittest.TestCase):
    def test_classify_all_builds_one_kb(self) -> None:
        state = state_with(fact("B1"))
        with patch("solver.agent.build_kb", wraps=build_kb) as build:
            verdicts = LogicAgent().classify_all(state)
        build.assert_called_once_with(state)
        self.assertIs(verdicts["A1"], Verdict.UNKNOWN)
        self.assertIs(verdicts["B1"], Verdict.CRIMINAL)
        self.assertEqual(set(verdicts), set(cell_ids(3)) - set(state.revealed))

    def test_step_records_skipped_unknown_queries_and_stops_at_first_proof(self) -> None:
        from unittest.mock import Mock

        before = state_with(fact("B1"))
        after = PublicState(
            before.size,
            before.names,
            before.jobs,
            {**before.revealed, "B1": (Verdict.CRIMINAL, fact("C1"))},
        )
        game = Mock(spec=["get_public_state", "submit_verdict"])
        game.get_public_state.side_effect = [before, after]
        game.submit_verdict.return_value = MoveResult.ACCEPTED
        with patch("solver.agent.solve", wraps=solve) as query:
            record = LogicAgent().step(game)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.cell, "B1")
        self.assertIs(record.verdict, Verdict.CRIMINAL)
        self.assertEqual(
            [(q.literal, q.result) for q in record.sat_queries],
            [(1, "SAT"), (-1, "SAT"), (2, "SAT"), (-2, "UNSAT")],
        )
        self.assertEqual(query.call_count, 4)
        game.submit_verdict.assert_called_once_with("B1", Verdict.CRIMINAL)
        self.assertEqual(record.new_clue_id, "fact_C1")

    def test_stall_rejection_and_timeout_leave_state_unchanged(self) -> None:
        from unittest.mock import Mock

        state = PublicState(3, {}, {}, {})
        game = Mock(spec=["get_public_state", "submit_verdict"])
        game.get_public_state.return_value = state
        self.assertEqual(LogicAgent().run(game), ())
        game.submit_verdict.assert_not_called()
        forced_state = state_with(fact("A1"))
        game.get_public_state.return_value = forced_state
        game.submit_verdict.return_value = MoveResult.NOT_PROVABLE
        self.assertEqual(LogicAgent().run(game), ())
        game.submit_verdict.assert_called_once_with("A1", Verdict.CRIMINAL)
        self.assertEqual(game.get_public_state(), forced_state)
        game.submit_verdict.reset_mock()
        self.assertEqual(LogicAgent(deadline=time.monotonic() - 1).run(game), ())
        game.submit_verdict.assert_not_called()

    def test_classification_and_judging(self) -> None:
        agent = LogicAgent()
        state = state_with(fact("A1"), fact("B1", False))
        self.assertIs(agent.classify(state, "A1"), Verdict.CRIMINAL)
        self.assertIs(agent.classify(state, "B1"), Verdict.INNOCENT)
        self.assertIs(agent.classify(state, "C1"), Verdict.UNKNOWN)
        for cell, claim, result in [
            ("A1", Verdict.CRIMINAL, MoveResult.ACCEPTED),
            ("A1", Verdict.INNOCENT, MoveResult.CONTRADICTED),
            ("C1", Verdict.CRIMINAL, MoveResult.NOT_PROVABLE),
            ("A3", Verdict.INNOCENT, MoveResult.ALREADY_REVEALED),
        ]:
            self.assertIs(agent.judge(state, cell, claim), result)
        self.assertEqual(agent.next_forced(state), ("A1", Verdict.CRIMINAL))
        self.assertEqual(agent.hint(state).cell, "A1")
        self.assertNotIn("A3", agent.classify_all(state))
        inconsistent = state_with(fact("A1"), fact("A1", False))
        self.assertIs(agent.classify(inconsistent, "B1"), Verdict.INCONSISTENT)
        self.assertIs(
            agent.judge(inconsistent, "B1", Verdict.CRIMINAL), MoveResult.INCONSISTENT
        )
        self.assertIsNone(agent.hint(inconsistent))
        with self.assertRaises(ValueError):
            agent.judge(state, "A1", Verdict.UNKNOWN)

    def test_deadline_and_second_query_timeout(self) -> None:
        state = PublicState(3, {}, {}, {})
        agent = LogicAgent(deadline=time.monotonic() - 1)
        self.assertIs(agent.classify(state, "A1"), Verdict.TIMEOUT)
        self.assertIs(agent.judge(state, "A1", Verdict.CRIMINAL), MoveResult.TIMEOUT)
        self.assertIsNone(agent.hint(state))
        sat = SolveResult(True, {}, False, SolveStatistics())
        timeout = SolveResult(None, None, True, SolveStatistics())
        with patch("solver.agent.solve", side_effect=[sat, timeout]):
            self.assertIs(LogicAgent().classify(state, "A1"), Verdict.TIMEOUT)

    def test_uniqueness_and_primary_blocking(self) -> None:
        all_cells = Region(RegionType.EXPLICIT, cells=tuple(cell_ids(3)))
        with_aux = check_uniqueness(
            3, [Clue("zero", ClueType.EXACTLY, region=all_cells, k=0)]
        )
        self.assertIs(with_aux.status, UniquenessStatus.UNIQUE)
        clues = [fact(c, i % 2 == 0) for i, c in enumerate(cell_ids(3))]
        unique = check_uniqueness(3, clues)
        self.assertIs(unique.status, UniquenessStatus.UNIQUE)
        multiple = check_uniqueness(3, [])
        self.assertIs(multiple.status, UniquenessStatus.MULTIPLE)
        self.assertNotEqual(multiple.first_solution, multiple.second_solution)
        self.assertIs(
            check_uniqueness(3, [fact("A1"), fact("A1", False)]).status,
            UniquenessStatus.NO_SOLUTION,
        )
        self.assertIs(
            check_uniqueness(3, [], deadline=time.monotonic() - 1).status,
            UniquenessStatus.TIMEOUT,
        )

    def test_shipped_puzzles_end_to_end(self) -> None:
        paths = sorted((Path(__file__).resolve().parents[1] / "puzzles").glob("*.json"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(puzzle=path.name):
                puzzle = load_puzzle(path)
                agent = LogicAgent(deadline=time.monotonic() + 20)
                game = GameEngine(puzzle, referee=agent)
                before = game.get_public_state()
                trace = agent.run(game)
                self.assertTrue(game.is_solved())
                self.assertEqual(len(trace), puzzle.size**2 - len(before.revealed))
                for record in trace:
                    self.assertEqual(
                        record.verdict is Verdict.CRIMINAL, puzzle.solution[record.cell]
                    )
                    self.assertTrue(
                        any(q.result == "UNSAT" for q in record.sat_queries)
                    )
                self.assertIsNone(agent.step(game))


if __name__ == "__main__":
    unittest.main()
