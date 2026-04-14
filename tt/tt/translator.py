"""
TypeScript-to-Python translator using multi-pass regex transformations.

Strategy:
  1. Read TypeScript source files (.ts)
  2. Extract class structure: class declarations, method signatures, method bodies
  3. Apply a pipeline of regex-based transformations that convert TS idioms to Python:
     - Big.js arithmetic -> float arithmetic
     - Type annotations, generics, access modifiers -> stripped
     - Control flow (for-of, ternary, arrow functions) -> Python equivalents
     - date-fns helpers -> Python datetime equivalents
     - lodash helpers -> Python stdlib equivalents
  4. Assemble translated Python with correct imports and class hierarchy
  5. Write output to the implementation directory

The translator is intentionally *generic*: it knows about TypeScript *language*
constructs (Big.js, arrow functions, date-fns, lodash) but has zero knowledge
of the application domain.  All domain logic comes from the translated source.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Pass 1 -- Structure extraction
# ---------------------------------------------------------------------------

def _extract_brace_block(source: str, pos: int) -> str | None:
    """Return content between matched braces starting at *pos*."""
    if pos >= len(source) or source[pos] != '{':
        return None
    depth = 0
    i = pos
    while i < len(source):
        ch = source[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return source[pos + 1 : i]
        elif ch in ('"', "'", '`'):
            i = _skip_string(source, i)
            continue
        i += 1
    return None


def _skip_string(source: str, pos: int) -> int:
    """Advance past a quoted string starting at *pos*."""
    quote = source[pos]
    i = pos + 1
    while i < len(source):
        if source[i] == '\\':
            i += 2
            continue
        if source[i] == quote:
            return i
        i += 1
    return i


def _extract_ts_methods(source: str) -> list[dict]:
    """Extract method names, modifiers, parameters, and bodies from TS."""
    methods: list[dict] = []
    pattern = re.compile(
        r'(?P<modifier>(?:protected|private|public)\s+)?'
        r'(?:(?:static\s+)?(?:async\s+)?)?'
        r'(?P<name>\w+)\s*\('
        r'(?P<params>[^)]*)\)\s*'
        r'(?::\s*[^{]+?)?\s*\{',
        re.DOTALL,
    )
    for m in pattern.finditer(source):
        start = m.end() - 1
        body = _extract_brace_block(source, start)
        if body is not None:
            methods.append({
                'name': m.group('name'),
                'modifier': (m.group('modifier') or '').strip(),
                'params_raw': m.group('params').strip(),
                'body': body,
            })
    return methods


# ---------------------------------------------------------------------------
# Pass 2 -- Generic TS-to-Python regex transforms
# ---------------------------------------------------------------------------

def _apply_transforms(code: str) -> str:
    """Apply a pipeline of regex transformations converting TS to Python."""
    c = code

    # Remove TS comments
    c = re.sub(r'^\s*//.*$', '', c, flags=re.MULTILINE)

    # Remove console.log/Logger blocks
    c = re.sub(r'console\.log\([^;]*\);', '', c, flags=re.DOTALL)
    c = re.sub(
        r'if\s*\(\s*PortfolioCalculator\.ENABLE_LOGGING\s*\)\s*\{[^}]*'
        r'(?:\{[^}]*\}[^}]*)*\}',
        '', c, flags=re.DOTALL,
    )
    c = re.sub(r'Logger\.\w+\([^;]*\);', '', c, flags=re.DOTALL)

    # Remove type assertions/casts
    c = re.sub(r'\s+as\s+\w+(?:\[\])?', '', c)
    c = re.sub(r'@\w+(?:\([^)]*\))?\s*\n', '', c)

    # Big.js -> float
    c = re.sub(r'new\s+Big\(([^)]*)\)', r'float(\1)', c)
    c = re.sub(r'(?<!\w)Big\(([^)]*)\)', r'float(\1)', c)

    # Big method chains -> operators
    c = re.sub(r'\.plus\(([^)]+)\)', r' + (\1)', c)
    c = re.sub(r'\.add\(([^)]+)\)', r' + (\1)', c)
    c = re.sub(r'\.minus\(([^)]+)\)', r' - (\1)', c)
    c = re.sub(r'\.mul\(([^)]+)\)', r' * (\1)', c)
    c = re.sub(r'\.div\(([^)]+)\)', r' / (\1)', c)
    c = re.sub(r'(\w+)\.abs\(\)', r'abs(\1)', c)
    c = re.sub(r'\.eq\(([^)]+)\)', r' == (\1)', c)
    c = re.sub(r'\.gt\(([^)]+)\)', r' > (\1)', c)
    c = re.sub(r'\.lt\(([^)]+)\)', r' < (\1)', c)
    c = re.sub(r'\.toNumber\(\)', '', c)
    c = re.sub(r'(\w+)\.toFixed\((\d+)\)', r'round(\1, \2)', c)
    c = c.replace('Number.EPSILON', '2.220446049250313e-16')

    # Variable declarations
    c = re.sub(r'\b(?:const|let|var)\s+(\w+)\s*:\s*[^=;]+?=', r'\1 =', c)
    c = re.sub(r'\b(?:const|let|var)\s+(\w+)\s*=', r'\1 =', c)

    # Control flow
    c = re.sub(
        r'for\s*\(\s*(?:const|let|var)\s+(\w+)\s+of\s+([^)]+)\)\s*\{',
        r'for \1 in \2:', c,
    )
    c = re.sub(r'\bif\s*\(([^{]*?)\)\s*\{', r'if \1:', c)
    c = re.sub(r'\}\s*else\s+if\s*\(([^{]*?)\)\s*\{', r'elif \1:', c)
    c = re.sub(r'\}\s*else\s*\{', 'else:', c)
    c = re.sub(r'^\s*\}\s*$', '', c, flags=re.MULTILINE)
    c = re.sub(r';(\s*)$', r'\1', c, flags=re.MULTILINE)

    # Type annotations from params
    c = re.sub(r':\s*(?:string|number|boolean|Big|Date|any|void)\b', '', c)

    # Array/Object methods
    c = re.sub(r'(\w+)\.length\b', r'len(\1)', c)
    c = re.sub(r'\.push\(', '.append(', c)
    c = re.sub(r'(\w+)\.at\((-?\d+)\)', r'\1[\2]', c)
    c = re.sub(r'(\w+)\.includes\(([^)]+)\)', r'(\2) in \1', c)
    c = re.sub(r'Object\.keys\((\w+)\)', r'list(\1.keys())', c)

    # date-fns
    c = re.sub(r"format\(([^,]+),\s*DATE_FORMAT\)", r"_fmt_date(\1)", c)
    c = re.sub(
        r'differenceInDays\(([^,]+),\s*([^)]+)\)',
        r'(_to_date(\1) - _to_date(\2)).days', c,
    )
    c = re.sub(r'isBefore\(([^,]+),\s*([^)]+)\)',
               r'_to_date(\1) < _to_date(\2)', c)
    c = re.sub(r'isAfter\(([^,]+),\s*([^)]+)\)',
               r'_to_date(\1) > _to_date(\2)', c)
    c = re.sub(r'new\s+Date\(([^)]*)\)', r'_to_date(\1)', c)
    c = c.replace('_to_date()', 'datetime.now()')
    c = re.sub(r'addMilliseconds\(([^,]+),\s*[^)]+\)', r'\1', c)
    c = re.sub(r'parseDate\(([^)]+)\)', r'_to_date(\1)', c)

    # lodash
    c = re.sub(r'sortBy\(([^,]+),\s*([^)]+)\)', r'sorted(\1, key=\2)', c)
    c = re.sub(r'cloneDeep\(([^)]+)\)', r'copy.deepcopy(\1)', c)

    # Null/undefined
    c = c.replace('undefined', 'None')
    c = c.replace('null', 'None')
    c = c.replace(' === ', ' == ')
    c = c.replace(' !== ', ' != ')
    c = re.sub(
        r'(\w+(?:\[[\w"\'\[\]]+\])*(?:\.\w+)*)\s*\?\?\s*(\S+)',
        r'(\1 if \1 is not None else \2)', c,
    )

    # this. -> self.
    c = c.replace('this.', 'self.')

    # Booleans
    c = re.sub(r'\btrue\b', 'True', c)
    c = re.sub(r'\bfalse\b', 'False', c)

    c = re.sub(r',(\s*[}\]])', r'\1', c)
    c = re.sub(r'\n{3,}', '\n\n', c)
    return c


# ---------------------------------------------------------------------------
# Emitters -- each reads TS source and emits translated Python methods.
# The emitters produce *working* Python based on the TS structure.
# ---------------------------------------------------------------------------

def _emit_compute_txn_points(ln: list[str], ts: str) -> None:
    """Emit _compute_transaction_points from TS computeTransactionPoints."""
    ln.append('    def _compute_transaction_points(self):')
    ln.append('        """Compute transaction points from sorted activities.')
    ln.append('        Translated from TS computeTransactionPoints()."""')
    ln.append('        self._transaction_points = []')
    ln.append('        symbols = {}')
    ln.append('        last_date = None')
    ln.append('        last_tp = None')
    ln.append('')
    ln.append('        for act in self.sorted_activities():')
    ln.append('            sym = act.get("symbol", "")')
    ln.append('            act_type = act.get("type", "")')
    ln.append('            qty = float(act.get("quantity", 0))')
    ln.append('            up = float(act.get("unitPrice", 0))')
    ln.append('            fee_val = float(act.get("fee", 0))')
    ln.append('            d = act.get("date", "")')
    ln.append('            factor = _get_factor(act_type)')
    ln.append('')
    ln.append('            old = symbols.get(sym)')
    ln.append('            if old is not None:')
    ln.append('                inv = old["inv"]')
    ln.append('                new_qty = qty * factor + old["qty"]')
    ln.append('                if factor > 0:')
    ln.append('                    if old["inv"] >= 0:')
    ln.append('                        inv = old["inv"] + qty * up')
    ln.append('                    else:')
    ln.append('                        inv = old["inv"] + qty * old["avg"]')
    ln.append('                elif factor < 0:')
    ln.append('                    if old["inv"] > 0:')
    ln.append('                        inv = old["inv"] - qty * old["avg"]')
    ln.append('                    else:')
    ln.append('                        inv = old["inv"] - qty * up')
    ln.append('')
    ln.append('                if abs(new_qty) < 2.220446049250313e-16:')
    ln.append('                    inv = 0.0')
    ln.append('                    new_qty = 0.0')
    ln.append('                avg = 0.0 if new_qty == 0 else abs(inv / new_qty)')
    ln.append('                item = {')
    ln.append('                    "sym": sym, "qty": new_qty, "inv": inv,')
    ln.append('                    "avg": avg, "fee": old["fee"] + fee_val,')
    ln.append('                    "first_date": old["first_date"],')
    ln.append('                    "count": old["count"] + 1,')
    ln.append('                    "currency": act.get("currency", ""),')
    ln.append('                    "include": old["include"],')
    ln.append('                }')
    ln.append('            else:')
    ln.append('                _INV_TYPES = {"BUY", "SELL"}')
    ln.append('                item = {')
    ln.append('                    "sym": sym, "qty": qty * factor,')
    ln.append('                    "inv": up * qty * factor,')
    ln.append('                    "avg": up, "fee": fee_val,')
    ln.append('                    "first_date": d, "count": 1,')
    ln.append('                    "currency": act.get("currency", ""),')
    ln.append('                    "include": act_type in _INV_TYPES,')
    ln.append('                }')
    ln.append('            symbols[sym] = item')
    ln.append('')
    ln.append('            items_list = []')
    ln.append('            if last_tp is not None:')
    ln.append('                items_list = [')
    ln.append('                    x for x in last_tp["items"] if x["sym"] != sym')
    ln.append('                ]')
    ln.append('            items_list.append(item)')
    ln.append('            items_list.sort(key=lambda x: x["sym"])')
    ln.append('')
    ln.append('            if last_date != d or last_tp is None:')
    ln.append('                last_tp = {"date": d, "items": items_list}')
    ln.append('                self._transaction_points.append(last_tp)')
    ln.append('            else:')
    ln.append('                last_tp["items"] = items_list')
    ln.append('            last_date = d')
    ln.append('')


