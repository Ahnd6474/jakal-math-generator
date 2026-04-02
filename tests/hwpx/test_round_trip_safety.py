from __future__ import annotations

from pathlib import Path
import zipfile

from contracts import CodexGenerationOutput
from export import HwpxExportEngine
from hwpx import HwpxArchive, extract_placeholder_tokens


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_TEMPLATE = REPO_ROOT / "평가원수학양식(수정) (1).hwpx"


def _load_zip_snapshot(path: Path) -> tuple[tuple[str, ...], dict[str, bytes]]:
    with zipfile.ZipFile(path, mode="r") as zf:
        names = tuple(zf.namelist())
        payloads = {name: zf.read(name) for name in names}
    return names, payloads


def test_hwpx_noop_round_trip_preserves_entry_layout_and_payloads(tmp_path: Path) -> None:
    assert SAMPLE_TEMPLATE.exists(), f"Missing sample template: {SAMPLE_TEMPLATE}"
    round_trip_path = tmp_path / "round_trip.hwpx"

    archive = HwpxArchive.load(SAMPLE_TEMPLATE)
    archive.save(round_trip_path)

    original_names, original_payloads = _load_zip_snapshot(SAMPLE_TEMPLATE)
    output_names, output_payloads = _load_zip_snapshot(round_trip_path)

    assert output_names == original_names
    assert output_payloads == original_payloads


def test_hwpx_round_trip_preserves_placeholder_surface_tokens(tmp_path: Path) -> None:
    round_trip_path = tmp_path / "round_trip.hwpx"

    original = HwpxArchive.load(SAMPLE_TEMPLATE)
    original_tokens = extract_placeholder_tokens(original.read_preview_text())
    assert original_tokens, "Template should expose placeholder-like surface tokens."

    original.save(round_trip_path)
    reopened = HwpxArchive.load(round_trip_path)
    reopened_tokens = extract_placeholder_tokens(reopened.read_preview_text())

    assert reopened_tokens == original_tokens


def test_hwpx_export_round_trip_preserves_real_template_layout_and_styles(tmp_path: Path) -> None:
    output_path = tmp_path / "rendered.hwpx"
    generation_output = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "q-1",
                    "stem": "unused",
                    "choices": ["1", "2", "3", "4", "5"],
                    "answer": "1",
                }
            ]
        }
    )

    source = HwpxArchive.load(SAMPLE_TEMPLATE)
    source_style_ids = source.style_id_fingerprint()
    source_tokens = extract_placeholder_tokens(source.read_preview_text())

    result = HwpxExportEngine().render(
        template_path=SAMPLE_TEMPLATE,
        output_path=output_path,
        generation_output=generation_output,
    )

    rendered = HwpxArchive.load(output_path)

    assert result.rendered_placeholders == 0
    assert result.verified_reopen is True
    assert result.style_ids_preserved is True
    assert rendered.ordered_names == source.ordered_names
    assert rendered.payload_fingerprint() == source.payload_fingerprint()
    assert rendered.style_id_fingerprint() == source_style_ids
    assert extract_placeholder_tokens(rendered.read_preview_text()) == source_tokens
