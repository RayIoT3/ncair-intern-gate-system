"""AI Report: ask questions in plain language and preview the daily memo."""
import logging
import threading
from tkinter import TclError

import customtkinter as ctk

import theme

log = logging.getLogger("gate")


class AIScreen(ctk.CTkFrame):
    def __init__(self, parent, service):
        super().__init__(parent, fg_color="transparent")
        self.service, self._stacked, self._chip_cols, self._layout_width = service, None, None, None
        self._height_job = None
        self._wrap, self._note_wrap, self.bubbles = 300, None, []
        self._request_pending = False

        self.chat_card = theme.card(self)
        theme.label(self.chat_card, "Ask the system", 18, True).pack(fill="x", padx=20, pady=(20, 2))
        theme.label(self.chat_card, "Get answers from attendance and card records.", 12,
                    color=theme.MUTED).pack(fill="x", padx=20, pady=(0, 10))
        self.chat = ctk.CTkScrollableFrame(self.chat_card, height=230, fg_color="transparent")
        self.chat.pack(fill="both", expand=True, padx=12)
        self._bubble("Ask about a card, who is inside, or today's attendance.", user=False)
        self.chips = ctk.CTkFrame(self.chat_card, fg_color="transparent")
        self.chips.pack(fill="x", padx=20, pady=12)
        self.chip_w = [
            ctk.CTkButton(
                self.chips,
                text=question,
                command=lambda q=question: self.ask(q),
                height=36,
                corner_radius=18,
                border_width=1,
                border_color=theme.BORDER,
                fg_color="transparent",
                hover_color=theme.CHIP,
                text_color=theme.TEXT,
                font=theme.font(13),
            )
            for question in ("Who has card 4?", "Who is inside?", "Write the memo")
        ]
        row = ctk.CTkFrame(self.chat_card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 20))
        row.columnconfigure(0, weight=1)
        self.input = theme.entry(row, "e.g. Who has card 7?")
        self.input.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.input.bind("<Return>", lambda e: self.ask(self.input.get()))
        self.ask_button = theme.primary_button(
            row, "Ask", lambda: self.ask(self.input.get())
        )
        self.ask_button.grid(row=0, column=1)

        self.memo_card = theme.card(self)
        theme.label(self.memo_card, "Daily attendance memo", 18, True).pack(
            fill="x", padx=20, pady=(20, 2))
        theme.label(self.memo_card, "A concise snapshot of today's gate activity.", 12,
                    color=theme.MUTED).pack(fill="x", padx=20, pady=(0, 10))
        self.memo_box = ctk.CTkTextbox(self.memo_card, height=170, corner_radius=theme.RADIUS, wrap="word",
                                       fg_color=theme.CHIP, text_color=theme.TEXT, font=theme.font(13))
        self.memo_box.pack(fill="both", expand=True, padx=20)
        theme.primary_button(self.memo_card, "Generate memo", self.refresh).pack(fill="x", padx=20, pady=14)
        self.note = theme.label(
            self.memo_card,
            "Answers use this app's records. Gemini assists when configured.",
            13,
            color=theme.MUTED,
        )
        self.note.pack(fill="x", padx=20, pady=(0, 20))
        self.bind("<Configure>", self._on_resize)

    def _bubble(self, text, user):
        b = ctk.CTkFrame(self.chat, corner_radius=12, fg_color=theme.PRIMARY if user else theme.CHIP)
        lbl = theme.label(b, text, 14, color="#FFFFFF" if user else theme.TEXT, wraplength=self._wrap)
        lbl.pack(padx=14, pady=10)
        self.bubbles.append(lbl)
        b.pack(anchor="e" if user else "w", padx=4, pady=4)
        self.after(60, lambda: self.chat._parent_canvas.yview_moveto(1.0))
        return lbl

    def ask(self, text):
        """Run the potentially slow records/AI lookup without blocking Tk's event loop."""
        text = text.strip()
        if not text or self._request_pending:
            return

        self._set_request_pending(True)
        self._bubble(text, user=True)
        answer_bubble = self._bubble("Checking the records\u2026", user=False)
        self.input.delete(0, "end")
        worker = threading.Thread(
            target=self._ask_in_background,
            args=(text, answer_bubble),
            daemon=True,
        )
        try:
            worker.start()
        except RuntimeError:
            log.exception("Could not start the AI request")
            self._finish_answer(
                answer_bubble,
                "The request could not be started. Please try again.",
            )

    def _ask_in_background(self, question, answer_bubble):
        """Ask the backend on a worker thread; all widget updates happen via `after`."""
        try:
            answer = self.service.ask(question)
        except Exception:
            log.exception("Unexpected failure while answering an AI screen question")
            answer = "The request failed unexpectedly. The problem was logged."
        try:
            self.after(0, self._finish_answer, answer_bubble, answer)
        except (TclError, RuntimeError):
            # The window may have closed while the network request was running.
            log.debug("Discarding the AI response because the Tk window is closing.")
            return

    def _finish_answer(self, answer_bubble, answer):
        answer_bubble.configure(text=answer)
        self._set_request_pending(False)

    def _set_request_pending(self, pending):
        self._request_pending = pending
        state = "disabled" if pending else "normal"
        self.input.configure(state=state)
        self.ask_button.configure(state=state)
        for button in self.chip_w:
            button.configure(state=state)

    def _on_resize(self, e):
        w = e.width / theme.scale(self)                       # pixels -> scaled units
        width_changed = w != self._layout_width
        self._layout_width = w
        stacked = w < 656                                     # mockup: two 320px columns + 16px gap
        layout_changed = stacked != self._stacked
        card_w = w if stacked else (w - 16) / 2
        wrap = max(140, int((card_w - 60) * 0.8))
        note_wrap = int(card_w - 40)
        chip_cols = 3 if card_w - 40 >= 440 else 2 if card_w - 40 >= 290 else 1

        if wrap != self._wrap:
            self._wrap = wrap
            for lbl in self.bubbles:
                lbl.configure(wraplength=wrap)
        if note_wrap != self._note_wrap:
            self._note_wrap = note_wrap
            self.note.configure(wraplength=note_wrap)
        if stacked != self._stacked:
            self._stacked = stacked
            theme.flow(self, [self.chat_card, self.memo_card], 1 if stacked else 2)
            for card in (self.chat_card, self.memo_card):
                card.grid_propagate(True)
                card.configure(height=0)
            if stacked:
                for card in (self.chat_card, self.memo_card):
                    card.grid_configure(sticky="new")
        if chip_cols != self._chip_cols:
            self._chip_cols = chip_cols
            theme.flow(self.chips, self.chip_w, chip_cols, gap=8)
        if not stacked and (width_changed or layout_changed):
            self._queue_height_sync()

    def _queue_height_sync(self):
        if self._height_job is None:
            self._height_job = self.after_idle(self._sync_card_heights)

    def _sync_card_heights(self):
        self._height_job = None
        if self._stacked:
            return
        for card in (self.chat_card, self.memo_card):
            card.grid_propagate(True)
            card.configure(height=0)
        self.update_idletasks()
        height = round(max(self.chat_card.winfo_reqheight(), self.memo_card.winfo_reqheight())
                       / theme.scale(self))
        for card in (self.chat_card, self.memo_card):
            card.grid_propagate(False)
            card.configure(height=height)
            card.grid_configure(sticky="nsew")

    def refresh(self):
        self.memo_box.configure(state="normal")
        self.memo_box.delete("1.0", "end")
        memo = self.service.memo()
        lines = [line for line in memo.splitlines() if line.strip()]
        self.memo_box.insert("1.0", "\n\n".join(lines))
        self.memo_box.configure(state="disabled")
