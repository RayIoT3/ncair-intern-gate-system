"""Dashboard: attendance KPIs, occupancy, weather and a compact guest-card summary."""
import customtkinter as ctk

import theme


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent, service):
        super().__init__(parent, fg_color="transparent")
        self.service, self._layout, self._weather_stacked = service, None, None

        self.kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        self.kpi_row.pack(fill="x")
        self.kpis = [self._kpi(name) for name in
                     ("Inside", "Outside", "Cards available", "Cards issued")]

        self.weather_card = theme.card(self)
        self.weather_card.pack(fill="x", pady=(0, 16))
        self.weather_title = theme.label(self.weather_card, "Weather \u00b7 Abuja", 13, True, color=theme.MUTED)
        self.weather = theme.label(self.weather_card, "Loading live weather\u2026", 20, True)
        self.weather_note = theme.label(
            self.weather_card, "Live data provided by Open-Meteo.", 13, color=theme.MUTED)

        self.lower = ctk.CTkFrame(self, fg_color="transparent")
        self.lower.pack(fill="x")

        self.occ = theme.card(self.lower)
        theme.label(self.occ, "Building occupancy", 16, True).pack(fill="x", padx=20, pady=(20, 14))
        self.bar = ctk.CTkProgressBar(self.occ, height=10, corner_radius=5,
                                      fg_color=theme.CHIP, progress_color=theme.PRIMARY)
        self.bar.pack(fill="x", padx=20)
        self.occ_text = theme.label(self.occ, "", 13, color=theme.MUTED)
        self.occ_text.pack(fill="x", padx=20, pady=(8, 0))

        self.cardbox = theme.card(self.lower)
        theme.label(self.cardbox, "Guest card pool", 16, True).pack(fill="x", padx=20, pady=(20, 10))
        self.cards_available = theme.label(self.cardbox, "0 cards available", 30, True)
        self.cards_available.pack(fill="x", padx=20)
        self.cards_bar = ctk.CTkProgressBar(self.cardbox, height=10, corner_radius=5,
                                            fg_color=theme.CHIP, progress_color=theme.PRIMARY)
        self.cards_bar.pack(fill="x", padx=20, pady=(12, 8))
        self.cards_summary = theme.label(self.cardbox, "", 13, color=theme.MUTED)
        self.cards_summary.pack(fill="x", padx=20, pady=(0, 20))
        self.bind("<Configure>", self._on_resize)

    def _kpi(self, name):
        c = theme.card(self.kpi_row)
        top = ctk.CTkFrame(c, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 0))
        num = theme.label(top, "0", 38, True)
        num.pack(side="left")
        theme.label(c, name, 14, True).pack(fill="x", padx=20)
        sub = theme.label(c, "", 13, color=theme.MUTED)
        sub.pack(fill="x", padx=20, pady=(0, 16))
        return c, num, sub

    def _on_resize(self, e):
        w = e.width / theme.scale(self)                       # pixels -> scaled units
        kc = max(1, min(4, int(w + 16) // 166))               # mockup: auto-fit, 150px min, 16px gaps
        lc = 2 if w >= 656 else 1
        previous = self._layout
        if (kc, lc) == previous:
            return
        self._layout = (kc, lc)
        if previous is None or kc != previous[0]:
            theme.flow(self.kpi_row, [k[0] for k in self.kpis], kc)
        if previous is None or lc != previous[1]:
            theme.flow(self.lower, [self.occ, self.cardbox], lc)

        stacked = w < 656
        if previous is None or lc != previous[1]:
            if lc == 2:
                self.lower.rowconfigure(0, weight=1, uniform="dashboard-cards")
                height = round(max(self.occ.winfo_reqheight(), self.cardbox.winfo_reqheight())
                               / theme.scale(self))
                for card in (self.occ, self.cardbox):
                    card.grid_propagate(False)
                    card.configure(height=height)
                    card.grid_configure(sticky="nsew")
            else:
                self.lower.rowconfigure(0, weight=0, uniform="")
                self.lower.rowconfigure(1, weight=0, uniform="")
                for card in (self.occ, self.cardbox):
                    card.grid_propagate(True)
                    card.grid_configure(sticky="new")

        if stacked != self._weather_stacked:
            self._weather_stacked = stacked
            for widget in (self.weather_title, self.weather, self.weather_note):
                widget.grid_forget()
            for column in range(3):
                self.weather_card.columnconfigure(column, weight=0)
            if stacked:
                self.weather_title.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 0))
                self.weather.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))
                self.weather_note.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 12))
            else:
                self.weather_card.columnconfigure((1, 2), weight=1)
                self.weather_title.grid(row=0, column=0, sticky="w", padx=(16, 12), pady=12)
                self.weather.grid(row=0, column=1, sticky="w", padx=12, pady=12)
                self.weather_note.grid(row=0, column=2, sticky="e", padx=16, pady=12)

    def _show_weather(self):
        """Live weather from service.weather(); it never blocks. Re-check shortly while it is loading."""
        w = self.service.weather()
        self.weather.configure(text=w.text)
        self.weather_note.configure(text=w.note)
        if w.loading:
            self.after(1500, self._show_weather)

    def refresh(self):
        self._show_weather()
        s = self.service.stats()
        vals = [(s["inside"], "in the building"), (s["outside"], "not checked in"),
                (s["free"], f"of {s['cards']} guest cards"), (s["issued"], "with interns now")]
        for (_, num, sub), (v, text) in zip(self.kpis, vals):
            num.configure(text=str(v))
            sub.configure(text=text)
        self.bar.set(s["inside"] / s["total"])
        self.occ_text.configure(text=f"{s['inside']} of {s['total']} interns are inside")
        noun = "card" if s["free"] == 1 else "cards"
        self.cards_available.configure(text=f"{s['free']} {noun} available")
        self.cards_bar.set(s["issued"] / s["cards"] if s["cards"] else 0)
        available_rate = s["free"] / s["cards"] if s["cards"] else 0
        self.cards_summary.configure(
            text=f"{s['issued']} issued of {s['cards']} cards \u00b7 {available_rate:.0%} available")
