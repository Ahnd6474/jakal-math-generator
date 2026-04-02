from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence, Any

from contracts import (
    CodexGenerationOutput,
    GenerationValidationResult,
    REGEN_REASON_RETRY_LIMIT_REACHED,
)
from validation import GenerationValidator


GeneratorFn = Callable[[], CodexGenerationOutput | Mapping[str, Any]]


@dataclass(frozen=True)
class RetryControllerConfig:
    max_retries: int = 1

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0.")


@dataclass(frozen=True)
class RetryAttemptRecord:
    attempt_number: int
    validation: GenerationValidationResult
    accepted: bool
    retry_reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_number": self.attempt_number,
            "accepted": self.accepted,
            "retry_reason_codes": list(self.retry_reason_codes),
            "validation": self.validation.to_dict(),
        }


@dataclass(frozen=True)
class RetryControllerResult:
    status: str
    attempts_made: int
    history: tuple[RetryAttemptRecord, ...]
    accepted_output: CodexGenerationOutput | None
    final_retry_reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "attempts_made": self.attempts_made,
            "history": [item.to_dict() for item in self.history],
            "accepted_output": (None if self.accepted_output is None else self.accepted_output.to_dict()),
            "final_retry_reason_codes": list(self.final_retry_reason_codes),
        }


class RetryController:
    def __init__(self, config: RetryControllerConfig | None = None) -> None:
        self._config = config or RetryControllerConfig()

    def run(
        self,
        *,
        generator: GeneratorFn,
        validator: GenerationValidator,
        reference_corpus: Sequence[str] | None = None,
    ) -> RetryControllerResult:
        history: list[RetryAttemptRecord] = []
        total_attempts = self._config.max_retries + 1

        for attempt_number in range(1, total_attempts + 1):
            generated = generator()
            output = generated if isinstance(generated, CodexGenerationOutput) else CodexGenerationOutput.from_dict(generated)
            validation = validator.validate_output(output, reference_corpus=reference_corpus)
            accepted = validation.passed
            history.append(
                RetryAttemptRecord(
                    attempt_number=attempt_number,
                    validation=validation,
                    accepted=accepted,
                    retry_reason_codes=validation.retry_reason_codes,
                )
            )
            if accepted:
                return RetryControllerResult(
                    status="accepted",
                    attempts_made=attempt_number,
                    history=tuple(history),
                    accepted_output=output,
                    final_retry_reason_codes=(),
                )

        final_reasons = list(history[-1].retry_reason_codes) if history else []
        if REGEN_REASON_RETRY_LIMIT_REACHED not in final_reasons:
            final_reasons.append(REGEN_REASON_RETRY_LIMIT_REACHED)
        return RetryControllerResult(
            status="retry_limit_reached",
            attempts_made=total_attempts,
            history=tuple(history),
            accepted_output=None,
            final_retry_reason_codes=tuple(final_reasons),
        )
