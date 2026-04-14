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


_METHOD_DECL_RE = re.compile(
    r"(?P<visibility>public|protected|private)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^\)]*\)\s*(?::\s*[^\{]+)?\s*\{",
    re.MULTILINE,
)


@dataclass(frozen=True)
class SourceMethod:
    name: str
    visibility: str
    body: str
@dataclass(frozen=True)
class SourceUnit:
    source_path: str
    digest: str
    class_name: str
    base_name: str
    method_names: list[str]
    import_paths: list[str]
    calc_kind: str


    methods: list[SourceMethod]

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _find_matching_brace(text: str, open_idx: int) -> int:
    depth = 0
    i = open_idx
    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if not (in_single or in_double or in_backtick):
            if ch == "/" and nxt == "/":
                in_line_comment = True
                i += 2
                continue
            if ch == "/" and nxt == "*":
                in_block_comment = True
                i += 2
                continue

        if ch == "'" and not (in_double or in_backtick):
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not (in_single or in_backtick):
            in_double = not in_double
            i += 1
            continue
        if ch == "`" and not (in_single or in_double):
            in_backtick = not in_backtick
            i += 1
            continue

        if in_single or in_double or in_backtick:
            i += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i

        i += 1

    return -1


def _extract_methods(text: str) -> list[SourceMethod]:
    methods: list[SourceMethod] = []
    for match in _METHOD_DECL_RE.finditer(text):
        open_brace = text.find("{", match.end() - 1)
        if open_brace < 0:
            continue
        close_brace = _find_matching_brace(text, open_brace)
        if close_brace < 0:
            continue
        body = text[open_brace + 1 : close_brace].strip("\n")
        methods.append(
            SourceMethod(
                name=match.group("name"),
                visibility=match.group("visibility"),
                body=body,
            )
        )
    return methods



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
    methods = _extract_methods(text)
    calc_kind = kind_match.group(1) if kind_match else "ROAI"

    return SourceUnit(
        source_path=str(source_file),
        digest=_sha256(text),
        class_name=class_name,
        base_name=base_name,
        method_names=method_names,
        import_paths=import_paths,
        methods=methods,
        calc_kind=calc_kind,
    )
