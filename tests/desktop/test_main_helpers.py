from __future__ import annotations

from pathlib import Path

from contracts import GenerationValidationResult, MathVerification, OriginalityReport, QuestionValidationResult
from export import HwpxExportResult
from main import format_export_summary, format_run_history_line, format_validation_summary
from product_shell.app import ShellRunRecord, RunStatus


def _sample_validation(*, passed: bool, reason: str | None = None) -> GenerationValidationResult:
    question = QuestionValidationResult(
        question_id="q1",
        passed=passed,
        scores={
            "format": 1.0,
            "answer_uniqueness": 1.0,
            "math": 1.0,
            "originality": 1.0,
        },
        failures=(),
        originality_report=OriginalityReport(
            is_original=True,
            max_similarity=0.0,
            threshold=0.8,
        ),
        math_verification=MathVerification(status="pass", score=1.0, message=None),
    )
    return GenerationValidationResult(
        passed=passed,
        questions=(question,),
        retry_reason_codes=(reason,) if reason else (),
    )


def test_format_validation_summary_passed() -> None:
    result = _sample_validation(passed=True)
    summary = format_validation_summary(result)
    assert "Validation passed" in summary
    assert "1 questions" in summary


def test_format_validation_summary_failed() -> None:
    result = _sample_validation(passed=False, reason="format_invalid")
    summary = format_validation_summary(result)
    assert "Validation failed" in summary
    assert "format_invalid" in summary


def test_format_export_summary() -> None:
    result = HwpxExportResult(
        output_path=Path("exported.hwpx"),
        rendered_placeholders=12,
        verified_reopen=True,
        style_ids_preserved=True,
    )
    summary = format_export_summary(result)
    assert "exported.hwpx" in summary
    assert "placeholders" in summary


def test_format_run_history_line() -> None:
    record = ShellRunRecord(
        index=2,
        status=RunStatus.EXPORT_SUCCEEDED,
        error=None,
        has_output=True,
        export_path="C:/exports/output.hwpx",
    )
    line = format_run_history_line(record)
    assert "Run 2" in line
    assert "export" in line
