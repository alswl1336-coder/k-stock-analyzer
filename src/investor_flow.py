from __future__ import annotations

import datetime as dt
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import pandas as pd
import streamlit as st

from .config import ENV_PATH, get_secret_status, load_project_env


load_project_env()


INVESTOR_ALIASES = {
    "외국인": ["외국인합계", "외국인"],
    "기관": ["기관합계", "기관"],
    "개인": ["개인"],
}

INVESTOR_RANKING_NAMES = {
    "외국인": "외국인",
    "기관합계": "기관합계",
    "개인": "개인",
}

FLOW_WARNING = "수급 데이터 기반 정량 지표이며 투자 추천이 아닙니다."

BUY_SELL_COLUMNS = [
    "Date",
    "ForeignBuyValue",
    "ForeignSellValue",
    "ForeignNetValue",
    "InstitutionBuyValue",
    "InstitutionSellValue",
    "InstitutionNetValue",
    "IndividualBuyValue",
    "IndividualSellValue",
    "IndividualNetValue",
    "ForeignBuyVolume",
    "ForeignSellVolume",
    "ForeignNetVolume",
    "InstitutionBuyVolume",
    "InstitutionSellVolume",
    "InstitutionNetVolume",
    "IndividualBuyVolume",
    "IndividualSellVolume",
    "IndividualNetVolume",
    "SmartBuyValue",
    "SmartSellValue",
    "SmartNetValue",
    "SmartBuyVolume",
    "SmartSellVolume",
    "SmartNetVolume",
    "DataMode",
    "DataWarning",
]

INVESTOR_KEYWORDS = {
    "Foreign": ["외국인", "외국인합계"],
    "Institution": ["기관합계", "기관"],
    "Individual": ["개인"],
}

INSTITUTION_DETAIL_COLUMNS = ["금융투자", "보험", "투신", "사모", "은행", "기타금융", "연기금"]


def _import_pykrx_stock():
    try:
        from pykrx import stock
    except Exception as exc:
        raise RuntimeError("pykrx가 설치되어 있지 않습니다. pip install -r requirements.txt를 실행해 주세요.") from exc
    return stock


def _to_yyyymmdd(value: str | dt.date | pd.Timestamp) -> str:
    return pd.to_datetime(value).strftime("%Y%m%d")


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    for alias in aliases:
        if alias in df.columns:
            return alias
    for column in df.columns:
        if any(alias in str(column) for alias in aliases):
            return str(column)
    return None


