from __future__ import annotations

import math
from copy import deepcopy
from typing import Any


DISCLAIMER = "종합점수는 정량 지표 기반의 분석 보조 지표이며 투자 추천이 아닙니다."


def safe_number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def has_number(data: dict | None, key: str) -> bool:
    if not data or key not in data:
        return False
    value = data.get(key)
    try:
        number = float(value)
        return not (math.isnan(number) or math.isinf(number))
    except (TypeError, ValueError):
        return False


def clip_score(value: Any, min_value: float = 0, max_value: float = 100) -> float:
    return max(min_value, min(max_value, safe_number(value)))


def grade_from_score(score: float) -> str:
    score = safe_number(score)
    if score >= 80:
        return "매우 양호"
    if score >= 65:
        return "양호"
    if score >= 50:
        return "중립"
    if score >= 35:
        return "주의"
    return "위험"


def _add(score: float, points: float, ok: bool, factors: list[str], label: str) -> float:
    if ok:
        factors.append(label)
        return score + points
    return score


def _missing_summary(label: str, data: dict | None, keys: list[str]) -> bool:
    return not data or not any(has_number(data, key) for key in keys)


def _normalize_total(sub_scores: dict[str, float], available_caps: dict[str, float], total_cap: float) -> float:
    available = sum(cap for key, cap in available_caps.items() if key in sub_scores)
    raw = sum(sub_scores.values())
    if available <= 0:
        return 0
    return clip_score(raw / available * total_cap)


def _stock_price_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    score = 0.0
    close = safe_number(summary.get("close"))
    high_52w = safe_number(summary.get("high_52w"))
    score = _add(score, 5, safe_number(summary.get("return_20d")) > 0, positives, "20일 수익률 양호")
    score = _add(score, 5, safe_number(summary.get("return_60d")) > 0, positives, "60일 수익률 양호")
    score = _add(score, 4, close > safe_number(summary.get("ma20")), positives, "종가가 MA20 상회")
    score = _add(score, 4, close > safe_number(summary.get("ma60")), positives, "종가가 MA60 상회")
    score = _add(score, 4, safe_number(summary.get("ma20")) > safe_number(summary.get("ma60")), positives, "MA20이 MA60 상회")
    rsi = safe_number(summary.get("rsi"))
    score = _add(score, 3, 40 <= rsi <= 65, positives, "RSI 중립 구간")
    score = _add(score, 3, safe_number(summary.get("volume_ratio_20d")) >= 1.2, positives, "거래량 증가")
    score = _add(score, 2, high_52w > 0 and close >= high_52w * 0.85, positives, "52주 최고가 근접")
    if rsi >= 75:
        negatives.append("RSI 과열")
    if close and safe_number(summary.get("ma60")) and close < safe_number(summary.get("ma60")):
        negatives.append("중기 추세 약세")
    if safe_number(summary.get("return_20d")) < -10:
        negatives.append("최근 20일 약세")
    return min(score, 25)


def _stock_flow_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    score = 0.0
    smart20 = safe_number(summary.get("smart_money_net_value_20d"))
    strength = safe_number(summary.get("smart_money_strength_20d", summary.get("flow_strength_20d")))
    score = _add(score, 3, safe_number(summary.get("foreign_net_value_5d")) > 0, positives, "외국인 5일 순매수")
    score = _add(score, 4, safe_number(summary.get("foreign_net_value_20d", summary.get("foreign_20d"))) > 0, positives, "외국인 20일 순매수")
    score = _add(score, 3, safe_number(summary.get("institution_net_value_5d")) > 0, positives, "기관 5일 순매수")
    score = _add(score, 4, safe_number(summary.get("institution_net_value_20d", summary.get("institution_20d"))) > 0, positives, "기관 20일 순매수")
    score = _add(score, 3, smart20 > 0, positives, "외국인/기관 20일 순매수")
    score = _add(score, 2, strength >= 3, positives, "20일 수급 강도 양호")
    score = _add(score, 1, safe_number(summary.get("smart_money_consecutive_days")) >= 3, positives, "연속 순매수")
    if smart20 < 0:
        negatives.append("외국인/기관 20일 순매도")
    if strength <= -3:
        negatives.append("수급 약세")
    return min(score, 20)


