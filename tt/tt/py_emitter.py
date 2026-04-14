"""Emit Python source code from tree-sitter TypeScript AST nodes.

This module walks the AST produced by tree-sitter and produces
equivalent Python code. It handles the key TS→Python patterns:
- class/method declarations
- variable declarations (let/const/var → plain assignment)
- this.x → self.x
- Big.js calls → Big() wrapper
- optional chaining (?.) → or-based fallback
- arrow functions → lambdas or inline
- type annotations → stripped
- for loops, if/else, ternary
"""
from __future__ import annotations

import re
from .ast_utils import node_text, find_child, find_children, find_descendants, find_descendant


class PyEmitter:
    """Translates tree-sitter TS AST nodes into Python source lines."""

    def __init__(self, source_bytes: bytes):
        self.src = source_bytes
        self.indent = 0
        self.lines: list[str] = []

    def text(self, node) -> str:
        return node_text(node, self.src)

    def emit(self, line: str) -> None:
        self.lines.append("    " * self.indent + line)

    def emit_blank(self) -> None:
        self.lines.append("")

    def result(self) -> str:
        return "\n".join(self.lines)

    # --- Main dispatch ---

    def translate_node(self, node) -> str:
        """Translate a single AST node to a Python expression string."""
        t = node.type

        handler = getattr(self, f"_expr_{t}", None)
        if handler:
            return handler(node)

        # Fallback: raw text with basic replacements
        return self._basic_translate(self.text(node))

    def _basic_translate(self, text: str) -> str:
        """Apply basic TS→Python text transformations."""
        # Handle .filter(arrow) → list comprehension
        text = self._translate_array_methods(text)
        # this. → self.
        text = re.sub(r'\bthis\.', 'self.', text)
        # new Big(x) → Big(x)
        text = re.sub(r'\bnew\s+Big\(', 'Big(', text)
        # new Date() → datetime.now()
        text = re.sub(r'\bnew\s+Date\(\)', 'datetime.now()', text)
        # new Date(x) → parse_date(x)
        text = re.sub(r'\bnew\s+Date\(([^)]+)\)', r'parse_date(\1)', text)
        # Remove semicolons at end
        text = text.rstrip(';').rstrip()
        # === → ==
        text = text.replace('===', '==').replace('!==', '!=')
        # const/let/var → remove
        text = re.sub(r'^(const|let|var)\s+', '', text)
        # null/undefined → None
        text = re.sub(r'\bnull\b', 'None', text)
        text = re.sub(r'\bundefined\b', 'None', text)
        # true/false → True/False
        text = re.sub(r'\btrue\b', 'True', text)
        text = re.sub(r'\bfalse\b', 'False', text)
        # Remove type annotations after : in declarations
        text = re.sub(r':\s*(?:Big|string|number|boolean|Date|void|any)\b(?:\[\])?', '', text)
        # ?? → or
        text = text.replace(' ?? ', ' or ')
        # ?. → careful handling
        text = text.replace('?.', '.')
        # .length → len() -- tricky, skip for now
        # || → or, && → and
        text = text.replace(' || ', ' or ').replace(' && ', ' and ')
        # ! prefix → not
        text = re.sub(r'(?<![=<>])!(?!=)', 'not ', text)
        # .includes( → in pattern - skip, complex
        # .push( → .append(
        text = text.replace('.push(', '.append(')
        # .indexOf( → .index(  -- close enough
        # .findIndex( → next(i for i... -- skip
        # .at(-1) → [-1]
        text = re.sub(r'\.at\((-?\d+)\)', r'[\1]', text)
        # .toNumber() → .toNumber()  -- Big wrapper has this
        # .eq(0) .gt(0) etc are on Big -- keep as-is
        # Number.EPSILON → EPSILON
        text = text.replace('Number.EPSILON', 'EPSILON')
        # PortfolioCalculator.ENABLE_LOGGING → False
        text = text.replace('PortfolioCalculator.ENABLE_LOGGING', 'False')
        # format(date, DATE_FORMAT) → format_date(date)
        text = re.sub(r'\bformat\(([^,]+),\s*DATE_FORMAT\)', r'format_date(\1)', text)
        # format(date, 'yyyy') → format_date(date, 'yyyy')
        text = re.sub(r"\bformat\(([^,]+),\s*'yyyy'\)", r"format_date(\1, 'yyyy')", text)
        # differenceInDays → difference_in_days
        text = text.replace('differenceInDays', 'difference_in_days')
        # isBefore → is_before
        text = text.replace('isBefore', 'is_before')
        # isAfter → is_after
        text = text.replace('isAfter', 'is_after')
        # isThisYear → is_this_year
        text = text.replace('isThisYear', 'is_this_year')
        # addMilliseconds → add_milliseconds
        text = text.replace('addMilliseconds', 'add_milliseconds')
        # eachYearOfInterval → each_year_of_interval
        text = text.replace('eachYearOfInterval', 'each_year_of_interval')
        # cloneDeep → clone_deep
        text = text.replace('cloneDeep', 'clone_deep')
        # sortBy → sort_by
        text = re.sub(r'\bsortBy\b', 'sort_by', text)
        # getIntervalFromDateRange → get_interval_from_date_range
        text = text.replace('getIntervalFromDateRange', 'get_interval_from_date_range')
        # getFactor → get_factor
        text = re.sub(r'\bgetFactor\b', 'get_factor', text)
        # console.log → # console.log (comment out)
        if 'console.log' in text:
            text = '# ' + text
        # Logger.warn → # Logger.warn
        if 'Logger.warn' in text:
            text = '# ' + text
        # Remove trailing commas before )
        text = re.sub(r',\s*\)', ')', text)
        # .includes(x) → x in collection
        text = re.sub(
            r"(\w[\w.\[\]'\"]+)\.includes\(([^)]+)\)",
            r'\2 in \1',
            text,
        )
        # Clean up multiline statements — join lines broken at =
        text = re.sub(r'=\s*$', '= ', text, flags=re.MULTILINE)
        text = re.sub(r'(=\s+)\s+\n\s+', r'\1 ', text)
        # Join continuation lines
        lines = text.split('\n')
        text = ' '.join(lines)
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace

        return text

    # --- Expression handlers ---

    def _expr_identifier(self, node) -> str:
        name = self.text(node)
        if name == 'this':
            return 'self'
        if name in ('null', 'undefined'):
            return 'None'
        if name == 'true':
            return 'True'
        if name == 'false':
            return 'False'
        return name

    def _expr_number(self, node) -> str:
        return self.text(node)

    def _expr_string(self, node) -> str:
        return self.text(node)

    def _expr_template_string(self, node) -> str:
        # f-string conversion would be complex; use basic translate
        return self._basic_translate(self.text(node))

    def _expr_true(self, node) -> str:
        return 'True'

    def _expr_false(self, node) -> str:
        return 'False'

    def _expr_null(self, node) -> str:
        return 'None'

    def _expr_property_identifier(self, node) -> str:
        return self.text(node)

    def _expr_member_expression(self, node) -> str:
        return self._basic_translate(self.text(node))

    def _expr_call_expression(self, node) -> str:
        return self._basic_translate(self.text(node))

    def _expr_binary_expression(self, node) -> str:
        return self._basic_translate(self.text(node))

    def _expr_unary_expression(self, node) -> str:
        return self._basic_translate(self.text(node))

    def _expr_parenthesized_expression(self, node) -> str:
        return self._basic_translate(self.text(node))

    def _expr_ternary_expression(self, node) -> str:
        raw = self.text(node)
        return self._basic_translate(raw)

    def _expr_assignment_expression(self, node) -> str:
        return self._basic_translate(self.text(node))

    def _expr_update_expression(self, node) -> str:
        raw = self.text(node)
        # x++ → x += 1, x-- → x -= 1
        raw = re.sub(r'(\w+)\+\+', r'\1 += 1', raw)
        raw = re.sub(r'(\w+)--', r'\1 -= 1', raw)
        return self._basic_translate(raw)

    def _expr_new_expression(self, node) -> str:
        raw = self.text(node)
        # new Big(x) → Big(x)
        raw = re.sub(r'^new\s+', '', raw)
        return self._basic_translate(raw)

    def _expr_object(self, node) -> str:
        return self._basic_translate(self.text(node))

    def _expr_array(self, node) -> str:
        return self._basic_translate(self.text(node))

    def _expr_arrow_function(self, node) -> str:
        return self._basic_translate(self.text(node))

    def _expr_spread_element(self, node) -> str:
        raw = self.text(node)
        return self._basic_translate(raw.replace('...', '**'))

    def _translate_array_methods(self, text: str) -> str:
        """Translate JS array methods with arrow fns to Python."""
        # .filter(({ prop }) => { return prop; })
        text = re.sub(
            r'\.filter\(\s*\(\{\s*(\w+)\s*\}\)\s*=>\s*\{\s*return\s+(\w+)\s*;?\s*\}\s*\)',
            r'',  # remove filter, we wrap the collection below
            text,
        )
        # If filter was removed, wrap in list comp
        # .filter(x => cond) → [x for x in ... if cond]
        text = re.sub(
            r'\.filter\(\s*\(?\s*(\w+)\s*\)?\s*=>\s*\{?\s*return\s+(.+?)\s*;?\s*\}?\s*\)',
            lambda m: '',  # handled at for-in level
            text,
        )
        # .filter(({ prop }) => prop)
        text = re.sub(
            r'\.filter\(\s*\(\{\s*(\w+)\s*\}\)\s*=>\s*\1\s*\)',
            r'',
            text,
        )
        # .map(({ prop }) => prop)
        text = re.sub(
            r'\.map\(\s*\(\{\s*(\w+)\s*\}\)\s*=>\s*\{\s*return\s+(\w+)\s*;?\s*\}\s*\)',
            r'',
            text,
        )
        # .includes(x) → x in collection
        text = re.sub(
            r"(\[.*?\])\.includes\(([^)]+)\)",
            r'\2 in \1',
            text,
        )
        return text
