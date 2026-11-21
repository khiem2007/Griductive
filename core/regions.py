"""Region resolution, direct clue semantics, and clue descriptions."""

from __future__ import annotations

import re
from collections.abc import Mapping

from core.models import Clue, ClueType, Region, RegionType, Verdict


_CELL_PATTERN = re.compile(r"^([A-Z])([1-9][0-9]*)$")
_COMPARE_OPERATORS = frozenset({">", ">=", "=", "<=", "<"})


def validate_size(size: int) -> None:
    """Validate a supported square board size."""

    if not isinstance(size, int) or isinstance(size, bool) or size not in {3, 4, 5}:
        raise ValueError("size must be one of 3, 4, or 5")


def cell_ids(size: int) -> list[str]:
    """Return every cell ID in deterministic row-major order."""

    validate_size(size)
    return [f"{chr(65 + col)}{row}" for row in range(1, size + 1) for col in range(size)]


def cell_coordinates(cell_id: str, size: int) -> tuple[int, int]:
    """Return zero-based row and column coordinates for a valid cell ID."""

    validate_size(size)
    if not isinstance(cell_id, str):
        raise ValueError("cell ID must be a string")
    match = _CELL_PATTERN.fullmatch(cell_id)
    if match is None:
        raise ValueError(f"invalid cell ID {cell_id!r}")
    col = ord(match.group(1)) - ord("A")
    row = int(match.group(2)) - 1
    if not 0 <= row < size or not 0 <= col < size:
        raise ValueError(f"cell {cell_id!r} is outside a {size}x{size} board")
    return row, col


def resolve_region(region: Region, size: int) -> list[str]:
    """Resolve a validated region expression to row-major cell IDs."""

    validate_size(size)
    ordered = cell_ids(size)
    if not isinstance(region, Region):
        raise ValueError("region must be a Region instance")

    if region.type is RegionType.ROW:
        if region.index is None or not 1 <= region.index <= size:
            raise ValueError(f"ROW index must be between 1 and {size}")
        return [cell for cell in ordered if int(cell[1:]) == region.index]
    if region.type is RegionType.COL:
        if region.col is None or len(region.col) != 1 or not "A" <= region.col <= chr(64 + size):
            raise ValueError(f"COL col must be between A and {chr(64 + size)}")
        return [cell for cell in ordered if cell[0] == region.col]
    if region.type is RegionType.NEIGHBORS:
        if region.of_cell is None:
            raise ValueError("NEIGHBORS requires an 'of' cell")
        center_row, center_col = cell_coordinates(region.of_cell, size)
        result: list[str] = []
        for cell in ordered:
            row, col = cell_coordinates(cell, size)
            if (row, col) != (center_row, center_col) and max(
                abs(row - center_row), abs(col - center_col)
            ) == 1:
                result.append(cell)
        return result
    if region.type is RegionType.EXPLICIT:
        if len(set(region.cells)) != len(region.cells):
            raise ValueError("EXPLICIT cells must be distinct")
        selected = set(region.cells)
        for cell in region.cells:
            cell_coordinates(cell, size)
        return [cell for cell in ordered if cell in selected]
    if region.type is RegionType.BOUNDARY:
        return [
            cell
            for cell in ordered
            if (lambda position: position[0] in {0, size - 1} or position[1] in {0, size - 1})(
                cell_coordinates(cell, size)
            )
        ]
    if region.type is RegionType.INTERSECTION:
        if len(region.regions) < 2:
            raise ValueError("INTERSECTION requires at least two child regions")
        child_sets = [set(resolve_region(child, size)) for child in region.regions]
        intersection = set.intersection(*child_sets)
        return [cell for cell in ordered if cell in intersection]
    raise ValueError(f"unsupported region type {region.type!r}")


