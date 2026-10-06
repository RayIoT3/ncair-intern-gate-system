"""NCAIR Intern Gate. Run:  python main.py or python3 main.py(for macOS/Linux).
main.py only starts the application; the logic lives in the packages."""
from pathlib import Path
import sys
import ctk_patch #noqa: F401  # patch CustomTkinter to avoid the scrollbar hanging on some systms due to scaling issues.

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "gui"))          # the GUI modules import each other by plain name

import config
from exceptions.custom_exceptions import GateError
from services.factory import build_services


def main():
    import tkinter as tk
    from tkinter import messagebox
    try:
        service = build_services(config.DATA_DIR, configure_logging=True)
    except GateError as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("NCAIR Intern Gate cannot start", str(e))
        return

    import customtkinter as ctk
    from app import App
    ctk.set_appearance_mode("system")
    window = App(service)
    if service.warnings:
        window.after(600, lambda: messagebox.showwarning("Data notice", "\n\n".join(service.warnings)))
    window.mainloop()


if __name__ == "__main__":
    main()
