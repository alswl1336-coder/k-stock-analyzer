from __future__ import annotations

import pandas as pd


def calculate_returns_for_sector(price_data: pd.DataFrame) -> pd.DataFrame:
    return price_data.copy()


def summarize_sector_performance(price_data: pd.DataFrame, sector_map: pd.DataFrame) -> pd.DataFrame:
    if price_data.empty or sector_map.empty:
        return pd.DataFrame()
    df = price_data.merge(sector_map[["Code", "Name", "Sector"]], on="Code", how="left")
    df["Sector"] = df["Sector"].fillna("미분류")
    rows = []
    for sector, group in df.groupby("Sector"):
        top = group.sort_values("Return20D", ascending=False).iloc[0]
        bottom = group.sort_values("Return20D", ascending=True).iloc[0]
        up_ratio = (group["Return20D"] > 0).mean() * 100
        score = min(100, max(0, group["Return20D"].mean() * 3 + up_ratio * 0.6))
        rows.append(
            {
                "Sector": sector,
                "StockCount": len(group),
                "UpCount": int((group["Return20D"] > 0).sum()),
                "DownCount": int((group["Return20D"] <= 0).sum()),
                "AvgReturn1D": group["Return1D"].mean(),
                "AvgReturn5D": group["Return5D"].mean(),
                "AvgReturn20D": group["Return20D"].mean(),
                "AvgReturn60D": group["Return60D"].mean(),
                "MedianReturn20D": group["Return20D"].median(),
                "TotalTradingValue": group["TradingValue"].sum(),
                "AvgTradingValue": group["TradingValue"].mean(),
                "TopStockName": top.get("Name", top["Code"]),
                "TopStockReturn20D": top["Return20D"],
                "BottomStockName": bottom.get("Name", bottom["Code"]),
                "BottomStockReturn20D": bottom["Return20D"],
                "SectorStrengthScore": score,
            }
        )
    return pd.DataFrame(rows).sort_values("SectorStrengthScore", ascending=False)


def compare_stock_to_sector(stock_code: str, stock_price_df: pd.DataFrame, sector_price_df: pd.DataFrame) -> dict:
    if stock_price_df.empty or sector_price_df.empty:
        return {}
    stock_return = stock_price_df["Close"].pct_change(20).iloc[-1] * 100
    sector_avg = sector_price_df["Return20D"].mean()
    rank_df = sector_price_df.sort_values("Return20D", ascending=False).reset_index(drop=True)
    rank = int(rank_df.index[rank_df["Code"] == stock_code][0] + 1) if stock_code in rank_df["Code"].values else None
    percentile = (1 - (rank - 1) / len(rank_df)) * 100 if rank else None
    return {"StockReturn20D": stock_return, "SectorAvgReturn20D": sector_avg, "ExcessReturn20D": stock_return - sector_avg, "SectorRank": rank, "SectorPercentile": percentile}


def rank_stocks_within_sector(sector_price_data: pd.DataFrame, sector: str) -> pd.DataFrame:
    if sector_price_data.empty:
        return pd.DataFrame()
    result = sector_price_data.copy().sort_values("Return20D", ascending=False).reset_index(drop=True)
    result["Rank"] = result.index + 1
    return result


def summarize_sector_flow(investor_flow_data: pd.DataFrame, sector_map: pd.DataFrame) -> pd.DataFrame:
    if investor_flow_data.empty:
        return pd.DataFrame()
    return investor_flow_data.copy()
