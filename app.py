from __future__ import annotations

import datetime as dt
import hmac

import pandas as pd
import streamlit as st

from src.config import get_app_config, get_secret, load_project_env


load_project_env()

from src.charts import (
    make_etf_flow_chart,
    make_foreign_institution_net_compare_chart,
    make_etf_index_comparison_chart,
    make_etf_nav_deviation_chart,
    make_etf_portfolio_chart,
    make_etf_price_chart,
    make_etf_tracking_error_chart,
    make_investor_buy_sell_value_chart,
    make_investor_cumulative_chart,
    make_investor_net_value_chart,
    make_macd_chart,
    make_price_chart,
    make_price_vs_flow_chart,
    make_rsi_chart,
    make_price_vs_short_balance_chart,
    make_shorting_ratio_chart,
    make_shorting_volume_ratio_chart,
    make_smart_money_net_chart,
    make_volume_chart,
)
from src.data_loader import default_date_range, load_price, load_stock_list
from src.etf_analysis import classify_etf_risk, summarize_etf
from src.etf_loader import (
    load_etf_investor_flow,
    load_etf_list,
    load_etf_ohlcv,
    load_etf_portfolio,
    load_etf_price_deviation,
    load_etf_tracking_error,
)
from src.formatters import format_krw, format_krw_eok, format_percent, format_signed_krw_eok
from src.indicators import add_all_indicators
from src.investor_flow import (
    FLOW_WARNING,
    classify_accumulation,
    load_investor_buy_sell_by_date,
    load_investor_trading_by_date,
    load_net_purchase_ranking,
    summarize_investor_flow,
)
from src.screener import CONDITION_LABELS, scan_one_stock
from src.watchlist import add_watchlist_item, delete_watchlist_item, load_watchlist, update_watchlist_memo, update_watchlist_score
from src.dart_loader import fetch_dart_financials_for_years, get_dart_api_key, get_dart_env_status
from src.financial_analysis import classify_earnings_trend, load_latest_fundamental, summarize_latest_financials
from src.news_analysis import enrich_news, make_news_timeline, summarize_news
from src.news_loader import (
    build_etf_news_query,
    build_stock_news_query,
    get_naver_credentials,
    get_naver_env_status,
    search_naver_news,
)
from src.scoring import DISCLAIMER, calculate_etf_score, calculate_stock_score
from src.shorting import calculate_shorting_score, load_shorting_data, summarize_shorting_data
from src.sector_analysis import compare_stock_to_sector, summarize_sector_performance
from src.sector_loader import get_stock_sector, load_sector_map, load_sector_price_data, merge_sector_info


st.set_page_config(page_title="K-Stock Analyzer", layout="wide")


ETF_CONDITION_LABELS = {
    "etf_return_20d_5": "20일 수익률 5% 이상",
    "etf_return_60d_10": "60일 수익률 10% 이상",
    "etf_value_ratio_2": "거래대금 20일 평균 대비 2배 이상",
    "etf_avg_value_1b": "20일 평균 거래대금 10억원 이상",
    "exclude_leveraged": "레버리지 ETF 제외",
    "exclude_inverse": "인버스 ETF 제외",
    "exclude_synthetic": "합성 ETF 제외",
}

SCORE_CONDITION_LABELS = {
    "score_80": "종합점수 80점 이상",
    "score_65": "종합점수 65점 이상",
    "score_50": "종합점수 50점 이상",
    "grade_good": "등급 양호 이상",
    "no_warning": "주의 요인 없는 종목/ETF",
}

SHORTING_CONDITIONS = {
    "short_ratio_low_5",
    "short_ratio_high_10",
    "short_balance_down",
    "short_balance_up",
    "short_score_80",
    "short_score_40",
}


def render_score_settings(prefix: str, asset_type: str) -> dict:
    with st.sidebar.expander("종합점수 설정", expanded=False):
        normalize_missing = st.checkbox("데이터 없는 항목 가중치 재조정", value=True, key=f"{prefix}_score_normalize")
        include_news = st.checkbox("뉴스 점수 포함", value=True, key=f"{prefix}_score_news")
        include_flow = st.checkbox("수급 점수 포함", value=True, key=f"{prefix}_score_flow")
        include_financials = True
        include_sector = True
        include_structure = True
        if asset_type == "Stock":
            include_financials = st.checkbox("실적 점수 포함", value=True, key=f"{prefix}_score_financials")
            include_sector = st.checkbox("섹터 점수 포함", value=True, key=f"{prefix}_score_sector")
            include_shorting = st.checkbox("공매도 점수 포함", value=True, key=f"{prefix}_score_shorting")
        else:
            include_structure = st.checkbox("ETF 상품구조 점수 포함", value=True, key=f"{prefix}_score_structure")
            include_shorting = False
    return {
        "normalize_missing": normalize_missing,
        "include_news": include_news,
        "include_flow": include_flow,
        "include_financials": include_financials,
        "include_sector": include_sector,
        "include_structure": include_structure,
        "include_shorting": include_shorting,
    }


def render_deploy_status() -> None:
    config = get_app_config()
    with st.sidebar.expander("배포 상태 / 시스템 체크", expanded=False):
        st.write(
            {
                "APP_ENV": config["app_env"],
                "cloud_environment": config["is_cloud_environment"],
                "debug_mode": config["debug_mode"],
                "env_exists": config["env_exists"],
                "env_path": config["env_path"],
            }
        )
        st.markdown("**Secrets 설정 여부**")
        st.write(config["secrets"])
        st.caption("API 키와 비밀번호 값은 표시하지 않고 설정 여부만 보여줍니다.")


def require_app_password() -> None:
    password = get_secret("APP_PASSWORD")
    if not password:
        st.sidebar.warning("APP_PASSWORD가 설정되지 않았습니다. 외부 공개 전 비밀번호 설정을 권장합니다.")
        return
    if st.session_state.get("app_authenticated"):
        return

    st.title("K-Stock Analyzer")
    st.caption("접속 비밀번호를 입력해 주세요.")
    entered = st.text_input("비밀번호", type="password")
    if st.button("접속"):
        if hmac.compare_digest(str(entered), str(password)):
            st.session_state["app_authenticated"] = True
            st.rerun()
        st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


def render_composite_score(score: dict) -> None:
    st.markdown("### 종합 분석 점수")
    if score.get("total_score") is None:
        st.warning("종합점수를 계산하지 못했습니다.")
        with st.expander("점수 산정 근거 보기"):
            st.write(score)
        return
    positives = score.get("positive_factors", [])[:3] or ["데이터 없음"]
    negatives = score.get("negative_factors", [])[:3] or ["주요 주의 요인 없음"]
    cols = st.columns(4)
    cols[0].metric("종합점수", f"{score['total_score']:.1f}/100")
    cols[1].metric("등급", score.get("grade", "-"))
    cols[2].metric("가장 큰 긍정 요인", positives[0])
    cols[3].metric("주요 주의 요인", negatives[0])
    st.caption(DISCLAIMER)

    sub_scores = score.get("sub_scores", {})
    if sub_scores:
        chart_df = pd.DataFrame(
            [{"항목": key, "점수": value} for key, value in sub_scores.items()]
        )
        st.bar_chart(chart_df.set_index("항목")["점수"])
    with st.expander("점수 산정 근거 보기"):
        st.markdown("**항목별 점수**")
        st.dataframe(pd.DataFrame([sub_scores]).T.rename(columns={0: "점수"}), use_container_width=True)
        st.markdown("**긍정 요인**")
        st.write(score.get("positive_factors", []))
        st.markdown("**주의 요인**")
        st.write(score.get("negative_factors", []))
        st.markdown("**안내**")
        st.write(score.get("warnings", []))


def build_price_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    latest = df.iloc[-1]
    return {
        "close": latest.get("Close"),
        "ma20": latest.get("MA20"),
        "ma60": latest.get("MA60"),
        "ma120": latest.get("MA120"),
        "rsi": latest.get("RSI14"),
        "macd": latest.get("MACD"),
        "return_5d": latest.get("RETURN_5D"),
        "return_20d": latest.get("RETURN_20D"),
        "return_60d": latest.get("RETURN_60D"),
        "volume_ratio_20d": latest.get("VOLUME_RATIO"),
        "high_52w": pd.to_numeric(df["Close"], errors="coerce").tail(252).max() if "Close" in df else pd.NA,
        "low_52w": pd.to_numeric(df["Close"], errors="coerce").tail(252).min() if "Close" in df else pd.NA,
    }