def _stock_financial_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    score = 0.0
    score = _add(score, 4, safe_number(summary.get("revenue_yoy", summary.get("RevenueYoY"))) > 0, positives, "매출 YoY 증가")
    score = _add(score, 5, safe_number(summary.get("operating_income_yoy", summary.get("OperatingIncomeYoY"))) > 0, positives, "영업이익 YoY 증가")
    score = _add(score, 4, safe_number(summary.get("net_income_yoy", summary.get("NetIncomeYoY"))) > 0, positives, "순이익 YoY 증가")
    score = _add(score, 3, safe_number(summary.get("operating_margin", summary.get("OperatingMargin"))) > 5, positives, "영업이익률 양호")
    score = _add(score, 3, safe_number(summary.get("roe", summary.get("ROE"))) > 5, positives, "ROE 양호")
    debt = safe_number(summary.get("debt_ratio", summary.get("DebtRatio")), 9999)
    score = _add(score, 3, debt < 200, positives, "부채비율 안정")
    per = safe_number(summary.get("per", summary.get("PER")))
    pbr = safe_number(summary.get("pbr", summary.get("PBR")))
    score = _add(score, 2, 0 < per < 30, positives, "PER 참고 범위")
    score = _add(score, 1, 0 < pbr < 3, positives, "PBR 참고 범위")
    if safe_number(summary.get("operating_income_yoy", summary.get("OperatingIncomeYoY"))) < 0:
        negatives.append("영업이익 감소")
    if safe_number(summary.get("net_income_yoy", summary.get("NetIncomeYoY"))) < 0:
        negatives.append("순이익 감소")
    if debt > 300:
        negatives.append("부채비율 과다")
    if per <= 0:
        negatives.append("적자 또는 PER 해석 제한")
    return min(score, 25)


def _news_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    score = 0.0
    positive = safe_number(summary.get("positive_news_count", summary.get("positive")))
    negative = safe_number(summary.get("negative_news_count", summary.get("negative")))
    score = _add(score, 2, safe_number(summary.get("recent_news_count", summary.get("count"))) >= 3, positives, "최근 뉴스 관심")
    score = _add(score, 3, positive >= 1, positives, "긍정 뉴스 존재")
    score = _add(score, 3, positive > negative, positives, "긍정 뉴스 우세")
    score = _add(score, 2, negative == 0, positives, "부정 뉴스 제한적")
    tags = " ".join(str(tag) for tag in summary.get("major_tags", [])) if isinstance(summary.get("major_tags"), list) else str(summary.get("major_tags", summary.get("top_tag", "")))
    if negative >= 2:
        negatives.append("부정 뉴스 다수")
    for tag in ["소송", "제재", "리콜", "파업", "유상증자"]:
        if tag in tags:
            negatives.append(f"{tag} 관련 뉴스")
    return min(score, 10)


def _sector_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    score = 0.0
    sector_return = safe_number(summary.get("sector_return_20d", summary.get("SectorAvgReturn20D")))
    excess = safe_number(summary.get("excess_return_20d", summary.get("ExcessReturn20D")))
    percentile = safe_number(summary.get("sector_rank_percentile", summary.get("SectorPercentile")))
    strength = safe_number(summary.get("sector_strength_score", summary.get("SectorStrengthScore")))
    score = _add(score, 3, sector_return > 0, positives, "섹터 20일 수익률 양호")
    score = _add(score, 5, excess > 0, positives, "섹터 대비 초과수익")
    score = _add(score, 4, percentile >= 70, positives, "섹터 내 상위권")
    score = _add(score, 3, strength >= 60, positives, "섹터 강도 양호")
    if sector_return < 0:
        negatives.append("섹터 약세")
    if excess < -5:
        negatives.append("섹터 대비 부진")
    return min(score, 15)


def _stock_risk_penalty(price: dict, investor: dict, financial: dict, news: dict, negatives: list[str]) -> float:
    penalty = 0.0
    if safe_number(price.get("rsi")) >= 80:
        penalty += 3
    if safe_number(price.get("return_20d")) <= -15:
        penalty += 4
    if safe_number(investor.get("smart_money_net_value_20d")) < 0 and safe_number(investor.get("smart_money_strength_20d", investor.get("flow_strength_20d"))) <= -3:
        penalty += 3
    if safe_number(financial.get("debt_ratio", financial.get("DebtRatio"))) >= 400:
        penalty += 3
    if safe_number(news.get("negative_news_count", news.get("negative"))) >= 3:
        penalty += 2
    penalty = min(penalty, 15)
    if penalty:
        negatives.append("리스크 패널티 적용")
    return -penalty


