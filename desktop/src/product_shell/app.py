from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from contracts import (
    CodexGenerationOutput,
    GenerationValidationResult,
    QuestionSpec,
    REGEN_REASON_ORIGINALITY_TOO_SIMILAR,
)
from export import HwpxExportEngine, HwpxExportError, HwpxExportResult
from generation.adapter.codex_cli import CodexAdapterResult
from validation import GenerationValidator


class GenerationAdapter(Protocol):
    def generate(
        self,
        question_spec: QuestionSpec | Mapping[str, Any],
        *,
        constraints: Mapping[str, Any] | None = None,
    ) -> CodexAdapterResult:
        ...


class RunStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    CODEX_PARSE_FAILED = "codex_parse_failed"
    VALIDATION_FAILED = "validation_failed"
    SIMILARITY_FAILED = "similarity_failed"
    ACCEPTED = "accepted"
    EXPORT_FAILED = "export_failed"
    EXPORT_SUCCEEDED = "export_succeeded"


@dataclass(frozen=True)
class GenerationForm:
    difficulty: str
    subject: str
    topic_major: str
    topic_minor: str
    topic_detail: str
    question_format: str
    style: str
    quantity: int
    output_type: str
    template_path: str

    def to_question_spec(self) -> QuestionSpec:
        if self.quantity < 1:
            raise ValueError("quantity must be >= 1.")

        format_map = {
            "5-choice": "multiple_choice",
            "short-answer": "short_answer",
            "multiple_choice": "multiple_choice",
            "short_answer": "short_answer",
        }
        question_type = format_map.get(self.question_format)
        if question_type is None:
            raise ValueError("question_format must be one of: 5-choice, short-answer.")

        output_map = {
            "problem_only": "questions_only",
            "problem_answer": "questions_with_answers",
            "problem_answer_solution": "questions_with_solutions",
            "questions_only": "questions_only",
            "questions_with_answers": "questions_with_answers",
            "questions_with_solutions": "questions_with_solutions",
        }
        output_format = output_map.get(self.output_type)
        if output_format is None:
            raise ValueError("output_type is not supported.")

        return QuestionSpec(
            subject=self.subject,
            topic=self.topic_major,
            difficulty=self.difficulty,
            question_type=question_type,
            question_count=self.quantity,
            style=self.style,
            include_explanation=output_format == "questions_with_solutions",
            output_format=output_format,
            metadata={
                "topic": {
                    "major": self.topic_major,
                    "minor": self.topic_minor,
                    "detail": self.topic_detail,
                },
                "ui_output_type": self.output_type,
                "template_path": self.template_path,
            },
        )


@dataclass(frozen=True)
class CodexAttemptLog:
    attempt: int
    status: str
    returncode: int | None
    parse_error: str | None
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ShellState:
    status: RunStatus = RunStatus.IDLE
    last_error: str | None = None
    validation_result: GenerationValidationResult | None = None
    generation_output: CodexGenerationOutput | None = None
    export_result: HwpxExportResult | None = None
    codex_logs: tuple[CodexAttemptLog, ...] = ()
    run_count: int = 0


