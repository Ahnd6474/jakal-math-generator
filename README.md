# jakal-math-generator

Jakal Math Generator is a desktop-first orchestration repo for a CSAT-style math question workflow with HWPX export guardrails.

The verified implementation in this repository includes:

- a runnable Tk desktop launcher at `desktop/src/main.py`
- a shared product shell in `desktop/src/product_shell/app.py`
- a UI controller layer in `desktop/src/product_shell/ui.py`
- Codex CLI adapter/config loading for generation runs
- validation and retry-state handling for generated questions
- HWPX placeholder rendering with archive round-trip checks
- style-id preservation checks before export writes the final file

The main design principle is HWPX structure preservation. Generation quality matters, but preserving template layout, untouched payloads, and exported XML safety matters more.

## What You Can Run

- Desktop launcher: `python desktop/src/main.py`
- Test suite: `python -m pytest`

The desktop launcher is the checked-in GUI entrypoint. It builds the shared product shell, opens a Tk window when Tk is available, and falls back to a headless test-friendly window for non-GUI environments. It does not use a separate web UI path.

## Requirements

- Python 3.11 or newer
- `pytest` for verification
- `codex` on `PATH` only if you intend to run real generation through the adapter

Install test dependencies with:

```powershell
python -m pip install -U pytest
```

## Repository Layout

- `configs/codex/execution.json`: verified Codex CLI execution config
- `prompts/codex/*.txt`: generation and repair prompt templates
- `src/contracts`: question, Codex output, and validation contracts
- `src/generation`: Codex CLI adapter and retry controller
- `src/validation`: format, uniqueness, consistency, and originality checks
- `src/hwpx`: HWPX archive round-trip utilities
- `src/export`: placeholder-based HWPX export engine
- `desktop/src/product_shell`: product integration shell
- `desktop/src/main.py`: desktop launcher entrypoint
- `tests`, `desktop/tests`: contract, export, round-trip, and e2e coverage
- `templates/hwpx`: placeholder contract surface

## Desktop Launch Flow

`desktop/src/main.py` is intentionally thin. It:

1. resolves the repo root
2. loads `configs/codex/execution.json`
3. constructs `CodexCliAdapter`, `GenerationValidator`, and `HwpxExportEngine`
4. bootstraps `ProductShellApp`
5. opens the Tk window

For a non-interactive smoke check, the launcher can be imported and constructed from `desktop/src`:

```powershell
python -c "import main; w=main.build_window(); w.update_idletasks(); w.destroy(); print('GUI smoke ok')"
```

You can also run the launcher directly:

```powershell
python desktop/src/main.py
```

## Product Shell Workflow

The shared shell in `desktop/src/product_shell/app.py` coordinates the product flow:

1. map `GenerationForm` to `QuestionSpec`
2. call the Codex CLI adapter
3. collect attempt logs from the artifact directory
4. validate parsed output
5. accept, reject, or mark the run as export-ready
6. export through the shared HWPX engine

Run states are explicit and surfaced to the desktop UI:

- `idle`
- `running`
- `codex_parse_failed`
- `validation_failed`
- `similarity_failed`
- `accepted`
- `export_failed`
- `export_succeeded`

## HWPX Guardrails

The export path in `src/export/hwpx_exporter.py` preserves the template contract and rejects unsafe writes.

Verified checks include:

- placeholder replacement only on the supported template surface
- XML parse validation after rendering
- archive entry order preservation
- untouched payload byte preservation
- style-id fingerprint preservation before the output replaces the destination file
- end-to-end launcher coverage through the shared shell

Relevant implementation files:

- `src/export/hwpx_exporter.py`
- `src/hwpx/archive.py`
- `templates/hwpx/placeholder_contract.txt`

## Codex CLI Configuration

`configs/codex/execution.json` is the verified adapter config. It pins:

- `mode`
- `command`
- `extra_args`
- `prompt_template_path`
- `repair_prompt_template_path`
- `artifacts_root`
- `timeout_seconds`
- `max_attempts`
- `enforce_json_only`

The adapter expects `mode: "problem_generation"` and JSON-only output.

## Verification

Run the full test suite with:

```powershell
python -m pytest
```

The verified coverage includes:

- HWPX no-op round-trip safety
- placeholder rendering and XML escaping
- Codex CLI adapter contracts and retries
- generation validation and originality checks
- product shell integration

## Limitations

- This repo provides a Tk desktop launcher, not a web UI.
- Real generation requires a local `codex` executable and a valid `configs/codex/execution.json`.
- The export engine only renders the verified placeholder contract surface.
- HWPX safety is enforced by tests and runtime guards, but template changes still need review.
- Tk GUI smoke checks still depend on the local environment being able to import `tkinter`; otherwise the launcher falls back to the headless window used by tests.

## Operator Notes

- Keep `templates/hwpx/placeholder_contract.txt` aligned with the placeholders used by the export engine.
- Keep `desktop/src/main.py` as the single GUI entrypoint unless a new launcher path is added deliberately.
- Keep `desktop/src/product_shell/ui.py` aligned with `desktop/src/product_shell/app.py` so the controller stays a thin projection of shell state.
- If you change HWPX template structure, rerun `python -m pytest` before shipping.
