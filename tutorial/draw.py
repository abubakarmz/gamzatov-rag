"""Простой «рисовальщик» слайдов 1920×1080 на Pillow (для видео и картинок в PDF)."""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
CONTENT_H = 880          # ниже — полоса субтитров
FONTS = "C:/Windows/Fonts/"

BG = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"
LINE = "#d6d5d0"
BLUE = "#2a78d6"
BLUE_BG = "#eef4fc"
ORANGE = "#eb6834"
ORANGE_BG = "#fdeee7"
GREEN = "#0ca30c"
GREEN_BG = "#e8f6e8"
RED = "#d03b3b"
RED_BG = "#fbeaea"
YELLOW_BG = "#fff1b8"
GREY_BG = "#f0efec"

_cache = {}


def font(size, bold=False, mono=False):
    name = ("consolab.ttf" if bold else "consola.ttf") if mono else ("segoeuib.ttf" if bold else "segoeui.ttf")
    key = (name, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(FONTS + name, size)
    return _cache[key]


def parse_rich(text):
    """**жирный**, ==выделение==, ~~зачёркнутый~~, [[синий]], {{красный}}, <<зелёный>>"""
    parts = re.split(r"(\*\*.+?\*\*|==.+?==|~~.+?~~|\[\[.+?\]\]|\{\{.+?\}\}|<<.+?>>)", text)
    out = []
    for p in parts:
        if not p:
            continue
        style = "normal"
        for mark, st, n in (("**", "bold", 2), ("==", "hl", 2), ("~~", "strike", 2),
                            ("[[", "blue", 2), ("{{", "red", 2), ("<<", "green", 2)):
            if p.startswith(mark) and len(p) > 2 * n:
                style, p = st, p[n:-n]
                break
        out.append((p, style))
    return out


class Slide:
    def __init__(self):
        self.img = Image.new("RGB", (W, H), BG)
        self.d = ImageDraw.Draw(self.img)

    # ---------- базовые элементы ----------
    def title(self, text, sub=None, num=None):
        x = 90
        if num is not None:
            self.d.rounded_rectangle((x, 62, x + 74, 136), 18, fill=BLUE)
            self.d.text((x + 37, 99), str(num), font=font(44, True), fill="white", anchor="mm")
            x += 100
        self.d.text((x, 58), text, font=font(58, True), fill=INK)
        if sub:
            self.d.text((x, 138), sub, font=font(30), fill=MUTED)

    def rich(self, x, y, w, text, size=36, color=INK, mono=False, line_gap=1.35, align="left"):
        """Текст с переносами и разметкой. Возвращает нижнюю координату."""
        lines, line, lw = [], [], 0
        for seg, style in parse_rich(text):
            for piece in re.split(r"(\n| )", seg):
                if piece == "\n":
                    lines.append(line); line, lw = [], 0
                    continue
                if piece == "":
                    continue
                f = font(size, style in ("bold",) or style in ("blue", "red", "green"), mono)
                pw = self.d.textlength(piece, font=f)
                if piece != " " and lw + pw > w and line:
                    while line and line[-1][0] == " ":
                        lw -= line.pop()[3]
                    lines.append(line); line, lw = [], 0
                if piece == " " and not line:
                    continue
                line.append((piece, style, f, pw)); lw += pw
        lines.append(line)
        lh = int(size * line_gap)
        for ln in lines:
            total = sum(p[3] for p in ln)
            cx = x + (w - total) / 2 if align == "center" else x
            for piece, style, f, pw in ln:
                col = {"blue": BLUE, "red": RED, "green": GREEN, "strike": "#9a9993"}.get(style, color)
                if style == "hl" and piece != " ":
                    self.d.rectangle((cx - 3, y + size * 0.12, cx + pw + 3, y + size * 1.22), fill=YELLOW_BG)
                self.d.text((cx, y), piece, font=f, fill=col)
                if style == "strike" and piece != " ":
                    self.d.line((cx, y + size * 0.72, cx + pw, y + size * 0.72), fill="#9a9993", width=3)
                cx += pw
            y += lh
        return y

    def box(self, x, y, w, h, fill=BLUE_BG, outline=None, radius=24, width=3):
        self.d.rounded_rectangle((x, y, x + w, y + h), radius, fill=fill, outline=outline, width=width)

    def card(self, x, y, w, h, head, body, color=BLUE, fill=BLUE_BG, size=32, head_size=34, mono=False):
        self.box(x, y, w, h, fill=fill, outline=color)
        self.d.text((x + 28, y + 20), head, font=font(head_size, True), fill=color)
        self.rich(x + 28, y + 30 + head_size * 1.4, w - 56, body, size=size, mono=mono)

    def arrow(self, x1, y1, x2, y2, color=MUTED, width=6, head=22):
        import math
        self.d.line((x1, y1, x2, y2), fill=color, width=width)
        a = math.atan2(y2 - y1, x2 - x1)
        p1 = (x2 - head * math.cos(a - 0.45), y2 - head * math.sin(a - 0.45))
        p2 = (x2 - head * math.cos(a + 0.45), y2 - head * math.sin(a + 0.45))
        self.d.polygon([(x2, y2), p1, p2], fill=color)

    def table(self, x, y, widths, rows, size=30, row_h=None, header=True, fills=None, aligns=None):
        row_h = row_h or int(size * 2.0)
        fills = fills or {}
        cy = y
        for r, row in enumerate(rows):
            heights = []
            for c, cell in enumerate(row):
                tmp = Slide.__new__(Slide); tmp.d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
                heights.append(tmp.rich(0, 0, widths[c] - 32, str(cell), size=size) + 22)
            h = max(row_h, max(heights))
            cx = x
            for c, cell in enumerate(row):
                fill = BLUE_BG if (header and r == 0) else fills.get(r, "white")
                self.d.rectangle((cx, cy, cx + widths[c], cy + h), fill=fill, outline=LINE, width=2)
                text = f"**{cell}**" if header and r == 0 and "**" not in str(cell) else str(cell)
                self.rich(cx + 16, cy + 12, widths[c] - 32, text, size=size)
                cx += widths[c]
            cy += h
        return cy

    def image(self, path, x, y, w=None, h=None, border=True):
        im = Image.open(path).convert("RGB")
        if w and not h:
            h = int(im.height * w / im.width)
        elif h and not w:
            w = int(im.width * h / im.height)
        im = im.resize((int(w), int(h)), Image.LANCZOS)
        self.img.paste(im, (int(x), int(y)))
        if border:
            self.d.rectangle((x, y, x + w, y + h), outline=LINE, width=3)
        return y + h

    def pill(self, x, y, text, color=BLUE, fill=None, size=30):
        f = font(size, True)
        tw = self.d.textlength(text, font=f)
        self.d.rounded_rectangle((x, y, x + tw + 40, y + size * 1.7), size, fill=fill or color)
        self.d.text((x + 20, y + size * 0.85), text, font=f, fill="white" if not fill else color, anchor="lm")
        return x + tw + 40

    # ---------- субтитры ----------
    def with_subtitle(self, text):
        im = self.img.copy()
        d = ImageDraw.Draw(im)
        d.rectangle((0, CONTENT_H + 20, W, H), fill="#1a1a19")
        tmp = Slide.__new__(Slide); tmp.img = im; tmp.d = d
        f = 34
        # подбираем размер, чтобы влезло в 3 строки
        for f in (36, 33, 30, 27):
            probe = Slide.__new__(Slide); probe.d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
            if probe.rich(0, 0, W - 260, text, size=f, line_gap=1.3) <= f * 1.3 * 3:
                break
        n_lines_h = probe.rich(0, 0, W - 260, text, size=f, line_gap=1.3)
        top = CONTENT_H + 20 + (H - CONTENT_H - 20 - n_lines_h) / 2
        tmp.rich(130, top, W - 260, text, size=f, color="#f0efec", line_gap=1.3, align="center")
        return im

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.img.save(path)
