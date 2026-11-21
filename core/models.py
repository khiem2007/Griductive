"""Typed data models and JSON loading for Griductive puzzles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Protocol


class Verdict(str, Enum):
    """A logical classification returned by the agent."""

    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"
    INCONSISTENT = "INCONSISTENT"
    TIMEOUT = "TIMEOUT"


class MoveResult(str, Enum):
    """The result of submitting a verdict to the game engine."""

    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    ALREADY_REVEALED = "ALREADY_REVEALED"
    INCONSISTENT = "INCONSISTENT"
    TIMEOUT = "TIMEOUT"


class ClueType(str, Enum):
    """Supported structured clue templates."""

    FACT = "FACT"
    SAME = "SAME"
    DIFFERENT = "DIFFERENT"
    EXACTLY = "EXACTLY"
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"
    PARITY = "PARITY"
    COMPARE = "COMPARE"


class RegionType(str, Enum):
    """Supported region expressions."""

    ROW = "ROW"
    COL = "COL"
    NEIGHBORS = "NEIGHBORS"
    EXPLICIT = "EXPLICIT"
    BOUNDARY = "BOUNDARY"
    INTERSECTION = "INTERSECTION"


@dataclass(frozen=True)
class Region:
    """A validated, structured description of a group of cells."""

    type: RegionType
    index: int | None = None
    col: str | None = None
    of_cell: str | None = None
    cells: tuple[str, ...] = ()
    regions: tuple[Region, ...] = ()


@dataclass(frozen=True)
class Clue:
    """A structured Griductive clue."""

    id: str
    type: ClueType
    cell: str | None = None
    status: Verdict | None = None
    cells: tuple[str, ...] = ()
    region: Region | None = None
    k: int | None = None
    parity: str | None = None
    left: Region | None = None
    right: Region | None = None
    op: str | None = None


@dataclass(frozen=True)
class Cell:
    """Complete private data for one puzzle card."""

    id: str
    name: str
    job: str
    status: Verdict
    revealed: bool
    clue: Clue


@dataclass(frozen=True)
class PublicState:
    """The only game information visible to the solver and GUI."""

    size: int
    names: dict[str, str]
    jobs: dict[str, str]
    revealed: dict[str, tuple[Verdict, Clue]]


@dataclass(frozen=True)
class Puzzle:
    """A complete puzzle, including its private solution and all clues."""

    size: int
    cells: tuple[Cell, ...]

    @property
    def solution(self) -> dict[str, bool]:
        """Return the stored complete solution as Boolean cell values."""

        return {cell.id: cell.status is Verdict.CRIMINAL for cell in self.cells}


class Referee(Protocol):
    """Protocol used by the engine to validate a claimed verdict."""

    def judge(
        self, state: PublicState, cell: str, claimed: Verdict
    ) -> MoveResult:
        """Judge a claim using public knowledge only."""


class GameInterface(Protocol):
    """Minimal game interface available to an automatic agent."""

    def get_public_state(self) -> PublicState:
        """Return a snapshot of the current public knowledge."""

    def submit_verdict(self, cell: str, claimed: Verdict) -> MoveResult:
        """Submit one logically justified verdict."""


def _expect_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _check_keys(
    data: Mapping[str, Any],
    required: set[str],
    context: str,
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    missing = required - data.keys()
    unknown = data.keys() - allowed
    if missing:
        raise ValueError(f"{context} is missing fields: {sorted(missing)}")
    if unknown:
        raise ValueError(f"{context} has unknown fields: {sorted(unknown)}")


def _nonempty_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value


def _enum_value(enum_type: type[Enum], value: Any, context: str) -> Any:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_type)
        raise ValueError(f"unknown {context} {value!r}; expected one of {allowed}") from exc


def region_from_dict(raw: Any, context: str = "region") -> Region:
    """Parse a region object without applying board-size validation yet."""

    data = _expect_object(raw, context)
    if "type" not in data:
        raise ValueError(f"{context} is missing fields: ['type']")
    region_type = _enum_value(RegionType, data["type"], f"{context} type")

    if region_type is RegionType.ROW:
        _check_keys(data, {"type", "index"}, context)
        index = data["index"]
        if not isinstance(index, int) or isinstance(index, bool):
            raise ValueError(f"{context}.index must be an integer")
        return Region(type=region_type, index=index)
    if region_type is RegionType.COL:
        _check_keys(data, {"type", "col"}, context)
        return Region(type=region_type, col=_nonempty_string(data["col"], f"{context}.col"))
    if region_type is RegionType.NEIGHBORS:
        _check_keys(data, {"type", "of"}, context)
        return Region(
            type=region_type,
            of_cell=_nonempty_string(data["of"], f"{context}.of"),
        )
    if region_type is RegionType.EXPLICIT:
        _check_keys(data, {"type", "cells"}, context)
        raw_cells = data["cells"]
        if not isinstance(raw_cells, list):
            raise ValueError(f"{context}.cells must be a list")
        cells = tuple(
            _nonempty_string(cell, f"{context}.cells[{index}]")
            for index, cell in enumerate(raw_cells)
        )
        if len(set(cells)) != len(cells):
            raise ValueError(f"{context}.cells must not contain duplicates")
        return Region(type=region_type, cells=cells)
    if region_type is RegionType.BOUNDARY:
        _check_keys(data, {"type"}, context)
        return Region(type=region_type)

    _check_keys(data, {"type", "of"}, context)
    raw_regions = data["of"]
    if not isinstance(raw_regions, list):
        raise ValueError(f"{context}.of must be a list")
    if len(raw_regions) < 2:
        raise ValueError(f"{context}.of must contain at least two regions")
    return Region(
        type=region_type,
        regions=tuple(
            region_from_dict(item, f"{context}.of[{index}]")
            for index, item in enumerate(raw_regions)
        ),
    )


def clue_from_dict(raw: Any, context: str = "clue") -> Clue:
    """Parse one structured clue object."""

    data = _expect_object(raw, context)
    if "type" not in data:
        raise ValueError(f"{context} is missing fields: ['type']")
    clue_type = _enum_value(ClueType, data["type"], f"{context} type")
    clue_id = _nonempty_string(data.get("id"), f"{context}.id")

    if clue_type is ClueType.FACT:
        _check_keys(data, {"id", "type", "cell", "status"}, context)
        return Clue(
            id=clue_id,
            type=clue_type,
            cell=_nonempty_string(data["cell"], f"{context}.cell"),
            status=_enum_value(Verdict, data["status"], f"{context}.status"),
        )
    if clue_type in {ClueType.SAME, ClueType.DIFFERENT}:
        _check_keys(data, {"id", "type", "cells"}, context)
        raw_cells = data["cells"]
        if not isinstance(raw_cells, list) or len(raw_cells) != 2:
            raise ValueError(f"{context}.cells must contain exactly two cells")
        cells = tuple(
            _nonempty_string(cell, f"{context}.cells[{index}]")
            for index, cell in enumerate(raw_cells)
        )
        return Clue(id=clue_id, type=clue_type, cells=cells)
    if clue_type in {ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST}:
        _check_keys(data, {"id", "type", "region", "k"}, context)
        k = data["k"]
        if not isinstance(k, int) or isinstance(k, bool):
            raise ValueError(f"{context}.k must be an integer")
        return Clue(
            id=clue_id,
            type=clue_type,
            region=region_from_dict(data["region"], f"{context}.region"),
            k=k,
        )
    if clue_type is ClueType.PARITY:
        _check_keys(data, {"id", "type", "region", "parity"}, context)
        return Clue(
            id=clue_id,
            type=clue_type,
            region=region_from_dict(data["region"], f"{context}.region"),
            parity=_nonempty_string(data["parity"], f"{context}.parity"),
        )

    _check_keys(data, {"id", "type", "left", "right", "op"}, context)
    return Clue(
        id=clue_id,
        type=clue_type,
        left=region_from_dict(data["left"], f"{context}.left"),
        right=region_from_dict(data["right"], f"{context}.right"),
        op=_nonempty_string(data["op"], f"{context}.op"),
    )


def puzzle_from_dict(raw: Any) -> Puzzle:
    """Build and fully validate a puzzle from decoded JSON data."""

    data = _expect_object(raw, "puzzle")
    _check_keys(data, {"size", "cells"}, "puzzle")
    size = data["size"]
    if not isinstance(size, int) or isinstance(size, bool) or size not in {3, 4, 5}:
        raise ValueError("puzzle.size must be one of 3, 4, or 5")
    raw_cells = data["cells"]
    if not isinstance(raw_cells, list):
        raise ValueError("puzzle.cells must be a list")
    if len(raw_cells) != size * size:
        raise ValueError(f"puzzle.cells must contain exactly {size * size} cards")

    cells: list[Cell] = []
    for index, item in enumerate(raw_cells):
        context = f"puzzle.cells[{index}]"
        cell_data = _expect_object(item, context)
        _check_keys(
            cell_data,
            {"id", "name", "job", "status", "revealed", "clue"},
            context,
        )
        status = _enum_value(Verdict, cell_data["status"], f"{context}.status")
        if status not in {Verdict.CRIMINAL, Verdict.INNOCENT}:
            raise ValueError(f"{context}.status must be CRIMINAL or INNOCENT")
        revealed = cell_data["revealed"]
        if not isinstance(revealed, bool):
            raise ValueError(f"{context}.revealed must be a Boolean")
        cells.append(
            Cell(
                id=_nonempty_string(cell_data["id"], f"{context}.id"),
                name=_nonempty_string(cell_data["name"], f"{context}.name"),
                job=_nonempty_string(cell_data["job"], f"{context}.job"),
                status=status,
                revealed=revealed,
                clue=clue_from_dict(cell_data["clue"], f"{context}.clue"),
            )
        )

    from core.regions import cell_ids, evaluate_clue_directly, validate_clue

    expected_ids = cell_ids(size)
    actual_ids = [cell.id for cell in cells]
    if len(set(actual_ids)) != len(actual_ids):
        raise ValueError("puzzle cell IDs must be unique")
    if set(actual_ids) != set(expected_ids):
        missing = sorted(set(expected_ids) - set(actual_ids))
        extra = sorted(set(actual_ids) - set(expected_ids))
        raise ValueError(f"puzzle cell IDs are invalid; missing={missing}, extra={extra}")
    clue_ids = [cell.clue.id for cell in cells]
    if len(set(clue_ids)) != len(clue_ids):
        raise ValueError("clue IDs must be unique")

    by_id = {cell.id: cell for cell in cells}
    normalized_cells = tuple(by_id[cell_id] for cell_id in expected_ids)
    puzzle = Puzzle(size=size, cells=normalized_cells)
    for cell in puzzle.cells:
        validate_clue(cell.clue, size)
        if not evaluate_clue_directly(cell.clue, puzzle.solution, size):
            raise ValueError(
                f"{cell.clue.id} on card {cell.id} is false under the stored solution"
            )
    return puzzle


def load_puzzle(path: str | Path) -> Puzzle:
    """Load and validate one UTF-8 JSON puzzle file."""

    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read puzzle {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in puzzle {source}: {exc}") from exc
    return puzzle_from_dict(raw)


def region_to_dict(region: Region) -> dict[str, Any]:
    """Convert a region dataclass to the required JSON shape."""

    if region.type is RegionType.ROW:
        return {"type": region.type.value, "index": region.index}
    if region.type is RegionType.COL:
        return {"type": region.type.value, "col": region.col}
    if region.type is RegionType.NEIGHBORS:
        return {"type": region.type.value, "of": region.of_cell}
    if region.type is RegionType.EXPLICIT:
        return {"type": region.type.value, "cells": list(region.cells)}
    if region.type is RegionType.BOUNDARY:
        return {"type": region.type.value}
    return {
        "type": region.type.value,
        "of": [region_to_dict(child) for child in region.regions],
    }


def clue_to_dict(clue: Clue) -> dict[str, Any]:
    """Convert a clue dataclass to the required JSON shape."""

    data: dict[str, Any] = {"id": clue.id, "type": clue.type.value}
    if clue.type is ClueType.FACT:
        data.update({"cell": clue.cell, "status": clue.status.value if clue.status else None})
    elif clue.type in {ClueType.SAME, ClueType.DIFFERENT}:
        data["cells"] = list(clue.cells)
    elif clue.type in {ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST}:
        if clue.region is None:
            raise ValueError(f"{clue.id} has no region")
        data.update({"k": clue.k, "region": region_to_dict(clue.region)})
    elif clue.type is ClueType.PARITY:
        if clue.region is None:
            raise ValueError(f"{clue.id} has no region")
        data.update({"parity": clue.parity, "region": region_to_dict(clue.region)})
    else:
        if clue.left is None or clue.right is None:
            raise ValueError(f"{clue.id} has incomplete comparison regions")
        data.update(
            {
                "left": region_to_dict(clue.left),
                "right": region_to_dict(clue.right),
                "op": clue.op,
            }
        )
    return data


def puzzle_to_dict(puzzle: Puzzle) -> dict[str, Any]:
    """Convert a complete puzzle to the exact JSON schema."""

    return {
        "size": puzzle.size,
        "cells": [
            {
                "id": cell.id,
                "name": cell.name,
                "job": cell.job,
                "status": cell.status.value,
                "revealed": cell.revealed,
                "clue": clue_to_dict(cell.clue),
            }
            for cell in puzzle.cells
        ],
    }


def save_puzzle(puzzle: Puzzle, path: str | Path) -> None:
    """Validate and save a puzzle as deterministic UTF-8 JSON."""

    validated = puzzle_from_dict(puzzle_to_dict(puzzle))
    target = Path(path)
    if not target.parent.exists():
        raise ValueError(f"output directory does not exist: {target.parent}")
    target.write_text(
        json.dumps(puzzle_to_dict(validated), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    sample = Region(type=RegionType.EXPLICIT, cells=("A1",))
    assert region_to_dict(sample) == {"type": "EXPLICIT", "cells": ["A1"]}
    assert Verdict.CRIMINAL.value == "CRIMINAL"
