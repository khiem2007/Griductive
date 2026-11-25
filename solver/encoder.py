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
        """Return CNF for one validated clue, allocating fresh auxiliaries."""

        validate_clue(clue, self.size)
        clauses: list[Clause] = []
        if clue.type is ClueType.FACT: # Clue là Fact (unit clause) => gán trực tiếp cho giá trị biến
            assert clue.cell is not None
            variable = self.var_of(clue.cell)
            return [[variable if clue.status is Verdict.CRIMINAL else -variable]]
        if clue.type in {ClueType.SAME, ClueType.DIFFERENT}: # Clue là Same (a <=> b) => a và b cùng đúng hoặc cùng sai
            a, b = (self.var_of(cell) for cell in clue.cells) # Clue là Different (Cả hai không cùng đúng hoặc cùng sai)
            return (
                [[-a, b], [a, -b]] if clue.type is ClueType.SAME else [[a, b], [-a, -b]]
            )
        if clue.type is ClueType.COMPARE: 
            assert clue.left is not None and clue.right is not None
            left = set(resolve_region(clue.left, self.size))
            right = set(resolve_region(clue.right, self.size))
            # Shared cells cancel. Negating right-only cells turns the
            # difference of two counts into one ordinary cardinality bound.
            literals = [
                self.var_of(c) for c in cell_ids(self.size) if c in left - right
            ]
            literals += [
                -self.var_of(c) for c in cell_ids(self.size) if c in right - left
            ]
            target = len(right - left)
            op = clue.op
        else: # Clue là parity (XOR) => đúng khi số lượng True lẻ, sai khi số lượng True chẵn
            assert clue.region is not None
            literals = [self.var_of(c) for c in resolve_region(clue.region, self.size)]
            if clue.type is ClueType.PARITY:
                parity: int | bool = False
                for literal in literals:
                    parity = self._gate("xor", parity, literal, clauses)
                self._add(
                    clauses, [parity if clue.parity == "ODD" else self._neg(parity)]
                )
                return clauses
            assert clue.k is not None
            target = clue.k
            op = {
                ClueType.EXACTLY: "=",
                ClueType.AT_LEAST: ">=",
                ClueType.AT_MOST: "<=",
            }[clue.type]

        thresholds = self._thresholds(literals, clauses)

        def at_least(k: int) -> int | bool:
            if k <= 0:
                return True
            return thresholds[k - 1] if k <= len(thresholds) else False

        if op in {"=", ">=", ">"}:
            self._add(clauses, [at_least(target + (op == ">"))])
        if op in {"=", "<=", "<"}:
            self._add(clauses, [self._neg(at_least(target + (op != "<")))])
        return clauses

    @staticmethod
    def _neg(literal: int | bool) -> int | bool:
        return not literal if isinstance(literal, bool) else -literal

    @staticmethod
    def _add(clauses: list[Clause], literals: list[int | bool]) -> None:
        """Xử lý các clauses trước khi thêm vào danh sách clauses 
        """
        if any(literal is True for literal in literals): # Nếu clause chứa True => Toàn bộ clause luôn đúng nên không cần thêm vào CNF
            return 
        clauses.append(
            [literal for literal in literals if not isinstance(literal, bool)]
        ) # Nếu clause không chứa True => chỉ giữ lại các literal khác False
        

    def _gate(
        self, op: str, a: int | bool, b: int | bool, clauses: list[Clause]
    ) -> int | bool:
        """Encode an equivalence, rather than just a one-way implication."""
        
        # Rút gọn khi gặp boolean hằng (True và False)
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
                return self._neg(b) if a else b
            if isinstance(b, bool):
                return self._neg(a) if b else a
            
        # Biểu diễn kết quả bằng biến mới
        self.num_vars += 1
        output = self.num_vars
        for av in (False, True):
            for bv in (False, True):
                value = (
                    (av and bv)
                    if op == "and"
                    else (av or bv)
                    if op == "or"
                    else av != bv
                )
                self._add(
                    clauses,
                    [self._neg(a) if av else a, self._neg(b) if bv else b, output if value else -output],
                )
        return output

    def _thresholds(
        self, literals: list[int], clauses: list[Clause]
    ) -> list[int | bool]:
        """Build unary counts, entry j means count >= j + 1."""

        previous: list[int | bool] = []
        for literal in literals:
            current: list[int | bool] = []
            for j in range(len(previous) + 1):
                lower = True if j == 0 else previous[j - 1]
                same = previous[j] if j < len(previous) else False
                added = self._gate("and", literal, lower, clauses)
                current.append(self._gate("or", same, added, clauses))
            previous = current
        return previous

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
        if cell not in state.revealed:
            continue
        status, clue = state.revealed[cell]
        if status not in {Verdict.CRIMINAL, Verdict.INNOCENT}:
            raise ValueError("revealed status must be CRIMINAL or INNOCENT")
        variable = encoder.var_of(cell)
        clauses.append([variable if status is Verdict.CRIMINAL else -variable])
        clauses.extend(encoder.encode_clue(clue))
    for cell in state.revealed:
        encoder.var_of(cell)
    return encoder.knowledge_base(clauses)


if __name__ == "__main__":
    smoke_encoder = Encoder(3)
    assert smoke_encoder.var_of("A1") == 1
    assert smoke_encoder.cell_of(9) == "C3"
