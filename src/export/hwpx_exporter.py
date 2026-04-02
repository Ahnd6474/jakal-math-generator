from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping
from xml.etree import ElementTree
from xml.sax.saxutils import escape as xml_escape

from contracts import CodexGenerationOutput
from hwpx import HwpxArchive


_XML_CONTENT_ENTRY_RE = re.compile(r"^Contents/.+\.xml$")
_STYLE_ID_RE = re.compile(r'(?:styleIDRef|paraPrIDRef|charPrIDRef)="([^"]+)"')


class HwpxExportError(RuntimeError):
    """Raised when an HWPX export cannot be completed safely."""


@dataclass(frozen=True)
class HwpxExportResult:
    output_path: Path
    rendered_placeholders: int
    verified_reopen: bool
    style_ids_preserved: bool


def build_problem_placeholder_map(output: CodexGenerationOutput) -> dict[str, str]:
    placeholders: dict[str, str] = {}
    for index, question in enumerate(output.questions, start=1):
        base = f"QUESTION_{index}"
        placeholders[f"{{{{{base}_NUMBER}}}}"] = str(index)
        placeholders[f"{{{{{base}_ID}}}}"] = question.question_id
        placeholders[f"{{{{{base}_STEM}}}}"] = question.stem
        placeholders[f"{{{{{base}_ANSWER}}}}"] = str(question.answer)
        placeholders[f"{{{{{base}_EXPLANATION}}}}"] = question.explanation or ""
        for choice_index, choice in enumerate(question.choices, start=1):
            placeholders[f"{{{{{base}_CHOICE_{choice_index}}}}}"] = choice
    return placeholders


class HwpxExportEngine:
    def render(
        self,
        *,
        template_path: str | Path,
        output_path: str | Path,
        generation_output: CodexGenerationOutput,
        extra_placeholders: Mapping[str, str] | None = None,
    ) -> HwpxExportResult:
        source = HwpxArchive.load(template_path)
        original_style_fingerprint = self._style_fingerprint(source)

        placeholder_map = build_problem_placeholder_map(generation_output)
        if extra_placeholders:
            placeholder_map.update(dict(extra_placeholders))

        rendered_archive, rendered_count = self._render_archive(source, placeholder_map)
        self._assert_xml_entries_parse(rendered_archive)

        destination = Path(output_path)
        temp_output = destination.with_name(f"{destination.name}.tmp")
        if temp_output.exists():
            temp_output.unlink()

        try:
            rendered_archive.save(temp_output)
            reopened = HwpxArchive.load(temp_output)
            reopened_fingerprint = self._style_fingerprint(reopened)
            style_ids_preserved = reopened_fingerprint == original_style_fingerprint
            if not style_ids_preserved:
                raise HwpxExportError("Style ID fingerprint changed after placeholder rendering.")

            temp_output.replace(destination)
            return HwpxExportResult(
                output_path=destination,
                rendered_placeholders=rendered_count,
                verified_reopen=True,
                style_ids_preserved=True,
            )
        except Exception as exc:
            if temp_output.exists():
                temp_output.unlink()
            if isinstance(exc, HwpxExportError):
                raise
            raise HwpxExportError(str(exc)) from exc

    def _render_archive(
        self,
        archive: HwpxArchive,
        placeholders: Mapping[str, str],
    ) -> tuple[HwpxArchive, int]:
        updated_contents = dict(archive.contents)
        total_count = 0

        for name in archive.ordered_names:
            payload = archive.contents[name]
            if name == "Preview/PrvText.txt":
                text = payload.decode("utf-8", errors="strict")
                replaced, count = _replace_text_with_placeholders(
                    text=text,
                    placeholders=placeholders,
                    escape_for_xml=False,
                )
                if count > 0:
                    updated_contents[name] = replaced.encode("utf-8")
                    total_count += count
                continue

            if _XML_CONTENT_ENTRY_RE.match(name):
                text = payload.decode("utf-8", errors="strict")
                replaced, count = _replace_text_with_placeholders(
                    text=text,
                    placeholders=placeholders,
                    escape_for_xml=True,
                )
                if count > 0:
                    updated_contents[name] = replaced.encode("utf-8")
                    total_count += count

        return HwpxArchive(
            ordered_names=archive.ordered_names,
            contents=updated_contents,
            zip_infos=archive.zip_infos,
        ), total_count

    @staticmethod
    def _assert_xml_entries_parse(archive: HwpxArchive) -> None:
        for name in archive.ordered_names:
            if not _XML_CONTENT_ENTRY_RE.match(name):
                continue
            xml_text = archive.contents[name].decode("utf-8", errors="strict")
            try:
                ElementTree.fromstring(xml_text)
            except ElementTree.ParseError as exc:
                raise HwpxExportError(f"Invalid XML after placeholder rendering: {name}: {exc}") from exc

    @staticmethod
    def _style_fingerprint(archive: HwpxArchive) -> tuple[tuple[str, tuple[str, ...]], ...]:
        fingerprint: list[tuple[str, tuple[str, ...]]] = []
        for name in archive.ordered_names:
            if not _XML_CONTENT_ENTRY_RE.match(name):
                continue
            xml_text = archive.contents[name].decode("utf-8", errors="strict")
            style_ids = tuple(_STYLE_ID_RE.findall(xml_text))
            fingerprint.append((name, style_ids))
        return tuple(fingerprint)


def _replace_text_with_placeholders(
    *,
    text: str,
    placeholders: Mapping[str, str],
    escape_for_xml: bool,
) -> tuple[str, int]:
    rendered = text
    replacement_count = 0
    for token, value in placeholders.items():
        replacement = xml_escape(value) if escape_for_xml else value
        count = rendered.count(token)
        rendered = rendered.replace(token, replacement)
        replacement_count += count
    return rendered, replacement_count
