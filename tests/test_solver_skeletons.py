"""Import and signature smoke tests for student-owned solver skeletons."""

from __future__ import annotations

import unittest

from core.models import PublicState


class SolverSkeletonTests(unittest.TestCase):
    """Ensure every reserved module is importable but not implemented."""

    def test_dpll_skeleton(self) -> None:
        from solver.dpll import SolveResult, SolveStatistics, solve

        result_type = SolveResult(None, None, False, SolveStatistics())
        self.assertIsNone(result_type.satisfiable)
        with self.assertRaises(NotImplementedError):
            solve([], 0)

    def test_encoder_skeleton(self) -> None:
        from solver.encoder import Encoder, EncoderStatistics, KnowledgeBase, build_kb

        encoder = Encoder(3)
        self.assertEqual(encoder.var_of("A1"), 1)
        self.assertEqual(encoder.cell_of(9), "C3")
        record = KnowledgeBase((), 9, EncoderStatistics(9, 0, 0))
        self.assertEqual(record.num_vars, 9)
        with self.assertRaises(NotImplementedError):
            build_kb(PublicState(3, {}, {}, {}))

    def test_agent_skeleton(self) -> None:
        from solver.agent import LogicAgent, UniquenessResult, UniquenessStatus

        record = UniquenessResult(UniquenessStatus.NO_SOLUTION)
        self.assertIs(record.status, UniquenessStatus.NO_SOLUTION)
        with self.assertRaises(NotImplementedError):
            LogicAgent().classify(PublicState(3, {}, {}, {}), "A1")


if __name__ == "__main__":
    unittest.main()
