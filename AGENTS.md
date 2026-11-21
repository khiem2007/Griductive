Prompt hoàn chỉnh: Griductive Solver
Sao chép phần bên dưới đường kẻ ngang, từ "ROLE & OBJECTIVE" đến hết dòng "Start with Step 1 only." Đoạn này chỉ là ghi chú cho bạn, đừng dán. Prompt dùng DPLL tự cài đặt (không dùng thư viện SAT), có schema JSON, Referee inject, timeout qua deadline, vòng suy diễn theo wave và tiêu chí độ khó cho puzzle.

ROLE & OBJECTIVE
You are a Senior Python Engineer with a SAT/logic background. Build Griductive Solver: a playable Griductive grid-deduction game with a GUI, plus a no-guess logic agent based on propositional logic, automatic CNF encoding and a self-implemented DPLL SAT solver. This is a university AI course project (CSC14003, Project 2). The code will be read and graded, so it must be correct, clearly structured and easy to explain.
Work iteratively (see WORKFLOW). Do NOT write the whole codebase at once.
GAME RULES (summary)
•	The board is N x N, N in {3, 4, 5}. Each cell holds one character who is secretly Criminal or Innocent.
•	Columns are letters A, B, C... left to right; rows are numbers 1, 2, 3... top to bottom. C2 = column C, row 2.
•	Each card has one structured clue. Every clue is true regardless of its owner's status (this is NOT a truth-teller/liar puzzle). Names and jobs carry no logical meaning.
•	Some cards start face-up. Face-up cards (status + clue) are the public knowledge. All other cards are face-down.
•	A verdict (CRIMINAL / INNOCENT) on a face-down card is accepted only if it is logically entailed by the current public knowledge. Otherwise it is rejected with NOT_PROVABLE (neither status is forced) or CONTRADICTED (the opposite status is forced). A rejected verdict changes nothing and does not reveal the hidden clue.
•	An accepted verdict flips the card and adds its status and clue to the public knowledge.
•	A valid puzzle has exactly ONE complete assignment satisfying all its clues.
HARD CONSTRAINTS (never violate)
1.	Python 3.10+. Main flow may use only the standard library, pygame and tkinter. Do NOT use python-sat, pysat, z3, pycosat or any SAT/SMT library in the main flow. The DPLL solver must be written from scratch. A SAT library may be used ONLY inside tests/ as an optional cross-check, guarded by try/except ImportError (skip the test if missing). Never list it in requirements.txt except as a commented optional line.
2.	Create ONLY the directory structure below, no other folders.
3.	Information isolation. core/engine.py is the ONLY place that holds the hidden solution and the clues of face-down cards. solver/ and gui/ receive only a PublicState and must never read the hidden solution or unrevealed clues.
4.	Dependency direction. core/ must NOT import solver/ or gui/. solver/ may import core.models and core.regions only, never core.engine. main.py wires engine, agent and GUI together.
5.	No hard-coded CNF per puzzle. Every clue is converted to CNF automatically by solver/encoder.py.
6.	Code quality: type hints everywhere, docstrings in English, dataclasses, no global mutable state, no print in library code (use return values or logging), and each module has a small if __name__ == "__main__": smoke test.
DIRECTORY STRUCTURE
Griductive/
├── main.py                 # entry point, wires engine + agent + GUI
├── run_experiments.py      # benchmark script (per-puzzle time budget), prints table + writes experiment_results.csv
├── generate_puzzles.py     # seeded puzzle generator (a tool, not a test)
├── requirements.txt        # pygame (python-sat only as a commented optional line)
├── README.md               # install and run instructions
├── REPORT_NOTES.md         # CNF derivations, algorithm notes, experiment tables for the report
├── puzzles/
│   ├── 3x3_easy.json
│   ├── 4x4_medium.json
│   └── 5x5_hard.json
├── core/
│   ├── __init__.py
│   ├── models.py           # enums, dataclasses, Referee/GameInterface protocols
│   ├── regions.py          # region resolution, direct semantic evaluator, clue-to-text
│   └── engine.py           # GameEngine: hidden state, move validation via injected Referee
├── solver/
│   ├── __init__.py
│   ├── encoder.py          # variable map + clue -> CNF compiler + statistics
│   ├── dpll.py             # self-implemented DPLL SAT solver
│   └── agent.py            # LogicAgent: classification, Hint, deduction loop, trace, uniqueness check
├── gui/
│   ├── __init__.py
│   └── app.py              # Pygame UI + tkinter file dialog
└── tests/
    ├── __init__.py
    ├── test_dpll.py        # DPLL vs brute force on random CNFs
    ├── test_encoder.py     # direct evaluator vs CNF, for every clue type
    └── verify_puzzles.py   # uniqueness + no-guess solvability check for every puzzle file