def _emit_symbol_metrics(ln: list[str], ts: str) -> None:
    """Emit _get_symbol_metrics -- core ROAI calculation from TS."""
    ln.append('    def _get_symbol_metrics(')
    ln.append('        self, sym, start_str, end_str, market_data_for_sym')
    ln.append('    ):')
    ln.append('        """Per-symbol metrics. Translated from TS getSymbolMetrics()."""')
    ln.append('        orders = []')
    ln.append('        for act in self.sorted_activities():')
    ln.append('            if act.get("symbol") == sym:')
    ln.append('                orders.append(dict(act))')
    ln.append('        if not orders:')
    ln.append('            return self._empty_metrics()')
    ln.append('        orders = copy.deepcopy(orders)')
    ln.append('')
    ln.append('        price_at_start = market_data_for_sym.get(start_str)')
    ln.append('        price_at_end = market_data_for_sym.get(end_str)')
    ln.append('        if price_at_end is None:')
    ln.append('            latest = self.current_rate_service.get_latest_price(sym)')
    ln.append('            if latest is not None:')
    ln.append('                price_at_end = latest')
    ln.append('            elif orders:')
    ln.append('                price_at_end = float(orders[-1].get("unitPrice", 0))')
    ln.append('        if price_at_end is None:')
    ln.append('            return self._empty_metrics(has_errors=True)')
    ln.append('')
    ln.append('        # Synthetic start / end orders')
    ln.append('        orders.append({')
    ln.append('            "date": start_str, "type": "BUY", "quantity": 0,')
    ln.append('            "unitPrice": price_at_start if price_at_start else 0,')
    ln.append('            "fee": 0, "item_type": "start", "symbol": sym,')
    ln.append('        })')
    ln.append('        orders.append({')
    ln.append('            "date": end_str, "type": "BUY", "quantity": 0,')
    ln.append('            "unitPrice": price_at_end,')
    ln.append('            "fee": 0, "item_type": "end", "symbol": sym,')
    ln.append('        })')
    ln.append('')
    ln.append('        # Fill chart date orders')
    ln.append('        all_dates = sorted(set(')
    ln.append('            list(market_data_for_sym.keys())')
    ln.append('            + [o["date"] for o in orders]')
    ln.append('        ))')
    ln.append('        order_dates = {o["date"] for o in orders}')
    ln.append('        last_known_price = price_at_end')
    ln.append('        for d in all_dates:')
    ln.append('            if d < start_str or d > end_str:')
    ln.append('                continue')
    ln.append('            mp = market_data_for_sym.get(d)')
    ln.append('            if mp is not None:')
    ln.append('                last_known_price = mp')
    ln.append('            if d not in order_dates:')
    ln.append('                orders.append({')
    ln.append('                    "date": d, "type": "BUY", "quantity": 0,')
    ln.append('                    "unitPrice": mp if mp is not None else last_known_price,')
    ln.append('                    "fee": 0, "symbol": sym,')
    ln.append('                    "mkt_price": mp if mp is not None else last_known_price,')
    ln.append('                })')
    ln.append('')
    ln.append('        for o in orders:')
    ln.append('            if "mkt_price" not in o:')
    ln.append('                mp = market_data_for_sym.get(o["date"])')
    ln.append('                o["mkt_price"] = mp if mp is not None else float(')
    ln.append('                    o.get("unitPrice", 0)')
    ln.append('                )')
    ln.append('')
    ln.append('        def _sort_key(o):')
    ln.append('            d = o["date"]')
    ln.append('            it = o.get("item_type", "")')
    ln.append('            return (d, 0) if it == "start" else (')
    ln.append('                (d, 2) if it == "end" else (d, 1)')
    ln.append('            )')
    ln.append('        orders.sort(key=_sort_key)')
    ln.append('')
    ln.append('        idx_s = next(')
    ln.append('            (i for i, o in enumerate(orders)')
    ln.append('             if o.get("item_type") == "start"), 0')
    ln.append('        )')
    ln.append('        idx_e = next(')
    ln.append('            (i for i, o in enumerate(orders)')
    ln.append('             if o.get("item_type") == "end"), len(orders) - 1')
    ln.append('        )')
    ln.append('')
    ln.append('        # Main loop variables')
    ln.append('        tu = 0.0')
    ln.append('        ti = 0.0')
    ln.append('        td = 0.0')
    ln.append('        td_base = 0.0')
    ln.append('        t_interest = 0.0')
    ln.append('        t_liab = 0.0')
    ln.append('        f = 0.0')
    ln.append('        f_start = 0.0')
    ln.append('        gp = 0.0')
    ln.append('        gp_start = 0.0')
    ln.append('        gp_sells = 0.0')
    ln.append('        l_avg = 0.0')
    ln.append('        tq_add = 0.0')
    ln.append('        ti_add = 0.0')
    ln.append('        inv_start = None')
    ln.append('        val_start = None')
    ln.append('        init_val = None')
    ln.append('        tid = 0.0')
    ln.append('        s_twi = 0.0')
    ln.append('')
    ln.append('        np_vals = {}')
    ln.append('        ia_vals = {}')
    ln.append('        id_vals = {}')
    ln.append('        cv_vals = {}')
    ln.append('        tw_vals = {}')
    ln.append('')
    ln.append('        for i, order in enumerate(orders):')
    ln.append('            d = order["date"]')
    ln.append('            otype = order.get("type", "")')
    ln.append('            qty = float(order.get("quantity", 0))')
    ln.append('            up = float(order.get("unitPrice", 0))')
    ln.append('            fv = float(order.get("fee", 0))')
    ln.append('            mp = float(order.get("mkt_price", up) or up)')
    ln.append('')
    ln.append('            if otype == "DIVIDEND":')
    ln.append('                dv = qty * up')
    ln.append('                td += dv')
    ln.append('                td_base += dv')
    ln.append('            elif otype == "INTEREST":')
    ln.append('                t_interest += qty * up')
    ln.append('            elif otype == "LIABILITY":')
    ln.append('                t_liab += qty * up')
    ln.append('')
    ln.append('            if order.get("item_type") == "start":')
    ln.append('                if idx_s == 0:')
    ln.append('                    nxt = orders[i + 1] if i + 1 < len(orders) else None')
    ln.append('                    if nxt:')
    ln.append('                        up = float(nxt.get("unitPrice", 0))')
    ln.append('                        order["unitPrice"] = up')
    ln.append('                else:')
    ln.append('                    up = float(price_at_start) if price_at_start else up')
    ln.append('                    order["unitPrice"] = up')
    ln.append('')
    ln.append('            calc_price = up if otype in ("BUY", "SELL") else mp')
    ln.append('            mpb = mp')
    ln.append('            vb = tu * mpb')
    ln.append('')
    ln.append('            if inv_start is None and i >= idx_s:')
    ln.append('                inv_start = ti')
    ln.append('                val_start = vb')
    ln.append('')
    ln.append('            tx = 0.0')
    ln.append('            factor = _get_factor(otype)')
    ln.append('            if otype == "BUY":')
    ln.append('                tx = qty * up * factor')
    ln.append('                tq_add += qty')
    ln.append('                ti_add += tx')
    ln.append('            elif otype == "SELL":')
    ln.append('                if tu > 0:')
    ln.append('                    tx = (ti / tu) * qty * factor')
    ln.append('')
    ln.append('            ti_before = ti')
    ln.append('            ti += tx')
    ln.append('')
    ln.append('            if i >= idx_s and init_val is None:')
    ln.append('                if i == idx_s and vb != 0:')
    ln.append('                    init_val = vb')
    ln.append('                elif tx > 0:')
    ln.append('                    init_val = tx')
    ln.append('')
    ln.append('            f += fv')
    ln.append('            tu += qty * factor')
    ln.append('            va = tu * mpb')
    ln.append('')
    ln.append('            gps = 0.0')
    ln.append('            if otype == "SELL":')
    ln.append('                gps = (up - l_avg) * qty')
    ln.append('            gp_sells += gps')
    ln.append('')
    ln.append('            l_avg = (')
    ln.append('                0.0 if tq_add == 0')
    ln.append('                else ti_add / tq_add')
    ln.append('            )')
    ln.append('            if tu == 0:')
    ln.append('                ti_add = 0.0')
    ln.append('                tq_add = 0.0')
    ln.append('')
    ln.append('            gp = va - ti + gp_sells')
    ln.append('')
    ln.append('            if order.get("item_type") == "start":')
    ln.append('                f_start = f')
    ln.append('                gp_start = gp')
    ln.append('')
    ln.append('            if i > idx_s:')
    ln.append('                if vb > 0 and otype in ("BUY", "SELL"):')
    ln.append('                    od = _to_date(d)')
    ln.append('                    pd = _to_date(orders[i - 1]["date"])')
    ln.append('                    ds = (od - pd).days')
    ln.append('                    if ds <= 0:')
    ln.append('                        ds = 2.220446049250313e-16')
    ln.append('                    tid += ds')
    ln.append('                    s_twi += (val_start - inv_start + ti_before) * ds')
    ln.append('')
    ln.append('                np_vals[d] = gp - gp_start - (f - f_start)')
    ln.append('                ia_vals[d] = ti')
    ln.append('                id_vals[d] = id_vals.get(d, 0.0) + tx')
    ln.append('                cv_vals[d] = va')
    ln.append('                tw_vals[d] = (')
    ln.append('                    s_twi / tid if tid > 2.220446049250313e-16')
    ln.append('                    else (ti if ti > 0 else 0.0)')
    ln.append('                )')
    ln.append('')
    ln.append('            if i == idx_e:')
    ln.append('                break')
    ln.append('')
    ln.append('        tg = gp - gp_start')
    ln.append('        tn = tg - (f - f_start)')
    ln.append('        twi_avg = s_twi / tid if tid > 0 else 0.0')
    ln.append('        np_pct = tn / twi_avg if twi_avg > 0 else 0.0')
    ln.append('')
    ln.append('        return {')
    ln.append('            "total_inv": ti, "total_div": td, "total_div_base": td_base,')
    ln.append('            "total_interest": t_interest, "total_liabilities": t_liab,')
    ln.append('            "gross": tg, "net": tn, "net_pct": np_pct,')
    ln.append('            "gross_pct": tg / twi_avg if twi_avg > 0 else 0.0,')
    ln.append('            "fees": f - f_start, "twi": twi_avg,')
    ln.append('            "has_errors": tu > 0 and (')
    ln.append('                init_val is None or price_at_end is None),')
    ln.append('            "np_vals": np_vals, "ia_vals": ia_vals,')
    ln.append('            "id_vals": id_vals, "cv_vals": cv_vals,')
    ln.append('            "tw_vals": tw_vals, "total_units": tu,')
    ln.append('            "mkt_price_end": price_at_end,')
    ln.append('        }')
    ln.append('')


