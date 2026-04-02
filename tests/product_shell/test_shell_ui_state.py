from __future__ import annotations

from pathlib import Path

from contracts import CodexGenerationOutput, GeneratedQuestion
from product_shell.app import (
    GenerationForm,
    ProductShellApp,
    RunStatus,
    ShellUiState,
)
from export import HwpxExportResult
from generation.adapter.codex_cli import CodexAdapterResult
from validation import GenerationValidator


class StubAdapter:
    def __init__(self, result: CodexAdapterResult) -> None:
        self._result = result

    def generate(self, question_spec, *, constraints=None) -> CodexAdapterResult:
        return self._result


class StubExporter:
    def __init__(self, result: HwpxExportResult) -> None:
        self._result = result

    def render(self, *, template_path, output_path, generation_output, extra_placeholders=None) -> HwpxExportResult:
        return HwpxExportResult(
            output_path=Path(output_path),
            rendered_placeholders=self._result.rendered_placeholders,
            verified_reopen=self._result.verified_reopen,
            style_ids_preserved=self._result.style_ids_preserved,
        )


def _build_output() -> CodexGenerationOutput:
    question = GeneratedQuestion(
        question_id="q1",
        stem="Solve 1+1.",
        choices=("1", "2"),
        answer=2,
        explanation="Basic addition.",
        metadata=None,
    )
    return CodexGenerationOutput(questions=(question,))


def _build_form(tmp_path: Path) -> GenerationForm:
    return GenerationForm(
        difficulty="easy",
        subject="math",
        topic_major="arithmetic",
        topic_minor="addition",
        topic_detail="single-digit",
        question_format="5-choice",
        style="standard",
        quantity=1,
        output_type="problem_answer",
        template_path=str(tmp_path / "template.hwpx"),
    )


def _build_adapter_result(tmp_path: Path, output: CodexGenerationOutput) -> CodexAdapterResult:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    attempt_dir = artifacts_dir / "attempt_01"
    attempt_dir.mkdir()
    (attempt_dir / "run.log").write_text(
        '{"status": "ok", "returncode": 0, "parse_error": null}',
        encoding="utf-8",
    )
    return CodexAdapterResult(
        success=True,
        attempt_count=1,
        artifacts_dir=artifacts_dir,
        parsed_output=output,
        parse_error=None,
    )


def test_ui_state_actions_and_history(tmp_path: Path) -> None:
    output = _build_output()
    adapter = StubAdapter(_build_adapter_result(tmp_path, output))
    exporter = StubExporter(
        HwpxExportResult(
            output_path=tmp_path / "out.hwpx",
            rendered_placeholders=3,
            verified_reopen=True,
            style_ids_preserved=True,
        )
    )
    app = ProductShellApp(
        adapter=adapter,
        validator=GenerationValidator(),
        exporter=exporter,
    )

    initial = app.ui_state()
    assert isinstance(initial, ShellUiState)
    assert initial.status == RunStatus.IDLE
    assert initial.actions.can_start is True
    assert initial.actions.can_regenerate is False
    assert initial.actions.can_preview is False
    assert initial.actions.can_export is False
    assert initial.run_history == ()

    app.start_generation(_build_form(tmp_path))
    ready = app.ui_state()
    assert ready.status == RunStatus.ACCEPTED
    assert ready.actions.can_regenerate is True
    assert ready.actions.can_preview is True
    assert ready.actions.can_export is True
    assert len(ready.run_history) == 1
    assert ready.run_history[0].status == RunStatus.ACCEPTED

    app.export_hwpx(output_path=tmp_path / "out.hwpx")
    exported = app.ui_state()
    assert exported.status == RunStatus.EXPORT_SUCCEEDED
    assert len(exported.run_history) == 2
    assert exported.run_history[-1].export_path is not None
