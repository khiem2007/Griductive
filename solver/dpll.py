"""A deterministic, self-contained DPLL SAT solver."""

from __future__ import annotations

import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

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


class _DPLLSolver:
    """Mutable state and recursive operations for one DPLL invocation."""

    def __init__(
        self,
        clauses: tuple[tuple[int, ...], ...],
        num_vars: int,
        deadline: float | None,
        started_at: float,
    ) -> None:
        self.clauses = clauses # Lưu công thức CNF đã được chuẩn hóa
        self.num_vars = num_vars # Số lượng các biến 
        self.deadline = deadline # Mốc thời gian mà solver phải chạy
        self.started_at = started_at # Thời điểm bắt đầu gọi solver
        self.assignment = [-1] * (num_vars + 1) # Giá trị gán cho các biến theo chuẩn DIMACS, vị trí 0 không được sử dụng để đơn giản hơn
        self.trail: list[int] = [] # Lưu thứ tự các biến được gán để phục vụ backtracking 
        self.decisions = 0 # Đếm số lần DPLL phải tự chọn 1 biến để rẽ nhánh
        self.propagations = 0 # Đếm số phép gán được suy ra từ unit clause hiện tại
        self.backtracks = 0 # Đếm số nhánh đã thử và thất bại

    def result(
        self,
        satisfiable: bool | None,
        *,
        model: dict[int, bool] | None = None,
        timed_out: bool = False,
    ) -> SolveResult:
        """Build a result using the current counters and elapsed runtime."""

        return SolveResult(
            satisfiable=satisfiable,
            model=model,
            timed_out=timed_out,
            statistics=SolveStatistics(
                decisions=self.decisions,
                propagations=self.propagations,
                backtracks=self.backtracks,
                runtime=time.monotonic() - self.started_at,
            ),
        )

    def deadline_check(self) -> None:
        """Stop the complete recursive search once its deadline expires."""

        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise _DeadlineExceeded

    def undo(self, mark: int) -> None:
        """Restore assignments made after a recorded trail position."""

        while len(self.trail) > mark:
            variable = self.trail.pop()
            self.assignment[variable] = -1
    
    
    def assign_literal(self, literal: int) -> bool:
        value = -1
        if literal > 0:
            value = 1
        else:
            value = 0
        if self.assignment[abs(literal)] == -1:
            self.assignment[abs(literal)] = value  
            self.trail.append(literal)
            return True
        return self.assignment[abs(literal)] == value
    
    
    
    
    
    
    def assign_literal(self, literal: int) -> bool:
        """Assign a literal, returning False only for an opposing assignment."""

        variable = abs(literal)
        value = 1 if literal > 0 else 0
        current = self.assignment[variable]
        if current == -1:
            self.assignment[variable] = value
            self.trail.append(variable)
            return True
        return current == value 
                
                
                
    def propagate_units(self) -> bool:
        """Repeatedly scan all clauses until stable or a conflict appears."""

        while True:
            self.deadline_check()
            changed = False
            for clause in self.clauses:
                self.deadline_check()
                satisfied, unassigned_count, unit_literal = self._analyze_clause(clause)
                if satisfied:
                    continue
                if unassigned_count == 0:
                    return False
                if unassigned_count == 1:
                    if not self.assign_literal(unit_literal):
                        return False
                    self.propagations += 1
                    changed = True
            if not changed:
                return True

    def choose_variable(self) -> int| None:
        """Choose the smallest unassigned variable in an unsatisfied clause"""

        candidate: int | None 
        for clause in self.clauses:
            self.deadline_check()
            for literal in clause:
                if self._is_true(literal): continue
            for literal in clause:
                variable = abs(literal)
                if self.assignment[variable] == -1 and (not candidate or candidate > variable):
                    candidate = variable
        return candidate
        
        
    def search(self) -> bool:
        """Run recursive DPLL, trying True before False at each decision."""

        self.deadline_check()
        level_mark = len(self.trail)
        if not self.propagate_units():
            self.undo(level_mark)
            return False

        variable = self.choose_variable()
        if variable is None:
            return True

        self.decisions += 1
        branch_mark = len(self.trail)
        for value in (True, False):
            literal = variable if value else -variable
            if not self.assign_literal(literal):
                raise AssertionError("selected DPLL variable was already assigned")
            if self.search():
                return True
            self.undo(branch_mark)
            self.backtracks += 1

        self.undo(level_mark)
        return False

    def build_model(self) -> dict[int, bool]:
        """Return a complete model, assigning False to every free variable."""

        return {
            variable: self.assignment[variable] == 1
            if self.assignment[variable] != -1
            else False
            for variable in range(1, self.num_vars + 1)
        }

    def _is_true(self, literal: int) -> bool:
        """Return whether a literal is true under the partial assignment."""

        value = self.assignment[abs(literal)]
        return (literal > 0 and value == 1) or (literal < 0 and value == 0)

    def _analyze_clause(self, clause: tuple[int, ...]) -> tuple[bool, int, int]:
        """Return satisfied flag, free-literal count, and last free literal."""

        unassigned_count = 0
        unit_literal = 0
        for literal in clause:
            if self.assignment[abs(literal)] == -1:
                unassigned_count += 1
                unit_literal = literal
            elif self._is_true(literal):
                return True, unassigned_count, unit_literal
        return False, unassigned_count, unit_literal


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

    solver = _DPLLSolver(
        normalized_clauses,
        num_vars,
        deadline,
        started_at,
    )

    for literal in normalized_assumptions:
        if not solver.assign_literal(literal):
            return solver.result(False)

    try:
        solver.deadline_check()
        satisfiable = solver.search()
    except _DeadlineExceeded:
        return solver.result(None, timed_out=True)

    if not satisfiable:
        return solver.result(False)
    return solver.result(True, model=solver.build_model())


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
