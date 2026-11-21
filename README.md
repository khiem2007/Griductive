# Griductive Manual Practice

This repository currently provides a playable manual-practice version of Griductive for Python 3.10+. It loads user-authored JSON puzzles and checks answers against the stored solution.

> **Manual practice — answer check** permits a lucky correct guess. It does not yet satisfy the course requirement that every verdict must be logically entailed. CNF encoding, DPLL, and `LogicAgent` are intentionally left as typed interfaces for the student team.

## Install and launch

Run every command from the repository root:

```powershell
python -m pip install -r requirements.txt
python main.py
```

You can optionally load a puzzle immediately:

```powershell
python main.py puzzles/3x3_easy.json
```

Inside the GUI:

1. Select **Load** and choose a JSON file anywhere on disk. If the system file dialog is unavailable, enter the path in the in-app prompt.
2. Click a face-down card.
3. Choose **CRIMINAL** or **INNOCENT**.
4. A correct answer reveals only that card and its clue. A wrong answer leaves the board unchanged and allows another attempt.
5. Click a revealed card to highlight every cell referenced or counted by its clue.
6. Use **Restart** to restore the puzzle's initially revealed cards.

Hint and Auto Solve remain disabled until the team implements `LogicAgent`.

## Puzzle JSON contract

A puzzle has `size` equal to 3, 4, or 5 and exactly `size * size` cell records. Coordinates use columns `A`, `B`, ... and rows beginning at `1`.

```json
{
  "size": 3,
  "cells": [
    {
      "id": "A1",
      "name": "Abel",
      "job": "Astronaut",
      "status": "INNOCENT",
      "revealed": true,
      "clue": {
        "id": "clue_A1",
        "type": "FACT",
        "cell": "B1",
        "status": "CRIMINAL"
      }
    }
  ]
}
```

A complete 3x3 file contains nine records, a 4x4 file sixteen, and a 5x5 file twenty-five. Cell IDs and clue IDs must be unique. Every clue must be true under the supplied statuses.

Supported clues:

- `FACT`: `cell`, `status`
- `SAME`, `DIFFERENT`: `cells` containing exactly two distinct coordinates
- `EXACTLY`, `AT_LEAST`, `AT_MOST`: `region`, `k`
- `PARITY`: `region`, `parity` (`EVEN` or `ODD`)
- `COMPARE`: `left`, `right`, `op` (`>`, `>=`, `=`, `<=`, `<`)

Supported regions:

```json
{"type": "ROW", "index": 2}
{"type": "COL", "col": "B"}
{"type": "NEIGHBORS", "of": "B2"}
{"type": "EXPLICIT", "cells": ["A1", "C3"]}
{"type": "BOUNDARY"}
{"type": "INTERSECTION", "of": [{"type": "ROW", "index": 2}, {"type": "COL", "col": "B"}]}
```

The loader validates schema fields, coordinates, duplicate cells, region bounds, counting limits, and clue truth. It does not establish uniqueness or no-guess solvability.

## Student-owned automatic algorithms

The following importable interfaces deliberately raise `NotImplementedError`:

- `solver/dpll.py`: `solve(...) -> SolveResult`
- `solver/encoder.py`: `Encoder.encode_clue(...)` and `build_kb(...) -> KnowledgeBase`
- `solver/agent.py`: `LogicAgent` classification, judging, hints, deduction steps, run loop, and `check_uniqueness(...)`

When the proof-based agent is ready, inject it with `GameEngine(puzzle, referee=logic_agent)`. The GUI checks `engine.has_referee` and then routes claims through `submit_verdict`. Without a referee, it uses `submit_manual` only.

## Verification

```powershell
python -m unittest tests.test_manual_game tests.test_gui
python -m tests.verify_puzzles
python -m core.engine
python -m solver.dpll
python -m solver.encoder
python -m solver.agent
```

