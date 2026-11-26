"""Pygame interface for proof-based Griductive play."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING, Protocol

import pygame

from core.engine import GameEngine
from core.models import MoveResult, PublicState, Verdict
from core.regions import cell_ids, clue_cells, describe_clue
from gui.avatars import AvatarRenderer

if TYPE_CHECKING:
    from solver.agent import LogicAgent


Color = tuple[int, int, int]
LoadCallback = Callable[[str], None]
LevelListCallback = Callable[[], tuple[str, ...]]

@dataclass(frozen=True)
class Theme:
    """Immutable colors for one interface appearance."""

    background: Color
    panel: Color
    face_down: Color
    card_border: Color
    criminal: Color
    innocent: Color
    text: Color
    muted: Color
    accent: Color
    highlight: Color
    button: Color
    button_disabled: Color
    success: Color
    error: Color


_DARK_THEME = Theme(
    background=(20, 25, 38),
    panel=(31, 39, 58),
    face_down=(58, 76, 113),
    card_border=(31, 39, 58),
    criminal=(145, 55, 62),
    innocent=(47, 120, 91),
    text=(239, 242, 248),
    muted=(170, 181, 202),
    accent=(84, 156, 255),
    highlight=(250, 199, 72),
    button=(66, 82, 116),
    button_disabled=(52, 57, 70),
    success=(104, 211, 145),
    error=(255, 126, 126),
)

_LIGHT_THEME = Theme(
    background=(244, 238, 226),
    panel=(250, 247, 240),
    face_down=(252, 249, 243),
    card_border=(51, 43, 38),
    criminal=(247, 220, 214),
    innocent=(224, 235, 218),
    text=(45, 37, 33),
    muted=(119, 106, 94),
    accent=(42, 119, 70),
    highlight=(143, 91, 0),
    button=(232, 222, 205),
    button_disabled=(239, 233, 222),
    success=(21, 109, 57),
    error=(174, 37, 48),
)

_PROOF_SECONDS = 1.0
_AUTO_STEP_INTERVAL = 0.25


class ProofGame(Protocol):
    """Game operations used by the GUI without exposing private puzzle data."""

    @property
    def has_referee(self) -> bool:
        """Return whether proof-based checking is installed."""

    def get_public_state(self) -> PublicState:
        """Return current public knowledge."""

    def submit_verdict(self, cell: str, claimed: Verdict) -> MoveResult:
        """Submit a proof-based verdict when a referee exists."""

    def restart(self) -> None:
        """Restore initially revealed cards."""

    def is_solved(self) -> bool:
        """Return whether every card is revealed."""


class GriductiveApp:
    """Draw the board and submit verdicts for proof-based checking."""

    def __init__(
        self,
        game: ProofGame,
        load_puzzle: LoadCallback,
        initial_message: str = "Chọn một màn để bắt đầu.",
        window_size: tuple[int, int] = (1280, 820),
        list_levels: LevelListCallback | None = None,
        load_level: LoadCallback | None = None,
        initial_level_name: str | None = None,
    ) -> None:
        pygame.init()
        pygame.display.set_caption("Griductive")
        self._screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
        self._clock = pygame.time.Clock()
        self._colors = _LIGHT_THEME
        self._loaded_game = game
        self._game = game
        self._agent: LogicAgent | None = None
        self._open_proof_game()
        self._hint_cell: str | None = None
        self._next_auto_step: float | None = None
        self._auto_steps = 0
        self._running = False
        self._selected_cell: str | None = None
        self._active_clue_cell: str | None = None
        self._highlighted_cells: set[str] = set()
        self._clue_scroll = 0
        self._message = initial_message
        self._message_color = self._colors.muted
        self._card_rects: dict[str, pygame.Rect] = {}
        self._buttons: dict[str, pygame.Rect] = {}
        self._popup_scroll = 0
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
            if (
                self._running
                and self._next_auto_step is not None
                and monotonic() >= self._next_auto_step
            ):
                self._advance_auto_solve()
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
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self._theme_button_rect().collidepoint(event.pos)
        ):
            self.toggle_theme()
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
            self._set_message("Đã bỏ khoanh vùng gợi ý.", self._colors.muted)
        elif event.type == pygame.MOUSEWHEEL and self._active_clue_cell is not None:
            self._clue_scroll = max(0, self._clue_scroll - event.y * 44)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def draw(self) -> None:
        """Draw the complete current interface."""

        self._screen.fill(self._colors.background)
        if self._choosing_level:
            self._draw_level_selector()
            self._draw_theme_button()
            return
        width, height = self._screen.get_size()
        side_width = 350
        side_left = width - side_width
        pygame.draw.rect(self._screen, self._colors.panel, (side_left, 0, side_width, height))
        self._draw_header(side_left)
        state = self._game.get_public_state()
        if state.size:
            self._draw_board(state, side_left, height)
        else:
            self._draw_empty_state(side_left, height)
        self._draw_side_panel(state, side_left, height)
        if self._selected_cell is not None:
            self._draw_card_popup(state)
        self._draw_theme_button()

    def toggle_theme(self) -> None:
        """Switch appearance for this app while preserving the active session."""

        previous = self._colors
        self._colors = _LIGHT_THEME if previous is _DARK_THEME else _DARK_THEME
        for role in ("muted", "success", "error", "highlight"):
            if self._message_color == getattr(previous, role):
                self._message_color = getattr(self._colors, role)
                break

    def _theme_button_rect(self) -> pygame.Rect:
        return pygame.Rect(self._screen.get_width() - 150, 16, 130, 36)

    def _draw_theme_button(self) -> None:
        rect = self._theme_button_rect()
        label = "Sáng" if self._colors is _DARK_THEME else "Tối"
        pygame.draw.rect(self._screen, self._colors.button, rect, border_radius=8)
        text = self._body_font.render(label, True, self._colors.text)
        self._screen.blit(text, text.get_rect(center=rect.center))

    def show_level_selector(self) -> None:
        """Rescan available names while retaining the current game in memory."""

        self._choosing_level = True
        self._next_auto_step = None
        self._selected_cell = None
        self._buttons.clear()
        self._card_rects.clear()
        self._set_message("Chọn một màn rồi bấm Chơi.", self._colors.muted)
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
            self._set_message("Hãy chọn một màn chơi trong danh sách.", self._colors.muted)
            return False
        try:
            self._load_level(name)
        except (OSError, ValueError, RuntimeError) as exc:
            self._set_message(f"Không thể mở {name}.json: {exc}", self._colors.error)
            return False
        self._enter_loaded_game(name)
        self._set_message(f"Đã mở màn {name}.", self._colors.success)
        return True

    def _enter_loaded_game(self, name: str) -> None:
        self._agent = None
        self._open_proof_game()
        self._choosing_level = False
        self._current_level_name = name
        self._buttons.clear()
        self._level_rects.clear()
        self._selected_cell = None
        self._hint_cell = None
        self._next_auto_step = None
        self.clear_clue_selection()

    def _refresh_levels(self) -> None:
        self._selected_level = None
        self._level_page = 0
        self._level_rects.clear()
        try:
            self._level_names = self._list_levels() if self._list_levels else ()
        except OSError:
            self._level_names = ()
            self._set_message("Không đọc được danh sách màn trong puzzles/.", self._colors.error)

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
            if key == "play":
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
        self._next_auto_step = None
        if cell_id in state.revealed:
            self._selected_cell = None
            self._active_clue_cell = cell_id
            self._clue_scroll = 0
            clue = state.revealed[cell_id][1]
            self._highlighted_cells = clue_cells(clue, state.size)
            self._set_message(
                f"Gợi ý từ {cell_id}: {len(self._highlighted_cells)} ô liên quan. "
                "Viền vàng: ô được nhắc đến. Esc: bỏ chọn.",
                self._colors.highlight,
            )
        else:
            self._selected_cell = cell_id
            self._popup_scroll = 0
            self.clear_clue_selection()
            self._set_message("", self._colors.muted)

    def clear_clue_selection(self) -> None:
        """Clear clue highlighting without changing the game or revealing cards."""

        self._active_clue_cell = None
        self._highlighted_cells.clear()
        self._clue_scroll = 0

    def submit_selected(self, claimed: Verdict) -> MoveResult | None:
        """Submit the selected claim using proof-based checking."""

        if self._selected_cell is None:
            self._set_message("Select a face-down card first.", self._colors.error)
            return None
        cell_id = self._selected_cell
        try:
            if not self._game.has_referee:
                raise RuntimeError("Chưa có bộ kiểm chứng suy luận.")
            if self._agent is not None:
                self._agent.deadline = monotonic() + _PROOF_SECONDS
            result = self._game.submit_verdict(cell_id, claimed)
        except (RuntimeError, ValueError, AssertionError) as exc:
            self._set_message(str(exc), self._colors.error)
            return None

        self._handle_proof_result(cell_id, result, claimed)
        return result

    def restart_game(self) -> None:
        """Restart the loaded puzzle and clear UI selection state."""

        self._game.restart()
        self._selected_cell = None
        self._hint_cell = None
        self._next_auto_step = None
        self.clear_clue_selection()
        self._set_message("Puzzle restarted.", self._colors.muted)

    def _open_proof_game(self) -> None:
        """Attach the existing logic agent while preserving launcher load callbacks."""

        self._game = self._loaded_game
        if isinstance(self._loaded_game, GameEngine) and not self._loaded_game.has_referee:
            from solver.agent import LogicAgent

            self._agent = LogicAgent()
            # Load callbacks still target the launcher's original engine.
            # Transfer the puzzle directly between engines for proof-based play.
            puzzle = (
                self._loaded_game._require_puzzle()
                if self._loaded_game.has_puzzle else None
            )
            self._game = GameEngine(puzzle, referee=self._agent)

    def _timed_agent(self) -> LogicAgent:
        if self._agent is None:
            from solver.agent import LogicAgent

            self._agent = LogicAgent()
        self._agent.deadline = monotonic() + _PROOF_SECONDS
        return self._agent

    def _request_hint(self) -> None:
        if not self._game.has_referee:
            self._set_message("Chưa có bộ kiểm chứng suy luận.", self._colors.error)
            return
        if self._game.is_solved():
            return
        self._next_auto_step = None
        self._hint_cell = None
        self.clear_clue_selection()
        agent = self._timed_agent()
        try:
            hint = agent.hint(self._game.get_public_state())
        except (RuntimeError, ValueError) as exc:
            self._set_message(str(exc), self._colors.error)
            return
        if hint is None:
            self._set_message(self._no_deduction_message(agent), self._colors.muted)
            return
        self._hint_cell = hint.cell
        self._set_message(
            f"Hint — Có thể chứng minh {hint.cell} là {hint.verdict.value}.",
            self._colors.highlight,
        )

    @staticmethod
    def _no_deduction_message(agent: LogicAgent) -> str:
        if agent.deadline is not None and monotonic() >= agent.deadline:
            return "TIMEOUT — Hết thời gian suy luận."
        return "Chưa tìm được kết luận mới có thể chứng minh."

    def _toggle_auto_solve(self) -> None:
        if not self._game.has_referee:
            self._set_message("Chưa có bộ kiểm chứng suy luận.", self._colors.error)
        elif self._next_auto_step is not None:
            self._next_auto_step = None
            self._set_message(f"Đã dừng Auto Solve sau {self._auto_steps} bước.", self._colors.muted)
        elif not self._game.is_solved():
            self._hint_cell = None
            self.clear_clue_selection()
            self._auto_steps = 0
            self._next_auto_step = monotonic()
            self._set_message("Auto Solve đang tìm nước đi có thể chứng minh.", self._colors.muted)

    def _advance_auto_solve(self) -> None:
        agent = self._timed_agent()
        try:
            proof = agent.step(self._game)
        except (RuntimeError, ValueError, AssertionError) as exc:
            self._next_auto_step = None
            self._set_message(f"Auto Solve — {exc}", self._colors.error)
            return
        if proof is None:
            self._next_auto_step = None
            message = self._no_deduction_message(agent)
            self._set_message(f"Auto Solve · {self._auto_steps} bước. {message}", self._colors.muted)
            return
        self._auto_steps += 1
        self.select_cell(proof.cell)
        deduction = f"{proof.cell} là {proof.verdict.value}."
        if self._game.is_solved():
            self._set_message(f"Hoàn thành sau {self._auto_steps} bước. {deduction}", self._colors.success)
        else:
            self._next_auto_step = monotonic() + _AUTO_STEP_INTERVAL
            self._set_message(f"Bước {self._auto_steps} — {deduction}", self._colors.success)

    @staticmethod
    def _verdict_feedback(cell_id: str, claimed: Verdict, result: MoveResult) -> str:
        """Explain a public-knowledge judgment without consulting hidden cards."""

        messages = {
            MoveResult.CONTRADICTED: (
                "CONTRADICTED — Lựa chọn mâu thuẫn với dữ kiện đã mở. Hãy xem lại các gợi ý."
            ),
            MoveResult.NOT_PROVABLE: (
                f"NOT_PROVABLE — Chưa đủ dữ kiện để kết luận {cell_id} là {claimed.value}."
            ),
            MoveResult.INCONSISTENT: "INCONSISTENT — Thông tin đã mở mâu thuẫn nhau.",
            MoveResult.TIMEOUT: "TIMEOUT — Hết thời gian kiểm tra suy luận. Hãy thử lại.",
            MoveResult.ALREADY_REVEALED: f"ALREADY_REVEALED — Thẻ {cell_id} đã được mở.",
        }
        return messages.get(result, "Lựa chọn không khớp đáp án của màn chơi.")

    def _handle_proof_result(
        self, cell_id: str, result: MoveResult, claimed: Verdict
    ) -> None:
        if result is MoveResult.ACCEPTED:
            self._selected_cell = None
            self._hint_cell = None
            if self._game.is_solved():
                self._set_message("ACCEPTED — Đã chứng minh toàn bộ bàn cờ!", self._colors.success)
            else:
                self._set_message(f"ACCEPTED — {cell_id} revealed.", self._colors.success)
        else:
            self._set_message(self._verdict_feedback(cell_id, claimed, result), self._colors.error)

    def _handle_click(self, position: tuple[int, int]) -> None:
        if self._buttons.get("levels", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            self.show_level_selector()
            return
        if self._buttons.get("restart", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            if self._game.get_public_state().size:
                self.restart_game()
            return
        if self._buttons.get("hint", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            self._request_hint()
            return
        if self._buttons.get("auto", pygame.Rect(0, 0, 0, 0)).collidepoint(position):
            self._toggle_auto_solve()
            return
        for cell_id, rect in self._card_rects.items():
            if rect.collidepoint(position):
                self.select_cell(cell_id)
                return

    def _draw_header(self, side_left: int) -> None:
        title = self._title_font.render("GRIDUCTIVE", True, self._colors.text)
        mode_label = "Suy luận — kết luận có chứng minh"
        mode = self._body_font.render(mode_label, True, self._colors.highlight)
        self._screen.blit(title, (28, 18))
        self._screen.blit(mode, (28, 52))
        if self._current_level_name:
            name = self._fit_text(self._current_level_name, self._body_font, side_left - 260)
            self._screen.blit(self._body_font.render(name, True, self._colors.muted), (240, 29))
        pygame.draw.line(self._screen, self._colors.panel, (20, 78), (side_left - 20, 78), 2)

    def _draw_level_selector(self) -> None:
        width, height = self._screen.get_size()
        self._card_rects.clear()
        self._level_rects.clear()
        title = self._title_font.render("Chọn màn chơi", True, self._colors.text)
        self._screen.blit(title, (40, 24))
        instruction = (
            "Chọn tên màn rồi bấm Chơi. Cuộn chuột hoặc dùng nút chuyển trang."
            if self._level_names else
            "Chưa có màn chơi. Hãy thêm file JSON vào thư mục puzzles/."
        )
        self._screen.blit(self._body_font.render(instruction, True, self._colors.muted), (40, 70))
        self._change_level_page(0)
        per_page = self._levels_per_page()
        start = self._level_page * per_page
        for index, name in enumerate(self._level_names[start:start + per_page]):
            rect = pygame.Rect(40, 110 + index * 52, width - 80, 44)
            self._level_rects[name] = rect
            pygame.draw.rect(self._screen, self._colors.panel, rect, border_radius=8)
            if name == self._selected_level:
                pygame.draw.rect(self._screen, self._colors.accent, rect, 2, border_radius=8)
            label = self._fit_text(name, self._heading_font, rect.width - 30)
            self._screen.blit(self._heading_font.render(label, True, self._colors.text), (rect.x + 15, rect.y + 10))

        self._buttons = {
            "previous": pygame.Rect(40, height - 218, 130, 40),
            "next": pygame.Rect(180, height - 218, 130, 40),
            "play": pygame.Rect(width - 260, height - 158, 220, 44),
        }
        pages = max(1, (len(self._level_names) + per_page - 1) // per_page)
        self._draw_button("previous", "Trang trước", self._level_page > 0)
        self._draw_button("next", "Trang sau", self._level_page + 1 < pages)
        label = f"Trang {self._level_page + 1}/{pages} · {len(self._level_names)} màn"
        self._screen.blit(self._body_font.render(label, True, self._colors.muted), (330, height - 208))
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
        pygame.draw.rect(self._screen, self._colors.panel, area, border_radius=16)
        heading = self._heading_font.render("Chưa chọn màn chơi", True, self._colors.text)
        body = self._body_font.render(
            "Bấm Chọn màn để bắt đầu.",
            True,
            self._colors.muted,
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
            label = self._heading_font.render(chr(65 + col), True, self._colors.muted)
            x = left + col * (card_size + gap) + card_size // 2
            self._screen.blit(label, label.get_rect(center=(x, top - 18)))
        for row in range(state.size):
            label = self._heading_font.render(str(row + 1), True, self._colors.muted)
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
            color = self._colors.criminal if status is Verdict.CRIMINAL else self._colors.innocent
        else:
            color = self._colors.face_down
        pygame.draw.rect(self._screen, color, rect, border_radius=10)

        border = self._colors.card_border
        width = 2
        if cell_id in self._highlighted_cells or cell_id == self._hint_cell:
            border, width = self._colors.highlight, 5
        if cell_id in {self._selected_cell, self._active_clue_cell}:
            border, width = self._colors.accent, 5
        pygame.draw.rect(self._screen, border, rect, width, border_radius=10)
        if cell_id == self._active_clue_cell and cell_id in self._highlighted_cells:
            pygame.draw.rect(
                self._screen, self._colors.highlight, rect.inflate(-12, -12), 3, border_radius=6
            )

        padding = max(7, rect.width // 18)
        id_font = self._small_font if rect.width >= 150 else self._tiny_font
        id_surface = id_font.render(cell_id, True, self._colors.text)
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
        name = name_font.render(self._fit_text(state.names[cell_id], name_font, content_width), True, self._colors.text)
        job = job_font.render(self._fit_text(state.jobs[cell_id], job_font, content_width), True, self._colors.text)
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
        badge = badge_font.render(status.value, True, self._colors.text)
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
            self._fit_text(state.names[cell_id], name_font, text_width), True, self._colors.text
        )
        job = job_font.render(
            self._fit_text(state.jobs[cell_id], job_font, text_width), True, self._colors.text
        )
        text_top = header_top + (header_height - name.get_height() - job.get_height() - 2) // 2
        self._screen.blit(name, name.get_rect(midtop=(text_center, text_top)))
        self._screen.blit(job, job.get_rect(midtop=(text_center, text_top + name.get_height() + 2)))

        separator_y = header_top + header_height + 4
        pygame.draw.line(
            self._screen, self._colors.muted,
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
            surface = clue_font.render(self._fit_text(line, clue_font, area.width), True, self._colors.text)
            self._screen.blit(surface, surface.get_rect(midtop=(rect.centerx, top + index * line_height)))
        self._screen.set_clip(previous_clip)

    def _draw_side_panel(self, state: PublicState, left: int, height: int) -> None:
        padding = 20
        x = left + padding
        panel_width = self._screen.get_width() - left - padding * 2
        heading = self._heading_font.render("Controls", True, self._colors.text)
        self._screen.blit(heading, (x, 24))

        column_width = (panel_width - 10) // 2
        other_column = x + column_width + 10
        self._buttons = {
            "restart": pygame.Rect(x, 62, panel_width, 42),
            "levels": pygame.Rect(x, 112, panel_width, 42),
            "hint": pygame.Rect(x, 172, column_width, 40),
            "auto": pygame.Rect(other_column, 172, column_width, 40),
        }
        self._draw_button("levels", "Chọn màn", True)
        self._draw_button("restart", "Restart", bool(state.size))
        can_solve = self._game.has_referee and bool(state.size) and not self._game.is_solved()
        auto_label = "Dừng giải" if self._next_auto_step is not None else "Auto Solve"
        self._draw_button("hint", "Hint", can_solve)
        self._draw_button("auto", auto_label, can_solve)
        y = 260
        label = self._small_font.render("Feedback", True, self._colors.muted)
        self._screen.blit(label, (x, y))
        y += 24
        for line in self._wrap_text(self._message, self._body_font, panel_width):
            surface = self._body_font.render(line, True, self._message_color)
            self._screen.blit(surface, (x, y))
            y += 22

        y = max(y + 20, 370)
        detail_label = self._small_font.render("Gợi ý đang xem", True, self._colors.muted)
        self._screen.blit(detail_label, (x, y))
        y += 25
        if self._active_clue_cell and self._active_clue_cell in state.revealed:
            status, clue = state.revealed[self._active_clue_cell]
            references = ", ".join(
                cell for cell in cell_ids(state.size) if cell in self._highlighted_cells
            ) or "Không có ô nào"
            paragraphs = (
                (f"{self._active_clue_cell} — {status.value} — {clue.id}", self._colors.accent),
                (f"Ô liên quan: {references}", self._colors.highlight),
                (describe_clue(clue), self._colors.text),
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
                surface = self._small_font.render(text, True, self._colors.muted)
                self._screen.blit(surface, (x, height - 44 + index * 20))
        else:
            text = self._body_font.render(
                "Bấm thẻ đã lật để xem ô liên quan.", True, self._colors.muted
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
        pygame.draw.rect(self._screen, self._colors.panel, box, border_radius=16)
        pygame.draw.rect(self._screen, self._colors.accent, box, 2, border_radius=16)
        title = self._heading_font.render(f"Thẻ {cell_id} — Chọn trạng thái", True, self._colors.text)
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
            surface = self._body_font.render(line, True, self._colors.text)
            self._screen.blit(surface, (text_area.x, text_area.y + index * 24 - self._popup_scroll))
        self._screen.set_clip(previous_clip)

        if len(lines) * 24 > content.height:
            help_text = self._small_font.render("Cuộn chuột để đọc thêm", True, self._colors.muted)
            self._screen.blit(help_text, (content.x, content.bottom + 6))
        feedback = self._wrap_text(self._message, self._small_font, content.width)
        for index, line in enumerate(feedback[:3]):
            surface = self._small_font.render(line, True, self._message_color)
            self._screen.blit(surface, (content.x, box.bottom - 150 + index * 20))
        for key, label, color in (
            ("innocent", "Innocent", self._colors.innocent),
            ("criminal", "Criminal", self._colors.criminal),
            ("close", "X", self._colors.button),
        ):
            rect = buttons[key]
            pygame.draw.rect(self._screen, color, rect, border_radius=8)
            surface = self._body_font.render(label, True, self._colors.text)
            self._screen.blit(surface, surface.get_rect(center=rect.center))

    def _draw_button(self, key: str, label: str, enabled: bool) -> None:
        rect = self._buttons[key]
        pygame.draw.rect(
            self._screen, self._colors.button if enabled else self._colors.button_disabled, rect, border_radius=8
        )
        text = self._body_font.render(label, True, self._colors.text if enabled else self._colors.muted)
        self._screen.blit(text, text.get_rect(center=rect.center))

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
