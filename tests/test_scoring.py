import math

from src.scoring import (
    calculate_etf_score,
    calculate_stock_score,
    clip_score,
    grade_from_score,
    safe_number,
)


def test_grade_from_score_ranges():
    assert grade_from_score(85) == "매우 양호"
    assert grade_from_score(65) == "양호"
    assert grade_from_score(50) == "중립"
    assert grade_from_score(35) == "주의"
    assert grade_from_score(10) == "위험"


def test_clip_score_limits_range():
    assert clip_score(-10) == 0
    assert clip_score(120) == 100
    assert clip_score(55) == 55


def test_safe_number_handles_none_nan_inf_and_strings():
    assert safe_number(None, 7) == 7
    assert safe_number(float("nan"), 7) == 7
    assert safe_number(float("inf"), 7) == 7
    assert safe_number("12.5") == 12.5


def test_stock_score_is_in_range_and_returns_factors():
    price = {
        "close": 100,
        "ma20": 90,
        "ma60": 80,
        "return_20d": 5,
        "return_60d": 10,
        "rsi": 55,
        "volume_ratio_20d": 1.5,
        "high_52w": 110,
    }
    result = calculate_stock_score(price_summary=price)
    assert 0 <= result["total_score"] <= 100
    assert result["positive_factors"]
    assert isinstance(result["negative_factors"], list)


def test_etf_score_is_in_range_and_returns_factors():
    summary = {
        "latest_close": 100,
        "ma20": 95,
        "ma60": 90,
        "return_20d": 4,
        "return_60d": 8,
        "high_52w": 105,
        "avg_trading_value_20d": 20_000_000_000,
        "trading_value_ratio_20d": 1.2,
        "liquidity_grade": "높음",
        "latest_deviation_rate": 0.2,
        "latest_tracking_error_rate": 0.5,
        "component_count": 30,
        "top10_weight": 60,
    }
    result = calculate_etf_score(etf_summary=summary)
    assert 0 <= result["total_score"] <= 100
    assert result["positive_factors"]


def test_normalize_missing_excludes_missing_sections():
    price = {"close": 100, "ma20": 90, "ma60": 80, "return_20d": 5, "rsi": 50}
    normalized = calculate_stock_score(price_summary=price, normalize_missing=True)
    unnormalized = calculate_stock_score(price_summary=price, normalize_missing=False)
    assert normalized["total_score"] >= unnormalized["total_score"]
    assert "뉴스 데이터 없음" in normalized["warnings"]


def test_risk_penalty_is_capped():
    price = {"close": 100, "ma20": 120, "ma60": 130, "return_20d": -30, "rsi": 90}
    investor = {"smart_money_net_value_20d": -1, "smart_money_strength_20d": -5}
    financial = {"DebtRatio": 500, "PER": -1}
    news = {"negative": 5}
    result = calculate_stock_score(
        price_summary=price,
        investor_summary=investor,
        financial_summary=financial,
        news_summary=news,
        normalize_missing=False,
    )
    assert result["sub_scores"]["리스크 패널티"] >= -15


def test_inputs_are_not_mutated():
    price = {"close": 100, "ma20": 90, "return_20d": 5, "rsi": 50}
    before = dict(price)
    calculate_stock_score(price_summary=price)
    assert price == before
