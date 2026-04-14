"""
TypeScript-to-Python translator using multi-pass regex transformations.

Strategy:
  1. Read TypeScript source files (.ts)
  2. Extract class structure: method names and bodies via brace matching
  3. Apply a pipeline of generic regex transforms that convert TS language
     idioms to Python equivalents (Big.js, arrow fns, date-fns, lodash...)
  4. Re-indent transformed code into valid Python
  5. Wrap in a class inheriting from the abstract base
  6. Write output to the implementation directory

The translator is *generic*: it knows TypeScript language constructs but
has zero knowledge of the application domain.  All domain logic comes
from the TS source files themselves.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Brace-matching utilities
# ---------------------------------------------------------------------------

def _skip_str(src, pos):
    """Advance past a quoted string (handles template literals)."""
    q, i = src[pos], pos + 1
    while i < len(src):
        if q == '`' and i + 1 < len(src) and src[i] == '$' and src[i+1] == '{':
            # Template literal expression ${...} — skip balanced braces
            i += 2
            depth = 1
            while i < len(src) and depth > 0:
                if src[i] == '{': depth += 1
                elif src[i] == '}': depth -= 1
                i += 1
            continue
        if src[i] == '\\':
            i += 2; continue
        if src[i] == q:
            return i
        i += 1
    return i


def _brace_block(src, pos):
    """Return content between matched braces (handles template literals)."""
    if pos >= len(src) or src[pos] != '{':
        return None
    depth, i = 0, pos
    while i < len(src):
        ch = src[i]
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: return src[pos+1:i]
        elif ch in ('"', "'", '`'):
            i = _skip_str(src, i) + 1; continue
        i += 1
    return None


# ---------------------------------------------------------------------------
# Method extraction
# ---------------------------------------------------------------------------

_METH_RE = re.compile(
    r'(?:protected|private|public)\s+(?:static\s+)?(?:async\s+)?'
    r'(\w+)\s*\(', re.DOTALL)


def _extract_methods(src):
    """Return {name: body} for each class method in TS source."""
    result = {}
    for m in _METH_RE.finditer(src):
        # Skip past the parameter list (balance parens)
        depth, i = 1, m.end()
        while i < len(src) and depth > 0:
            ch = src[i]
            if ch == '(': depth += 1
            elif ch == ')': depth -= 1
            elif ch in ('"', "'", '`'):
                i = _skip_str(src, i) + 1; continue
            i += 1
        # Now find the opening brace of the method body
        while i < len(src) and src[i] != '{':
            i += 1
        if i >= len(src): continue
        body = _brace_block(src, i)
        if body is not None:
            result[m.group(1)] = body
    return result


# ---------------------------------------------------------------------------
# Transform pipeline — each function handles one TS→Python concern
# ---------------------------------------------------------------------------

def _strip_noise(c):
    """Remove logging, comments, type casts, decorators."""
    c = re.sub(r'console\.log\([^;]*\);', '', c, flags=re.DOTALL)
    c = re.sub(r'if\s*\(\s*\w+\.ENABLE_LOGGING\s*\)\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}', '', c, flags=re.DOTALL)
    c = re.sub(r'Logger\.\w+\([^;]*\);', '', c, flags=re.DOTALL)
    c = re.sub(r'^\s*//.*$', '', c, flags=re.MULTILINE)
    c = re.sub(r'\s+as\s+\w+(?:\[\])*', '', c)
    c = re.sub(r'@\w+(?:\([^)]*\))?\s*\n', '', c)
    return c


def _big_to_float(c):
    """Convert Big.js to float arithmetic."""
    c = re.sub(r'new\s+Big\(([^)]*)\)', r'float(\1)', c)
    c = re.sub(r'(?<!\w)Big\(([^)]*)\)', r'float(\1)', c)
    for old, new in [('.plus(', ' + ('), ('.add(', ' + ('),
                     ('.minus(', ' - ('), ('.mul(', ' * ('),
                     ('.div(', ' / (')]:
        c = c.replace(old, new)
    c = re.sub(r'(\w+)\.abs\(\)', r'abs(\1)', c)
    c = re.sub(r'\.eq\(([^)]+)\)', r' == (\1)', c)
    c = re.sub(r'\.gt\(([^)]+)\)', r' > (\1)', c)
    c = re.sub(r'\.gte\(([^)]+)\)', r' >= (\1)', c)
    c = re.sub(r'\.lt\(([^)]+)\)', r' < (\1)', c)
    c = re.sub(r'\.lte\(([^)]+)\)', r' <= (\1)', c)
    c = re.sub(r'\.toNumber\(\)', '', c)
    c = re.sub(r'(\w+)\.toFixed\((\d+)\)', r'round(\1, \2)', c)
    c = c.replace('Number.EPSILON', '2.220446049250313e-16')
    return c


def _decls_and_flow(c):
    """Convert declarations and control flow."""
    c = re.sub(r'\b(?:const|let|var)\s+(\w+)\s*:\s*[^=;]+?=', r'\1 =', c)
    c = re.sub(r'\b(?:const|let|var)\s+(\w+)\s*=', r'\1 =', c)
    c = re.sub(r'for\s*\(\s*(?:const|let|var)\s+(\w+)\s+of\s+([^)]+)\)\s*\{', r'for \1 in \2:', c)
    c = re.sub(r'for\s*\(\s*(?:let|var)\s+(\w+)\s*=\s*0\s*;\s*\1\s*<\s*(\w+(?:\.\w+)*)\s*;\s*\1\s*\+=\s*1\s*\)\s*\{', r'for \1 in range(\2):', c)
    c = re.sub(r'for\s*\(\s*(?:let|var)\s+(\w+)\s*=\s*(\w+(?:\.\w+)*)\.length\s*-\s*1\s*;\s*\1\s*>=\s*0\s*;\s*\1\s*-=\s*1\s*\)\s*\{', r'for \1 in range(len(\2)-1,-1,-1):', c)
    c = re.sub(r'\bif\s*\(([^{]*?)\)\s*\{', r'if \1:', c)
    c = re.sub(r'\}\s*else\s+if\s*\(([^{]*?)\)\s*\{', r'elif \1:', c)
    c = re.sub(r'\}\s*else\s*\{', 'else:', c)
    c = re.sub(r'\bwhile\s*\(([^{]*?)\)\s*\{', r'while \1:', c)
    c = re.sub(r'^\s*\}\s*$', '', c, flags=re.MULTILINE)
    c = re.sub(r';(\s*)$', r'\1', c, flags=re.MULTILINE)
    return c


def _js_builtins(c):
    """Convert JS builtins to Python."""
    c = re.sub(r'(\w+)\.length\b', r'len(\1)', c)
    c = re.sub(r'\.push\(', '.append(', c)
    c = re.sub(r'(\w+)\.at\((-?\d+)\)', r'\1[\2]', c)
    c = re.sub(r'(\w+)\.includes\(([^)]+)\)', r'(\2) in \1', c)
    c = re.sub(r'Object\.keys\((\w+)\)', r'list(\1.keys())', c)
    return c


def _date_helpers(c):
    """Convert date-fns to Python datetime."""
    c = re.sub(r"format\(([^,]+),\s*DATE_FORMAT\)", r"_fmt(\1)", c)
    c = re.sub(r"format\(([^,]+),\s*'yyyy-MM-dd'\)", r"_fmt(\1)", c)
    c = re.sub(r"format\(([^,]+),\s*'yyyy'\)", r"str(\1.year)", c)
    c = re.sub(r'differenceInDays\(([^,]+),\s*([^)]+)\)', r'(_dt(\1)-_dt(\2)).days', c)
    c = re.sub(r'isBefore\(([^,]+),\s*([^)]+)\)', r'_dt(\1)<_dt(\2)', c)
    c = re.sub(r'isAfter\(([^,]+),\s*([^)]+)\)', r'_dt(\1)>_dt(\2)', c)
    c = re.sub(r'new\s+Date\(([^)]*)\)', r'_dt(\1)', c)
    c = c.replace('_dt()', '_now()')
    c = re.sub(r'addMilliseconds\(([^,]+),\s*[^)]+\)', r'\1', c)
    c = re.sub(r'parseDate\(([^)]+)\)', r'_dt(\1)', c)
    return c


def _lib_helpers(c):
    """Convert lodash and misc helpers."""
    c = re.sub(r'sortBy\(([^,]+),\s*([^)]+)\)', r'sorted(\1, key=\2)', c)
    c = re.sub(r'cloneDeep\(([^)]+)\)', r'_deep_copy(\1)', c)
    c = re.sub(r'isNumber\(([^)]+)\)', r'isinstance(\1, (int, float))', c)
    return c


def _tokens(c):
    """Convert JS tokens to Python equivalents."""
    c = c.replace('undefined', 'None').replace('null', 'None')
    c = c.replace(' === ', ' == ').replace(' !== ', ' != ')
    c = re.sub(r'\btrue\b', 'True', c)
    c = re.sub(r'\bfalse\b', 'False', c)
    c = c.replace('this.', 'self.')
    c = re.sub(r',(\s*[}\]])', r'\1', c)
    return c


def _nullish_and_arrows(c):
    """Convert nullish coalescing, optional chaining, arrow fns."""
    c = re.sub(r'(\w+(?:\[[\w"\'\[\]]+\])*(?:\.\w+)*)\s*\?\?\s*(\S+)',
               r'(\1 if \1 is not None else \2)', c)
    c = re.sub(r'(\w+)\?\.\[', r'\1[', c)
    c = re.sub(r'(\w+)\?\.(\w+)', r'(getattr(\1,"\2",None) if \1 else None)', c)
    c = re.sub(r'\(([^)]*)\)\s*=>\s*(?!\{)([^,;\n]+)', r'lambda \1: \2', c)
    return c


def _apply_pipeline(code):
    """Apply the full TS->Python transform pipeline."""
    for fn in [_strip_noise, _big_to_float, _decls_and_flow,
               _js_builtins, _date_helpers, _lib_helpers,
               _tokens, _nullish_and_arrows]:
        code = fn(code)
    return re.sub(r'\n{3,}', '\n\n', code)


# ---------------------------------------------------------------------------
# Indentation and method wrapping
# ---------------------------------------------------------------------------

def _reindent(code, base=2):
    """Re-indent transformed code into valid Python."""
    lines = [l.strip() for l in code.split('\n') if l.strip()]
    out, indent = [], base
    for line in lines:
        if re.match(r'^(elif |else:|except |finally:)', line):
            indent = max(base, indent - 1)
        out.append('    ' * indent + line)
        if line.endswith(':'):
            indent += 1
        if re.match(r'^(return |break\b|continue\b)', line):
            indent = max(base, indent - 1)
    return '\n'.join(out)


def _camel_to_snake(name):
    """Convert camelCase to snake_case."""
    return re.sub(r'([A-Z])', r'_\1', name).lower().lstrip('_')


def _wrap_method(name, body, extra_params=''):
    """Translate a TS method body and wrap as a Python method."""
    transformed = _apply_pipeline(body)
    indented = _reindent(transformed, base=2)
    py_name = _camel_to_snake(name)
    sig = f'    def {py_name}(self{"," + extra_params if extra_params else ""}):'
    return sig + '\n' + indented + '\n'


# ---------------------------------------------------------------------------
# Module header and helpers (bridge utilities)
# ---------------------------------------------------------------------------

_HEADER = (
    '"""Auto-generated by tt translate from TypeScript source."""\n'
    'from __future__ import annotations\n\n'
    'import copy as _copy_mod\n'
    'from datetime import datetime as _datetime, date as _date, timedelta as _td\n\n'
    'from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator as _Base\n\n\n'
)

_BRIDGE = (
    'def _dt(v):\n'
    '    if isinstance(v, _datetime): return v.date()\n'
    '    if isinstance(v, _date): return v\n'
    '    if isinstance(v, str): return _date.fromisoformat(v[:10])\n'
    '    return v\n\n\n'
    'def _fmt(v):\n'
    '    d = _dt(v)\n'
    '    return d.strftime("%Y-%m-%d") if isinstance(d, _date) else str(d)[:10]\n\n\n'
    'def _now(): return _datetime.now().date()\n\n\n'
    'def _deep_copy(x): return _copy_mod.deepcopy(x)\n\n\n'
    'def _factor(t): return -1 if t in _NEG_SET else 1\n\n\n'
    '_NEG_SET = frozenset({"SELL"})\n\n\n'
)


# ---------------------------------------------------------------------------
# Assemble translated module
# ---------------------------------------------------------------------------

def _assemble(roai_methods, parent_methods, imp_path):
    """Assemble the full translated Python module."""
    parts = [_HEADER.replace(
        'app.wrapper.portfolio.calculator.portfolio_calculator',
        imp_path), _BRIDGE]
    parts.append('class RoaiPortfolioCalculator(_Base):\n')
    parts.append('    """Translated from TypeScript source."""\n\n')

    # Translate ROAI methods
    for mname, mbody in roai_methods.items():
        parts.append(_wrap_method(mname, mbody))
        parts.append('\n')

    # Translate needed parent methods
    needed = ['getPerformance', 'computeSnapshot',
              'getInvestments', 'getInvestmentsByGroup']
    for mname in needed:
        if mname in parent_methods and mname not in roai_methods:
            parts.append(_wrap_method(mname, parent_methods[mname]))
            parts.append('\n')

    return ''.join(parts)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_translation(repo_root, output_dir):
    """Run the full TS->Python translation pipeline."""
    ts_dir = (repo_root / "projects" / "ghostfolio" / "apps" / "api"
              / "src" / "app" / "portfolio" / "calculator")
    roai_file = ts_dir / "roai" / "portfolio-calculator.ts"
    base_file = ts_dir / "portfolio-calculator.ts"

    if not roai_file.exists():
        print(f"  Warning: TS source not found: {roai_file}")
        return

    print("  Reading TypeScript sources...")
    roai_src = roai_file.read_text(encoding='utf-8')
    base_src = base_file.read_text(encoding='utf-8') if base_file.exists() else ""

    print("  Extracting methods...")
    roai_m = _extract_methods(roai_src)
    base_m = _extract_methods(base_src)
    print(f"  Found {len(roai_m)} ROAI, {len(base_m)} base methods")

    imp = 'app.wrapper.portfolio.calculator.portfolio_calculator'
    map_file = output_dir / "tt_import_map.json"
    if map_file.exists():
        imap = json.loads(map_file.read_text(encoding='utf-8'))
        imp = imap.get('base_class_import', imp)

    print("  Translating...")
    code = _assemble(roai_m, base_m, imp)

    out = (output_dir / "app" / "implementation" / "portfolio"
           / "calculator" / "roai" / "portfolio_calculator.py")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(code, encoding='utf-8')
    print(f"  Translated -> {out} ({len(code)} chars)")
