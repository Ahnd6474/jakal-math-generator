# Desktop Shell

## Purpose

`desktop/src/product_shell` is the integration shell that combines:

- Codex generation adapter (`src/generation/adapter`)
- Validation and originality checks (`src/validation`)
- HWPX export engine (`src/export`)

The shell keeps product-facing run states explicit so the desktop UI can render each failure mode separately.

## Run States

`RunStatus` values:

- `idle`
- `running`
- `codex_parse_failed`
- `validation_failed`
- `similarity_failed`
- `accepted`
- `export_failed`
- `export_succeeded`

## User Input Mapping

`GenerationForm` supports UI fields for:

- difficulty
- subject
- topic (major/middle/detail)
- question format (`5-choice` or `short-answer`)
- style
- quantity
- output type (`problem_only`, `problem_answer`, `problem_answer_solution`)
- template path

The form is translated into the shared `QuestionSpec` contract before calling Codex.

## Launch Path

Start the desktop launcher from the repository root with the single checked-in entrypoint:

```powershell
python desktop/src/main.py
```

`desktop/src/main.py` is intentionally thin. It resolves the shared Codex config, builds the shell through `bootstrap_product_shell(...)`, and starts the Tk window through `launch_desktop_app()`.

## Setup

1. Install Python 3.11+.
2. Install test dependencies:

```powershell
python -m pip install -U pytest
```

3. Run tests:

```powershell
python -m pytest
```

## Programmatic Usage Sketch

```python
from generation.adapter import CodexCliAdapter, CodexExecutionConfig
from product_shell import GenerationForm, bootstrap_product_shell
from validation import GenerationValidator
from export import HwpxExportEngine

config = CodexExecutionConfig.from_path("configs/codex/execution.json")
app = bootstrap_product_shell(
    adapter=CodexCliAdapter(config),
    validator=GenerationValidator(),
    exporter=HwpxExportEngine(),
    reference_corpus=("existing exam stem...",),
)

form = GenerationForm(
    difficulty="mid-4pt",
    subject="calculus",
    topic_major="function",
    topic_minor="limit",
    topic_detail="composite limit",
    question_format="5-choice",
    style="reasoning",
    quantity=1,
    output_type="problem_answer_solution",
    template_path="templates/hwpx/my-template.hwpx",
)

state = app.start_generation(form)
if state.status == "accepted":
    print(app.preview())
    app.export_hwpx(output_path="out.hwpx")
```

## Codex CLI Notes

- Keep `configs/codex/execution.json` in `mode: "problem_generation"`.
- Prompt templates must begin with `PROMPT_KIND: problem_generation`.
- Artifacts (`request.json`, `stdout.log`, `stderr.log`, `run.log`) are collected by the adapter and exposed as `state.codex_logs`.

## Export Guarantees

The desktop launcher does not implement a second export path. Once the shell accepts generated output, it delegates to the shared `HwpxExportEngine`, which keeps the existing export guardrails in force:

- placeholder replacement stays inside the template contract surface
- rendered XML entries must still parse before writeout
- archive entry order and untouched payload bytes are preserved on reopen
- HWPX style-id fingerprints must match before the output file replaces the destination

## E2E Coverage

`desktop/tests/e2e/test_product_shell_integration.py` validates:

- launcher entrypoint -> shell bootstrap -> generate -> export flow
- successful generate -> preview -> export flow
- Codex parse failure state
- validation failure state
- similarity failure state
- regenerate after failure
- export failure state
