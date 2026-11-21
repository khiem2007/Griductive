"""Seeded brute-force puzzle generator for the Step 1 3x3 puzzle."""

from __future__ import annotations

import argparse
import itertools
import random
from pathlib import Path
from typing import Sequence

from core.models import Cell, Clue, ClueType, Puzzle, Region, RegionType, Verdict, load_puzzle, save_puzzle
from core.regions import cell_ids, evaluate_clue_directly, resolve_region


_NAMES = ("Abel", "Bianca", "Cyrus", "Daphne", "Elias", "Farah", "Gideon", "Hazel", "Iris")
_JOBS = ("Astronaut", "Baker", "Chemist", "Dentist", "Engineer", "Florist", "Geologist", "Historian", "Illustrator")
_CORE_CLUE_TYPES = (
    ClueType.FACT,
    ClueType.SAME,
    ClueType.DIFFERENT,
    ClueType.EXACTLY,
    ClueType.AT_LEAST,
    ClueType.AT_MOST,
)


def _all_assignments(size: int) -> list[dict[str, bool]]:
    ids = cell_ids(size)
    return [dict(zip(ids, values, strict=True)) for values in itertools.product((False, True), repeat=len(ids))]


def _satisfying_assignments(size: int, clues: Sequence[Clue]) -> list[dict[str, bool]]:
    return [
        assignment
        for assignment in _all_assignments(size)
        if all(evaluate_clue_directly(clue, assignment, size) for clue in clues)
    ]


def _simulate_no_guess(puzzle: Puzzle) -> tuple[bool, int]:
    revealed = {cell.id for cell in puzzle.cells if cell.revealed}
    active_clues = [cell.clue for cell in puzzle.cells if cell.revealed]
    known = {
        cell.id: cell.status is Verdict.CRIMINAL
        for cell in puzzle.cells
        if cell.revealed
    }
    waves = 0
    while len(revealed) < puzzle.size * puzzle.size:
        models = [
            assignment
            for assignment in _all_assignments(puzzle.size)
            if all(assignment[cell] == status for cell, status in known.items())
            and all(
                evaluate_clue_directly(clue, assignment, puzzle.size)
                for clue in active_clues
            )
        ]
        if not models:
            return False, waves
        forced = [
            cell_id
            for cell_id in cell_ids(puzzle.size)
            if cell_id not in revealed
            and len({model[cell_id] for model in models}) == 1
        ]
        if not forced:
            return False, waves
        waves += 1
        by_id = {cell.id: cell for cell in puzzle.cells}
        for cell_id in forced:
            cell = by_id[cell_id]
            revealed.add(cell_id)
            known[cell_id] = cell.status is Verdict.CRIMINAL
            active_clues.append(cell.clue)
    return True, waves


def _random_region(size: int, rng: random.Random) -> Region:
    ids = cell_ids(size)
    region_type = rng.choice(
        (RegionType.ROW, RegionType.COL, RegionType.NEIGHBORS, RegionType.EXPLICIT)
    )
    if region_type is RegionType.ROW:
        return Region(type=region_type, index=rng.randint(1, size))
    if region_type is RegionType.COL:
        return Region(type=region_type, col=chr(65 + rng.randrange(size)))
    if region_type is RegionType.NEIGHBORS:
        return Region(type=region_type, of_cell=rng.choice(ids))
    count = rng.randint(1, len(ids))
    return Region(type=region_type, cells=tuple(rng.sample(ids, count)))


def _true_clue(
    clue_type: ClueType,
    clue_id: str,
    assignment: dict[str, bool],
    size: int,
    rng: random.Random,
) -> Clue:
    ids = cell_ids(size)
    if clue_type is ClueType.FACT:
        target = rng.choice(ids)
        status = Verdict.CRIMINAL if assignment[target] else Verdict.INNOCENT
        return Clue(id=clue_id, type=clue_type, cell=target, status=status)
    if clue_type is ClueType.SAME:
        pairs = [pair for pair in itertools.combinations(ids, 2) if assignment[pair[0]] == assignment[pair[1]]]
        return Clue(id=clue_id, type=clue_type, cells=rng.choice(pairs))
    if clue_type is ClueType.DIFFERENT:
        pairs = [pair for pair in itertools.combinations(ids, 2) if assignment[pair[0]] != assignment[pair[1]]]
        return Clue(id=clue_id, type=clue_type, cells=rng.choice(pairs))

    region = _random_region(size, rng)
    region_cells = resolve_region(region, size)
    criminals = sum(assignment[cell] for cell in region_cells)
    if clue_type is ClueType.EXACTLY:
        k = criminals
    elif clue_type is ClueType.AT_LEAST:
        k = rng.randint(0, criminals)
    else:
        k = rng.randint(criminals, len(region_cells))
    return Clue(id=clue_id, type=clue_type, region=region, k=k)


