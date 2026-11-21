ROLE AND SCOPE
Continue the existing Python 3.10+ CSC14003 project after completed Step 1. Inspect its interfaces first. Reuse core/models.py, core/regions.py, the clue evaluator and existing tests. Deliver the manual practice game in this prompt and stop. The student owns the automatic algorithms.
All playable puzzles are authored and selected by the user. Remove puzzle generation from the workflow, launch path, documentation and dependencies. Leave any legacy Step 1 generator unused. Never generate or overwrite puzzle files. An empty puzzle directory is a supported starting state. Preserve all existing hand-written and Step 1 puzzle files. Keep the existing 3×3 verifier available as a separate, optional developer command.
Launch and load

Implement the Pygame entry point and level selector using the existing
main.py, core/engine.py and gui/app.py.

Running `python main.py` opens the “Chọn màn chơi” screen. Every JSON file
directly inside the project's `puzzles/` directory represents one level.
Locate this directory relative to main.py so discovery also works when
the game is launched from another working directory.

Each time the selector opens, automatically discover all `.json` files,
sort them by filename, and display their filename stems as level names.
Use pagination or a scrollable list if needed. If `puzzles/man_01.json` and
`puzzles/man_02.json` exist, the player must see `man_01` and `man_02`
immediately on startup. Clicking a level selects its name; pressing “Chơi”
loads and starts that level. GUI catalog callbacks receive names only.

Discover filenames first without reading JSON contents. On “Chơi”, use the existing
Step 1 loader and validation to load that puzzle. Keep the current JSON
schema and support 3×3, 4×4 and 5×5 boards. If the selected file is invalid
or has been removed, show a readable error, keep the selector usable,
and let the player choose another level. Preserve any current game until
the new level loads successfully.

Provide a “Chọn màn” action during play and after completion. Returning to
the selector refreshes the list so newly added puzzle files appear.
Restart resets only the current level.

If `puzzles/` is missing or contains no JSON files, show an empty level
list and the message “Thêm file JSON vào thư mục puzzles/ hoặc chọn Mở file JSON”.
Keep “Mở file JSON” available for external files via a tkinter picker in a child
process, with path entry if the picker is unavailable. Cancellation preserves
the current game. Preserve the optional command-line JSON path for direct
launch into a valid puzzle; on error, show the selector and failed filename.
Manual practice rules
Display coordinates, names and jobs. Start with exactly the cards marked revealed. Show each face-up status and clue. Clicking a revealed clue highlights all cells it refers to. Keep longer clue text readable on every board size. Wrap clue text and show the full selected clue in a readable detail area on a 5×5 board.
The player chooses a face-down card and submits CRIMINAL or INNOCENT. In manual practice, the engine compares that choice with the stored status. A match flips just that card and reveals its clue. A mismatch gives feedback and leaves the board intact. Allow another attempt after a wrong answer. Reject submissions on an already revealed card. Restart restores the loaded board’s initial state. Announce completion when all cards are face-up.
Label the mode “Manual practice — answer check”. A lucky correct guess can pass this mode. Reserve the course’s proof-based ACCEPTED, NOT_PROVABLE and CONTRADICTED outcomes for a future referee that checks entailment from public knowledge. Keep Hint and Auto Solve disabled with an explanation. Show CORRECT, WRONG or ALREADY_REVEALED for manual feedback. Keep manual feedback distinct from proof results and preserve the Step 1 GameInterface and MoveResult contracts. A wrong answer indirectly identifies the other status. This practice mode alone does not satisfy the graded no-guess rule. 
Puzzle file contract
Keep the Step 1 schema. Each file holds size and a cells array with exactly one record per coordinate. Rows start at 1 and columns start at A. The following is one cell record inside cells. A complete 3×3 file contains nine records.
{"id":"A1","name":"Abel","job":"Astronaut","status":"INNOCENT","revealed":true,"clue":{"id":"clue_A1","type":"FACT","cell":"B1","status":"CRIMINAL"}}
FACT: cell, status (CRIMINAL or INNOCENT)
SAME, DIFFERENT: cells: [cellA, cellB]
EXACTLY, AT_LEAST, AT_MOST: region, k
PARITY: region, parity (EVEN or ODD)
COMPARE: left (region), right (region), op
Region objects: {"type":"ROW","index":2}, {"type":"COL","col":"B"}, {"type":"NEIGHBORS","of":"B2"}, {"type":"EXPLICIT","cells":["A1","C3"]}, {"type":"BOUNDARY"}, {"type":"INTERSECTION","of":[region, region]}.
Counting clues count criminals. NEIGHBORS includes diagonal neighbors and excludes the center. For each board, validate size, coordinates, unique IDs, field types, status values, region bounds and counting limits. Use the existing direct evaluator to check each clue against the single supplied assignment. This validation does not establish uniqueness or no-guess solvability. Do not enumerate assignments.
Integration boundary
GameEngine owns the puzzle, hidden statuses and unrevealed clues. PublicState exposes only board size, names, jobs, and revealed statuses and clues. Wire GameEngine(puzzle, referee=None) in main.py. Expose a read-only GameEngine.has_referee property derived from the injected referee. Route each GUI submission through submit_verdict when this property is true and submit_manual otherwise. Read the property before dispatch. Practice submissions return ManualResult. Define ManualResult in core/models.py with CORRECT, WRONG and ALREADY_REVEALED. Only this method may consult the answer key to judge a move. With a referee installed, disable this method at the engine boundary. Preserve GameInterface.submit_verdict(cell, claimed) → MoveResult for proof-based play. After validating the mode, submit_verdict returns MoveResult.ALREADY_REVEALED immediately for a face-up cell, without calling the referee. For a face-down cell it calls judge(public_state, cell, claimed). In this proof-based path only ACCEPTED reveals a card. For either method, a wrong-mode call raises RuntimeError before reading hidden data or changing state. A rejection, timeout or referee error leaves the board intact.
Reserve solver/dpll.py, solver/encoder.py and solver/agent.py for the student. If missing, create importable signature-only skeletons for solve, build_kb, classify, judge, hint, step, run and check_uniqueness, with typed inputs, outputs and NotImplementedError. The manual launch and gameplay must work without importing solver. Do not implement a temporary brute-force referee, SAT search, encoding, auto-play, puzzle generation or benchmarks. Keep core independent of gui and solver. Future solver code may import core.models and core.regions only. Use typed package imports, no sys.path edits and no mutable global session state. Add type hints and English docstrings to public interfaces. Return results or use logging in library modules. Reuse existing project directories and place focused tests under tests/.
 
