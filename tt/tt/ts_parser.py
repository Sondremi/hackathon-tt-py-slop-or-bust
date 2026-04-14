"""Tree-sitter TypeScript parser utilities.

Provides functions to parse TypeScript source code into an AST
using the tree-sitter library with the TypeScript grammar.
"""
from __future__ import annotations

from tree_sitter import Language, Parser
import tree_sitter_typescript as ts_typescript


def _create_parser() -> Parser:
    """Create a tree-sitter parser configured for TypeScript."""
    parser = Parser()
    lang = Language(ts_typescript.language_typescript())
    parser.language = lang
    return parser


_parser: Parser | None = None


def get_parser() -> Parser:
    """Get or create the singleton TypeScript parser."""
    global _parser
    if _parser is None:
        _parser = _create_parser()
    return _parser


def parse_typescript(source: str) -> tuple:
    """Parse TypeScript source code and return (tree, source_bytes).

    Returns the tree-sitter Tree and the source as bytes (needed for
    extracting node text).
    """
    source_bytes = source.encode("utf8")
    parser = get_parser()
    tree = parser.parse(source_bytes)
    return tree, source_bytes
