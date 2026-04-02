from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
import zipfile

_PLACEHOLDER_TOKEN_RE = re.compile(
    r"<[^<>\r\n]{0,120}>|\[[^\[\]\r\n]{0,120}\]|[①②③④⑤]"
)


@dataclass(frozen=True)
class HwpxArchive:
    """In-memory HWPX archive that preserves entry order and payload bytes."""

    ordered_names: tuple[str, ...]
    contents: dict[str, bytes]
    zip_infos: dict[str, zipfile.ZipInfo]

    @classmethod
    def load(cls, path: str | Path) -> "HwpxArchive":
        source = Path(path)
        with zipfile.ZipFile(source, mode="r") as zf:
            names = tuple(zf.namelist())
            payloads = {name: zf.read(name) for name in names}
            infos = {name: zf.getinfo(name) for name in names}
        return cls(ordered_names=names, contents=payloads, zip_infos=infos)

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, mode="w") as zf:
            for name in self.ordered_names:
                original = self.zip_infos[name]
                cloned = zipfile.ZipInfo(filename=original.filename, date_time=original.date_time)
                cloned.compress_type = original.compress_type
                cloned.comment = original.comment
                cloned.extra = original.extra
                cloned.internal_attr = original.internal_attr
                cloned.external_attr = original.external_attr
                cloned.create_system = original.create_system
                cloned.create_version = original.create_version
                cloned.extract_version = original.extract_version
                cloned.flag_bits = original.flag_bits
                cloned.volume = original.volume
                zf.writestr(cloned, self.contents[name])

    def read_preview_text(self) -> str:
        return self.contents["Preview/PrvText.txt"].decode("utf-8", errors="strict")


def extract_placeholder_tokens(text: str) -> tuple[str, ...]:
    """Extract surface placeholder tokens from HWPX preview text."""

    return tuple(_PLACEHOLDER_TOKEN_RE.findall(text))
