from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, ttk


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
DESKTOP_SRC_PATH = REPO_ROOT / "desktop" / "src"

for path in (str(SRC_PATH), str(DESKTOP_SRC_PATH)):
    if path not in sys.path:
        sys.path.insert(0, path)

from export import HwpxExportEngine, HwpxExportResult
from generation.adapter import CodexCliAdapter, CodexExecutionConfig
from product_shell import ProductShellApp, RunStatus, bootstrap_product_shell
from product_shell.app import ShellActionAvailability, ShellRunRecord, ShellUiState
from validation import GenerationValidator


WINDOW_TITLE = "Jakal Math Generator"
DEFAULT_TEMPLATE_FILENAME = "평가원수학양식(수정) (1).hwpx"
DEFAULT_OUTPUT_FILENAME = "jakal_generation.hwpx"


@dataclass(frozen=True)
class FormField:
    label: str
    variable: tk.Variable
    widget: tk.Widget


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


def format_validation_summary(result) -> str:
    if result is None:
        return "No validation results yet."
    question_count = len(result.questions)
    if result.passed:
        return f"Validation passed ({question_count} questions)."
    reasons = ", ".join(result.retry_reason_codes) if result.retry_reason_codes else "unspecified"
    return f"Validation failed ({question_count} questions). Reasons: {reasons}."


def format_export_summary(result: HwpxExportResult | None) -> str:
    if result is None:
        return "No export completed yet."
    return (
        f"Exported to {result.output_path} | "
        f"placeholders: {result.rendered_placeholders} | "
        f"verified reopen: {result.verified_reopen}"
    )


def format_run_history_line(record: ShellRunRecord) -> str:
    status = record.status.value if isinstance(record.status, RunStatus) else str(record.status)
    details = []
    if record.error:
        details.append(f"error: {record.error}")
    if record.export_path:
        details.append(f"export: {record.export_path}")
    detail_text = " | ".join(details)
    suffix = f" | {detail_text}" if detail_text else ""
    return f"Run {record.index}: {status}{suffix}"