def validate_clue(clue: Clue, size: int) -> None:
    """Validate all parameters and cell references of a clue."""

    validate_size(size)
    if not isinstance(clue, Clue):
        raise ValueError("clue must be a Clue instance")
    if not clue.id:
        raise ValueError("clue ID must be non-empty")

    if clue.type is ClueType.FACT:
        if clue.cell is None:
            raise ValueError(f"{clue.id}: FACT requires a cell")
        cell_coordinates(clue.cell, size)
        if clue.status not in {Verdict.CRIMINAL, Verdict.INNOCENT}:
            raise ValueError(f"{clue.id}: FACT status must be CRIMINAL or INNOCENT")
        return
    if clue.type in {ClueType.SAME, ClueType.DIFFERENT}:
        if len(clue.cells) != 2:
            raise ValueError(f"{clue.id}: {clue.type.value} requires exactly two cells")
        if clue.cells[0] == clue.cells[1]:
            raise ValueError(f"{clue.id}: binary clue cells must be distinct")
        for cell in clue.cells:
            cell_coordinates(cell, size)
        return
    if clue.type in {ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST}:
        if clue.region is None:
            raise ValueError(f"{clue.id}: {clue.type.value} requires a region")
        region_cells = resolve_region(clue.region, size)
        if clue.k is None or isinstance(clue.k, bool) or not isinstance(clue.k, int):
            raise ValueError(f"{clue.id}: k must be an integer")
        if not 0 <= clue.k <= len(region_cells):
            raise ValueError(
                f"{clue.id}: k must be between 0 and region size {len(region_cells)}"
            )
        return
    if clue.type is ClueType.PARITY:
        if clue.region is None:
            raise ValueError(f"{clue.id}: PARITY requires a region")
        resolve_region(clue.region, size)
        if clue.parity not in {"EVEN", "ODD"}:
            raise ValueError(f"{clue.id}: parity must be EVEN or ODD")
        return
    if clue.type is ClueType.COMPARE:
        if clue.left is None or clue.right is None:
            raise ValueError(f"{clue.id}: COMPARE requires left and right regions")
        resolve_region(clue.left, size)
        resolve_region(clue.right, size)
        if clue.op not in _COMPARE_OPERATORS:
            raise ValueError(f"{clue.id}: comparison op must be one of {sorted(_COMPARE_OPERATORS)}")
        return
    raise ValueError(f"{clue.id}: unsupported clue type {clue.type!r}")


