"""Core JSON contracts used by generation adapters."""

from .codex_output import CODEX_OUTPUT_JSON_SCHEMA, CodexGenerationOutput, GeneratedQuestion
from .question_spec import QUESTION_SPEC_JSON_SCHEMA, QuestionSpec
from .validation import (
    MATH_VERIFICATION_JSON_SCHEMA,
    ORIGINALITY_REPORT_JSON_SCHEMA,
    REGENERATION_REASON_CODES,
    REGEN_REASON_ANSWER_NOT_UNIQUE,
    REGEN_REASON_FORMAT_INVALID,
    REGEN_REASON_MATH_INCONSISTENT,
    REGEN_REASON_ORIGINALITY_TOO_SIMILAR,
    REGEN_REASON_RETRY_LIMIT_REACHED,
    VALIDATION_RESULT_JSON_SCHEMA,
    GenerationValidationResult,
    MathVerification,
    OriginalityReport,
    QuestionValidationResult,
    ValidationFailure,
)

__all__ = [
    "CODEX_OUTPUT_JSON_SCHEMA",
    "QUESTION_SPEC_JSON_SCHEMA",
    "VALIDATION_RESULT_JSON_SCHEMA",
    "ORIGINALITY_REPORT_JSON_SCHEMA",
    "MATH_VERIFICATION_JSON_SCHEMA",
    "REGENERATION_REASON_CODES",
    "REGEN_REASON_FORMAT_INVALID",
    "REGEN_REASON_ANSWER_NOT_UNIQUE",
    "REGEN_REASON_MATH_INCONSISTENT",
    "REGEN_REASON_ORIGINALITY_TOO_SIMILAR",
    "REGEN_REASON_RETRY_LIMIT_REACHED",
    "CodexGenerationOutput",
    "GeneratedQuestion",
    "QuestionSpec",
    "GenerationValidationResult",
    "QuestionValidationResult",
    "ValidationFailure",
    "OriginalityReport",
    "MathVerification",
]

