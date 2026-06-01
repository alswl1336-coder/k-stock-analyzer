from __future__ import annotations

import datetime as dt
import re
from typing import Callable

import FinanceDataReader as fdr
import pandas as pd
import streamlit as st

from .config import ENV_PATH, get_secret_status, load_project_env


load_project_env()


PROVIDER_PREFIXES = {
    "KODEX": "삼성자산운용",
    "TIGER": "미래에셋자산운용",
    "ACE": "한국투자신탁운용",
    "KBSTAR": "KB자산운용",
    "SOL": "신한자산운용",
    "HANARO": "NH-Amundi자산운용",
    "ARIRANG": "한화자산운용",
    "KOSEF": "키움투자자산운용",
    "TIMEFOLIO": "타임폴리오자산운용",
}


def _import_pykrx_stock():
    try:
        from pykrx import stock
    except ImportError as exc:
        raise RuntimeError("pykrx가 설치되어 있지 않습니다. pip install -r requirements.txt를 실행해 주세요.") from exc
    return stock


def to_yyyymmdd(value=None) -> str:
    return pd.to_datetime(value or dt.date.today()).strftime("%Y%m%d")


def _to_yyyymmdd(value=None) -> str:
    return to_yyyymmdd(value)


def make_recent_date_candidates(base_date=None, lookback_days: int = 20) -> list[str]:
    base = pd.to_datetime(base_date or dt.date.today()).date()
    return [to_yyyymmdd(base - dt.timedelta(days=offset)) for offset in range(max(1, lookback_days))]


def get_krx_env_status() -> dict[str, object]:
    load_project_env()
    return {
        "env_path": str(ENV_PATH),
        "env_exists": ENV_PATH.exists(),
        "has_krx_id": get_secret_status("KRX_ID"),
        "has_krx_pw": get_secret_status("KRX_PW"),
    }


def has_krx_credentials() -> bool:
    status = get_krx_env_status()
    return bool(status["has_krx_id"] and status["has_krx_pw"])


def infer_etf_provider(name: str) -> str:
    upper_name = str(name).upper()
    for prefix, provider in PROVIDER_PREFIXES.items():
        if upper_name.startswith(prefix):
            return provider
    return "기타"


def infer_etf_category(name: str) -> str:
    upper_name = str(name).upper()
    if any(keyword in upper_name for keyword in ["200", "코스피", "KOSPI", "코스닥", "KOSDAQ"]):
        return "국내지수"
    if any(keyword in upper_name for keyword in ["미국", "S&P", "나스닥", "NASDAQ", "다우", "글로벌"]):
        return "해외주식"
    if any(keyword in upper_name for keyword in ["채권", "국고채", "회사채", "단기채", "머니마켓", "CD", "KOFR"]):
        return "채권/금리"
    if any(keyword in upper_name for keyword in ["배당", "고배당", "커버드콜"]):
        return "배당/인컴"
    if any(keyword in upper_name for keyword in ["반도체", "2차전지", "바이오", "AI", "로봇", "방산", "조선", "자동차"]):
        return "테마/섹터"
    if any(keyword in upper_name for keyword in ["금", "은", "원유", "구리", "농산물", "원자재"]):
        return "원자재"
    return "기타"


def infer_etf_flags(name: str) -> dict[str, bool]:
    upper_name = str(name).upper()
    return {
        "IsLeveraged": any(keyword in upper_name for keyword in ["레버리지", "2X", "2배"]),
        "IsInverse": any(keyword in upper_name for keyword in ["인버스", "곱버스", "-1X", "-2X"]),
        "IsHedged": bool(re.search(r"\(H\)|\bH\b|환헤지|헤지", upper_name)),
        "IsSynthetic": "합성" in upper_name,
    }


