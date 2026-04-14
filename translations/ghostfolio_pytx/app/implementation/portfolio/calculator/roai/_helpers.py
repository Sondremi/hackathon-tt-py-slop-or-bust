__all__ = ["_dt", "_fmt", "_now", "_deep_copy", "_fct", "_N", "_DT", "_D", "_TD"]
from datetime import datetime as _DT, date as _D, timedelta as _TD
def _dt(val):
    if isinstance(val, _DT): return val.date()
    if isinstance(val, _D): return val
    if isinstance(val, str): return _D.fromisoformat(val[:10])
    return val
def _fmt(val):
    c = _dt(val)
    if isinstance(c, _D): return c.strftime("%Y-%m-%d")
    return str(c)[:10]
def _now(): return _DT.now().date()
import copy as _cm
def _deep_copy(o): return _cm.deepcopy(o)
_N = frozenset({"SELL"})
def _fct(t): return -1 if t in _N else 1