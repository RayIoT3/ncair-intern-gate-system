"""Gate screen: check-in / check-out with ID feedback and recent activity.

The screen holds no business rules. It calls a service object with:
    service.gate_candidates(query) -> [(id, name, programme, serial, inside, card_id)]
    service.check_in(text)    -> GateResult
    service.check_out(text)   -> GateResult
    service.recent(limit)     -> list[Movement]   (newest first)
The production app supplies its real service through the application entry point.
"""
from typing import List

import customtkinter as ctk

from services.gate_contract import GateCandidate, GateResult, GateScreenService, Movement
import theme


class GateScreen(ctk.CTkFrame):
    NARROW = 656   # below this width the two cards stack (mockup: two 320px columns + 16px gap)
    MAX_SUGGESTIONS = 3

    def __init__(self, parent, service: GateScreenService):
        super().__init__(parent, fg_color="transparent")
        self.service = service
        self._stacked = None
        self._hint_wrap = self._msg_wrap = None
        self.candidates: List[GateCandidate] = []
        self.suggestion_rows = {}
        self.selected_id = None
        self._build_form()
        self._build_activity()
        self._refresh_activity()
        self.bind("<Configure>", self._on_resize)

    # ---- widgets -------------------------------------------------------
    def _build_form(self):
        self.form = theme.card(self)
        theme.label(self.form, "Check-in / check-out", 16, True).pack(fill="x", padx=20, pady=(16, 10))
        theme.label(self.form, "Find an intern", 13, True).pack(fill="x", padx=20)
        self.entry = theme.entry(self.form, "Roster number, name, or intern ID")
        self.entry.pack(fill="x", padx=20, pady=(6, 0))
        self.entry.bind("<KeyRelease>", self._search)
        self.entry.bind("<Return>", self._select_single_match)
        self.hint = theme.label(self.form, "Type to see matching interns.", 13, color=theme.MUTED)
        self.hint.pack(fill="x", padx=20, pady=(6, 0))

        self.matches = ctk.CTkFrame(self.form, width=1, height=0, fg_color="transparent")
        self.matches.pack_propagate(True)
        self.matches.pack(fill="x", padx=20, pady=(6, 0))
        self.action_row = ctk.CTkFrame(self.form, fg_color="transparent")
        self.action_row.pack(fill="x", padx=20, pady=12)
        self.action_row.columnconfigure((0, 1), weight=1, uniform="gate-actions")
        self.check_in_button = theme.primary_button(
            self.action_row, "Check in", lambda: self._act_selected("check_in")
        )
        self.check_in_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.check_out_button = theme.secondary_button(
            self.action_row, "Check out", lambda: self._act_selected("check_out")
        )
        self.check_out_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.check_out_unreturned_button = theme.secondary_button(
            self.action_row,
            "Check out \u00b7 card not returned",
            lambda: self._act_selected("check_out_card_not_returned"),
        )
        self.check_out_unreturned_button.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        self._set_actions_enabled(False, False)

        self.msg = ctk.CTkFrame(self.form, corner_radius=theme.RADIUS)
        self.msg.pack(fill="x", padx=20, pady=(0, 20))
        self.msg_title = theme.label(self.msg, "", 17, True)
        self.msg_title.pack(fill="x", padx=16, pady=(10, 0))
        self.msg_body = theme.label(self.msg, "", 14, wraplength=300)
        self.msg_body.pack(fill="x", padx=16, pady=(2, 10))
        self._say("idle", "Ready", "Search by roster number, name, full ID, or the last 3 ID digits.")

    def _build_activity(self):
        self.activity = theme.card(self)
        theme.label(self.activity, "Recent activity", 16, True).pack(fill="x", padx=20, pady=(20, 6))
        self.rows = ctk.CTkFrame(self.activity, fg_color="transparent")
        self.rows.pack(fill="x", padx=20, pady=(0, 14))

    # ---- behaviour -----------------------------------------------------
    def _search(self, _event=None):
        query = self.entry.get().strip()
        self._clear_selection()

        if query:
            self._say("idle", "Search results", "Select the correct intern to enable their gate action.")

        if not query:
            self.hint.configure(text="Type to see matching interns.")
            return

        if not query.isdigit() and len(query) < 2:
            self.hint.configure(text="Type at least 2 characters to search.")
            return

        self.candidates = self.service.gate_candidates(query)
        if not self.candidates:
            hint = ("No roster number matches. Enter all 3 ending ID digits to search by ID."
                    if query.isdigit() and len(query) < 3 else
                    "No matching interns. Try a roster number, name, full ID, or last 3 ID digits.")
            self.hint.configure(text=hint)
            return

        visible = self.candidates[:self.MAX_SUGGESTIONS]
        if len(self.candidates) > len(visible):
            self.hint.configure(text=f"Showing {len(visible)} of {len(self.candidates)} matches \u00b7 refine your search")
        else:
            count = len(self.candidates)
            noun = "match" if count == 1 else "matches"
            self.hint.configure(text=f"{count} {noun} \u00b7 select the correct intern")

        for candidate in visible:
            intern_id, name, programme, serial_number, inside, card_id = candidate
            state = "Inside" if inside else "Outside"
            card = f" \u00b7 card #{card_id}" if card_id else ""
            roster_number = f"Roster no. {serial_number} \u00b7 " if serial_number else ""

            row = ctk.CTkFrame(
                self.matches,
                fg_color=theme.CHIP,
                corner_radius=theme.RADIUS,
            )
            row.pack(fill="x", pady=2)

            # Keep each line in its own left-anchored widget; multiline button text
            # is centered line-by-line by Tk and gives the result uneven indentation.
            name_button = ctk.CTkButton(
                row,
                text=f"{name}  \u00b7  {intern_id}",
                anchor="w",
                height=28,
                corner_radius=theme.RADIUS,
                font=theme.font(13),
                text_color=theme.TEXT,
                fg_color="transparent",
                hover_color=theme.BORDER,
                command=lambda iid=intern_id: self._select(iid),
            )
            name_button.pack(fill="x", padx=3, pady=(3, 0))

            details = theme.label(
                row,
                f"{roster_number}{programme} \u00b7 {state}{card}",
                13,
                color=theme.TEXT,
                height=22,
            )
            details.pack(fill="x", padx=11, pady=(0, 3))
            details.bind("<Button-1>", lambda _event, iid=intern_id: self._select(iid))
            row.bind("<Button-1>", lambda _event, iid=intern_id: self._select(iid))

            self.suggestion_rows[intern_id] = (row, name_button, details)

    def _clear_selection(self, reset_message=True):
        self.selected_id = None
        self.candidates = []
        self.suggestion_rows = {}
        self._set_actions_enabled(False, False)
        for widget in self.matches.winfo_children():
            widget.destroy()
        self.matches.configure(height=0)
        if reset_message:
            self._say("idle", "Ready", "Search by roster number, name, full ID, or the last 3 ID digits.")

    def _select_single_match(self, _event=None):
        if len(self.candidates) == 1:
            self._select(self.candidates[0][0])

    def _select(self, intern_id):
        selected = next((row for row in self.candidates if row[0] == intern_id), None)
        if selected is None:
            return
        self.selected_id = intern_id
        _, name, _, _, inside, _ = selected
        self._set_actions_enabled(not inside, inside)
        for candidate_id, (row, name_button, details) in self.suggestion_rows.items():
            selected_style = candidate_id == intern_id
            row.configure(fg_color=theme.PRIMARY if selected_style else theme.CHIP)
            name_button.configure(
                text_color="#FFFFFF" if selected_style else theme.TEXT,
                hover_color=theme.PRIMARY_HOVER if selected_style else theme.BORDER,
            )
            details.configure(text_color="#FFFFFF" if selected_style else theme.TEXT)
        self._say("idle", "Intern selected", f"{name} \u00b7 {intern_id} \u00b7 "
                  f"{'currently inside' if inside else 'currently outside'}")

    def _set_actions_enabled(self, check_in, check_out):
        actions = (
            (self.check_in_button, check_in),
            (self.check_out_button, check_out),
            (self.check_out_unreturned_button, check_out),
        )
        for button, enabled in actions:
            button.configure(state="normal" if enabled else "disabled",
                             fg_color=theme.PRIMARY if enabled else theme.CHIP,
                             hover_color=theme.PRIMARY_HOVER if enabled else theme.CHIP,
                             text_color="#FFFFFF" if enabled else theme.MUTED,
                             text_color_disabled=theme.MUTED)

    def _act_selected(self, action):
        if self.selected_id is None:
            return
        selected = next((row for row in self.candidates if row[0] == self.selected_id), None)
        if selected is None:
            return
        current = next((row for row in self.service.gate_candidates(self.selected_id)
                        if row[0] == self.selected_id), None)
        if current is None:
            self._say("er", "Intern not found", "Search again before recording gate activity.")
            self._search()
            return
        if action == "check_in":
            result = self.service.check_in(self.selected_id)
        elif action == "check_out":
            result = self.service.check_out(self.selected_id)
        else:
            result = self.service.check_out_card_not_returned(self.selected_id)
        self._say(result.kind, result.title, result.detail)
        completed = result.kind == "ok" or (
            action == "check_out_card_not_returned"
            and result.title == "Checked out, card not returned"
        )
        if completed:  # Keep the ID on errors so it can be corrected.
            self.entry.delete(0, "end")
            self._clear_selection(reset_message=False)
            self.hint.configure(text="Type to see matching interns.")
            self._refresh_activity()

    def _say(self, kind, title, detail):
        bg, fg = theme.STATUS[kind]
        self.msg.configure(fg_color=bg)
        self.msg_title.configure(text=title, text_color=fg)
        self.msg_body.configure(text=detail, text_color=fg)

    def _refresh_activity(self):
        for w in self.rows.winfo_children():
            w.destroy()
        moves = self.service.recent(6)
        if not moves:
            theme.label(self.rows, "No movements yet.", 14, color=theme.MUTED).pack(fill="x", pady=10)
        for i, m in enumerate(moves):
            if i:
                ctk.CTkFrame(self.rows, height=2, corner_radius=0, fg_color=theme.BORDER).pack(fill="x")
            row = ctk.CTkFrame(self.rows, fg_color="transparent")
            row.pack(fill="x", pady=10)
            theme.pill(row, m.direction, "In" if m.direction == "in" else "Out").pack(side="left", anchor="n")
            text = ctk.CTkFrame(row, fg_color="transparent")
            text.pack(side="left", padx=(12, 0))
            theme.label(text, m.name, 14, True).pack(fill="x")
            theme.label(text, f"{m.intern_id} \u00b7 {m.at}", 13, color=theme.MUTED).pack(fill="x")

    def _on_resize(self, event):
        w = event.width / theme.scale(self)      # pixels -> the scaled units every size here is written in
        stacked = w < self.NARROW
        if stacked != self._stacked:
            self._stacked = stacked
            self.form.grid_forget()
            self.activity.grid_forget()
            group = "" if stacked else "c"
            self.columnconfigure(0, weight=1, uniform=group)
            self.columnconfigure(1, weight=0 if stacked else 1, uniform=group)
            if stacked:
                self.form.grid(row=0, column=0, sticky="new")
                self.activity.grid(row=1, column=0, sticky="new", pady=(16, 0))
            else:
                self.form.grid(row=0, column=0, sticky="new", padx=(0, 8))
                self.activity.grid(row=0, column=1, sticky="new", padx=(8, 0))
        card_w = w if stacked else (w - 16) / 2
        hint_wrap = max(160, int(card_w - 40))
        msg_wrap = max(160, int(card_w - 72))
        if hint_wrap != self._hint_wrap:
            self._hint_wrap = hint_wrap
            self.hint.configure(wraplength=hint_wrap)
        if msg_wrap != self._msg_wrap:
            self._msg_wrap = msg_wrap
            self.msg_body.configure(wraplength=msg_wrap)
