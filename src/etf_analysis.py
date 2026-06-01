from __future__ import annotations

import pandas as pd


def _latest(df: pd.DataFrame | None, column: str):
    if df is None or df.empty or column not in df.columns:
        return pd.NA
    series = pd.to_numeric(df[column], errors="coerce").dropna()
    return series.iloc[-1] if not series.empty else pd.NA


def _pct_change(df: pd.DataFrame, column: str, days: int):
    if df.empty or column not in df.columns or len(df) <= days:
        return pd.NA
    current = pd.to_numeric(df[column], errors="coerce").iloc[-1]
    base = pd.to_numeric(df[column], errors="coerce").iloc[-days - 1]
    if pd.isna(current) or pd.isna(base) or base == 0:
        return pd.NA
    return (current / base - 1) * 100


def _sum_tail(df: pd.DataFrame | None, column: str, days: int):
    if df is None or df.empty or column not in df.columns:
        return pd.NA
    return pd.to_numeric(df[column], errors="coerce").fillna(0).tail(days).sum()


def summarize_etf(
    etf_price_df: pd.DataFrame,
    deviation_df: pd.DataFrame | None = None,
    tracking_df: pd.DataFrame | None = None,
    flow_df: pd.DataFrame | None = None,
    portfolio_df: pd.DataFrame | None = None,
) -> dict:
    price = etf_price_df.copy()
    deviation = deviation_df.copy() if deviation_df is not None else pd.DataFrame()
    tracking = tracking_df.copy() if tracking_df is not None else pd.DataFrame()
    flow = flow_df.copy() if flow_df is not None else pd.DataFrame()
    portfolio = portfolio_df.copy() if portfolio_df is not None else pd.DataFrame()

    avg_trading_value_20d = pd.to_numeric(price.get("TradingValue", pd.Series(dtype=float)), errors="coerce").tail(20).mean()
    latest_trading_value = _latest(price, "TradingValue")
    top = portfolio.sort_values("Weight", ascending=False).iloc[0] if not portfolio.empty and "Weight" in portfolio.columns else None

    return {
        "latest_close": _latest(price, "Close"),
        "latest_nav": _latest(price, "NAV"),
        "latest_deviation_rate": _latest(deviation, "DeviationRate"),
        "latest_tracking_error_rate": _latest(tracking, "TrackingErrorRate"),
        "latest_underlying_index": _latest(price, "UnderlyingIndex"),
        "latest_volume": _latest(price, "Volume"),
        "latest_trading_value": latest_trading_value,
        "avg_trading_value_20d": avg_trading_value_20d,
        "trading_value_ratio_20d": latest_trading_value / avg_trading_value_20d if avg_trading_value_20d else pd.NA,
        "return_5d": _pct_change(price, "Close", 5),
        "return_20d": _pct_change(price, "Close", 20),
        "return_60d": _pct_change(price, "Close", 60),
        "high_52w": pd.to_numeric(price["Close"], errors="coerce").tail(252).max() if "Close" in price else pd.NA,
        "low_52w": pd.to_numeric(price["Close"], errors="coerce").tail(252).min() if "Close" in price else pd.NA,
        "nav_return_20d": _pct_change(price, "NAV", 20),
        "index_return_20d": _pct_change(price, "UnderlyingIndex", 20),
        "foreign_net_value_5d": _sum_tail(flow, "ForeignNetValue", 5),
        "institution_net_value_5d": _sum_tail(flow, "InstitutionNetValue", 5),
        "smart_money_net_value_20d": _sum_tail(flow, "SmartMoneyNetValue", 20),
        "top_component_name": top["ComponentName"] if top is not None and "ComponentName" in top else "-",
        "top_component_weight": top["Weight"] if top is not None and "Weight" in top else pd.NA,
        "component_count": len(portfolio),
    }


def classify_etf_risk(
    etf_info: dict,
    price_df: pd.DataFrame,
    deviation_df: pd.DataFrame | None = None,
    tracking_df: pd.DataFrame | None = None,
) -> dict:
    summary = summarize_etf(price_df, deviation_df, tracking_df)
    avg_value = summary["avg_trading_value_20d"]
    if pd.isna(avg_value) or avg_value < 1_000_000_000:
        liquidity = "낮음"
    elif avg_value < 10_000_000_000:
        liquidity = "보통"
    else:
        liquidity = "높음"

    deviation = abs(summary["latest_deviation_rate"]) if not pd.isna(summary["latest_deviation_rate"]) else pd.NA
    if pd.isna(deviation):
        deviation_grade = "데이터 없음"
    elif deviation < 0.5:
        deviation_grade = "안정"
    elif deviation < 1.0:
        deviation_grade = "주의"
    else:
        deviation_grade = "위험"

    tracking = summary["latest_tracking_error_rate"]
    if pd.isna(tracking):
        tracking_grade = "데이터 없음"
    elif tracking < 1.0:
        tracking_grade = "안정"
    elif tracking < 3.0:
        tracking_grade = "주의"
    else:
        tracking_grade = "위험"

    flags: list[str] = []
    if etf_info.get("IsLeveraged"):
        flags.append("레버리지 ETF")
    if etf_info.get("IsInverse"):
        flags.append("인버스 ETF")
    if etf_info.get("IsSynthetic"):
        flags.append("합성 ETF")
    if etf_info.get("IsHedged"):
        flags.append("환헤지 ETF")
    if etf_info.get("Category") == "해외주식":
        flags.append("해외자산 ETF")
    if etf_info.get("Category") == "원자재":
        flags.append("원자재 ETF")
    if liquidity == "낮음":
        flags.append("거래대금 부족")
    if deviation_grade == "위험":
        flags.append("괴리율 확대")
    if tracking_grade == "위험":
        flags.append("추적오차 확대")

    return {
        "LiquidityGrade": liquidity,
        "DeviationGrade": deviation_grade,
        "TrackingGrade": tracking_grade,
        "ProductRiskFlags": flags,
    }