def _stock_shorting_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    score = safe_number(summary.get("shorting_score"), 70.0) / 100 * 20
    grade = str(summary.get("shorting_grade", ""))
    if grade in {"낮음", "보통"}:
        positives.append("공매도 위험도 참고 범위")
    if grade in {"주의", "높음"}:
        negatives.append("공매도 위험도 주의")
    return min(max(score, 0), 20)


def calculate_stock_score(
    price_summary: dict | None = None,
    technical_summary: dict | None = None,
    investor_summary: dict | None = None,
    financial_summary: dict | None = None,
    news_summary: dict | None = None,
    sector_summary: dict | None = None,
    shorting_summary: dict | None = None,
    normalize_missing: bool = True,
    include_news: bool = True,
    include_financials: bool = True,
    include_sector: bool = True,
    include_flow: bool = True,
    include_shorting: bool = True,
) -> dict:
    price = deepcopy(price_summary or {})
    price.update(deepcopy(technical_summary or {}))
    investor = deepcopy(investor_summary or {})
    financial = deepcopy(financial_summary or {})
    news = deepcopy(news_summary or {})
    sector = deepcopy(sector_summary or {})
    shorting = deepcopy(shorting_summary or {})
    positives: list[str] = []
    negatives: list[str] = []
    warnings = [DISCLAIMER]
    sub_scores: dict[str, float] = {}
    caps: dict[str, float] = {}

    if _missing_summary("가격 기술", price, ["close", "return_20d", "ma20", "rsi"]):
        return {"asset_type": "Stock", "total_score": None, "grade": "계산 불가", "sub_scores": {}, "positive_factors": [], "negative_factors": [], "warnings": warnings + ["가격 데이터가 없어 종합점수를 계산하지 못했습니다."]}
    sub_scores["가격 기술"] = _stock_price_score(price, positives, negatives)
    caps["가격 기술"] = 25
    if include_flow and (not normalize_missing or not _missing_summary("수급", investor, ["foreign_20d", "smart_money_net_value_20d"])):
        sub_scores["수급"] = _stock_flow_score(investor, positives, negatives)
        caps["수급"] = 20
    elif include_flow:
        warnings.append("수급 데이터 없음")
    if include_financials and (not normalize_missing or not _missing_summary("실적/밸류에이션", financial, ["RevenueYoY", "PER", "per"])):
        sub_scores["실적/밸류에이션"] = _stock_financial_score(financial, positives, negatives)
        caps["실적/밸류에이션"] = 25
    elif include_financials:
        warnings.append("실적/밸류에이션 데이터 없음")
    if include_news and (not normalize_missing or not _missing_summary("뉴스", news, ["count", "positive", "recent_news_count"])):
        sub_scores["뉴스"] = _news_score(news, positives, negatives)
        caps["뉴스"] = 10
    elif include_news:
        warnings.append("뉴스 데이터 없음")
    if include_sector and (not normalize_missing or not _missing_summary("섹터", sector, ["SectorAvgReturn20D", "ExcessReturn20D", "sector_return_20d"])):
        sub_scores["섹터"] = _sector_score(sector, positives, negatives)
        caps["섹터"] = 15
    elif include_sector:
        warnings.append("섹터 데이터 없음")
    if include_shorting and (not normalize_missing or not _missing_summary("공매도", shorting, ["shorting_score"])):
        sub_scores["공매도"] = _stock_shorting_score(shorting, positives, negatives)
        caps["공매도"] = 20
    elif include_shorting:
        warnings.append("공매도 데이터 없음")
    risk = _stock_risk_penalty(price, investor, financial, news, negatives)
    sub_scores["리스크 패널티"] = risk
    total = _normalize_total(sub_scores, caps, 100) if normalize_missing else sum(sub_scores.values())
    total = clip_score(total)
    return {"asset_type": "Stock", "total_score": total, "grade": grade_from_score(total), "sub_scores": sub_scores, "positive_factors": positives, "negative_factors": negatives, "warnings": warnings}


