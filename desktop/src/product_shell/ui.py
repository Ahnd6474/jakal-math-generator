from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import tkinter as tk
from tkinter import ttk

from product_shell.app import (
    GenerationForm,
    ProductShellApp,
    RunStatus,
    ShellUiState,
)


@dataclass(frozen=True)
class ShellButtonState:
    start_enabled: bool
    regenerate_enabled: bool
    preview_enabled: bool
    export_enabled: bool


@dataclass(frozen=True)
class ShellViewData:
    status_text: str
    run_count_text: str
    error_text: str
    preview_text: str
    export_text: str
    log_text: str
    buttons: ShellButtonState


@dataclass
class ShellUiBindings:
    root: tk.Misc | None = None
    status_var: tk.StringVar | None = None
    run_count_var: tk.StringVar | None = None
    error_var: tk.StringVar | None = None
    preview_target: Any | None = None
    export_var: tk.StringVar | None = None
    log_var: tk.StringVar | None = None
    start_button: ttk.Button | None = None
    regenerate_button: ttk.Button | None = None
    preview_button: ttk.Button | None = None
    export_button: ttk.Button | None = None


class ShellUiController:
    def __init__(
        self,
        *,
        shell_app: ProductShellApp,
        bindings: ShellUiBindings,
        form_provider: Callable[[], GenerationForm],
        constraints_provider: Callable[[], Mapping[str, Any] | None] | None = None,
        export_path_provider: Callable[[], str | Path] | None = None,
        extra_placeholders_provider: Callable[[], Mapping[str, str] | None] | None = None,
        auto_wire: bool = True,
    ) -> None:
        self._shell_app = shell_app
        self._bindings = bindings
        self._form_provider = form_provider
        self._constraints_provider = constraints_provider
        self._export_path_provider = export_path_provider
        self._extra_placeholders_provider = extra_placeholders_provider
        self._ui_error: str | None = None

        if auto_wire:
            self._wire_buttons()

    def refresh(self) -> ShellViewData:
        ui_state = self._shell_app.ui_state()
        preview_text = self._safe_preview_text(ui_state)
        view_data = build_shell_view_data(
            ui_state,
            preview_text=preview_text,
            ui_error=self._ui_error,
        )
        self._apply_view_data(view_data)
        return view_data

    def handle_generate(self) -> None:
        def action() -> None:
            form = self._form_provider()
            constraints = self._constraints_provider() if self._constraints_provider else None
            self._shell_app.start_generation(form, constraints=constraints)

        self._run_action(action)

    def handle_regenerate(self) -> None:
        def action() -> None:
            constraints = self._constraints_provider() if self._constraints_provider else None
            self._shell_app.regenerate(constraints=constraints)

        self._run_action(action)

    def handle_preview(self) -> None:
        self._ui_error = None
        self.refresh()

    def handle_export(self) -> None:
        def action() -> None:
            if self._export_path_provider is None:
                raise RuntimeError("Export path provider is not configured.")
            output_path = self._export_path_provider()
            extra_placeholders = (
                self._extra_placeholders_provider()
                if self._extra_placeholders_provider
                else None
            )
            self._shell_app.export_hwpx(
                output_path=output_path,
                extra_placeholders=extra_placeholders,
            )

        self._run_action(action)

    def _run_action(self, action: Callable[[], None]) -> None:
        self._ui_error = None
        self._set_busy(True)
        try:
            action()
        except Exception as exc:  # noqa: BLE001 - surface UI errors to the view
            self._ui_error = str(exc)
        finally:
            self._set_busy(False)
            self.refresh()

    def _set_busy(self, is_busy: bool) -> None:
        if is_busy:
            _set_button_enabled(self._bindings.start_button, False)
            _set_button_enabled(self._bindings.regenerate_button, False)
            _set_button_enabled(self._bindings.preview_button, False)
            _set_button_enabled(self._bindings.export_button, False)
        if self._bindings.root is not None:
            self._bindings.root.update_idletasks()

    def _wire_buttons(self) -> None:
        if self._bindings.start_button is not None:
            self._bindings.start_button.configure(command=self.handle_generate)
        if self._bindings.regenerate_button is not None:
            self._bindings.regenerate_button.configure(command=self.handle_regenerate)
        if self._bindings.preview_button is not None:
            self._bindings.preview_button.configure(command=self.handle_preview)
        if self._bindings.export_button is not None:
            self._bindings.export_button.configure(command=self.handle_export)

    def _apply_view_data(self, view_data: ShellViewData) -> None:
        _set_var(self._bindings.status_var, view_data.status_text)
        _set_var(self._bindings.run_count_var, view_data.run_count_text)
        _set_var(self._bindings.error_var, view_data.error_text)
        _set_var(self._bindings.export_var, view_data.export_text)
        _set_var(self._bindings.log_var, view_data.log_text)
        _set_text_target(self._bindings.preview_target, view_data.preview_text)

        _set_button_enabled(self._bindings.start_button, view_data.buttons.start_enabled)
        _set_button_enabled(
            self._bindings.regenerate_button,
            view_data.buttons.regenerate_enabled,
        )
        _set_button_enabled(self._bindings.preview_button, view_data.buttons.preview_enabled)
        _set_button_enabled(self._bindings.export_button, view_data.buttons.export_enabled)

    def _safe_preview_text(self, ui_state: ShellUiState) -> str:
        if ui_state.generation_output is None:
            return ""
        try:
            return self._shell_app.preview()
        except Exception as exc:  # noqa: BLE001 - surface UI errors to the view
            self._ui_error = str(exc)
            return ""


