"""Turning engine raw outputs into APA 7 text. Numbers come only from results.json."""

from __future__ import annotations

from . import apa


def headline(plan: dict, results: dict) -> str:
    """One-line statistical summary for terminal output."""
    return HEADLINES[plan["method"]](plan, results["statistics"])


def _paired_headline(plan, s) -> str:
    return (f"t({apa.df(s['df'])}) = {apa.num(s['t'])}, p {apa.p_value(s['p'])}, "
            f"M_diff = {apa.num(s['mean_diff'])}, d_z = {apa.num(s['cohens_dz'])}")


HEADLINES = {"paired-t-test": _paired_headline}
