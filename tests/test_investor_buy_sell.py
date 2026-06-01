import pandas as pd

from src.investor_flow import normalize_investor_buy_sell_frames


def test_buy_sell_columns_are_normalized_and_net_is_calculated():
    raw = pd.DataFrame(
        {
            "외국인 매수": [1000, 2000],
            "외국인 매도": [400, 500],
            "기관 매수": [3000, 4000],
            "기관 매도": [1000, 1500],
            "개인 매수": [500, 600],
            "개인 매도": [700, 800],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )

    result = normalize_investor_buy_sell_frames(raw)

    assert result.loc[0, "ForeignNetValue"] == 600
    assert result.loc[1, "InstitutionNetValue"] == 2500
    assert result.loc[0, "DataMode"] == "buy_sell"


def test_net_only_mode_when_only_net_columns_exist():
    raw = pd.DataFrame(
        {"외국인 순매수": [100], "기관합계 순매수": [-50], "개인 순매수": [-50]},
        index=pd.to_datetime(["2024-01-02"]),
    )

    result = normalize_investor_buy_sell_frames(raw)

    assert result.loc[0, "DataMode"] == "net_only"
    assert result.loc[0, "ForeignNetValue"] == 100
    assert pd.isna(result.loc[0, "ForeignBuyValue"])


def test_pykrx_detail_net_columns_are_used_as_net_only():
    raw = pd.DataFrame(
        {
            "금융투자": [10],
            "보험": [20],
            "투신": [30],
            "사모": [40],
            "은행": [50],
            "기타금융": [60],
            "연기금": [70],
            "개인": [-100],
            "외국인": [200],
        },
        index=pd.to_datetime(["2024-01-02"]),
    )

    result = normalize_investor_buy_sell_frames(raw)

    assert result.loc[0, "DataMode"] == "net_only"
    assert result.loc[0, "ForeignNetValue"] == 200
    assert result.loc[0, "InstitutionNetValue"] == 280
    assert result.loc[0, "IndividualNetValue"] == -100


def test_smart_money_columns_are_calculated():
    raw = pd.DataFrame(
        {
            "외국인 매수": [1000],
            "외국인 매도": [100],
            "기관 매수": [2000],
            "기관 매도": [300],
        },
        index=pd.to_datetime(["2024-01-02"]),
    )

    result = normalize_investor_buy_sell_frames(raw)

    assert result.loc[0, "SmartBuyValue"] == 3000
    assert result.loc[0, "SmartSellValue"] == 400
    assert result.loc[0, "SmartNetValue"] == 2600


def test_date_index_becomes_date_column_and_numbers_are_numeric():
    raw = pd.DataFrame(
        {"외국인 매수": ["1,000"], "외국인 매도": ["200"]},
        index=pd.to_datetime(["2024-01-02"]),
    )

    result = normalize_investor_buy_sell_frames(raw)

    assert "Date" in result.columns
    assert pd.api.types.is_datetime64_any_dtype(result["Date"])
    assert result.loc[0, "ForeignNetValue"] == 800


def test_empty_dataframe_has_debug_attrs():
    result = normalize_investor_buy_sell_frames(pd.DataFrame())

    assert result.empty
    assert "debug" in result.attrs
    assert result.attrs["debug"]["data_mode"] == "unavailable"


def test_original_dataframe_is_not_mutated():
    raw = pd.DataFrame({"외국인 매수": [100], "외국인 매도": [50]}, index=pd.to_datetime(["2024-01-02"]))
    before = raw.copy(deep=True)

    normalize_investor_buy_sell_frames(raw)

    pd.testing.assert_frame_equal(raw, before)
