# Explanation of the submission
 
## Solution

This submission implements a TypeScript-to-Python translator (`tt`) that converts TypeScript source code from the Ghostfolio wealth management software into equivalent Python code. The translator uses tree-sitter AST parsing to accurately understand and transform TypeScript constructs into idiomatic Python.

## Translator Architecture

The translator is built as a multi-stage pipeline:

### Core Components

1. **TypeScript Parser (`ts_parser.py`)**
   - Uses tree-sitter library to parse TypeScript/JavaScript code into an Abstract Syntax Tree (AST)
   - Handles both TypeScript-specific syntax and JavaScript features
   - Provides source bytes for accurate position tracking during translation

2. **AST Utilities (`ast_utils.py`)**
   - Helper functions for navigating the tree-sitter AST
   - `node_text()` - Extracts text content from AST nodes
   - `find_child()` / `find_children()` - Locates direct children of a given type
   - `find_descendant()` / `find_descendants()` - Recursively finds nodes anywhere in the tree
   - Enables reliable AST traversal and analysis

3. **Python Code Emitter (`py_emitter.py`)**
   - Translates tree-sitter AST nodes into Python source code
   - Manages indentation levels for proper Python formatting
   - Handles language-specific transformations:
     - `this.x` → `self.x` (object context)
     - Type annotations removal
     - Optional chaining (`?.`) → conditional fallbacks
     - `let`/`const`/`var` → plain Python assignment
     - Arrow functions → lambdas or inline code
     - TypeScript types → Python equivalents

4. **Statement Translator (`statements.py`)**
   - Translates control flow statements (if/else, for loops, etc.)
   - Handles complex nested structures
   - Preserves logic semantics across languages

5. **Main Translator (`translator.py`)**
   - Orchestrates the translation pipeline
   - Entry point: `translate_typescript_to_python(ts_source: str) -> str`
   - Processes class declarations, method definitions, and fields
   - Includes `run_translation()` for batch processing from the file system
   - Generates properly formatted Python modules with headers and imports

### Translation Process

1. Source TypeScript file is parsed into an AST using tree-sitter
2. AST is traversed depth-first, identifying key constructs (classes, methods, fields)
3. Each construct is transformed using language-specific rules
4. Python code is emitted line-by-line with proper indentation
5. Post-processing fixes common artifacts and normalizes output
6. Final code is wrapped with necessary imports and module headers

### Key Features

- **Semantic-preserving translation**: Maintains the logic and behavior of the original TypeScript
- **AST-based approach**: More reliable than regex or token-based parsing
- **Selective translation**: Filters imports and comments, focuses on executable code
- **Inheritance handling**: Properly translates class hierarchies
- **Parameter extraction**: Handles rest parameters, optional parameters, and destructuring patterns
- **Code cleanup**: Post-processing removes duplication and normalizes whitespace

## Coding approach

The team approached this problem by:

Make 1+ individual branch(es)

Approach with ai agents (in ide, opencode, github agents, vscode agent app, codex)

Find the best looking branches and keep iterating on them
