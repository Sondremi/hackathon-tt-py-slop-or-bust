"""
Support utilities for the translated portfolio calculator.

Provides:
- Big: Decimal wrapper mimicking Big.js API for seamless TS→Python translation
- Date helpers: Python equivalents of date-fns functions
- getFactor: Activity type multiplier
- getIntervalFromDateRange: Date range to interval conversion
"""
from __future__ import annotations

import copy
import math
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any


# ---------------------------------------------------------------------------
# Big.js compatible decimal wrapper
# ---------------------------------------------------------------------------

class Big:
    """Decimal wrapper that mirrors the Big.js API used in TypeScript."""

    __slots__ = ("_v",)

    def __init__(self, value: Any = 0):
        if isinstance(value, Big):
            self._v = value._v
        elif isinstance(value, Decimal):
            self._v = value
        elif isinstance(value, float):
            self._v = Decimal(str(value))
        elif isinstance(value, int):
            self._v = Decimal(value)
        elif isinstance(value, str):
            try:
                self._v = Decimal(value)
            except InvalidOperation:
                self._v = Decimal(0)
        elif value is None:
            self._v = Decimal(0)
        else:
            try:
                self._v = Decimal(str(value))
            except (InvalidOperation, TypeError):
                self._v = Decimal(0)

    def _coerce(self, other: Any) -> Decimal:
        if isinstance(other, Big):
            return other._v
        return Big(other)._v

    # Arithmetic (Big.js API)
    def plus(self, other: Any) -> Big:
        return Big(self._v + self._coerce(other))

    def add(self, other: Any) -> Big:
        return self.plus(other)

    def minus(self, other: Any) -> Big:
        return Big(self._v - self._coerce(other))

    def mul(self, other: Any) -> Big:
        return Big(self._v * self._coerce(other))

    def div(self, other: Any) -> Big:
        divisor = self._coerce(other)
        if divisor == 0:
            return Big(0)
        return Big(self._v / divisor)

    def abs(self) -> Big:
        return Big(abs(self._v))

    def neg(self) -> Big:
        return Big(-self._v)

    # Comparison (Big.js API)
    def eq(self, other: Any) -> bool:
        return self._v == self._coerce(other)

    def gt(self, other: Any) -> bool:
        return self._v > self._coerce(other)

    def gte(self, other: Any) -> bool:
        return self._v >= self._coerce(other)

    def lt(self, other: Any) -> bool:
        return self._v < self._coerce(other)

    def lte(self, other: Any) -> bool:
        return self._v <= self._coerce(other)

    # Conversion
    def toNumber(self) -> float:
        return float(self._v)

    def toFixed(self, dp: int = 0) -> str:
        if dp == 0:
            return str(int(self._v.to_integral_value(rounding=ROUND_HALF_UP)))
        quant = Decimal(10) ** -dp
        return str(self._v.quantize(quant, rounding=ROUND_HALF_UP))

    # Python operator overloads
    def __add__(self, other: Any) -> Big:
        return self.plus(other)

    def __radd__(self, other: Any) -> Big:
        return Big(other).plus(self)

    def __sub__(self, other: Any) -> Big:
        return self.minus(other)

    def __rsub__(self, other: Any) -> Big:
        return Big(other).minus(self)

    def __mul__(self, other: Any) -> Big:
        return self.mul(other)

    def __rmul__(self, other: Any) -> Big:
        return Big(other).mul(self)

    def __truediv__(self, other: Any) -> Big:
        return self.div(other)

    def __neg__(self) -> Big:
        return self.neg()

    def __abs__(self) -> Big:
        return self.abs()

    def __eq__(self, other: Any) -> bool:
        if other is None:
            return False
        try:
            return self._v == self._coerce(other)
        except (TypeError, InvalidOperation):
            return NotImplemented

    def __ne__(self, other: Any) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __gt__(self, other: Any) -> bool:
        return self._v > self._coerce(other)

    def __ge__(self, other: Any) -> bool:
        return self._v >= self._coerce(other)

    def __lt__(self, other: Any) -> bool:
        return self._v < self._coerce(other)

    def __le__(self, other: Any) -> bool:
        return self._v <= self._coerce(other)

    def __float__(self) -> float:
        return float(self._v)

    def __int__(self) -> int:
        return int(self._v)

    def __bool__(self) -> bool:
        return self._v != 0

    def __repr__(self) -> str:
        return f"Big({self._v})"

    def __str__(self) -> str:
        return str(self._v)

    def __hash__(self) -> int:
        return hash(self._v)


# ---------------------------------------------------------------------------
# Date utilities (mirrors date-fns)
# ---------------------------------------------------------------------------

DATE_FORMAT = "%Y-%m-%d"


