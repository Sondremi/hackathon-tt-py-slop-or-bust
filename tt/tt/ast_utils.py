"""AST node text extraction helpers for tree-sitter."""
from __future__ import annotations


def node_text(node, source_bytes: bytes) -> str:
    """Extract the text of a tree-sitter node."""
    return source_bytes[node.start_byte:node.end_byte].decode("utf8")


def find_children(node, type_name: str) -> list:
    """Find all direct children of a given type."""
    return [c for c in node.children if c.type == type_name]


def find_child(node, type_name: str):
    """Find first direct child of a given type."""
    for c in node.children:
        if c.type == type_name:
            return c
    return None


def find_descendants(node, type_name: str) -> list:
    """Find all descendants of a given type (recursive)."""
    results = []
    for c in node.children:
        if c.type == type_name:
            results.append(c)
        results.extend(find_descendants(c, type_name))
    return results


def find_descendant(node, type_name: str):
    """Find first descendant of a given type."""
    for c in node.children:
        if c.type == type_name:
            return c
        result = find_descendant(c, type_name)
        if result:
            return result
    return None