def build_shell_view_data(
    ui_state: ShellUiState,
    *,
    preview_text: str,
    ui_error: str | None = None,
) -> ShellViewData:
    status_text = f"Status: {_format_status(ui_state.status)}"
    run_count_text = f"Runs: {ui_state.run_count}"
    error_text = _compose_error_message(ui_state.last_error, ui_error)
    export_text = _format_export(ui_state)
    log_text = _format_codex_logs(ui_state)
    buttons = ShellButtonState(
        start_enabled=ui_state.actions.can_start,
        regenerate_enabled=ui_state.actions.can_regenerate,
        preview_enabled=ui_state.actions.can_preview,
        export_enabled=ui_state.actions.can_export,
    )
    return ShellViewData(
        status_text=status_text,
        run_count_text=run_count_text,
        error_text=error_text,
        preview_text=preview_text,
        export_text=export_text,
        log_text=log_text,
        buttons=buttons,
    )


def _format_status(status: RunStatus) -> str:
    return status.value.replace("_", " ").title()


def _compose_error_message(shell_error: str | None, ui_error: str | None) -> str:
    if shell_error and ui_error:
        return f"{ui_error}\n{shell_error}"
    return ui_error or shell_error or ""


def _format_export(ui_state: ShellUiState) -> str:
    if ui_state.export_result is None:
        if ui_state.status == RunStatus.EXPORT_FAILED:
            return "Export failed."
        return ""
    result = ui_state.export_result
    return (
        "Exported to: "
        f"{result.output_path} "
        f"(placeholders: {result.rendered_placeholders}, verified: {result.verified_reopen})"
    )


def _format_codex_logs(ui_state: ShellUiState) -> str:
    if not ui_state.codex_logs:
        return ""
    lines: list[str] = []
    for entry in ui_state.codex_logs:
        detail = f"attempt {entry.attempt}: {entry.status}"
        if entry.returncode is not None:
            detail = f"{detail} (code={entry.returncode})"
        if entry.parse_error:
            detail = f"{detail} parse_error={entry.parse_error}"
        lines.append(detail)
    return "\n".join(lines)


def _set_var(target: tk.StringVar | None, value: str) -> None:
    if target is None:
        return
    target.set(value)


def _set_text_target(target: Any | None, value: str) -> None:
    if target is None:
        return
    if hasattr(target, "set") and callable(target.set):
        target.set(value)
        return
    if hasattr(target, "delete") and hasattr(target, "insert"):
        target.delete("1.0", "end")
        target.insert("1.0", value)


def _set_button_enabled(button: Any | None, enabled: bool) -> None:
    if button is None:
        return
    state_value = "normal" if enabled else "disabled"
    if hasattr(button, "configure"):
        try:
            button.configure(state=state_value)
            return
        except tk.TclError:
            pass
    if hasattr(button, "state"):
        if enabled:
            button.state(["!disabled"])
        else:
            button.state(["disabled"])
