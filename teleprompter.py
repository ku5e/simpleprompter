import pygame
import pyperclip
import tkinter as tk
from tkinter import filedialog
import re
import sys

# ── Colors ────────────────────────────────────────────────────────────────────
BLACK      = (  0,   0,   0)
WHITE      = (255, 255, 255)
GRAY       = (150, 150, 150)
DIM_GRAY   = ( 80,  80,  80)
DARK_GREEN = ( 20, 100,  40)
BTN_GREEN  = ( 50, 200,  80)
GOLD       = (220, 180,  80)   # H1 headers
GOLD_DIM   = (170, 130,  50)   # H2 headers
GOLD_DIMMER= (120,  90,  35)   # H3 headers
RULE_COLOR = ( 70,  70,  70)   # horizontal rule

MARKER_COLORS = {
    '[pause]':             (220,  50,  50),
    '[beat]':              (100, 149, 237),
    '[applause]':          ( 50, 205,  50),
    '[hold for reaction]': (  0, 220, 220),
    '[roll video]':        (220,   0, 220),
}

MARKER_PATTERN = re.compile(
    '(' + '|'.join(re.escape(k) for k in MARKER_COLORS) + ')'
)

# Inline markdown: **bold** and *italic*
INLINE_MD = re.compile(r'(\*\*[^*\n]+\*\*|\*[^*\n]+\*)')

# ── Settings ──────────────────────────────────────────────────────────────────
FONT_SIZE_DEFAULT = 52
FONT_SIZE_MIN     = 20
FONT_SIZE_MAX     = 140
FONT_SIZE_STEP    = 4

SPEED_DEFAULT   = 2.0
SPEED_MIN       = 0.3
SPEED_MAX       = 20.0
SPEED_STEP      = 0.3

FPS             = 60
HIGHLIGHT_RATIO = 0.38
HIGHLIGHT_ALPHA = 50       # bumped — more visible
EDIT_MARGIN     = 60
CURSOR_BLINK_MS = 500

WIN_W, WIN_H = 1280, 800

PLACEHOLDER = [
    "# Your Script Title",
    "",
    "Type or paste your script here. Use Ctrl+O to open a .txt or .md file.",
    "",
    "## Section markers use ##",
    "",
    "Use **bold** for emphasis. Use *italic* for softer emphasis.",
    "",
    "Teleprompter markers: [pause]  [beat]  [applause]  [hold for reaction]  [roll video]",
    "",
    "---",
    "",
    "Ctrl+Alt+Enter or click START to run.  ESC returns here.",
]


