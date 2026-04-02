from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


REGEN_REASON_FORMAT_INVALID = "format_invalid"
REGEN_REASON_ANSWER_NOT_UNIQUE = "answer_not_unique"
REGEN_REASON_MATH_INCONSISTENT = "math_inconsistent"
REGEN_REASON_ORIGINALITY_TOO_SIMILAR = "originality_too_similar"
REGEN_REASON_RETRY_LIMIT_REACHED = "retry_limit_reached"

REGENERATION_REASON_CODES: tuple[str, ...] = (
    REGEN_REASON_FORMAT_INVALID,
    REGEN_REASON_ANSWER_NOT_UNIQUE,
    REGEN_REASON_MATH_INCONSISTENT,
    REGEN_REASON_ORIGINALITY_TOO_SIMILAR,
    REGEN_REASON_RETRY_LIMIT_REACHED,
)


ORIGINALITY_REPORT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["is_original", "max_similarity", "threshold"],
    "additionalProperties": True,
    "properties": {
        "is_original": {"type": "boolean"},
        "max_similarity": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "matched_reference": {"type": ["string", "null"]},
        "matched_source": {"type": ["string", "null"]},
    },
}

MATH_VERIFICATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["status", "score"],
    "additionalProperties": True,
    "properties": {
        "status": {"type": "string", "enum": ["pass", "fail", "not_evaluated"]},
        "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "message": {"type": ["string", "null"]},
    },
}

VALIDATION_RESULT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["passed", "questions", "retry_reason_codes"],
    "additionalProperties": True,
    "properties": {
        "passed": {"type": "boolean"},
        "retry_reason_codes": {
            "type": "array",
            "items": {"type": "string", "enum": list(REGENERATION_REASON_CODES)},
            "uniqueItems": True,
        },
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "question_id",
                    "passed",
                    "scores",
                    "failures",
                    "originality_report",
                    "math_verification",
                ],
                "additionalProperties": True,
                "properties": {
                    "question_id": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "scores": {
                        "type": "object",
                        "required": ["format", "answer_uniqueness", "math", "originality"],
                        "additionalProperties": False,
                        "properties": {
                            "format": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                            "answer_uniqueness": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                            "math": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                            "originality": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        },
                    },
                    "failures": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["reason_code", "category", "message"],
                            "additionalProperties": True,
                            "properties": {
                                "reason_code": {
                                    "type": "string",
                                    "enum": list(REGENERATION_REASON_CODES),
                                },
                                "category": {"type": "string"},
                                "message": {"type": "string"},
                                "details": {},
                            },
                        },
                    },
                    "originality_report": ORIGINALITY_REPORT_JSON_SCHEMA,
                    "math_verification": MATH_VERIFICATION_JSON_SCHEMA,
                },
            },
        },
    },
}


@dataclass(frozen=True)
class ValidationFailure:
    reason_code: str
    category: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "reason_code": self.reason_code,
            "category": self.category,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


@dataclass(frozen=True)
class OriginalityReport:
    is_original: bool
    max_similarity: float
    threshold: float
    matched_reference: str | None = None
    matched_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_original": self.is_original,
            "max_similarity": self.max_similarity,
            "threshold": self.threshold,
            "matched_reference": self.matched_reference,
            "matched_source": self.matched_source,
        }


@dataclass(frozen=True)
class MathVerification:
    status: str
    score: float
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "score": self.score, "message": self.message}


@dataclass(frozen=True)
class QuestionValidationResult:
    question_id: str
    passed: bool
    scores: dict[str, float]
    failures: tuple[ValidationFailure, ...]
    originality_report: OriginalityReport
    math_verification: MathVerification

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "passed": self.passed,
            "scores": dict(self.scores),
            "failures": [failure.to_dict() for failure in self.failures],
            "originality_report": self.originality_report.to_dict(),
            "math_verification": self.math_verification.to_dict(),
        }


@dataclass(frozen=True)
class GenerationValidationResult:
    passed: bool
    questions: tuple[QuestionValidationResult, ...]
    retry_reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "questions": [item.to_dict() for item in self.questions],
            "retry_reason_codes": list(self.retry_reason_codes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GenerationValidationResult":
        passed = bool(data.get("passed"))
        raw_reasons = data.get("retry_reason_codes", [])
        if not isinstance(raw_reasons, list) or not all(isinstance(item, str) for item in raw_reasons):
            raise ValueError("retry_reason_codes must be an array of strings.")
        raw_questions = data.get("questions", [])
        if not isinstance(raw_questions, list):
            raise ValueError("questions must be an array.")

        parsed_questions = []
        for item in raw_questions:
            if not isinstance(item, Mapping):
                raise ValueError("Each question validation result must be an object.")
            failures = tuple(
                ValidationFailure(
                    reason_code=str(failure["reason_code"]),
                    category=str(failure["category"]),
                    message=str(failure["message"]),
                    details=(
                        dict(failure["details"])
                        if isinstance(failure.get("details"), Mapping)
                        else None
                    ),
                )
                for failure in item.get("failures", [])
            )
            parsed_questions.append(
                QuestionValidationResult(
                    question_id=str(item.get("question_id", "")),
                    passed=bool(item.get("passed", False)),
                    scores={key: float(value) for key, value in dict(item.get("scores", {})).items()},
                    failures=failures,
                    originality_report=OriginalityReport(
                        is_original=bool(item["originality_report"]["is_original"]),
                        max_similarity=float(item["originality_report"]["max_similarity"]),
                        threshold=float(item["originality_report"]["threshold"]),
                        matched_reference=item["originality_report"].get("matched_reference"),
                        matched_source=item["originality_report"].get("matched_source"),
                    ),
                    math_verification=MathVerification(
                        status=str(item["math_verification"]["status"]),
                        score=float(item["math_verification"]["score"]),
                        message=item["math_verification"].get("message"),
                    ),
                )
            )
        return cls(
            passed=passed,
            questions=tuple(parsed_questions),
            retry_reason_codes=tuple(raw_reasons),
        )