def classify_etf_name(name: str) -> dict[str, object]:
    return {
        "AssetType": "ETF",
        "Category": infer_etf_category(name),
        "Provider": infer_etf_provider(name),
        "MarketType": "ETF",
        **infer_etf_flags(name),
    }


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def load_etf_list(base_date: str | None = None) -> pd.DataFrame:
    stock = _import_pykrx_stock()
    dates = make_recent_date_candidates(base_date, lookback_days=370)
    last_error: Exception | None = None
    for date in dates:
        try:
            tickers = stock.get_etf_ticker_list(date)
            if tickers:
                rows = []
                for ticker in tickers:
                    name = stock.get_etf_ticker_name(ticker)
                    rows.append({"Code": ticker, "Name": name, **classify_etf_name(name)})
                return pd.DataFrame(rows)
        except Exception as exc:
            last_error = exc

    try:
        fallback = fdr.StockListing("ETF/KR").rename(columns={"Symbol": "Code"})
        rows = []
        for row in fallback.itertuples():
            code = getattr(row, "Code", "")
            name = getattr(row, "Name", "")
            if code and name:
                rows.append({"Code": code, "Name": name, **classify_etf_name(name)})
        if rows:
            return pd.DataFrame(rows)
    except Exception as exc:
        last_error = exc
    raise RuntimeError(f"ETF 목록을 불러오지 못했습니다: {last_error}")


