from __future__ import annotations

from contracts import (
    CodexGenerationOutput,
    REGEN_REASON_ANSWER_NOT_UNIQUE,
    REGEN_REASON_FORMAT_INVALID,
    REGEN_REASON_MATH_INCONSISTENT,
    REGEN_REASON_ORIGINALITY_TOO_SIMILAR,
)
from validation import GenerationValidator, ValidationConfig


def _single_question_output(question: dict[str, object]) -> CodexGenerationOutput:
    return CodexGenerationOutput.from_dict({"questions": [question]})


def test_generation_validation_passes_valid_question() -> None:
    validator = GenerationValidator(ValidationConfig(originality_threshold=0.9))
    output = _single_question_output(
        {
            "id": "Q1",
            "stem": "함수 f(x)=x^2-1 일 때 f(3)의 값을 구하시오.",
            "choices": ["6", "7", "8", "9", "10"],
            "answer": "4",
            "metadata": {"math_verification": {"consistent": True, "message": "Checked by solver."}},
        }
    )

    result = validator.validate_output(output, reference_corpus=["전혀 다른 문항입니다."])

    assert result.passed is True
    assert result.retry_reason_codes == ()
    question = result.questions[0]
    assert question.passed is True
    assert question.scores["format"] == 1.0
    assert question.scores["answer_uniqueness"] == 1.0
    assert question.scores["math"] == 1.0
    assert question.originality_report.is_original is True


def test_generation_validation_flags_format_failure() -> None:
    validator = GenerationValidator()
    output = _single_question_output(
        {
            "id": "Q2",
            "stem": "형식 검증 문항",
            "choices": ["", "2"],
            "answer": "1",
        }
    )

    result = validator.validate_output(output)

    assert result.passed is False
    assert REGEN_REASON_FORMAT_INVALID in result.retry_reason_codes


def test_generation_validation_flags_answer_uniqueness_failure() -> None:
    validator = GenerationValidator()
    output = _single_question_output(
        {
            "id": "Q3",
            "stem": "중복 정답 검증 문항",
            "choices": ["2", "2", "3", "4", "5"],
            "answer": "2",
        }
    )

    result = validator.validate_output(output)

    assert result.passed is False
    assert REGEN_REASON_ANSWER_NOT_UNIQUE in result.retry_reason_codes


def test_generation_validation_flags_math_consistency_failure() -> None:
    validator = GenerationValidator()
    output = _single_question_output(
        {
            "id": "Q4",
            "stem": "수학 검증 문항",
            "answer": "42",
            "metadata": {"math_verification": {"consistent": False, "message": "Answer mismatch."}},
        }
    )

    result = validator.validate_output(output)

    assert result.passed is False
    assert REGEN_REASON_MATH_INCONSISTENT in result.retry_reason_codes
    assert result.questions[0].math_verification.status == "fail"


def test_generation_validation_flags_originality_failure() -> None:
    validator = GenerationValidator(ValidationConfig(originality_threshold=0.7))
    stem = "함수의 극한 값이 존재할 조건을 구하시오"
    output = _single_question_output(
        {
            "id": "Q5",
            "stem": stem,
            "answer": "1",
        }
    )

    result = validator.validate_output(output, reference_corpus=[stem])

    assert result.passed is False
    assert REGEN_REASON_ORIGINALITY_TOO_SIMILAR in result.retry_reason_codes
    assert result.questions[0].originality_report.max_similarity == 1.0