Run rule: every script and test is run from the project root (the Griductive/ folder) and uses package imports only (from core..., from solver...); never edit sys.path. Commands to use and to list in README.md: python main.py, python generate_puzzles.py --size 3 --seed 1 --out puzzles/3x3_easy.json, python run_experiments.py, python -m unittest tests.test_dpll tests.test_encoder, python -m tests.verify_puzzles.
LOGIC CONVENTIONS (strict)
•	Primary variables: one per cell, numbered in row-major order: A1 = 1, B1 = 2, ..., N-th column of row 1 = N, A2 = N+1, ... , last cell = N*N.
•	Literal sign: +i means cell i is CRIMINAL (True); -i means INNOCENT (False).
•	Auxiliary variables (counters, XOR chains) must have IDs greater than N*N and must stay separate from primary variables. They are allocated by the encoder with a counter that is reset for each knowledge-base build, so the mapping is deterministic.
•	A CNF is a list of clauses, each clause a list of non-zero ints (DIMACS-style).
•	Verdict values (plus TIMEOUT, see classify): CRIMINAL, INNOCENT, UNKNOWN, INCONSISTENT.
•	Move results (plus TIMEOUT: a solver time-out rejects the move and changes nothing): ACCEPTED, NOT_PROVABLE, CONTRADICTED, ALREADY_REVEALED, INCONSISTENT.
CLUE LANGUAGE
Six core clue types (required):
Type	Meaning	Logic
FACT	a cell has a given status	unit literal Ci or -Ci
SAME	two cells have the same status	Ci <-> Cj
DIFFERENT	two cells have different statuses	Ci xor Cj
EXACTLY	exactly k criminals in region	sum = k
AT_LEAST	at least k criminals in region	sum >= k
AT_MOST	at most k criminals in region	sum <= k
For counting clues, 0 <= k <= |region|. "NO criminals" is EXACTLY with k = 0.
Four core regions: ROW, COL, NEIGHBORS (the up to 8 touching cells, excluding the cell itself), EXPLICIT (list of distinct cells).
Extensions (at least two distinct ones are required; implement all of these):
1.	PARITY clue: the number of criminals in a region is EVEN or ODD.
2.	COMPARE clue: compare criminal counts of two regions with an operator in >, >=, =, <=, <.
3.	Region BOUNDARY: cells on the outer border of the grid.
4.	Region INTERSECTION: intersection of two or more regions (can nest).
JSON schema for puzzles (use exactly this)
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
        "type": "EXACTLY",
        "k": 2,
        "region": {"type": "NEIGHBORS", "of": "B2"}
      }
    }
  ]
}
Clue fields by type:
•	FACT: cell, status (CRIMINAL or INNOCENT)
•	SAME, DIFFERENT: cells: [cellA, cellB]
•	EXACTLY, AT_LEAST, AT_MOST: region, k
•	PARITY: region, parity (EVEN or ODD)
•	COMPARE: left (region), right (region), op
Region objects: {"type":"ROW","index":2}, {"type":"COL","col":"B"}, {"type":"NEIGHBORS","of":"B2"}, {"type":"EXPLICIT","cells":["A1","C3"]}, {"type":"BOUNDARY"}, {"type":"INTERSECTION","of":[region, region]}.
The loader must validate everything: unknown types, out-of-range k, cells outside the grid, duplicate cells, and every clue must be true under the stored solution (raise a clear error otherwise). Edge cases: an empty region (for example an INTERSECTION of disjoint regions) is allowed and always has 0 criminals, so only k = 0 is valid for counting clues on it and its PARITY is EVEN; in COMPARE the two regions may overlap, and each region's count is computed independently (a shared cell counts on both sides).
MODULE SPECIFICATIONS
core/models.py
•	Verdict, MoveResult, ClueType, RegionType enums.
•	Frozen dataclasses: Cell, Region, Clue.
•	PublicState: size, names and jobs for ALL cells (face-down too, because the GUI must draw them), revealed: dict[cell_id -> (status, Clue)]. Nothing else. No hidden status and no unrevealed clue.
•	Puzzle: full data including solution (used only by the engine).
•	Protocols: Referee with judge(state: PublicState, cell: str, claimed: Verdict) -> MoveResult, and GameInterface with get_public_state() and submit_verdict(cell, claimed) (so the agent can drive the game without importing the engine).
core/regions.py
•	resolve_region(region, size) -> list[str] returning cell ids in row-major order, with validation.
•	evaluate_clue_directly(clue, assignment: dict[str, bool], size) -> bool: the direct semantic evaluator for all six core types and both extensions. It must NOT call or import the CNF encoder.
•	describe_clue(clue) -> str: natural-language text for the GUI.
•	clue_cells(clue, size) -> set[str]: all cells referenced or counted by the clue (for GUI highlighting).
solver/dpll.py (from scratch)
def solve(clauses, num_vars, assumptions=(), deadline=None) -> SolveResult
SolveResult: satisfiable: bool, model: dict[int, bool] | None (complete for variables 1..num_vars; free variables default to False), a timed_out flag (true when the deadline expired; no verdict is given then), and statistics decisions, propagations, backtracks, runtime.
Required: unit propagation, conflict detection, deterministic variable selection (smallest-ID unassigned variable that still occurs in an unsatisfied clause; try True first), recursive branching with backtracking (restore state correctly on backtrack), assumptions as temporary unit literals, and an immediately UNSAT answer if assumptions contradict. Pure-literal elimination is optional. Performance: keep one assignment trail and undo it on backtrack (never copy the clause list at each branch), index clauses by literal (watched literals are optional), and check the deadline (a time.monotonic() timestamp, or None for no limit) regularly inside the search; when it expires, stop and return timed_out=True instead of continuing. Handle the empty clause and the empty formula. Raise sys.setrecursionlimit if needed.
solver/encoder.py
•	Encoder(size): deterministic cell-to-variable mapping (var_of(cell_id), cell_of(var)).
•	encode_clue(clue) -> list[Clause], allocating auxiliary variables from the counter when needed.
•	build_kb(state: PublicState) -> KnowledgeBase: CNF(revealed clues) AND unit clauses for revealed statuses. It reads ONLY the public state.
•	KnowledgeBase exposes clauses, num_vars and stats (primary_vars, aux_vars, clauses).
•	Encodings (derivations must be explainable in the report):
o	FACT, SAME (2 clauses), DIFFERENT (2 clauses).
o	Counting clues: direct combinatorial encoding when the region has at most 8 cells; for larger regions use a sequential counter / totalizer with auxiliary variables (full equivalence, so it can be reused by COMPARE).
o	PARITY: Tseitin XOR chain with auxiliary variables. Do NOT enumerate 2^(n-1) clauses.
o	COMPARE: build unary counters for both regions and add implication clauses between them.
•	Validate clue parameters before encoding.
core/engine.py
GameEngine(puzzle, referee):
•	Holds the hidden solution and all clues; starts with the cards marked revealed.
•	get_public_state() -> PublicState.
•	submit_verdict(cell, claimed) -> MoveResult: if already revealed return ALREADY_REVEALED; otherwise call referee.judge(public_state, cell, claimed). On ACCEPTED, reveal the card (its true status and clue become public). Never use the hidden solution to decide a verdict. The solution may only be used afterwards to assert that an accepted verdict matches it (sanity check).
•	restart(), is_solved(), load(puzzle).
solver/agent.py
LogicAgent implements Referee and works only from PublicState:
•	classify(state, cell) -> Verdict: first check the KB itself (INCONSISTENT if UNSAT). Then KB AND NOT Ci UNSAT -> CRIMINAL; KB AND Ci UNSAT -> INNOCENT; both SAT -> UNKNOWN. If the KB itself is INCONSISTENT (only possible for a corrupted or hand-edited puzzle, because the public knowledge of a valid puzzle is always satisfiable), just return that verdict and stop, with no extra recovery logic. If any solve() call returns timed_out, return TIMEOUT: a timeout is NEVER treated as UNSAT, so it can never produce a forced verdict. Use DPLL assumptions.
•	judge(...): classify, then UNKNOWN -> NOT_PROVABLE, forced equals claimed -> ACCEPTED, forced is the opposite -> CONTRADICTED, KB unsat -> INCONSISTENT, TIMEOUT -> TIMEOUT (move rejected, nothing changes).
•	classify_all(state) and next_forced(state): the first forced unsolved cell in row-major order (deterministic). Used by Hint and manual play only; the deduction loop works wave by wave (see run/step).
•	hint(state): one currently forced cell, plus a revealed clue relevant to it (the most recently revealed clue whose clue_cells include that cell; if no revealed clue references it, return the cell alone). Must NOT read the hidden solution.
•	run(game: GameInterface) and step(game: GameInterface) -> TraceStep | None: the deduction loop, organised in waves (the only loop the agent uses; run() is just step() called repeatedly). A wave classifies every unresolved cell under the current KB (one consistency check, then 2 SAT queries per cell) and queues all forced verdicts in row-major order. step() submits ONE queued verdict through game.submit_verdict and returns its TraceStep; when the queue is empty it starts a new wave on the enlarged KB (incrementing waves), and it returns None when finished. Stop when solved, stuck (no forced cell, status STUCK), timed out (status TIMEOUT: the agent accepts an optional time budget and passes it as deadline to every solve() call) or inconsistent. A verdict queued earlier in a wave stays valid after later reveals because knowledge only grows. Never guess.
•	Deduction trace: list of TraceStep with step, active_clue_ids, sat_queries (each query's literal and SAT/UNSAT result), cell, verdict, new_clue_id.
•	Aggregated statistics: sat_calls, decisions, propagations, backtracks, runtime, steps, waves, plus encoder stats. A "wave" = one round where the agent classifies all unresolved cells under the current KB and submits all forced ones in row-major order before re-evaluating.
•	Separate module-level function check_uniqueness(size, clues) -> UniquenessResult that takes the COMPLETE clue set (all cards), finds a model with DPLL, adds a blocking clause on the primary variables and re-solves; reports UNIQUE, MULTIPLE (with two solutions) or NO_SOLUTION. A timed-out solve yields TIMEOUT, never UNIQUE or NO_SOLUTION. It is NOT part of the agent's deduction flow and is never called from main.py, the GUI or the engine (they must not see hidden clues): it is called only from tests/verify_puzzles.py and generate_puzzles.py, which load puzzle files directly.
gui/app.py (Pygame)
•	Draw the NxN grid with column letters and row numbers, each character's name and job, face-down cards, and face-up cards showing status (distinct colors/labels) and their clue text (describe_clue).
•	The player selects a card, then clicks CRIMINAL or INNOCENT. Show the result message: accepted (card flips and reveals the clue), NOT_PROVABLE, or CONTRADICTED. Rejected moves must NOT reveal the hidden clue.
•	Clicking a revealed clue highlights every cell referenced or counted by it (clue_cells).
•	Buttons: Load (open tkinter.filedialog in a separate subprocess or guarded call so it does not conflict with Pygame on macOS; fall back to a built-in list of files in puzzles/ if tkinter is unavailable), Restart, Hint (highlight a forced cell and the relevant clue), Auto Solve (step through the agent's deduction with a short delay, with a side panel for the deduction trace and stats).
•	The GUI uses only PublicState, GameEngine.submit_verdict, LogicAgent.step (Auto Solve: one verdict per timer tick, with the trace and stats shown in a side panel) and LogicAgent.hint/next_forced. DPLL runs on the main thread; a short freeze on 5x5 is acceptable.
main.py, run_experiments.py and generate_puzzles.py
•	main.py: wire LogicAgent, GameEngine, GUI; optional CLI argument for the initial puzzle path.
•	run_experiments.py: for every puzzle in puzzles/, run the agent to completion (with a per-puzzle time budget, default 60 s, enforced through the solver's deadline parameter, so no multiprocessing is needed; a puzzle that runs out of time is reported as TIMEOUT) and record: primary vars, auxiliary vars, clauses, SAT calls, decisions, propagations, backtracks, steps/waves, runtime, and final status. Include failures and timeouts in the output, do not drop them. Print an aligned table and write experiment_results.csv.
generate_puzzles.py (project root; a tool, not a test): python generate_puzzles.py --size N --seed S --out puzzles/NxN_name.json. Seeded generator: random solution, random true clues over all clue types; keep a clue set only if the solution is unique and the agent solves it with no guessing from the initial face-up cards. Step 1 ships a brute-force-only mode for 3x3 (no DPLL yet: uniqueness and solvability by enumeration with evaluate_clue_directly); Step 6 switches it to check_uniqueness and the agent so it also produces 4x4_medium.json and 5x5_hard.json. Never hand-write any puzzle file. Difficulty targets, which the generator must check and not just name the files after: 3x3_easy = at least 2 face-up cards, solved in at most 2 waves, core clue types only; 4x4_medium = at most 3 face-up cards, at least 2 waves, at least one extension clue (PARITY, COMPARE, BOUNDARY or INTERSECTION); 5x5_hard = at most 3 face-up cards, at least 3 waves, at least one PARITY or COMPARE clue, at least one BOUNDARY or INTERSECTION region, and at least one clue over a region of 8 or more cells (so the counter encoding is exercised). If a target cannot be met within a reasonable number of seeds, report the closest puzzle and tell me; never relax a target silently.
tests/
•	test_dpll.py: all tests use the standard unittest module. Random small CNFs: compare SAT/UNSAT against brute force; test assumptions, empty clause and empty formula; optional python-sat cross-check (skip if missing).
•	test_encoder.py: for every clue type and every region type, on N = 3 (exhaustively, all 512 assignments) and on N = 4 (500 random assignments with a fixed seed, to keep the runtime short), check each complete assignment of the primary variables; assert evaluate_clue_directly(clue, a) equals "CNF with a as unit assumptions is SAT" (using our DPLL so auxiliary variables are handled). Also test the variable mapping, that auxiliary IDs are greater than N*N, and that clause stats are reported.
•	verify_puzzles.py: for every puzzle file: validate the schema, check all clues are true under the stored solution, check uniqueness with check_uniqueness (and the brute-force simulation described in Step 1 for 3x3), and, once the agent exists (added in Step 4), check that the no-guess agent solves it completely.
WORKFLOW (strict)
Complete ONE step at a time. After each step: list the files created, give the exact commands to run the tests or smoke tests, state any assumption you made, then STOP and wait for my confirmation before the next step. At the start of every step, restate the HARD CONSTRAINTS in one line and keep following them.
•	Step 1: core/models.py, core/regions.py, puzzles/3x3_easy.json, tests/verify_puzzles.py (3x3 brute-force part only). Also write generate_puzzles.py (project root) in its brute-force-only 3x3 mode and use it to create the puzzle; never write it by hand. The brute-force check uses no SAT and relies on evaluate_clue_directly: enumerate all 2^9 assignments and verify (a) exactly one satisfies all clues; (b) a no-guess simulation: start from the initial face-up cards, repeatedly find the cells whose status is identical in every assignment that satisfies the currently public clues and statuses, reveal them (adding their clues), and continue until every cell is revealed (solvable) or no cell is forced (fail).
•	Step 2: solver/dpll.py and tests/test_dpll.py.
•	Step 3: solver/encoder.py and tests/test_encoder.py.
•	Step 4: core/engine.py and solver/agent.py (including check_uniqueness, trace and statistics). Provide a command-line smoke test that auto-solves 3x3_easy.json without any GUI, and extend tests/verify_puzzles.py with the agent-based check.
•	Step 5: gui/app.py and main.py.
•	Step 6: generate_puzzles.py, puzzles/4x4_medium.json, puzzles/5x5_hard.json, run_experiments.py, requirements.txt, README.md.
Step 7: REPORT_NOTES.md (project root): full CNF derivations for one binary clue (SAME or DIFFERENT) and one counting clue (for example EXACTLY 2 over 3 cells, written out clause by clause), the Tseitin encoding of PARITY, pseudocode of DPLL, entailment classification, the uniqueness check and the deduction loop, and tables of the experiment results copied from experiment_results.csv (including failures and timeouts). Use only facts from the real code and real run outputs; never invent numbers. Do NOT start Step 7 until I paste the contents of experiment_results.csv; ask me for it first.
OUTPUT RULES
•	Write complete, runnable files (no placeholders such as ... or TODO).
•	Keep explanations short; put the effort into correct code.
•	If something in this spec is ambiguous or contradictory, ask me ONE concise question before coding; otherwise make the most reasonable choice and state it.
Start with Step 1 only.