@dataclass
class ProductShellApp:
    adapter: GenerationAdapter
    validator: GenerationValidator
    exporter: HwpxExportEngine
    reference_corpus: Sequence[str] = ()
    state: ShellState = field(default_factory=ShellState)
    _last_form: GenerationForm | None = field(default=None, init=False, repr=False)

    def start_generation(
        self,
        form: GenerationForm,
        *,
        constraints: Mapping[str, Any] | None = None,
    ) -> ShellState:
        self._last_form = form
        self.state = ShellState(status=RunStatus.RUNNING, run_count=self.state.run_count + 1)
        spec = form.to_question_spec()

        adapter_result = self.adapter.generate(spec, constraints=constraints or {})
        logs = _load_codex_attempt_logs(adapter_result.artifacts_dir, adapter_result.attempt_count)
        if not adapter_result.success or adapter_result.parsed_output is None:
            self.state = ShellState(
                status=RunStatus.CODEX_PARSE_FAILED,
                last_error=adapter_result.parse_error or "Codex parsing failed.",
                codex_logs=logs,
                run_count=self.state.run_count,
            )
            return self.state

        validation = self.validator.validate_output(
            adapter_result.parsed_output,
            reference_corpus=self.reference_corpus,
        )
        if not validation.passed:
            status = (
                RunStatus.SIMILARITY_FAILED
                if REGEN_REASON_ORIGINALITY_TOO_SIMILAR in validation.retry_reason_codes
                else RunStatus.VALIDATION_FAILED
            )
            self.state = ShellState(
                status=status,
                last_error="Validation rejected generated output.",
                validation_result=validation,
                generation_output=adapter_result.parsed_output,
                codex_logs=logs,
                run_count=self.state.run_count,
            )
            return self.state

        self.state = ShellState(
            status=RunStatus.ACCEPTED,
            validation_result=validation,
            generation_output=adapter_result.parsed_output,
            codex_logs=logs,
            run_count=self.state.run_count,
        )
        return self.state

    def regenerate(self, *, constraints: Mapping[str, Any] | None = None) -> ShellState:
        if self._last_form is None:
            raise RuntimeError("Cannot regenerate before an initial generation run.")
        return self.start_generation(self._last_form, constraints=constraints)

    def preview(self) -> str:
        if self.state.generation_output is None:
            raise RuntimeError("No accepted generation output available for preview.")
        lines: list[str] = []
        for index, question in enumerate(self.state.generation_output.questions, start=1):
            lines.append(f"{index}. {question.stem}")
            if question.choices:
                for choice_index, choice in enumerate(question.choices, start=1):
                    lines.append(f"  {choice_index}) {choice}")
            lines.append(f"  answer: {question.answer}")
            if question.explanation:
                lines.append(f"  explanation: {question.explanation}")
        return "\n".join(lines)

    def export_hwpx(
        self,
        *,
        output_path: str | Path,
        extra_placeholders: Mapping[str, str] | None = None,
    ) -> ShellState:
        if self.state.generation_output is None:
            raise RuntimeError("Cannot export before generation output is accepted.")
        if self._last_form is None:
            raise RuntimeError("Missing form context required to resolve template path.")

        try:
            result = self.exporter.render(
                template_path=self._last_form.template_path,
                output_path=output_path,
                generation_output=self.state.generation_output,
                extra_placeholders=extra_placeholders,
            )
            self.state = ShellState(
                status=RunStatus.EXPORT_SUCCEEDED,
                validation_result=self.state.validation_result,
                generation_output=self.state.generation_output,
                export_result=result,
                codex_logs=self.state.codex_logs,
                run_count=self.state.run_count,
            )
            return self.state
        except (HwpxExportError, OSError, ValueError) as exc:
            self.state = ShellState(
                status=RunStatus.EXPORT_FAILED,
                last_error=str(exc),
                validation_result=self.state.validation_result,
                generation_output=self.state.generation_output,
                codex_logs=self.state.codex_logs,
                run_count=self.state.run_count,
            )
            return self.state


def _load_codex_attempt_logs(root: Path, attempt_count: int) -> tuple[CodexAttemptLog, ...]:
    logs: list[CodexAttemptLog] = []
    for attempt in range(1, attempt_count + 1):
        attempt_dir = root / f"attempt_{attempt:02d}"
        run_path = attempt_dir / "run.log"
        stdout_path = attempt_dir / "stdout.log"
        stderr_path = attempt_dir / "stderr.log"

        run_payload: dict[str, Any] = {}
        if run_path.exists():
            run_payload = json.loads(run_path.read_text(encoding="utf-8"))
        logs.append(
            CodexAttemptLog(
                attempt=attempt,
                status=str(run_payload.get("status", "unknown")),
                returncode=_int_or_none(run_payload.get("returncode")),
                parse_error=_str_or_none(run_payload.get("parse_error")),
                stdout=stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else "",
                stderr=stderr_path.read_text(encoding="utf-8") if stderr_path.exists() else "",
            )
        )
    return tuple(logs)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