def build_etf_score_summary(price: pd.DataFrame, summary: dict, risk: dict, asset: pd.Series, portfolio: pd.DataFrame) -> dict:
    latest = price.iloc[-1] if not price.empty else {}
    result = {
        **summary,
        "ma20": latest.get("MA20") if hasattr(latest, "get") else pd.NA,
        "ma60": latest.get("MA60") if hasattr(latest, "get") else pd.NA,
        "ma120": latest.get("MA120") if hasattr(latest, "get") else pd.NA,
        "liquidity_grade": risk.get("LiquidityGrade"),
        "deviation_grade": risk.get("DeviationGrade"),
        "tracking_grade": risk.get("TrackingGrade"),
        "is_leveraged": bool(asset.get("IsLeveraged", False)),
        "is_inverse": bool(asset.get("IsInverse", False)),
        "is_synthetic": bool(asset.get("IsSynthetic", False)),
        "is_hedged": bool(asset.get("IsHedged", False)),
    }
    if not portfolio.empty and "Weight" in portfolio.columns:
        result["top10_weight"] = pd.to_numeric(portfolio["Weight"], errors="coerce").fillna(0).head(10).sum()
    return result


def score_conditions_match(score: dict, selected: list[str]) -> tuple[bool, list[str]]:
    if not selected:
        return True, []
    value = score.get("total_score")
    if value is None:
        return False, []
    grade = score.get("grade", "")
    negatives = score.get("negative_factors", [])
    labels = []
    if "score_80" in selected and value >= 80:
        labels.append(SCORE_CONDITION_LABELS["score_80"])
    if "score_65" in selected and value >= 65:
        labels.append(SCORE_CONDITION_LABELS["score_65"])
    if "score_50" in selected and value >= 50:
        labels.append(SCORE_CONDITION_LABELS["score_50"])
    if "grade_good" in selected and grade in {"매우 양호", "양호"}:
        labels.append(SCORE_CONDITION_LABELS["grade_good"])
    if "no_warning" in selected and not negatives:
        labels.append(SCORE_CONDITION_LABELS["no_warning"])
    return bool(labels), labels


def shorting_conditions_match(summary: dict, score: dict, selected: list[str]) -> tuple[bool, list[str]]:
    selected_shorting = [condition for condition in selected if condition in SHORTING_CONDITIONS]
    if not selected_shorting:
        return True, []
    labels = []
    ratio = summary.get("short_volume_ratio_1d")
    balance_change = summary.get("short_balance_change_rate")
    score_value = score.get("score")
    if "short_ratio_low_5" in selected_shorting and pd.notna(ratio) and ratio <= 5:
        labels.append(CONDITION_LABELS["short_ratio_low_5"])
    if "short_ratio_high_10" in selected_shorting and pd.notna(ratio) and ratio >= 10:
        labels.append(CONDITION_LABELS["short_ratio_high_10"])
    if "short_balance_down" in selected_shorting and pd.notna(balance_change) and balance_change < 0:
        labels.append(CONDITION_LABELS["short_balance_down"])
    if "short_balance_up" in selected_shorting and pd.notna(balance_change) and balance_change > 0:
        labels.append(CONDITION_LABELS["short_balance_up"])
    if "short_score_80" in selected_shorting and score_value is not None and score_value >= 80:
        labels.append(CONDITION_LABELS["short_score_80"])
    if "short_score_40" in selected_shorting and score_value is not None and score_value <= 40:
        labels.append(CONDITION_LABELS["short_score_40"])
    return bool(labels), labels


def calculate_watchlist_score(item: dict) -> dict:
    end = dt.date.today()
    start = end - dt.timedelta(days=420)
    if item.get("type", "Stock") == "ETF":
        price, deviation, tracking, portfolio, flow = load_etf_bundle(item["code"], start, end)
        price = add_all_indicators(price.rename(columns={"TradingValue": "Amount"})).rename(columns={"Amount": "TradingValue"})
        summary = summarize_etf(price, deviation, tracking, flow, portfolio)
        pseudo_asset = pd.Series(
            {
                "IsLeveraged": False,
                "IsInverse": False,
                "IsSynthetic": False,
                "IsHedged": False,
                "Category": item.get("category", ""),
            }
        )
        risk = classify_etf_risk(pseudo_asset.to_dict(), price, deviation, tracking)
        return calculate_etf_score(etf_summary=build_etf_score_summary(price, summary, risk, pseudo_asset, portfolio))
    df = add_all_indicators(load_price(item["code"], start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))
    shorting_df = load_shorting_data(item["code"], start, end)
    shorting_summary = summarize_shorting_data(shorting_df) if not shorting_df.empty else {}
    shorting_score = calculate_shorting_score(shorting_summary) if shorting_summary else {}
    return calculate_stock_score(
        price_summary=build_price_summary(df),
        shorting_summary={
            **shorting_summary,
            "shorting_score": shorting_score.get("score"),
            "shorting_grade": shorting_score.get("grade"),
        } if shorting_score else {},
    )


