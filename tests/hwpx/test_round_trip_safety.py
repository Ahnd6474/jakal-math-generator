from __future__ import annotations

from pathlib import Path
import zipfile

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
