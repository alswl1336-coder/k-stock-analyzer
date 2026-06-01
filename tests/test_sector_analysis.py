import pandas as pd

from src.sector_analysis import compare_stock_to_sector, summarize_sector_performance
from src.sector_loader import merge_sector_info


def test_sector_merge_and_summary():
    stocks = pd.DataFrame({"Code": ["000001", "000002"], "Name": ["A은행", "B바이오"], "Market": ["KOSPI", "KOSPI"]})
    sector_map = pd.DataFrame({"Code": ["000001"], "Sector": ["금융"], "Industry": ["은행"]})
    merged = merge_sector_info(stocks, sector_map)
    assert merged.loc[merged["Code"] == "000001", "Sector"].iloc[0] == "금융"
    assert merged.loc[merged["Code"] == "000002", "Sector"].iloc[0] == "바이오/헬스케어"

    price = pd.DataFrame(
        {
            "Code": ["000001", "000002"],
            "Return1D": [1, -1],
            "Return5D": [2, -2],
            "Return20D": [10, -5],
            "Return60D": [20, -10],
            "TradingValue": [1000, 2000],
        }
    )
    summary = summarize_sector_performance(price, merged)
    assert "SectorStrengthScore" in summary.columns


def test_stock_to_sector_comparison_no_mutation():
    stock_price = pd.DataFrame({"Close": list(range(100, 125))})
    sector_price = pd.DataFrame({"Code": ["000001", "000002"], "Return20D": [10, 5], "TradingValue": [1, 2]})
    before = sector_price.copy(deep=True)
    result = compare_stock_to_sector("000001", stock_price, sector_price)
    assert "ExcessReturn20D" in result
    pd.testing.assert_frame_equal(sector_price, before)
