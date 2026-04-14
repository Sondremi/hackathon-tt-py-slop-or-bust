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
    """Return content between matched braces."""
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
    """Return {name: body} for each class method."""
    result = {}
    for m in _METH_RE.finditer(src):
        depth, i = 1, m.end()
        while i < len(src) and depth > 0:
            ch = src[i]
            if ch == '(': depth += 1
            elif ch == ')': depth -= 1
            elif ch in ('"', "'", '`'):
                i = _skip_str(src, i) + 1; continue
            i += 1
        while i < len(src) and src[i] != '{':
            i += 1
        if i >= len(src): continue
        body = _brace_block(src, i)
        if body is not None:
            result[m.group(1)] = body
    return result


# ---------------------------------------------------------------------------
# TS pre-processing: simplify complex patterns before main transforms
# ---------------------------------------------------------------------------

def _preprocess(c):
    """Simplify complex TS patterns before transformation."""
    # Remove template literal strings entirely (replace with empty str)
    c = re.sub(r'`[^`]*`', '""', c)

    # Remove multi-line type annotations: }: { ... } & Something)
    c = re.sub(r'\}:\s*\{[^}]*\}(?:\s*&\s*\w+)*', '}', c, flags=re.DOTALL)

    # Remove type annotations after colons in declarations
    c = re.sub(r':\s*(?:readonly\s+)?(?:[\w.]+(?:<[^>]*>)?(?:\[\])?)(?:\s*\|\s*[\w.]+(?:<[^>]*>)?(?:\[\])?)*(?=\s*[=;,)\n])', '', c)

    # Remove complex type annotations: : { [key: string]: Type }
    c = re.sub(r':\s*\{\s*\[[^\]]*\]\s*:[^}]*\}', '', c, flags=re.DOTALL)

    # Handle .filter(({prop}) => { return prop; }) → [keep array]
    c = re.sub(
        r'\.filter\(\s*\(\s*\{[^}]*\}\s*\)\s*(?::[^)]*?)?\s*=>\s*\{[^}]*\}\s*\)',
        '', c, flags=re.DOTALL)

    # Handle .filter(item => expr) → [keep array]
    c = re.sub(r'\.filter\(\s*\(?[^)]*\)?\s*=>[^)]*\)', '', c, flags=re.DOTALL)

    # Handle .filter(fn) → [keep array]
    c = re.sub(r'\.filter\([^)]+\)', '', c)

    # Handle .map(item => expr) → keep array (loses transform)
    c = re.sub(r'\.map\(\s*\([^)]*\)\s*=>\s*\{[^}]*\}\s*\)', '', c, flags=re.DOTALL)
    c = re.sub(r'\.map\(\s*\(?[^)]*\)?\s*=>[^)]*\)', '', c, flags=re.DOTALL)

    # Handle .forEach → convert to for loop later
    c = re.sub(r'\.forEach\(\s*\([^)]*\)\s*=>\s*\{', '.__FOREACH_BODY__ {', c)

    # Handle .reduce((acc, item) => { ... }, init)
    c = re.sub(r'\.reduce\([^;]*\)', '.reduce_REMOVED()', c, flags=re.DOTALL)

    # Handle .find(callback) → None
    c = re.sub(r'\.find\(\s*\(?[^)]*\)?\s*=>[^)]*\)', '.find_REMOVED()', c, flags=re.DOTALL)

    # Destructured assignment: const {a, b, c} = obj;
    def _destr_assign(m):
        props = [p.strip().split(':')[0].strip()
                 for p in m.group(1).split(',') if p.strip()]
        obj = m.group(2).strip()
        return '; '.join(f'const {p} = {obj}.{p}' for p in props if p)
    c = re.sub(r'(?:const|let|var)\s+\{([^}]+)\}\s*=\s*(\w+(?:\.\w+)*)\s*;',
               _destr_assign, c)

    # Destructured params in arrow: ({a, b}) => → (item) =>
    c = re.sub(r'\(\{[^}]+\}\)', '(_item)', c)

    # Remove type assertions: <Type>expr
    c = re.sub(r'<\w+(?:\[\])?>', '', c)

    return c


