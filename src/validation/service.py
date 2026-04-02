from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from contracts import (
    CodexGenerationOutput,
    GeneratedQuestion,
    GenerationValidationResult,
    MathVerification,
    OriginalityReport,
    QuestionValidationResult,
    REGENERATION_REASON_CODES,
    REGEN_REASON_ANSWER_NOT_UNIQUE,
    REGEN_REASON_FORMAT_INVALID,
    REGEN_REASON_MATH_INCONSISTENT,
    REGEN_REASON_ORIGINALITY_TOO_SIMILAR,
    ValidationFailure,
)


_TEXT_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_SHORT_ANSWER_MULTI_DELIMITERS: tuple[str, ...] = (",", ";", " 또는 ", " or ")


@dataclass(frozen=True)
class ValidationConfig:
    originality_threshold: float = 0.85

    def __post_init__(self) -> None:
        if not (0.0 <= self.originality_threshold <= 1.0):
            raise ValueError("originality_threshold must be between 0.0 and 1.0.")


class GenerationValidator:
    def __init__(self, config: ValidationConfig | None = None) -> None:
        self._config = config or ValidationConfig()

    def validate_output(
        self,
        output: CodexGenerationOutput | Mapping[str, Any],
        *,
        reference_corpus: Sequence[str] | None = None,
    ) -> GenerationValidationResult:
        output_obj = output if isinstance(output, CodexGenerationOutput) else CodexGenerationOutput.from_dict(output)
        corpus = tuple(reference_corpus or ())
        peer_stems = tuple(question.stem for question in output_obj.questions)

        results = tuple(
            self.validate_question(
                question,
                reference_corpus=corpus,
                peer_stems=peer_stems,
            )
            for question in output_obj.questions
        )
        aggregated_reasons = self._aggregate_retry_reasons(results)
        passed = all(item.passed for item in results)
        return GenerationValidationResult(
            passed=passed,
            questions=results,
            retry_reason_codes=aggregated_reasons,
        )

    def validate_question(
        self,
        question: GeneratedQuestion | Mapping[str, Any],
        *,
        reference_corpus: Sequence[str] | None = None,
        peer_stems: Sequence[str] | None = None,
    ) -> QuestionValidationResult:
        question_obj = question if isinstance(question, GeneratedQuestion) else GeneratedQuestion.from_dict(question)
        failures: list[ValidationFailure] = []

        format_passed = self._validate_format(question_obj, failures)
        uniqueness_passed = self._validate_answer_uniqueness(question_obj, failures)
        math_verification = self._verify_math(question_obj, failures)
        originality_report = self._check_originality(
            question_obj,
            reference_corpus=reference_corpus or (),
            peer_stems=peer_stems or (),
            failures=failures,
        )

        scores = {
            "format": 1.0 if format_passed else 0.0,
            "answer_uniqueness": 1.0 if uniqueness_passed else 0.0,
            "math": math_verification.score,
            "originality": max(0.0, 1.0 - originality_report.max_similarity),
        }
        passed = not failures
        return QuestionValidationResult(
            question_id=question_obj.question_id,
            passed=passed,
            scores=scores,
            failures=tuple(failures),
            originality_report=originality_report,
            math_verification=math_verification,
        )

    @staticmethod
    def _validate_format(question: GeneratedQuestion, failures: list[ValidationFailure]) -> bool:
        if not question.stem.strip():
            failures.append(
                ValidationFailure(
                    reason_code=REGEN_REASON_FORMAT_INVALID,
                    category="format",
                    message="Question stem must be non-empty.",
                )
            )
            return False
        if any(not choice.strip() for choice in question.choices):
            failures.append(
                ValidationFailure(
                    reason_code=REGEN_REASON_FORMAT_INVALID,
                    category="format",
                    message="Choices cannot include empty strings.",
                )
            )
            return False
        if question.choices and len(question.choices) < 2:
            failures.append(
                ValidationFailure(
                    reason_code=REGEN_REASON_FORMAT_INVALID,
                    category="format",
                    message="Multiple-choice items must include at least two choices.",
                )
            )
            return False
        if question.answer is None:
            failures.append(
                ValidationFailure(
                    reason_code=REGEN_REASON_FORMAT_INVALID,
                    category="format",
                    message="Question answer must be present.",
                )
            )
            return False
        return True

    @staticmethod
    def _validate_answer_uniqueness(question: GeneratedQuestion, failures: list[ValidationFailure]) -> bool:
        answer_text = _resolve_answer_text(question)
        if not question.choices:
            lowered = answer_text.lower()
            if any(token in lowered for token in _SHORT_ANSWER_MULTI_DELIMITERS):
                failures.append(
                    ValidationFailure(
                        reason_code=REGEN_REASON_ANSWER_NOT_UNIQUE,
                        category="answer_uniqueness",
                        message="Short-answer output appears to include multiple answers.",
                        details={"answer": answer_text},
                    )
                )
                return False
            return True

        if not answer_text:
            failures.append(
                ValidationFailure(
                    reason_code=REGEN_REASON_ANSWER_NOT_UNIQUE,
                    category="answer_uniqueness",
                    message="Answer could not be resolved to a unique choice.",
                )
            )
            return False

        normalized_answer = _normalize_text(answer_text)
        normalized_choices = [_normalize_text(choice) for choice in question.choices]
        matches = [choice for choice in normalized_choices if choice == normalized_answer]
        if len(matches) != 1:
            failures.append(
                ValidationFailure(
                    reason_code=REGEN_REASON_ANSWER_NOT_UNIQUE,
                    category="answer_uniqueness",
                    message="Answer does not map to exactly one choice.",
                    details={"resolved_answer": answer_text, "match_count": len(matches)},
                )
            )
            return False
        return True

    @staticmethod
    def _verify_math(question: GeneratedQuestion, failures: list[ValidationFailure]) -> MathVerification:
        if not isinstance(question.metadata, Mapping):
            return MathVerification(status="not_evaluated", score=0.5, message=None)
        meta = question.metadata.get("math_verification")
        if not isinstance(meta, Mapping):
            return MathVerification(status="not_evaluated", score=0.5, message=None)

        if "consistent" in meta and isinstance(meta["consistent"], bool):
            consistent = bool(meta["consistent"])
        else:
            status = str(meta.get("status", "")).lower()
            if status in {"pass", "ok", "true"}:
                consistent = True
            elif status in {"fail", "false", "error"}:
                consistent = False
            else:
                return MathVerification(status="not_evaluated", score=0.5, message=None)

        message = None if meta.get("message") is None else str(meta.get("message"))
        if consistent:
            return MathVerification(status="pass", score=1.0, message=message)

        failures.append(
            ValidationFailure(
                reason_code=REGEN_REASON_MATH_INCONSISTENT,
                category="math",
                message=message or "Question failed mathematical consistency check.",
            )
        )
        return MathVerification(status="fail", score=0.0, message=message)

    def _check_originality(
        self,
        question: GeneratedQuestion,
        *,
        reference_corpus: Sequence[str],
        peer_stems: Sequence[str],
        failures: list[ValidationFailure],
    ) -> OriginalityReport:
        max_similarity = 0.0
        matched_reference: str | None = None
        matched_source: str | None = None

        for candidate in reference_corpus:
            score = _jaccard_similarity(question.stem, candidate)
            if score > max_similarity:
                max_similarity = score
                matched_reference = candidate
                matched_source = "reference_corpus"

        for candidate in peer_stems:
            if candidate == question.stem:
                continue
            score = _jaccard_similarity(question.stem, candidate)
            if score > max_similarity:
                max_similarity = score
                matched_reference = candidate
                matched_source = "batch_generation"

        is_original = max_similarity < self._config.originality_threshold
        if not is_original:
            failures.append(
                ValidationFailure(
                    reason_code=REGEN_REASON_ORIGINALITY_TOO_SIMILAR,
                    category="originality",
                    message="Question is too similar to existing corpus content.",
                    details={
                        "max_similarity": max_similarity,
                        "threshold": self._config.originality_threshold,
                        "matched_source": matched_source,
                    },
                )
            )

        return OriginalityReport(
            is_original=is_original,
            max_similarity=max_similarity,
            threshold=self._config.originality_threshold,
            matched_reference=matched_reference,
            matched_source=matched_source,
        )

    @staticmethod
    def _aggregate_retry_reasons(results: Sequence[QuestionValidationResult]) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for reason_code in REGENERATION_REASON_CODES:
            if reason_code not in seen and any(
                reason_code == failure.reason_code
                for result in results
                for failure in result.failures
            ):
                seen.add(reason_code)
                ordered.append(reason_code)
        return tuple(ordered)


def _resolve_answer_text(question: GeneratedQuestion) -> str:
    if question.answer is None:
        return ""
    if not question.choices:
        return str(question.answer).strip()

    if isinstance(question.answer, int):
        idx = question.answer - 1
        if 0 <= idx < len(question.choices):
            return question.choices[idx]
        return ""

    answer_text = str(question.answer).strip()
    if answer_text.isdigit():
        idx = int(answer_text) - 1
        if 0 <= idx < len(question.choices):
            return question.choices[idx]
    return answer_text


def _normalize_text(text: str) -> str:
    tokens = _TEXT_TOKEN_RE.findall(text.lower())
    return " ".join(tokens)


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = set(_TEXT_TOKEN_RE.findall(left.lower()))
    right_tokens = set(_TEXT_TOKEN_RE.findall(right.lower()))
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    intersection = left_tokens & right_tokens
    return len(intersection) / len(union)