def _etf_price_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    score = 0.0
    close = safe_number(summary.get("latest_close", summary.get("close")))
    high_52w = safe_number(summary.get("high_52w"))
    score = _add(score, 6, safe_number(summary.get("return_20d")) > 0, positives, "20일 수익률 양호")
    score = _add(score, 6, safe_number(summary.get("return_60d")) > 0, positives, "60일 수익률 양호")
    score = _add(score, 4, close > safe_number(summary.get("ma20")), positives, "종가가 MA20 상회")
    score = _add(score, 4, close > safe_number(summary.get("ma60")), positives, "종가가 MA60 상회")
    score = _add(score, 3, safe_number(summary.get("ma20")) > safe_number(summary.get("ma60")), positives, "MA20이 MA60 상회")
    score = _add(score, 2, high_52w > 0 and close >= high_52w * 0.85, positives, "52주 최고가 근접")
    return min(score, 25)


def _etf_liquidity_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    avg_value = safe_number(summary.get("avg_trading_value_20d"))
    ratio = safe_number(summary.get("trading_value_ratio_20d"))
    grade = str(summary.get("liquidity_grade", summary.get("LiquidityGrade", "")))
    score = 0.0
    if avg_value >= 10_000_000_000:
        score += 10
        positives.append("20일 평균 거래대금 충분")
    elif avg_value >= 1_000_000_000:
        score += 6
        positives.append("20일 평균 거래대금 참고 가능")
    score = _add(score, 4, ratio >= 1, positives, "최근 거래대금 평균 상회")
    score = _add(score, 6, grade == "높음", positives, "유동성 등급 높음")
    if avg_value < 1_000_000_000:
        negatives.append("ETF 유동성 부족")
    return min(score, 20)


def _etf_nav_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    deviation = abs(safe_number(summary.get("latest_deviation_rate")))
    tracking = safe_number(summary.get("latest_tracking_error_rate"))
    score = 0.0
    if deviation < 0.5:
        score += 8
        positives.append("괴리율 안정")
    elif deviation < 1.0:
        score += 5
    if tracking < 1.0:
        score += 8
        positives.append("추적오차 안정")
    elif tracking < 3.0:
        score += 5
    score = _add(score, 2, summary.get("deviation_grade") == "안정" or summary.get("DeviationGrade") == "안정", positives, "괴리율 등급 안정")
    score = _add(score, 2, summary.get("tracking_grade") == "안정" or summary.get("TrackingGrade") == "안정", positives, "추적오차 등급 안정")
    if deviation >= 1.0:
        negatives.append("괴리율 확대")
    if tracking >= 3.0:
        negatives.append("추적오차 확대")
    return min(score, 20)


def _etf_flow_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    score = 0.0
    smart20 = safe_number(summary.get("smart_money_net_value_20d"))
    score = _add(score, 3, safe_number(summary.get("foreign_net_value_5d")) > 0, positives, "외국인 5일 순매수")
    score = _add(score, 3, safe_number(summary.get("institution_net_value_5d")) > 0, positives, "기관 5일 순매수")
    score = _add(score, 5, smart20 > 0, positives, "외국인/기관 20일 순매수")
    score = _add(score, 2, safe_number(summary.get("smart_money_cum_change", smart20)) > 0, positives, "누적 순매수 증가")
    score = _add(score, 2, safe_number(summary.get("smart_money_consecutive_days")) >= 3, positives, "연속 순매수")
    if smart20 < 0:
        negatives.append("ETF 수급 약세")
    return min(score, 15)


def _etf_structure_score(summary: dict, positives: list[str], negatives: list[str]) -> float:
    score = 0.0
    score = _add(score, 3, safe_number(summary.get("component_count")) >= 10, positives, "구성종목 수 충분")
    top_weight = safe_number(summary.get("top_component_weight"))
    top10_weight = safe_number(summary.get("top10_weight"))
    score = _add(score, 3, top10_weight > 0 and top10_weight <= 80, positives, "상위 10개 비중 분산")
    leveraged = bool(summary.get("is_leveraged", summary.get("IsLeveraged")))
    inverse = bool(summary.get("is_inverse", summary.get("IsInverse")))
    synthetic = bool(summary.get("is_synthetic", summary.get("IsSynthetic")))
    score = _add(score, 2, not leveraged, positives, "레버리지 상품 아님")
    score = _add(score, 1, not inverse, positives, "인버스 상품 아님")
    score = _add(score, 1, not synthetic, positives, "합성 ETF 아님")
    if leveraged:
        negatives.append("레버리지 상품")
    if inverse:
        negatives.append("인버스 상품")
    if synthetic:
        negatives.append("합성 ETF")
    if top_weight >= 30:
        negatives.append("구성종목 집중도 높음")
    return min(score, 10)


