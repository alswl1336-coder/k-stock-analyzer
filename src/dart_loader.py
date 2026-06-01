from __future__ import annotations

import io
import zipfile
import pandas as pd
import requests
import streamlit as st

from .config import ENV_PATH, PROJECT_ROOT, get_secret, get_secret_status, load_project_env

DATA_DIR = PROJECT_ROOT / "data"


load_project_env()


def get_dart_env_status() -> dict[str, object]:
    load_project_env()
    return {
        "env_path": str(ENV_PATH),
        "env_exists": ENV_PATH.exists(),
        "has_dart_api_key": get_secret_status("DART_API_KEY"),
    }


def get_dart_api_key() -> str | None:
    load_project_env()
    return get_secret("DART_API_KEY")


def parse_amount(value) -> float:
    if value is None:
        return float("nan")
    text = str(value).replace(",", "").strip()
    if text in {"", "-", "nan", "None"}:
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def download_corp_codes(api_key: str) -> pd.DataFrame:
    response = requests.get("https://opendart.fss.or.kr/api/corpCode.xml", params={"crtfc_key": api_key}, timeout=20)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        xml_data = zf.read("CORPCODE.xml")
    df = pd.read_xml(io.BytesIO(xml_data))
    df["stock_code"] = df["stock_code"].fillna("").astype(str).str.zfill(6)
    return df.rename(columns={"corp_code": "CorpCode", "corp_name": "CorpName", "stock_code": "StockCode"})


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def load_corp_code_map(api_key: str, force_refresh: bool = False) -> pd.DataFrame:
    DATA_DIR.mkdir(exist_ok=True)
    cache_path = DATA_DIR / "corp_codes.json"
    if cache_path.exists() and not force_refresh:
        return pd.read_json(cache_path, dtype={"StockCode": str, "CorpCode": str})
    df = download_corp_codes(api_key)
    df.to_json(cache_path, force_ascii=False, orient="records")
    return df


def find_corp_code_by_stock_code(stock_code: str, corp_map: pd.DataFrame) -> str | None:
    if corp_map.empty:
        return None
    target = str(stock_code).zfill(6)
    matched = corp_map[corp_map["StockCode"].astype(str).str.zfill(6) == target]
    if matched.empty:
        return None
    return str(matched.iloc[0]["CorpCode"]).zfill(8)


def fetch_dart_major_accounts(api_key: str, corp_code: str, year: int, report_code: str, fs_div: str = "CFS") -> pd.DataFrame:
    response = requests.get(
        "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
        params={"crtfc_key": api_key, "corp_code": corp_code, "bsns_year": year, "reprt_code": report_code, "fs_div": fs_div},
        timeout=20,
    )
    if response.status_code != 200:
        return pd.DataFrame()
    data = response.json()
    if data.get("status") != "000":
        return pd.DataFrame()
    rows = data.get("list", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return pd.DataFrame(
        {
            "StockCode": df.get("stock_code", ""),
            "CorpCode": corp_code,
            "BusinessYear": year,
            "ReportCode": report_code,
            "ReportName": df.get("reprt_code", report_code),
            "FsDiv": fs_div,
            "FsName": df.get("fs_nm", ""),
            "StatementName": df.get("sj_nm", ""),
            "AccountName": df.get("account_nm", ""),
            "CurrentAmount": df.get("thstrm_amount", pd.Series(dtype=object)).map(parse_amount),
            "PreviousAmount": df.get("frmtrm_amount", pd.Series(dtype=object)).map(parse_amount),
            "PreviousYearAmount": df.get("bfefrmtrm_amount", pd.Series(dtype=object)).map(parse_amount),
            "Currency": df.get("currency", "KRW"),
            "Ord": df.get("ord", ""),
        }
    )


def fetch_dart_financials_for_years(stock_code: str, years: list[int], fs_div: str = "CFS") -> pd.DataFrame:
    api_key = get_dart_api_key()
    if not api_key:
        return pd.DataFrame()
    corp_map = load_corp_code_map(api_key)
    corp_code = find_corp_code_by_stock_code(stock_code, corp_map)
    if not corp_code:
        return pd.DataFrame()
    frames = []
    for year in years:
        annual = fetch_dart_major_accounts(api_key, corp_code, year, "11011", fs_div)
        if annual.empty and fs_div == "CFS":
            annual = fetch_dart_major_accounts(api_key, corp_code, year, "11011", "OFS")
        if not annual.empty:
            frames.append(annual)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_recent_disclosures(api_key: str, corp_code: str, days: int = 365) -> pd.DataFrame:
    end = pd.Timestamp.today()
    start = end - pd.Timedelta(days=days)
    response = requests.get(
        "https://opendart.fss.or.kr/api/list.json",
        params={"crtfc_key": api_key, "corp_code": corp_code, "bgn_de": start.strftime("%Y%m%d"), "end_de": end.strftime("%Y%m%d")},
        timeout=20,
    )
    if response.status_code != 200:
        return pd.DataFrame()
    rows = response.json().get("list", [])
    return pd.DataFrame(rows)
