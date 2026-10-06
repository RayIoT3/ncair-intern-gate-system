"""The mockup's icons (nav icons and the light/dark toggle), drawn with Pillow, so no SVG library is needed.
Pillow is not installed with CustomTkinter: run `pip install pillow` once.

They are 24x24 stroke icons (2px, round ends) in the style of the Feather set. To add
an icon, paste its SVG path data into PATHS; this parser handles M L H V A Z, upper
and lower case, with circular arcs only. Check the icon set's licence before shipping.
"""
import math
import re

import customtkinter as ctk
from PIL import Image, ImageDraw

import theme

PATHS = {
    "Gate": "M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3",
    "Dashboard": "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
    "Interns": "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8"
               "M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
    "Cards": "M2 5h20v14H2zM2 10h20M6 15h4",
    "AI Report": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8",
}
ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "A": 7, "Z": 0}


def _arc(x1, y1, r, fa, fs, x2, y2):
    """Points along an SVG circular arc (endpoint form), excluding the start point."""
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    d2 = dx * dx + dy * dy
    r = max(r, math.sqrt(d2))
    co = math.sqrt(max(0, (r * r - d2) / d2)) * (-1 if fa == fs else 1)
    cx, cy = co * dy + (x1 + x2) / 2, -co * dx + (y1 + y2) / 2
    a1 = math.atan2(y1 - cy, x1 - cx)
    da = math.atan2(y2 - cy, x2 - cx) - a1
    if fs and da < 0:
        da += 2 * math.pi
    if not fs and da > 0:
        da -= 2 * math.pi
    return [(cx + r * math.cos(a1 + da * k / 24), cy + r * math.sin(a1 + da * k / 24)) for k in range(1, 25)]


def _polylines(d):
    toks = re.findall(r"[MmLlHhVvAaZz]|-?\d*\.?\d+", d)
    lines, cur, x, y, start, cmd, i = [], [], 0.0, 0.0, (0.0, 0.0), "", 0
    while i < len(toks):
        if toks[i].isalpha():
            cmd, i = toks[i], i + 1
            if cmd in "Zz":
                if cur:
                    lines.append(cur + [start])
                cur, (x, y) = [], start
                continue
        c, rel = cmd.upper(), cmd.islower()
        a = [float(t) for t in toks[i:i + ARGS[c]]]
        i += ARGS[c]
        nx, ny = x, y
        if c in "ML":
            nx, ny = (x + a[0], y + a[1]) if rel else (a[0], a[1])
        elif c == "H":
            nx = x + a[0] if rel else a[0]
        elif c == "V":
            ny = y + a[0] if rel else a[0]
        elif c == "A":
            nx, ny = (x + a[5], y + a[6]) if rel else (a[5], a[6])
        if c == "M":
            if cur:
                lines.append(cur)
            cur, start, cmd = [(nx, ny)], (nx, ny), "l" if rel else "L"   # extra pairs are line-tos
        elif c == "A":
            cur += _arc(x, y, a[0], int(a[3]), int(a[4]), nx, ny)
        else:
            cur.append((nx, ny))
        x, y = nx, ny
    if cur:
        lines.append(cur)
    return lines


def render(d, color, size=22, stroke=2.0):
    """Draw path data as a `size`-px icon (stored at 2x so it stays sharp on HiDPI screens)."""
    ss = 8
    im = Image.new("RGBA", (24 * ss, 24 * ss), (0, 0, 0, 0))
    dr, w = ImageDraw.Draw(im), stroke * ss
    for pts in _polylines(d):
        pts = [(px * ss, py * ss) for px, py in pts]
        for p, q in zip(pts, pts[1:]):
            dr.line([p, q], fill=color, width=round(w))
        for px, py in pts:                                    # round joints and caps
            dr.ellipse([px - w / 2, py - w / 2, px + w / 2, py + w / 2], fill=color)
    return im.resize((size * 2, size * 2), Image.LANCZOS)


def nav_icon(name, size=22):
    """(inactive, active) CTkImage pair; each follows light/dark mode on its own."""
    def make(colors):
        return ctk.CTkImage(light_image=render(PATHS[name], colors[0], size),
                            dark_image=render(PATHS[name], colors[1], size), size=(size, size))
    return make(theme.MUTED), make(theme.PRIMARY_TEXT)


def render_theme(color, size=18, stroke=1.6):
    """The mockup's half-filled circle glyph (the light/dark button), stored at 2x."""
    ss, n = 8, size * 2
    im = Image.new("RGBA", (n * ss, n * ss), (0, 0, 0, 0))
    pad = 3 * ss
    box = [pad, pad, n * ss - pad - 1, n * ss - pad - 1]
    dr = ImageDraw.Draw(im)
    dr.pieslice(box, 90, 270, fill=color)                     # left half filled
    dr.ellipse(box, outline=color, width=round(stroke * 2 * ss))
    return im.resize((n, n), Image.LANCZOS)


def theme_icon(size=18):
    """CTkImage for the light/dark button; follows light/dark mode on its own."""
    return ctk.CTkImage(light_image=render_theme(theme.TEXT[0], size),
                        dark_image=render_theme(theme.TEXT[1], size), size=(size, size))