def _etf_risk_penalty(summary: dict, news: dict, negatives: list[str]) -> float:
    penalty = 0.0
    if summary.get("is_leveraged", summary.get("IsLeveraged")):
        penalty += 5
    if summary.get("is_inverse", summary.get("IsInverse")):
        penalty += 5
    if summary.get("is_synthetic", summary.get("IsSynthetic")):
        penalty += 3
    if safe_number(summary.get("avg_trading_value_20d")) < 1_000_000_000:
        penalty += 4
    if abs(safe_number(summary.get("latest_deviation_rate"))) >= 1:
        penalty += 3
    if safe_number(summary.get("latest_tracking_error_rate")) >= 3:
        penalty += 3
    if safe_number(news.get("negative_news_count", news.get("negative"))) >= 3:
        penalty += 2
    penalty = min(penalty, 20)
    if penalty:
        negatives.append("ETF 리스크 패널티 적용")
    return -penalty


def calculate_etf_score(
    etf_summary: dict | None = None,
    flow_summary: dict | None = None,
    news_summary: dict | None = None,
    normalize_missing: bool = True,
    include_news: bool = True,
    include_flow: bool = True,
    include_structure: bool = True,
) -> dict:
    summary = deepcopy(etf_summary or {})
    flow = deepcopy(flow_summary or {})
    summary.update({key: value for key, value in flow.items() if key not in summary})
    news = deepcopy(news_summary or {})
    positives: list[str] = []
    negatives: list[str] = []
    warnings = [DISCLAIMER]
    sub_scores: dict[str, float] = {}
    caps: dict[str, float] = {}
    if _missing_summary("가격 추세", summary, ["latest_close", "return_20d", "ma20"]):
        return {"asset_type": "ETF", "total_score": None, "grade": "계산 불가", "sub_scores": {}, "positive_factors": [], "negative_factors": [], "warnings": warnings + ["가격 데이터가 없어 종합점수를 계산하지 못했습니다."]}
    sub_scores["가격 추세"] = _etf_price_score(summary, positives, negatives)
    caps["가격 추세"] = 25
    sub_scores["유동성"] = _etf_liquidity_score(summary, positives, negatives)
    caps["유동성"] = 20
    if not normalize_missing or any(has_number(summary, key) for key in ["latest_deviation_rate", "latest_tracking_error_rate"]):
        sub_scores["NAV/괴리율/추적오차"] = _etf_nav_score(summary, positives, negatives)
        caps["NAV/괴리율/추적오차"] = 20
    else:
        warnings.append("NAV/괴리율/추적오차 데이터 없음")
    if include_flow and (not normalize_missing or any(has_number(summary, key) for key in ["foreign_net_value_5d", "smart_money_net_value_20d"])):
        sub_scores["수급"] = _etf_flow_score(summary, positives, negatives)
        caps["수급"] = 15
    elif include_flow:
        warnings.append("수급 데이터 없음")
    if include_structure and (not normalize_missing or any(has_number(summary, key) for key in ["component_count", "top_component_weight"])):
        sub_scores["구성종목/상품구조"] = _etf_structure_score(summary, positives, negatives)
        caps["구성종목/상품구조"] = 10
    elif include_structure:
        warnings.append("구성종목 데이터 없음")
    if include_news and (not normalize_missing or not _missing_summary("뉴스", news, ["count", "positive", "recent_news_count"])):
        sub_scores["뉴스"] = _news_score(news, positives, negatives)
        caps["뉴스"] = 10
    elif include_news:
        warnings.append("뉴스 데이터 없음")
    risk = _etf_risk_penalty(summary, news, negatives)
    sub_scores["리스크 패널티"] = risk
    total = _normalize_total(sub_scores, caps, 100) if normalize_missing else sum(sub_scores.values())
    total = clip_score(total)
    return {"asset_type": "ETF", "total_score": total, "grade": grade_from_score(total), "sub_scores": sub_scores, "positive_factors": positives, "negative_factors": negatives, "warnings": warnings}


def calculate_composite_score(asset_type: str, **kwargs) -> dict:
    if str(asset_type).upper() == "ETF":
        return calculate_etf_score(**kwargs)
    return calculate_stock_score(**kwargs)
