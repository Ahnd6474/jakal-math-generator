from __future__ import annotations

import json
from pathlib import Path
import zipfile

import main as desktop_main
from contracts import CodexGenerationOutput, REGEN_REASON_ORIGINALITY_TOO_SIMILAR
from export import HwpxExportEngine
from generation.adapter.codex_cli import CodexAdapterResult
from hwpx import HwpxArchive
from product_shell import GenerationForm, ProductShellApp, RunStatus
from validation import GenerationValidator


_SECTION_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
    xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p id="10" paraPrIDRef="10" styleIDRef="12">
    <hp:run charPrIDRef="21">
      <hp:t>{{QUESTION_1_NUMBER}}. {{QUESTION_1_STEM}}</hp:t>
    </hp:run>
  </hp:p>
  <hp:p id="11" paraPrIDRef="11" styleIDRef="13">
    <hp:run charPrIDRef="22"><hp:t>{{QUESTION_1_CHOICE_1}}</hp:t></hp:run>
  </hp:p>
  <hp:p id="12" paraPrIDRef="11" styleIDRef="13">
    <hp:run charPrIDRef="22"><hp:t>{{QUESTION_1_CHOICE_2}}</hp:t></hp:run>
  </hp:p>
  <hp:p id="16" paraPrIDRef="12" styleIDRef="14">
    <hp:run charPrIDRef="23"><hp:t>{{QUESTION_1_ANSWER}}</hp:t></hp:run>
  </hp:p>