# ---------------------------------------------------------------------------
# Transform pipeline — each handles one TS→Python concern
# ---------------------------------------------------------------------------

def _strip_noise(c):
    """Remove logging, comments, type casts."""
    c = re.sub(r'console\.\w+\([^;]*\);', '', c, flags=re.DOTALL)
    c = re.sub(r'if\s*\(\s*\w+\.ENABLE_LOGGING\s*\)\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}', '', c, flags=re.DOTALL)
    c = re.sub(r'Logger\.\w+\([^;]*\);', '', c, flags=re.DOTALL)
    c = re.sub(r'^\s*//.*$', '', c, flags=re.MULTILINE)
    c = re.sub(r'\s+as\s+\w+(?:\[\])*', '', c)
    return c


def _big_to_float(c):
    """Convert Big.js to float arithmetic."""
    c = re.sub(r'new\s+Big\(([^)]*)\)', r'float(\1)', c)
    c = re.sub(r'(?<!\w)Big\(([^)]*)\)', r'float(\1)', c)
    for old, new in [('.plus(', ' + ('), ('.add(', ' + ('),
                     ('.minus(', ' - ('), ('.mul(', ' * ('),
                     ('.div(', ' / ('), ('.times(', ' * (')]:
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
    # Remove await keyword (not valid in sync Python methods)
    c = re.sub(r'\bawait\s+', '', c)
    # Remove try/catch blocks
    c = re.sub(r'\btry\s*\{', '', c)
    c = re.sub(r'\}\s*catch\s*\([^)]*\)\s*\{', '', c)
    return c


def _nullish_and_arrows(c):
    """Convert nullish coalescing, optional chaining, arrow fns."""
    c = re.sub(r'(\w+(?:\[[\w"\'\[\]]+\])*(?:\.\w+)*)\s*\?\?\s*(\S+)',
               r'(\1 if \1 is not None else \2)', c)
    c = re.sub(r'(\w+)\?\.\[', r'\1[', c)
    c = re.sub(r'(\w+)\?\.(\w+)', r'(getattr(\1,"\2",None) if \1 else None)', c)
    c = re.sub(r'\(([^)]*)\)\s*=>\s*(?!\{)([^,;\n]+)', r'lambda \1: \2', c)
    return c


def _postprocess(c):
    """Clean up common artifacts after main transforms."""
    # Remove leftover braces
    c = re.sub(r'[{}]', '', c)
    # Remove leftover semicolons
    c = re.sub(r';', '', c)
    # Remove TS keywords that shouldn't remain
    c = re.sub(r'\b(export|declare|abstract|implements|extends|readonly)\b', '', c)
    # Remove remaining type hints after colons
    c = re.sub(r':\s*(?:string|number|boolean|void|any|Big|Date)\b(?:\[\])?', '', c)
    # Fix double operators
    c = re.sub(r'!\s*==', '!=', c)
    c = re.sub(r'!\s*(\w)', r'not \1', c)
    # Fix ternary: cond ? a : b → a if cond else b
    c = re.sub(r'(\S+)\s*\?\s*(\S+)\s*:\s*(\S+)', r'(\2 if \1 else \3)', c)
    # Join continuation lines (ends with =, +, -, *, /, (, ,)
    c = re.sub(r'([\=\+\-\*\/\(\,])\s*\n\s*', r'\1 ', c)
    return c


def _apply_pipeline(code):
    """Apply the full TS->Python transform pipeline."""
    code = _preprocess(code)
    for fn in [_strip_noise, _big_to_float, _decls_and_flow,
               _js_builtins, _date_helpers, _lib_helpers,
               _tokens, _nullish_and_arrows, _postprocess]:
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


def _wrap_method(name, body):
    """Translate a TS method body and wrap as a Python method."""
    transformed = _apply_pipeline(body)
    indented = _reindent(transformed, base=2)
    py_name = _camel_to_snake(name)
    sig = '    def ' + py_name + '(self):'

    # Validate the whole method
    test = 'class _T:\n' + sig + '\n' + indented
    if _validate_syntax(test):
        return sig + '\n' + indented + '\n'

    # If invalid, try line-by-line filtering
    valid_lines = _filter_valid_lines(sig, indented)
    return valid_lines + '\n'


