import pandas as pd

from src.investor_flow import classify_accumulation, summarize_investor_flow


def sample_investor_df(rows=70):
    dates = pd.date_range("2024-01-01", periods=rows)
    foreign = [100_000_000] * rows
    institution = [50_000_000] * rows
    individual = [-150_000_000] * rows
    return pd.DataFrame(
        {
            "Date": dates,
            "ForeignNetValue": foreign,
            "InstitutionNetValue": institution,
            "IndividualNetValue": individual,
            "ForeignNetVolume": [1000] * rows,
            "InstitutionNetVolume": [500] * rows,
            "IndividualNetVolume": [-1500] * rows,
            "ForeignCumNetValue": pd.Series(foreign).cumsum(),
            "InstitutionCumNetValue": pd.Series(institution).cumsum(),
            "SmartMoneyNetValue": pd.Series(foreign) + pd.Series(institution),
            "SmartMoneyNetVolume": [1500] * rows,
            "SmartMoneyCumNetValue": (pd.Series(foreign) + pd.Series(institution)).cumsum(),
        }
    )


def sample_price_df(rows=70):
    close = pd.Series(range(1000, 1000 + rows), dtype="float64")
    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=rows),
            "Open": close - 5,
            "High": close + 10,
            "Low": close - 10,
            "Close": close,
            "Volume": [10_000_000] * rows,
        }
    )


def test_summarize_creates_foreign_and_institution_keys():
    summary = summarize_investor_flow(sample_investor_df(), sample_price_df())
    assert summary["foreign_5d"] == 500_000_000
    assert summary["institution_5d"] == 250_000_000
    assert summary["smart_20d"] == 3_000_000_000


def test_flow_strength_calculation():
    summary = summarize_investor_flow(sample_investor_df(), sample_price_df())
    turnover_20 = (sample_price_df()["Close"] * sample_price_df()["Volume"]).tail(20).sum()
    expected = 3_000_000_000 / turnover_20 * 100
    assert summary["flow_strength_20d"] == expected


def test_consecutive_positive_days():
    summary = summarize_investor_flow(sample_investor_df(), sample_price_df())
    assert summary["foreign_consecutive_days"] == 70
    assert summary["institution_consecutive_days"] == 70
    assert summary["smart_consecutive_days"] == 70


def test_classify_accumulation_returns_grade_and_conditions():
    summary = summarize_investor_flow(sample_investor_df(), sample_price_df())
    result = classify_accumulation(summary)
    assert result["score"] >= 50
    assert result["grade"] in {"강함", "보통", "약함", "없음"}
    assert "matched_conditions" in result
    assert result["warning"]


def test_summarize_does_not_mutate_inputs():
    investor_df = sample_investor_df()
    price_df = sample_price_df()
    investor_before = investor_df.copy(deep=True)
    price_before = price_df.copy(deep=True)

    summarize_investor_flow(investor_df, price_df)

    pd.testing.assert_frame_equal(investor_df, investor_before)
    pd.testing.assert_frame_equal(price_df, price_before)
