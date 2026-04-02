from __future__ import annotations

from pathlib import Path
import zipfile

from contracts import CodexGenerationOutput
from export import HwpxExportEngine, build_problem_placeholder_map
from hwpx import HwpxArchive


_SECTION_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
    xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p id="10" paraPrIDRef="10" styleIDRef="12">
    <hp:run charPrIDRef="21">
      <hp:t>{{QUESTION_1_NUMBER}}. {{QUESTION_1_STEM}}</hp:t>
    </hp:run>
  </hp:p>
  <hp:p id="11" paraPrIDRef="11" styleIDRef="13">
    <hp:run charPrIDRef="22"><hp:t>① {{QUESTION_1_CHOICE_1}}</hp:t></hp:run>
  </hp:p>
  <hp:p id="12" paraPrIDRef="11" styleIDRef="13">
    <hp:run charPrIDRef="22"><hp:t>② {{QUESTION_1_CHOICE_2}}</hp:t></hp:run>
  </hp:p>
  <hp:p id="13" paraPrIDRef="11" styleIDRef="13">
    <hp:run charPrIDRef="22"><hp:t>③ {{QUESTION_1_CHOICE_3}}</hp:t></hp:run>
  </hp:p>
  <hp:p id="14" paraPrIDRef="11" styleIDRef="13">
    <hp:run charPrIDRef="22"><hp:t>④ {{QUESTION_1_CHOICE_4}}</hp:t></hp:run>
  </hp:p>
  <hp:p id="15" paraPrIDRef="11" styleIDRef="13">
    <hp:run charPrIDRef="22"><hp:t>⑤ {{QUESTION_1_CHOICE_5}}</hp:t></hp:run>
  </hp:p>
  <hp:p id="16" paraPrIDRef="12" styleIDRef="14">
    <hp:run charPrIDRef="23"><hp:t>정답: {{QUESTION_1_ANSWER}}</hp:t></hp:run>
  </hp:p>
</hs:sec>
"""


def _create_template(path: Path) -> None:
    with zipfile.ZipFile(path, mode="w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr(
            "Preview/PrvText.txt",
            "{{QUESTION_1_NUMBER}}. {{QUESTION_1_STEM}}\n정답: {{QUESTION_1_ANSWER}}",
        )
        zf.writestr("Contents/section0.xml", _SECTION_XML)
        zf.writestr("BinData/binary.dat", b"\x00\x01guard")
        zf.writestr("META-INF/manifest.xml", "<manifest>stable</manifest>")


def test_hwpx_export_renders_placeholders_and_preserves_styles(tmp_path: Path) -> None:
    template_path = tmp_path / "template.hwpx"
    output_path = tmp_path / "rendered.hwpx"
    _create_template(template_path)

    generation_output = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "q-1",
                    "stem": "함수 f(x)의 값을 구하시오.",
                    "choices": ["1", "2", "3", "4", "5"],
                    "answer": "2",
                    "explanation": "조건을 대입하면 2이다.",
                }
            ]
        }
    )

    result = HwpxExportEngine().render(
        template_path=template_path,
        output_path=output_path,
        generation_output=generation_output,
    )

    assert result.output_path == output_path
    assert result.rendered_placeholders >= 8
    assert result.verified_reopen is True
    assert result.style_ids_preserved is True

    rendered = HwpxArchive.load(output_path)
    preview = rendered.read_preview_text()
    section_xml = rendered.contents["Contents/section0.xml"].decode("utf-8")

    assert "{{QUESTION_1_STEM}}" not in preview
    assert "1. 함수 f(x)의 값을 구하시오." in preview
    assert "정답: 2" in preview
    assert "{{QUESTION_1_CHOICE_3}}" not in section_xml
    assert "③ 3" in section_xml
    assert 'styleIDRef="12"' in section_xml
    assert 'styleIDRef="13"' in section_xml
    assert 'charPrIDRef="22"' in section_xml
    assert rendered.ordered_names == (
        "mimetype",
        "Preview/PrvText.txt",
        "Contents/section0.xml",
        "BinData/binary.dat",
        "META-INF/manifest.xml",
    )
    assert rendered.contents["BinData/binary.dat"] == b"\x00\x01guard"
    assert rendered.contents["META-INF/manifest.xml"] == b"<manifest>stable</manifest>"


def test_hwpx_export_escapes_xml_text_values(tmp_path: Path) -> None:
    template_path = tmp_path / "template.hwpx"
    output_path = tmp_path / "rendered.hwpx"
    _create_template(template_path)

    generation_output = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "q-1",
                    "stem": "x < y 이고 x & y 조건을 만족한다.",
                    "choices": ["1", "2", "3", "4", "5"],
                    "answer": "x < y & z",
                }
            ]
        }
    )

    HwpxExportEngine().render(
        template_path=template_path,
        output_path=output_path,
        generation_output=generation_output,
    )

    rendered = HwpxArchive.load(output_path)
    section_xml = rendered.contents["Contents/section0.xml"].decode("utf-8")
    assert "x &lt; y" in section_xml
    assert "x &lt; y &amp; z" in section_xml


def test_placeholder_contract_surface_matches_export_map() -> None:
    generation_output = CodexGenerationOutput.from_dict(
        {
            "questions": [
                {
                    "id": "q-1",
                    "stem": "문항 본문",
                    "choices": ["A", "B", "C", "D", "E"],
                    "answer": "B",
                    "explanation": "해설",
                }
            ]
        }
    )

    contract_text = (Path(__file__).resolve().parents[2] / "templates" / "hwpx" / "placeholder_contract.txt").read_text(
        encoding="utf-8"
    )
    placeholders = set(build_problem_placeholder_map(generation_output))

    assert "{{QUESTION_N_NUMBER}}" in contract_text
    assert "{{QUESTION_N_ID}}" in contract_text
    assert "{{QUESTION_N_STEM}}" in contract_text
    assert "{{QUESTION_N_CHOICE_M}}" in contract_text
    assert "{{QUESTION_N_ANSWER}}" in contract_text
    assert "{{QUESTION_N_EXPLANATION}}" in contract_text
    assert {
        "{{QUESTION_1_NUMBER}}",
        "{{QUESTION_1_ID}}",
        "{{QUESTION_1_STEM}}",
        "{{QUESTION_1_CHOICE_1}}",
        "{{QUESTION_1_ANSWER}}",
        "{{QUESTION_1_EXPLANATION}}",
    }.issubset(placeholders)

