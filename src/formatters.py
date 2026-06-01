from __future__ import annotations

import pandas as pd


def _is_empty(value) -> bool:
    return value is None or pd.isna(value)


def format_krw(value) -> str:
    if _is_empty(value):
        return "-"
    return f"{value:,.0f}원"


def format_krw_eok(value) -> str:
    if _is_empty(value):
        return "-"
    return f"{value / 100_000_000:,.1f}억원"


def format_signed_krw_eok(value) -> str:
    if _is_empty(value):
        return "-"
    label = "순매수" if value >= 0 else "순매도"
    return f"{value / 100_000_000:,.1f}억원 {label}"


def format_percent(value) -> str:
    if _is_empty(value):
        return "-"
    return f"{value:+.2f}%"


def format_volume(value) -> str:
    if _is_empty(value):
        return "-"
    return f"{value:,.0f}주"


def format_grade(value) -> str:
    return str(value) if value else "-"