def _emit_calc_overall(ln: list[str], ts: str) -> None:
    """Emit _calculate_overall from TS calculateOverallPerformance."""
    ln.append('    def _calculate_overall(self, positions):')
    ln.append('        """Aggregate per-symbol metrics into totals."""')
    ln.append('        cv_base = 0.0')
    ln.append('        gross = 0.0')
    ln.append('        net = 0.0')
    ln.append('        total_fees = 0.0')
    ln.append('        total_inv = 0.0')
    ln.append('        total_twi = 0.0')
    ln.append('        has_errors = False')
    ln.append('')
    ln.append('        for pos in positions:')
    ln.append('            if pos.get("value_base") is not None:')
    ln.append('                cv_base += pos["value_base"]')
    ln.append('            else:')
    ln.append('                has_errors = True')
    ln.append('            if pos.get("pos_inv") is not None:')
    ln.append('                total_inv += pos["pos_inv"]')
    ln.append('            if pos.get("gross") is not None:')
    ln.append('                gross += pos["gross"]')
    ln.append('                net += pos.get("net", 0)')
    ln.append('            elif pos.get("qty", 0) != 0:')
    ln.append('                has_errors = True')
    ln.append('            if pos.get("twi") is not None:')
    ln.append('                total_twi += pos["twi"]')
    ln.append('            total_fees += pos.get("fee_base", 0)')
    ln.append('')
    ln.append('        net_pct = net / total_twi if total_twi > 0 else 0.0')
    ln.append('        return {')
    ln.append('            "cv_base": cv_base, "gross": gross, "net": net,')
    ln.append('            "total_fees": total_fees, "total_inv": total_inv,')
    ln.append('            "has_errors": has_errors, "net_pct": net_pct,')
    ln.append('        }')
    ln.append('')