def _validate_assignment(assignment: Mapping[str, bool], size: int) -> None:
    expected = set(cell_ids(size))
    actual = set(assignment)
    if actual != expected:
        raise ValueError(
            f"assignment must contain every board cell exactly once; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    if any(type(value) is not bool for value in assignment.values()):
        raise ValueError("assignment values must be Boolean")


def evaluate_clue_directly(
    clue: Clue, assignment: Mapping[str, bool], size: int
) -> bool:
    """Evaluate clue semantics directly without using a CNF encoder."""

    validate_clue(clue, size)
    _validate_assignment(assignment, size)
    if clue.type is ClueType.FACT:
        assert clue.cell is not None and clue.status is not None
        return assignment[clue.cell] is (clue.status is Verdict.CRIMINAL)
    if clue.type is ClueType.SAME:
        return assignment[clue.cells[0]] is assignment[clue.cells[1]]
    if clue.type is ClueType.DIFFERENT:
        return assignment[clue.cells[0]] is not assignment[clue.cells[1]]
    if clue.type in {ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST}:
        assert clue.region is not None and clue.k is not None
        count = sum(assignment[cell] for cell in resolve_region(clue.region, size))
        if clue.type is ClueType.EXACTLY:
            return count == clue.k
        if clue.type is ClueType.AT_LEAST:
            return count >= clue.k
        return count <= clue.k
    if clue.type is ClueType.PARITY:
        assert clue.region is not None and clue.parity is not None
        count = sum(assignment[cell] for cell in resolve_region(clue.region, size))
        return (count % 2 == 0) is (clue.parity == "EVEN")

    assert clue.left is not None and clue.right is not None and clue.op is not None
    left_count = sum(assignment[cell] for cell in resolve_region(clue.left, size))
    right_count = sum(assignment[cell] for cell in resolve_region(clue.right, size))
    comparisons = {
        ">": left_count > right_count,
        ">=": left_count >= right_count,
        "=": left_count == right_count,
        "<=": left_count <= right_count,
        "<": left_count < right_count,
    }
    return comparisons[clue.op]


def _describe_region(region: Region) -> str:
    if region.type is RegionType.ROW:
        return f"row {region.index}"
    if region.type is RegionType.COL:
        return f"column {region.col}"
    if region.type is RegionType.NEIGHBORS:
        return f"the neighbors of {region.of_cell}"
    if region.type is RegionType.EXPLICIT:
        return "cells " + ", ".join(region.cells) if region.cells else "the empty region"
    if region.type is RegionType.BOUNDARY:
        return "the boundary"
    return "the intersection of " + "; ".join(
        _describe_region(child) for child in region.regions
    )


def describe_clue(clue: Clue) -> str:
    """Return concise natural-language text suitable for the GUI."""

    if clue.type is ClueType.FACT:
        status = clue.status.value.lower() if clue.status else "unknown"
        return f"{clue.cell} is {status}."
    if clue.type is ClueType.SAME:
        return f"{clue.cells[0]} and {clue.cells[1]} have the same status."
    if clue.type is ClueType.DIFFERENT:
        return f"{clue.cells[0]} and {clue.cells[1]} have different statuses."
    if clue.type is ClueType.EXACTLY:
        assert clue.region is not None
        return f"Exactly {clue.k} criminals are in {_describe_region(clue.region)}."
    if clue.type is ClueType.AT_LEAST:
        assert clue.region is not None
        return f"At least {clue.k} criminals are in {_describe_region(clue.region)}."
    if clue.type is ClueType.AT_MOST:
        assert clue.region is not None
        return f"At most {clue.k} criminals are in {_describe_region(clue.region)}."
    if clue.type is ClueType.PARITY:
        assert clue.region is not None
        return f"The criminal count in {_describe_region(clue.region)} is {clue.parity.lower()}."
    assert clue.left is not None and clue.right is not None
    return (
        f"The criminal count in {_describe_region(clue.left)} is {clue.op} "
        f"the count in {_describe_region(clue.right)}."
    )


def _region_anchor_cells(region: Region, size: int) -> set[str]:
    anchors: set[str] = set()
    if region.type is RegionType.NEIGHBORS and region.of_cell is not None:
        cell_coordinates(region.of_cell, size)
        anchors.add(region.of_cell)
    for child in region.regions:
        anchors.update(_region_anchor_cells(child, size))
    return anchors


def clue_cells(clue: Clue, size: int) -> set[str]:
    """Return every cell referenced directly or counted by a clue."""

    validate_clue(clue, size)
    if clue.type is ClueType.FACT:
        assert clue.cell is not None
        return {clue.cell}
    if clue.type in {ClueType.SAME, ClueType.DIFFERENT}:
        return set(clue.cells)
    if clue.type in {
        ClueType.EXACTLY,
        ClueType.AT_LEAST,
        ClueType.AT_MOST,
        ClueType.PARITY,
    }:
        assert clue.region is not None
        return set(resolve_region(clue.region, size)) | _region_anchor_cells(clue.region, size)
    assert clue.left is not None and clue.right is not None
    return (
        set(resolve_region(clue.left, size))
        | set(resolve_region(clue.right, size))
        | _region_anchor_cells(clue.left, size)
        | _region_anchor_cells(clue.right, size)
    )


if __name__ == "__main__":
    smoke_region = Region(type=RegionType.NEIGHBORS, of_cell="B2")
    assert resolve_region(smoke_region, 3) == [
        "A1",
        "B1",
        "C1",
        "A2",
        "C2",
        "A3",
        "B3",
        "C3",
    ]
