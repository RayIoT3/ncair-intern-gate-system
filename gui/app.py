"""NCAIR Intern Gate main window. Run: python app.py"""
import ctypes
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from PIL import Image

import icons
import theme
from ai_screen import AIScreen
from dashboard_screen import DashboardScreen
from gate_screen import GateScreen
from cards_screen import CardsScreen
from interns_screen import InternsScreen

PAGES = [("Gate", GateScreen, True), ("Dashboard", DashboardScreen, True),
         ("Interns", InternsScreen, False), ("Cards", CardsScreen, False),
         ("AI Report", AIScreen, True)]   # True = scrolls

def _dark_logo(source):
    """Lighten the logo's black lettering for dark mode while preserving its green mark."""
    pixels = []
    for red, green, blue, alpha in source.getdata():
        if alpha and max(red, green, blue) < 64 and max(red, green, blue) - min(red, green, blue) < 20:
            pixels.append((232, 240, 233, alpha))
        else:
            pixels.append((red, green, blue, alpha))
    logo = source.copy()
    logo.putdata(pixels)
    return logo


def initial_window_size(screen_width, screen_height, scale):
    """Choose the normal window size, capped to the scaled usable screen area."""
    if scale <= 0:
        raise ValueError("Display scale must be greater than zero.")

    screen_width /= scale
    screen_height /= scale
    available_width = max(1, round(screen_width - App.SCREEN_MARGIN[0]))
    available_height = max(1, round(screen_height - App.SCREEN_MARGIN[1]))
    return (
        min(App.DEFAULT_SIZE[0], available_width),
        min(App.DEFAULT_SIZE[1], available_height),
    )