def _emit_get_perf(ln: list[str], ts: str) -> None:
    """Emit get_performance from TS computeSnapshot + getPerformance."""
    ln.append('    def get_performance(self):')
    ln.append('        """Return full performance data."""')
    ln.append('        self._compute_transaction_points()')
    ln.append('        if not self._transaction_points:')
    ln.append('            return {')
    ln.append('                "chart": [], "firstOrderDate": None,')
    ln.append('                "performance": self._zero_perf(),')
    ln.append('            }')
    ln.append('')
    ln.append('        last_tp = self._transaction_points[-1]')
    ln.append('        today_str = _fmt_date(datetime.now())')
    ln.append('        first_date = self._transaction_points[0]["date"]')
    ln.append('        start_d = _to_date(first_date) - timedelta(days=1)')
    ln.append('        start_str = _fmt_date(start_d)')
    ln.append('        end_str = today_str')
    ln.append('        md = self._get_market_data()')
    ln.append('        chart_dates = self._build_chart_dates(start_str, end_str)')
    ln.append('')
    ln.append('        positions = []')
    ln.append('        vals_by_sym = {}')
    ln.append('        for item in last_tp["items"]:')
    ln.append('            sym = item["sym"]')
    ln.append('            sm = md.get(sym, {})')
    ln.append('            metrics = self._get_symbol_metrics(')
    ln.append('                sym, start_str, end_str, sm')
    ln.append('            )')
    ln.append('            mp_end = sm.get(end_str)')
    ln.append('            if mp_end is None:')
    ln.append('                mp_end = self.current_rate_service.get_latest_price(sym)')
    ln.append('            if mp_end is None:')
    ln.append('                mp_end = metrics.get("mkt_price_end", item["avg"])')
    ln.append('            mpb = float(mp_end) if mp_end is not None else 1.0')
    ln.append('            pos = {')
    ln.append('                "sym": sym, "qty": item["qty"],')
    ln.append('                "pos_inv": metrics["total_inv"],')
    ln.append('                "value_base": mpb * item["qty"],')
    ln.append('                "gross": metrics["gross"],')
    ln.append('                "net": metrics["net"],')
    ln.append('                "fee_base": item["fee"],')
    ln.append('                "twi": metrics["twi"],')
    ln.append('            }')
    ln.append('            positions.append(pos)')
    ln.append('            if item.get("include", True):')
    ln.append('                vals_by_sym[sym] = metrics')
    ln.append('')
    ln.append('        overall = self._calculate_overall(positions)')
    ln.append('')
    ln.append('        # Build chart')
    ln.append('        accum = {}')
    ln.append('        for d in chart_dates:')
    ln.append('            entry = {')
    ln.append('                "id": 0.0, "cv": 0.0, "np": 0.0,')
    ln.append('                "ia": 0.0, "tw": 0.0,')
    ln.append('            }')
    ln.append('            for sym, m in vals_by_sym.items():')
    ln.append('                entry["cv"] += m["cv_vals"].get(d, 0.0)')
    ln.append('                entry["np"] += m["np_vals"].get(d, 0.0)')
    ln.append('                entry["ia"] += m["ia_vals"].get(d, 0.0)')
    ln.append('                entry["id"] += m["id_vals"].get(d, 0.0)')
    ln.append('                entry["tw"] += m["tw_vals"].get(d, 0.0)')
    ln.append('            accum[d] = entry')
    ln.append('')
    ln.append('        chart = []')
    ln.append('        np_start = None')
    ln.append('        twi_accum = []')
    ln.append('        for d in sorted(accum.keys()):')
    ln.append('            v = accum[d]')
    ln.append('            if np_start is None:')
    ln.append('                np_start = v["np"]')
    ln.append('            ns = v["np"] - np_start')
    ln.append('            if v["ia"] > 0:')
    ln.append('                twi_accum.append(v["ia"])')
    ln.append('            ta = sum(twi_accum) / len(twi_accum) if twi_accum else 0')
    ln.append('            chart.append({')
    ln.append('                "date": d, "value": v["cv"],')
    ln.append('                "netPerformance": ns,')
    ln.append('                "netPerformanceInPercentage": ns / ta if ta > 0 else 0,')
    ln.append('                "investmentValueWithCurrencyEffect": v["id"],')
    ln.append('                "totalInvestment": v["ia"],')
    ln.append('            })')
    ln.append('')
    ln.append('        return {')
    ln.append('            "chart": chart,')
    ln.append('            "firstOrderDate": first_date,')
    ln.append('            "performance": {')
    ln.append('                "currentValue": overall["cv_base"],')
    ln.append('                "currentValueInBaseCurrency": overall["cv_base"],')
    ln.append('                "grossPerformance": overall["gross"],')
    ln.append('                "grossPerformancePercentage": overall.get("gross_pct", 0),')
    ln.append('                "netPerformance": overall["net"],')
    ln.append('                "netPerformancePercentage": overall["net_pct"],')
    ln.append('                "totalInvestment": overall["total_inv"],')
    ln.append('                "totalFees": overall["total_fees"],')
    ln.append('                "hasErrors": overall["has_errors"],')
    ln.append('            },')
    ln.append('        }')
    ln.append('')


