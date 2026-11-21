"""Pygame interface for user-authored Griductive puzzle practice."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pygame

from core.models import ManualResult, MoveResult, PublicState, Verdict
from core.regions import cell_ids, clue_cells, describe_clue


Color = tuple[int, int, int]
LoadCallback = Callable[[str], None]

_BACKGROUND: Color = (20, 25, 38)
_PANEL: Color = (31, 39, 58)
_FACE_DOWN: Color = (58, 76, 113)
_CRIMINAL: Color = (145, 55, 62)
_INNOCENT: Color = (47, 120, 91)
_TEXT: Color = (239, 242, 248)
_MUTED: Color = (170, 181, 202)
_ACCENT: Color = (84, 156, 255)
_HIGHLIGHT: Color = (250, 199, 72)
_BUTTON: Color = (66, 82, 116)
_BUTTON_DISABLED: Color = (52, 57, 70)
_SUCCESS: Color = (104, 211, 145)
_ERROR: Color = (255, 126, 126)


class PracticeGame(Protocol):
    """Game operations used by the GUI without exposing private puzzle data."""

    @property
    def has_referee(self) -> bool:
        """Return whether proof-based checking is installed."""

    def get_public_state(self) -> PublicState:
        """Return current public knowledge."""

    def submit_manual(self, cell: str, claimed: Verdict) -> ManualResult:
        """Check an answer in manual practice mode."""

    def submit_verdict(self, cell: str, claimed: Verdict) -> MoveResult:
        """Submit a proof-based verdict when a referee exists."""

    def restart(self) -> None:
        """Restore initially revealed cards."""

    def is_solved(self) -> bool:
        """Return whether every card is revealed."""


class GriductiveApp:
    """Draw the board and dispatch manual or future proof-based submissions."""

    def __init__(
        self,
        game: PracticeGame,
        load_puzzle: LoadCallback,
        initial_message: str = "Load a puzzle JSON file to begin.",
        window_size: tuple[int, int] = (1280, 820),
    ) -> None:
        pygame.init()
        pygame.display.set_caption("Griductive — Manual practice — answer check")
        self._screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
        self._clock = pygame.time.Clock()
        self._game = game
        self._load_puzzle = load_puzzle
        self._running = False
        self._selected_cell: str | None = None
        self._active_clue_cell: str | None = None
        self._highlighted_cells: set[str] = set()
        self._message = initial_message
        self._message_color = _MUTED
        self._card_rects: dict[str, pygame.Rect] = {}
        self._buttons: dict[str, pygame.Rect] = {}
        self._path_entry_active = False
        self._path_text = ""
        self._title_font = pygame.font.SysFont("arial", 28, bold=True)
        self._heading_font = pygame.font.SysFont("arial", 20, bold=True)
        self._body_font = pygame.font.SysFont("arial", 17)
        self._small_font = pygame.font.SysFont("arial", 14)
        self._tiny_font = pygame.font.SysFont("arial", 12)

    @property
    def selected_cell(self) -> str | None:
        """Return the currently selected face-down cell."""

        return self._selected_cell

    @property
    def highlighted_cells(self) -> frozenset[str]:
        """Return cells highlighted by the active revealed clue."""

        return frozenset(self._highlighted_cells)

    @property
    def message(self) -> str:
        """Return the latest user-facing feedback message."""

        return self._message

    def run(self, max_frames: int | None = None) -> None:
        """Run the event loop; max_frames is available for headless smoke tests."""

        self._running = True
        frames = 0
        while self._running and (max_frames is None or frames < max_frames):
            for event in pygame.event.get():
                self.handle_event(event)
            self.draw()
            pygame.display.flip()
            self._clock.tick(60)
            frames += 1
        if max_frames is None:
            pygame.quit()

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle one Pygame event."""

        if event.type == pygame.QUIT:
            self._running = False
            return
        if event.type == pygame.VIDEORESIZE:
            width = max(960, int(event.w))
            height = max(680, int(event.h))
            self._screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
            return
        if self._path_entry_active:
            self._handle_path_entry_event(event)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def draw(self) -> None:
        """Draw the complete current interface."""

        self._screen.fill(_BACKGROUND)
        width, height = self._screen.get_size()
        side_width = 350
        side_left = width - side_width
        pygame.draw.rect(self._screen, _PANEL, (side_left, 0, side_width, height))
        self._draw_header(side_left)
        state = self._game.get_public_state()
        if state.size:
            self._draw_board(state, side_left, height)
        else:
            self._draw_empty_state(side_left, height)
        self._draw_side_panel(state, side_left, height)
        if self._path_entry_active:
            self._draw_path_entry()

    def load_from_path(self, path: str) -> bool:
        """Try to load a user-selected path while preserving the current game on error."""

        if not path.strip():
            self._set_message("Load cancelled.", _MUTED)
            return False
        try:
            self._load_puzzle(path)
        except (OSError, ValueError, RuntimeError) as exc:
            self._set_message(f"Load failed: {exc}", _ERROR)
            return False
        self._selected_cell = None
        self._active_clue_cell = None
        self._highlighted_cells.clear()
        self._set_message(f"Loaded {Path(path).name}.", _SUCCESS)
        return True

    def select_cell(self, cell_id: str) -> None:
        """Select a face-down card or activate a revealed clue."""

        state = self._game.get_public_state()
        if cell_id not in state.names:
            raise ValueError(f"unknown cell {cell_id!r}")
        if cell_id in state.revealed:
            self._selected_cell = None
            self._active_clue_cell = cell_id
            clue = state.revealed[cell_id][1]
            self._highlighted_cells = clue_cells(clue, state.size)
            self._set_message(f"Showing references for {clue.id}.", _MUTED)
        else:
            self._selected_cell = cell_id
            self._active_clue_cell = None
            self._highlighted_cells.clear()
            self._set_message(
                f"Selected {cell_id}. Choose CRIMINAL or INNOCENT.", _MUTED
            )

    def submit_selected(self, claimed: Verdict) -> ManualResult | MoveResult | None:
        """Dispatch the selected claim through the engine's active mode."""

        if self._selected_cell is None:
            self._set_message("Select a face-down card first.", _ERROR)
            return None
        cell_id = self._selected_cell
        try:
            if self._game.has_referee:
                result: ManualResult | MoveResult = self._game.submit_verdict(
                    cell_id, claimed
                )
            else:
                result = self._game.submit_manual(cell_id, claimed)
        except (RuntimeError, ValueError) as exc:
            self._set_message(str(exc), _ERROR)
            return None

        if isinstance(result, ManualResult):
            self._handle_manual_result(cell_id, result)
        else:
            self._handle_proof_result(cell_id, result)
        return result

    def restart_game(self) -> None:
        """Restart the loaded puzzle and clear UI selection state."""

        self._game.restart()
        self._selected_cell = None
        self._active_clue_cell = None
        self._highlighted_cells.clear()
        self._set_message("Puzzle restarted.", _MUTED)

    def _handle_manual_result(self, cell_id: str, result: ManualResult) -> None:
        if result is ManualResult.CORRECT:
            self._selected_cell = None
            if self._game.is_solved():
                self._set_message("CORRECT — puzzle complete!", _SUCCESS)
            else:
                self._set_message(f"CORRECT — {cell_id} revealed.", _SUCCESS)
        elif result is ManualResult.WRONG:
            self._set_message("WRONG — card stays face-down. Try again.", _ERROR)
        else:
            self._selected_cell = None
            self._set_message("ALREADY_REVEALED — choose another card.", _ERROR)

    def _handle_proof_result(self, cell_id: str, result: MoveResult) -> None:
        if result is MoveResult.ACCEPTED:
            self._selected_cell = None
            self._set_message(f"ACCEPTED — {cell_id} revealed.", _SUCCESS)
        else:
            self._set_message(result.value, _ERROR)

    def _handle_click(self, position: tuple[int, int]) -> None:
        if self._buttons.get("load", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            self._request_load()
            return
        if self._buttons.get("restart", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            if self._game.get_public_state().size:
                self.restart_game()
            return
        if self._buttons.get("criminal", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            self.submit_selected(Verdict.CRIMINAL)
            return
        if self._buttons.get("innocent", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            self.submit_selected(Verdict.INNOCENT)
            return
        if self._buttons.get("hint", pygame.Rect(0, 0, 0, 0)).collidepoint(position) or self._buttons.get(
            "auto", pygame.Rect(0, 0, 0, 0)
        ).collidepoint(position):
            self._set_message(
                "Disabled: Hint and Auto Solve require the future LogicAgent.",
                _MUTED,
            )
            return
        for cell_id, rect in self._card_rects.items():
            if rect.collidepoint(position):
                self.select_cell(cell_id)
                return

    def _request_load(self) -> None:
        selected, picker_available = self._pick_file_in_child_process()
        if selected is not None:
            self.load_from_path(selected)
        elif picker_available:
            self._set_message("Load cancelled.", _MUTED)
        else:
            self._path_entry_active = True
            self._path_text = ""
            self._set_message("File dialog unavailable. Enter a JSON path.", _MUTED)

    @staticmethod
    def _pick_file_in_child_process() -> tuple[str | None, bool]:
        script = (
            "import sys, tkinter as tk; "
            "from tkinter import filedialog; "
            "root=tk.Tk(); root.withdraw(); "
            "path=filedialog.askopenfilename(title='Load Griductive puzzle', "
            "filetypes=[('JSON puzzle','*.json'),('All files','*.*')]); "
            "root.destroy(); sys.stdout.write(path)"
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None, False
        if completed.returncode != 0:
            return None, False
        selected = completed.stdout.strip()
        return (selected or None), True

    def _handle_path_entry_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self._path_entry_active = False
            self._set_message("Load cancelled.", _MUTED)
        elif event.key == pygame.K_RETURN:
            path = self._path_text.strip().strip('"')
            self._path_entry_active = False
            self.load_from_path(path)
        elif event.key == pygame.K_BACKSPACE:
            self._path_text = self._path_text[:-1]
        elif event.unicode and event.unicode.isprintable():
            self._path_text += event.unicode

    def _draw_header(self, side_left: int) -> None:
        title = self._title_font.render("GRIDUCTIVE", True, _TEXT)
        mode = self._body_font.render("Manual practice — answer check", True, _HIGHLIGHT)
        self._screen.blit(title, (28, 18))
        self._screen.blit(mode, (28, 52))
        pygame.draw.line(self._screen, _PANEL, (20, 78), (side_left - 20, 78), 2)

    def _draw_empty_state(self, side_left: int, height: int) -> None:
        area = pygame.Rect(30, 105, side_left - 60, height - 150)
        pygame.draw.rect(self._screen, _PANEL, area, border_radius=16)
        heading = self._heading_font.render("No puzzle loaded", True, _TEXT)
        body = self._body_font.render(
            "Choose Load and select a complete 3x3, 4x4, or 5x5 JSON puzzle.",
            True,
            _MUTED,
        )
        self._screen.blit(heading, heading.get_rect(center=(area.centerx, area.centery - 18)))
        self._screen.blit(body, body.get_rect(center=(area.centerx, area.centery + 20)))
        self._card_rects.clear()

    def _draw_board(self, state: PublicState, side_left: int, height: int) -> None:
        available_width = side_left - 105
        available_height = height - 150
        gap = 8
        card_size = int(
            min(
                (available_width - gap * (state.size - 1)) / state.size,
                (available_height - gap * (state.size - 1)) / state.size,
            )
        )
        grid_width = card_size * state.size + gap * (state.size - 1)
        left = max(62, (side_left - grid_width) // 2)
        top = 105
        self._card_rects.clear()

        for col in range(state.size):
            label = self._heading_font.render(chr(65 + col), True, _MUTED)
            x = left + col * (card_size + gap) + card_size // 2
            self._screen.blit(label, label.get_rect(center=(x, top - 18)))
        for row in range(state.size):
            label = self._heading_font.render(str(row + 1), True, _MUTED)
            y = top + row * (card_size + gap) + card_size // 2
            self._screen.blit(label, label.get_rect(center=(left - 25, y)))

        for index, cell_id in enumerate(cell_ids(state.size)):
            row, col = divmod(index, state.size)
            rect = pygame.Rect(
                left + col * (card_size + gap),
                top + row * (card_size + gap),
                card_size,
                card_size,
            )
            self._card_rects[cell_id] = rect
            self._draw_card(state, cell_id, rect)

    def _draw_card(self, state: PublicState, cell_id: str, rect: pygame.Rect) -> None:
        revealed = cell_id in state.revealed
        if revealed:
            status = state.revealed[cell_id][0]
            color = _CRIMINAL if status is Verdict.CRIMINAL else _INNOCENT
        else:
            color = _FACE_DOWN
        pygame.draw.rect(self._screen, color, rect, border_radius=10)

        border = _PANEL
        width = 2
        if cell_id in self._highlighted_cells:
            border, width = _HIGHLIGHT, 5
        if cell_id == self._selected_cell:
            border, width = _ACCENT, 5
        pygame.draw.rect(self._screen, border, rect, width, border_radius=10)

        padding = max(7, rect.width // 18)
        id_surface = self._small_font.render(cell_id, True, _TEXT)
        self._screen.blit(id_surface, (rect.x + padding, rect.y + padding))
        name_font = self._heading_font if rect.width >= 150 else self._body_font
        name = name_font.render(state.names[cell_id], True, _TEXT)
        self._screen.blit(name, (rect.x + padding, rect.y + 29))
        job = self._small_font.render(state.jobs[cell_id], True, _TEXT)
        self._screen.blit(job, (rect.x + padding, rect.y + 55))

        if not revealed:
            face_down = self._small_font.render("FACE DOWN", True, _MUTED)
            self._screen.blit(
                face_down,
                face_down.get_rect(center=(rect.centerx, rect.bottom - max(24, rect.height // 5))),
            )
            return

        status, clue = state.revealed[cell_id]
        status_text = self._small_font.render(status.value, True, _TEXT)
        self._screen.blit(status_text, (rect.x + padding, rect.y + 78))
        clue_top = rect.y + 101
        available_lines = max(1, (rect.bottom - padding - clue_top) // 15)
        for line_number, line in enumerate(
            self._wrap_text(describe_clue(clue), self._tiny_font, rect.width - padding * 2)[
                :available_lines
            ]
        ):
            clue_line = self._tiny_font.render(line, True, _TEXT)
            self._screen.blit(clue_line, (rect.x + padding, clue_top + line_number * 15))

    def _draw_side_panel(self, state: PublicState, left: int, height: int) -> None:
        padding = 20
        x = left + padding
        panel_width = self._screen.get_width() - left - padding * 2
        heading = self._heading_font.render("Controls", True, _TEXT)
        self._screen.blit(heading, (x, 24))

        self._buttons = {
            "load": pygame.Rect(x, 62, (panel_width - 10) // 2, 42),
            "restart": pygame.Rect(x + (panel_width + 10) // 2, 62, (panel_width - 10) // 2, 42),
            "criminal": pygame.Rect(x, 122, panel_width, 44),
            "innocent": pygame.Rect(x, 176, panel_width, 44),
            "hint": pygame.Rect(x, 238, (panel_width - 10) // 2, 40),
            "auto": pygame.Rect(x + (panel_width + 10) // 2, 238, (panel_width - 10) // 2, 40),
        }
        self._draw_button("load", "Load", True)
        self._draw_button("restart", "Restart", bool(state.size))
        self._draw_button("criminal", "CRIMINAL", bool(state.size))
        self._draw_button("innocent", "INNOCENT", bool(state.size))
        self._draw_button("hint", "Hint", False)
        self._draw_button("auto", "Auto Solve", False)

        disabled = self._small_font.render(
            "Hint and Auto Solve await LogicAgent.", True, _MUTED
        )
        self._screen.blit(disabled, (x, 286))

        y = 322
        label = self._small_font.render("Feedback", True, _MUTED)
        self._screen.blit(label, (x, y))
        y += 24
        for line in self._wrap_text(self._message, self._body_font, panel_width):
            surface = self._body_font.render(line, True, self._message_color)
            self._screen.blit(surface, (x, y))
            y += 22

        y = max(y + 20, 430)
        detail_label = self._small_font.render("Selected revealed clue", True, _MUTED)
        self._screen.blit(detail_label, (x, y))
        y += 25
        if self._active_clue_cell and self._active_clue_cell in state.revealed:
            status, clue = state.revealed[self._active_clue_cell]
            heading_text = f"{self._active_clue_cell} — {status.value} — {clue.id}"
            for line in self._wrap_text(heading_text, self._body_font, panel_width):
                surface = self._body_font.render(line, True, _HIGHLIGHT)
                self._screen.blit(surface, (x, y))
                y += 22
            for line in self._wrap_text(describe_clue(clue), self._body_font, panel_width):
                if y > height - 25:
                    break
                surface = self._body_font.render(line, True, _TEXT)
                self._screen.blit(surface, (x, y))
                y += 22
        else:
            text = self._body_font.render(
                "Click a face-up card to inspect its clue.", True, _MUTED
            )
            self._screen.blit(text, (x, y))

    def _draw_button(self, key: str, label: str, enabled: bool) -> None:
        rect = self._buttons[key]
        pygame.draw.rect(
            self._screen, _BUTTON if enabled else _BUTTON_DISABLED, rect, border_radius=8
        )
        text = self._body_font.render(label, True, _TEXT if enabled else _MUTED)
        self._screen.blit(text, text.get_rect(center=rect.center))

    def _draw_path_entry(self) -> None:
        width, height = self._screen.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self._screen.blit(overlay, (0, 0))
        box = pygame.Rect(width // 2 - 360, height // 2 - 90, 720, 180)
        pygame.draw.rect(self._screen, _PANEL, box, border_radius=12)
        title = self._heading_font.render("Enter puzzle JSON path", True, _TEXT)
        self._screen.blit(title, (box.x + 24, box.y + 22))
        input_rect = pygame.Rect(box.x + 24, box.y + 65, box.width - 48, 42)
        pygame.draw.rect(self._screen, _BACKGROUND, input_rect, border_radius=6)
        pygame.draw.rect(self._screen, _ACCENT, input_rect, 2, border_radius=6)
        visible = self._path_text[-80:]
        value = self._body_font.render(visible, True, _TEXT)
        self._screen.blit(value, (input_rect.x + 10, input_rect.y + 10))
        help_text = self._small_font.render(
            "Enter: load    Esc: cancel", True, _MUTED
        )
        self._screen.blit(help_text, (box.x + 24, box.y + 130))

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font, width: int) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.size(candidate)[0] <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _set_message(self, message: str, color: Color) -> None:
        self._message = message
        self._message_color = color


if __name__ == "__main__":
    pygame.font.init()
    smoke_font = pygame.font.Font(None, 18)
    assert GriductiveApp._wrap_text("one two three", smoke_font, 50)
    pygame.quit()