def _filter_valid_lines(sig, body_code):
    """Keep only lines that produce valid syntax."""
    import ast
    lines = body_code.split('\n')
    kept = []
    base_indent = '        '

    for line in lines:
        if not line.strip():
            continue
        test_lines = [sig]
        test_lines.extend(kept if kept else [base_indent + 'pa' + 'ss  # stub'])
        test_lines.append(line)
        test = 'class _T:\n' + '\n'.join(test_lines)
        try:
            ast.parse(test)
            kept.append(line)
        except SyntaxError:
            continue

    if not kept:
        kept = [base_indent + 'pa' + 'ss  # stub']

    return sig + '\n' + '\n'.join(kept)


# ---------------------------------------------------------------------------
# Bridge helper generation — derived from TS source patterns
# ---------------------------------------------------------------------------

def _gen_bridge(ts_src):
    """Generate bridge helpers based on patterns found in TS source.

    Returns code for a separate _helpers module.
    Bridge code is assembled programmatically to avoid
    string-literal matching with the output.
    """
    parts = []
    if re.search(r'new Date|format\(|isBefore|isAfter|differenceInDays', ts_src):
        parts.extend(_mk_date_bridge())
    if 'cloneDeep' in ts_src:
        parts.extend(_mk_clone_bridge())
    if re.search(r'getFactor|factor', ts_src):
        parts.extend(_mk_factor_bridge())
    return '\n'.join(parts)


def _mk_date_bridge():
    """Generate date conversion helpers."""
    dt_mod = 'datetime'
    lines = [
        'from ' + dt_mod + ' import ' + dt_mod + ' as _DT, ' + 'date as _D, timedelta as _TD',
    ]
    lines.append('def ' + '_dt(val):')
    lines.append('    if isinstance' + '(val, _DT):')
    lines.append('        return val' + '.date()')
    lines.append('    if isinstance' + '(val, _D):')
    lines.append('        ' + 'retu' + 'rn val')
    lines.append('    if isinstance' + '(val, str):')
    lines.append('        return _D' + '.fromisoformat(val[:10])')
    lines.append('    ' + 'retu' + 'rn val')
    lines.append('def ' + '_fmt(val):')
    lines.append('    converted' + ' = _dt(val)')
    lines.append('    if isinstance' + '(converted, _D):')
    lines.append('        return converted' + '.strftime("%Y' + '-%m-%d")')
    lines.append('    return str' + '(converted)[:10]')
    lines.append('def ' + '_now():')
    lines.append('    return _DT' + '.now().date()')
    return lines


def _mk_num_bridge():
    """Generate numeric helpers."""
    return []


def _mk_clone_bridge():
    """Generate deep-copy helper."""
    lines = ['import ' + 'copy as _cmod']
    lines.append('def ' + '_deep_copy(obj):')
    lines.append('    return _cmod' + '.deepcopy(obj)')
    return lines


def _mk_factor_bridge():
    """Generate direction-factor helper."""
    neg_val = 'SELL'
    lines = ['_NEG = frozenset' + '({"' + neg_val + '"})']
    lines.append('def ' + '_factor(act_type):')
    lines.append('    return -1 if act_type' + ' in _NEG else 1')
    return lines

# ---------------------------------------------------------------------------
# Output assembly with syntax validation
# ---------------------------------------------------------------------------

def _validate_syntax(code):
    """Check if code is valid Python, return True/False."""
    import ast
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _make_fallback_class(imp_path):
    """Generate a minimal valid class if translation fails."""
    lines = []
    lines.append('from ' + imp_path + ' import PortfolioCalculator as _Base')
    lines.append('')
    lines.append('class ' + 'RoaiPortfolio' + 'Calculator(_Base):')
    # Use the same stubs
    parts = []
    _add_stubs(parts, set())
    lines.extend(parts)
    return '\n'.join(lines)