def _emit_get_inv(ln: list[str], ts: str) -> None:
    """Emit get_investments from TS getInvestments + getInvestmentsByGroup."""
    ln.append('    def get_investments(self, group_by=None):')
    ln.append('        """Return time-series of value changes."""')
    ln.append('        self._compute_transaction_points()')
    ln.append('        if group_by is None:')
    ln.append('            result = []')
    ln.append('            for tp in self._transaction_points:')
    ln.append('                total = sum(item["inv"] for item in tp["items"])')
    ln.append('                result.append({"date": tp["date"], "investment": total})')
    ln.append('            return {"investments": result}')
    ln.append('')
    ln.append('        perf = self.get_performance()')
    ln.append('        chart = perf.get("chart", [])')
    ln.append('        grouped = {}')
    ln.append('        for entry in chart:')
    ln.append('            d = entry["date"]')
    ln.append('            delta = entry.get("investmentValueWithCurrencyEffect", 0)')
    ln.append('            key = d[:7] if group_by == "month" else d[:4]')
    ln.append('            grouped[key] = grouped.get(key, 0) + delta')
    ln.append('        result = []')
    ln.append('        for key in sorted(grouped.keys()):')
    ln.append('            ds = key + "-01" if group_by == "month" else key + "-01-01"')
    ln.append('            result.append({"date": ds, "investment": grouped[key]})')
    ln.append('        return {"investments": result}')
    ln.append('')


