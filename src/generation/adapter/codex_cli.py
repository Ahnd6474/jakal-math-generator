from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Protocol

from contracts import CODEX_OUTPUT_JSON_SCHEMA, CodexGenerationOutput, QuestionSpec

from .config import CodexExecutionConfig
from .prompts import load_prompt_template, render_prompt


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, *, command: tuple[str, ...], input_text: str, timeout_seconds: int) -> CommandResult:
        ...


class SubprocessCommandRunner:
    def run(self, *, command: tuple[str, ...], input_text: str, timeout_seconds: int) -> CommandResult:
        completed = subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


@dataclass(frozen=True)
class CodexAdapterResult:
    success: bool
    attempt_count: int
    artifacts_dir: Path
    parsed_output: CodexGenerationOutput | None
    parse_error: str | None


class CodexCliAdapter:
    def __init__(self, config: CodexExecutionConfig, runner: CommandRunner | None = None) -> None:
        self._config = config
        self._runner = runner or SubprocessCommandRunner()
        self._generation_template = load_prompt_template(self._config.prompt_template_path)
        self._repair_template = load_prompt_template(self._config.repair_prompt_template_path)

    def generate(
        self,
        question_spec: QuestionSpec | Mapping[str, Any],
        *,
        constraints: Mapping[str, Any] | None = None,
    ) -> CodexAdapterResult:
        spec_obj = (
            question_spec
            if isinstance(question_spec, QuestionSpec)
            else QuestionSpec.from_dict(dict(question_spec))
        )
        constraints_obj = dict(constraints or {})
        command = self._config.command + self._config.extra_args

        request_id = _utc_timestamp()
        request_root = self._config.artifacts_root / request_id
        request_root.mkdir(parents=True, exist_ok=True)

        previous_stdout: str | None = None
        parse_error: str | None = None

        for attempt in range(1, self._config.max_attempts + 1):
            attempt_dir = request_root / f"attempt_{attempt:02d}"
            attempt_dir.mkdir(parents=True, exist_ok=True)

            prompt_template = self._generation_template if attempt == 1 else self._repair_template
            prompt = render_prompt(
                template=prompt_template,
                question_spec=spec_obj.to_dict(),
                constraints=constraints_obj,
                output_schema=CODEX_OUTPUT_JSON_SCHEMA,
                previous_stdout=previous_stdout,
                parse_error=parse_error,
            )
            request_payload = self._build_json_request(prompt)
            request_json = json.dumps(request_payload, ensure_ascii=False, indent=2)
            (attempt_dir / "request.json").write_text(request_json, encoding="utf-8")

            result = self._runner.run(
                command=command,
                input_text=request_json,
                timeout_seconds=self._config.timeout_seconds,
            )
            (attempt_dir / "stdout.log").write_text(result.stdout, encoding="utf-8")
            (attempt_dir / "stderr.log").write_text(result.stderr, encoding="utf-8")

            parsed_output: CodexGenerationOutput | None = None
            try:
                payload = _parse_json_only_stdout(result.stdout)
                parsed_output = CodexGenerationOutput.from_dict(payload)
                (attempt_dir / "parsed_output.json").write_text(
                    json.dumps(parsed_output.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._write_run_log(
                    attempt_dir=attempt_dir,
                    command=command,
                    returncode=result.returncode,
                    status="ok",
                    parse_error=None,
                )
                return CodexAdapterResult(
                    success=True,
                    attempt_count=attempt,
                    artifacts_dir=request_root,
                    parsed_output=parsed_output,
                    parse_error=None,
                )
            except (json.JSONDecodeError, ValueError) as exc:
                parse_error = str(exc)
                previous_stdout = result.stdout
                (attempt_dir / "parse_failure.log").write_text(parse_error, encoding="utf-8")
                self._write_run_log(
                    attempt_dir=attempt_dir,
                    command=command,
                    returncode=result.returncode,
                    status="parse_failure",
                    parse_error=parse_error,
                )

        return CodexAdapterResult(
            success=False,
            attempt_count=self._config.max_attempts,
            artifacts_dir=request_root,
            parsed_output=None,
            parse_error=parse_error or "Unknown parse failure.",
        )

    def _build_json_request(self, prompt: str) -> dict[str, Any]:
        if not self._config.enforce_json_only:
            raise ValueError("JSON-only request mode is required.")
        return {
            "mode": self._config.mode,
            "response_format": {"type": "json_object"},
            "prompt": prompt,
        }

    @staticmethod
    def _write_run_log(
        *,
        attempt_dir: Path,
        command: tuple[str, ...],
        returncode: int,
        status: str,
        parse_error: str | None,
    ) -> None:
        metadata = {
            "timestamp": _utc_timestamp(),
            "command": list(command),
            "returncode": returncode,
            "status": status,
            "parse_error": parse_error,
        }
        (attempt_dir / "run.log").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _parse_json_only_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("Codex stdout is empty.")

    if text.startswith("```"):
        text = _strip_code_fence(text)

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = json.loads(_extract_first_json_object(text))

    if not isinstance(payload, dict):
        raise ValueError("Codex output must be a JSON object.")
    return payload


def _strip_code_fence(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_first_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise json.JSONDecodeError("No JSON object start token found.", text, 0)

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "\"":
                in_string = False
            continue

        if ch == "\"":
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    raise json.JSONDecodeError("Could not find a balanced JSON object.", text, start)


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")

