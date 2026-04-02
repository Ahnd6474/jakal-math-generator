from __future__ import annotations

from contracts import (
    CodexGenerationOutput,
    REGEN_REASON_ORIGINALITY_TOO_SIMILAR,
    REGEN_REASON_RETRY_LIMIT_REACHED,
)
from generation.retry import RetryController, RetryControllerConfig
from validation import GenerationValidator, ValidationConfig


def _output(question_id: str, stem: str) -> CodexGenerationOutput:
    return CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": question_id,
                    "stem": stem,
                    "answer": "1",
                }
            ]
        }
    )


def test_retry_controller_accepts_after_regeneration() -> None:
    validator = GenerationValidator(ValidationConfig(originality_threshold=0.8))
    controller = RetryController(RetryControllerConfig(max_retries=2))

    attempts = [
        _output("Q1", "중복 가능성이 큰 문장"),
        _output("Q2", "충분히 새롭고 다른 문장"),
    ]

    def generator() -> CodexGenerationOutput:
        if not attempts:
            raise AssertionError("No more attempts queued.")
        return attempts.pop(0)

    result = controller.run(
        generator=generator,
        validator=validator,
        reference_corpus=["중복 가능성이 큰 문장"],
    )

    assert result.status == "accepted"
    assert result.attempts_made == 2
    assert result.accepted_output is not None
    assert result.history[0].accepted is False
    assert REGEN_REASON_ORIGINALITY_TOO_SIMILAR in result.history[0].retry_reason_codes


def test_retry_controller_stops_at_configured_limit() -> None:
    validator = GenerationValidator(ValidationConfig(originality_threshold=0.8))
    controller = RetryController(RetryControllerConfig(max_retries=1))

    def generator() -> CodexGenerationOutput:
        return _output("QX", "동일 문장")

    result = controller.run(
        generator=generator,
        validator=validator,
        reference_corpus=["동일 문장"],
    )

    assert result.status == "retry_limit_reached"
    assert result.attempts_made == 2
    assert result.accepted_output is None
    assert result.final_retry_reason_codes[-1] == REGEN_REASON_RETRY_LIMIT_REACHED
    assert REGEN_REASON_ORIGINALITY_TOO_SIMILAR in result.final_retry_reason_codes
