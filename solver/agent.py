"""Proof-based deductions using only public knowledge and SAT queries."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import Enum

from core.models import Clue, GameInterface, MoveResult, PublicState, Verdict
from core.regions import cell_ids
from solver.dpll import solve
from solver.encoder import Encoder, build_kb


@dataclass(frozen=True)
class Hint:
    """A proved verdict using public knowledge only."""

    cell: str
    verdict: Verdict
    relevant_clue_id: str | None = None


@dataclass(frozen=True)
class SatQuery:
    """One SAT query recorded as SAT, UNSAT, or TIMEOUT."""

    literal: int | None
    result: str


@dataclass(frozen=True)
class TraceStep:
    """One accepted no-guess deduction, with its public premises and queries."""

    step: int
    active_clue_ids: tuple[str, ...]
    sat_queries: tuple[SatQuery, ...]
    cell: str
    verdict: Verdict
    new_clue_id: str | None


class UniquenessStatus(str, Enum):
    """Possible outcomes of a complete-clue uniqueness check."""

    UNIQUE = "UNIQUE"
    MULTIPLE = "MULTIPLE"
    NO_SOLUTION = "NO_SOLUTION"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class UniquenessResult:
    """Uniqueness outcome and up to two primary assignments."""

    status: UniquenessStatus
    first_solution: dict[str, bool] | None = None
    second_solution: dict[str, bool] | None = None


class LogicAgent:
    """Prove verdicts by testing both polarities against public CNF.

    ``deadline`` is an optional absolute time.monotonic() timestamp shared by
    all SAT calls, including calls made during an automatic run.
    """

    def __init__(self, deadline: float | None = None) -> None:
        self.deadline = deadline
        self._steps = 0

    def _classify_cells(
        self, state: PublicState, cells: Iterable[str]
    ) -> Iterator[tuple[str, Verdict, tuple[SatQuery, ...]]]:
        """Classify requested cells lazily, sharing one KB and recording queries."""

        encoder = Encoder(state.size)
        kb = build_kb(state)
        clauses = [list(clause) for clause in kb.clauses]
        for cell in cells:
            variable = encoder.var_of(cell)
            queries: list[SatQuery] = []
            outcomes: list[bool] = []
            # Test both statuses against public knowledge to establish entailment.
            for literal in (variable, -variable):
                result = solve(clauses, kb.num_vars, (literal,), self.deadline)
                if result.timed_out or result.satisfiable is None:
                    label = "TIMEOUT"
                elif result.satisfiable:
                    label = "SAT"
                else:
                    label = "UNSAT"
                queries.append(SatQuery(literal, label))
                if result.timed_out or result.satisfiable is None:
                    verdict = Verdict.TIMEOUT
                    break
                outcomes.append(result.satisfiable)
            else:
                verdict = {
                    (True, True): Verdict.UNKNOWN,
                    (True, False): Verdict.CRIMINAL,
                    (False, True): Verdict.INNOCENT,
                    (False, False): Verdict.INCONSISTENT,
                }[(outcomes[0], outcomes[1])]
            yield cell, verdict, tuple(queries)

    def classify(self, state: PublicState, cell: str) -> Verdict:
        """Return a forced status, UNKNOWN, INCONSISTENT, or TIMEOUT."""

        _, verdict, _ = next(self._classify_cells(state, (cell,)))
        return verdict

    def judge(self, state: PublicState, cell: str, claimed: Verdict) -> MoveResult:
        """Accept only entailed claims, distinguishing contradiction and timeout."""

        if claimed not in {Verdict.CRIMINAL, Verdict.INNOCENT}:
            raise ValueError("claimed verdict must be CRIMINAL or INNOCENT")
        Encoder(state.size).var_of(cell)
        if cell in state.revealed:
            return MoveResult.ALREADY_REVEALED
        verdict = self.classify(state, cell)
        if verdict is Verdict.INCONSISTENT:
            return MoveResult.INCONSISTENT
        if verdict is Verdict.TIMEOUT:
            return MoveResult.TIMEOUT
        if verdict is Verdict.UNKNOWN:
            return MoveResult.NOT_PROVABLE

        if verdict is claimed:
            return MoveResult.ACCEPTED
        else:
            return MoveResult.CONTRADICTED

    def hint(self, state: PublicState) -> Hint | None:
        """Return the first forced hidden cell, or None when no proof is found."""

        forced = self.next_forced(state)
        if forced is not None:
            return Hint(*forced)
        else:
            return None

    def next_forced(self, state: PublicState) -> tuple[str, Verdict] | None:
        """Return the first forced hidden cell in row-major order."""

        cells = (c for c in cell_ids(state.size) if c not in state.revealed)
        for cell, verdict, _ in self._classify_cells(state, cells):
            if verdict in {Verdict.TIMEOUT, Verdict.INCONSISTENT}:
                return None
            if verdict in {Verdict.CRIMINAL, Verdict.INNOCENT}:
                return cell, verdict
        return None

    def classify_all(self, state: PublicState) -> dict[str, Verdict]:
        """Classify all hidden cells against the same public knowledge base."""

        cells = (c for c in cell_ids(state.size) if c not in state.revealed)
        return {cell: verdict
                for cell, verdict, _ in self._classify_cells(state, cells)}

    def step(self, game: GameInterface) -> TraceStep | None:
        """Submit one proved move and record it only if the game accepts it."""

        before = game.get_public_state()
        cells = (c for c in cell_ids(before.size) if c not in before.revealed)
        queries: list[SatQuery] = []
        for cell, verdict, queried in self._classify_cells(before, cells):
            queries.extend(queried)
            if verdict in {Verdict.TIMEOUT, Verdict.INCONSISTENT}:
                return None
            if verdict in {Verdict.CRIMINAL, Verdict.INNOCENT}:
                break
        else:
            return None
        if game.submit_verdict(cell, verdict) is not MoveResult.ACCEPTED:
            return None
        after = game.get_public_state()
        if cell not in after.revealed:
            raise RuntimeError("game accepted a move without revealing the cell")
        self._steps += 1
        return TraceStep(
            self._steps,
            tuple(
                before.revealed[c][1].id
                for c in cell_ids(before.size)
                if c in before.revealed
            ),
            tuple(queries),
            cell,
            verdict,
            after.revealed[cell][1].id,
        )

    def run(self, game: GameInterface) -> tuple[TraceStep, ...]:
        """Reveal proved cells until completed, stalled, rejected, or timed out."""

        trace: list[TraceStep] = []
        while True:
            record = self.step(game)
            if record is None:
                break
            trace.append(record)
        return tuple(trace)


def check_uniqueness(
    size: int, clues: Sequence[Clue], *, deadline: float | None = None
) -> UniquenessResult:
    """Find up to two distinct primary models, ignoring auxiliary assignments."""

    encoder = Encoder(size)
    clauses: list[list[int]] = []
    for clue in clues:
        clauses.extend(encoder.encode_clue(clue))
    first = solve(clauses, encoder.num_vars, deadline=deadline)
    if first.timed_out:
        return UniquenessResult(UniquenessStatus.TIMEOUT)
    if not first.satisfiable:
        return UniquenessResult(UniquenessStatus.NO_SOLUTION)
    assert first.model is not None
    ids = cell_ids(size)
    first_solution = {cell: first.model[i] for i, cell in enumerate(ids, 1)}
    blocking_clause: list[int] = []
    for variable in range(1, size * size + 1):
        if first.model[variable]:
            blocking_clause.append(-variable)
        else:
            blocking_clause.append(variable)
    clauses.append(blocking_clause)
    second = solve(clauses, encoder.num_vars, deadline=deadline)
    if second.timed_out:
        return UniquenessResult(UniquenessStatus.TIMEOUT, first_solution)
    if not second.satisfiable:
        return UniquenessResult(UniquenessStatus.UNIQUE, first_solution)
    assert second.model is not None
    return UniquenessResult(
        UniquenessStatus.MULTIPLE,
        first_solution,
        {cell: second.model[i] for i, cell in enumerate(ids, 1)},
    )


if __name__ == "__main__":
    assert UniquenessStatus.UNIQUE.value == "UNIQUE"
    assert LogicAgent().classify(PublicState(3, {}, {}, {}), "A1") is Verdict.UNKNOWN