class ProductShellWindow(tk.Tk):
    def __init__(self, shell_app: ProductShellApp, *, repo_root: Path | None = None) -> None:
        super().__init__()
        self.shell_app = shell_app
        self.repo_root = repo_root or REPO_ROOT
        self._manual_error_message: str | None = None

        self.title(WINDOW_TITLE)
        self.geometry("1080x720")
        self.minsize(980, 640)

        self._build_variables()
        self._build_layout()
        self._populate_defaults()
        self._refresh_ui()

    def _build_variables(self) -> None:
        self.difficulty_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.topic_major_var = tk.StringVar()
        self.topic_minor_var = tk.StringVar()
        self.topic_detail_var = tk.StringVar()
        self.question_format_var = tk.StringVar()
        self.style_var = tk.StringVar()
        self.quantity_var = tk.IntVar()
        self.output_type_var = tk.StringVar()
        self.template_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()

        self.status_var = tk.StringVar()
        self.run_count_var = tk.StringVar()
        self.validation_var = tk.StringVar()
        self.export_var = tk.StringVar()

    def _build_layout(self) -> None:
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container)
        header.pack(fill="x")
        ttk.Label(header, text=WINDOW_TITLE, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="Generate, preview, and export math problems using the shared shell workflow.",
        ).pack(anchor="w", pady=(6, 0))

        main_frame = ttk.Frame(container)
        main_frame.pack(fill="both", expand=True, pady=(16, 0))
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        form_frame = ttk.LabelFrame(main_frame, text="Generation Form", padding=16)
        form_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        form_frame.columnconfigure(1, weight=1)

        self.form_fields = self._build_form_fields(form_frame)

        side_frame = ttk.Frame(main_frame)
        side_frame.grid(row=0, column=1, sticky="nsew")
        side_frame.columnconfigure(0, weight=1)
        side_frame.rowconfigure(1, weight=1)

        status_frame = ttk.LabelFrame(side_frame, text="Status", padding=16)
        status_frame.grid(row=0, column=0, sticky="ew")
        status_frame.columnconfigure(1, weight=1)

        ttk.Label(status_frame, text="Run status:").grid(row=0, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self.status_var).grid(row=0, column=1, sticky="w")
        ttk.Label(status_frame, text="Run count:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(status_frame, textvariable=self.run_count_var).grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(status_frame, text="Validation:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(status_frame, textvariable=self.validation_var, wraplength=360, justify="left").grid(
            row=2, column=1, sticky="w", pady=(6, 0)
        )
        ttk.Label(status_frame, text="Export:").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Label(status_frame, textvariable=self.export_var, wraplength=360, justify="left").grid(
            row=3, column=1, sticky="w", pady=(6, 0)
        )
        ttk.Label(status_frame, text="Last error:").grid(row=4, column=0, sticky="nw", pady=(6, 0))
        self.error_text = tk.Text(status_frame, height=4, wrap="word", relief="solid", borderwidth=1)
        self.error_text.grid(row=4, column=1, sticky="ew", pady=(6, 0))
        self._set_text(self.error_text, "")

        preview_frame = ttk.LabelFrame(side_frame, text="Preview", padding=16)
        preview_frame.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)

        self.preview_text = tk.Text(preview_frame, height=12, wrap="word", relief="solid", borderwidth=1)
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        self.preview_text.grid(row=1, column=0, sticky="nsew")
        preview_scroll.grid(row=1, column=1, sticky="ns")

        preview_actions = ttk.Frame(preview_frame)
        preview_actions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        preview_actions.columnconfigure(0, weight=1)
        self.preview_button = ttk.Button(preview_actions, text="Refresh Preview", command=self._on_preview)
        self.preview_button.pack(anchor="e")

        export_frame = ttk.LabelFrame(side_frame, text="Export", padding=16)
        export_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        export_frame.columnconfigure(1, weight=1)

        ttk.Label(export_frame, text="Output path:").grid(row=0, column=0, sticky="w")
        output_entry = ttk.Entry(export_frame, textvariable=self.output_path_var)
        output_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(export_frame, text="Browse", command=self._on_choose_output).grid(row=0, column=2, sticky="e")

        history_frame = ttk.LabelFrame(side_frame, text="Run History", padding=16)
        history_frame.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)

        self.history_list = tk.Listbox(history_frame, height=5)
        history_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_list.yview)
        self.history_list.configure(yscrollcommand=history_scroll.set)
        self.history_list.grid(row=0, column=0, sticky="nsew")
        history_scroll.grid(row=0, column=1, sticky="ns")

        action_frame = ttk.Frame(container)
        action_frame.pack(fill="x", pady=(16, 0))
        action_frame.columnconfigure(0, weight=1)
        self.generate_button = ttk.Button(action_frame, text="Generate", command=self._on_generate)
        self.regenerate_button = ttk.Button(action_frame, text="Regenerate", command=self._on_regenerate)
        self.export_button = ttk.Button(action_frame, text="Export", command=self._on_export)
        close_button = ttk.Button(action_frame, text="Close", command=self.destroy)

        self.generate_button.pack(side="left")
        self.regenerate_button.pack(side="left", padx=(8, 0))
        self.export_button.pack(side="left", padx=(8, 0))
        close_button.pack(side="right")

    def _build_form_fields(self, frame: ttk.LabelFrame) -> list[FormField]:
        fields: list[FormField] = []
        row = 0

        fields.append(
            self._add_combo(
                frame,
                row,
                "Difficulty",
                self.difficulty_var,
                ["easy", "medium", "hard"],
            )
        )
        row += 1
        fields.append(self._add_entry(frame, row, "Subject", self.subject_var))
        row += 1
        fields.append(self._add_entry(frame, row, "Topic (major)", self.topic_major_var))
        row += 1
        fields.append(self._add_entry(frame, row, "Topic (minor)", self.topic_minor_var))
        row += 1
        fields.append(self._add_entry(frame, row, "Topic (detail)", self.topic_detail_var))
        row += 1
        fields.append(
            self._add_combo(
                frame,
                row,
                "Question format",
                self.question_format_var,
                ["5-choice", "short-answer"],
            )
        )
        row += 1
        fields.append(self._add_entry(frame, row, "Style", self.style_var))
        row += 1
        fields.append(self._add_spinbox(frame, row, "Quantity", self.quantity_var, 1, 50))
        row += 1
        fields.append(
            self._add_combo(
                frame,
                row,
                "Output type",
                self.output_type_var,
                ["problem_only", "problem_answer", "problem_answer_solution"],
            )
        )
        row += 1

        label = ttk.Label(frame, text="Template path")
        label.grid(row=row, column=0, sticky="w", pady=(8, 0))
        entry = ttk.Entry(frame, textvariable=self.template_path_var)
        entry.grid(row=row, column=1, sticky="ew", pady=(8, 0), padx=(8, 8))
        button = ttk.Button(frame, text="Browse", command=self._on_choose_template)
        button.grid(row=row, column=2, sticky="e", pady=(8, 0))
        fields.append(FormField(label="Template path", variable=self.template_path_var, widget=entry))
        return fields

    def _add_entry(self, frame: ttk.LabelFrame, row: int, label: str, variable: tk.StringVar) -> FormField:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=(8, 0))
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(8, 0), padx=(8, 0))
        return FormField(label=label, variable=variable, widget=entry)

    def _add_combo(
        self,
        frame: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        values: list[str],
    ) -> FormField:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=(8, 0))
        combo = ttk.Combobox(frame, textvariable=variable, values=values, state="readonly")
        combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(8, 0), padx=(8, 0))
        return FormField(label=label, variable=variable, widget=combo)

    def _add_spinbox(
        self,
        frame: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.IntVar,
        start: int,
        end: int,
    ) -> FormField:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=(8, 0))
        spin = ttk.Spinbox(frame, from_=start, to=end, textvariable=variable, width=6)
        spin.grid(row=row, column=1, sticky="w", pady=(8, 0), padx=(8, 0))
        return FormField(label=label, variable=variable, widget=spin)

    def _populate_defaults(self) -> None:
        self.difficulty_var.set("medium")
        self.subject_var.set("math")
        self.topic_major_var.set("")
        self.topic_minor_var.set("")
        self.topic_detail_var.set("")
        self.question_format_var.set("5-choice")
        self.style_var.set("standard")
        self.quantity_var.set(1)
        self.output_type_var.set("problem_only")
        template_path = self.repo_root / DEFAULT_TEMPLATE_FILENAME
        if template_path.exists():
            self.template_path_var.set(str(template_path))
        else:
            self.template_path_var.set("")
        output_path = self.repo_root / DEFAULT_OUTPUT_FILENAME
        self.output_path_var.set(str(output_path))

    def _refresh_ui(self, *, preview_on_success: bool = False) -> None:
        ui_state = self.shell_app.ui_state()
        self.status_var.set(ui_state.status.value)
        self.run_count_var.set(str(ui_state.run_count))
        self.validation_var.set(format_validation_summary(ui_state.validation_result))
        self.export_var.set(format_export_summary(ui_state.export_result))

        error_message = ui_state.last_error or self._manual_error_message or ""
        if ui_state.last_error:
            self._manual_error_message = None
        self._set_text(self.error_text, error_message)

        self._set_action_states(ui_state.actions)
        self._update_history(ui_state)

        if preview_on_success and ui_state.actions.can_preview:
            self._populate_preview_from_shell()
        elif not ui_state.actions.can_preview:
            self._set_text(self.preview_text, "No preview available yet.")

    def _set_action_states(self, actions: ShellActionAvailability) -> None:
        self.generate_button.configure(state="normal" if actions.can_start else "disabled")
        self.regenerate_button.configure(state="normal" if actions.can_regenerate else "disabled")
        self.export_button.configure(state="normal" if actions.can_export else "disabled")
        self.preview_button.configure(state="normal" if actions.can_preview else "disabled")

    def _update_history(self, ui_state: ShellUiState) -> None:
        self.history_list.delete(0, tk.END)
        for record in ui_state.run_history[-6:]:
            self.history_list.insert(tk.END, format_run_history_line(record))

    def _set_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        widget.configure(state="disabled")

    def _read_form(self):
        quantity_raw = self.quantity_var.get()
        try:
            quantity = int(quantity_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Quantity must be an integer.") from exc
        template_path = self.template_path_var.get().strip()
        if not template_path:
            raise ValueError("Template path is required.")

        from product_shell import GenerationForm

        return GenerationForm(
            difficulty=self.difficulty_var.get().strip(),
            subject=self.subject_var.get().strip(),
            topic_major=self.topic_major_var.get().strip(),
            topic_minor=self.topic_minor_var.get().strip(),
            topic_detail=self.topic_detail_var.get().strip(),
            question_format=self.question_format_var.get().strip(),
            style=self.style_var.get().strip(),
            quantity=quantity,
            output_type=self.output_type_var.get().strip(),
            template_path=template_path,
        )

    def _run_shell_action(self, label: str, action) -> None:
        self.status_var.set(label)
        self.update_idletasks()
        try:
            action()
        except Exception as exc:  # pragma: no cover - UI guardrail
            self._manual_error_message = str(exc)
        self._refresh_ui(preview_on_success=True)

    def _on_generate(self) -> None:
        try:
            form = self._read_form()
        except ValueError as exc:
            self._manual_error_message = str(exc)
            self._refresh_ui()
            return

        self._run_shell_action("running", lambda: self.shell_app.start_generation(form))

    def _on_regenerate(self) -> None:
        self._run_shell_action("running", self.shell_app.regenerate)

    def _on_preview(self) -> None:
        self._populate_preview_from_shell()
        self._refresh_ui()

    def _populate_preview_from_shell(self) -> None:
        try:
            preview_text = self.shell_app.preview()
        except Exception as exc:  # pragma: no cover - UI guardrail
            self._manual_error_message = str(exc)
            self._set_text(self.preview_text, "Preview unavailable.")
            return
        self._set_text(self.preview_text, preview_text)

    def _on_export(self) -> None:
        output_path = self.output_path_var.get().strip()
        if not output_path:
            self._manual_error_message = "Output path is required to export."
            self._refresh_ui()
            return
        output = Path(output_path)
        if not output.parent.exists():
            output.parent.mkdir(parents=True, exist_ok=True)

        self._run_shell_action(
            "exporting",
            lambda: self.shell_app.export_hwpx(output_path=output),
        )

    def _on_choose_template(self) -> None:
        filename = filedialog.askopenfilename(
            title="Select HWPX template",
            initialdir=str(self.repo_root),
            filetypes=[("HWPX files", "*.hwpx"), ("All files", "*.*")],
        )
        if filename:
            self.template_path_var.set(filename)

    def _on_choose_output(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Export HWPX",
            initialdir=str(self.repo_root),
            defaultextension=".hwpx",
            filetypes=[("HWPX files", "*.hwpx"), ("All files", "*.*")],
        )
        if filename:
            self.output_path_var.set(filename)


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
