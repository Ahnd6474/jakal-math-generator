from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


CODEX_OUTPUT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["questions"],
    "additionalProperties": True,
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "stem", "answer"],
                "additionalProperties": True,
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "stem": {"type": "string", "minLength": 1},
                    "choices": {"type": "array", "items": {"type": "string"}},
                    "answer": {},
                    "explanation": {"type": "string"},
                    "metadata": {"type": "object"},
                },
            },
        }
    },
}


@dataclass(frozen=True)
class GeneratedQuestion:
    question_id: str
    stem: str
    choices: tuple[str, ...]
    answer: Any
    explanation: str | None
    metadata: dict[str, Any] | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GeneratedQuestion":
        if not isinstance(data.get("id"), str) or not data["id"].strip():
            raise ValueError("Each generated question must include non-empty 'id'.")
        if not isinstance(data.get("stem"), str) or not data["stem"].strip():
            raise ValueError("Each generated question must include non-empty 'stem'.")
        if "answer" not in data:
            raise ValueError("Each generated question must include 'answer'.")

        raw_choices = data.get("choices", [])
        if raw_choices is None:
            raw_choices = []
        if not isinstance(raw_choices, list) or not all(isinstance(item, str) for item in raw_choices):
            raise ValueError("'choices' must be an array of strings when provided.")

        explanation = data.get("explanation")
        if explanation is not None and not isinstance(explanation, str):
            raise ValueError("'explanation' must be a string when provided.")

        metadata_obj = data.get("metadata")
        if metadata_obj is not None and not isinstance(metadata_obj, Mapping):
            raise ValueError("'metadata' must be an object when provided.")

        return cls(
            question_id=data["id"].strip(),
            stem=data["stem"].strip(),
            choices=tuple(raw_choices),
            answer=data["answer"],
            explanation=explanation,
            metadata=(None if metadata_obj is None else dict(metadata_obj)),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.question_id,
            "stem": self.stem,
            "answer": self.answer,
            "choices": list(self.choices),
        }
        if self.explanation is not None:
            payload["explanation"] = self.explanation
        if self.metadata is not None:
            payload["metadata"] = self.metadata
        return payload


@dataclass(frozen=True)
class CodexGenerationOutput:
    questions: tuple[GeneratedQuestion, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CodexGenerationOutput":
        raw_questions = data.get("questions")
        if not isinstance(raw_questions, list) or not raw_questions:
            raise ValueError("Codex output must include a non-empty 'questions' array.")
        parsed = tuple(GeneratedQuestion.from_dict(item) for item in raw_questions)
        return cls(questions=parsed)

    def to_dict(self) -> dict[str, Any]:
        return {"questions": [question.to_dict() for question in self.questions]}