class Teleprompter:

    def __init__(self):
        pygame.init()
        pygame.key.start_text_input()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        self.W, self.H = WIN_W, WIN_H
        pygame.display.set_caption("Teleprompter")
        self.clock = pygame.time.Clock()

        self.font_size = FONT_SIZE_DEFAULT
        self.font        = self._make_font(self.font_size, bold=False, italic=False)
        self.font_bold   = self._make_font(self.font_size, bold=True,  italic=False)
        self.font_italic = self._make_font(self.font_size, bold=False, italic=True)
        self.hud_font    = self._make_font(20)
        self.ui_font     = self._make_font(26)

        self.lines     = PLACEHOLDER[:]
        self.scroll_y  = 0.0
        self.speed     = SPEED_DEFAULT
        self.direction = 0
        self.mode      = 'edit'

        self.cursor_line    = 0
        self.cursor_col     = 0
        self.cursor_visible = True
        self.cursor_blink_t = pygame.time.get_ticks()
        self.selection      = None   # None or ((l1,c1),(l2,c2)) normalized

        self.running = True

    # ── Fonts ─────────────────────────────────────────────────────────────────

    def _make_font(self, size, bold=False, italic=False):
        for name in ("verdana", "arial", "trebuchetms", "dejavusans"):
            path = pygame.font.match_font(name, bold=bold, italic=italic)
            if path:
                return pygame.font.Font(path, size)
        return pygame.font.SysFont("sans-serif", size, bold=bold, italic=italic)

    def _reload_fonts(self):
        self.font        = self._make_font(self.font_size, bold=False, italic=False)
        self.font_bold   = self._make_font(self.font_size, bold=True,  italic=False)
        self.font_italic = self._make_font(self.font_size, bold=False, italic=True)

    # ── Text loading ──────────────────────────────────────────────────────────

    def _load_text(self, text):
        self.lines       = text.splitlines() or [""]
        self.scroll_y    = 0.0
        self.cursor_line = 0
        self.cursor_col  = 0

    def _open_file(self):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            filetypes=[
                ("Script files", "*.txt *.md"),
                ("Text files", "*.txt"),
                ("Markdown files", "*.md"),
                ("All files", "*.*"),
            ]
        )
        root.destroy()
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self._load_text(f.read())

    def _paste(self):
        try:
            text = pyperclip.paste()
            if text.strip():
                self._load_text(text)
        except Exception:
            pass

    # ── Markdown parsing ──────────────────────────────────────────────────────

    def _header_level(self, line):
        """Return (level, text) for heading lines, or (0, line) for normal."""
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            return len(m.group(1)), m.group(2)
        return 0, line

    def _is_rule(self, line):
        return re.match(r'^[-*_]{3,}\s*$', line.strip()) is not None

    def _parse_inline(self, text):
        """Return list of (segment_text, font, color) for a raw text string."""
        parts = INLINE_MD.split(text)
        result = []
        for p in parts:
            if not p:
                continue
            if p.startswith('**') and p.endswith('**') and len(p) > 4:
                result.append((p[2:-2], self.font_bold, WHITE))
            elif p.startswith('*') and p.endswith('*') and len(p) > 2:
                result.append((p[1:-1], self.font_italic, (200, 200, 200)))
            else:
                # Teleprompter markers within normal text
                subparts = MARKER_PATTERN.split(p)
                for sp in subparts:
                    if sp:
                        result.append((sp, self.font, MARKER_COLORS.get(sp, WHITE)))
        return result

    def _parse_inline_edit(self, text):
        """Edit mode: show markdown syntax dimmed, content colored."""
        parts = INLINE_MD.split(text)
        result = []
        for p in parts:
            if not p:
                continue
            if p.startswith('**') and p.endswith('**') and len(p) > 4:
                result.append(('**', self.font, DIM_GRAY))
                result.append((p[2:-2], self.font_bold, WHITE))
                result.append(('**', self.font, DIM_GRAY))
            elif p.startswith('*') and p.endswith('*') and len(p) > 2:
                result.append(('*', self.font, DIM_GRAY))
                result.append((p[1:-1], self.font_italic, (200, 200, 200)))
                result.append(('*', self.font, DIM_GRAY))
            else:
                subparts = MARKER_PATTERN.split(p)
                for sp in subparts:
                    if sp:
                        result.append((sp, self.font, MARKER_COLORS.get(sp, WHITE)))
        return result

    # ── Cursor helpers ────────────────────────────────────────────────────────

    def _clamp_cursor(self):
        self.cursor_line = max(0, min(self.cursor_line, len(self.lines) - 1))
        self.cursor_col  = max(0, min(self.cursor_col, len(self.lines[self.cursor_line])))

    def _cursor_reset_blink(self):
        self.cursor_visible = True
        self.cursor_blink_t = pygame.time.get_ticks()

    def _max_scroll(self):
        return max(0.0, (len(self.lines) - 1) * self.font.get_linesize())

    def _scroll_to_cursor(self):
        line_h = self.font.get_linesize()
        hl_y   = int(self.H * HIGHLIGHT_RATIO)
        cy     = hl_y + self.cursor_line * line_h - int(self.scroll_y)
        if cy < line_h * 2:
            self.scroll_y = max(0.0, self.cursor_line * line_h - line_h * 2)
        elif cy > self.H - line_h * 3:
            self.scroll_y = min(self._max_scroll(),
                                self.cursor_line * line_h - self.H + line_h * 3)

    def _edit_scroll(self, lines):
        self.scroll_y = max(0.0, min(
            self.scroll_y + lines * self.font.get_linesize(), self._max_scroll()
        ))

    def _edit_scroll_page(self, direction):
        self.scroll_y = max(0.0, min(
            self.scroll_y + direction * self.H * 0.85, self._max_scroll()
        ))

    # ── Editing ops ───────────────────────────────────────────────────────────

    def _insert_char(self, text):
        line = self.lines[self.cursor_line]
        self.lines[self.cursor_line] = line[:self.cursor_col] + text + line[self.cursor_col:]
        self.cursor_col += len(text)
        self._scroll_to_cursor()
        self._cursor_reset_blink()

    def _backspace(self):
        if self.cursor_col > 0:
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = line[:self.cursor_col - 1] + line[self.cursor_col:]
            self.cursor_col -= 1
        elif self.cursor_line > 0:
            prev = self.lines[self.cursor_line - 1]
            self.cursor_col = len(prev)
            self.lines[self.cursor_line - 1] = prev + self.lines[self.cursor_line]
            self.lines.pop(self.cursor_line)
            self.cursor_line -= 1
        self._scroll_to_cursor()
        self._cursor_reset_blink()

    def _delete_forward(self):
        line = self.lines[self.cursor_line]
        if self.cursor_col < len(line):
            self.lines[self.cursor_line] = line[:self.cursor_col] + line[self.cursor_col + 1:]
        elif self.cursor_line < len(self.lines) - 1:
            self.lines[self.cursor_line] = line + self.lines[self.cursor_line + 1]
            self.lines.pop(self.cursor_line + 1)
        self._cursor_reset_blink()

    def _enter(self):
        line = self.lines[self.cursor_line]
        self.lines[self.cursor_line] = line[:self.cursor_col]
        self.lines.insert(self.cursor_line + 1, line[self.cursor_col:])
        self.cursor_line += 1
        self.cursor_col  = 0
        self._scroll_to_cursor()
        self._cursor_reset_blink()

    # ── Selection ─────────────────────────────────────────────────────────────

    def _select_all(self):
        last = len(self.lines) - 1
        self.selection = ((0, 0), (last, len(self.lines[last])))
        self.cursor_line = last
        self.cursor_col  = len(self.lines[last])
        self._cursor_reset_blink()

    def _clear_selection(self):
        self.selection = None

    def _delete_selection(self):
        if not self.selection:
            return
        (l1, c1), (l2, c2) = self.selection
        if l1 == l2:
            line = self.lines[l1]
            self.lines[l1] = line[:c1] + line[c2:]
        else:
            self.lines[l1] = self.lines[l1][:c1] + self.lines[l2][c2:]
            del self.lines[l1 + 1:l2 + 1]
        self.cursor_line = l1
        self.cursor_col  = c1
        self.selection   = None
        self._clamp_cursor()

    def _draw_selection(self, surf, line, y, line_idx):
        if not self.selection:
            return
        (l1, c1), (l2, c2) = self.selection
        if not (l1 <= line_idx <= l2):
            return
        line_h = self.font.get_linesize()
        if l1 == l2:
            x0 = EDIT_MARGIN + self.font.size(line[:c1])[0]
            x1 = EDIT_MARGIN + self.font.size(line[:c2])[0]
        elif line_idx == l1:
            x0 = EDIT_MARGIN + self.font.size(line[:c1])[0]
            x1 = EDIT_MARGIN + self.font.size(line)[0] + 12
        elif line_idx == l2:
            x0 = EDIT_MARGIN
            x1 = EDIT_MARGIN + self.font.size(line[:c2])[0]
        else:
            x0 = EDIT_MARGIN
            x1 = EDIT_MARGIN + self.font.size(line)[0] + 12
        if x1 <= x0:
            return
        sel = pygame.Surface((x1 - x0, line_h))
        sel.fill((70, 110, 190))
        sel.set_alpha(130)
        surf.blit(sel, (x0, y))

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _blit_segments(self, surf, segments, x, y):
        """Blit a list of (text, font, color) segments left-to-right from x."""
        cx = x
        for text, font, color in segments:
            ts = font.render(text, True, color)
            surf.blit(ts, (cx, y))
            cx += ts.get_width()
        return cx

    def _render_line_edit(self, surf, line, y, line_idx):
        line_h = self.font.get_linesize()
        self._draw_selection(surf, line, y, line_idx)

        if self._is_rule(line):
            mid = y + line_h // 2
            pygame.draw.line(surf, RULE_COLOR, (EDIT_MARGIN, mid), (self.W - 20, mid), 1)
            # Cursor on rule line
            if line_idx == self.cursor_line and self.cursor_visible:
                pygame.draw.rect(surf, WHITE, (EDIT_MARGIN, y + 2, 2, line_h - 4))
            return

        level, heading_text = self._header_level(line)

        if level > 0:
            header_colors = {1: GOLD, 2: GOLD_DIM, 3: GOLD_DIMMER}
            hc = header_colors.get(level, GOLD_DIMMER)
            prefix = '#' * level + ' '
            # Render prefix dim, heading text in gold
            px = EDIT_MARGIN
            ps = self.font.render(prefix, True, DIM_GRAY)
            surf.blit(ps, (px, y))
            px += ps.get_width()
            segs = self._parse_inline_edit(heading_text)
            for text, font, color in segs:
                ts = font.render(text, True, hc)
                surf.blit(ts, (px, y))
                px += ts.get_width()
        else:
            segs = self._parse_inline_edit(line)
            self._blit_segments(surf, segs, EDIT_MARGIN, y)

        # Cursor — measured on raw text with base font for consistency
        if line_idx == self.cursor_line and self.cursor_visible:
            cursor_x = EDIT_MARGIN + self.font.size(line[:self.cursor_col])[0]
            pygame.draw.rect(surf, WHITE, (cursor_x, y + 2, 2, line_h - 4))

    def _render_line_run(self, surf, line, y):
        line_h = self.font.get_linesize()

        if self._is_rule(line):
            mid = y + line_h // 2
            pygame.draw.line(surf, RULE_COLOR, (60, mid), (self.W - 60, mid), 1)
            return

        level, heading_text = self._header_level(line)

        if level > 0:
            header_colors = {1: GOLD, 2: GOLD_DIM, 3: GOLD_DIMMER}
            hc = header_colors.get(level, GOLD_DIMMER)
            segs = self._parse_inline(heading_text)
            total_w = sum(f.size(t)[0] for t, f, _ in segs)
            cx = max(60, (self.W - total_w) // 2)
            for text, font, _ in segs:
                ts = font.render(text, True, hc)
                surf.blit(ts, (cx, y))
                cx += ts.get_width()
        else:
            segs = self._parse_inline(line)
            total_w = sum(f.size(t)[0] for t, f, _ in segs)
            cx = max(60, (self.W - total_w) // 2)
            for text, font, color in segs:
                ts = font.render(text, True, color)
                surf.blit(ts, (cx, y))
                cx += ts.get_width()

    def _draw_highlight_band(self, surf, hl_y, hl_h):
        band = pygame.Surface((self.W, hl_h))
        band.fill((255, 255, 200))
        band.set_alpha(HIGHLIGHT_ALPHA)
        surf.blit(band, (0, hl_y - hl_h // 2))

    def _draw_scrollbar(self, surf):
        line_h   = self.font.get_linesize()
        total_px = len(self.lines) * line_h
        if total_px <= self.H:
            return
        bar_x        = self.W - 6
        view_ratio   = min(1.0, self.H / total_px)
        thumb_h      = max(24, int(self.H * view_ratio))
        max_scroll   = total_px - self.H
        scroll_ratio = self.scroll_y / max_scroll if max_scroll > 0 else 0
        thumb_y      = int((self.H - thumb_h) * scroll_ratio)
        pygame.draw.rect(surf, (30, 30, 30), (bar_x, 0, 6, self.H))
        pygame.draw.rect(surf, (90, 90, 90), (bar_x, thumb_y, 6, thumb_h), border_radius=3)

    def _start_btn_rect(self):
        label = self.ui_font.render("START  (Ctrl+Alt+Enter)", True, WHITE)
        bw = label.get_width() + 30
        bh = 52
        return pygame.Rect((self.W - bw) // 2, self.H - 90, bw, bh)

    def _font_minus_rect(self):
        return pygame.Rect(18, self.H - 90, 40, 52)

    def _font_plus_rect(self):
        return pygame.Rect(130, self.H - 90, 40, 52)

    def _draw_font_controls(self, surf):
        minus = self._font_minus_rect()
        plus  = self._font_plus_rect()
        mid_y = minus.y + minus.h // 2
        for rect, char in ((minus, "−"), (plus, "+")):
            pygame.draw.rect(surf, (60, 60, 60), rect, border_radius=6)
            pygame.draw.rect(surf, GRAY, rect, 1, border_radius=6)
            t = self.ui_font.render(char, True, WHITE)
            surf.blit(t, (rect.x + (rect.w - t.get_width()) // 2,
                          rect.y + (rect.h - t.get_height()) // 2))
        label = self.hud_font.render(f"{self.font_size}pt", True, GRAY)
        surf.blit(label, (minus.right + 8, mid_y - label.get_height() // 2))

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw(self):
        line_h = self.font.get_linesize()
        hl_y   = int(self.H * HIGHLIGHT_RATIO)
        hl_h   = int(line_h * 1.3)

        surf = pygame.Surface((self.W, self.H))
        surf.fill(BLACK)

        self._draw_highlight_band(surf, hl_y, hl_h)

        surf.set_clip(pygame.Rect(EDIT_MARGIN, 0, self.W - 2 * EDIT_MARGIN, self.H))
        for i, line in enumerate(self.lines):
            y = hl_y + i * line_h - int(self.scroll_y)
            if y < -line_h:
                continue
            if y > self.H + line_h:
                break
            if self.mode == 'edit':
                self._render_line_edit(surf, line, y, i)
            else:
                self._render_line_run(surf, line, y)
        surf.set_clip(None)

        if self.mode == 'run':
            surf = pygame.transform.flip(surf, True, False)

        # HUD
        cur_line = min(len(self.lines), int(self.scroll_y / line_h) + 1)
        pos = self.hud_font.render(f"Line {cur_line} / {len(self.lines)}", True, DIM_GRAY)
        spd = self.hud_font.render(f"Speed: {self.speed:.1f}", True, GRAY)
        fsz = self.hud_font.render(f"Font: {self.font_size}", True, DIM_GRAY)
        surf.blit(spd, (self.W - spd.get_width() - 18, 14))
        surf.blit(fsz, (self.W - fsz.get_width() - 18, 38))
        surf.blit(pos, (self.W - pos.get_width() - 18, 62))
        self._draw_scrollbar(surf)

        if self.mode == 'edit':
            lbl = self.hud_font.render(
                "EDIT — Ctrl+O: open  |  Ctrl+V: paste  |  Ctrl+A: select all  |  Ctrl+Q: quit",
                True, DIM_GRAY
            )
            surf.blit(lbl, (18, 14))
            self._draw_font_controls(surf)
            btn = self._start_btn_rect()
            pygame.draw.rect(surf, DARK_GREEN, btn, border_radius=8)
            pygame.draw.rect(surf, BTN_GREEN,  btn, 2, border_radius=8)
            txt = self.ui_font.render("START  (Ctrl+Alt+Enter)", True, WHITE)
            surf.blit(txt, (btn.x + (btn.w - txt.get_width()) // 2,
                            btn.y + (btn.h - txt.get_height()) // 2))
        else:
            lbl = self.hud_font.render("ESC = edit mode", True, DIM_GRAY)
            surf.blit(lbl, (18, 14))

        self.screen.blit(surf, (0, 0))
        pygame.display.flip()

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self):
        now = pygame.time.get_ticks()
        if now - self.cursor_blink_t >= CURSOR_BLINK_MS:
            self.cursor_visible = not self.cursor_visible
            self.cursor_blink_t = now

        if self.mode != 'run' or self.direction == 0:
            return
        self.scroll_y = max(0.0, min(
            self.scroll_y + self.direction * self.speed,
            max(0.0, (len(self.lines) - 1) * self.font.get_linesize())
        ))

    # ── Events ────────────────────────────────────────────────────────────────

    def _click_to_cursor(self, mx, my):
        line_h  = self.font.get_linesize()
        hl_y    = int(self.H * HIGHLIGHT_RATIO)
        clicked = max(0, min(int((my - hl_y + self.scroll_y) / line_h), len(self.lines) - 1))
        self.cursor_line = clicked
        line    = self.lines[clicked]
        rel_x   = mx - EDIT_MARGIN
        best_col, best_dist = 0, float('inf')
        for i in range(len(line) + 1):
            dist = abs(self.font.size(line[:i])[0] - rel_x)
            if dist < best_dist:
                best_dist, best_col = dist, i
        self.cursor_col = best_col
        self._cursor_reset_blink()

    def _handle_events(self):
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.VIDEORESIZE:
                self.W, self.H = event.w, event.h
                self.screen = pygame.display.set_mode((self.W, self.H), pygame.RESIZABLE)

            elif event.type == pygame.TEXTINPUT:
                if self.mode == 'edit':
                    if self.selection:
                        self._delete_selection()
                    self._insert_char(event.text)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self.mode == 'edit' and event.button == 1:
                    mx, my = event.pos
                    if self._start_btn_rect().collidepoint((mx, my)):
                        self.mode = 'run'
                    elif self._font_minus_rect().collidepoint((mx, my)):
                        self.font_size = max(FONT_SIZE_MIN, self.font_size - FONT_SIZE_STEP)
                        self._reload_fonts()
                    elif self._font_plus_rect().collidepoint((mx, my)):
                        self.font_size = min(FONT_SIZE_MAX, self.font_size + FONT_SIZE_STEP)
                        self._reload_fonts()
                    else:
                        self._click_to_cursor(mx, my)

            elif event.type == pygame.KEYDOWN:
                k   = event.key
                mod = event.mod

                if self.mode == 'edit':
                    ctrl = bool(mod & pygame.KMOD_CTRL)
                    alt  = bool(mod & pygame.KMOD_ALT)

                    if ctrl and alt and k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.mode = 'run'
                    elif ctrl and k == pygame.K_q:
                        self.running = False
                    elif ctrl and k == pygame.K_a:
                        self._select_all()
                    elif ctrl and k == pygame.K_o:
                        self._open_file()
                    elif ctrl and k == pygame.K_v:
                        self._paste()
                    elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if self.selection:
                            self._delete_selection()
                        else:
                            self._enter()
                    elif k == pygame.K_BACKSPACE:
                        if self.selection:
                            self._delete_selection()
                        else:
                            self._backspace()
                    elif k == pygame.K_DELETE:
                        if self.selection:
                            self._delete_selection()
                        else:
                            self._delete_forward()
                    elif k == pygame.K_LEFT:
                        self._clear_selection()
                        if self.cursor_col > 0:
                            self.cursor_col -= 1
                        elif self.cursor_line > 0:
                            self.cursor_line -= 1
                            self.cursor_col = len(self.lines[self.cursor_line])
                        self._scroll_to_cursor()
                        self._cursor_reset_blink()
                    elif k == pygame.K_RIGHT:
                        self._clear_selection()
                        if self.cursor_col < len(self.lines[self.cursor_line]):
                            self.cursor_col += 1
                        elif self.cursor_line < len(self.lines) - 1:
                            self.cursor_line += 1
                            self.cursor_col = 0
                        self._scroll_to_cursor()
                        self._cursor_reset_blink()
                    elif k == pygame.K_UP:
                        self._clear_selection()
                        if self.cursor_line > 0:
                            self.cursor_line -= 1
                            self._clamp_cursor()
                        self._scroll_to_cursor()
                        self._cursor_reset_blink()
                    elif k == pygame.K_DOWN:
                        self._clear_selection()
                        if self.cursor_line < len(self.lines) - 1:
                            self.cursor_line += 1
                            self._clamp_cursor()
                        self._scroll_to_cursor()
                        self._cursor_reset_blink()
                    elif k == pygame.K_HOME:
                        self._clear_selection()
                        self.cursor_col = 0
                        self._cursor_reset_blink()
                    elif k == pygame.K_END:
                        self._clear_selection()
                        self.cursor_col = len(self.lines[self.cursor_line])
                        self._cursor_reset_blink()
                    elif k == pygame.K_PAGEDOWN:
                        self._edit_scroll_page(1)
                    elif k == pygame.K_PAGEUP:
                        self._edit_scroll_page(-1)
                    elif k == pygame.K_r and not ctrl:
                        self.scroll_y = 0.0
                    elif k in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                        self.font_size = min(FONT_SIZE_MAX, self.font_size + FONT_SIZE_STEP)
                        self._reload_fonts()
                    elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.font_size = max(FONT_SIZE_MIN, self.font_size - FONT_SIZE_STEP)
                        self._reload_fonts()

                elif self.mode == 'run':
                    if k == pygame.K_ESCAPE:
                        self.mode      = 'edit'
                        self.direction = 0
                    elif k == pygame.K_PAGEDOWN:
                        self.direction = 1
                    elif k == pygame.K_PAGEUP:
                        self.direction = -1
                    elif k == pygame.K_UP:
                        self.speed = min(SPEED_MAX, round(self.speed + SPEED_STEP, 1))
                    elif k == pygame.K_DOWN:
                        self.speed = max(SPEED_MIN, round(self.speed - SPEED_STEP, 1))
                    elif k in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                        self.font_size = min(FONT_SIZE_MAX, self.font_size + FONT_SIZE_STEP)
                        self._reload_fonts()
                    elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.font_size = max(FONT_SIZE_MIN, self.font_size - FONT_SIZE_STEP)
                        self._reload_fonts()
                    elif k == pygame.K_r:
                        self.scroll_y = 0.0

            elif event.type == pygame.KEYUP:
                if self.mode == 'run':
                    k = event.key
                    if k == pygame.K_PAGEDOWN and self.direction == 1:
                        self.direction = 0
                    elif k == pygame.K_PAGEUP and self.direction == -1:
                        self.direction = 0

            elif event.type == pygame.MOUSEWHEEL:
                if self.mode == 'edit':
                    self._edit_scroll(-event.y * 3)
                else:
                    self.speed = max(SPEED_MIN, min(
                        SPEED_MAX, round(self.speed + event.y * SPEED_STEP, 1)
                    ))

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        while self.running:
            self._handle_events()
            self._update()
            self._draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Teleprompter().run()
