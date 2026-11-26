"""Capture actual solver queries and accepted deductions for the trace viewer."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from core.models import Clue, PublicState, Verdict
from solver.agent import LogicAgent, SatQuery, TraceStep


class TracedAgent(LogicAgent):
    """Collect SAT query records from the existing classification implementation."""

    def __init__(self) -> None:
        super().__init__()
        self.queries: list[SatQuery] = []

    def _classify_cells(
        self, state: PublicState, cells: Iterable[str]
    ) -> Iterator[tuple[str, Verdict, tuple[SatQuery, ...]]]:
        for cell, verdict, queries in super()._classify_cells(state, cells):
            self.queries.extend(queries)
            yield cell, verdict, queries


@dataclass(frozen=True)
class TraceEntry:
    """An accepted move, its public premises, actual queries, and revealed clue."""

    deduction: TraceStep
    source: str
    new_clue: Clue