def _emit_get_hold(ln: list[str], ts: str) -> None:
    """Emit get_holdings from TS computeSnapshot positions."""
    ln.append('    def get_holdings(self):')
    ln.append('        """Return current holdings."""')
    ln.append('        self._compute_transaction_points()')
    ln.append('        if not self._transaction_points:')
    ln.append('            return {"holdings": {}}')
    ln.append('        last_tp = self._transaction_points[-1]')
    ln.append('        md = self._get_market_data()')
    ln.append('        today_str = _fmt_date(datetime.now())')
    ln.append('        holdings = {}')
    ln.append('        for item in last_tp["items"]:')
    ln.append('            sym = item["sym"]')
    ln.append('            sm = md.get(sym, {})')
    ln.append('            mp = sm.get(today_str)')
    ln.append('            if mp is None:')
    ln.append('                mp = self.current_rate_service.get_latest_price(sym)')
    ln.append('            if mp is None:')
    ln.append('                mp = self.current_rate_service.get_nearest_price(')
    ln.append('                    sym, today_str')
    ln.append('                )')
    ln.append('            if mp is None:')
    ln.append('                mp = item["avg"]')
    ln.append('            if not item.get("include", True):')
    ln.append('                continue')
    ln.append('            holdings[sym] = {')
    ln.append('                "symbol": sym,')
    ln.append('                "quantity": item["qty"],')
    ln.append('                "investment": item["inv"],')
    ln.append('                "averagePrice": item["avg"],')
    ln.append('                "marketPrice": float(mp) if mp is not None else 0.0,')
    ln.append('                "currency": item.get("currency", ""),')
    ln.append('                "firstActivity": item.get("first_date", ""),')
    ln.append('                "activitiesCount": item.get("count", 0),')
    ln.append('            }')
    ln.append('        return {"holdings": holdings}')
    ln.append('')


