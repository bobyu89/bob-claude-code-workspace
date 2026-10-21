"""APA 7 number formatting. Every number shown in a report passes through here."""

from __future__ import annotations

import math


def num(x: float | None, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "NA"
    s = f"{x:.{digits}f}"
    return "0" + s[2:] if s.startswith("-0") and float(s) == 0 else s  # avoid "-0.00"


def bounded(x: float | None, digits: int = 2) -> str:
    """Statistics that cannot exceed 1 in absolute value: no leading zero (APA 7 §6.36)."""
    s = num(x, digits)
    if s.startswith("0."):
        return s[1:]
    if s.startswith("-0."):
        return "-" + s[2:]
    return s


def p_value(p: float | None) -> str:
    """Returns the operator and value, e.g. '= .003', '< .001'."""
    if p is None:
        return "= NA"
    if p < 0.001:
        return "< .001"
    if p > 0.999:
        return "> .999"
    return "= " + bounded(p, 3)


def df(x: float | None) -> str:
    if x is None:
        return "NA"
    return str(int(round(x))) if abs(x - round(x)) < 1e-9 else num(x, 2)


def pct(x: float) -> str:
    return num(100 * x, 1) + "%"


def significant(p: float | None, alpha: float) -> bool:
    return p is not None and p < alpha
