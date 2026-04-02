from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodexExecutionConfig:
    command: tuple[str, ...]
    extra_args: tuple[str, ...]
    prompt_template_path: Path
    repair_prompt_template_path: Path
    artifacts_root: Path
    timeout_seconds: int
    max_attempts: int
    mode: str
    enforce_json_only: bool

    @classmethod
    def from_path(
        cls,
        config_path: str | Path,
        *,
        repo_root: str | Path | None = None,
    ) -> "CodexExecutionConfig":
        path = Path(config_path)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("Codex execution config must be a JSON object.")

        resolved_repo_root = Path(repo_root) if repo_root else path.resolve().parents[2]
        return cls.from_dict(loaded, repo_root=resolved_repo_root)

    @classmethod
    def from_dict(
        cls,
        raw: dict[str, Any],
        *,
        repo_root: str | Path,
    ) -> "CodexExecutionConfig":
        root = Path(repo_root)

        command = tuple(str(part) for part in raw.get("command", ["codex"]))
        extra_args = tuple(str(part) for part in raw.get("extra_args", []))
        timeout_seconds = int(raw.get("timeout_seconds", 60))
        max_attempts = int(raw.get("max_attempts", 2))
        mode = str(raw.get("mode", "problem_generation"))
        enforce_json_only = bool(raw.get("enforce_json_only", True))

        if not command:
            raise ValueError("command must include at least one executable name.")
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be >= 1.")
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1.")
        if mode != "problem_generation":
            raise ValueError("Only mode='problem_generation' is allowed for this adapter.")
        if not enforce_json_only:
            raise ValueError("enforce_json_only must be true for Codex generation adapter.")

        prompt_template_path = _resolve_path(raw.get("prompt_template_path"), root)
        repair_prompt_template_path = _resolve_path(raw.get("repair_prompt_template_path"), root)
        artifacts_root = _resolve_path(raw.get("artifacts_root"), root)

        return cls(
            command=command,
            extra_args=extra_args,
            prompt_template_path=prompt_template_path,
            repair_prompt_template_path=repair_prompt_template_path,
            artifacts_root=artifacts_root,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            mode=mode,
            enforce_json_only=enforce_json_only,
        )


def _resolve_path(raw_path: Any, repo_root: Path) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("All path entries in codex config must be non-empty strings.")
    path = Path(raw_path)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()

