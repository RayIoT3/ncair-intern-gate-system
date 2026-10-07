"""Interns: search box, All / Inside / Outside filter and the intern table."""
from tkinter import ttk

import customtkinter as ctk

import theme

COLUMNS = (("serial", "No.", 60), ("id", "ID", 130), ("intern", "Intern", 200),
           ("type", "Type", 80), ("status", "Status", 90), ("card", "Card", 70),
           ("since", "Since", 80))
FORM_FIELDS = (("intern_id", "Intern ID", "NC-SI-000001"),
               ("serial_number", "Roster number (optional)", "Printed serial number"),
               ("name", "Full name", "Intern full name"),
               ("department", "Department", "Department or programme"),
               ("phone", "Phone (optional)", "08012345678"),
               ("email", "Email (optional)", "name@example.com"))


class InternsScreen(ctk.CTkFrame):
    def __init__(self, parent, service):
        super().__init__(parent, fg_color="transparent")
        self.service, self.status = service, "all"
        self._narrow = self._compact_toolbar = None
        self._search_job = None
        box = theme.card(self)
        box.pack(fill="both", expand=True)

        bar = ctk.CTkFrame(box, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=(20, 16))
        bar.columnconfigure(0, weight=1)
        self.search = theme.entry(bar, "Search roster no., name or ID")
        self.search.grid(row=0, column=0, sticky="ew")
        self.search.bind("<KeyRelease>", self._queue_search_refresh)
        self.tabs_frame = ctk.CTkFrame(bar, fg_color="transparent")
        self.tabs = {}
        for key, text in (("all", "All"), ("in", "Inside"), ("out", "Outside")):
            b = theme.secondary_button(self.tabs_frame, text, lambda k=key: self._filter(k))
            b.configure(width=80, height=44)
            self.tabs[key] = b
        self.actions = ctk.CTkFrame(self.tabs_frame, fg_color="transparent")
        self.register_button = theme.primary_button(self.actions, "Register intern", self._open_registration)
        self.serial_button = theme.secondary_button(self.actions, "Set roster no.", self._open_serial_editor)
        self.serial_button.configure(state="disabled")
        self.tabs_frame.columnconfigure((0, 1, 2), weight=1, uniform="intern-filters")
        self.actions.columnconfigure((0, 1), weight=1, uniform="intern-actions")
        self.register_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.serial_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        wrap = ctk.CTkFrame(box, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.table_wrap = wrap
        self.tree = ttk.Treeview(wrap, style="Gate.Treeview", show="headings", selectmode="browse",
                                 columns=[c[0] for c in COLUMNS])
        k = theme.scale(self.tree)                       # ttk column widths are real pixels
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title, anchor="w")
            self.tree.column(key, width=round(width * k), anchor="w", stretch=key == "intern")
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        sb = ctk.CTkScrollbar(wrap, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        wrap.bind("<Configure>", lambda _event: self._size_columns() if not self._narrow else None)
        self.bind("<Configure>", self._on_resize)

    def _open_registration(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Register intern")
        display_scale = theme.scale(self)
        available_width = round(self.winfo_screenwidth() / display_scale) - 32
        available_height = round(self.winfo_screenheight() / display_scale) - 80
        width = min(440, max(320, available_width))
        height = min(680, max(440, available_height))
        dialog.geometry(f"{width}x{height}")
        dialog.minsize(min(340, width), min(440, height))
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        box = theme.card(dialog)
        box.pack(fill="both", expand=True, padx=16, pady=16)
        theme.label(box, "Register intern", 20, True).pack(fill="x", padx=20, pady=(20, 4))
        theme.label(box, "Add the intern's details to the gate roster.", 13,
                    color=theme.MUTED).pack(fill="x", padx=20, pady=(0, 16))

        form = ctk.CTkScrollableFrame(box, fg_color="transparent", corner_radius=0)
        form.pack(fill="both", expand=True)
        fields = {}
        for key, label, placeholder in FORM_FIELDS:
            theme.label(form, label, 13, True).pack(fill="x", padx=20, pady=(7, 0))
            field = theme.entry(form, placeholder)
            field.pack(fill="x", padx=20, pady=(5, 0))
            fields[key] = field

        result_box = ctk.CTkFrame(box, fg_color="transparent", corner_radius=theme.RADIUS)
        result_box.pack(fill="x", padx=20, pady=(12, 0))
        result = theme.label(result_box, "", 13, wraplength=360)
        result.pack(fill="x", padx=10, pady=8)

        def submit():
            response = self.service.register_intern(
                fields["intern_id"].get(), fields["name"].get(), fields["department"].get(),
                fields["phone"].get(), fields["email"].get(), fields["serial_number"].get())
            bg, fg = theme.STATUS[response.kind]
            result_box.configure(fg_color=bg)
            result.configure(text=f"{response.title}: {response.detail}", text_color=fg)
            if response.kind == "ok":
                self.refresh()
                dialog.after(900, dialog.destroy)

        buttons = ctk.CTkFrame(box, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=16)
        buttons.columnconfigure((0, 1), weight=1, uniform="registration")
        theme.secondary_button(buttons, "Cancel", dialog.destroy).grid(
            row=0, column=0, sticky="ew", padx=(0, 5))
        theme.primary_button(buttons, "Register", submit).grid(
            row=0, column=1, sticky="ew", padx=(5, 0))
        fields["intern_id"].focus_set()

    def _selection_changed(self, _event=None):
        selection = self.tree.selection()
        has_intern = bool(selection and self.tree.item(selection[0], "values")[1])
        self.serial_button.configure(
            state="normal" if has_intern else "disabled")

    def _open_serial_editor(self):
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        if not values[1]:
            return
        intern_id, name, current = values[1], values[2], values[0]
        dialog = ctk.CTkToplevel(self)
        dialog.title("Set roster number")
        dialog.geometry("380x250")
        dialog.minsize(340, 220)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        box = theme.card(dialog)
        box.pack(fill="both", expand=True, padx=16, pady=16)
        theme.label(box, "Set roster number", 18, True).pack(
            fill="x", padx=20, pady=(18, 4))
        theme.label(box, f"{name} \u00b7 {intern_id}", 13, color=theme.MUTED).pack(
            fill="x", padx=20, pady=(0, 12))
        field = theme.entry(box, "Printed serial number")
        field.pack(fill="x", padx=20)
        if current != "\u2014":
            field.insert(0, current)
        result = theme.label(box, "", 13, wraplength=310)
        result.pack(fill="x", padx=20, pady=(8, 0))

        def submit():
            response = self.service.set_serial_number(intern_id, field.get())
            _, fg = theme.STATUS[response.kind]
            result.configure(text=f"{response.title}: {response.detail}", text_color=fg)
            if response.kind == "ok":
                self.refresh()
                dialog.after(700, dialog.destroy)

        buttons = ctk.CTkFrame(box, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=12)
        buttons.columnconfigure((0, 1), weight=1, uniform="serial")
        theme.secondary_button(buttons, "Cancel", dialog.destroy).grid(
            row=0, column=0, sticky="ew", padx=(0, 5))
        theme.primary_button(buttons, "Save", submit).grid(
            row=0, column=1, sticky="ew", padx=(5, 0))
        field.focus_set()

    def _filter(self, key):
        self.status = key
        self.refresh()

    def _queue_search_refresh(self, _event=None):
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(120, self._run_search_refresh)

    def _run_search_refresh(self):
        self._search_job = None
        self.refresh()

    def _on_resize(self, e):
        width = e.width / theme.scale(self)                    # pixels -> scaled units
        narrow = width < 640
        compact_toolbar = width < 900
        if narrow == self._narrow and compact_toolbar == self._compact_toolbar:
            self._size_columns()
            return
        self._narrow = narrow
        self._compact_toolbar = compact_toolbar
        self._layout_toolbar(compact_toolbar)
        self.tree.configure(displaycolumns=("serial", "intern", "status", "card")
                            if narrow else [c[0] for c in COLUMNS])
        self._size_columns()

    def _layout_toolbar(self, compact):
        self.tabs_frame.grid_forget()
        for button in self.tabs.values():
            button.grid_forget()
        self.actions.grid_forget()
        if compact:
            self.tabs_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
            for index, button in enumerate(self.tabs.values()):
                button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 3,
                                                                    0 if index == 2 else 3))
            self.actions.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
            self.register_button.configure(text="Register")
            self.serial_button.configure(text="Set no.")
        else:
            self.tabs_frame.grid(row=0, column=1, padx=(12, 0))
            for index, button in enumerate(self.tabs.values()):
                button.grid(row=0, column=index, sticky="ew", padx=(0, 4))
            self.actions.grid(row=0, column=3, sticky="ew", padx=(4, 0))
            self.register_button.configure(text="Register")
            self.serial_button.configure(text="Set roster no.")

    def _size_columns(self):
        scale = theme.scale(self.tree)
        width = self.table_wrap.winfo_width() - round(18 * scale)
        if width <= 1:
            return
        fractions = {"serial": 0.08, "id": 0.19, "intern": 0.24, "type": 0.10,
                     "status": 0.15, "card": 0.09, "since": 0.15}
        for key, fraction in fractions.items():
            self.tree.column(key, width=max(round(60 * scale), round(width * fraction)))

    def refresh(self):
        if self._search_job is not None:
            self.after_cancel(self._search_job)
            self._search_job = None
        theme.style_treeview(self.tree)
        for key, b in self.tabs.items():
            on = key == self.status
            b.configure(fg_color=theme.PRIMARY if on else theme.CHIP, text_color="#FFFFFF" if on else theme.TEXT,
                        hover_color=theme.PRIMARY_HOVER if on else theme.BORDER)
        self.tree.delete(*self.tree.get_children())
        self.serial_button.configure(state="disabled")
        rows = self.service.roster(self.search.get(), self.status)
        for iid, name, kind, serial, inside, card, since in rows:
            self.tree.insert("", "end", tags=("in" if inside else "out",), values=(
                serial or "\u2014", iid, name, kind, "Inside" if inside else "Outside",
                f"#{card}" if card else "\u2014", since))
        if not rows:
            self.tree.insert("", "end", values=("", "", "No interns match.", "", "", "", ""))
