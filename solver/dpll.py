"""A deterministic, self-contained DPLL SAT solver."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Iterable, Sequence


Clause = list[int]


@dataclass(frozen=True)
class SolveStatistics:
    """Counters collected during one DPLL search."""

    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    runtime: float = 0.0


@dataclass(frozen=True)
class SolveResult:
    """The SAT status, complete model, timeout flag, and search statistics."""

    satisfiable: bool | None
    model: dict[int, bool] | None
    timed_out: bool
    statistics: SolveStatistics


class _DeadlineExceeded(Exception):
    """Internal control-flow signal used to stop every recursive branch."""


def solve(
    clauses: Sequence[Clause],
    num_vars: int,
    assumptions: Iterable[int] = (),
    deadline: float | None = None,
) -> SolveResult:
    """Solve a DIMACS-style CNF formula with deterministic DPLL.

    Variables are numbered from 1 through ``num_vars``. Positive literals mean
    True and negative literals mean False. ``deadline`` is an absolute
    ``time.monotonic()`` timestamp. A timeout never reports SAT or UNSAT.
    """

    started_at = time.monotonic()
    if not isinstance(num_vars, int) or isinstance(num_vars, bool) or num_vars < 0:
        raise ValueError("num_vars must be a non-negative integer")

    normalized_clauses = _normalize_clauses(clauses, num_vars)
    normalized_assumptions = _validate_assumptions(assumptions, num_vars)
    required_recursion_limit = num_vars + 200
    if required_recursion_limit > sys.getrecursionlimit():
        sys.setrecursionlimit(required_recursion_limit)

    assignment = [-1] * (num_vars + 1)
    trail: list[int] = []
    decisions = 0
    propagations = 0
    backtracks = 0

    def statistics() -> SolveStatistics:
        return SolveStatistics(
            decisions = decisions,
            propagations = propagations,
            backtracks = backtracks,
            runtime = time.monotonic() - started_at,
        )

    def deadline_check() -> None:
        if deadline is not None and time.monotonic() >= deadline:
            raise _DeadlineExceeded

    def undo(mark: int) -> None:
        while len(trail) > mark:
            variable = trail.pop()
            assignment[variable] = -1

    def assign_literal(literal: int) -> bool:
        variable = abs(literal)
        value = 1 if literal > 0 else 0
        current = assignment[variable]
        if current == -1:
            assignment[variable] = value
            trail.append(variable)
            return True
        return current == value

    def propagate_units() -> bool:
        nonlocal propagations
        while True:
            deadline_check()
            changed = False
            for clause in normalized_clauses:
                deadline_check()
                satisfied = False
                unassigned_count = 0
                unit_literal = 0
                for literal in clause:
                    value = assignment[abs(literal)]
                    if value == -1:
                        unassigned_count += 1
                        unit_literal = literal
                    elif (literal > 0 and value == 1) or (literal < 0 and value == 0):
                        satisfied = True
                        break
                if satisfied:
                    continue
                if unassigned_count == 0:
                    return False
                if unassigned_count == 1:
                    if not assign_literal(unit_literal):
                        return False
                    propagations += 1
                    changed = True
            if not changed:
                return True

    def choose_variable() -> int | None:
        candidate: int | None = None
        for clause in normalized_clauses:
            deadline_check()
            clause_satisfied = False
            for literal in clause:
                value = assignment[abs(literal)]
                if (literal > 0 and value == 1) or (literal < 0 and value == 0):
                    clause_satisfied = True
                    break
            if clause_satisfied:
                continue
            for literal in clause:
                variable = abs(literal)
                if assignment[variable] == -1 and (
                    candidate is None or variable < candidate
                ):
                    candidate = variable
        return candidate

    def search() -> bool:
        nonlocal decisions, backtracks
        deadline_check()
        level_mark = len(trail)
        if not propagate_units():
            undo(level_mark)
            return False

        variable = choose_variable()
        if variable is None:
            return True

        decisions += 1
        branch_mark = len(trail)
        for value in (True, False):
            literal = variable if value else -variable
            if not assign_literal(literal):
                raise AssertionError("selected DPLL variable was already assigned")
            if search():
                return True
            undo(branch_mark)
            backtracks += 1

        undo(level_mark)
        return False

    for literal in normalized_assumptions:
        if not assign_literal(literal):
            return SolveResult(
                satisfiable=False,
                model=None,
                timed_out=False,
                statistics=statistics(),
            )

    try:
        deadline_check()
        satisfiable = search()
    except _DeadlineExceeded:
        return SolveResult(
            satisfiable=None,
            model=None,
            timed_out=True,
            statistics=statistics(),
        )

    if not satisfiable:
        return SolveResult(
            satisfiable=False,
            model=None,
            timed_out=False,
            statistics=statistics(),
        )

    model = {
        variable: assignment[variable] == 1
        if assignment[variable] != -1
        else False
        for variable in range(1, num_vars + 1)
    }
    return SolveResult(
        satisfiable=True,
        model=model,
        timed_out=False,
        statistics=statistics(),
    )


def _normalize_clauses(
    clauses: Sequence[Clause], num_vars: int
) -> tuple[tuple[int, ...], ...]:
    """Validate clauses, remove duplicate literals, and discard tautologies."""

    normalized: list[tuple[int, ...]] = []
    for clause_index, clause in enumerate(clauses):
        if not isinstance(clause, Sequence) or isinstance(clause, (str, bytes)):
            raise ValueError(f"clause {clause_index} must be a sequence of literals")
        seen: set[int] = set()
        cleaned: list[int] = []
        tautology = False
        for literal in clause:
            _validate_literal(literal, num_vars, f"clause {clause_index}")
            if -literal in seen:
                tautology = True
            if literal not in seen:
                seen.add(literal)
                cleaned.append(literal)
        if not tautology:
            normalized.append(tuple(cleaned))
    return tuple(normalized)


def _validate_assumptions(
    assumptions: Iterable[int], num_vars: int
) -> tuple[int, ...]:
    """Materialize and validate temporary assumption literals."""

    try:
        materialized = tuple(assumptions)
    except TypeError as exc:
        raise ValueError("assumptions must be an iterable of literals") from exc
    for literal in materialized:
        _validate_literal(literal, num_vars, "assumptions")
    return materialized


def _validate_literal(literal: int, num_vars: int, context: str) -> None:
    if not isinstance(literal, int) or isinstance(literal, bool) or literal == 0:
        raise ValueError(f"{context} contains a non-zero-integer literal violation")
    if abs(literal) > num_vars:
        raise ValueError(
            f"{context} literal {literal} exceeds declared variable count {num_vars}"
        )


if __name__ == "__main__":
    smoke_sat = solve([[1, 2], [-1, 2]], 2)
    assert smoke_sat.satisfiable is True
    assert smoke_sat.model == {1: True, 2: True}
    smoke_unsat = solve([[1], [-1]], 1)
    assert smoke_unsat.satisfiable is False
