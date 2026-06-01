from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

from .config import ENV_PATH, get_secret, get_secret_status, load_project_env
from .news_analysis import normalize_news_items


load_project_env()


def get_naver_env_status() -> dict[str, object]:
    load_project_env()
    return {
        "env_path": str(ENV_PATH),
        "env_exists": ENV_PATH.exists(),
        "has_naver_client_id": get_secret_status("NAVER_CLIENT_ID"),
        "has_naver_client_secret": get_secret_status("NAVER_CLIENT_SECRET"),
    }


def get_naver_credentials() -> tuple[str | None, str | None]:
    load_project_env()
    return get_secret("NAVER_CLIENT_ID"), get_secret("NAVER_CLIENT_SECRET")


def build_stock_news_query(name: str, code: str | None = None, sector: str | None = None) -> str:
    parts = [name]
    if code:
        parts.append(code)
    if sector:
        parts.append(sector)
    return " ".join(parts)


def build_etf_news_query(name: str, category: str | None = None) -> str:
    return f"{name} ETF {category or ''}".strip()


@st.cache_data(ttl=60 * 10, show_spinner=False)
def search_naver_news(query: str, display: int = 20, start: int = 1, sort: str = "date") -> tuple[pd.DataFrame, str | None]:
    client_id, client_secret = get_naver_credentials()
    if not client_id or not client_secret:
        return pd.DataFrame(), "뉴스 API 키가 설정되지 않았습니다."
    display = max(1, min(int(display), 100))
    sort = sort if sort in {"date", "sim"} else "date"
    try:
        response = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            params={"query": query, "display": display, "start": start, "sort": sort},
            headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
            timeout=10,
        )
    except requests.RequestException as exc:
        return pd.DataFrame(), f"?댁뒪 API ?몄텧 ?ㅽ뙣: {exc}"
    if response.status_code != 200:
        return pd.DataFrame(), f"?댁뒪 API ?묐떟 ?ㅻ쪟: {response.status_code}"
    items = response.json().get("items", [])
    return normalize_news_items(items, query), None
