from __future__ import annotations

import datetime as dt
import hmac

import pandas as pd
import streamlit as st

from src.charts import (
    make_macd_chart,
    make_price_chart,
    make_price_vs_short_balance_chart,
    make_rsi_chart,
    make_shorting_ratio_chart,
    make_shorting_volume_ratio_chart,
    make_volume_chart,
)
from src.config import get_secret, load_project_env
from src.data_loader import default_date_range, load_price, load_stock_list
from src.formatters import format_krw, format_percent
from src.indicators import add_all_indicators
from src.shorting import calculate_shorting_score, load_shorting_data, summarize_shorting_data
from src.watchlist import add_watchlist_item, delete_watchlist_item, load_watchlist


st.set_page_config(page_title="K-Stock Mobile", layout="centered")
load_project_env()


def apply_mobile_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding: 0.65rem 0.75rem 2.5rem;
            max-width: 760px;
        }

        h1 {
            font-size: 1.55rem !important;
            line-height: 1.2 !important;
            margin-bottom: 0.2rem !important;
        }

        h2 {
            font-size: 1.25rem !important;
        }

        h3 {
            font-size: 1.05rem !important;
        }

        p, li, label, div[data-testid="stCaptionContainer"] {
            font-size: 0.88rem !important;
        }

        div[data-testid="stMetric"] {
            border: 1px solid rgba(49, 51, 63, 0.12);
            border-radius: 8px;
            padding: 0.7rem 0.75rem;
            margin-bottom: 0.5rem;
            background: rgba(250, 250, 250, 0.76);
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.22rem !important;
            line-height: 1.22 !important;
            overflow-wrap: anywhere;
        }

        div[data-testid="column"] {
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stPlotlyChart"] {
            overflow-x: auto;
        }

        .stButton button,
        .stDownloadButton button {
            width: 100%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def require_app_password() -> None:
    password = get_secret("APP_PASSWORD")
    if not password:
        return
    if st.session_state.get("mobile_authenticated"):
        return
    st.title("K-Stock Mobile")
    st.caption("접속 비밀번호를 입력해 주세요.")
    entered = st.text_input("비밀번호", type="password")
    if st.button("접속"):
        if hmac.compare_digest(str(entered), str(password)):
            st.session_state["mobile_authenticated"] = True
            st.rerun()
        st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def load_mobile_stocks() -> pd.DataFrame:
    try:
        stocks = load_stock_list()
    except Exception:
        return pd.DataFrame(columns=["Market", "Code", "Name"])
    return stocks[["Market", "Code", "Name"]].copy()


def select_stock(stocks: pd.DataFrame) -> pd.Series | None:
    keyword = st.text_input("종목명 또는 코드", value="삼성전자")
    market = st.selectbox("시장", ["전체", "KOSPI", "KOSDAQ"])
    filtered = stocks.copy()
    if market != "전체":
        filtered = filtered[filtered["Market"] == market]
    if keyword.strip():
        term = keyword.strip()
        filtered = filtered[
            filtered["Name"].str.contains(term, case=False, na=False)
            | filtered["Code"].str.contains(term, case=False, na=False)
        ]
    filtered = filtered.head(30)
    if filtered.empty:
        st.info("검색 결과가 없습니다.")
        return None
    labels = [f"{row.Name} ({row.Code}) [{row.Market}]" for row in filtered.itertuples()]
    selected = st.selectbox("종목 선택", labels)
    return filtered.iloc[labels.index(selected)]


def render_mobile_analysis(stocks: pd.DataFrame) -> None:
    asset = select_stock(stocks)
    if asset is None:
        return

    default_start, default_end = default_date_range()
    with st.expander("기간 설정", expanded=False):
        start_date = st.date_input("시작일", value=default_start)
        end_date = st.date_input("종료일", value=default_end)
    if start_date > end_date:
        st.error("시작일은 종료일보다 늦을 수 없습니다.")
        return

    with st.spinner("데이터를 불러오는 중입니다..."):
        df = load_price(asset["Code"], start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        if df.empty:
            st.warning("선택한 기간에 가격 데이터가 없습니다.")
            return
        df = add_all_indicators(df)

    latest = df.iloc[-1]
    st.subheader(f"{asset['Name']} ({asset['Code']})")
    st.metric("최신 종가", format_krw(latest["Close"]), format_percent(latest.get("RETURN_1D")))
    st.metric("거래량", f"{latest['Volume']:,.0f}주", f"{latest.get('VOLUME_RATIO', 0):.2f}x")
    st.metric("RSI 14", f"{latest.get('RSI14', 0):.2f}")
    st.metric("20일 수익률", format_percent(latest.get("RETURN_20D")))

    memo = st.text_input("관심종목 메모", key="mobile_stock_memo")
    if st.button("관심종목에 추가"):
        added = add_watchlist_item(asset["Code"], asset["Name"], asset["Market"], memo, item_type="Stock")
        st.success("관심종목에 추가했습니다.") if added else st.info("이미 관심종목에 있습니다.")

    st.plotly_chart(make_price_chart(df, asset["Name"]), use_container_width=True, key=f"mobile_price_{asset['Code']}")
    st.plotly_chart(make_volume_chart(df), use_container_width=True, key=f"mobile_volume_{asset['Code']}")

    with st.expander("RSI / MACD", expanded=False):
        st.plotly_chart(make_rsi_chart(df), use_container_width=True, key=f"mobile_rsi_{asset['Code']}")
        st.plotly_chart(make_macd_chart(df), use_container_width=True, key=f"mobile_macd_{asset['Code']}")

    render_mobile_shorting(asset["Code"], asset["Name"], start_date, end_date)

    with st.expander("최근 20거래일", expanded=False):
        st.dataframe(df.tail(20).reset_index(), use_container_width=True, height=360)


def render_mobile_shorting(code: str, name: str, start_date: dt.date, end_date: dt.date) -> None:
    with st.expander("공매도 분석", expanded=False):
        shorting = load_shorting_data(code, start_date, end_date)
        if shorting.empty:
            st.info("공매도 데이터를 불러오지 못했습니다.")
            debug = shorting.attrs.get("debug", {}) if hasattr(shorting, "attrs") else {}
            if debug:
                st.caption(f"{debug.get('exception_type') or ''} {debug.get('exception_message') or ''}".strip())
            return
        summary = summarize_shorting_data(shorting)
        score = calculate_shorting_score(summary)
        st.metric("공매도 위험도 점수", f"{score['score']:.1f}/100")
        st.metric("공매도 위험도 등급", score["grade"])
        st.metric("공매도 비중", format_percent(summary.get("short_volume_ratio_1d")))
        st.metric("20일 평균 공매도 비중", format_percent(summary.get("short_volume_ratio_20d_avg")))
        st.plotly_chart(make_shorting_ratio_chart(shorting, name), use_container_width=True, key=f"mobile_short_ratio_{code}")
        st.plotly_chart(make_price_vs_short_balance_chart(shorting, name), use_container_width=True, key=f"mobile_short_balance_{code}")
        st.plotly_chart(make_shorting_volume_ratio_chart(shorting, name), use_container_width=True, key=f"mobile_short_volume_{code}")


def render_mobile_watchlist() -> None:
    st.subheader("관심종목")
    items = load_watchlist()
    if not items:
        st.info("관심종목이 아직 없습니다.")
        return
    for item in items:
        with st.container(border=True):
            st.markdown(f"**{item.get('name', '')}**")
            st.caption(f"{item.get('type', 'Stock')} | {item.get('code', '')} [{item.get('market', '-')}]")
            if item.get("memo"):
                st.write(item["memo"])
            if st.button("삭제", key=f"mobile_delete_{item.get('type', 'Stock')}_{item.get('code', '')}"):
                delete_watchlist_item(item["code"])
                st.success("삭제했습니다.")
                st.rerun()


def render_mobile_help() -> None:
    st.subheader("도움말")
    st.write("모바일 화면은 핵심 차트와 주요 지표 중심으로 구성했습니다.")
    st.write("전체 기능은 PC용 `app.py` 화면에서 사용할 수 있습니다.")
    st.info("모든 지표는 투자 추천이 아닌 분석 보조 정보입니다.")


def main() -> None:
    apply_mobile_styles()
    require_app_password()
    st.title("K-Stock Mobile")
    st.caption("모바일용 한국 주식 분석 화면")
    menu = st.segmented_control("화면", ["종목 분석", "관심종목", "도움말"], default="종목 분석")
    stocks = load_mobile_stocks()
    if stocks.empty:
        st.warning("종목 목록을 불러오지 못했습니다.")
        return
    if menu == "종목 분석":
        render_mobile_analysis(stocks)
    elif menu == "관심종목":
        render_mobile_watchlist()
    else:
        render_mobile_help()


if __name__ == "__main__":
    main()
