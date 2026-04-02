from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


PROMPT_KIND_HEADER = "PROMPT_KIND: problem_generation"


def load_prompt_template(path: str | Path) -> str:
    template_path = Path(path)
    template = template_path.read_text(encoding="utf-8")
    lines = template.splitlines()
    if not lines or lines[0].strip() != PROMPT_KIND_HEADER:
        raise ValueError(
            f"Prompt template must start with '{PROMPT_KIND_HEADER}' to avoid mode mixing: "
            f"{template_path}"
        )
    return template


def render_prompt(
    *,
    template: str,
    question_spec: Mapping[str, Any],
    constraints: Mapping[str, Any],
    output_schema: Mapping[str, Any],
    previous_stdout: str | None = None,
    parse_error: str | None = None,
) -> str:
    replacements = {
        "{{QUESTION_SPEC_JSON}}": _as_pretty_json(question_spec),
        "{{CONSTRAINTS_JSON}}": _as_pretty_json(constraints),
        "{{OUTPUT_SCHEMA_JSON}}": _as_pretty_json(output_schema),
        "{{PREVIOUS_STDOUT}}": previous_stdout or "",
        "{{PARSE_ERROR}}": parse_error or "",
    }

    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def _as_pretty_json(data: Mapping[str, Any]) -> str:
    return json.dumps(dict(data), ensure_ascii=False, sort_keys=True, indent=2)

