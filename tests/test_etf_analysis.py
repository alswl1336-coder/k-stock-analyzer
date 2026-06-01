import pandas as pd

from src.etf_analysis import classify_etf_risk, summarize_etf
from src.etf_loader import classify_etf_name, infer_etf_category, infer_etf_flags, infer_etf_provider, normalize_etf_ohlcv


def sample_etf_price(rows=80):
    close = pd.Series(range(10000, 10000 + rows), dtype="float64")
    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=rows),
            "NAV": close + 5,
            "Open": close - 10,
            "High": close + 20,
            "Low": close - 20,
            "Close": close,
            "Volume": [100000] * rows,
            "TradingValue": [2_000_000_000] * rows,
            "UnderlyingIndex": pd.Series(range(300, 300 + rows), dtype="float64"),
        }
    )


def test_etf_provider_inference():
    assert infer_etf_provider("KODEX 200") == "삼성자산운용"
    assert infer_etf_provider("TIGER 미국S&P500") == "미래에셋자산운용"


def test_etf_category_inference():
    assert infer_etf_category("KODEX 200") == "국내지수"
    assert infer_etf_category("TIGER 미국NASDAQ100") == "해외주식"
    assert infer_etf_category("ACE 국고채10년") == "채권/금리"


def test_etf_flags_inference():
    flags = infer_etf_flags("KODEX 레버리지 합성 H")
    assert flags["IsLeveraged"]
    assert flags["IsSynthetic"]
    assert flags["IsHedged"]
    assert infer_etf_flags("KODEX 인버스")["IsInverse"]


def test_normalize_etf_ohlcv_columns():
    raw = pd.DataFrame(
        {
            "날짜": pd.date_range("2024-01-01", periods=2),
            "시가": [1, 2],
            "고가": [2, 3],
            "저가": [1, 1],
            "종가": [2, 2],
            "거래량": [100, 200],
            "거래대금": [1000, 2000],
            "기초지수": [300, 301],
            "NAV": [2, 2],
        }
    )
    result = normalize_etf_ohlcv(raw)
    assert {"Date", "NAV", "Open", "High", "Low", "Close", "Volume", "TradingValue", "UnderlyingIndex"}.issubset(
        result.columns
    )


def test_summarize_etf_calculates_metrics():
    deviation = pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=1), "DeviationRate": [0.3]})
    tracking = pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=1), "TrackingErrorRate": [0.8]})
    portfolio = pd.DataFrame({"ComponentName": ["삼성전자"], "Weight": [20.0]})
    summary = summarize_etf(sample_etf_price(), deviation, tracking, portfolio_df=portfolio)
    assert summary["latest_close"] == 10079
    assert summary["avg_trading_value_20d"] == 2_000_000_000
    assert summary["component_count"] == 1
    assert summary["top_component_name"] == "삼성전자"


def test_classify_etf_risk_grades():
    deviation = pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=1), "DeviationRate": [1.2]})
    tracking = pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=1), "TrackingErrorRate": [3.5]})
    info = classify_etf_name("KODEX 레버리지")
    risk = classify_etf_risk(info, sample_etf_price(), deviation, tracking)
    assert risk["LiquidityGrade"] == "보통"
    assert risk["DeviationGrade"] == "위험"
    assert risk["TrackingGrade"] == "위험"
    assert "레버리지 ETF" in risk["ProductRiskFlags"]


def test_etf_analysis_does_not_mutate_input():
    price = sample_etf_price()
    before = price.copy(deep=True)
    summarize_etf(price)
    pd.testing.assert_frame_equal(price, before)
