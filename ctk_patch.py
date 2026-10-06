"""Work around CustomTkinter's CTkScrollbar._draw hanging at startup on some setups
(update_idletasks called while the scrollable frame is still being built)."""
from customtkinter.windows.widgets.ctk_scrollbar import CTkScrollbar

_orig_draw = CTkScrollbar._draw


def _draw_without_idle_flush(self, *args, **kwargs):
    canvas = self._canvas
    canvas.update_idletasks = lambda: None  # skip the flush that triggers the hang
    try:
        _orig_draw(self, *args, **kwargs)
    finally:
        del canvas.update_idletasks  # restore the normal method


CTkScrollbar._draw = _draw_without_idle_flush 