def _series_for(df: pd.DataFrame, investor: str) -> pd.Series:
    column = _find_column(df, INVESTOR_ALIASES[investor])
    if column is None:
        return pd.Series(0, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(0)


def _normalize_date_index(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result.index = pd.to_datetime(result.index)
    result.index.name = "Date"
    return result.sort_index()


def _pykrx_version() -> str:
    try:
        return version("pykrx")
    except PackageNotFoundError:
        return "unknown"


def _empty_buy_sell_frame(debug: dict | None = None) -> pd.DataFrame:
    result = pd.DataFrame(columns=BUY_SELL_COLUMNS)
    result.attrs["debug"] = debug or {}
    return result


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = [
            " ".join(str(part) for part in column if str(part) and str(part) != "nan").strip()
            for column in result.columns
        ]
    else:
        result.columns = [str(column) for column in result.columns]
    return result


def _frame_with_date(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = _flatten_columns(df.copy())
    result = result.reset_index()
    date_column = next((column for column in result.columns if column in {"Date", "날짜", "일자"}), None)
    if date_column is None and len(result.columns) > 0:
        date_column = result.columns[0]
    result = result.rename(columns={date_column: "Date"})
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    return result.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _find_investor_column(df: pd.DataFrame, investor: str, action: str) -> str | None:
    investor_words = INVESTOR_KEYWORDS[investor]
    action_words = {
        "Buy": ["매수", "buy"],
        "Sell": ["매도", "sell"],
        "Net": ["순매수", "순매매", "순매수금액", "net"],
    }[action]
    for column in df.columns:
        text = str(column).replace(" ", "")
        lowered = text.lower()
        if _contains_any(text, investor_words) and (_contains_any(text, action_words) or _contains_any(lowered, action_words)):
            return column
    return None


def _numeric_column(df: pd.DataFrame, column: str | None) -> pd.Series:
    if column is None:
        return pd.Series(pd.NA, index=df.index, dtype="Float64")
    return pd.to_numeric(df[column].astype(str).str.replace(",", "", regex=False), errors="coerce")


def _fallback_net_series(df: pd.DataFrame, investor: str) -> pd.Series:
    if investor == "Institution":
        columns = [column for column in df.columns if str(column).replace(" ", "") in INSTITUTION_DETAIL_COLUMNS]
        if columns:
            return sum((_numeric_column(df, column).fillna(0) for column in columns), pd.Series(0, index=df.index, dtype="float64"))
    for keyword in INVESTOR_KEYWORDS[investor]:
        for column in df.columns:
            if str(column).replace(" ", "") == keyword:
                return _numeric_column(df, column)
    return pd.Series(pd.NA, index=df.index, dtype="Float64")


def normalize_investor_buy_sell_frames(value_df: pd.DataFrame, volume_df: pd.DataFrame | None = None) -> pd.DataFrame:
    value = _frame_with_date(value_df)
    volume = _frame_with_date(volume_df) if volume_df is not None else pd.DataFrame()
    if value.empty and volume.empty:
        return _empty_buy_sell_frame({"data_mode": "unavailable"})

    dates = value["Date"] if not value.empty else volume["Date"]
    result = pd.DataFrame({"Date": pd.to_datetime(dates).drop_duplicates().sort_values().reset_index(drop=True)})
    result = result.merge(value, on="Date", how="left", suffixes=("", "_ValueRaw")) if not value.empty else result
    value_cols = set(result.columns)
    if not volume.empty:
        result = result.merge(volume, on="Date", how="left", suffixes=("", "_VolumeRaw"))
    working = result.copy()

    buy_sell_available = False
    net_available = False
    output = pd.DataFrame({"Date": working["Date"]})
    for investor in ["Foreign", "Institution", "Individual"]:
        buy_value = _numeric_column(working, _find_investor_column(working, investor, "Buy"))
        sell_value = _numeric_column(working, _find_investor_column(working, investor, "Sell"))
        net_value = _numeric_column(working, _find_investor_column(working, investor, "Net"))
        if not net_value.notna().any():
            net_value = _fallback_net_series(working, investor)
        value_has_buy_sell = buy_value.notna().any() and sell_value.notna().any()
        value_has_net = net_value.notna().any()
        if value_has_buy_sell:
            buy_sell_available = True
            net_value = buy_value.fillna(0) - sell_value.fillna(0)
        elif value_has_net:
            net_available = True
        output[f"{investor}BuyValue"] = buy_value if value_has_buy_sell else pd.NA
        output[f"{investor}SellValue"] = sell_value if value_has_buy_sell else pd.NA
        output[f"{investor}NetValue"] = net_value if value_has_net or value_has_buy_sell else 0

        volume_working = working.drop(columns=[col for col in value_cols if col != "Date"], errors="ignore")
        buy_volume = _numeric_column(volume_working, _find_investor_column(volume_working, investor, "Buy"))
        sell_volume = _numeric_column(volume_working, _find_investor_column(volume_working, investor, "Sell"))
        net_volume = _numeric_column(volume_working, _find_investor_column(volume_working, investor, "Net"))
        if not net_volume.notna().any():
            net_volume = _fallback_net_series(volume_working, investor)
        volume_has_buy_sell = buy_volume.notna().any() and sell_volume.notna().any()
        volume_has_net = net_volume.notna().any()
        if volume_has_buy_sell:
            net_volume = buy_volume.fillna(0) - sell_volume.fillna(0)
        output[f"{investor}BuyVolume"] = buy_volume if volume_has_buy_sell else pd.NA
        output[f"{investor}SellVolume"] = sell_volume if volume_has_buy_sell else pd.NA
        output[f"{investor}NetVolume"] = net_volume if volume_has_net or volume_has_buy_sell else 0

    output["SmartBuyValue"] = output["ForeignBuyValue"] + output["InstitutionBuyValue"]
    output["SmartSellValue"] = output["ForeignSellValue"] + output["InstitutionSellValue"]
    output["SmartNetValue"] = output["ForeignNetValue"].fillna(0) + output["InstitutionNetValue"].fillna(0)
    output["SmartBuyVolume"] = output["ForeignBuyVolume"] + output["InstitutionBuyVolume"]
    output["SmartSellVolume"] = output["ForeignSellVolume"] + output["InstitutionSellVolume"]
    output["SmartNetVolume"] = output["ForeignNetVolume"].fillna(0) + output["InstitutionNetVolume"].fillna(0)
    data_mode = "buy_sell" if buy_sell_available else "net_only" if net_available else "unavailable"
    warning = "" if data_mode == "buy_sell" else "현재 데이터 소스에서 매수/매도 분리 데이터를 제공하지 않아 순매수 기준으로 표시합니다."
    output["DataMode"] = data_mode
    output["DataWarning"] = warning
    for column in BUY_SELL_COLUMNS:
        if column not in output.columns:
            output[column] = pd.NA
    return output[BUY_SELL_COLUMNS].sort_values("Date").reset_index(drop=True)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_investor_buy_sell_by_date(
    ticker: str,
    start_date,
    end_date,
    asset_type: str = "Stock",
    lookback_days: int = 40,
) -> pd.DataFrame:
    load_project_env()
    requested_start = pd.to_datetime(start_date).date()
    requested_end = pd.to_datetime(end_date).date()
    start = min(requested_start, requested_end - dt.timedelta(days=max(lookback_days, 40)))
    end = requested_end
    start_ymd = _to_yyyymmdd(start)
    end_ymd = _to_yyyymmdd(end)
    debug = {
        "ticker": ticker,
        "asset_type": asset_type,
        "start_ymd": start_ymd,
        "end_ymd": end_ymd,
        "pykrx_version": _pykrx_version(),
        "value_raw_shape": None,
        "value_raw_columns": [],
        "volume_raw_shape": None,
        "volume_raw_columns": [],
        "data_mode": "unavailable",
        "exception_type": None,
        "exception_message": None,
        "env_path": str(ENV_PATH),
        "env_exists": ENV_PATH.exists(),
        "has_krx_id": get_secret_status("KRX_ID"),
        "has_krx_pw": get_secret_status("KRX_PW"),
    }
    try:
        stock = _import_pykrx_stock()
        try:
            value_df = stock.get_market_trading_value_by_date(start_ymd, end_ymd, ticker, detail=True)
        except TypeError:
            value_df = stock.get_market_trading_value_by_date(start_ymd, end_ymd, ticker)
        try:
            volume_df = stock.get_market_trading_volume_by_date(start_ymd, end_ymd, ticker, detail=True)
        except TypeError:
            volume_df = stock.get_market_trading_volume_by_date(start_ymd, end_ymd, ticker)
        debug["value_raw_shape"] = value_df.shape if value_df is not None else None
        debug["value_raw_columns"] = [str(column) for column in value_df.columns] if value_df is not None else []
        debug["volume_raw_shape"] = volume_df.shape if volume_df is not None else None
        debug["volume_raw_columns"] = [str(column) for column in volume_df.columns] if volume_df is not None else []
        result = normalize_investor_buy_sell_frames(value_df, volume_df)
        if not result.empty:
            result = result.tail(20).reset_index(drop=True)
        debug["data_mode"] = result["DataMode"].iloc[-1] if not result.empty and "DataMode" in result else "unavailable"
        result.attrs["debug"] = debug
        return result
    except Exception as exc:
        debug["exception_type"] = type(exc).__name__
        debug["exception_message"] = str(exc)
        return _empty_buy_sell_frame(debug)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_investor_trading_by_date(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    start = _to_yyyymmdd(start_date)
    end = _to_yyyymmdd(end_date)

    try:
        stock = _import_pykrx_stock()
        value_df = stock.get_market_trading_value_by_date(start, end, ticker)
        volume_df = stock.get_market_trading_volume_by_date(start, end, ticker)
    except Exception:
        return pd.DataFrame()

    if value_df is None or volume_df is None or value_df.empty or volume_df.empty:
        return pd.DataFrame()

    value_df = _normalize_date_index(value_df)
    volume_df = _normalize_date_index(volume_df)
    common_index = value_df.index.union(volume_df.index)
    value_df = value_df.reindex(common_index).fillna(0)
    volume_df = volume_df.reindex(common_index).fillna(0)

    result = pd.DataFrame({"Date": common_index})
    result["ForeignNetValue"] = _series_for(value_df, "외국인").to_numpy()
    result["InstitutionNetValue"] = _series_for(value_df, "기관").to_numpy()
    result["IndividualNetValue"] = _series_for(value_df, "개인").to_numpy()
    result["ForeignNetVolume"] = _series_for(volume_df, "외국인").to_numpy()
    result["InstitutionNetVolume"] = _series_for(volume_df, "기관").to_numpy()
    result["IndividualNetVolume"] = _series_for(volume_df, "개인").to_numpy()
    result["ForeignCumNetValue"] = result["ForeignNetValue"].cumsum()
    result["InstitutionCumNetValue"] = result["InstitutionNetValue"].cumsum()
    result["SmartMoneyNetValue"] = result["ForeignNetValue"] + result["InstitutionNetValue"]
    result["SmartMoneyNetVolume"] = result["ForeignNetVolume"] + result["InstitutionNetVolume"]
    result["SmartMoneyCumNetValue"] = result["SmartMoneyNetValue"].cumsum()
    return result


def _sum_tail(df: pd.DataFrame, column: str, days: int) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).tail(days).sum())


def _consecutive_positive(series: pd.Series) -> int:
    count = 0
    for value in pd.to_numeric(series, errors="coerce").fillna(0).iloc[::-1]:
        if value > 0:
            count += 1
        else:
            break
    return count


def _turnover(price_df: pd.DataFrame, days: int) -> float:
    if price_df.empty:
        return 0.0
    if "Amount" in price_df.columns:
        amount = pd.to_numeric(price_df["Amount"], errors="coerce").fillna(0)
    else:
        amount = pd.to_numeric(price_df["Close"], errors="coerce").fillna(0) * pd.to_numeric(
            price_df["Volume"], errors="coerce"
        ).fillna(0)
    return float(amount.tail(days).sum())


def summarize_investor_flow(investor_df: pd.DataFrame, price_df: pd.DataFrame) -> dict[str, Any]:
    flows = investor_df.copy()
    prices = price_df.copy()
    smart = flows.get("SmartMoneyNetValue", flows["ForeignNetValue"] + flows["InstitutionNetValue"])

    smart_20 = _sum_tail(flows.assign(SmartMoneyNetValue=smart), "SmartMoneyNetValue", 20)
    smart_60 = _sum_tail(flows.assign(SmartMoneyNetValue=smart), "SmartMoneyNetValue", 60)
    turnover_20 = _turnover(prices, 20)
    turnover_60 = _turnover(prices, 60)

    price_return_20d = 0.0
    if len(prices) > 20:
        base = float(prices["Close"].iloc[-21])
        if base:
            price_return_20d = (float(prices["Close"].iloc[-1]) / base - 1) * 100

    return {
        "foreign_1d": _sum_tail(flows, "ForeignNetValue", 1),
        "foreign_5d": _sum_tail(flows, "ForeignNetValue", 5),
        "foreign_20d": _sum_tail(flows, "ForeignNetValue", 20),
        "foreign_60d": _sum_tail(flows, "ForeignNetValue", 60),
        "institution_1d": _sum_tail(flows, "InstitutionNetValue", 1),
        "institution_5d": _sum_tail(flows, "InstitutionNetValue", 5),
        "institution_20d": _sum_tail(flows, "InstitutionNetValue", 20),
        "institution_60d": _sum_tail(flows, "InstitutionNetValue", 60),
        "smart_5d": _sum_tail(flows.assign(SmartMoneyNetValue=smart), "SmartMoneyNetValue", 5),
        "smart_20d": smart_20,
        "smart_60d": smart_60,
        "foreign_consecutive_days": _consecutive_positive(flows["ForeignNetValue"]),
        "institution_consecutive_days": _consecutive_positive(flows["InstitutionNetValue"]),
        "smart_consecutive_days": _consecutive_positive(smart),
        "flow_strength_20d": (smart_20 / turnover_20 * 100) if turnover_20 else 0.0,
        "flow_strength_60d": (smart_60 / turnover_60 * 100) if turnover_60 else 0.0,
        "price_return_20d": price_return_20d,
    }


def classify_accumulation(summary: dict[str, Any]) -> dict[str, Any]:
    conditions = [
        ("외국인 5일 누적 순매매 양수", summary.get("foreign_5d", 0) > 0, 10),
        ("기관 5일 누적 순매매 양수", summary.get("institution_5d", 0) > 0, 10),
        ("외국인+기관 20일 누적 순매매 양수", summary.get("smart_20d", 0) > 0, 15),
        ("외국인+기관 60일 누적 순매매 양수", summary.get("smart_60d", 0) > 0, 15),
        ("20일 수급 강도 3% 이상", summary.get("flow_strength_20d", 0) >= 3, 15),
        ("60일 수급 강도 5% 이상", summary.get("flow_strength_60d", 0) >= 5, 15),
        ("외국인+기관 연속 순매수 3일 이상", summary.get("smart_consecutive_days", 0) >= 3, 10),
        (
            "최근 20일 주가 수익률 양수와 외국인+기관 순매수",
            summary.get("price_return_20d", 0) > 0 and summary.get("smart_20d", 0) > 0,
            10,
        ),
    ]
    matched = [label for label, ok, _points in conditions if ok]
    score = min(100, sum(points for _label, ok, points in conditions if ok))
    if score >= 80:
        grade = "강함"
    elif score >= 50:
        grade = "보통"
    elif score >= 30:
        grade = "약함"
    else:
        grade = "없음"
    return {"score": score, "grade": grade, "matched_conditions": matched, "warning": FLOW_WARNING}


def _normalize_ranking_columns(df: pd.DataFrame, market: str) -> pd.DataFrame:
    result = df.reset_index().copy()
    rename_map = {
        "티커": "Code",
        "종목코드": "Code",
        "종목명": "Name",
        "매도거래량": "SellVolume",
        "매수거래량": "BuyVolume",
        "순매수거래량": "NetBuyVolume",
        "매도거래대금": "SellValue",
        "매수거래대금": "BuyValue",
        "순매수거래대금": "NetBuyValue",
    }
    result = result.rename(columns=rename_map)
    if "Code" not in result.columns and "index" in result.columns:
        result = result.rename(columns={"index": "Code"})
    if "Name" not in result.columns:
        result["Name"] = ""
    result["Market"] = market
    for column in ["SellVolume", "BuyVolume", "NetBuyVolume", "SellValue", "BuyValue", "NetBuyValue"]:
        if column not in result.columns:
            result[column] = 0
    return result[["Market", "Code", "Name", "SellVolume", "BuyVolume", "NetBuyVolume", "SellValue", "BuyValue", "NetBuyValue"]]


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_net_purchase_ranking(start_date: str, end_date: str, market: str, investor: str) -> pd.DataFrame:
    investor_name = INVESTOR_RANKING_NAMES.get(investor, investor)

    try:
        stock = _import_pykrx_stock()
        df = stock.get_market_net_purchases_of_equities(
            _to_yyyymmdd(start_date),
            _to_yyyymmdd(end_date),
            market,
            investor_name,
        )
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()
    return _normalize_ranking_columns(df, market)
