"""Core JSON contracts used by generation adapters."""

from .codex_output import CODEX_OUTPUT_JSON_SCHEMA, CodexGenerationOutput, GeneratedQuestion
from .question_spec import QUESTION_SPEC_JSON_SCHEMA, QuestionSpec

__all__ = [
    "CODEX_OUTPUT_JSON_SCHEMA",
    "QUESTION_SPEC_JSON_SCHEMA",
    "CodexGenerationOutput",
    "GeneratedQuestion",
    "QuestionSpec",
]

