from __future__ import annotations

import pandas as pd

from .data_loader import load_price
from .indicators import add_all_indicators
from .investor_flow import classify_accumulation, load_investor_trading_by_date, summarize_investor_flow


CONDITION_LABELS = {
    "rsi_low": "RSI 30 이하",
    "rsi_high": "RSI 70 이상",
    "volume_spike": "거래량 20일 평균의 2배 이상",
    "close_cross_ma20": "종가 MA20 상향 돌파",
    "ma20_cross_ma60": "MA20 MA60 상향 돌파",
    "near_52w_high": "52주 최고가 대비 3% 이내",
    "return_5d_high": "최근 5거래일 수익률 5% 이상",
    "foreign_5d_positive": "외국인 5일 누적 순매매 양수",
    "foreign_20d_positive": "외국인 20일 누적 순매매 양수",
    "institution_5d_positive": "기관 5일 누적 순매매 양수",
    "institution_20d_positive": "기관 20일 누적 순매매 양수",
    "smart_20d_positive": "외국인+기관 20일 누적 순매매 양수",
    "flow_strength_20d": "외국인+기관 20일 수급 강도 3% 이상",
    "smart_consecutive_3d": "외국인+기관 연속 순매수 3일 이상",
    "foreign_institution_both_5d": "외국인과 기관 모두 최근 5일 순매수",
    "short_ratio_low_5": "공매도 비중 5% 이하",
    "short_ratio_high_10": "공매도 비중 10% 이상",
    "short_balance_down": "공매도 잔고 감소",
    "short_balance_up": "공매도 잔고 증가",
    "short_score_80": "공매도 위험도 점수 80 이상",
    "short_score_40": "공매도 위험도 점수 40 이하",
}

FLOW_CONDITIONS = {
    "foreign_5d_positive",
    "foreign_20d_positive",
    "institution_5d_positive",
    "institution_20d_positive",
    "smart_20d_positive",
    "flow_strength_20d",
    "smart_consecutive_3d",
    "foreign_institution_both_5d",
}


def evaluate_conditions(
    df: pd.DataFrame,
    selected_conditions: list[str],
    investor_summary: dict | None = None,
) -> list[str]:
    if len(df) < 2:
        return []

    latest = df.iloc[-1]
    previous = df.iloc[-2]
    summary = investor_summary or {}
    matched: list[str] = []

    if "rsi_low" in selected_conditions and pd.notna(latest.get("RSI14")) and latest["RSI14"] <= 30:
        matched.append(CONDITION_LABELS["rsi_low"])
    if "rsi_high" in selected_conditions and pd.notna(latest.get("RSI14")) and latest["RSI14"] >= 70:
        matched.append(CONDITION_LABELS["rsi_high"])
    if (
        "volume_spike" in selected_conditions
        and pd.notna(latest.get("VOLUME_RATIO"))
        and latest["VOLUME_RATIO"] >= 2
    ):
        matched.append(CONDITION_LABELS["volume_spike"])
    if (
        "close_cross_ma20" in selected_conditions
        and pd.notna(latest.get("MA20"))
        and pd.notna(previous.get("MA20"))
        and previous["Close"] <= previous["MA20"]
        and latest["Close"] > latest["MA20"]
    ):
        matched.append(CONDITION_LABELS["close_cross_ma20"])
    if (
        "ma20_cross_ma60" in selected_conditions
        and pd.notna(latest.get("MA20"))
        and pd.notna(latest.get("MA60"))
        and pd.notna(previous.get("MA20"))
        and pd.notna(previous.get("MA60"))
        and previous["MA20"] <= previous["MA60"]
        and latest["MA20"] > latest["MA60"]
    ):
        matched.append(CONDITION_LABELS["ma20_cross_ma60"])
    if (
        "near_52w_high" in selected_conditions
        and pd.notna(latest.get("HIGH_52W"))
        and latest["HIGH_52W"] > 0
        and latest["Close"] >= latest["HIGH_52W"] * 0.97
    ):
        matched.append(CONDITION_LABELS["near_52w_high"])
    if (
        "return_5d_high" in selected_conditions
        and pd.notna(latest.get("RETURN_5D"))
        and latest["RETURN_5D"] >= 5
    ):
        matched.append(CONDITION_LABELS["return_5d_high"])

    if "foreign_5d_positive" in selected_conditions and summary.get("foreign_5d", 0) > 0:
        matched.append(CONDITION_LABELS["foreign_5d_positive"])
    if "foreign_20d_positive" in selected_conditions and summary.get("foreign_20d", 0) > 0:
        matched.append(CONDITION_LABELS["foreign_20d_positive"])
    if "institution_5d_positive" in selected_conditions and summary.get("institution_5d", 0) > 0:
        matched.append(CONDITION_LABELS["institution_5d_positive"])
    if "institution_20d_positive" in selected_conditions and summary.get("institution_20d", 0) > 0:
        matched.append(CONDITION_LABELS["institution_20d_positive"])
    if "smart_20d_positive" in selected_conditions and summary.get("smart_20d", 0) > 0:
        matched.append(CONDITION_LABELS["smart_20d_positive"])
    if "flow_strength_20d" in selected_conditions and summary.get("flow_strength_20d", 0) >= 3:
        matched.append(CONDITION_LABELS["flow_strength_20d"])
    if "smart_consecutive_3d" in selected_conditions and summary.get("smart_consecutive_days", 0) >= 3:
        matched.append(CONDITION_LABELS["smart_consecutive_3d"])
    if (
        "foreign_institution_both_5d" in selected_conditions
        and summary.get("foreign_5d", 0) > 0
        and summary.get("institution_5d", 0) > 0
    ):
        matched.append(CONDITION_LABELS["foreign_institution_both_5d"])

    return matched


def scan_one_stock(
    code: str,
    start: str,
    end: str,
    selected_conditions: list[str],
) -> tuple[pd.DataFrame, list[str], dict | None, dict | None]:
    prices = load_price(code, start, end)
    if prices.empty:
        return prices, [], None, None
    prices = add_all_indicators(prices)

    summary = None
    accumulation = None
    if FLOW_CONDITIONS.intersection(selected_conditions):
        investor_df = load_investor_trading_by_date(code, start, end)
        if not investor_df.empty:
            summary = summarize_investor_flow(investor_df, prices)
            accumulation = classify_accumulation(summary)

    return prices, evaluate_conditions(prices, selected_conditions, summary), summary, accumulation