def _build_candidate(size: int, seed: int, attempt: int) -> Puzzle:
    rng = random.Random((seed << 16) + attempt)
    ids = cell_ids(size)
    while True:
        assignment = {cell: bool(rng.getrandbits(1)) for cell in ids}
        if 0 < sum(assignment.values()) < len(ids):
            break

    initial_indices = sorted(rng.sample(range(len(ids)), 2))
    initial_ids = [ids[index] for index in initial_indices]
    criminals = tuple(cell for cell in ids if assignment[cell])
    innocents = tuple(cell for cell in ids if not assignment[cell])
    partition_clues = [
        Clue(
            id=f"clue_{initial_ids[0]}",
            type=ClueType.EXACTLY,
            region=Region(type=RegionType.EXPLICIT, cells=criminals),
            k=len(criminals),
        ),
        Clue(
            id=f"clue_{initial_ids[1]}",
            type=ClueType.EXACTLY,
            region=Region(type=RegionType.EXPLICIT, cells=innocents),
            k=0,
        ),
    ]
    clue_by_cell = dict(zip(initial_ids, partition_clues, strict=True))

    hidden_ids = [cell for cell in ids if cell not in set(initial_ids)]
    hidden_types = [
        ClueType.FACT,
        ClueType.SAME,
        ClueType.DIFFERENT,
        ClueType.AT_LEAST,
        ClueType.AT_MOST,
        rng.choice(_CORE_CLUE_TYPES),
        rng.choice(_CORE_CLUE_TYPES),
    ]
    rng.shuffle(hidden_types)
    for owner, clue_type in zip(hidden_ids, hidden_types, strict=True):
        clue_by_cell[owner] = _true_clue(
            clue_type, f"clue_{owner}", assignment, size, rng
        )

    jobs = list(_JOBS)
    rng.shuffle(jobs)
    cells = tuple(
        Cell(
            id=cell_id,
            name=_NAMES[index],
            job=jobs[index],
            status=Verdict.CRIMINAL if assignment[cell_id] else Verdict.INNOCENT,
            revealed=cell_id in set(initial_ids),
            clue=clue_by_cell[cell_id],
        )
        for index, cell_id in enumerate(ids)
    )
    return Puzzle(size=size, cells=cells)


def generate_easy_3x3(seed: int, max_attempts: int = 100) -> Puzzle:
    """Generate a unique, core-only 3x3 puzzle solvable in at most two waves."""

    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    for attempt in range(max_attempts):
        puzzle = _build_candidate(3, seed, attempt)
        clue_types = {cell.clue.type for cell in puzzle.cells}
        full_models = _satisfying_assignments(3, [cell.clue for cell in puzzle.cells])
        solved, waves = _simulate_no_guess(puzzle)
        if (
            len(full_models) == 1
            and full_models[0] == puzzle.solution
            and solved
            and waves <= 2
            and sum(cell.revealed for cell in puzzle.cells) >= 2
            and clue_types == set(_CORE_CLUE_TYPES)
        ):
            return puzzle
    raise RuntimeError(
        f"no 3x3 easy puzzle met every target after {max_attempts} attempts for seed {seed}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, required=True, help="board size; Step 1 supports only 3")
    parser.add_argument("--seed", type=int, required=True, help="deterministic random seed")
    parser.add_argument("--out", type=Path, required=True, help="output JSON path")
    parser.add_argument("--max-attempts", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    """Generate, validate, and save the requested Step 1 puzzle."""

    args = _parse_args()
    if args.size != 3:
        raise SystemExit("Step 1 generator supports only --size 3")
    puzzle = generate_easy_3x3(args.seed, args.max_attempts)
    save_puzzle(puzzle, args.out)
    round_trip = load_puzzle(args.out)
    solved, waves = _simulate_no_guess(round_trip)
    print(
        f"generated {args.out} with seed={args.seed}, "
        f"revealed={sum(cell.revealed for cell in round_trip.cells)}, "
        f"waves={waves}, no_guess_solved={solved}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