def _rename_known_columns(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    return df.copy().rename(columns={key: value for key, value in mapping.items() if key in df.columns})


def normalize_etf_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy().reset_index()
    result = _rename_known_columns(
        result,
        {
            "날짜": "Date",
            "시가": "Open",
            "고가": "High",
            "저가": "Low",
            "종가": "Close",
            "거래량": "Volume",
            "거래대금": "TradingValue",
            "기초지수": "UnderlyingIndex",
        },
    )
    if "Date" not in result.columns:
        result = result.rename(columns={result.columns[0]: "Date"})
    for column in ["NAV", "Open", "High", "Low", "Close", "Volume", "TradingValue", "UnderlyingIndex"]:
        if column not in result.columns:
            result[column] = pd.NA
    result["Date"] = pd.to_datetime(result["Date"])
    for column in ["NAV", "Open", "High", "Low", "Close", "Volume", "TradingValue", "UnderlyingIndex"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result[["Date", "NAV", "Open", "High", "Low", "Close", "Volume", "TradingValue", "UnderlyingIndex"]].sort_values(
        "Date"
    )


def _find_available_etf_ohlcv(stock, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    start = pd.to_datetime(start_date).date()
    end = pd.to_datetime(end_date).date()
    span = min(max((end - start).days, 180), 900)
    attempts = [(start, end)]
    for offset in range(0, 370, 60):
        probe_end = end - dt.timedelta(days=offset)
        attempts.append((probe_end - dt.timedelta(days=span), probe_end))
    for probe_start, probe_end in attempts:
        try:
            raw = stock.get_etf_ohlcv_by_date(to_yyyymmdd(probe_start), to_yyyymmdd(probe_end), ticker)
        except Exception:
            continue
        result = normalize_etf_ohlcv(raw)
        if not result.empty:
            return result
    return pd.DataFrame()


def _load_fdr_etf_ohlcv(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    try:
        df = fdr.DataReader(ticker, start_date, end_date)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy().reset_index()
    if "Date" not in result.columns:
        result = result.rename(columns={result.columns[0]: "Date"})
    result["Date"] = pd.to_datetime(result["Date"])
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        if column not in result.columns:
            return pd.DataFrame()
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["NAV"] = result["Close"]
    result["TradingValue"] = result["Close"] * result["Volume"]
    result["UnderlyingIndex"] = pd.NA
    return result[["Date", "NAV", "Open", "High", "Low", "Close", "Volume", "TradingValue", "UnderlyingIndex"]].sort_values(
        "Date"
    )


@st.cache_data(ttl=60 * 30, show_spinner=False)
def load_etf_ohlcv(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    stock = _import_pykrx_stock()
    result = _find_available_etf_ohlcv(stock, ticker, start_date, end_date)
    if result.empty:
        result = _load_fdr_etf_ohlcv(ticker, start_date, end_date)
    if result.empty:
        raise RuntimeError("선택한 기간과 최근 거래일 범위에서 ETF 가격/NAV 데이터를 찾지 못했습니다.")
    return result


def _load_optional_timed_df(func: Callable, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    try:
        df = func(to_yyyymmdd(start_date), to_yyyymmdd(end_date), ticker)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy().reset_index()
    if "Date" not in result.columns:
        result = result.rename(columns={result.columns[0]: "Date"})
    result["Date"] = pd.to_datetime(result["Date"])
    return result.sort_values("Date")


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_etf_price_deviation(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    stock = _import_pykrx_stock()
    func = getattr(stock, "get_etf_price_deviation", None)
    if func is None:
        return pd.DataFrame()
    result = _load_optional_timed_df(func, ticker, start_date, end_date)
    result = _rename_known_columns(result, {"종가": "Close", "괴리율": "DeviationRate", "괴리율(%)": "DeviationRate"})
    for column in ["Close", "NAV", "DeviationRate"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_etf_tracking_error(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    stock = _import_pykrx_stock()
    func = getattr(stock, "get_etf_tracking_error", None)
    if func is None:
        return pd.DataFrame()
    result = _load_optional_timed_df(func, ticker, start_date, end_date)
    result = _rename_known_columns(
        result,
        {"지수": "IndexValue", "추적오차율": "TrackingErrorRate", "추적오차율(%)": "TrackingErrorRate"},
    )
    for column in ["IndexValue", "TrackingErrorRate"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def lookup_component_name(code: str) -> str:
    normalized = str(code).strip()
    if normalized.upper() in {"KRD010010001", "CASH", "CASH00000001"} or "현금" in normalized:
        return "원화현금"
    if re.fullmatch(r"\d{6}", normalized):
        try:
            stock = _import_pykrx_stock()
            name = stock.get_market_ticker_name(normalized)
            return name or normalized
        except Exception:
            return normalized
    return normalized


def _component_name_for_code(code: str) -> str:
    normalized = str(code).strip()
    if normalized.upper() in {"KRD010010001", "CASH", "CASH00000001"} or "현금" in normalized:
        return "원화현금"
    return lookup_component_name(normalized)


def normalize_etf_portfolio(raw_df: pd.DataFrame, base_date: str) -> pd.DataFrame:
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(
            columns=[
                "BaseDate",
                "ComponentCode",
                "ComponentName",
                "ContractCount",
                "Amount",
                "Weight",
                "IsDomesticStock",
            ]
        )

    result = raw_df.copy().reset_index()
    result = _rename_known_columns(
        result,
        {
            "index": "ComponentCode",
            "티커": "ComponentCode",
            "종목코드": "ComponentCode",
            "종목명": "ComponentName",
            "계약수": "ContractCount",
            "금액": "Amount",
            "비중": "Weight",
        },
    )
    if "ComponentCode" not in result.columns:
        result = result.rename(columns={result.columns[0]: "ComponentCode"})

    for column in ["ContractCount", "Amount", "Weight"]:
        if column not in result.columns:
            result[column] = pd.NA
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)

    result["BaseDate"] = to_yyyymmdd(base_date)
    result["ComponentCode"] = result["ComponentCode"].astype(str).str.strip()
    result["IsDomesticStock"] = result["ComponentCode"].str.fullmatch(r"\d{6}")
    if "ComponentName" not in result.columns:
        result["ComponentName"] = result["ComponentCode"].map(_component_name_for_code)
    else:
        result["ComponentName"] = result["ComponentName"].fillna("")
        missing_name = result["ComponentName"].astype(str).str.strip() == ""
        result.loc[missing_name, "ComponentName"] = result.loc[missing_name, "ComponentCode"].map(_component_name_for_code)

    if (result["Weight"].fillna(0) == 0).all() and result["Amount"].sum() > 0:
        result["Weight"] = result["Amount"] / result["Amount"].sum() * 100

    return result[
        [
            "BaseDate",
            "ComponentCode",
            "ComponentName",
            "ContractCount",
            "Amount",
            "Weight",
            "IsDomesticStock",
        ]
    ]


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_etf_portfolio(ticker: str, base_date=None, lookback_days: int = 20) -> pd.DataFrame:
    env_status = get_krx_env_status()
    attempted_dates = make_recent_date_candidates(base_date, lookback_days)
    errors: list[str] = []
    raw_shape = None
    raw_columns: list[str] = []
    exception_type = None
    exception_message = None

    if not (env_status["has_krx_id"] and env_status["has_krx_pw"]):
        empty = normalize_etf_portfolio(pd.DataFrame(), attempted_dates[0] if attempted_dates else to_yyyymmdd(base_date))
        empty.attrs["debug"] = {
            "ticker": ticker,
            "attempted_dates": attempted_dates,
            "errors": [],
            "raw_shape": raw_shape,
            "raw_columns": raw_columns,
            "disabled_reason": "missing_krx_credentials",
            "exception_type": "MissingKrxCredentials",
            "exception_message": "ETF PDF 구성종목 조회에는 KRX 로그인이 필요합니다. .env에 KRX_ID, KRX_PW를 설정해 주세요.",
            **env_status,
        }
        return empty

    stock = _import_pykrx_stock()

    for candidate in attempted_dates:
        try:
            raw = stock.get_etf_portfolio_deposit_file(ticker, candidate)
            raw_shape = raw.shape if raw is not None else None
            raw_columns = [str(column) for column in raw.columns] if raw is not None else []
        except Exception as exc:
            exception_type = type(exc).__name__
            exception_message = str(exc)
            errors.append(f"{candidate}: {exc}")
            continue
        normalized = normalize_etf_portfolio(raw, candidate)
        if not normalized.empty:
            normalized.attrs["debug"] = {
                "ticker": ticker,
                "attempted_dates": attempted_dates,
                "errors": errors,
                "raw_shape": raw_shape,
                "raw_columns": raw_columns,
                "disabled_reason": None,
                "exception_type": exception_type,
                "exception_message": exception_message,
                **env_status,
            }
            return normalized
        if raw is None or raw.empty:
            errors.append(f"{candidate}: empty DataFrame")
        else:
            errors.append(f"{candidate}: normalized portfolio is empty")

    empty = normalize_etf_portfolio(pd.DataFrame(), attempted_dates[0] if attempted_dates else to_yyyymmdd(base_date))
    empty.attrs["debug"] = {
        "ticker": ticker,
        "attempted_dates": attempted_dates,
        "errors": errors,
        "raw_shape": raw_shape,
        "raw_columns": raw_columns,
        "disabled_reason": None,
        "exception_type": exception_type,
        "exception_message": exception_message,
        **env_status,
    }
    return empty


def _normalize_etf_flow(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy().reset_index()
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = [
            " ".join(str(part) for part in column if str(part) and str(part) != "nan").strip()
            for column in result.columns
        ]
    else:
        result.columns = [str(column) for column in result.columns]

    date_column = next(
        (
            column
            for column in result.columns
            if column == "Date" or column in {"날짜", "일자"} or column.lower().startswith("date")
        ),
        None,
    )
    if date_column is None and len(result.columns) > 0:
        first_column = result.columns[0]
        parsed = pd.to_datetime(result[first_column], errors="coerce")
        if parsed.notna().any():
            date_column = first_column
    if date_column is None:
        return pd.DataFrame()

    result = result.rename(columns={date_column: "Date"})
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    result = result.dropna(subset=["Date"])
    if result.empty:
        return pd.DataFrame()
    aliases = {
        "InstitutionNetValue": ["기관합계", "기관", "금액 기관합계", "순매수 기관합계"],
        "IndividualNetValue": ["개인", "금액 개인", "순매수 개인"],
        "ForeignNetValue": ["외국인합계", "외국인", "금액 외국인합계", "순매수 외국인합계"],
    }
    normalized = pd.DataFrame({"Date": result["Date"]})
    for target, names in aliases.items():
        column = next(
            (
                column
                for column in result.columns
                if column in names or any(name in column for name in names)
            ),
            None,
        )
        normalized[target] = pd.to_numeric(result[column], errors="coerce").fillna(0) if column else 0
    normalized["InstitutionNetVolume"] = 0
    normalized["IndividualNetVolume"] = 0
    normalized["ForeignNetVolume"] = 0
    normalized["SmartMoneyNetValue"] = normalized["InstitutionNetValue"] + normalized["ForeignNetValue"]
    normalized["SmartMoneyCumNetValue"] = normalized["SmartMoneyNetValue"].cumsum()
    return normalized.sort_values("Date")


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_etf_investor_flow(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    stock = _import_pykrx_stock()
    func = getattr(stock, "get_etf_trading_volume_and_value", None) or getattr(
        stock,
        "get_etf_trading_volumne_and_value",
        None,
    )
    if func is None:
        return pd.DataFrame()
    try:
        df = func(to_yyyymmdd(start_date), to_yyyymmdd(end_date), ticker)
    except Exception:
        return pd.DataFrame()
    try:
        return _normalize_etf_flow(df)
    except Exception:
        return pd.DataFrame()
