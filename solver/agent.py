"""Typed interface reserved for the future proof-based LogicAgent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from core.models import Clue, GameInterface, MoveResult, PublicState, Verdict


@dataclass(frozen=True)
class Hint:
    """A future proof-based hint using public knowledge only."""

    cell: str
    verdict: Verdict
    relevant_clue_id: str | None = None


@dataclass(frozen=True)
class SatQuery:
    """One SAT query recorded in a future deduction trace."""

    literal: int | None
    result: str


@dataclass(frozen=True)
class TraceStep:
    """One future no-guess deduction step."""

    step: int
    active_clue_ids: tuple[str, ...]
    sat_queries: tuple[SatQuery, ...]
    cell: str
    verdict: Verdict
    new_clue_id: str | None


class UniquenessStatus(str, Enum):
    """Possible outcomes of the future complete-clue uniqueness check."""

    UNIQUE = "UNIQUE"
    MULTIPLE = "MULTIPLE"
    NO_SOLUTION = "NO_SOLUTION"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class UniquenessResult:
    """Future uniqueness outcome and up to two primary assignments."""

    status: UniquenessStatus
    first_solution: dict[str, bool] | None = None
    second_solution: dict[str, bool] | None = None


class LogicAgent:
    """Reserve the proof-based agent API without implementing algorithms."""

    def classify(self, state: PublicState, cell: str) -> Verdict:
        """Classify one cell from public knowledge in the future solver."""

        raise NotImplementedError("LogicAgent is reserved for the student implementation")

    def judge(
        self, state: PublicState, cell: str, claimed: Verdict
    ) -> MoveResult:
        """Judge one proof-based claim in the future solver."""

        raise NotImplementedError("LogicAgent is reserved for the student implementation")

    def hint(self, state: PublicState) -> Hint | None:
        """Return a future proof-based hint."""

        raise NotImplementedError("LogicAgent is reserved for the student implementation")

    def next_forced(self, state: PublicState) -> tuple[str, Verdict] | None:
        """Return the first future forced cell in row-major order."""

        raise NotImplementedError("LogicAgent is reserved for the student implementation")

    def classify_all(self, state: PublicState) -> dict[str, Verdict]:
        """Classify all unresolved cells in the future solver."""

        raise NotImplementedError("LogicAgent is reserved for the student implementation")

    def step(self, game: GameInterface) -> TraceStep | None:
        """Perform one future queued deduction step."""

        raise NotImplementedError("LogicAgent is reserved for the student implementation")

    def run(self, game: GameInterface) -> tuple[TraceStep, ...]:
        """Run the future no-guess deduction loop."""

        raise NotImplementedError("LogicAgent is reserved for the student implementation")


def check_uniqueness(size: int, clues: Sequence[Clue]) -> UniquenessResult:
    """Check complete-clue uniqueness after the student supplies the solver."""

    raise NotImplementedError("uniqueness checking is reserved for the student implementation")


if __name__ == "__main__":
    assert UniquenessStatus.UNIQUE.value == "UNIQUE"
    try:
        LogicAgent().classify(PublicState(3, {}, {}, {}), "A1")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("the LogicAgent skeleton must remain unimplemented")