Interfaces reserved for the student
Preserve any established Step 1 types and protocol signatures. Reserve solve(clauses, num_vars, assumptions=(), deadline=None) → SolveResult in dpll.py. In encoder.py reserve Encoder(size), var_of(cell_id), cell_of(var), encode_clue(clue) and build_kb(state) → KnowledgeBase. In agent.py reserve LogicAgent.classify(state, cell), judge(state, cell, claimed), hint(state), next_forced(state), classify_all(state), step(game), run(game) and module-level check_uniqueness(size, clues). Keep algorithm bodies empty. Reserve SAT results, timeouts and statistics for the future implementation. Reuse existing result types first. For missing types define typed dataclasses in their owning modules: SolveResult in dpll.py (SAT status, model, timeout and statistics), KnowledgeBase in encoder.py (clauses, variable count and encoding statistics), TraceStep and UniquenessResult in agent.py (deduction record and uniqueness outcome respectively). Keep these records importable on their own. Algorithm methods raise NotImplementedError until the student fills them in.
Verification and handoff
Run from the project root. Check the empty start screen and loading a user-authored file. Verify one matching and one mismatching move, repeated selection, clue highlighting, full-board completion, Restart and loading a second file. Test cancellation and invalid JSON midway through a game. Confirm that manual play does not load solver modules or write to the puzzle file. Exercise engine actions independently of Pygame events. In a fresh Python process verify that neither solver nor solver.* appears in sys.modules after a manual move. If there is no display, drive GUI smoke tests with SDL_VIDEODRIVER=dummy and synthetic events. Distinguish headless checks from visual inspection. Use a referee test double to verify that a rejected claim matching the hidden answer leaves the card face-down. Test both wrong-mode calls and verify that neither reveals a card. Import each skeleton in a separate smoke test to catch missing result types. With a counting referee test double, submit a claim on a face-up cell and assert MoveResult.ALREADY_REVEALED, zero judge calls and unchanged public state. Check GUI dispatch in each mode.
Use existing Step 1 test data or small hand-written in-memory fixtures for tests. If no complete user puzzle is present, still deliver the working loader and GUI. Report exactly which GUI actions were verified with a real file and which were covered by fixtures.
Update requirements.txt and README.md with installation, python main.py, loading a JSON file, its schema, and how to write a complete board. Document which functions the student will fill and where to inject the future referee. Distinguish manual answer checking from the final course requirement of proving each verdict.
Finish by listing changed files, exact launch and test commands, and actual results. Stop after delivering the manual game and empty algorithm interfaces.