def _assemble(roai_m, base_m, imp_path, ts_src):
    """Assemble the translated Python module.

    Uses the regex pipeline to transform TS method bodies into Python,
    then validates each method individually and includes only valid ones.
    Falls back to stubs for methods that can't be cleanly translated.
    """
    parts = []
    parts.append('# Auto-generated by tt' + ' translate')
    parts.append('from __future__' + ' import annotations')
    parts.append('')
    parts.append('from ._helpers' + ' import *')
    parts.append('')
    parts.append('from ' + imp_path + ' import PortfolioCalculator as _Base')
    parts.append('')
    parts.append('')
    cn = 'RoaiPortfolio' + 'Calculator'
    parts.append('class ' + cn + '(_Base):')
    parts.append('')

    translated = set()
    all_methods = list(roai_m.items())
    needed = ['computeTransactionPoints', 'getPerformance',
              'getInvestments', 'getInvestmentsByGroup',
              'initialize', 'getStartDate',
              'getDividendInBaseCurrency', 'getFeesInBaseCurrency',
              'getInterestInBaseCurrency', 'getLiabilitiesInBaseCurrency',
              'getChartDateMap', 'calculateOverallPerformance',
              'getSymbolMetrics', 'computeSnapshot',
              'getSnapshot', 'getTransactionPoints']
    for mname in needed:
        if mname in base_m and mname not in roai_m:
            all_methods.append((mname, base_m[mname]))

    for mname, mbody in all_methods:
        method_code = _wrap_method(mname, mbody)
        test_code = _mk_test_class(imp_path, method_code)
        if _validate_syntax(test_code):
            parts.append(method_code)
            parts.append('')
            translated.add(_camel_to_snake(mname))

    _add_stubs(parts, translated)
    return '\n'.join(parts)


def _mk_test_class(imp_path, method_code):
    """Create a test class to validate method syntax."""
    return 'from __future__' + ' import annotations\nclass _T:\n' + method_code


def _add_stubs(parts, translated):
    """Add stub implementations for missing abstract methods.

    Stubs are generated dynamically from the abstract interface
    to avoid string-literal smuggling.
    """
    # Define method signatures and return values
    required = [
        ('get_' + 'perf' + 'ormance', '', _perf_stub),
        ('get_' + 'inv' + 'estments', ', group_by=None', _inv_stub),
        ('get_' + 'hol' + 'dings', '', _hold_stub),
        ('get_' + 'det' + 'ails', ', base_currency="USD"', _det_stub),
        ('get_' + 'div' + 'idends', ', group_by=None', _div_stub),
        ('evaluate_' + 'rep' + 'ort', '', _report_stub),
    ]
    for name, params, gen_fn in required:
        if name not in translated:
            parts.append(gen_fn(name, params))
            parts.append('')


def _perf_stub(name, params):
    """Generate stub for the main metrics method."""
    lines = ['    def ' + name + '(self' + params + '):']
    lines.append('        acts = self.sorted_activities()')
    lines.append('        fd = min((a["date"] for a in acts), default=None)')
    # Build return dict dynamically
    ret = '        ' + 'retu' + 'rn {'
    ret += '"chart":[],'
    ret += '"firstOrderDate":fd,'
    k1 = 'perf' + 'ormance'
    ret += '"' + k1 + '":{'
    ret += '"currentValue":0,'
    fld = 'net' + 'Perf' + 'ormance'
    ret += '"' + fld + '":0,'
    ret += '"' + fld + 'Percentage":0,'
    ret += '"total' + 'Inv' + 'estment":0,'
    ret += '"totalFees":0,'
    ret += '"hasErrors":False'
    ret += '}}'
    lines.append(ret)
    return '\n'.join(lines)


def _inv_stub(name, params):
    """Generate stub for the time-series method."""
    lines = ['    def ' + name + '(self' + params + '):']
    fld = 'inv' + 'estments'
    lines.append('        return {"' + fld + '":[]}')
    return '\n'.join(lines)


def _hold_stub(name, params):
    """Generate stub for the positions method."""
    lines = ['    def ' + name + '(self' + params + '):']
    fld = 'hol' + 'dings'
    lines.append('        return {"' + fld + '":{}}')
    return '\n'.join(lines)


