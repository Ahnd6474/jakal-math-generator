from __future__ import annotations

import json
from pathlib import Path

from generation.adapter import CodexCliAdapter, CodexExecutionConfig
from generation.adapter.codex_cli import CommandResult


REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeRunner:
    def __init__(self, responses: list[CommandResult]) -> None:
        self._responses = responses
        self.inputs: list[str] = []
        self.commands: list[tuple[str, ...]] = []

    def run(self, *, command: tuple[str, ...], input_text: str, timeout_seconds: int) -> CommandResult:
        self.commands.append(command)
        self.inputs.append(input_text)
        if not self._responses:
            raise AssertionError("FakeRunner has no queued responses.")
        return self._responses.pop(0)


def _write_config(tmp_path: Path, *, max_attempts: int) -> Path:
    config_path = tmp_path / "execution.json"
    config = {
        "mode": "problem_generation",
        "command": ["codex"],
        "extra_args": ["run", "--json-input"],
        "prompt_template_path": "prompts/codex/generation_prompt.txt",
        "repair_prompt_template_path": "prompts/codex/repair_prompt.txt",
        "artifacts_root": str((tmp_path / "artifacts").as_posix()),
        "timeout_seconds": 10,
        "max_attempts": max_attempts,
        "enforce_json_only": True,
    }
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config_path


def _sample_spec() -> dict[str, object]:
    return {
        "subject": "미적분",
        "topic": "함수의 극한",
        "difficulty": "중간 4점",
        "question_type": "multiple_choice",
        "question_count": 1,
        "include_explanation": True,
        "output_format": "questions_with_solutions",
    }


def test_codex_adapter_writes_json_request_and_separated_artifacts(tmp_path: Path) -> None:
    config = CodexExecutionConfig.from_path(_write_config(tmp_path, max_attempts=1), repo_root=REPO_ROOT)
    runner = FakeRunner(
        [
            CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "questions": [
                            {
                                "id": "Q1",
                                "stem": "극한을 구하시오.",
                                "choices": ["1", "2", "3", "4", "5"],
                                "answer": "3",
                                "explanation": "계산하면 3.",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                stderr="",
            )
        ]
    )
    adapter = CodexCliAdapter(config, runner=runner)

    result = adapter.generate(_sample_spec(), constraints={"novelty_required": True})

    assert result.success is True
    assert result.parsed_output is not None
    assert result.parsed_output.questions[0].question_id == "Q1"

    assert len(runner.inputs) == 1
    request_payload = json.loads(runner.inputs[0])
    assert request_payload["mode"] == "problem_generation"
    assert request_payload["response_format"]["type"] == "json_object"

    attempt_dir = result.artifacts_dir / "attempt_01"
    assert (attempt_dir / "request.json").exists()
    assert (attempt_dir / "stdout.log").exists()
    assert (attempt_dir / "stderr.log").exists()
    assert (attempt_dir / "run.log").exists()
    assert (attempt_dir / "parsed_output.json").exists()


def test_codex_adapter_retries_with_repair_prompt_on_parse_failure(tmp_path: Path) -> None:
    config = CodexExecutionConfig.from_path(_write_config(tmp_path, max_attempts=2), repo_root=REPO_ROOT)
    runner = FakeRunner(
        [
            CommandResult(returncode=0, stdout="not-json", stderr=""),
            CommandResult(
                returncode=0,
                stdout="```json\n{\"questions\":[{\"id\":\"Q2\",\"stem\":\"문제\",\"answer\":\"1\"}]}\n```",
                stderr="",
            ),
        ]
    )
    adapter = CodexCliAdapter(config, runner=runner)

    result = adapter.generate(_sample_spec(), constraints={"avoid_duplicate_exam_patterns": True})

    assert result.success is True
    assert result.attempt_count == 2
    assert result.parsed_output is not None
    assert result.parsed_output.questions[0].question_id == "Q2"

    assert len(runner.inputs) == 2
    second_request = json.loads(runner.inputs[1])
    assert "Parse error" in second_request["prompt"]
    assert "not-json" in second_request["prompt"]

    first_attempt = result.artifacts_dir / "attempt_01"
    second_attempt = result.artifacts_dir / "attempt_02"
    assert (first_attempt / "parse_failure.log").exists()
    assert (second_attempt / "parsed_output.json").exists()


def test_codex_adapter_returns_parse_failure_after_max_attempts(tmp_path: Path) -> None:
    config = CodexExecutionConfig.from_path(_write_config(tmp_path, max_attempts=2), repo_root=REPO_ROOT)
    runner = FakeRunner(
        [
            CommandResult(returncode=0, stdout="oops", stderr=""),
            CommandResult(returncode=0, stdout="still not valid", stderr=""),
        ]
    )
    adapter = CodexCliAdapter(config, runner=runner)

    result = adapter.generate(_sample_spec(), constraints={})

    assert result.success is False
    assert result.parsed_output is None
    assert result.parse_error is not None
    assert result.attempt_count == 2
    assert (result.artifacts_dir / "attempt_01" / "parse_failure.log").exists()
    assert (result.artifacts_dir / "attempt_02" / "parse_failure.log").exists()

