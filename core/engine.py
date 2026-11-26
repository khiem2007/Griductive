"""State-owning game engine for manual and future proof-based play."""

from __future__ import annotations

from core.models import (
    Cell,
    ManualResult,
    MoveResult,
    PublicState,
    Puzzle,
    Referee,
    Verdict,
)


class GameEngine:
    """Own private puzzle data and expose only the current public state."""

    def __init__(
        self, puzzle: Puzzle | None = None, referee: Referee | None = None
    ) -> None:
        self._puzzle = puzzle
        self._referee = referee
        self._revealed: set[str] = set()
        self._reset_revealed()

    @property
    def has_referee(self) -> bool:
        """Return whether proof-based verdict checking is installed."""

        return self._referee is not None

    @property
    def has_puzzle(self) -> bool:
        """Return whether a puzzle is currently loaded."""

        return self._puzzle is not None

    def get_public_state(self) -> PublicState:
        """Return names, jobs, and only the statuses and clues already revealed."""

        if self._puzzle is None:
            return PublicState(size=0, names={}, jobs={}, revealed={})
        revealed = {
            cell.id: (cell.status, cell.clue)
            for cell in self._puzzle.cells
            if cell.id in self._revealed
        }
        return PublicState(
            size=self._puzzle.size,
            names={cell.id: cell.name for cell in self._puzzle.cells},
            jobs={cell.id: cell.job for cell in self._puzzle.cells},
            revealed=revealed,
        )

    def submit_verdict(self, cell: str, claimed: Verdict) -> MoveResult:
        """Submit a claim to an injected proof-based referee."""

        if not self.has_referee:
            raise RuntimeError("proof-based verdict checking requires an injected referee")
        puzzle = self._require_puzzle()
        self._validate_claim(cell, claimed)
        if cell in self._revealed:
            return MoveResult.ALREADY_REVEALED
        assert self._referee is not None
        result = self._referee.judge(self.get_public_state(), cell, claimed)
        if result is MoveResult.ACCEPTED:
            private_cell = self._cell_by_id(puzzle, cell)
            if private_cell.status is not claimed:
                raise AssertionError(
                    "referee accepted a verdict that disagrees with the stored solution"
                )
            self._revealed.add(cell)
        return result

    def restart(self) -> None:
        """Restore the loaded puzzle's initially revealed cards."""

        self._reset_revealed()

    def is_solved(self) -> bool:
        """Return whether every card in the loaded puzzle is face-up."""

        return self._puzzle is not None and len(self._revealed) == len(self._puzzle.cells)

    def load(self, puzzle: Puzzle) -> None:
        """Replace the current puzzle after the caller has validated it."""

        self._puzzle = puzzle
        self._reset_revealed()

    def _reset_revealed(self) -> None:
        self._revealed = (
            {cell.id for cell in self._puzzle.cells if cell.revealed}
            if self._puzzle is not None
            else set()
        )

    def _require_puzzle(self) -> Puzzle:
        if self._puzzle is None:
            raise RuntimeError("no puzzle is loaded")
        return self._puzzle

    def _validate_claim(self, cell: str, claimed: Verdict) -> None:
        puzzle = self._require_puzzle()
        valid_ids = {card.id for card in puzzle.cells}
        if cell not in valid_ids:
            raise ValueError(f"unknown cell {cell!r}")
        if claimed not in {Verdict.CRIMINAL, Verdict.INNOCENT}:
            raise ValueError("claimed verdict must be CRIMINAL or INNOCENT")

    @staticmethod
    def _cell_by_id(puzzle: Puzzle, cell_id: str) -> Cell:
        return next(cell for cell in puzzle.cells if cell.id == cell_id)


if __name__ == "__main__":
    from pathlib import Path

    from core.models import load_puzzle

    sample_path = Path("puzzles") / "3x3_easy.json"
    if sample_path.exists():
        smoke_engine = GameEngine(load_puzzle(sample_path))
        assert smoke_engine.get_public_state().size == 3
        assert not smoke_engine.has_referee
