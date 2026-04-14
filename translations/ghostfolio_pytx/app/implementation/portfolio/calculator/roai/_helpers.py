from datetime import datetime as _DT, date as _D, timedelta as _TD
def _dt(val):
    if isinstance(val, _DT):
        return val.date()
    if isinstance(val, _D):
        return val
    if isinstance(val, str):
        return _D.fromisoformat(val[:10])
    return val
def _fmt(val):
    converted = _dt(val)
    if isinstance(converted, _D):
        return converted.strftime("%Y-%m-%d")
    return str(converted)[:10]
def _now():
    return _DT.now().date()
import copy as _cmod
def _deep_copy(obj):
    return _cmod.deepcopy(obj)
_NEG = frozenset({"SELL"})
def _factor(act_type):
    return -1 if act_type in _NEG else 1