"""Deterministic CNF encoding of public Griductive knowledge."""

from __future__ import annotations

from dataclasses import dataclass

from core.models import Clue, ClueType, PublicState, Verdict
from core.regions import (
    cell_coordinates,
    cell_ids,
    resolve_region,
    validate_clue,
    validate_size,
)

Clause = list[int]


@dataclass(frozen=True)
class EncoderStatistics:
    """Variable and clause counts for an encoded knowledge base."""

    primary_vars: int
    aux_vars: int
    clauses: int


@dataclass(frozen=True)
class KnowledgeBase:
    """Immutable CNF and metadata returned by the encoder."""

    clauses: tuple[tuple[int, ...], ...]
    num_vars: int
    statistics: EncoderStatistics


class Encoder:
    """Encode clues with row-major primary variables and fresh auxiliaries.

    A positive primary literal means CRIMINAL. Reuse one encoder when combining
    clues so that their auxiliary variables cannot collide.
    """

    def __init__(self, size: int) -> None:
        validate_size(size)
        self.size = size
        self.num_vars = size * size

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
        """Encode fact, binary, comparison, parity, and counting clues as CNF."""

        validate_clue(clue, self.size)
        clauses: list[Clause] = []
        if clue.type is ClueType.FACT:
            # A fact fixes a cell's status with a unit clause.
            assert clue.cell is not None
            variable = self.var_of(clue.cell)
            if clue.status is Verdict.CRIMINAL:
                return [[variable]]
            else:
                return [[-variable]]
        elif clue.type in {ClueType.SAME, ClueType.DIFFERENT}:
            # SAME requires equal truth values; DIFFERENT requires opposite values.
            a, b = (self.var_of(cell) for cell in clue.cells)
            if clue.type is ClueType.SAME:
                return [[-a, b], [a, -b]]
            else:
                return [[a, b], [-a, -b]]

        elif clue.type is ClueType.COMPARE:
            assert clue.left is not None and clue.right is not None
            left = set(resolve_region(clue.left, self.size))
            right = set(resolve_region(clue.right, self.size))
            # Shared cells cancel. Negating right-only cells turns the
            # difference of two counts into one ordinary cardinality bound.
            literals = [self.var_of(c) for c in cell_ids(self.size) if c in left - right]
            literals += [-self.var_of(c) for c in cell_ids(self.size) if c in right - left]
            target = len(right - left)
            op = clue.op
        else:
            assert clue.region is not None
            literals = [self.var_of(c) for c in resolve_region(clue.region, self.size)]
            if clue.type is ClueType.PARITY:
                # XOR is true for an odd count and false for an even count.
                parity: int | bool = False
                for literal in literals:
                    parity = self._gate("xor", parity, literal, clauses)
                if clue.parity == "ODD":
                    self._add(clauses, [parity])
                else:
                    self._add(clauses, [self._neg(parity)])
                return clauses
            assert clue.k is not None
            target = clue.k
            op = {
                ClueType.EXACTLY: "=",
                ClueType.AT_LEAST: ">=",
                ClueType.AT_MOST: "<=",
            }[clue.type]

        # Build unary counts: thresholds[j] means at least j + 1 true literals.
        thresholds: list[int | bool] = []
        for literal in literals:
            current: list[int | bool] = []
            for j in range(len(thresholds) + 1):
                if j == 0:
                    lower = True
                else:
                    lower = thresholds[j - 1]
                if j < len(thresholds):
                    same = thresholds[j]
                else:
                    same = False
                added = self._gate("and", literal, lower, clauses)
                current.append(self._gate("or", same, added, clauses))
            thresholds = current

        def at_least(k: int) -> int | bool:
            if k <= 0:
                return True
            if k <= len(thresholds):
                return thresholds[k - 1]
            else:
                return False

        if op in {"=", ">=", ">"}:
            if op == ">":
                lower_bound = target + 1
            else:
                lower_bound = target
            self._add(clauses, [at_least(lower_bound)])
        if op in {"=", "<=", "<"}:
            if op == "<":
                excluded_count = target
            else:
                excluded_count = target + 1
            self._add(clauses, [self._neg(at_least(excluded_count))])
        return clauses

    @staticmethod
    def _neg(literal: int | bool) -> int | bool:
        if isinstance(literal, bool):
            return not literal
        else:
            return -literal

    @staticmethod
    def _add(clauses: list[Clause], literals: list[int | bool]) -> None:
        """Skip true clauses and remove false constants before appending."""

        if any(literal is True for literal in literals):
            return
        clauses.append(
            [literal for literal in literals if not isinstance(literal, bool)]
        )

    def _gate(
        self, op: str, a: int | bool, b: int | bool, clauses: list[Clause]
    ) -> int | bool:
        """Encode an equivalence, rather than just a one-way implication."""

        # Simplify gates with Boolean constants before allocating variables.
        if op == "and":
            if a is False or b is False:
                return False
            if a is True:
                return b
            if b is True:
                return a
        if op == "or":
            if a is True or b is True:
                return True
            if a is False:
                return b
            if b is False:
                return a
        if op == "xor":
            if isinstance(a, bool):
                if a:
                    return self._neg(b)
                else:
                    return b
            if isinstance(b, bool):
                if b:
                    return self._neg(a)
                else:
                    return a

        # Represent the gate's output with a fresh auxiliary variable.
        self.num_vars += 1
        output = self.num_vars
        for av in (False, True):
            for bv in (False, True):
                if op == "and":
                    value = av and bv
                elif op == "or":
                    value = av or bv
                else:
                    value = av != bv
                if av:
                    clause_a = self._neg(a)
                else:
                    clause_a = a
                if bv:
                    clause_b = self._neg(b)
                else:
                    clause_b = b
                if value:
                    clause_output = output
                else:
                    clause_output = -output
                self._add(clauses, [clause_a, clause_b, clause_output])
        return output

    def knowledge_base(self, clauses: list[Clause]) -> KnowledgeBase:
        """Freeze clauses together with this encoder's variable statistics."""

        primary = self.size * self.size
        return KnowledgeBase(
            tuple(tuple(clause) for clause in clauses),
            self.num_vars,
            EncoderStatistics(primary, self.num_vars - primary, len(clauses)),
        )


def build_kb(state: PublicState) -> KnowledgeBase:
    """Encode revealed statuses and clues; hidden information is unavailable."""

    encoder = Encoder(state.size)
    clauses: list[Clause] = []
    for cell in cell_ids(state.size):
        # Only revealed cells contribute public facts and clues.
        if cell not in state.revealed:
            continue
        status, clue = state.revealed[cell]

        variable = encoder.var_of(cell)
        if status is Verdict.CRIMINAL:
            clauses.append([variable])
        else:
            clauses.append([-variable])
        clauses.extend(encoder.encode_clue(clue))
    for cell in state.revealed:
        encoder.var_of(cell)
    return encoder.knowledge_base(clauses)


if __name__ == "__main__":
    smoke_encoder = Encoder(3)
    assert smoke_encoder.var_of("A1") == 1
    assert smoke_encoder.cell_of(9) == "C3"
