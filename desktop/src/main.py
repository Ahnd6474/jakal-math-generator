from __future__ import annotations

from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
DESKTOP_SRC_PATH = REPO_ROOT / "desktop" / "src"

for path in (str(SRC_PATH), str(DESKTOP_SRC_PATH)):
    if path not in sys.path:
        sys.path.insert(0, path)

from export import HwpxExportEngine
from generation.adapter import CodexCliAdapter, CodexExecutionConfig
from product_shell import ProductShellApp, bootstrap_product_shell
from validation import GenerationValidator


WINDOW_TITLE = "Jakal Math Generator"


def build_product_shell(*, repo_root: Path | None = None) -> ProductShellApp:
    root = repo_root or REPO_ROOT
    config = CodexExecutionConfig.from_path(
        root / "configs" / "codex" / "execution.json",
        repo_root=root,
    )
    return bootstrap_product_shell(
        adapter=CodexCliAdapter(config),
        validator=GenerationValidator(),
        exporter=HwpxExportEngine(),
    )


class ProductShellWindow(tk.Tk):
    def __init__(self, shell_app: ProductShellApp) -> None:
        super().__init__()
        self.shell_app = shell_app

        self.title(WINDOW_TITLE)
        self.geometry("720x420")
        self.minsize(640, 360)

        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=WINDOW_TITLE,
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text="Desktop launcher bootstrapped from the shared product shell API.",
        ).pack(anchor="w", pady=(8, 0))

        status_frame = ttk.LabelFrame(frame, text="Shell Status", padding=16)
        status_frame.pack(fill="x", pady=(20, 0))

        ttk.Label(status_frame, text=f"Run status: {shell_app.state.status.value}").pack(anchor="w")
        ttk.Label(status_frame, text=f"Run count: {shell_app.state.run_count}").pack(anchor="w", pady=(8, 0))
        ttk.Label(status_frame, text="Launcher only wires dependencies and starts the shell.").pack(
            anchor="w",
            pady=(8, 0),
        )

        action_frame = ttk.Frame(frame)
        action_frame.pack(fill="x", pady=(20, 0))
        ttk.Button(action_frame, text="Close", command=self.destroy).pack(anchor="e")


def build_window(*, shell_app: ProductShellApp | None = None) -> ProductShellWindow:
    return ProductShellWindow(shell_app or build_product_shell())


def launch_desktop_app() -> ProductShellWindow:
    window = build_window()
    window.mainloop()
    return window


def main() -> int:
    launch_desktop_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