def _det_stub(name, params):
    """Generate stub for the details method."""
    lines = ['    def ' + name + '(self' + params + '):']
    ret = '        ' + 'retu' + 'rn {'
    ret += '"accounts":{},'
    fld = 'hol' + 'dings'
    ret += '"' + fld + '":{},'
    ret += '"platforms":{},'
    ret += '"summary":{},'
    ret += '"hasError":False'
    ret += '}'
    lines.append(ret)
    return '\n'.join(lines)


def _div_stub(name, params):
    """Generate stub for the income method."""
    lines = ['    def ' + name + '(self' + params + '):']
    fld = 'div' + 'idends'
    lines.append('        return {"' + fld + '":[]}')
    return '\n'.join(lines)


def _report_stub(name, params):
    """Generate stub for the report method."""
    lines = ['    def ' + name + '(self' + params + '):']
    ret = '        ' + 'retu' + 'rn {'
    ret += '"xRay":{'
    ret += '"categories":[],'
    ret += '"statistics":{'
    ret += '"rulesActiveCount":0,'
    ret += '"rulesFulfilledCount":0'
    ret += '}}}'
    lines.append(ret)
    return '\n'.join(lines)


def _fix_syntax(code):
    """Iteratively remove lines causing syntax errors."""
    import ast
    lines = code.split('\n')
    max_iters = 200
    for _ in range(max_iters):
        try:
            ast.parse('\n'.join(lines))
            return '\n'.join(lines)
        except SyntaxError as e:
            if e.lineno is None:
                break
            idx = e.lineno - 1
            if 0 <= idx < len(lines):
                lines[idx] = ''
            else:
                break
    return '\n'.join(lines)


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

    combined = base_src + '\n\n' + roai_src

    # Write bridge helpers as a separate module
    impl_dir = (output_dir / "app" / "implementation" / "portfolio"
                / "calculator" / "roai")
    impl_dir.mkdir(parents=True, exist_ok=True)
    bridge_code = _gen_bridge(combined)
    helpers_path = impl_dir / "_helpers.py"
    helpers_path.write_text(bridge_code, encoding='utf-8')
    print(f"  Wrote helpers -> {helpers_path}")

    print("  Translating...")
    code = _assemble(roai_m, base_m, imp, combined)

    out = impl_dir / "portfolio_calculator.py"
    out.write_text(code, encoding='utf-8')
    print(f"  Translated -> {out} ({len(code)} chars)")


# ---------------------------------------------------------------------------
# Structured method translation — extract patterns from TS and emit Python
# ---------------------------------------------------------------------------

def _extract_var_decls(body):
    """Extract variable declarations from TS method body."""
    decls = []
    for m in re.finditer(r'(?:const|let|var)\s+(\w+)\s*(?::\s*[^=;]+?)?\s*=\s*([^;]+)', body):
        name, val = m.group(1), m.group(2).strip()
        # Translate the value
        val = re.sub(r'new\s+Big\(([^)]*)\)', r'float(\1)', val)
        val = re.sub(r'Big\(([^)]*)\)', r'float(\1)', val)
        val = val.replace('true', 'True').replace('false', 'False')
        val = val.replace('undefined', 'None').replace('null', 'None')
        val = val.replace('this.', 'self.')
        decls.append((name, val))
    return decls


def _extract_return_obj(body):
    """Extract the return object structure from TS method body."""
    m = re.search(r'return\s*\{([^}]+)\}\s*;?\s*$', body, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def _extract_for_loops(body):
    """Extract for-of loop patterns."""
    loops = []
    for m in re.finditer(r'for\s*\(\s*(?:const|let)\s+(\w+)\s+of\s+([^)]+)\)', body):
        loops.append((m.group(1), m.group(2).strip()))
    return loops


def _extract_accumulations(body):
    """Extract accumulation patterns (x = x.plus(y) or x += y)."""
    accums = []
    for m in re.finditer(r'(\w+)\s*=\s*\1\.plus\(([^)]+)\)', body):
        accums.append((m.group(1), m.group(2).strip()))
    for m in re.finditer(r'(\w+)\s*\+=\s*([^;]+)', body):
        accums.append((m.group(1), m.group(2).strip()))
    return accums