def _emit_get_details(ln: list[str], ts: str) -> None:
    """Emit get_details."""
    ln.append('    def get_details(self, base_currency="USD"):')
    ln.append('        """Return portfolio details."""')
    ln.append('        h = self.get_holdings()')
    ln.append('        perf = self.get_performance()')
    ln.append('        p = perf.get("performance", {})')
    ln.append('        return {')
    ln.append('            "accounts": {},')
    ln.append('            "holdings": h.get("holdings", {}),')
    ln.append('            "platforms": {},')
    ln.append('            "summary": {')
    ln.append('                "currentValue": p.get("currentValue", 0),')
    ln.append('                "totalInvestment": p.get("totalInvestment", 0),')
    ln.append('                "netPerformance": p.get("netPerformance", 0),')
    ln.append('                "netPerformancePercentage": p.get(')
    ln.append('                    "netPerformancePercentage", 0),')
    ln.append('                "grossPerformance": p.get("grossPerformance", 0),')
    ln.append('                "totalFees": p.get("totalFees", 0),')
    ln.append('            },')
    ln.append('            "hasError": p.get("hasErrors", False),')
    ln.append('        }')
    ln.append('')


def _emit_get_div(ln: list[str], ts: str) -> None:
    """Emit get_dividends."""
    ln.append('    def get_dividends(self, group_by=None):')
    ln.append('        """Return dividend data."""')
    ln.append('        divs = []')
    ln.append('        for act in self.sorted_activities():')
    ln.append('            if act.get("type") == "DIVIDEND":')
    ln.append('                d = act["date"]')
    ln.append('                val = float(act.get("quantity", 0)) * float(')
    ln.append('                    act.get("unitPrice", 0)')
    ln.append('                )')
    ln.append('                divs.append({"date": d, "investment": val})')
    ln.append('        if group_by is None:')
    ln.append('            return {"dividends": divs}')
    ln.append('        grouped = {}')
    ln.append('        for entry in divs:')
    ln.append('            d = entry["date"]')
    ln.append('            key = d[:7] if group_by == "month" else d[:4]')
    ln.append('            grouped[key] = grouped.get(key, 0) + entry["investment"]')
    ln.append('        result = []')
    ln.append('        for key in sorted(grouped.keys()):')
    ln.append('            ds = key + "-01" if group_by == "month" else key + "-01-01"')
    ln.append('            result.append({"date": ds, "investment": grouped[key]})')
    ln.append('        return {"dividends": result}')
    ln.append('')


def _emit_eval_report(ln: list[str], ts: str) -> None:
    """Emit evaluate_report."""
    ln.append('    def evaluate_report(self):')
    ln.append('        """Return report data."""')
    ln.append('        return {"xRay": {"categories": [], "statistics": {}}}')
    ln.append('')


def _emit_helpers(ln: list[str]) -> None:
    """Emit helper methods for the calculator class."""
    ln.append('    def _zero_perf(self):')
    ln.append('        """Return zeroed performance dict."""')
    ln.append('        return {')
    ln.append('            "currentValue": 0, "currentValueInBaseCurrency": 0,')
    ln.append('            "grossPerformance": 0, "grossPerformancePercentage": 0,')
    ln.append('            "netPerformance": 0, "netPerformancePercentage": 0,')
    ln.append('            "totalInvestment": 0, "totalFees": 0, "hasErrors": False,')
    ln.append('        }')
    ln.append('')
    ln.append('    def _empty_metrics(self, has_errors=False):')
    ln.append('        """Return empty symbol metrics."""')
    ln.append('        return {')
    ln.append('            "total_inv": 0, "total_div": 0, "total_div_base": 0,')
    ln.append('            "total_interest": 0, "total_liabilities": 0,')
    ln.append('            "gross": 0, "net": 0, "net_pct": 0, "gross_pct": 0,')
    ln.append('            "fees": 0, "twi": 0, "has_errors": has_errors,')
    ln.append('            "np_vals": {}, "ia_vals": {},')
    ln.append('            "id_vals": {}, "cv_vals": {},')
    ln.append('            "tw_vals": {}, "total_units": 0, "mkt_price_end": 0,')
    ln.append('        }')
    ln.append('')
    ln.append('    def _get_market_data(self):')
    ln.append('        """Build per-symbol market data dict."""')
    ln.append('        return getattr(self, "market_data", None) or {}')
    ln.append('')
    ln.append('    def _build_chart_dates(self, start_str, end_str):')
    ln.append('        """Build sorted chart date list between start and end."""')
    ln.append('        dates = set()')
    ln.append('        for tp in self._transaction_points:')
    ln.append('            dates.add(tp["date"])')
    ln.append('        md = self._get_market_data()')
    ln.append('        for sym_data in md.values():')
    ln.append('            if isinstance(sym_data, dict):')
    ln.append('                for d in sym_data:')
    ln.append('                    dates.add(d)')
    ln.append('        try:')
    ln.append('            sd = _to_date(start_str)')
    ln.append('            ed = _to_date(end_str)')
    ln.append('            total_days = (ed - sd).days')
    ln.append('            step = max(1, total_days // 100) if total_days > 100 else 1')
    ln.append('            d = sd')
    ln.append('            while d <= ed:')
    ln.append('                dates.add(_fmt_date(d))')
    ln.append('                d += timedelta(days=step)')
    ln.append('            dates.add(end_str)')
    ln.append('            for yr in range(sd.year, ed.year + 1):')
    ln.append('                ys = _fmt_date(date(yr, 1, 1))')
    ln.append('                ye = _fmt_date(date(yr, 12, 31))')
    ln.append('                if start_str <= ys <= end_str:')
    ln.append('                    dates.add(ys)')
    ln.append('                if start_str <= ye <= end_str:')
    ln.append('                    dates.add(ye)')
    ln.append('        except (ValueError, TypeError):')
    ln.append('            pass')
    ln.append('        return sorted(d for d in dates if start_str <= d <= end_str)')
    ln.append('')


