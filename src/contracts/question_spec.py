from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


QUESTION_SPEC_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "subject",
        "topic",
        "difficulty",
        "question_type",
        "question_count",
    ],
    "additionalProperties": True,
    "properties": {
        "subject": {"type": "string", "minLength": 1},
        "topic": {"type": "string", "minLength": 1},
        "difficulty": {"type": "string", "minLength": 1},
        "question_type": {"type": "string", "enum": ["multiple_choice", "short_answer"]},
        "question_count": {"type": "integer", "minimum": 1},
        "style": {"type": "string"},
        "include_explanation": {"type": "boolean"},
        "output_format": {
            "type": "string",
            "enum": ["questions_only", "questions_with_answers", "questions_with_solutions"],
        },
        "metadata": {"type": "object"},
    },
}


@dataclass(frozen=True)
class QuestionSpec:
    subject: str
    topic: str
    difficulty: str
    question_type: str
    question_count: int
    style: str | None = None
    include_explanation: bool = False
    output_format: str = "questions_with_answers"
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QuestionSpec":
        required = ("subject", "topic", "difficulty", "question_type", "question_count")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"Missing required question spec fields: {', '.join(missing)}")

        question_type = str(data["question_type"])
        if question_type not in {"multiple_choice", "short_answer"}:
            raise ValueError("question_type must be 'multiple_choice' or 'short_answer'.")

        count = int(data["question_count"])
        if count < 1:
            raise ValueError("question_count must be >= 1.")

        output_format = str(data.get("output_format", "questions_with_answers"))
        allowed_output_formats = {
            "questions_only",
            "questions_with_answers",
            "questions_with_solutions",
        }
        if output_format not in allowed_output_formats:
            raise ValueError(
                "output_format must be one of: questions_only, questions_with_answers, "
                "questions_with_solutions."
            )

        metadata_obj = data.get("metadata")
        if metadata_obj is not None and not isinstance(metadata_obj, Mapping):
            raise ValueError("metadata must be an object when provided.")

        return cls(
            subject=str(data["subject"]),
            topic=str(data["topic"]),
            difficulty=str(data["difficulty"]),
            question_type=question_type,
            question_count=count,
            style=(None if data.get("style") is None else str(data["style"])),
            include_explanation=bool(data.get("include_explanation", False)),
            output_format=output_format,
            metadata=(None if metadata_obj is None else dict(metadata_obj)),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "subject": self.subject,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "question_type": self.question_type,
            "question_count": self.question_count,
            "include_explanation": self.include_explanation,
            "output_format": self.output_format,
        }
        if self.style is not None:
            payload["style"] = self.style
        if self.metadata is not None:
            payload["metadata"] = self.metadata
        return payload