def parse_date(value: Any) -> datetime:
    """Parse a date string or return datetime objects as-is."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if not isinstance(value, str):
        return datetime.now()
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y%m%d"]:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").replace("+00:00", ""))
    except (ValueError, AttributeError):
        return datetime.now()


def format_date(d: Any, fmt: str | None = None) -> str:
    """Format a date to string. Accepts date-fns format patterns."""
    if isinstance(d, str):
        d = parse_date(d)
    if fmt is None:
        fmt = DATE_FORMAT
    # Convert common date-fns patterns to Python strftime
    py_fmt = fmt.replace("yyyy", "%Y").replace("MM", "%m").replace("dd", "%d")
    return d.strftime(py_fmt)


def reset_hours(d: datetime) -> datetime:
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def start_of_day(d: datetime) -> datetime:
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(d: datetime) -> datetime:
    return d.replace(hour=23, minute=59, second=59, microsecond=999999)


def start_of_year(d: datetime) -> datetime:
    return datetime(d.year, 1, 1)


def end_of_year(d: datetime) -> datetime:
    return datetime(d.year, 12, 31, 23, 59, 59, 999999)


def sub_days(d: datetime, n: int) -> datetime:
    return d - timedelta(days=n)


def add_milliseconds(d: datetime, ms: int) -> datetime:
    return d + timedelta(milliseconds=ms)


def difference_in_days(a: Any, b: Any) -> int:
    if isinstance(a, str):
        a = parse_date(a)
    if isinstance(b, str):
        b = parse_date(b)
    return (a - b).days


def is_before(a: Any, b: Any) -> bool:
    if isinstance(a, str):
        a = parse_date(a)
    if isinstance(b, str):
        b = parse_date(b)
    return a < b


def is_after(a: Any, b: Any) -> bool:
    if isinstance(a, str):
        a = parse_date(a)
    if isinstance(b, str):
        b = parse_date(b)
    return a > b


def is_within_interval(d: datetime, interval: dict) -> bool:
    start = interval.get("start", interval.get("startDate"))
    end = interval.get("end", interval.get("endDate"))
    if isinstance(start, str):
        start = parse_date(start)
    if isinstance(end, str):
        end = parse_date(end)
    return start <= d <= end


def is_this_year(d: datetime) -> bool:
    return d.year == datetime.now().year


def each_day_of_interval(start: Any, end: Any, step: int = 1) -> list[datetime]:
    """Return list of dates in interval with given step."""
    if isinstance(start, dict):
        end = start.get("end", start.get("endDate"))
        start = start.get("start", start.get("startDate"))
    if isinstance(start, str):
        start = parse_date(start)
    if isinstance(end, str):
        end = parse_date(end)
    result = []
    current = start_of_day(start)
    end_dt = start_of_day(end)
    while current <= end_dt:
        result.append(current)
        current += timedelta(days=step)
    return result


def each_year_of_interval(start: Any, end: Any) -> list[datetime]:
    """Return list of Jan 1 dates for each year in interval."""
    if isinstance(start, dict):
        end = start.get("end", start.get("endDate"))
        start = start.get("start", start.get("startDate"))
    if isinstance(start, str):
        start = parse_date(start)
    if isinstance(end, str):
        end = parse_date(end)
    result = []
    year = start.year
    while year <= end.year:
        result.append(datetime(year, 1, 1))
        year += 1
    return result


def min_date(*dates: datetime) -> datetime:
    valid = [d for d in dates if d is not None]
    return min(valid) if valid else datetime.now()


# ---------------------------------------------------------------------------
# Activity helpers
# ---------------------------------------------------------------------------

_FACTOR_MAP = {"BUY": 1, "SELL": -1, "DIVIDEND": 0, "INTEREST": 0,
               "ITEM": 1, "LIABILITY": 1, "FEE": 0}

INVESTMENT_ACTIVITY_TYPES = ["BUY", "SELL"]


def get_factor(activity_type: str) -> int:
    """Return the quantity multiplier for an activity type."""
    return _FACTOR_MAP.get(activity_type, 0)


# ---------------------------------------------------------------------------
# Date range helpers
# ---------------------------------------------------------------------------

def get_interval_from_date_range(
    date_range: str, reference_date: datetime | None = None
) -> dict:
    """Convert a date range string ('1d','1y','5y','max','mtd','wtd','ytd','YYYY') to interval."""
    now = datetime.now()
    if reference_date is None:
        reference_date = now

    if date_range == "1d":
        return {"startDate": start_of_day(sub_days(now, 1)), "endDate": end_of_day(now)}
    elif date_range == "wtd":
        start = now - timedelta(days=now.weekday())
        return {"startDate": start_of_day(start), "endDate": end_of_day(now)}
    elif date_range == "mtd":
        return {"startDate": start_of_day(datetime(now.year, now.month, 1)), "endDate": end_of_day(now)}
    elif date_range == "ytd":
        return {"startDate": start_of_day(datetime(now.year, 1, 1)), "endDate": end_of_day(now)}
    elif date_range == "1y":
        return {"startDate": start_of_day(sub_days(now, 365)), "endDate": end_of_day(now)}
    elif date_range == "5y":
        return {"startDate": start_of_day(sub_days(now, 5 * 365)), "endDate": end_of_day(now)}
    elif date_range == "max":
        return {"startDate": start_of_day(reference_date), "endDate": end_of_day(now)}
    elif len(date_range) == 4 and date_range.isdigit():
        year = int(date_range)
        return {
            "startDate": datetime(year, 1, 1),
            "endDate": datetime(year, 12, 31, 23, 59, 59, 999999),
        }
    else:
        return {"startDate": start_of_day(reference_date), "endDate": end_of_day(now)}


def clone_deep(obj: Any) -> Any:
    """Deep copy an object (equivalent to lodash cloneDeep)."""
    return copy.deepcopy(obj)


def sort_by(items: list, key_fn) -> list:
    """Sort a list by a key function (equivalent to lodash sortBy)."""
    return sorted(items, key=key_fn)


EPSILON = sys.float_info.epsilon