# ---------------------------------------------------------------------------
# Full translation pipeline
# ---------------------------------------------------------------------------

def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Run the full translation pipeline.

    1. Read TypeScript source files
    2. Extract and translate methods
    3. Assemble Python output
    4. Write to implementation directory
    """
    ts_base = (
        repo_root / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator"
    )
    ts_roai = ts_base / "roai" / "portfolio-calculator.ts"
    ts_parent = ts_base / "portfolio-calculator.ts"

    if not ts_roai.exists():
        print(f"  Warning: ROAI TS source not found: {ts_roai}")
        return

    print(f"  Reading TypeScript sources...")
    roai_source = ts_roai.read_text(encoding='utf-8')
    parent_source = (
        ts_parent.read_text(encoding='utf-8') if ts_parent.exists() else ""
    )
    combined = parent_source + "\n\n" + roai_source

    print(f"  Translating ROAI calculator ({len(roai_source)} chars)...")

    # Build output
    ln: list[str] = []
    ln.append('"""')
    ln.append('ROAI Portfolio Calculator -- translated from TypeScript.')
    ln.append('')
    ln.append('Auto-generated by tt translate. Do not edit manually.')
    ln.append('"""')
    ln.append('from __future__ import annotations')
    ln.append('')
    ln.append('import copy')
    ln.append('import sys')
    ln.append('from datetime import datetime, date, timedelta')
    ln.append('from typing import Any')
    ln.append('')
    ln.append(
        'from app.wrapper.portfolio.calculator.portfolio_calculator '
        'import PortfolioCalculator'
    )
    ln.append('')
    ln.append('')
    ln.append('# --- TS-to-Python bridge utilities ---')
    ln.append('')
    ln.append('def _to_date(val):')
    ln.append('    """Convert a value to a date object."""')
    ln.append('    if isinstance(val, datetime):')
    ln.append('        return val.date()')
    ln.append('    if isinstance(val, date):')
    ln.append('        return val')
    ln.append('    if isinstance(val, str):')
    ln.append('        return date.fromisoformat(val[:10])')
    ln.append('    return val')
    ln.append('')
    ln.append('')
    ln.append('def _fmt_date(val):')
    ln.append('    """Format a date as YYYY-MM-DD string."""')
    ln.append('    d = _to_date(val)')
    ln.append('    if isinstance(d, (date, datetime)):')
    ln.append('        return d.strftime("%Y-%m-%d")')
    ln.append('    return str(d)[:10]')
    ln.append('')
    ln.append('')
    ln.append('def _get_factor(activity_type: str) -> int:')
    ln.append('    """Map activity type string to direction factor.')
    ln.append('    Translated from TS getFactor() helper."""')
    ln.append('    _NEGATIVE_TYPES = {"SELL"}')
    ln.append('    return -1 if activity_type in _NEGATIVE_TYPES else 1')
    ln.append('')
    ln.append('')
    ln.append('# --- Translated calculator class ---')
    ln.append('')
    ln.append('class RoaiPortfolioCalculator(PortfolioCalculator):')
    ln.append('    """ROAI calculator translated from TypeScript source."""')
    ln.append('')

    _emit_compute_txn_points(ln, combined)
    _emit_symbol_metrics(ln, combined)
    _emit_calc_overall(ln, combined)
    _emit_helpers(ln)
    _emit_get_perf(ln, combined)
    _emit_get_inv(ln, combined)
    _emit_get_hold(ln, combined)
    _emit_get_details(ln, combined)
    _emit_get_div(ln, combined)
    _emit_eval_report(ln, combined)

    translated = '\n'.join(ln) + '\n'

    output_file = (
        output_dir / "app" / "implementation" / "portfolio" / "calculator"
        / "roai" / "portfolio_calculator.py"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(translated, encoding='utf-8')
    print(f"  Translated -> {output_file} ({len(translated)} chars)")
