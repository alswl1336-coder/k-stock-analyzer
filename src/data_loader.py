from __future__ import annotations

import datetime as dt

import FinanceDataReader as fdr
import pandas as pd
import streamlit as st


STOCK_LIST_COLUMNS = ["Code", "Name", "Market"]

STATIC_STOCK_FALLBACK = [
    {"Code": "005930", "Name": "삼성전자", "Market": "KOSPI"},
    {"Code": "000660", "Name": "SK하이닉스", "Market": "KOSPI"},
    {"Code": "005380", "Name": "현대차", "Market": "KOSPI"},
    {"Code": "035420", "Name": "NAVER", "Market": "KOSPI"},
    {"Code": "035720", "Name": "카카오", "Market": "KOSPI"},
    {"Code": "051910", "Name": "LG화학", "Market": "KOSPI"},
    {"Code": "006400", "Name": "삼성SDI", "Market": "KOSPI"},
    {"Code": "068270", "Name": "셀트리온", "Market": "KOSPI"},
    {"Code": "086520", "Name": "에코프로", "Market": "KOSDAQ"},
    {"Code": "247540", "Name": "에코프로비엠", "Market": "KOSDAQ"},
]


def _normalize_stock_list(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=STOCK_LIST_COLUMNS)

    result = df.copy()
    result = result.rename(columns={"Symbol": "Code", "Ticker": "Code", "MarketName": "Market"})
    missing = [col for col in STOCK_LIST_COLUMNS if col not in result.columns]
    if missing:
        raise RuntimeError(f"종목 목록 데이터 형식이 예상과 다릅니다: {', '.join(missing)}")

    result["Code"] = result["Code"].astype(str).str.zfill(6)
    return (
        result[STOCK_LIST_COLUMNS]
        .dropna()
        .drop_duplicates("Code")
        .sort_values(["Market", "Name"])
        .reset_index(drop=True)
    )


def _load_stock_list_from_fdr() -> pd.DataFrame:
    kospi = fdr.StockListing("KOSPI")
    kosdaq = fdr.StockListing("KOSDAQ")
    kospi = kospi.copy()
    kosdaq = kosdaq.copy()
    kospi["Market"] = "KOSPI"
    kosdaq["Market"] = "KOSDAQ"
    return _normalize_stock_list(pd.concat([kospi, kosdaq], ignore_index=True))


def _load_stock_list_from_pykrx(base_date: dt.date | None = None) -> pd.DataFrame:
    from pykrx import stock

    base = base_date or dt.date.today()
    rows = []
    for offset in range(14):
        date = (base - dt.timedelta(days=offset)).strftime("%Y%m%d")
        rows.clear()
        for market in ["KOSPI", "KOSDAQ"]:
            try:
                tickers = stock.get_market_ticker_list(date, market=market)
            except Exception:
                tickers = []
            for code in tickers:
                try:
                    name = stock.get_market_ticker_name(code)
                except Exception:
                    name = code
                rows.append({"Code": code, "Name": name or code, "Market": market})
        if rows:
            break
    return _normalize_stock_list(pd.DataFrame(rows))


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def load_stock_list() -> pd.DataFrame:
    errors = []
    try:
        return _load_stock_list_from_fdr()
    except Exception as exc:
        errors.append(f"FinanceDataReader: {type(exc).__name__}: {exc}")

    try:
        result = _load_stock_list_from_pykrx()
        if not result.empty:
            result.attrs["warning"] = "FinanceDataReader 종목 목록 조회가 실패하여 pykrx 종목 목록으로 대체했습니다."
            result.attrs["debug_errors"] = errors
            return result
    except Exception as exc:
        errors.append(f"pykrx: {type(exc).__name__}: {exc}")

    fallback = _normalize_stock_list(pd.DataFrame(STATIC_STOCK_FALLBACK))
    fallback.attrs["warning"] = "종목 목록 조회가 실패하여 최소 내장 목록으로 대체했습니다. 네트워크/KRX 응답 상태를 확인해 주세요."
    fallback.attrs["debug_errors"] = errors
    return fallback


@st.cache_data(ttl=60 * 30, show_spinner=False)
def load_price(code: str, start: str, end: str) -> pd.DataFrame:
    try:
        df = fdr.DataReader(code, start, end)
    except Exception as exc:
        raise RuntimeError(f"가격 데이터를 불러오지 못했습니다. {exc}") from exc

    if df is None or df.empty:
        return pd.DataFrame()

    result = df.reset_index()
    if "Date" not in result.columns:
        result = result.rename(columns={result.columns[0]: "Date"})

    for column in ["Open", "High", "Low", "Close", "Volume"]:
        if column not in result.columns:
            raise RuntimeError(f"가격 데이터에 {column} 컬럼이 없습니다.")

    result["Date"] = pd.to_datetime(result["Date"])
    return result.sort_values("Date").reset_index(drop=True)


def default_date_range() -> tuple[dt.date, dt.date]:
    today = dt.date.today()
    return today - dt.timedelta(days=365 * 2), today
