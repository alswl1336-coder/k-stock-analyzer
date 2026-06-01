from __future__ import annotations

from pathlib import Path

import pandas as pd

from .data_loader import load_price


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_sector_map() -> pd.DataFrame:
    path = DATA_DIR / "sector_map.csv"
    if not path.exists():
        return pd.DataFrame(columns=["Code", "Name", "Market", "Sector", "Industry"])
    return pd.read_csv(path, dtype={"Code": str})


def _infer_sector_from_name(name: str) -> str:
    rules = [
        (["은행", "금융지주", "증권", "보험"], "금융"),
        (["바이오", "제약", "헬스케어"], "바이오/헬스케어"),
        (["반도체", "전자", "하이닉스"], "반도체/IT"),
        (["조선", "중공업"], "조선"),
        (["자동차", "모비스", "타이어"], "자동차"),
        (["건설"], "건설"),
    ]
    for keywords, sector in rules:
        if any(keyword in str(name) for keyword in keywords):
            return sector
    return "미분류"


def infer_sector_from_listing(stock_list_df: pd.DataFrame) -> pd.DataFrame:
    result = stock_list_df.copy()
    result["Sector"] = result.get("Sector", pd.Series(index=result.index, dtype=object)).fillna(result["Name"].map(_infer_sector_from_name))
    result["Industry"] = result.get("Industry", pd.Series(index=result.index, dtype=object)).fillna(result["Sector"])
    return result


def merge_sector_info(stock_list_df: pd.DataFrame, sector_map_df: pd.DataFrame) -> pd.DataFrame:
    listing = infer_sector_from_listing(stock_list_df)
    if sector_map_df.empty:
        return listing
    merged = listing.merge(sector_map_df[["Code", "Sector", "Industry"]], on="Code", how="left", suffixes=("", "_map"))
    merged["Sector"] = merged["Sector_map"].fillna(merged["Sector"]).fillna("미분류")
    merged["Industry"] = merged["Industry_map"].fillna(merged["Industry"]).fillna(merged["Sector"])
    return merged.drop(columns=[col for col in ["Sector_map", "Industry_map"] if col in merged.columns])


def get_stock_sector(code: str, stock_list_df: pd.DataFrame, sector_map_df: pd.DataFrame) -> dict:
    merged = merge_sector_info(stock_list_df, sector_map_df)
    row = merged[merged["Code"].astype(str).str.zfill(6) == str(code).zfill(6)]
    if row.empty:
        return {"Sector": "미분류", "Industry": "미분류"}
    return row.iloc[0][["Sector", "Industry"]].to_dict()


def load_sector_price_data(codes: list[str], start_date: str, end_date: str, max_count: int = 300) -> pd.DataFrame:
    rows = []
    for code in codes[:max_count]:
        try:
            price = load_price(code, start_date, end_date)
            if price.empty:
                continue
            latest = price.iloc[-1]
            rows.append(
                {
                    "Code": code,
                    "Close": latest["Close"],
                    "Return1D": price["Close"].pct_change().iloc[-1] * 100,
                    "Return5D": price["Close"].pct_change(5).iloc[-1] * 100,
                    "Return20D": price["Close"].pct_change(20).iloc[-1] * 100,
                    "Return60D": price["Close"].pct_change(60).iloc[-1] * 100,
                    "TradingValue": latest["Close"] * latest["Volume"],
                }
            )
        except Exception:
            continue
    return pd.DataFrame(rows)
