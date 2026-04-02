from __future__ import annotations

from dataclasses import dataclass

from product_shell.app import (
    RunStatus,
    ShellActionAvailability,
    ShellRunContext,
    ShellUiState,
)
from product_shell.ui import (
    ShellUiBindings,
    ShellUiController,
    build_shell_view_data,
)


class DummyVar:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class DummyText:
    def __init__(self) -> None:
        self.value = ""

    def delete(self, start: str, end: str) -> None:
        self.value = ""

    def insert(self, start: str, value: str) -> None:
        self.value = value


class DummyButton:
    def __init__(self) -> None:
        self.state_value = "normal"
        self.command = None

    def configure(self, *, state=None, command=None) -> None:
        if state is not None:
            self.state_value = state
        if command is not None:
            self.command = command


@dataclass
class StubShellApp:
    ui_state_value: ShellUiState
    preview_text: str = "preview text"
    generated: bool = False

    def ui_state(self) -> ShellUiState:
        return self.ui_state_value

    def start_generation(self, form, *, constraints=None) -> ShellUiState:
        self.generated = True
        self.ui_state_value = _build_state(
            status=RunStatus.ACCEPTED,
            run_count=self.ui_state_value.run_count + 1,
            can_start=True,
            can_regenerate=True,
            can_preview=True,
            can_export=True,
            has_output=True,
        )
        return self.ui_state_value

    def regenerate(self, *, constraints=None) -> ShellUiState:
        return self.start_generation(None)

    def export_hwpx(self, *, output_path, extra_placeholders=None) -> ShellUiState:
        self.ui_state_value = _build_state(
            status=RunStatus.EXPORT_SUCCEEDED,
            run_count=self.ui_state_value.run_count,
            can_start=True,
            can_regenerate=True,
            can_preview=True,
            can_export=True,
            has_output=True,
            has_export=True,
        )
        return self.ui_state_value

    def preview(self) -> str:
        return self.preview_text


def _build_state(
    *,
    status: RunStatus,
    run_count: int,
    can_start: bool,
    can_regenerate: bool,
    can_preview: bool,
    can_export: bool,
    has_output: bool = False,
    has_export: bool = False,
    last_error: str | None = None,
) -> ShellUiState:
    actions = ShellActionAvailability(
        can_start=can_start,
        can_regenerate=can_regenerate,
        can_preview=can_preview,
        can_export=can_export,
        is_busy=False,
    )
    run_context = ShellRunContext(
        last_form=None,
        last_status=status,
        last_error=last_error,
        run_count=run_count,
        has_output=has_output,
        has_export=has_export,
        export_path="out.hwpx" if has_export else None,
    )
    return ShellUiState(
        status=status,
        last_error=last_error,
        validation_result=None,
        generation_output=object() if has_output else None,
        export_result=None,
        codex_logs=(),
        run_count=run_count,
        actions=actions,
        run_context=run_context,
        run_history=(),
    )


def test_build_shell_view_data_formats_status_and_buttons() -> None:
    state = _build_state(
        status=RunStatus.ACCEPTED,
        run_count=2,
        can_start=False,
        can_regenerate=True,
        can_preview=True,
        can_export=True,
        has_output=True,
    )

    view_data = build_shell_view_data(state, preview_text="preview")
    assert view_data.status_text == "Status: Accepted"
    assert view_data.run_count_text == "Runs: 2"
    assert view_data.buttons.start_enabled is False
    assert view_data.buttons.export_enabled is True
    assert view_data.preview_text == "preview"


def test_controller_updates_bindings_after_generate() -> None:
    initial_state = _build_state(
        status=RunStatus.IDLE,
        run_count=0,
        can_start=True,
        can_regenerate=False,
        can_preview=False,
        can_export=False,
    )
    shell = StubShellApp(ui_state_value=initial_state)

    bindings = ShellUiBindings(
        status_var=DummyVar(),
        run_count_var=DummyVar(),
        error_var=DummyVar(),
        preview_target=DummyText(),
        export_var=DummyVar(),
        log_var=DummyVar(),
        start_button=DummyButton(),
        regenerate_button=DummyButton(),
        preview_button=DummyButton(),
        export_button=DummyButton(),
    )

    controller = ShellUiController(
        shell_app=shell,
        bindings=bindings,
        form_provider=lambda: object(),
    )
    controller.refresh()
    assert bindings.status_var.value == "Status: Idle"
    assert bindings.start_button.state_value == "normal"

    controller.handle_generate()
    assert shell.generated is True
    assert bindings.status_var.value == "Status: Accepted"
    assert bindings.preview_target.value == "preview text"
    assert bindings.export_button.state_value == "normal"
