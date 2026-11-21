"""Typed interface reserved for the future automatic CNF encoder."""

from __future__ import annotations

from dataclasses import dataclass

from core.models import Clue, PublicState
from core.regions import cell_coordinates, cell_ids, validate_size


Clause = list[int]


@dataclass(frozen=True)
class EncoderStatistics:
    """Size statistics for a future encoded knowledge base."""

    primary_vars: int
    aux_vars: int
    clauses: int


@dataclass(frozen=True)
class KnowledgeBase:
    """CNF and metadata returned by the future encoder."""

    clauses: tuple[tuple[int, ...], ...]
    num_vars: int
    statistics: EncoderStatistics


class Encoder:
    """Reserve deterministic variable mapping and clue encoding methods."""

    def __init__(self, size: int) -> None:
        validate_size(size)
        self.size = size

    def var_of(self, cell_id: str) -> int:
        """Map a valid cell ID to its one-based row-major primary variable."""

        row, col = cell_coordinates(cell_id, self.size)
        return row * self.size + col + 1

    def cell_of(self, variable: int) -> str:
        """Map a primary variable to its row-major cell ID."""

        if not isinstance(variable, int) or isinstance(variable, bool):
            raise ValueError("variable must be an integer")
        ids = cell_ids(self.size)
        if not 1 <= variable <= len(ids):
            raise ValueError(f"primary variable must be between 1 and {len(ids)}")
        return ids[variable - 1]

    def encode_clue(self, clue: Clue) -> list[Clause]:
        """Encode one clue after the student supplies the CNF algorithm."""

        raise NotImplementedError("CNF clue encoding is reserved for the student implementation")


def build_kb(state: PublicState) -> KnowledgeBase:
    """Build public-knowledge CNF after the student supplies the encoder."""

    raise NotImplementedError("knowledge-base encoding is reserved for the student implementation")


if __name__ == "__main__":
    smoke_encoder = Encoder(3)
    assert smoke_encoder.var_of("A1") == 1
    assert smoke_encoder.cell_of(9) == "C3"
