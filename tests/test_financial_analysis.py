import pandas as pd

from src.dart_loader import parse_amount
from src.financial_analysis import calculate_financial_ratios, classify_earnings_trend, extract_key_financials, normalize_account_name


def sample_financials():
    return pd.DataFrame(
        {
            "BusinessYear": [2023, 2023, 2023, 2023, 2023, 2023, 2024, 2024, 2024, 2024, 2024, 2024],
            "ReportCode": ["11011"] * 12,
            "AccountName": ["매출액", "영업이익", "당기순이익", "부채총계", "자본총계", "영업활동현금흐름"] * 2,
            "CurrentAmount": [1000, 100, 80, 300, 700, 90, 1200, 150, 100, 320, 800, 120],
            "Ord": list(range(12)),
        }
    )


def test_parse_amount():
    assert parse_amount("1,234") == 1234
    assert pd.isna(parse_amount("-"))


def test_account_alias_and_ratios():
    assert normalize_account_name("수익(매출액)") == "Revenue"
    key = extract_key_financials(sample_financials())
    ratios = calculate_financial_ratios(key)
    latest = ratios.iloc[-1]
    assert latest["Revenue"] == 1200
    assert latest["OperatingMargin"] == 12.5
    assert latest["DebtRatio"] == 40
    assert latest["ROE"] == 12.5


def test_earnings_grade_and_no_mutation():
    df = sample_financials()
    before = df.copy(deep=True)
    ratios = calculate_financial_ratios(extract_key_financials(df))
    grade = classify_earnings_trend(ratios.iloc[-1].to_dict())
    assert grade["grade"] in {"개선", "유지", "악화", "데이터 부족"}
    pd.testing.assert_frame_equal(df, before)