def render_investor_buy_sell_detail(
    code: str,
    start_date: dt.date,
    end_date: dt.date,
    asset_type: str = "Stock",
    key_prefix: str = "flow_detail",
) -> None:
    st.subheader("최근 20거래일 외국인/기관 매수/매도 상세")
    st.caption(
        "아래 표는 최근 20거래일 기준 외국인과 기관의 일별 매수금액, 매도금액, 순매수금액을 분리해 보여줍니다. "
        "데이터 제공 방식에 따라 순매수만 제공될 수 있습니다."
    )
    widget_base = f"{key_prefix}_{asset_type}_{code}"
    period = st.selectbox("기간 선택", [5, 10, 20, 60], index=2, format_func=lambda value: f"최근 {value}거래일", key=f"{widget_base}_period")
    display_basis = st.selectbox("표시 기준", ["거래대금", "거래량", "거래대금+거래량"], key=f"{widget_base}_basis")
    include_individual = st.checkbox("개인 포함", value=False, key=f"{widget_base}_individual")
    unit = st.selectbox("단위", ["억원", "원"], key=f"{widget_base}_unit")
    emphasize_net = st.checkbox("순매수 강조", value=True, key=f"{widget_base}_emphasis")

    detail = load_investor_buy_sell_by_date(code, start_date, end_date, asset_type=asset_type, lookback_days=max(period * 2, 40))
    debug = detail.attrs.get("debug", {}) if hasattr(detail, "attrs") else {}
    if detail.empty:
        st.info("선택한 기간의 외국인/기관 매수/매도 상세 데이터를 불러오지 못했습니다.")
        with st.expander("개발용 조회 정보"):
            st.write({key: value for key, value in debug.items() if value is not None})
        return

    detail = detail.tail(period).copy()
    data_mode = str(detail["DataMode"].iloc[-1])
    if data_mode == "net_only":
        st.info("매수/매도 분리 데이터가 없어 순매매 차트만 표시합니다.")
    elif data_mode == "unavailable":
        st.info("선택한 기간의 외국인/기관 매수/매도 상세 데이터를 불러오지 못했습니다.")
        return

    if data_mode == "buy_sell":
        st.plotly_chart(make_investor_buy_sell_value_chart(detail), use_container_width=True, key=f"{widget_base}_buy_sell_value_chart")
    st.plotly_chart(make_smart_money_net_chart(detail), use_container_width=True, key=f"{widget_base}_smart_net_chart")
    st.plotly_chart(
        make_foreign_institution_net_compare_chart(detail),
        use_container_width=True,
        key=f"{widget_base}_foreign_institution_compare_chart",
    )

    display = detail.copy()
    display["Date"] = pd.to_datetime(display["Date"]).dt.strftime("%Y-%m-%d")
    value_columns = [
        "ForeignBuyValue",
        "ForeignSellValue",
        "ForeignNetValue",
        "InstitutionBuyValue",
        "InstitutionSellValue",
        "InstitutionNetValue",
        "SmartBuyValue",
        "SmartSellValue",
        "SmartNetValue",
    ]
    volume_columns = [
        "ForeignBuyVolume",
        "ForeignSellVolume",
        "ForeignNetVolume",
        "InstitutionBuyVolume",
        "InstitutionSellVolume",
        "InstitutionNetVolume",
        "SmartBuyVolume",
        "SmartSellVolume",
        "SmartNetVolume",
    ]
    if include_individual:
        value_columns += ["IndividualBuyValue", "IndividualSellValue", "IndividualNetValue"]
        volume_columns += ["IndividualBuyVolume", "IndividualSellVolume", "IndividualNetVolume"]
    selected_columns = ["Date"]
    if display_basis in {"거래대금", "거래대금+거래량"}:
        selected_columns += value_columns
    if display_basis in {"거래량", "거래대금+거래량"}:
        selected_columns += volume_columns

    column_names = {
        "Date": "날짜",
        "ForeignBuyValue": "외국인 매수금액",
        "ForeignSellValue": "외국인 매도금액",
        "ForeignNetValue": "외국인 순매수금액",
        "InstitutionBuyValue": "기관 매수금액",
        "InstitutionSellValue": "기관 매도금액",
        "InstitutionNetValue": "기관 순매수금액",
        "IndividualBuyValue": "개인 매수금액",
        "IndividualSellValue": "개인 매도금액",
        "IndividualNetValue": "개인 순매수금액",
        "SmartBuyValue": "외국인+기관 매수금액",
        "SmartSellValue": "외국인+기관 매도금액",
        "SmartNetValue": "외국인+기관 순매수금액",
        "ForeignBuyVolume": "외국인 매수수량",
        "ForeignSellVolume": "외국인 매도수량",
        "ForeignNetVolume": "외국인 순매수수량",
        "InstitutionBuyVolume": "기관 매수수량",
        "InstitutionSellVolume": "기관 매도수량",
        "InstitutionNetVolume": "기관 순매수수량",
        "IndividualBuyVolume": "개인 매수수량",
        "IndividualSellVolume": "개인 매도수량",
        "IndividualNetVolume": "개인 순매수수량",
        "SmartBuyVolume": "외국인+기관 매수수량",
        "SmartSellVolume": "외국인+기관 매도수량",
        "SmartNetVolume": "외국인+기관 순매수수량",
    }
    formatted = display[selected_columns].rename(columns=column_names)
    for column in formatted.columns:
        if "금액" in column:
            values = pd.to_numeric(formatted[column], errors="coerce")
            formatted[column] = values.map(lambda value: "" if pd.isna(value) else (f"{value / 100_000_000:,.1f}" if unit == "억원" else f"{value:,.0f}"))
        elif "수량" in column:
            formatted[column] = pd.to_numeric(formatted[column], errors="coerce").map(lambda value: "" if pd.isna(value) else f"{value:,.0f}")
    if emphasize_net:
        st.dataframe(formatted, use_container_width=True, height=420)
    else:
        st.dataframe(formatted, use_container_width=True, height=420)

    csv = detail.drop(columns=["DataMode", "DataWarning"], errors="ignore").to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "CSV 다운로드",
        data=csv,
        file_name=f"investor_buy_sell_{code}_{dt.date.today().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key=f"{widget_base}_buy_sell_csv",
    )
    with st.expander("개발용 조회 정보"):
        st.write({key: value for key, value in debug.items() if value is not None})


def render_shorting_analysis(code: str, name: str, start_date: dt.date, end_date: dt.date, shorting: pd.DataFrame | None = None) -> dict:
    st.markdown("### 공매도 분석")
    st.caption("공매도 현황은 공매도 비중, 공매도 잔고, 공매도 추세를 보는 분석 보조 지표입니다. 투자 추천이 아닙니다.")
    shorting = shorting if shorting is not None else load_shorting_data(code, start_date, end_date)
    debug = shorting.attrs.get("debug", {}) if hasattr(shorting, "attrs") else {}
    if shorting.empty:
        st.info("선택한 기간의 공매도 데이터를 불러오지 못했습니다.")
        with st.expander("공매도 데이터 조회 정보"):
            st.write({key: value for key, value in debug.items() if value is not None})
        return {}

    summary = summarize_shorting_data(shorting)
    score = calculate_shorting_score(summary)
    cols = st.columns(6)
    cols[0].metric("공매도 위험도 점수", f"{score['score']:.1f}/100")
    cols[1].metric("공매도 위험도 등급", score["grade"])
    cols[2].metric("공매도 잔고비율", format_percent(summary.get("short_balance_ratio")))
    cols[3].metric("공매도 비중", format_percent(summary.get("short_volume_ratio_1d")))
    cols[4].metric("20일 평균 공매도 비중", format_percent(summary.get("short_volume_ratio_20d_avg")))
    cols[5].metric("공매도 증감률", format_percent(summary.get("short_volume_change_20d")))

    st.caption("공매도 증가가 반드시 주가 하락을 의미하지 않으며, 공매도 감소가 반드시 주가 상승을 의미하지 않습니다.")
    left, right = st.columns(2)
    left.plotly_chart(make_shorting_ratio_chart(shorting, name), use_container_width=True, key=f"short_ratio_{code}")
    right.plotly_chart(make_price_vs_short_balance_chart(shorting, name), use_container_width=True, key=f"short_balance_{code}")
    st.plotly_chart(make_shorting_volume_ratio_chart(shorting, name), use_container_width=True, key=f"short_volume_{code}")

    table = shorting.tail(20).copy()
    table["Date"] = pd.to_datetime(table["Date"]).dt.strftime("%Y-%m-%d")
    table = table.rename(
        columns={
            "Date": "날짜",
            "Close": "종가",
            "ShortVolume": "공매도 거래량",
            "TotalVolume": "총 거래량",
            "ShortVolumeRatio": "공매도 비중",
            "ShortValue": "공매도 거래대금",
            "TotalValue": "총 거래대금",
            "ShortValueRatio": "공매도 거래대금 비중",
            "ShortBalance": "공매도 잔고",
            "ShortBalanceRatio": "공매도 잔고비율",
        }
    )
    display_cols = [
        "날짜",
        "종가",
        "공매도 거래량",
        "총 거래량",
        "공매도 비중",
        "공매도 거래대금",
        "총 거래대금",
        "공매도 거래대금 비중",
        "공매도 잔고",
        "공매도 잔고비율",
    ]
    st.markdown("**최근 20거래일 공매도 상세**")
    st.dataframe(table[display_cols], use_container_width=True, height=420)
    with st.expander("공매도 점수 산정 근거"):
        st.write({"positive_factors": score["positive_factors"], "negative_factors": score["negative_factors"], "debug": debug})
    return {"summary": summary, "score": score}


def load_all_lists() -> tuple[pd.DataFrame, pd.DataFrame]:
    stocks = load_stock_list()
    if stocks.attrs.get("warning"):
        st.warning(stocks.attrs["warning"])
        with st.expander("종목 목록 대체 로딩 정보"):
            for error in stocks.attrs.get("debug_errors", []):
                st.code(error)
    try:
        etfs = load_etf_list()
    except Exception as exc:
        st.warning(f"ETF 목록을 불러오지 못했습니다. ETF 기능 일부가 제한됩니다. {exc}")
        etfs = pd.DataFrame(
            columns=["Code", "Name", "AssetType", "Category", "Provider", "IsLeveraged", "IsInverse", "IsHedged", "IsSynthetic", "MarketType"]
        )
    return stocks, etfs