class App(ctk.CTk):
    NARROW = 760
    DEFAULT_SIZE = (1040, 660)
    MINIMUM_SIZE = (360, 520)
    SCREEN_MARGIN = (64, 96)

    def __init__(self, service):
        super().__init__(fg_color=theme.BG)
        self.title("NCAIR Intern Gate")
        self.iconbitmap(str(Path(__file__).resolve().parents[1] / "img" / "app-icon.ico"))
        self._fit_initial_geometry()
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._narrow, self.current = None, "Gate"

        self.nav = ctk.CTkFrame(self, fg_color=theme.SURFACE, border_color=theme.BORDER,
                                border_width=1, corner_radius=0)
        self.nav.pack_propagate(False)
        self.logo = theme.label(self.nav, "GATE", 13, True, color=theme.PRIMARY_TEXT)
        self.logo.configure(anchor="center")
        self.icons = {n: icons.nav_icon(n) for n, _, _ in PAGES}   # (inactive, active) per page
        self.nav_items = {}                                        # name -> (cell, button, active bar)

        self.main = ctk.CTkFrame(self, fg_color="transparent")
        head = ctk.CTkFrame(self.main, fg_color="transparent")
        head.pack(fill="x", pady=(24, 16))
        self.logo_source = Image.open(Path(__file__).resolve().parents[1] / "img" / "logo.png").convert("RGBA")
        self.dark_logo_source = _dark_logo(self.logo_source)
        self.logo_image = ctk.CTkImage(
            light_image=self.logo_source, dark_image=self.dark_logo_source, size=(112, 67))
        self.brand = ctk.CTkLabel(
            head, text="", image=self.logo_image, width=112, height=67, fg_color="transparent")
        self.brand.pack(side="left", padx=(0, 12))
        self.titles = ctk.CTkFrame(head, fg_color="transparent")
        self.titles.pack(side="left")
        self.heading = theme.label(self.titles, "Gate", theme.FONT_SIZE["title"], True)
        self.heading.pack(fill="x")
        self.sub = theme.label(self.titles, "NCAIR E-Government Facility", 13, color=theme.MUTED)
        self.sub.pack(fill="x")
        self.toggle = ctk.CTkButton(head, text="", image=icons.theme_icon(), width=40, height=40, corner_radius=20, border_width=1,
                                    border_color=theme.BORDER, fg_color=theme.SURFACE, hover_color=theme.CHIP,
                                    command=self._toggle_mode)
        self.toggle.pack(side="right", padx=(12, 0))
        clockbox = ctk.CTkFrame(head, fg_color="transparent")
        clockbox.pack(side="right")
        self.clock = theme.label(clockbox, "", 22)
        self.clock.configure(anchor="e")
        self.clock.pack(fill="x")
        self.date = theme.label(clockbox, "", 13, color=theme.MUTED)
        self.date.configure(anchor="e")

        body = ctk.CTkFrame(self.main, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.pages = {}
        for name, cls, scroll in PAGES:
            holder = (ctk.CTkScrollableFrame if scroll else ctk.CTkFrame)(
                body, fg_color="transparent")
            screen = cls(holder, service)
            screen.pack(fill="x" if scroll else "both", expand=not scroll)
            holder.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = (holder, screen)

        self.bind("<Configure>", self._on_configure)
        self._layout(False)
        self.show("Gate")
        self._tick()
        self.after(200, self._apply_native_titlebar)

    def _fit_initial_geometry(self):
        """Start within the usable screen area at the current monitor's DPI scale."""
        scale = theme.scale(self)
        width, height = initial_window_size(
            self.winfo_screenwidth(),
            self.winfo_screenheight(),
            scale,
        )

        # On a small or high-DPI display, lower the minimum so the window can still fit.
        self.minsize(min(self.MINIMUM_SIZE[0], width), min(self.MINIMUM_SIZE[1], height))
        self.geometry(f"{width}x{height}")

    def _build_nav(self, narrow):
        """Icon-only 68px rail on wide windows; icon + 11px label tabs along the bottom on narrow ones."""
        for cell, _, _ in self.nav_items.values():
            cell.destroy()
        self.nav_items = {}
        for name, _, _ in PAGES:
            cell = ctk.CTkFrame(self.nav, fg_color="transparent", corner_radius=0)
            btn = ctk.CTkButton(cell, text=name if narrow else "", image=self.icons[name][0],
                                compound="top" if narrow else "left", width=10, height=68 if narrow else 52,
                                corner_radius=0, font=theme.font(11), fg_color="transparent", hover=False,
                                text_color=theme.MUTED, command=lambda n=name: self.show(n))
            btn.pack(fill="both", expand=True)
            # 6px blue marker on the right edge; 9px wide with 3px pushed past the edge clips the right corners
            bar = ctk.CTkFrame(cell, width=9, height=36, corner_radius=3, fg_color=theme.PRIMARY)
            if narrow:
                cell.pack(side="left", expand=True, fill="both", padx=1, pady=(1, 0))
            else:
                cell.pack(fill="x", padx=1, pady=(0, 6))
            self.nav_items[name] = (cell, btn, bar)
        self._mark_active()

    def _mark_active(self):
        for n, (_, btn, bar) in self.nav_items.items():
            on = n == self.current
            btn.configure(image=self.icons[n][1 if on else 0],
                          text_color=theme.PRIMARY_TEXT if on else theme.MUTED)
            if on and not self._narrow:
                bar.place(relx=1.0, x=3, y=8, anchor="ne")
            else:
                bar.place_forget()

    def _layout(self, narrow):
        if narrow == self._narrow:
            return
        self._narrow = narrow
        self.nav.grid_forget()
        self.main.grid_forget()
        self.logo.pack_forget()
        self.brand.pack_forget()
        self.date.pack_forget()
        self.sub.pack_forget()
        self.clock.configure(font=theme.font(18 if narrow else 22))
        if narrow:
            self.logo_image = ctk.CTkImage(
                light_image=self.logo_source, dark_image=self.dark_logo_source, size=(76, 45))
            self.brand.configure(image=self.logo_image, width=76, height=45)
            self.brand.pack(side="left", before=self.titles, padx=(0, 8))
            self.nav.configure(width=10, height=72)
            self.main.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=16)
            self.nav.grid(row=1, column=0, columnspan=2, sticky="ew")
        else:
            self.logo_image = ctk.CTkImage(
                light_image=self.logo_source, dark_image=self.dark_logo_source, size=(112, 67))
            self.brand.configure(image=self.logo_image, width=112, height=67)
            self.brand.pack(side="left", before=self.titles, padx=(0, 12))
            self.nav.configure(width=68, height=10)
            self.nav.grid(row=0, column=0, rowspan=2, sticky="ns")
            self.main.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=24)
            self.logo.pack(fill="x", pady=(20, 14))
            self.date.pack(fill="x")
            self.sub.pack(fill="x")
        self._build_nav(narrow)

    def _on_configure(self, event):
        if event.widget is self:
            narrow = event.width / theme.scale(self) < self.NARROW
            self._layout(narrow)

    def show(self, name):
        self.current = name
        for n, (holder, _) in self.pages.items():
            if n == name:
                holder.grid()
            else:
                holder.grid_remove()
        screen = self.pages[name][1]
        self._mark_active()
        self.heading.configure(text=name)
        refresh = getattr(screen, "refresh", None)
        if refresh:
            refresh()

    def _toggle_mode(self):
        ctk.set_appearance_mode("light" if ctk.get_appearance_mode() == "Dark" else "dark")
        self.show(self.current)

    def _apply_native_titlebar(self):
        if not hasattr(ctypes, "windll"):
            return
        get_parent = ctypes.windll.user32.GetParent
        get_parent.argtypes = (ctypes.c_void_p,)
        get_parent.restype = ctypes.c_void_p
        hwnd = get_parent(self.winfo_id())
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint)
        for attribute, color in ((35, 0x356A0F), (34, 0x356A0F), (36, 0xFFFFFF)):
            value = ctypes.c_int(color)
            set_attribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))

    def _tick(self):
        now = datetime.now()
        self.clock.configure(text=now.strftime("%H:%M:%S"))
        self.date.configure(text=now.strftime("%a %d %b %Y"))
        self.after(1000, self._tick)