</hs:sec>
"""


class FakeAdapter:
    def __init__(self, results: list[CodexAdapterResult]) -> None:
        self._results = results

    def generate(self, question_spec, *, constraints=None) -> CodexAdapterResult:
        if not self._results:
            raise AssertionError("No queued adapter results.")
        return self._results.pop(0)


def _write_attempt(root: Path, *, status: str, stdout: str = "", stderr: str = "", parse_error: str | None = None) -> None:
    attempt = root / "attempt_01"
    attempt.mkdir(parents=True, exist_ok=True)
    (attempt / "stdout.log").write_text(stdout, encoding="utf-8")
    (attempt / "stderr.log").write_text(stderr, encoding="utf-8")
    (attempt / "run.log").write_text(
        json.dumps(
            {
                "status": status,
                "returncode": 0,
                "parse_error": parse_error,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _make_adapter_result(tmp_path: Path, *, output: CodexGenerationOutput | None, success: bool, parse_error: str | None = None) -> CodexAdapterResult:
    artifacts = tmp_path / f"artifacts_{len(list(tmp_path.glob('artifacts_*')))}"
    _write_attempt(
        artifacts,
        status="ok" if success else "parse_failure",
        stdout="" if output is None else json.dumps(output.to_dict(), ensure_ascii=False),
        parse_error=parse_error,
    )
    return CodexAdapterResult(
        success=success,
        attempt_count=1,
        artifacts_dir=artifacts,
        parsed_output=output,
        parse_error=parse_error,
    )


def _build_form(template_path: Path) -> GenerationForm:
    return GenerationForm(
        difficulty="mid-4pt",
        subject="calculus",
        topic_major="function",
        topic_minor="limit",
        topic_detail="composite limit",
        question_format="5-choice",
        style="reasoning",
        quantity=1,
        output_type="problem_answer_solution",
        template_path=str(template_path),
    )


def _create_template(path: Path) -> None:
    with zipfile.ZipFile(path, mode="w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Preview/PrvText.txt", "{{QUESTION_1_STEM}}")
        zf.writestr("Contents/section0.xml", _SECTION_XML)


def test_shell_successful_generation_preview_and_export(tmp_path: Path) -> None:
    template_path = tmp_path / "template.hwpx"
    export_path = tmp_path / "output.hwpx"
    _create_template(template_path)

    output = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "Q1",
                    "stem": "Find the limit.",
                    "choices": ["1", "2"],
                    "answer": "2",
                    "explanation": "Direct substitution.",
                }
            ]
        }
    )
    adapter = FakeAdapter([_make_adapter_result(tmp_path, output=output, success=True)])
    app = ProductShellApp(adapter=adapter, validator=GenerationValidator(), exporter=HwpxExportEngine())

    state = app.start_generation(_build_form(template_path))

    assert state.status == RunStatus.ACCEPTED
    assert state.validation_result is not None
    assert state.validation_result.passed is True
    assert state.codex_logs[0].status == "ok"
    assert "Find the limit." in app.preview()

    exported = app.export_hwpx(output_path=export_path)
    assert exported.status == RunStatus.EXPORT_SUCCEEDED
    assert exported.export_result is not None
    assert exported.export_result.output_path == export_path


def test_launcher_entrypoint_reaches_export_preserving_hwpx_contracts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    template_path = tmp_path / "template.hwpx"
    export_path = tmp_path / "launcher-output.hwpx"
    _create_template(template_path)

    output = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "Q1",
                    "stem": "Launcher-generated stem.",
                    "choices": ["1", "2"],
                    "answer": "2",
                    "explanation": "Launcher path uses the shared shell.",
                }
            ]
        }
    )
    adapter = FakeAdapter([_make_adapter_result(tmp_path, output=output, success=True)])

    class FakeConfig:
        def __init__(self, repo_root: Path) -> None:
            self.repo_root = repo_root

    class FakeWindow:
        def __init__(self, shell_app: ProductShellApp) -> None:
            self.shell_app = shell_app
            self.mainloop_calls = 0

        def mainloop(self) -> None:
            self.mainloop_calls += 1

    def fake_from_path(path: Path, *, repo_root: Path) -> FakeConfig:
        assert path == repo_root / "configs" / "codex" / "execution.json"
        return FakeConfig(repo_root)

    def fake_adapter_factory(config: FakeConfig) -> FakeAdapter:
        assert config.repo_root == tmp_path
        return adapter

    launcher_state: dict[str, object] = {}

    def fake_build_window(*, shell_app=None):
        if shell_app is None:
            shell_app = desktop_main.build_product_shell(repo_root=tmp_path)
        window = FakeWindow(shell_app)
        launcher_state["window"] = window
        return window

    monkeypatch.setattr(desktop_main.CodexExecutionConfig, "from_path", fake_from_path)
    monkeypatch.setattr(desktop_main, "CodexCliAdapter", fake_adapter_factory)
    monkeypatch.setattr(desktop_main, "build_window", fake_build_window)

    window = desktop_main.launch_desktop_app()
    assert window is launcher_state["window"]
    assert window.mainloop_calls == 1
    assert isinstance(window.shell_app, ProductShellApp)

    accepted = window.shell_app.start_generation(_build_form(template_path))
    assert accepted.status == RunStatus.ACCEPTED

    exported = window.shell_app.export_hwpx(output_path=export_path)
    assert exported.status == RunStatus.EXPORT_SUCCEEDED
    assert exported.export_result is not None
    assert exported.export_result.verified_reopen is True
    assert exported.export_result.style_ids_preserved is True

    archive = HwpxArchive.load(export_path)
    preview = archive.read_preview_text()
    section_xml = archive.contents["Contents/section0.xml"].decode("utf-8")

    assert "Launcher-generated stem." in preview
    assert "{{QUESTION_1_STEM}}" not in preview
    assert 'styleIDRef="12"' in section_xml
    assert 'styleIDRef="13"' in section_xml


def test_shell_distinguishes_codex_parse_failure(tmp_path: Path) -> None:
    template_path = tmp_path / "template.hwpx"
    _create_template(template_path)

    adapter = FakeAdapter(
        [
            _make_adapter_result(
                tmp_path,
                output=None,
                success=False,
                parse_error="No JSON object start token found.",
            )
        ]
    )
    app = ProductShellApp(adapter=adapter, validator=GenerationValidator(), exporter=HwpxExportEngine())

    state = app.start_generation(_build_form(template_path))
    assert state.status == RunStatus.CODEX_PARSE_FAILED
    assert "No JSON object start token found." in (state.last_error or "")


def test_shell_distinguishes_validation_failure(tmp_path: Path) -> None:
    template_path = tmp_path / "template.hwpx"
    _create_template(template_path)

    invalid_output = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "Q1",
                    "stem": "Pick one.",
                    "choices": ["A", "B"],
                    "answer": "C",
                }
            ]
        }
    )
    adapter = FakeAdapter([_make_adapter_result(tmp_path, output=invalid_output, success=True)])
    app = ProductShellApp(adapter=adapter, validator=GenerationValidator(), exporter=HwpxExportEngine())

    state = app.start_generation(_build_form(template_path))
    assert state.status == RunStatus.VALIDATION_FAILED
    assert state.validation_result is not None
    assert state.validation_result.retry_reason_codes
    assert REGEN_REASON_ORIGINALITY_TOO_SIMILAR not in state.validation_result.retry_reason_codes


def test_shell_distinguishes_similarity_failure(tmp_path: Path) -> None:
    template_path = tmp_path / "template.hwpx"
    _create_template(template_path)

    output = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "Q1",
                    "stem": "reused exam style stem",
                    "answer": "1",
                }
            ]
        }
    )
    adapter = FakeAdapter([_make_adapter_result(tmp_path, output=output, success=True)])
    app = ProductShellApp(
        adapter=adapter,
        validator=GenerationValidator(),
        exporter=HwpxExportEngine(),
        reference_corpus=("reused exam style stem",),
    )

    state = app.start_generation(_build_form(template_path))
    assert state.status == RunStatus.SIMILARITY_FAILED
    assert state.validation_result is not None
    assert REGEN_REASON_ORIGINALITY_TOO_SIMILAR in state.validation_result.retry_reason_codes


def test_shell_can_regenerate_after_failure(tmp_path: Path) -> None:
    template_path = tmp_path / "template.hwpx"
    _create_template(template_path)

    rejected = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "Q1",
                    "stem": "reused stem",
                    "answer": "1",
                }
            ]
        }
    )
    accepted = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "Q2",
                    "stem": "fresh stem",
                    "answer": "1",
                }
            ]
        }
    )
    adapter = FakeAdapter(
        [
            _make_adapter_result(tmp_path, output=rejected, success=True),
            _make_adapter_result(tmp_path, output=accepted, success=True),
        ]
    )
    app = ProductShellApp(
        adapter=adapter,
        validator=GenerationValidator(),
        exporter=HwpxExportEngine(),
        reference_corpus=("reused stem",),
    )
    form = _build_form(template_path)

    failed = app.start_generation(form)
    assert failed.status == RunStatus.SIMILARITY_FAILED

    regenerated = app.regenerate()
    assert regenerated.status == RunStatus.ACCEPTED
    assert regenerated.run_count == 2


def test_shell_distinguishes_export_failure(tmp_path: Path) -> None:
    form = _build_form(tmp_path / "missing-template.hwpx")
    output = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "Q1",
                    "stem": "valid stem",
                    "answer": "1",
                }
            ]
        }
    )
    adapter = FakeAdapter([_make_adapter_result(tmp_path, output=output, success=True)])
    app = ProductShellApp(adapter=adapter, validator=GenerationValidator(), exporter=HwpxExportEngine())

    accepted = app.start_generation(form)
    assert accepted.status == RunStatus.ACCEPTED

    exported = app.export_hwpx(output_path=tmp_path / "out.hwpx")
    assert exported.status == RunStatus.EXPORT_FAILED
    assert exported.last_error is not None
