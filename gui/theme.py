"""NCAIR-inspired design tokens for the Intern Gate app.

Colours are (light, dark) pairs, which CustomTkinter accepts directly, so
widgets switch theme with ctk.set_appearance_mode("light" | "dark").
Font-size tokens are shared base units; CustomTkinter scales them for display DPI.
"""
from tkinter import ttk

import customtkinter as ctk

BG      = ("#F6F8F4", "#101812")   # NCAIR pale green, deep green-tinted dark mode
SURFACE = ("#FFFFFF", "#1C241F")   # cards
TEXT    = ("#143126", "#E8F0E9")
MUTED   = ("#4A6658", "#A8B6AC")
BORDER  = ("#DCE6DD", "#3C4A40")
CHIP    = ("#EEF5EF", "#263229")   # idle boxes, secondary buttons
PRIMARY, PRIMARY_HOVER = "#0F6A35", "#0A592C"
PRIMARY_TEXT = ("#0F6A35", "#79D99A")

# kind -> (background, text). Keep the pale backgrounds in dark mode too,
# exactly as the mockup does, so the text contrast stays high.
STATUS = {
    "idle": (CHIP, MUTED),
    "ok":   ("#E4F6EC", "#0E6B3B"),
    "er":   ("#FFE5EE", "#AA0000"),
    "wa":   ("#FFF8E7", "#8A6D00"),
    "in":   (("#ECF8EF", "#203A29"), ("#0A592C", "#8DDCA7")),
    "out":  (("#EFEFEF", "#2A302C"), TEXT),

}

RADIUS = 5
FAMILY = "Segoe UI"
FONT_SIZE = {
    "caption": 12,
    "small": 13,
    "body": 14,
    "section": 16,
    "title": 24,
    "metric": 38,
}
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 20}


def scale(widget):
    """Display scaling (1.0 = 100%, 1.25 = 125%, ...).

    Tk reports window and event sizes in real pixels, while every CustomTkinter size, font and
    wraplength is in scaled units. Divide a pixel width by this before comparing it with a breakpoint.
    """
    for get in (lambda: ctk.ScalingTracker.get_widget_scaling(widget), lambda: widget._get_widget_scaling()):
        try:
            return float(get())
        except Exception:
            pass
    return 1.0


def font(size=FONT_SIZE["body"], bold=False):
    return ctk.CTkFont(family=FAMILY, size=size, weight="bold" if bold else "normal")


def card(parent):
    return ctk.CTkFrame(parent, fg_color=SURFACE, border_color=BORDER,
                        border_width=1, corner_radius=RADIUS)


def label(parent, text, size=FONT_SIZE["body"], bold=False, color=TEXT, **kw):
    return ctk.CTkLabel(parent, text=text, font=font(size, bold), text_color=color,
                        anchor="w", justify="left", **kw)


def primary_button(parent, text, command):
    return ctk.CTkButton(parent, text=text, command=command, height=44,
                         corner_radius=RADIUS, font=font(FONT_SIZE["body"], True),
                         fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color="#FFFFFF")


def secondary_button(parent, text, command):
    return ctk.CTkButton(parent, text=text, command=command, height=44,
                         corner_radius=RADIUS, font=font(FONT_SIZE["body"], True),
                         fg_color=CHIP, hover_color=BORDER, text_color=TEXT)


def entry(parent, placeholder):
    return ctk.CTkEntry(parent, placeholder_text=placeholder, height=44,
                        corner_radius=RADIUS, border_width=1, border_color=BORDER,
                        fg_color=SURFACE, text_color=TEXT,
                        placeholder_text_color=MUTED, font=font(FONT_SIZE["body"] + 2))


def pill(parent, kind, text):
    bg, fg = STATUS[kind]
    return ctk.CTkLabel(parent, text=text, width=46, height=24, corner_radius=3,
                        fg_color=bg, text_color=fg, font=font(FONT_SIZE["small"]))


def flow(parent, widgets, cols, gap=SPACE["lg"]):
    """Grid `widgets` in `cols` equal columns. Call again with a new `cols` to re-flow."""
    for c in range(20):
        parent.columnconfigure(c, weight=0, uniform="")
    parent.columnconfigure(tuple(range(cols)), weight=1, uniform="flow")
    for i, w in enumerate(widgets):
        w.grid_forget()
        w.grid(row=i // cols, column=i % cols, sticky="new", pady=(0, gap),
               padx=(0 if i % cols == 0 else gap // 2, 0 if i % cols == cols - 1 else gap // 2))


def style_treeview(tree=None):
    """Theme ttk.Treeview for the current light/dark mode; call again after a mode change."""
    d = 1 if ctk.get_appearance_mode() == "Dark" else 0
    k = scale(tree) if tree is not None else 1.0        # ttk sizes are real pixels: scale them ourselves
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Gate.Treeview", background=SURFACE[d], fieldbackground=SURFACE[d], foreground=TEXT[d],
                rowheight=round(46 * k), borderwidth=0, font=(FAMILY, -round(14 * k)))
    s.configure("Gate.Treeview.Heading", background=SURFACE[d], foreground=MUTED[d], relief="flat",
                borderwidth=0, padding=(round(6 * k), round(8 * k)), font=(FAMILY, -round(13 * k)))
    s.map("Gate.Treeview", background=[("selected", CHIP[d])], foreground=[("selected", TEXT[d])])
    s.map("Gate.Treeview.Heading", background=[("active", SURFACE[d])])
    s.layout("Gate.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    if tree is not None:
        tree.tag_configure("in", foreground=("#0F6A35", "#8DDCA7")[d])
        tree.tag_configure("out", foreground=MUTED[d])
