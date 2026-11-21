"""Typed interface reserved for the future self-implemented DPLL solver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


Clause = list[int]


@dataclass(frozen=True)
class SolveStatistics:
    """Counters produced by a future DPLL search."""

    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    runtime: float = 0.0


@dataclass(frozen=True)
class SolveResult:
    """Result record reserved for the future DPLL implementation."""

    satisfiable: bool | None
    model: dict[int, bool] | None
    timed_out: bool
    statistics: SolveStatistics


def solve(
    clauses: Sequence[Clause],
    num_vars: int,
    assumptions: Iterable[int] = (),
    deadline: float | None = None,
) -> SolveResult:
    """Solve CNF with DPLL after the student supplies the algorithm."""

    raise NotImplementedError("DPLL is reserved for the student implementation")


if __name__ == "__main__":
    assert SolveStatistics().decisions == 0
    try:
        solve([], 0)
    except NotImplementedError:
        pass
    else:
        raise AssertionError("the DPLL skeleton must remain unimplemented")
