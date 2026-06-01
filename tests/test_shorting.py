import pandas as pd

from src.shorting import calculate_shorting_score, normalize_shorting_data, summarize_shorting_data


def sample_frames():
    dates = pd.date_range("2024-01-01", periods=25, freq="B")
    volume = pd.DataFrame({"공매도": range(100, 125), "매수": [1000] * 25, "비중": [5.0] * 25}, index=dates)
    value = pd.DataFrame({"공매도": range(1000, 1025), "매수": [10000] * 25, "비중": [10.0] * 25}, index=dates)
    balance = pd.DataFrame({"공매도잔고": range(1000, 1025), "시가총액": [100000] * 25, "비중": [1.0] * 25}, index=dates)
    price = pd.DataFrame({"Date": dates, "Close": range(50000, 50025)})
    return volume, value, balance, price


def test_normalize_shorting_data_columns_and_date():
    volume, value, balance, price = sample_frames()
    result = normalize_shorting_data(volume, value, balance, price)

    assert "Date" in result.columns
    assert pd.api.types.is_datetime64_any_dtype(result["Date"])
    assert {"ShortVolume", "ShortValue", "ShortBalance", "Close"}.issubset(result.columns)


def test_summarize_shorting_data_returns_recent_metrics():
    result = normalize_shorting_data(*sample_frames())
    summary = summarize_shorting_data(result)

    assert summary["short_volume_ratio_1d"] == 5.0
    assert summary["short_volume_ratio_20d_avg"] == 5.0
    assert "short_balance_change_rate" in summary


def test_calculate_shorting_score_range_and_grade():
    summary = {
        "short_balance_ratio": 6,
        "short_balance_change_rate": 10,
        "short_volume_ratio_20d_avg": 12,
        "short_volume_change_20d": 20,
        "price_change_20d": -5,
    }

    score = calculate_shorting_score(summary)

    assert 0 <= score["score"] <= 100
    assert score["grade"] in {"낮음", "보통", "주의", "높음"}
    assert score["negative_factors"]


def test_positive_factors_when_shorting_declines():
    summary = {
        "short_balance_ratio": 1,
        "short_balance_change_rate": -5,
        "short_volume_ratio_20d_avg": 2,
        "short_volume_change_20d": -15,
        "price_change_20d": 5,
    }

    score = calculate_shorting_score(summary)

    assert score["score"] > 70
    assert score["positive_factors"]


def test_input_frames_are_not_mutated():
    volume, value, balance, price = sample_frames()
    before = volume.copy(deep=True)

    normalize_shorting_data(volume, value, balance, price)

    pd.testing.assert_frame_equal(volume, before)
