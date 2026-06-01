from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from src.config import load_project_env
from src.data_loader import load_price


def _to_yyyymmdd(value) -> str:
    return pd.to_datetime(value).strftime("%Y%m%d")


def _empty_shorting_frame(debug: dict | None = None) -> pd.DataFrame:
    columns = [
        "Date",
        "ShortVolume",
        "TotalVolume",
        "ShortVolumeRatio",
        "ShortValue",
        "TotalValue",
        "ShortValueRatio",
        "ShortBalance",
        "MarketCap",
        "ShortBalanceRatio",
        "Close",
    ]
    result = pd.DataFrame(columns=columns)
    result.attrs["debug"] = debug or {}
    return result


def _normalize_date(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy().reset_index()
    if "Date" not in result.columns:
        date_col = next((col for col in result.columns if str(col) in {"날짜", "일자"}), result.columns[0])
        result = result.rename(columns={date_col: "Date"})
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    return result.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)


def _number(series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def normalize_shorting_data(
    volume_df: pd.DataFrame | None,
    value_df: pd.DataFrame | None,
    balance_df: pd.DataFrame | None,
    price_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    volume = _normalize_date(volume_df)
    value = _normalize_date(value_df)
    balance = _normalize_date(balance_df)
    price = _normalize_date(price_df) if price_df is not None else pd.DataFrame()

    dates = []
    for frame in [volume, value, balance, price]:
        if not frame.empty and "Date" in frame.columns:
            dates.extend(frame["Date"].tolist())
    if not dates:
        return _empty_shorting_frame({"data_mode": "unavailable"})

    result = pd.DataFrame({"Date": sorted(pd.Series(dates).dropna().drop_duplicates())})
    if not volume.empty:
        volume_norm = pd.DataFrame(
            {
                "Date": volume["Date"],
                "ShortVolume": _number(volume.get("공매도")),
                "TotalVolume": _number(volume.get("매수")),
                "ShortVolumeRatio": _number(volume.get("비중")),
            }
        )
        result = result.merge(volume_norm, on="Date", how="left")
    if not value.empty:
        value_norm = pd.DataFrame(
            {
                "Date": value["Date"],
                "ShortValue": _number(value.get("공매도")),
                "TotalValue": _number(value.get("매수")),
                "ShortValueRatio": _number(value.get("비중")),
            }
        )
        result = result.merge(value_norm, on="Date", how="left")
    if not balance.empty:
        balance_norm = pd.DataFrame(
            {
                "Date": balance["Date"],
                "ShortBalance": _number(balance.get("공매도잔고")),
                "MarketCap": _number(balance.get("시가총액")),
                "ShortBalanceRatio": _number(balance.get("비중")),
            }
        )
        result = result.merge(balance_norm, on="Date", how="left")
    if not price.empty and "Close" in price.columns:
        result = result.merge(price[["Date", "Close"]], on="Date", how="left")

    for column in _empty_shorting_frame().columns:
        if column not in result.columns:
            result[column] = pd.NA
    numeric_columns = [col for col in result.columns if col != "Date"]
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result[_empty_shorting_frame().columns].sort_values("Date").reset_index(drop=True)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_shorting_data(ticker, start_date, end_date) -> pd.DataFrame:
    load_project_env()
    start = _to_yyyymmdd(start_date)
    end = _to_yyyymmdd(end_date)
    debug = {
        "ticker": ticker,
        "start_ymd": start,
        "end_ymd": end,
        "available_functions": {},
        "volume_raw_shape": None,
        "value_raw_shape": None,
        "balance_raw_shape": None,
        "exception_type": None,
        "exception_message": None,
    }
    try:
        from pykrx import stock
    except Exception as exc:
        debug["exception_type"] = type(exc).__name__
        debug["exception_message"] = f"pykrx import failed: {exc}"
        return _empty_shorting_frame(debug)

    try:
        volume_func = getattr(stock, "get_shorting_volume_by_date", None)
        value_func = getattr(stock, "get_shorting_value_by_date", None)
        balance_func = getattr(stock, "get_shorting_balance_by_date", None)
        debug["available_functions"] = {
            "get_shorting_volume_by_date": volume_func is not None,
            "get_shorting_value_by_date": value_func is not None,
            "get_shorting_balance_by_date": balance_func is not None,
        }
        volume_df = volume_func(start, end, ticker) if volume_func else pd.DataFrame()
        value_df = value_func(start, end, ticker) if value_func else pd.DataFrame()
        balance_df = balance_func(start, end, ticker) if balance_func else pd.DataFrame()
        debug["volume_raw_shape"] = volume_df.shape if volume_df is not None else None
        debug["value_raw_shape"] = value_df.shape if value_df is not None else None
        debug["balance_raw_shape"] = balance_df.shape if balance_df is not None else None
        price_df = load_price(ticker, pd.to_datetime(start_date).strftime("%Y-%m-%d"), pd.to_datetime(end_date).strftime("%Y-%m-%d"))
        result = normalize_shorting_data(volume_df, value_df, balance_df, price_df)
        result.attrs["debug"] = debug
        return result
    except Exception as exc:
        debug["exception_type"] = type(exc).__name__
        debug["exception_message"] = str(exc)
        return _empty_shorting_frame(debug)


def summarize_shorting_data(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    data = df.copy().sort_values("Date")
    latest = data.iloc[-1]
    short_volume = pd.to_numeric(data["ShortVolume"], errors="coerce")
    short_balance = pd.to_numeric(data["ShortBalance"], errors="coerce")
    close = pd.to_numeric(data["Close"], errors="coerce")

    def pct_change(series: pd.Series, periods: int) -> float:
        valid = series.dropna()
        if len(valid) <= periods:
            return float("nan")
        base = valid.iloc[-periods - 1]
        if not base:
            return float("nan")
        return (valid.iloc[-1] / base - 1) * 100

    return {
        "short_volume_ratio_1d": latest.get("ShortVolumeRatio"),
        "short_volume_ratio_5d_avg": pd.to_numeric(data["ShortVolumeRatio"], errors="coerce").tail(5).mean(),
        "short_volume_ratio_20d_avg": pd.to_numeric(data["ShortVolumeRatio"], errors="coerce").tail(20).mean(),
        "short_value_ratio_1d": latest.get("ShortValueRatio"),
        "short_value_ratio_20d_avg": pd.to_numeric(data["ShortValueRatio"], errors="coerce").tail(20).mean(),
        "short_balance_ratio": latest.get("ShortBalanceRatio"),
        "short_balance_change_rate": pct_change(short_balance, 20),
        "short_volume_change_5d": pct_change(short_volume, 5),
        "short_volume_change_20d": pct_change(short_volume, 20),
        "price_change_20d": pct_change(close, 20),
    }


def calculate_shorting_score(summary: dict | None = None) -> dict:
    summary = summary or {}
    score = 70.0
    positive_factors: list[str] = []
    negative_factors: list[str] = []

    balance_ratio = pd.to_numeric(pd.Series([summary.get("short_balance_ratio")]), errors="coerce").iloc[0]
    balance_change = pd.to_numeric(pd.Series([summary.get("short_balance_change_rate")]), errors="coerce").iloc[0]
    volume_ratio_20 = pd.to_numeric(pd.Series([summary.get("short_volume_ratio_20d_avg")]), errors="coerce").iloc[0]
    volume_change_20 = pd.to_numeric(pd.Series([summary.get("short_volume_change_20d")]), errors="coerce").iloc[0]
    price_change_20 = pd.to_numeric(pd.Series([summary.get("price_change_20d")]), errors="coerce").iloc[0]

    if pd.notna(balance_ratio) and balance_ratio > 5:
        score -= 15
        negative_factors.append("공매도 잔고비율 5% 초과")
    elif pd.notna(balance_ratio) and balance_ratio > 3:
        score -= 10
        negative_factors.append("공매도 잔고비율 3% 초과")
    if pd.notna(balance_change) and balance_change > 0:
        score -= 10
        negative_factors.append("공매도 잔고 20일 증가")
    if pd.notna(volume_ratio_20) and volume_ratio_20 > 10:
        score -= 15
        negative_factors.append("20일 평균 공매도 비중 10% 초과")
    elif pd.notna(volume_ratio_20) and volume_ratio_20 > 5:
        score -= 10
        negative_factors.append("20일 평균 공매도 비중 5% 초과")
    if pd.notna(volume_change_20) and pd.notna(price_change_20) and volume_change_20 > 0 and price_change_20 < 0:
        score -= 10
        negative_factors.append("공매도 증가와 주가 하락 동시 발생")

    if pd.notna(balance_change) and balance_change < 0:
        score += 10
        positive_factors.append("공매도 잔고 감소")
    if pd.notna(volume_change_20) and volume_change_20 < 0:
        score += 10
        positive_factors.append("공매도 비중 감소")
    if pd.notna(price_change_20) and pd.notna(volume_change_20) and price_change_20 > 0 and volume_change_20 < 0:
        score += 15
        positive_factors.append("주가 상승과 공매도 감소 동시 발생")
    if pd.notna(volume_change_20) and volume_change_20 <= -10:
        score += 10
        positive_factors.append("20일 공매도 감소율 10% 이상")

    score = max(0, min(100, score))
    if score >= 80:
        grade = "낮음"
    elif score >= 60:
        grade = "보통"
    elif score >= 40:
        grade = "주의"
    else:
        grade = "높음"
    return {"score": score, "grade": grade, "positive_factors": positive_factors, "negative_factors": negative_factors}
