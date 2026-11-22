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
from gui.avatars import AvatarRenderer


Color = tuple[int, int, int]
LoadCallback = Callable[[str], None]
LevelListCallback = Callable[[], tuple[str, ...]]

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
        list_levels: LevelListCallback | None = None,
        load_level: LoadCallback | None = None,
        initial_level_name: str | None = None,
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
        self._clue_scroll = 0
        self._message = initial_message
        self._message_color = _MUTED
        self._card_rects: dict[str, pygame.Rect] = {}
        self._buttons: dict[str, pygame.Rect] = {}
        self._popup_scroll = 0
        self._path_entry_active = False
        self._path_text = ""
        # Prefer fonts with Vietnamese glyphs; Arial may resolve to Arial Narrow.
        font_names = ("tahoma", "dejavusans", "liberationsans", "arial")
        self._title_font = pygame.font.SysFont(font_names, 28, bold=True)
        self._heading_font = pygame.font.SysFont(font_names, 20, bold=True)
        self._body_font = pygame.font.SysFont(font_names, 17)
        self._small_font = pygame.font.SysFont(font_names, 14)
        self._tiny_font = pygame.font.SysFont(font_names, 12)
        self._card_job_font = pygame.font.SysFont(font_names, 10)
        self._badge_font = pygame.font.SysFont(font_names, 9, bold=True)
        self._avatars = AvatarRenderer()
        self._list_levels = list_levels
        self._load_level = load_level
        self._level_names: tuple[str, ...] = ()
        self._selected_level: str | None = None
        self._level_page = 0
        self._level_rects: dict[str, pygame.Rect] = {}
        self._current_level_name = initial_level_name
        self._choosing_level = not bool(game.get_public_state().size)
        if self._choosing_level:
            self._refresh_levels()

    @property
    def choosing_level(self) -> bool:
        """Return whether the level selector is visible."""

        return self._choosing_level

    @property
    def level_names(self) -> tuple[str, ...]:
        """Return discovered display names without private puzzle data."""

        return self._level_names

    @property
    def current_level_name(self) -> str | None:
        """Return the name of the successfully loaded level."""

        return self._current_level_name

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
        if self._choosing_level:
            if event.type == pygame.MOUSEWHEEL:
                self._change_level_page(-event.y)
            elif event.type == pygame.KEYDOWN:
                if event.key in {pygame.K_LEFT, pygame.K_PAGEUP}:
                    self._change_level_page(-1)
                elif event.key in {pygame.K_RIGHT, pygame.K_PAGEDOWN}:
                    self._change_level_page(1)
                elif event.key == pygame.K_RETURN:
                    self.play_selected_level()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_selector_click(event.pos)
            return
        if self._selected_cell is not None:
            self._handle_card_popup_event(event)
            return
        if (
            event.type == pygame.KEYDOWN
            and event.key == pygame.K_ESCAPE
            and self._active_clue_cell is not None
        ):
            self.clear_clue_selection()
            self._set_message("Đã bỏ khoanh vùng gợi ý.", _MUTED)
        elif event.type == pygame.MOUSEWHEEL and self._active_clue_cell is not None:
            self._clue_scroll = max(0, self._clue_scroll - event.y * 44)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def draw(self) -> None:
        """Draw the complete current interface."""

        self._screen.fill(_BACKGROUND)
        if self._choosing_level:
            self._draw_level_selector()
            if self._path_entry_active:
                self._draw_path_entry()
            return
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
        if self._selected_cell is not None:
            self._draw_card_popup(state)
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
            self._set_message(f"Không thể mở {Path(path).name}: {exc}", _ERROR)
            return False
        self._enter_loaded_game(Path(path).stem)
        self._set_message(f"Loaded {Path(path).name}.", _SUCCESS)
        return True

    def show_level_selector(self) -> None:
        """Rescan available names while retaining the current game in memory."""

        self._choosing_level = True
        self._selected_cell = None
        self._buttons.clear()
        self._card_rects.clear()
        self._set_message("Chọn một màn rồi bấm Chơi.", _MUTED)
        self._refresh_levels()

    def select_level(self, name: str) -> None:
        """Select a catalog name without reading its JSON file."""

        if name not in self._level_names:
            raise ValueError("unknown level name")
        self._selected_level = name

    def play_selected_level(self) -> bool:
        """Load the selected level lazily and keep the old game on failure."""

        name = self._selected_level
        if name is None or self._load_level is None:
            self._set_message("Hãy chọn một màn chơi trong danh sách.", _MUTED)
            return False
        try:
            self._load_level(name)
        except (OSError, ValueError, RuntimeError) as exc:
            self._set_message(f"Không thể mở {name}.json: {exc}", _ERROR)
            return False
        self._enter_loaded_game(name)
        self._set_message(f"Đã mở màn {name}.", _SUCCESS)
        return True

    def _enter_loaded_game(self, name: str) -> None:
        self._choosing_level = False
        self._current_level_name = name
        self._buttons.clear()
        self._level_rects.clear()
        self._selected_cell = None
        self.clear_clue_selection()

    def _refresh_levels(self) -> None:
        self._selected_level = None
        self._level_page = 0
        self._level_rects.clear()
        try:
            self._level_names = self._list_levels() if self._list_levels else ()
        except OSError:
            self._level_names = ()
            self._set_message("Không đọc được thư mục puzzles/. Bạn vẫn có thể Mở file JSON.", _ERROR)

    def _levels_per_page(self) -> int:
        return max(1, (self._screen.get_height() - 300) // 52)

    def _change_level_page(self, delta: int) -> None:
        last_page = max(0, (len(self._level_names) - 1) // self._levels_per_page())
        self._level_page = max(0, min(last_page, self._level_page + delta))
        self._level_rects.clear()

    def _handle_selector_click(self, position: tuple[int, int]) -> None:
        for name, rect in self._level_rects.items():
            if rect.collidepoint(position):
                self.select_level(name)
                return
        for key, rect in self._buttons.items():
            if not rect.collidepoint(position):
                continue
            if key == "load":
                self._request_load()
            elif key == "play":
                self.play_selected_level()
            elif key == "previous":
                self._change_level_page(-1)
            elif key == "next":
                self._change_level_page(1)
            elif key == "resume" and self._game.get_public_state().size:
                self._choosing_level = False
                self._buttons.clear()
                self._level_rects.clear()
            return

    def select_cell(self, cell_id: str) -> None:
        """Select a face-down card or activate a revealed clue."""

        state = self._game.get_public_state()
        if cell_id not in state.names:
            raise ValueError(f"unknown cell {cell_id!r}")
        if cell_id in state.revealed:
            self._selected_cell = None
            self._active_clue_cell = cell_id
            self._clue_scroll = 0
            clue = state.revealed[cell_id][1]
            self._highlighted_cells = clue_cells(clue, state.size)
            self._set_message(
                f"Gợi ý từ {cell_id}: {len(self._highlighted_cells)} ô liên quan. "
                "Viền vàng: ô được nhắc đến. Esc: bỏ chọn.",
                _HIGHLIGHT,
            )
        else:
            self._selected_cell = cell_id
            self._popup_scroll = 0
            self.clear_clue_selection()
            self._set_message("", _MUTED)

    def clear_clue_selection(self) -> None:
        """Clear clue highlighting without changing the game or revealing cards."""

        self._active_clue_cell = None
        self._highlighted_cells.clear()
        self._clue_scroll = 0

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
        self.clear_clue_selection()
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
        if self._buttons.get("levels", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            self.show_level_selector()
            return
        if self._buttons.get("load", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            self._request_load()
            return
        if self._buttons.get("restart", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            if self._game.get_public_state().size:
                self.restart_game()
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
        if self._current_level_name:
            name = self._fit_text(self._current_level_name, self._body_font, side_left - 260)
            self._screen.blit(self._body_font.render(name, True, _MUTED), (240, 29))
        pygame.draw.line(self._screen, _PANEL, (20, 78), (side_left - 20, 78), 2)

    def _draw_level_selector(self) -> None:
        width, height = self._screen.get_size()
        self._card_rects.clear()
        self._level_rects.clear()
        title = self._title_font.render("Chọn màn chơi", True, _TEXT)
        self._screen.blit(title, (40, 24))
        instruction = (
            "Chọn tên màn rồi bấm Chơi. Cuộn chuột hoặc dùng nút chuyển trang."
            if self._level_names else
            "Thêm file JSON vào thư mục puzzles/ hoặc chọn Mở file JSON"
        )
        self._screen.blit(self._body_font.render(instruction, True, _MUTED), (40, 70))
        self._change_level_page(0)
        per_page = self._levels_per_page()
        start = self._level_page * per_page
        for index, name in enumerate(self._level_names[start:start + per_page]):
            rect = pygame.Rect(40, 110 + index * 52, width - 80, 44)
            self._level_rects[name] = rect
            pygame.draw.rect(self._screen, _PANEL, rect, border_radius=8)
            if name == self._selected_level:
                pygame.draw.rect(self._screen, _ACCENT, rect, 2, border_radius=8)
            label = self._fit_text(name, self._heading_font, rect.width - 30)
            self._screen.blit(self._heading_font.render(label, True, _TEXT), (rect.x + 15, rect.y + 10))

        self._buttons = {
            "previous": pygame.Rect(40, height - 218, 130, 40),
            "next": pygame.Rect(180, height - 218, 130, 40),
            "load": pygame.Rect(40, height - 158, 240, 44),
            "play": pygame.Rect(width - 260, height - 158, 220, 44),
        }
        pages = max(1, (len(self._level_names) + per_page - 1) // per_page)
        self._draw_button("previous", "Trang trước", self._level_page > 0)
        self._draw_button("next", "Trang sau", self._level_page + 1 < pages)
        label = f"Trang {self._level_page + 1}/{pages} · {len(self._level_names)} màn"
        self._screen.blit(self._body_font.render(label, True, _MUTED), (330, height - 208))
        self._draw_button("load", "Mở file JSON", True)
        self._draw_button("play", "Chơi", self._selected_level is not None)
        if self._game.get_public_state().size:
            self._buttons["resume"] = pygame.Rect(width - 500, height - 158, 220, 44)
            self._draw_button("resume", "Tiếp tục ván", True)
        lines = self._wrap_text(self._message, self._body_font, width - 80)
        for index, line in enumerate(lines[:3]):
            if index == 2 and len(lines) > 3:
                line = self._fit_text(line + " …", self._body_font, width - 80)
            self._screen.blit(
                self._body_font.render(line, True, self._message_color),
                (40, height - 90 + index * 22),
            )

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
        if cell_id in {self._selected_cell, self._active_clue_cell}:
            border, width = _ACCENT, 5
        pygame.draw.rect(self._screen, border, rect, width, border_radius=10)
        if cell_id == self._active_clue_cell and cell_id in self._highlighted_cells:
            pygame.draw.rect(
                self._screen, _HIGHLIGHT, rect.inflate(-12, -12), 3, border_radius=6
            )

        padding = max(7, rect.width // 18)
        id_font = self._small_font if rect.width >= 150 else self._tiny_font
        id_surface = id_font.render(cell_id, True, _TEXT)
        self._screen.blit(id_surface, (rect.x + padding, rect.y + padding))
        if revealed:
            self._draw_revealed_card(state, cell_id, rect, padding, id_surface.get_height())
            return
        content_width = rect.width - padding * 2
        name_font = (
            self._heading_font if rect.width >= 180 else
            self._small_font if rect.width >= 120 else self._tiny_font
        )
        job_font = self._small_font if rect.width >= 150 else self._card_job_font
        name = name_font.render(self._fit_text(state.names[cell_id], name_font, content_width), True, _TEXT)
        job = job_font.render(self._fit_text(state.jobs[cell_id], job_font, content_width), True, _TEXT)
        job_rect = job.get_rect(midbottom=(rect.centerx, rect.bottom - padding))
        name_rect = name.get_rect(midbottom=(rect.centerx, job_rect.top - 2))
        self._screen.blit(name, name_rect)
        self._screen.blit(job, job_rect)

        body_top = rect.y + padding + id_surface.get_height() + 3
        body_bottom = name_rect.top - 4
        portrait_bottom = body_bottom
        diameter = max(1, min(int(rect.width * 0.56), portrait_bottom - body_top))
        identity = f"{cell_id}|{state.names[cell_id]}|{state.jobs[cell_id]}"
        portrait = self._avatars.render(identity, diameter)
        portrait_rect = portrait.get_rect(center=(rect.centerx, (body_top + portrait_bottom) // 2))
        self._screen.blit(portrait, portrait_rect)

    def _draw_revealed_card(
        self,
        state: PublicState,
        cell_id: str,
        rect: pygame.Rect,
        padding: int,
        coordinate_height: int,
    ) -> None:
        """Keep public character details compact above a centered clue area."""

        status, clue = state.revealed[cell_id]
        badge_font = self._tiny_font if rect.width >= 180 else self._badge_font
        badge = badge_font.render(status.value, True, _TEXT)
        self._screen.blit(
            badge, badge.get_rect(topright=(rect.right - padding, rect.y + padding))
        )

        header_top = rect.y + padding + coordinate_height + 3
        diameter = max(18, min(36, rect.width // 5))
        name_font = (
            self._small_font if rect.width >= 150 else
            self._tiny_font if rect.width >= 110 else self._card_job_font
        )
        job_font = self._tiny_font if rect.width >= 180 else self._card_job_font
        header_height = max(diameter, name_font.get_height() + job_font.get_height() + 2)
        identity = f"{cell_id}|{state.names[cell_id]}|{state.jobs[cell_id]}"
        portrait = self._avatars.render(identity, diameter)
        self._screen.blit(
            portrait,
            portrait.get_rect(midleft=(rect.x + padding, header_top + header_height // 2)),
        )
        text_left = rect.x + padding + diameter + 5
        text_width = rect.right - padding - text_left
        text_center = text_left + text_width // 2
        name = name_font.render(
            self._fit_text(state.names[cell_id], name_font, text_width), True, _TEXT
        )
        job = job_font.render(
            self._fit_text(state.jobs[cell_id], job_font, text_width), True, _TEXT
        )
        text_top = header_top + (header_height - name.get_height() - job.get_height() - 2) // 2
        self._screen.blit(name, name.get_rect(midtop=(text_center, text_top)))
        self._screen.blit(job, job.get_rect(midtop=(text_center, text_top + name.get_height() + 2)))

        separator_y = header_top + header_height + 4
        pygame.draw.line(
            self._screen, _MUTED,
            (rect.x + padding, separator_y), (rect.right - padding, separator_y),
        )
        area = pygame.Rect(
            rect.x + padding, separator_y + 5,
            rect.width - padding * 2, max(1, rect.bottom - padding - separator_y - 5),
        )
        clue_font = (
            self._body_font if rect.width >= 210 else
            self._small_font if rect.width >= 150 else
            self._tiny_font if rect.width >= 110 else self._card_job_font
        )
        line_height = clue_font.get_linesize()
        lines = self._wrap_text(describe_clue(clue), clue_font, area.width)
        visible_lines = max(1, area.height // line_height)
        displayed = lines[:visible_lines]
        if len(lines) > visible_lines:
            displayed[-1] = self._fit_text(displayed[-1] + " …", clue_font, area.width)
        top = area.y + max(0, (area.height - len(displayed) * line_height) // 2)
        previous_clip = self._screen.get_clip()
        self._screen.set_clip(area)
        for index, line in enumerate(displayed):
            surface = clue_font.render(self._fit_text(line, clue_font, area.width), True, _TEXT)
            self._screen.blit(surface, surface.get_rect(midtop=(rect.centerx, top + index * line_height)))
        self._screen.set_clip(previous_clip)

    def _draw_side_panel(self, state: PublicState, left: int, height: int) -> None:
        padding = 20
        x = left + padding
        panel_width = self._screen.get_width() - left - padding * 2
        heading = self._heading_font.render("Controls", True, _TEXT)
        self._screen.blit(heading, (x, 24))

        self._buttons = {
            "load": pygame.Rect(x, 62, (panel_width - 10) // 2, 42),
            "restart": pygame.Rect(x + (panel_width + 10) // 2, 62, (panel_width - 10) // 2, 42),
            "levels": pygame.Rect(x, 112, panel_width, 42),
            "hint": pygame.Rect(x, 172, (panel_width - 10) // 2, 40),
            "auto": pygame.Rect(x + (panel_width + 10) // 2, 172, (panel_width - 10) // 2, 40),
        }
        self._draw_button("load", "Mở file JSON", True)
        self._draw_button("levels", "Chọn màn", True)
        self._draw_button("restart", "Restart", bool(state.size))
        self._draw_button("hint", "Hint", False)
        self._draw_button("auto", "Auto Solve", False)

        disabled = self._small_font.render(
            "Hint and Auto Solve await LogicAgent.", True, _MUTED
        )
        self._screen.blit(disabled, (x, 224))

        y = 260
        label = self._small_font.render("Feedback", True, _MUTED)
        self._screen.blit(label, (x, y))
        y += 24
        for line in self._wrap_text(self._message, self._body_font, panel_width):
            surface = self._body_font.render(line, True, self._message_color)
            self._screen.blit(surface, (x, y))
            y += 22

        y = max(y + 20, 370)
        detail_label = self._small_font.render("Gợi ý đang xem", True, _MUTED)
        self._screen.blit(detail_label, (x, y))
        y += 25
        if self._active_clue_cell and self._active_clue_cell in state.revealed:
            status, clue = state.revealed[self._active_clue_cell]
            references = ", ".join(
                cell for cell in cell_ids(state.size) if cell in self._highlighted_cells
            ) or "Không có ô nào"
            paragraphs = (
                (f"{self._active_clue_cell} — {status.value} — {clue.id}", _ACCENT),
                (f"Ô liên quan: {references}", _HIGHLIGHT),
                (describe_clue(clue), _TEXT),
            )
            lines = [
                (line, color)
                for text, color in paragraphs
                for line in (*self._wrap_text(text, self._body_font, panel_width), "")
            ]
            area = pygame.Rect(x, y, panel_width, max(1, height - y - 54))
            self._clue_scroll = min(self._clue_scroll, max(0, len(lines) * 22 - area.height))
            previous_clip = self._screen.get_clip()
            self._screen.set_clip(area)
            for index, (line, color) in enumerate(lines):
                surface = self._body_font.render(line, True, color)
                self._screen.blit(surface, (x, y + index * 22 - self._clue_scroll))
            self._screen.set_clip(previous_clip)
            for index, text in enumerate((
                "Xanh: thẻ gợi ý · Vàng: ô liên quan",
                "Cuộn: đọc gợi ý · Esc: bỏ khoanh vùng",
            )):
                surface = self._small_font.render(text, True, _MUTED)
                self._screen.blit(surface, (x, height - 44 + index * 20))
        else:
            text = self._body_font.render(
                "Bấm thẻ đã lật để xem ô liên quan.", True, _MUTED
            )
            self._screen.blit(text, (x, y))

    def _card_popup_layout(self) -> tuple[pygame.Rect, dict[str, pygame.Rect]]:
        width, height = self._screen.get_size()
        box = pygame.Rect(0, 0, min(600, width - 48), min(480, height - 48))
        box.center = (width // 2, height // 2)
        button_width = (box.width - 64) // 2
        buttons = {
            "innocent": pygame.Rect(box.x + 24, box.bottom - 78, button_width, 46),
            "criminal": pygame.Rect(box.centerx + 8, box.bottom - 78, button_width, 46),
            "close": pygame.Rect(box.right - 62, box.y + 14, 42, 36),
        }
        return box, buttons

    def _handle_card_popup_event(self, event: pygame.event.Event) -> None:
        box, buttons = self._card_popup_layout()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._selected_cell = None
        elif event.type == pygame.MOUSEWHEEL:
            self._popup_scroll = max(0, self._popup_scroll - event.y * 44)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if buttons["close"].collidepoint(event.pos) or not box.collidepoint(event.pos):
                self._selected_cell = None
            elif buttons["innocent"].collidepoint(event.pos):
                self.submit_selected(Verdict.INNOCENT)
            elif buttons["criminal"].collidepoint(event.pos):
                self.submit_selected(Verdict.CRIMINAL)

    def _draw_card_popup(self, state: PublicState) -> None:
        cell_id = self._selected_cell
        if cell_id is None:
            return
        overlay = pygame.Surface(self._screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self._screen.blit(overlay, (0, 0))
        box, buttons = self._card_popup_layout()
        pygame.draw.rect(self._screen, _PANEL, box, border_radius=16)
        pygame.draw.rect(self._screen, _ACCENT, box, 2, border_radius=16)
        title = self._heading_font.render(f"Thẻ {cell_id} — Chọn trạng thái", True, _TEXT)
        self._screen.blit(title, (box.x + 24, box.y + 24))

        # Unrevealed clues belong to the engine, so this view uses public data only.
        content = pygame.Rect(box.x + 24, box.y + 82, box.width - 48, box.height - 270)
        identity = f"{cell_id}|{state.names[cell_id]}|{state.jobs[cell_id]}"
        portrait = self._avatars.render(identity, min(120, content.height))
        portrait_rect = portrait.get_rect(midleft=(content.x, content.centery))
        self._screen.blit(portrait, portrait_rect)
        text_area = pygame.Rect(
            portrait_rect.right + 24, content.y,
            content.right - portrait_rect.right - 24, content.height,
        )
        lines: list[str] = []
        for text in (
            f"Tên: {state.names[cell_id]}",
            f"Nghề nghiệp: {state.jobs[cell_id]}",
            "Gợi ý: Sẽ hiển thị sau khi bạn lật đúng thẻ.",
        ):
            lines.extend(self._wrap_text(text, self._body_font, text_area.width))
            lines.append("")
        self._popup_scroll = min(self._popup_scroll, max(0, len(lines) * 24 - content.height))
        previous_clip = self._screen.get_clip()
        self._screen.set_clip(text_area)
        for index, line in enumerate(lines):
            surface = self._body_font.render(line, True, _TEXT)
            self._screen.blit(surface, (text_area.x, text_area.y + index * 24 - self._popup_scroll))
        self._screen.set_clip(previous_clip)

        if len(lines) * 24 > content.height:
            help_text = self._small_font.render("Cuộn chuột để đọc thêm", True, _MUTED)
            self._screen.blit(help_text, (content.x, content.bottom + 6))
        feedback = self._wrap_text(self._message, self._small_font, content.width)
        for index, line in enumerate(feedback[:3]):
            surface = self._small_font.render(line, True, self._message_color)
            self._screen.blit(surface, (content.x, box.bottom - 150 + index * 20))
        for key, label, color in (
            ("innocent", "Innocent", _INNOCENT),
            ("criminal", "Criminal", _CRIMINAL),
            ("close", "X", _BUTTON),
        ):
            rect = buttons[key]
            pygame.draw.rect(self._screen, color, rect, border_radius=8)
            surface = self._body_font.render(label, True, _TEXT)
            self._screen.blit(surface, surface.get_rect(center=rect.center))

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
    def _fit_text(text: str, font: pygame.font.Font, width: int) -> str:
        if font.size(text)[0] <= width:
            return text
        while text and font.size(text + "…")[0] > width:
            text = text[:-1]
        return text + "…"

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
