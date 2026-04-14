"""Statement-level translator: walks TS AST and emits Python statements.

This module handles translating top-level and method-body statements:
- variable declarations → assignments
- for loops → Python for/while
- if/else → Python if/elif/else
- return statements
- expression statements
- class/method declarations
"""
from __future__ import annotations

import re
from .ast_utils import node_text, find_child, find_children, find_descendants
from .py_emitter import PyEmitter


class StatementTranslator:
    """Translates statement-level AST nodes to Python lines."""

    def __init__(self, emitter: PyEmitter):
        self.em = emitter

    def translate_statements(self, node) -> None:
        """Translate child statements of a block/body node."""
        for child in node.children:
            self.translate_statement(child)

    def translate_statement(self, node) -> None:
        """Dispatch a single statement node."""
        t = node.type

        if t in ("{", "}", ";", "comment"):
            return
        if t == "lexical_declaration" or t == "variable_declaration":
            self._stmt_variable(node)
        elif t == "expression_statement":
            self._stmt_expression(node)
        elif t == "return_statement":
            self._stmt_return(node)
        elif t == "if_statement":
            self._stmt_if(node)
        elif t == "for_statement":
            self._stmt_for(node)
        elif t == "for_in_statement":
            self._stmt_for_in(node)
        elif t == "while_statement":
            self._stmt_while(node)
        elif t == "break_statement":
            self.em.emit("break")
        elif t == "continue_statement":
            self.em.emit("continue")
        elif t == "statement_block":
            self.translate_statements(node)
        elif t == "empty_statement":
            return
        elif t == "try_statement":
            self._stmt_try(node)
        elif t == "throw_statement":
            self._stmt_throw(node)
        elif t == "switch_statement":
            self._stmt_switch(node)
        else:
            # Fallback: try to translate the raw text
            raw = self.em._basic_translate(self.em.text(node))
            if raw.strip():
                self.em.emit(raw)

    def _stmt_variable(self, node) -> None:
        """Translate let/const/var declarations."""
        for decl in find_children(node, "variable_declarator"):
            name_node = find_child(decl, "identifier") or find_child(decl, "object_pattern") or find_child(decl, "array_pattern")
            if not name_node:
                # Try raw extraction
                raw = self.em._basic_translate(self.em.text(node))
                self.em.emit(raw)
                return

            value_node = None
            # value is everything after the = sign
            saw_eq = False
            for c in decl.children:
                if c.type == "=" :
                    saw_eq = True
                    continue
                if saw_eq and c.type != "type_annotation":
                    value_node = c
                    break

            name_text = self.em.text(name_node)

            # Handle destructuring: const { a, b } = expr
            if name_node.type == "object_pattern":
                if value_node:
                    val = self.em.translate_node(value_node)
                    # Extract identifiers from the pattern
                    ids = [self.em.text(c) for c in find_descendants(name_node, "shorthand_property_identifier_pattern")]
                    if not ids:
                        ids = [self.em.text(c) for c in find_descendants(name_node, "identifier")]
                    if ids:
                        tmp_name = "_destructured"
                        self.em.emit(f"{tmp_name} = {val}")
                        for ident in ids:
                            py_ident = self.em._basic_translate(ident)
                            self.em.emit(f"{py_ident} = {tmp_name}.get('{ident}', {tmp_name}.get('{self._to_snake(ident)}'))")
                    else:
                        self.em.emit(f"# DESTRUCTURE: {self.em._basic_translate(self.em.text(node))}")
                return

            # Handle array destructuring: const [a, b] = expr
            if name_node.type == "array_pattern":
                if value_node:
                    val = self.em.translate_node(value_node)
                    ids = [self.em.text(c) for c in name_node.children if c.type == "identifier"]
                    if ids:
                        self.em.emit(f"{', '.join(ids)} = {val}")
                return

            # Remove type annotation from name
            name_text = re.sub(r'\s*:.*$', '', name_text)
            name_text = self.em._basic_translate(name_text)

            if value_node:
                val = self.em.translate_node(value_node)
                self.em.emit(f"{name_text} = {val}")
            else:
                self.em.emit(f"{name_text} = None")

    def _stmt_expression(self, node) -> None:
        """Translate expression statements."""
        # Get the actual expression (first non-semicolon child)
        expr = None
        for c in node.children:
            if c.type != ";":
                expr = c
                break
        if expr:
            raw = self.em.translate_node(expr)
            if raw.strip():
                self.em.emit(raw)

    def _stmt_return(self, node) -> None:
        """Translate return statements."""
        # Get everything after 'return'
        children = [c for c in node.children if c.type not in ("return", ";")]
        if children:
            val = self.em.translate_node(children[0])
            # Handle multi-line object returns
            if children[0].type == "object":
                self._emit_return_object(children[0])
            else:
                self.em.emit(f"return {val}")
        else:
            self.em.emit("return")

    def _emit_return_object(self, obj_node) -> None:
        """Translate return {...} into return dict."""
        raw = self.em.text(obj_node)
        translated = self.em._basic_translate(raw)
        # Convert { key: val, ... } to dict
        translated = self._convert_object_to_dict(translated)
        self.em.emit(f"return {translated}")

    def _convert_object_to_dict(self, text: str) -> str:
        """Convert JS object literal to Python dict literal."""
        text = text.strip()
        if text.startswith('{') and text.endswith('}'):
            # Replace shorthand properties: { foo, bar } → {"foo": foo, "bar": bar}
            # This is a simplification — complex objects should be handled at AST level
            pass
        return text

    def _stmt_if(self, node) -> None:
        """Translate if/else if/else statements."""
        condition_node = find_child(node, "parenthesized_expression")
        if condition_node:
            cond = self.em.translate_node(condition_node)
            # Remove outer parens
            if cond.startswith('(') and cond.endswith(')'):
                cond = cond[1:-1]
        else:
            cond = "True"

        self.em.emit(f"if {cond}:")
        self.em.indent += 1

        body = find_child(node, "statement_block")
        if body:
            self.translate_statements(body)
        else:
            # Single-line if body
            for c in node.children:
                if c.type not in ("if", "parenthesized_expression", "else_clause", "(", ")", "else"):
                    self.translate_statement(c)
                    break

        # Check for empty body
        if not any(l.strip() for l in self.em.lines[-(self.em.indent):] if l):
            self.em.emit("pass")

        self.em.indent -= 1

        # Handle else clause
        else_clause = find_child(node, "else_clause")
        if else_clause:
            # Check if it's else if
            nested_if = find_child(else_clause, "if_statement")
            if nested_if:
                # Convert to elif
                last_line_idx = len(self.em.lines) - 1
                self._translate_elif(nested_if)
            else:
                self.em.emit("else:")
                self.em.indent += 1
                body = find_child(else_clause, "statement_block")
                if body:
                    self.translate_statements(body)
                else:
                    for c in else_clause.children:
                        if c.type not in ("else",):
                            self.translate_statement(c)
                            break
                self.em.indent -= 1

    def _translate_elif(self, node) -> None:
        """Translate else-if as elif."""
        condition_node = find_child(node, "parenthesized_expression")
        if condition_node:
            cond = self.em.translate_node(condition_node)
            if cond.startswith('(') and cond.endswith(')'):
                cond = cond[1:-1]
        else:
            cond = "True"

        self.em.emit(f"elif {cond}:")
        self.em.indent += 1

        body = find_child(node, "statement_block")
        if body:
            self.translate_statements(body)
        self.em.indent -= 1

        else_clause = find_child(node, "else_clause")
        if else_clause:
            nested_if = find_child(else_clause, "if_statement")
            if nested_if:
                self._translate_elif(nested_if)
            else:
                self.em.emit("else:")
                self.em.indent += 1
                body = find_child(else_clause, "statement_block")
                if body:
                    self.translate_statements(body)
                self.em.indent -= 1

    def _stmt_for(self, node) -> None:
        """Translate C-style for loops."""
        raw = self.em.text(node)

        # Try to detect: for (let i = 0; i < x; i += 1)
        init_node = None
        cond_node = None
        update_node = None
        body_node = None

        parts = []
        for c in node.children:
            if c.type == "statement_block":
                body_node = c
            elif c.type not in ("for", "(", ")", ";"):
                parts.append(c)

        if len(parts) >= 3:
            init_node, cond_node, update_node = parts[0], parts[1], parts[2]

        if init_node and cond_node:
            init_text = self.em._basic_translate(self.em.text(init_node))
            cond_text = self.em._basic_translate(self.em.text(cond_node))

            # Check for simple range pattern: for (let i = 0; i < N; i += 1)
            range_match = re.match(r'(\w+)\s*=\s*(\d+)', init_text)
            cond_match = re.match(r'(\w+)\s*<\s*(.+)', cond_text)

            if range_match and cond_match and range_match.group(1) == cond_match.group(1):
                var = range_match.group(1)
                start = range_match.group(2)
                end = cond_match.group(2)
                if start == "0":
                    self.em.emit(f"for {var} in range({end}):")
                else:
                    self.em.emit(f"for {var} in range({start}, {end}):")
            else:
                # General for → while
                self.em.emit(init_text)
                self.em.emit(f"while {cond_text}:")
                self.em.indent += 1
                if body_node:
                    self.translate_statements(body_node)
                if update_node:
                    upd = self.em._basic_translate(self.em.text(update_node))
                    self.em.emit(upd)
                self.em.indent -= 1
                return
        else:
            self.em.emit("while True:  # for loop fallback")

        self.em.indent += 1
        if body_node:
            self.translate_statements(body_node)
        elif not parts:
            self.em.emit("pass")
        self.em.indent -= 1

    def _stmt_for_in(self, node) -> None:
        """Translate for...of / for...in loops."""
        raw = self.em.text(node)
        # for (const x of y) → for x in y:
        # for (const x in y) → for x in y:
        var_node = None
        collection_node = None

        children = list(node.children)
        # Skip 'for', '(', keyword nodes to find the variable and collection
        saw_of_in = False
        for c in children:
            if c.type in ("of", "in"):
                saw_of_in = True
                continue
            if c.type == "statement_block":
                continue
            if c.type in ("for", "(", ")"):
                continue
            if not saw_of_in:
                var_node = c
            else:
                collection_node = c

        if var_node and collection_node:
            var_text = self.em._basic_translate(self.em.text(var_node))
            # Remove let/const/var from var_text
            var_text = re.sub(r'^(const|let|var)\s+', '', var_text)
            # Remove type annotations
            var_text = re.sub(r'\s*:.*$', '', var_text)
            coll_raw = self.em.text(collection_node)
            coll_text = self._translate_collection(coll_raw, var_text)
            self.em.emit(f"for {var_text} in {coll_text}:")
        else:
            self.em.emit(f"# FOR: {self.em._basic_translate(raw)}")
            self.em.emit("for _item in []:")

        self.em.indent += 1
        body = find_child(node, "statement_block")
        if body:
            self.translate_statements(body)
        else:
            self.em.emit("pass")
        self.em.indent -= 1

    def _stmt_while(self, node) -> None:
        """Translate while loops."""
        condition_node = find_child(node, "parenthesized_expression")
        if condition_node:
            cond = self.em.translate_node(condition_node)
            if cond.startswith('(') and cond.endswith(')'):
                cond = cond[1:-1]
        else:
            cond = "True"

        self.em.emit(f"while {cond}:")
        self.em.indent += 1
        body = find_child(node, "statement_block")
        if body:
            self.translate_statements(body)
        else:
            self.em.emit("pass")
        self.em.indent -= 1

    def _stmt_try(self, node) -> None:
        """Translate try/catch."""
        self.em.emit("try:")
        self.em.indent += 1
        body = find_child(node, "statement_block")
        if body:
            self.translate_statements(body)
        else:
            self.em.emit("pass")
        self.em.indent -= 1

        catch_clause = find_child(node, "catch_clause")
        if catch_clause:
            self.em.emit("except Exception:")
            self.em.indent += 1
            body = find_child(catch_clause, "statement_block")
            if body:
                self.translate_statements(body)
            else:
                self.em.emit("pass")
            self.em.indent -= 1
        else:
            self.em.emit("except Exception:")
            self.em.indent += 1
            self.em.emit("pass")
            self.em.indent -= 1

    def _stmt_throw(self, node) -> None:
        """Translate throw statements."""
        raw = self.em.text(node)
        raw = raw.replace("throw ", "raise ").rstrip(";")
        raw = re.sub(r'new\s+Error\(', 'Exception(', raw)
        self.em.emit(self.em._basic_translate(raw))

    def _stmt_switch(self, node) -> None:
        """Translate switch to if/elif chain."""
        # Get the switch expression
        condition_node = find_child(node, "parenthesized_expression")
        if condition_node:
            switch_expr = self.em.translate_node(condition_node)
            if switch_expr.startswith('(') and switch_expr.endswith(')'):
                switch_expr = switch_expr[1:-1]
        else:
            switch_expr = "_switch_val"

        body = find_child(node, "switch_body")
        if not body:
            self.em.emit("pass  # empty switch")
            return

        first = True
        for case_node in body.children:
            if case_node.type == "switch_case":
                val_node = None
                for c in case_node.children:
                    if c.type not in ("case", ":", "default"):
                        val_node = c
                        break
                if val_node:
                    val = self.em.translate_node(val_node)
                    keyword = "if" if first else "elif"
                    self.em.emit(f"{keyword} {switch_expr} == {val}:")
                    first = False
                else:
                    self.em.emit("else:")

                self.em.indent += 1
                has_body = False
                for c in case_node.children:
                    if c.type in ("case", ":", "default") or c == val_node:
                        continue
                    if c.type == "break_statement":
                        continue  # Skip break in switch
                    self.translate_statement(c)
                    has_body = True
                if not has_body:
                    self.em.emit("pass")
                self.em.indent -= 1
            elif case_node.type == "switch_default":
                self.em.emit("else:")
                self.em.indent += 1
                has_body = False
                for c in case_node.children:
                    if c.type in ("default", ":"):
                        continue
                    if c.type == "break_statement":
                        continue
                    self.translate_statement(c)
                    has_body = True
                if not has_body:
                    self.em.emit("pass")
                self.em.indent -= 1

    @staticmethod
    def _to_snake(name: str) -> str:
        """Convert camelCase to snake_case."""
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _translate_collection(self, raw: str, loop_var: str) -> str:
        """Translate a collection expression, handling .filter() etc."""
        # Pattern: x.filter(({ prop }) => { return prop; })
        m = re.search(
            r'^(.+?)\.filter\(\s*'
            r'\(\{\s*(\w+)\s*\}\)\s*=>\s*\{?\s*'
            r'return\s+(\w+)\s*;?\s*\}?\s*\)$',
            raw, re.DOTALL,
        )
        if m:
            coll = self.em._basic_translate(m.group(1))
            prop = m.group(2)
            return f'[{loop_var} for {loop_var} in {coll} if {loop_var}.get("{prop}")]'

        # Pattern: x.filter(({ prop }) => prop)
        m = re.search(
            r'^(.+?)\.filter\(\s*'
            r'\(\{\s*(\w+)\s*\}\)\s*=>\s*\2\s*\)$',
            raw, re.DOTALL,
        )
        if m:
            coll = self.em._basic_translate(m.group(1))
            prop = m.group(2)
            return f'[{loop_var} for {loop_var} in {coll} if {loop_var}.get("{prop}")]'

        # Pattern: x.filter(item => condition)
        m = re.search(
            r'^(.+?)\.filter\(\s*'
            r'\(?\s*(\w+)\s*\)?\s*=>\s*\{?\s*'
            r'return\s+(.+?)\s*;?\s*\}?\s*\)$',
            raw, re.DOTALL,
        )
        if m:
            coll = self.em._basic_translate(m.group(1))
            param = m.group(2)
            body = self.em._basic_translate(m.group(3))
            body = body.replace(param + '.', f'{loop_var}.')
            return f'[{loop_var} for {loop_var} in {coll} if {body}]'

        # No filter pattern matched — just translate normally
        return self.em._basic_translate(raw)
