"""
TypeScript to Python translator using tree-sitter AST.
"""
from __future__ import annotations

import re
from pathlib import Path

from .ts_parser import parse_typescript
from .ast_utils import node_text, find_child, find_children, find_descendants
from .py_emitter import PyEmitter
from .statements import StatementTranslator


def translate_typescript_to_python(ts_source: str) -> str:
    """Translate a TypeScript source file to Python."""
    tree, src_bytes = parse_typescript(ts_source)
    root = tree.root_node
    em = PyEmitter(src_bytes)
    stmt = StatementTranslator(em)

    for child in root.children:
        if child.type == "export_statement":
            inner = find_child(child, "class_declaration") or find_child(child, "class")
            if inner:
                _translate_class(inner, em, stmt, src_bytes)
        elif child.type == "class_declaration":
            _translate_class(child, em, stmt, src_bytes)
        elif child.type in ("import_statement", "comment"):
            continue

    return em.result()


def _translate_class(node, em, stmt, src_bytes):
    """Translate a class declaration."""
    name_node = find_child(node, "type_identifier") or find_child(node, "identifier")
    class_name = node_text(name_node, src_bytes) if name_node else "TranslatedClass"

    heritage = find_child(node, "class_heritage")
    parent_name = None
    if heritage:
        parent_id = find_descendants(heritage, "type_identifier") or find_descendants(heritage, "identifier")
        if parent_id:
            parent_name = node_text(parent_id[0], src_bytes)

    if parent_name:
        em.emit(f"class {class_name}({parent_name}):")
    else:
        em.emit(f"class {class_name}:")

    em.indent += 1
    em.emit_blank()

    body = find_child(node, "class_body")
    if not body:
        em.emit("pass")
        em.indent -= 1
        return

    has_content = False
    for member in body.children:
        if member.type == "method_definition":
            _translate_method(member, em, stmt, src_bytes)
            has_content = True
        elif member.type in ("public_field_definition", "property_definition"):
            _translate_field(member, em, src_bytes)
            has_content = True

    if not has_content:
        em.emit("pass")
    em.indent -= 1


def _translate_method(node, em, stmt, src_bytes):
    """Translate a method definition."""
    name_node = find_child(node, "property_identifier")
    method_name = node_text(name_node, src_bytes) if name_node else "_unknown"

    params_node = find_child(node, "formal_parameters")
    params = _extract_params(params_node, src_bytes) if params_node else []
    all_params = ["self"] + params

    em.emit_blank()
    em.emit(f"def {method_name}({', '.join(all_params)}):")
    em.indent += 1

    body = find_child(node, "statement_block")
    if body:
        meaningful = [c for c in body.children if c.type not in ("{", "}", ";")]
        if meaningful:
            stmt.translate_statements(body)
        else:
            em.emit("pass")
    else:
        em.emit("pass")
    em.indent -= 1


def _translate_field(node, em, src_bytes):
    """Translate a class field."""
    raw = em._basic_translate(node_text(node, src_bytes)).rstrip(";").strip()
    if "=" in raw:
        em.emit(f"# field: {raw}")


def _extract_params(params_node, src_bytes):
    """Extract parameter names from formal_parameters."""
    params = []
    for child in params_node.children:
        if child.type in ("(", ")", ","):
            continue
        if child.type in ("required_parameter", "optional_parameter"):
            ident = find_child(child, "identifier")
            if ident:
                params.append(node_text(ident, src_bytes))
            else:
                obj_pattern = find_child(child, "object_pattern")
                if obj_pattern:
                    params.append("**kwargs")
                else:
                    raw = node_text(child, src_bytes)
                    name = re.sub(r'\s*[:?].*$', '', raw).strip()
                    name = re.sub(r'^(readonly|public|private|protected)\s+', '', name)
                    if name:
                        params.append(name)
        elif child.type == "rest_parameter":
            ident = find_child(child, "identifier")
            if ident:
                params.append(f"*{node_text(ident, src_bytes)}")
    return params


def _postprocess(code: str) -> str:
    """Fix common translation artifacts."""
    code = code.replace("self.self.", "self.")
    code = re.sub(r'\n{3,}', '\n\n', code)
    return code


HEADER = '''"""ROAI Portfolio Calculator — translated from TypeScript by tt."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Any

from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator
from app.implementation.portfolio.calculator.helpers import (
    Big, DATE_FORMAT, EPSILON, INVESTMENT_ACTIVITY_TYPES,
    add_milliseconds, clone_deep, difference_in_days,
    each_year_of_interval, end_of_day, end_of_year,
    format_date, get_factor, get_interval_from_date_range,
    is_after, is_before, is_this_year, is_within_interval,
    min_date, parse_date, reset_hours, sort_by,
    start_of_day, start_of_year, sub_days,
)

'''


def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Run the full translation pipeline."""
    ts_roai = (
        repo_root / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "roai" / "portfolio-calculator.ts"
    )
    ts_base = (
        repo_root / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "portfolio-calculator.ts"
    )
    output_file = (
        output_dir / "app" / "implementation" / "portfolio" / "calculator"
        / "roai" / "portfolio_calculator.py"
    )

    if not ts_roai.exists():
        print(f"Warning: TypeScript source not found: {ts_roai}")
        return

    print(f"Translating {ts_roai.name} using tree-sitter AST...")
    ts_source = ts_roai.read_text(encoding="utf-8")

    translated = translate_typescript_to_python(ts_source)
    translated = _postprocess(translated)
    final_code = HEADER + translated + "\n"

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(final_code, encoding="utf-8")
    print(f"  Translated → {output_file}")