def build_search_pool(stocks: pd.DataFrame, etfs: pd.DataFrame, target: str) -> pd.DataFrame:
    frames = []
    if target in {"전체", "일반주식"}:
        stock_rows = stocks.copy()
        stock_rows["Type"] = "Stock"
        stock_rows["Category"] = ""
        stock_rows["Provider"] = ""
        frames.append(stock_rows[["Type", "Market", "Code", "Name", "Category", "Provider"]])
    if target in {"전체", "ETF"} and not etfs.empty:
        etf_rows = etfs.copy()
        etf_rows["Type"] = "ETF"
        etf_rows["Market"] = "ETF"
        frames.append(etf_rows[["Type", "Market", "Code", "Name", "Category", "Provider"]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def select_asset(stocks: pd.DataFrame, etfs: pd.DataFrame) -> pd.Series | None:
    target = st.selectbox("검색 대상", ["전체", "일반주식", "ETF"])
    keyword = st.text_input("종목명, ETF명 또는 코드", value="삼성전자")
    pool = build_search_pool(stocks, etfs, target)
    if keyword.strip():
        pool = pool[
            pool["Name"].str.contains(keyword.strip(), case=False, na=False)
            | pool["Code"].str.contains(keyword.strip(), case=False, na=False)
        ]
    if pool.empty and target in {"전체", "ETF"} and not etfs.empty:
        st.info("검색 결과가 없습니다. 예: KODEX 200, TIGER 미국S&P500")
        pool = build_search_pool(stocks, etfs, "ETF").head(30)
    if pool.empty:
        st.warning("검색 결과가 없습니다.")
        return None
    labels = [f"{r.Type} | {r.Name} ({r.Code}) [{r.Market}] {r.Category} {r.Provider}".strip() for r in pool.itertuples()]
    selected = st.selectbox("분석 대상 선택", labels)
    return pool.iloc[labels.index(selected)]


def render_stock_analysis(asset: pd.Series, start_date: dt.date, end_date: dt.date) -> None:
    score_options = render_score_settings("stock_analysis", "Stock")
    with st.spinner("가격 데이터와 기술적 지표를 계산하는 중입니다..."):
        df = load_price(asset["Code"], start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        if df.empty:
            st.warning("선택한 기간에 가격 데이터가 없습니다.")
            return
        df = add_all_indicators(df)

    latest = df.iloc[-1]
    st.subheader(f"{asset['Name']} ({asset['Code']})")
    shorting_df = load_shorting_data(asset["Code"], start_date, end_date) if score_options["include_shorting"] else pd.DataFrame()
    shorting_summary = summarize_shorting_data(shorting_df) if not shorting_df.empty else {}
    shorting_score = calculate_shorting_score(shorting_summary) if shorting_summary else {}
    score = calculate_stock_score(
        price_summary=build_price_summary(df),
        shorting_summary={
            **shorting_summary,
            "shorting_score": shorting_score.get("score"),
            "shorting_grade": shorting_score.get("grade"),
        } if shorting_score else {},
        normalize_missing=score_options["normalize_missing"],
        include_news=score_options["include_news"],
        include_financials=score_options["include_financials"],
        include_sector=score_options["include_sector"],
        include_flow=score_options["include_flow"],
        include_shorting=score_options["include_shorting"],
    )
    render_composite_score(score)
    render_shorting_analysis(asset["Code"], asset["Name"], start_date, end_date, shorting_df if not shorting_df.empty else None)
    cols = st.columns(5)
    cols[0].metric("최신 종가", format_krw(latest["Close"]), format_percent(latest.get("RETURN_1D")))
    cols[1].metric("거래량", f"{latest['Volume']:,.0f}주", f"{latest.get('VOLUME_RATIO', 0):.2f}x")
    cols[2].metric("RSI 14", f"{latest.get('RSI14', 0):.2f}")
    cols[3].metric("MACD", f"{latest.get('MACD', 0):.2f}")
    cols[4].metric("20일 수익률", format_percent(latest.get("RETURN_20D")))

    memo = st.text_input("관심종목 메모", key="stock_memo")
    if st.button("현재 종목을 관심종목에 추가", type="primary"):
        added = add_watchlist_item(asset["Code"], asset["Name"], asset["Market"], memo, item_type="Stock")
        st.success("관심종목에 추가했습니다.") if added else st.info("이미 관심종목에 있습니다.")

    st.plotly_chart(make_price_chart(df, asset["Name"]), use_container_width=True)
    st.plotly_chart(make_volume_chart(df), use_container_width=True)
    left, right = st.columns(2)
    left.plotly_chart(make_rsi_chart(df), use_container_width=True)
    right.plotly_chart(make_macd_chart(df), use_container_width=True)
    render_stock_flow(asset["Code"], df, start_date, end_date)


def render_stock_flow(code: str, price_df: pd.DataFrame, start_date: dt.date, end_date: dt.date) -> None:
    st.subheader("외국인/기관 수급")
    st.caption(FLOW_WARNING)
    flow = load_investor_trading_by_date(code, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    if flow.empty:
        st.info("현재 환경에서 pykrx 외국인/기관 수급 데이터를 가져오지 못했습니다.")
        render_investor_buy_sell_detail(code, start_date, end_date, asset_type="Stock", key_prefix="stock_empty_flow")
        return
    summary = summarize_investor_flow(flow, price_df)
    grade = classify_accumulation(summary)
    cols = st.columns(4)
    cols[0].metric("외국인 20일 누적", format_signed_krw_eok(summary["foreign_20d"]))
    cols[1].metric("기관 20일 누적", format_signed_krw_eok(summary["institution_20d"]))
    cols[2].metric("20일 수급 강도", f"{summary['flow_strength_20d']:.2f}%")
    cols[3].metric("매집 추정 등급", grade["grade"], f"{grade['score']}점")
    st.plotly_chart(make_investor_net_value_chart(flow), use_container_width=True)
    st.plotly_chart(make_investor_cumulative_chart(flow), use_container_width=True)
    st.plotly_chart(make_price_vs_flow_chart(price_df, flow), use_container_width=True)
    render_investor_buy_sell_detail(code, start_date, end_date, asset_type="Stock", key_prefix="stock_analysis_flow")


def load_etf_bundle(code: str, start_date: dt.date, end_date: dt.date):
    start = start_date.strftime("%Y-%m-%d")
    end = end_date.strftime("%Y-%m-%d")
    price = load_etf_ohlcv(code, start, end)
    deviation = load_etf_price_deviation(code, start, end)
    tracking = load_etf_tracking_error(code, start, end)
    portfolio = load_etf_portfolio(code, end)
    flow = load_etf_investor_flow(code, start, end)
    return price, deviation, tracking, portfolio, flow


def render_etf_portfolio_section(portfolio: pd.DataFrame, etf_name: str) -> None:
    st.subheader("PDF 구성종목")
    debug = portfolio.attrs.get("debug", {}) if hasattr(portfolio, "attrs") else {}
    attempted_dates = debug.get("attempted_dates") or []
    errors = debug.get("errors") or []
    raw_shape = debug.get("raw_shape")
    raw_columns = debug.get("raw_columns") or []
    disabled_reason = debug.get("disabled_reason")
    exception_type = debug.get("exception_type")
    exception_message = debug.get("exception_message")
    env_path = debug.get("env_path")
    env_exists = debug.get("env_exists")
    has_krx_id = debug.get("has_krx_id")
    has_krx_pw = debug.get("has_krx_pw")

    if portfolio.empty:
        if disabled_reason == "missing_krx_credentials":
            st.warning("ETF PDF 구성종목 조회에는 KRX 로그인이 필요합니다. .env에 KRX_ID, KRX_PW를 설정해 주세요.")
            st.info("ETF PDF 구성종목 기능만 비활성화되었습니다. ETF 가격, NAV, 괴리율, 수급 분석은 계속 사용할 수 있습니다.")
        else:
            st.warning("ETF 구성종목 데이터를 불러오지 못했습니다.")
            st.info(
                "KRX 로그인 정보가 있어도 pykrx/KRX 응답 제한, ETF 유형 또는 기준일에 따라 PDF 데이터가 제공되지 않을 수 있습니다."
            )
        with st.expander("개발용 조회 정보"):
            st.markdown(f"- ticker: `{debug.get('ticker') or '-'}`")
            st.markdown(f"- disabled reason: `{disabled_reason or '-'}`")
            st.markdown(f"- exception type: `{exception_type or '-'}`")
            st.markdown(f"- exception message: `{exception_message or '-'}`")
            st.markdown(f"- env path: `{env_path or '-'}`")
            st.markdown(f"- env exists: `{env_exists}`")
            st.markdown(f"- has KRX_ID: `{has_krx_id}`")
            st.markdown(f"- has KRX_PW: `{has_krx_pw}`")
            st.markdown(f"- raw shape: `{raw_shape if raw_shape is not None else '-'}`")
            st.markdown(f"- raw columns: `{', '.join(raw_columns) if raw_columns else '-'}`")
            if attempted_dates:
                st.dataframe(pd.DataFrame({"시도 날짜": attempted_dates}), use_container_width=True, height=220)
            if errors:
                st.dataframe(pd.DataFrame({"조회 결과/예외": errors}), use_container_width=True, height=260)
            else:
                st.caption("명시적인 예외는 없었고 pykrx가 빈 DataFrame을 반환했습니다.")
        st.caption(
            "PDF 구성종목은 데이터 제공 시점과 ETF 유형에 따라 실제 보유 내역과 차이가 있을 수 있습니다. "
            "해외형, 합성형, 선물형 ETF는 구성종목 코드와 비중이 정확히 매핑되지 않을 수 있습니다."
        )
        return

    sorted_portfolio = portfolio.sort_values("Weight", ascending=False).reset_index(drop=True)
    top = sorted_portfolio.iloc[0]
    top10_weight = sorted_portfolio.head(10)["Weight"].fillna(0).sum()
    base_date = str(top.get("BaseDate", "-"))

    cols = st.columns(5)
    cols[0].metric("구성종목 수", f"{len(sorted_portfolio):,}")
    cols[1].metric("1위 구성종목명", str(top.get("ComponentName", "-")))
    cols[2].metric("1위 비중", format_percent(top.get("Weight")))
    cols[3].metric("상위 10개 비중 합계", format_percent(top10_weight))
    cols[4].metric("PDF 기준일", base_date)

    if sorted_portfolio["Weight"].fillna(0).sum() > 0:
        st.plotly_chart(make_etf_portfolio_chart(sorted_portfolio.head(10), etf_name), use_container_width=True)
    else:
        st.info("비중 데이터가 없어 구성종목 비중 차트를 표시하지 않습니다.")

    display = sorted_portfolio.head(20).rename(
        columns={
            "BaseDate": "기준일",
            "ComponentCode": "구성종목코드",
            "ComponentName": "구성종목명",
            "ContractCount": "계약수",
            "Amount": "금액",
            "Weight": "비중",
            "IsDomesticStock": "국내주식여부",
        }
    )
    st.dataframe(
        display[["기준일", "구성종목코드", "구성종목명", "계약수", "금액", "비중", "국내주식여부"]],
        use_container_width=True,
        height=520,
    )

    with st.expander("개발용 조회 정보"):
        st.markdown(f"- ticker: `{debug.get('ticker') or '-'}`")
        st.markdown(f"- disabled reason: `{disabled_reason or '-'}`")
        st.markdown(f"- exception type: `{exception_type or '-'}`")
        st.markdown(f"- exception message: `{exception_message or '-'}`")
        st.markdown(f"- env path: `{env_path or '-'}`")
        st.markdown(f"- env exists: `{env_exists}`")
        st.markdown(f"- has KRX_ID: `{has_krx_id}`")
        st.markdown(f"- has KRX_PW: `{has_krx_pw}`")
        st.markdown(f"- raw shape: `{raw_shape if raw_shape is not None else '-'}`")
        st.markdown(f"- raw columns: `{', '.join(raw_columns) if raw_columns else '-'}`")
        if attempted_dates:
            st.dataframe(pd.DataFrame({"시도 날짜": attempted_dates}), use_container_width=True, height=220)
        if errors:
            st.dataframe(pd.DataFrame({"조회 결과/예외": errors}), use_container_width=True, height=260)

    st.caption(
        "PDF 구성종목은 데이터 제공 시점과 ETF 유형에 따라 실제 보유 내역과 차이가 있을 수 있습니다. "
        "해외형, 합성형, 선물형 ETF는 구성종목 코드와 비중이 정확히 매핑되지 않을 수 있습니다."
    )


def render_etf_analysis(asset: pd.Series, start_date: dt.date, end_date: dt.date) -> None:
    score_options = render_score_settings("etf_analysis", "ETF")
    st.subheader(f"{asset['Name']} ({asset['Code']})")
    st.caption("ETF 분석 정보는 가격, NAV, 괴리율, 추적오차율, 구성종목, 수급 데이터를 기반으로 한 분석 보조 지표입니다. 매수/매도 추천이 아닙니다.")
    try:
        price, deviation, tracking, portfolio, flow = load_etf_bundle(asset["Code"], start_date, end_date)
        price = add_all_indicators(price.rename(columns={"TradingValue": "Amount"})).rename(columns={"Amount": "TradingValue"})
    except Exception as exc:
        st.error(f"ETF 데이터를 처리하지 못했습니다. {exc}")
        return

    summary = summarize_etf(price, deviation, tracking, flow, portfolio)
    risk = classify_etf_risk(asset.to_dict(), price, deviation, tracking)
    score = calculate_etf_score(
        etf_summary=build_etf_score_summary(price, summary, risk, asset, portfolio),
        normalize_missing=score_options["normalize_missing"],
        include_news=score_options["include_news"],
        include_flow=score_options["include_flow"],
        include_structure=score_options["include_structure"],
    )
    render_composite_score(score)
    cols = st.columns(6)
    cols[0].metric("현재가", format_krw(summary["latest_close"]))
    cols[1].metric("NAV", format_krw(summary["latest_nav"]))
    cols[2].metric("괴리율", format_percent(summary["latest_deviation_rate"]))
    cols[3].metric("추적오차율", format_percent(summary["latest_tracking_error_rate"]))
    cols[4].metric("거래대금", format_krw_eok(summary["latest_trading_value"]))
    cols[5].metric("20일 수익률", format_percent(summary["return_20d"]))

    cols = st.columns(3)
    cols[0].metric("유동성 등급", risk["LiquidityGrade"])
    cols[1].metric("괴리율 등급", risk["DeviationGrade"])
    cols[2].metric("추적오차 등급", risk["TrackingGrade"])
    if risk["ProductRiskFlags"]:
        st.warning("주의 플래그: " + ", ".join(risk["ProductRiskFlags"]))

    memo = st.text_input("ETF 관심종목 메모", key="etf_memo")
    if st.button("현재 ETF를 관심종목에 추가", type="primary"):
        added = add_watchlist_item(
            asset["Code"],
            asset["Name"],
            "ETF",
            memo,
            item_type="ETF",
            category=asset.get("Category", ""),
            provider=asset.get("Provider", ""),
        )
        st.success("관심종목에 추가했습니다.") if added else st.info("이미 관심종목에 있습니다.")

    st.plotly_chart(make_etf_price_chart(price, asset["Name"]), use_container_width=True)
    if not deviation.empty and {"Close", "DeviationRate"}.issubset(deviation.columns):
        st.plotly_chart(make_etf_nav_deviation_chart(deviation, asset["Name"]), use_container_width=True)
    else:
        st.info("괴리율 데이터가 없어 가격 차트만 표시합니다.")
    if not tracking.empty and "TrackingErrorRate" in tracking.columns:
        st.plotly_chart(make_etf_tracking_error_chart(tracking, asset["Name"]), use_container_width=True)
    if price["UnderlyingIndex"].notna().any() or not tracking.empty:
        st.plotly_chart(make_etf_index_comparison_chart(price, tracking, asset["Name"]), use_container_width=True)
    if not flow.empty:
        st.plotly_chart(make_etf_flow_chart(flow, asset["Name"]), use_container_width=True)
    else:
        st.info("ETF 투자자별 수급 데이터는 현재 환경에서 가져오지 못했습니다.")
    render_investor_buy_sell_detail(asset["Code"], start_date, end_date, asset_type="ETF", key_prefix="etf_analysis_flow")
    render_etf_portfolio_section(portfolio, asset["Name"])


def render_asset_analysis_tab(stocks: pd.DataFrame, etfs: pd.DataFrame) -> None:
    with st.sidebar:
        st.header("종목/ETF 분석 조건")
        asset = select_asset(stocks, etfs)
        default_start, default_end = default_date_range()
        start_date = st.date_input("시작일", value=default_start, key="asset_start")
        end_date = st.date_input("종료일", value=default_end, key="asset_end")
    if asset is None:
        return
    if start_date > end_date:
        st.error("시작일은 종료일보다 늦을 수 없습니다.")
        return
    render_etf_analysis(asset, start_date, end_date) if asset["Type"] == "ETF" else render_stock_analysis(asset, start_date, end_date)


def build_turnover_fallback_ranking(stocks: pd.DataFrame, market: str, days: int) -> pd.DataFrame:
    end = dt.date.today()
    start = end - dt.timedelta(days=int(days * 1.8) + 30)
    rows = []
    for stock_row in stocks[stocks["Market"] == market].head(40).itertuples():
        try:
            price = load_price(stock_row.Code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
            if price.empty:
                continue
            latest = price.iloc[-1]
            rows.append(
                {
                    "Market": market,
                    "Code": stock_row.Code,
                    "Name": stock_row.Name,
                    "Close": latest["Close"],
                    "Volume": latest["Volume"],
                    "Turnover": float(latest["Close"] * latest["Volume"]),
                    "Note": "수급 API 불가로 거래대금 기준 대체 표시",
                }
            )
        except Exception:
            continue
    return pd.DataFrame(rows).sort_values("Turnover", ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def render_flow_ranking_tab(stocks: pd.DataFrame) -> None:
    st.subheader("외국인/기관 수급")
    st.caption("일별 순매매 데이터 기준이며 투자 추천이 아닌 분석 보조 지표입니다.")
    col1, col2, col3 = st.columns(3)
    days = col1.selectbox("기간", [5, 20, 60, 120], index=1, format_func=lambda value: f"최근 {value}일")
    market = col2.selectbox("시장", ["KOSPI", "KOSDAQ"])
    investor = col3.selectbox("투자자", ["외국인", "기관합계", "개인"])
    end = dt.date.today()
    start = end - dt.timedelta(days=int(days * 1.8) + 10)
    st.markdown("#### 수급 상세")
    keyword = st.text_input("상세 조회 종목명 또는 코드", value="삼성전자", key="flow_detail_keyword")
    candidates = stocks[
        stocks["Name"].str.contains(keyword, case=False, na=False)
        | stocks["Code"].str.contains(keyword, case=False, na=False)
    ].head(30)
    if not candidates.empty:
        labels = [f"{row.Name} ({row.Code}) [{row.Market}]" for row in candidates.itertuples()]
        selected_label = st.selectbox("수급 상세 종목 선택", labels, key="flow_detail_asset")
        selected_row = candidates.iloc[labels.index(selected_label)]
        render_investor_buy_sell_detail(selected_row["Code"], start, end, asset_type="Stock", key_prefix="flow_tab_detail")
    if st.button("순매매 상위 조회", type="primary"):
        ranking = load_net_purchase_ranking(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), market, investor)
        if not ranking.empty:
            left, right = st.columns(2)
            left.markdown("**순매수 상위 30개**")
            left.dataframe(ranking.sort_values("NetBuyValue", ascending=False).head(30), use_container_width=True)
            right.markdown("**순매도 상위 30개**")
            right.dataframe(ranking.sort_values("NetBuyValue", ascending=True).head(30), use_container_width=True)
            return
        st.warning("현재 환경에서 pykrx 외국인/기관 순매매 데이터를 가져오지 못했습니다. KRX 응답 제한이나 데이터 제공 방식 문제일 수 있습니다.")
        st.info("아래 표는 실제 수급 데이터가 아니라 거래대금 기준 대체 참고 랭킹입니다.")
        with st.spinner("거래대금 기준 대체 랭킹을 만드는 중입니다..."):
            fallback = build_turnover_fallback_ranking(stocks, market, days)
        if fallback.empty:
            st.info("대체 거래대금 랭킹을 만들 수 없습니다.")
            return
        fallback.insert(0, "Rank", range(1, len(fallback) + 1))
        display = fallback.head(30).copy()
        display["Close"] = display["Close"].map(lambda value: f"{value:,.0f}원")
        display["Volume"] = display["Volume"].map(lambda value: f"{value:,.0f}주")
        display["Turnover"] = display["Turnover"].map(lambda value: f"{value / 100_000_000:,.1f}억원")
        display = display.rename(columns={"Rank": "순위", "Market": "시장", "Code": "종목코드", "Name": "종목명", "Close": "현재가", "Volume": "거래량", "Turnover": "거래대금", "Note": "비고"})
        st.markdown("**거래대금 기준 대체 참고 랭킹**")
        st.dataframe(display, use_container_width=True, height=520)


def render_etf_ranking_tab(etfs: pd.DataFrame) -> None:
    st.subheader("ETF 랭킹")
    st.caption("국내 ETF를 조건별로 정렬해 보는 분석 화면입니다. 추천 ETF가 아닙니다.")
    if etfs.empty:
        st.warning("ETF 목록이 없어 랭킹을 표시할 수 없습니다.")
        return
    scan_count = st.selectbox("최대 스캔 ETF 수", [50, 100, 200], index=0)
    sort_type = st.selectbox("랭킹 유형", ["거래대금 상위", "20일 수익률 상위", "60일 수익률 상위", "유동성 낮은 ETF"])
    if st.button("ETF 랭킹 조회", type="primary"):
        end = dt.date.today()
        start = end - dt.timedelta(days=140)
        rows = []
        progress = st.progress(0)
        for idx, row in etfs.head(scan_count).reset_index(drop=True).iterrows():
            try:
                price, deviation, tracking, portfolio, flow = load_etf_bundle(row["Code"], start, end)
                summary = summarize_etf(price, deviation, tracking, flow, portfolio)
                risk = classify_etf_risk(row.to_dict(), price, deviation, tracking)
                rows.append({
                    "ETF 코드": row["Code"],
                    "ETF명": row["Name"],
                    "운용사": row["Provider"],
                    "카테고리": row["Category"],
                    "현재가": summary["latest_close"],
                    "거래대금": summary["latest_trading_value"],
                    "20일 평균 거래대금": summary["avg_trading_value_20d"],
                    "20일 수익률": summary["return_20d"],
                    "60일 수익률": summary["return_60d"],
                    "유동성 등급": risk["LiquidityGrade"],
                    "주의 플래그": ", ".join(risk["ProductRiskFlags"]),
                })
            except Exception:
                pass
            progress.progress((idx + 1) / max(scan_count, 1))
        result = pd.DataFrame(rows)
        if result.empty:
            st.info("표시할 ETF 랭킹 데이터가 없습니다.")
            return
        sort_map = {
            "거래대금 상위": ("거래대금", False),
            "20일 수익률 상위": ("20일 수익률", False),
            "60일 수익률 상위": ("60일 수익률", False),
            "유동성 낮은 ETF": ("20일 평균 거래대금", True),
        }
        column, ascending = sort_map[sort_type]
        result = result.sort_values(column, ascending=ascending).reset_index(drop=True)
        result.insert(0, "순위", result.index + 1)
        st.dataframe(result, use_container_width=True)


def render_screener_tab(stocks: pd.DataFrame, etfs: pd.DataFrame) -> None:
    st.subheader("조건검색")
    target = st.selectbox("검색 대상", ["일반주식", "ETF"], key="screen_target")
    end = dt.date.today()
    start = end - dt.timedelta(days=420)
    if target == "일반주식":
        selected = st.multiselect("주식 조건 선택", list(CONDITION_LABELS.keys()), default=["rsi_low"], format_func=lambda key: CONDITION_LABELS[key])
        max_count = st.selectbox("최대 스캔 수", [50, 100, 200], index=0)
        include_score = st.checkbox("종합점수 계산 포함", value=False, help="계산 시간이 오래 걸릴 수 있어 최대 50개까지만 적용합니다.")
        score_conditions = st.multiselect("종합점수 조건", list(SCORE_CONDITION_LABELS.keys()), format_func=lambda key: SCORE_CONDITION_LABELS[key], disabled=not include_score)
        if st.button("조건검색 실행", type="primary"):
            rows = []
            scan_df = stocks.head(min(max_count, 50) if include_score else max_count)
            progress = st.progress(0)
            for idx, row in scan_df.reset_index(drop=True).iterrows():
                try:
                    df, matched, _summary, _acc = scan_one_stock(row["Code"], start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), selected)
                    shorting_summary = {}
                    shorting_score = {}
                    if SHORTING_CONDITIONS.intersection(selected):
                        shorting_df = load_shorting_data(row["Code"], start, end)
                        shorting_summary = summarize_shorting_data(shorting_df) if not shorting_df.empty else {}
                        shorting_score = calculate_shorting_score(shorting_summary) if shorting_summary else {}
                        short_ok, short_labels = shorting_conditions_match(shorting_summary, shorting_score, selected)
                        if not short_ok:
                            progress.progress((idx + 1) / max(len(scan_df), 1))
                            continue
                        matched += short_labels
                    score = None
                    score_labels = []
                    if include_score and not df.empty:
                        score = calculate_stock_score(
                            price_summary=build_price_summary(df),
                            shorting_summary={**shorting_summary, "shorting_score": shorting_score.get("score"), "shorting_grade": shorting_score.get("grade")} if shorting_score else {},
                        )
                        score_ok, score_labels = score_conditions_match(score, score_conditions)
                        if score_conditions and not score_ok:
                            progress.progress((idx + 1) / max(len(scan_df), 1))
                            continue
                        matched = matched + score_labels
                    if matched and not df.empty:
                        latest = df.iloc[-1]
                        rows.append({"Type": "Stock", "Code": row["Code"], "Name": row["Name"], "Close": latest["Close"], "종합점수": score.get("total_score") if score else "", "등급": score.get("grade") if score else "", "MatchedConditions": ", ".join(matched)})
                except Exception:
                    pass
                progress.progress((idx + 1) / max(len(scan_df), 1))
            st.dataframe(pd.DataFrame(rows), use_container_width=True) if rows else st.info("조건 충족 분석 후보가 없습니다.")
    else:
        selected = st.multiselect("ETF 조건 선택", list(ETF_CONDITION_LABELS.keys()), default=["etf_return_20d_5"], format_func=lambda key: ETF_CONDITION_LABELS[key])
        max_count = st.selectbox("ETF 최대 스캔 수", [50, 100, 200], index=0)
        include_score = st.checkbox("종합점수 계산 포함", value=False, help="계산 시간이 오래 걸릴 수 있어 최대 50개까지만 적용합니다.", key="etf_screen_score")
        score_conditions = st.multiselect("종합점수 조건", list(SCORE_CONDITION_LABELS.keys()), format_func=lambda key: SCORE_CONDITION_LABELS[key], disabled=not include_score, key="etf_score_conditions")
        if st.button("조건검색 실행", type="primary"):
            rows = []
            scan_df = etfs.head(min(max_count, 50) if include_score else max_count)
            progress = st.progress(0)
            for idx, row in scan_df.reset_index(drop=True).iterrows():
                try:
                    price, deviation, tracking, portfolio, flow = load_etf_bundle(row["Code"], start, end)
                    price = add_all_indicators(price.rename(columns={"TradingValue": "Amount"})).rename(columns={"Amount": "TradingValue"})
                    summary = summarize_etf(price, deviation, tracking, flow, portfolio)
                    risk = classify_etf_risk(row.to_dict(), price, deviation, tracking)
                    ok = []
                    if "etf_return_20d_5" in selected and pd.notna(summary["return_20d"]) and summary["return_20d"] >= 5:
                        ok.append(ETF_CONDITION_LABELS["etf_return_20d_5"])
                    if "etf_return_60d_10" in selected and pd.notna(summary["return_60d"]) and summary["return_60d"] >= 10:
                        ok.append(ETF_CONDITION_LABELS["etf_return_60d_10"])
                    if "exclude_leveraged" in selected and not bool(row["IsLeveraged"]):
                        ok.append(ETF_CONDITION_LABELS["exclude_leveraged"])
                    score = None
                    score_labels = []
                    if include_score:
                        score = calculate_etf_score(etf_summary=build_etf_score_summary(price, summary, risk, row, portfolio))
                        score_ok, score_labels = score_conditions_match(score, score_conditions)
                        if score_conditions and not score_ok:
                            progress.progress((idx + 1) / max(len(scan_df), 1))
                            continue
                        ok += score_labels
                    if ok:
                        rows.append({"Type": "ETF", "Code": row["Code"], "Name": row["Name"], "Close": summary["latest_close"], "Return20D": summary["return_20d"], "LiquidityGrade": risk["LiquidityGrade"], "종합점수": score.get("total_score") if score else "", "등급": score.get("grade") if score else "", "MatchedConditions": ", ".join(ok)})
                except Exception:
                    pass
                progress.progress((idx + 1) / max(len(scan_df), 1))
            st.dataframe(pd.DataFrame(rows), use_container_width=True) if rows else st.info("조건 충족 ETF가 없습니다.")


def render_watchlist_tab() -> None:
    st.subheader("관심종목")
    items = load_watchlist()
    if not items:
        st.info("관심종목이 아직 없습니다.")
        return
    score_rows = [
        {
            "구분": item.get("type", "Stock"),
            "코드": item["code"],
            "이름": item.get("name", ""),
            "종합점수": item.get("score", ""),
            "등급": item.get("grade", ""),
            "주요 긍정 요인": ", ".join(item.get("positive_factors", [])[:3]),
            "주요 주의 요인": ", ".join(item.get("negative_factors", [])[:3]),
            "마지막 점수 계산일": item.get("score_updated_at", ""),
        }
        for item in items
    ]
    st.dataframe(pd.DataFrame(score_rows), use_container_width=True)
    for item in items:
        with st.container(border=True):
            left, middle, right = st.columns([1.5, 3, 1.2])
            left.markdown(f"**{item['name']}**  \n{item.get('type', 'Stock')} | {item['code']} [{item.get('market', '-')}] ")
            if item.get("score") != "":
                left.caption(f"종합점수: {item.get('score'):.1f} / {item.get('grade', '-')}" if isinstance(item.get("score"), (int, float)) else f"종합점수: {item.get('score')}")
            memo = middle.text_input("메모", value=item.get("memo", ""), key=f"memo_{item.get('type', 'Stock')}_{item['code']}", label_visibility="collapsed")
            if middle.button("메모 저장", key=f"save_{item.get('type', 'Stock')}_{item['code']}"):
                update_watchlist_memo(item["code"], memo)
                st.success("메모를 저장했습니다.")
                st.rerun()
            if middle.button("종합점수 새로고침", key=f"score_{item.get('type', 'Stock')}_{item['code']}"):
                with st.spinner("종합점수를 계산하는 중입니다..."):
                    try:
                        score = calculate_watchlist_score(item)
                        update_watchlist_score(item["code"], item.get("type", "Stock"), score)
                        st.success("종합점수를 갱신했습니다.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"종합점수를 계산하지 못했습니다. {exc}")
            right.caption(f"추가일 {item.get('added_at', '-')}")
            if right.button("삭제", key=f"delete_{item.get('type', 'Stock')}_{item['code']}"):
                delete_watchlist_item(item["code"])
                st.success("관심종목에서 삭제했습니다.")
                st.rerun()


def render_help_tab() -> None:
    st.subheader("도움말")
    st.markdown(
        """
        K-Stock Analyzer는 한국 주식과 국내 상장 ETF를 분석하는 개인용 대시보드입니다.

        외국인/기관 수급은 pykrx가 제공하는 KRX 순매매 데이터를 사용합니다. KRX 응답 제한이나 데이터 제공 방식에 따라 비어 있을 수 있으며, 이 경우 거래대금 기준 대체 참고 랭킹을 표시합니다.

        공매도 비중은 전체 거래량 중 공매도 거래량 비율입니다. 공매도 잔고는 아직 상환되지 않은 공매도 수량입니다. 공매도 잔고비율은 시가총액 대비 공매도 잔고 비율입니다.
        공매도 위험도는 공매도 비중, 잔고, 증가 추세를 종합한 분석 지표입니다.

        공매도 증가가 반드시 주가 하락을 의미하지 않으며, 공매도 감소가 반드시 주가 상승을 의미하지 않습니다.
        종합점수와 조건검색은 매수/매도 추천이 아니라 분석 후보를 좁히기 위한 보조 도구입니다.
        """
    )
def render_news_tab(stocks: pd.DataFrame, etfs: pd.DataFrame) -> None:
    st.subheader("뉴스")
    st.caption("뉴스 감성분류는 단순 키워드 기반 분석 보조 지표이며 투자 추천이 아닙니다.")
    mode = st.radio("검색 방식", ["직접 검색어", "종목/ETF 선택"], horizontal=True)
    if mode == "종목/ETF 선택":
        asset = select_asset(stocks, etfs)
        if asset is None:
            return
        query = build_etf_news_query(asset["Name"], asset.get("Category", "")) if asset["Type"] == "ETF" else build_stock_news_query(asset["Name"], asset["Code"])
    else:
        query = st.text_input("뉴스 검색어", value="삼성전자")
    sort_label = st.selectbox("정렬", ["최신순", "관련도순"])
    display = st.selectbox("검색 개수", [10, 20, 50, 100], index=1)
    if st.button("뉴스 검색", type="primary"):
        client_id, client_secret = get_naver_credentials()
        if not client_id or not client_secret:
            st.info("뉴스 API 키가 설정되지 않았습니다. .env에 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET을 입력해 주세요.")
            status = get_naver_env_status()
            with st.expander("뉴스 API 설정 확인"):
                st.markdown(f"- env path: `{status['env_path']}`")
                st.markdown(f"- env exists: `{status['env_exists']}`")
                st.markdown(f"- has NAVER_CLIENT_ID: `{status['has_naver_client_id']}`")
                st.markdown(f"- has NAVER_CLIENT_SECRET: `{status['has_naver_client_secret']}`")
            return
        news, error = search_naver_news(query, display=display, sort="date" if sort_label == "최신순" else "sim")
        if error:
            st.info(error)
            return
        enriched = enrich_news(news)
        summary = summarize_news(enriched)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("뉴스 수", summary["count"])
        c2.metric("Positive", summary["positive"])
        c3.metric("Negative", summary["negative"])
        c4.metric("주요 태그", summary["top_tag"])
        if enriched.empty:
            st.info("검색된 뉴스가 없습니다.")
            return
        table = enriched[["PubDate", "Title", "Description", "TagText", "Sentiment", "Source", "Link"]].copy()
        table["Link"] = table["Link"].apply(lambda value: f"[원문]({value})")
        st.dataframe(table, use_container_width=True)
        timeline = make_news_timeline(enriched)
        if not timeline.empty:
            st.bar_chart(timeline.set_index("Date")["Count"])


def render_financial_sector_tab(stocks: pd.DataFrame) -> None:
    st.subheader("실적/섹터")
    view = st.radio("화면", ["선택 종목 실적", "섹터 분석"], horizontal=True)
    keyword = st.text_input("종목명 또는 코드", value="삼성전자", key="fs_keyword")
    filtered = stocks[
        stocks["Name"].str.contains(keyword, case=False, na=False)
        | stocks["Code"].str.contains(keyword, case=False, na=False)
    ]
    if filtered.empty:
        st.warning("검색 결과가 없습니다.")
        return
    label_map = {f"{row.Name} ({row.Code}) [{row.Market}]": row for row in filtered.head(50).itertuples()}
    selected_label = st.selectbox("종목 선택", list(label_map.keys()), key="fs_asset")
    selected = label_map[selected_label]

    sector_map = load_sector_map()
    merged_sector = merge_sector_info(stocks, sector_map)
    sector_info = get_stock_sector(selected.Code, stocks, sector_map)

    if view == "선택 종목 실적":
        st.caption("실적 추세 점수는 정량 보조 지표이며 투자 추천이 아닙니다. ETF에는 기업 실적 섹션을 표시하지 않습니다.")
        fundamental = load_latest_fundamental(selected.Code)
        if fundamental:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("PER", fundamental.get("PER", "-"))
            c2.metric("PBR", fundamental.get("PBR", "-"))
            c3.metric("EPS", fundamental.get("EPS", "-"))
            c4.metric("BPS", fundamental.get("BPS", "-"))
            c5.metric("DPS", fundamental.get("DPS", "-"))
        else:
            st.info("PER/PBR/EPS/BPS/DPS 데이터를 가져오지 못했습니다.")

        if not get_dart_api_key():
            st.info("DART API 키가 설정되지 않아 실적 데이터를 불러올 수 없습니다. .env에 DART_API_KEY를 입력해 주세요.")
            status = get_dart_env_status()
            with st.expander("DART API 설정 확인"):
                st.markdown(f"- env path: `{status['env_path']}`")
                st.markdown(f"- env exists: `{status['env_exists']}`")
                st.markdown(f"- has DART_API_KEY: `{status['has_dart_api_key']}`")
            return
        years = list(range(dt.date.today().year - 4, dt.date.today().year + 1))
        with st.spinner("OpenDART 실적 데이터를 불러오는 중입니다..."):
            financials = fetch_dart_financials_for_years(selected.Code, years)
        if financials.empty:
            st.info("선택한 기간에 DART 재무 데이터가 없습니다.")
            return
        summary = summarize_latest_financials(financials)
        trend = classify_earnings_trend(summary)
        st.metric("실적 추세 등급", trend["grade"], f"{trend['score']}점")
        st.dataframe(financials.head(200), use_container_width=True)
    else:
        st.caption("섹터 매핑은 data/sector_map.csv가 없으면 종목명 기반 추정값을 사용합니다.")
        sector = sector_info.get("Sector", "미분류")
        st.metric("선택 종목 섹터", sector)
        sector_codes = merged_sector[merged_sector["Sector"] == sector]["Code"].tolist()
        max_count = st.selectbox("섹터 가격 스캔 수", [50, 100, 200], index=1)
        end = dt.date.today()
        start = end - dt.timedelta(days=160)
        if st.button("섹터 분석 실행", type="primary"):
            with st.spinner("섹터 가격 데이터를 계산하는 중입니다..."):
                price_data = load_sector_price_data(sector_codes, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), max_count=max_count)
                summary = summarize_sector_performance(price_data, merged_sector)
                stock_price = load_price(selected.Code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
                comparison = compare_stock_to_sector(selected.Code, stock_price, price_data)
            if comparison:
                c1, c2, c3 = st.columns(3)
                c1.metric("종목 20일 수익률", format_percent(comparison.get("StockReturn20D")))
                c2.metric("섹터 평균 20일 수익률", format_percent(comparison.get("SectorAvgReturn20D")))
                c3.metric("섹터 대비 초과수익률", format_percent(comparison.get("ExcessReturn20D")))
            if not summary.empty:
                st.dataframe(summary, use_container_width=True)
            if not price_data.empty:
                st.dataframe(price_data.sort_values("Return20D", ascending=False), use_container_width=True)


def main() -> None:
    require_app_password()
    st.title("K-Stock Analyzer")
    st.caption("한국 주식/ETF 분석 보조 도구")
    render_deploy_status()
    with st.spinner("기본 데이터를 불러오는 중입니다..."):
        try:
            stocks, etfs = load_all_lists()
        except Exception as exc:
            st.error(f"기본 데이터를 불러오지 못했습니다. {exc}")
            return
    tabs = st.tabs(["종목/ETF 분석", "뉴스", "실적/섹터", "외국인/기관 수급", "ETF 랭킹", "조건검색", "관심종목", "도움말"])
    with tabs[0]:
        render_asset_analysis_tab(stocks, etfs)
    with tabs[1]:
        render_news_tab(stocks, etfs)
    with tabs[2]:
        render_financial_sector_tab(stocks)
    with tabs[3]:
        render_flow_ranking_tab(stocks)
    with tabs[4]:
        render_etf_ranking_tab(etfs)
    with tabs[5]:
        render_screener_tab(stocks, etfs)
    with tabs[6]:
        render_watchlist_tab()
    with tabs[7]:
        render_help_tab()


if __name__ == "__main__":
    main()
