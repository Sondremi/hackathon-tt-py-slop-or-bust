from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from pathlib import Path


_CLASS_RE = re.compile(r"export\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\s+extends\s+([A-Za-z_][A-Za-z0-9_]*)")
_METHOD_RE = re.compile(r"(?:public|protected|private)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_IMPORT_RE = re.compile(r"^\s*import\s+.+?from\s+['\"](.+?)['\"];?\s*$", re.MULTILINE)
_KIND_RE = re.compile(
    r"getPerformanceCalculationType\s*\(\s*\)\s*\{[\s\S]*?return\s+[A-Za-z_][A-Za-z0-9_]*\.([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class SourceUnit:
    source_path: str
    digest: str
    class_name: str
    base_name: str
    method_names: list[str]
    import_paths: list[str]
    calc_kind: str



def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()



def scan_source(source_file: Path) -> SourceUnit:
    text = source_file.read_text(encoding="utf-8")

    class_match = _CLASS_RE.search(text)
    if class_match:
        class_name = class_match.group(1)
        base_name = class_match.group(2)
    else:
        class_name = "UnknownClass"
        base_name = "UnknownBase"

    method_names = sorted(set(_METHOD_RE.findall(text)))
    import_paths = sorted(set(_IMPORT_RE.findall(text)))

    kind_match = _KIND_RE.search(text)
    calc_kind = kind_match.group(1) if kind_match else "ROAI"

    return SourceUnit(
        source_path=str(source_file),
        digest=_sha256(text),
        class_name=class_name,
        base_name=base_name,
        method_names=method_names,
        import_paths=import_paths,
        calc_kind=calc_kind,
    )
