"""Guest-card inventory with safe return and missing-card actions."""
from tkinter import messagebox, ttk
from types import SimpleNamespace

import customtkinter as ctk

import theme

COLUMNS = (("card", "Card", 80), ("status", "Status", 120),
           ("holder", "Current / last holder", 190), ("name", "Intern", 180),
           ("assigned", "Issued at", 150))


class CardsScreen(ctk.CTkFrame):
    def __init__(self, parent, service):
        super().__init__(parent, fg_color="transparent")
        self.service = service
        self._narrow = None

        box = theme.card(self)
        box.pack(fill="both", expand=True)
        theme.label(box, "Guest cards", 16, True).pack(fill="x", padx=20, pady=(20, 4))
        self.description = theme.label(
            box, "Review card status, record returns, or flag a card that cannot be found.",
            13, color=theme.MUTED, wraplength=600)
        self.description.pack(fill="x", padx=20, pady=(0, 14))

        actions = ctk.CTkFrame(box, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 12))
        self.actions = actions
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=0)
        self.card_input = theme.entry(actions, "Card number, e.g. 047")
        self.card_input.grid(row=0, column=0, sticky="ew")
        self.card_input.bind("<Return>", lambda _event: self._return_card())
        self.return_button = theme.primary_button(actions, "Record return", self._return_card)
        self.missing_button = theme.secondary_button(actions, "Mark missing", self._mark_missing)
        self.bind("<Configure>", self._on_resize)

        self.message_box = ctk.CTkFrame(box, fg_color="transparent", corner_radius=theme.RADIUS)
        self.message_box.pack(fill="x", padx=20, pady=(0, 12))
        self.message = theme.label(self.message_box, "", 13, wraplength=700)
        self.message.pack(fill="x", padx=12, pady=8)

        wrap = ctk.CTkFrame(box, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=(20, 8), pady=(0, 20))
        self.tree = ttk.Treeview(wrap, style="Gate.Treeview", show="headings", selectmode="browse",
                                 columns=[column[0] for column in COLUMNS])
        scale = theme.scale(self.tree)
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title, anchor="w")
            self.tree.column(key, width=round(width * scale), anchor="w", stretch=key in ("name", "holder"))
        scrollbar = ctk.CTkScrollbar(wrap, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select_card)

    def _selected_card(self):
        value = self.card_input.get().strip()
        if value:
            return value
        selected = self.tree.selection()
        return self.tree.item(selected[0], "values")[0] if selected else ""

    def _select_card(self, _event=None):
        selected = self.tree.selection()
        if selected:
            self.card_input.delete(0, "end")
            self.card_input.insert(0, self.tree.item(selected[0], "values")[0])

    def _return_card(self):
        card_id = self._selected_card()
        if not card_id:
            self._show_result(SimpleNamespace(
                kind="er", title="Select a card", detail="Choose a row or enter a card number."
            ))
            return
        self._show_result(self.service.return_card(card_id))

    def _mark_missing(self):
        card_id = self._selected_card()
        if not card_id:
            self._show_result(SimpleNamespace(
                kind="er", title="Select a card",
                detail="Choose an issued card or enter its number."
            ))
            return
        if not messagebox.askyesno(
                "Mark card missing", f"Mark guest card {card_id} as missing? It will remain unavailable.",
                parent=self.winfo_toplevel()):
            return
        self._show_result(self.service.mark_card_missing(card_id))

    def _show_result(self, response):
        bg, fg = theme.STATUS[response.kind]
        self.message_box.configure(fg_color=bg)
        self.message.configure(text=f"{response.title}: {response.detail}", text_color=fg)
        self.refresh()

    def _on_resize(self, event):
        width = event.width / theme.scale(self)
        narrow = width < 640
        self.description.configure(wraplength=max(180, round(width - 48)))
        if narrow == self._narrow:
            return
        self._narrow = narrow
        self.return_button.grid_forget()
        self.missing_button.grid_forget()
        self.card_input.grid_forget()
        if narrow:
            self.actions.columnconfigure(1, weight=1, uniform="card-actions")
            self.card_input.grid(row=0, column=0, columnspan=2, sticky="ew")
            self.return_button.grid(row=1, column=0, sticky="ew", pady=(8, 0))
            self.missing_button.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        else:
            self.actions.columnconfigure(1, weight=0, uniform="")
            self.return_button.grid(row=0, column=1, padx=(8, 0))
            self.missing_button.grid(row=0, column=2, padx=(8, 0))
            self.card_input.grid(row=0, column=0, sticky="ew")
        columns = ("card", "status", "holder") if narrow else tuple(c[0] for c in COLUMNS)
        self.tree.configure(displaycolumns=columns)
        scale = theme.scale(self.tree)
        widths = (("card", 52), ("status", 82), ("holder", 120)) if narrow else \
            (("card", 80), ("status", 120), ("holder", 190), ("name", 180), ("assigned", 150))
        for key, width in widths:
            self.tree.column(key, width=round(width * scale),
                             stretch=key == "holder" if narrow else key in ("name", "holder"))

    def refresh(self):
        theme.style_treeview(self.tree)
        self.tree.delete(*self.tree.get_children())
        for card_id, status, holder_id, holder_name, assigned_at in self.service.card_report():
            self.tree.insert("", "end", values=(
                card_id, status.title(), holder_id or "\u2014", holder_name or "\u2014",
                assigned_at or "\u2014"))