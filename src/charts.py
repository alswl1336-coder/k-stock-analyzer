from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def make_price_chart(df: pd.DataFrame, stock_name: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df["Date"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="가격",
        )
    )

    colors = {"MA5": "#2563eb", "MA20": "#16a34a", "MA60": "#f97316", "MA120": "#7c3aed"}
    for ma, color in colors.items():
        if ma in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df[ma],
                    mode="lines",
                    name=ma,
                    line={"width": 1.5, "color": color},
                )
            )

    if {"BB_UPPER", "BB_LOWER"}.issubset(df.columns):
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["BB_UPPER"],
                mode="lines",
                name="볼린저 상단",
                line={"width": 1, "color": "rgba(100, 116, 139, 0.7)"},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["BB_LOWER"],
                mode="lines",
                name="볼린저 하단",
                fill="tonexty",
                fillcolor="rgba(148, 163, 184, 0.14)",
                line={"width": 1, "color": "rgba(100, 116, 139, 0.7)"},
            )
        )

    fig.update_layout(
        title=f"{stock_name} 가격 차트",
        height=620,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        xaxis_rangeslider_visible=False,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    return fig


def make_volume_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Date"], y=df["Volume"], name="거래량", marker_color="#64748b"))
    if "VOLUME_MA20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["VOLUME_MA20"],
                mode="lines",
                name="20일 평균 거래량",
                line={"color": "#ef4444", "width": 1.5},
            )
        )
    fig.update_layout(title="거래량", height=300, margin={"l": 20, "r": 20, "t": 45, "b": 20})
    return fig


def make_rsi_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["RSI14"], mode="lines", name="RSI 14"))
    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444")
    fig.add_hline(y=30, line_dash="dash", line_color="#2563eb")
    fig.update_layout(title="RSI", height=320, yaxis_range=[0, 100], margin={"l": 20, "r": 20, "t": 45, "b": 20})
    return fig


def make_macd_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD"], mode="lines", name="MACD"))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD_SIGNAL"], mode="lines", name="Signal"))
    fig.add_trace(go.Bar(x=df["Date"], y=df["MACD_HIST"], name="Histogram", marker_color="#94a3b8"))
    fig.update_layout(title="MACD", height=320, margin={"l": 20, "r": 20, "t": 45, "b": 20})
    return fig


def make_investor_net_value_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Date"], y=df["ForeignNetValue"] / 100_000_000, name="외국인 순매매"))
    fig.add_trace(go.Bar(x=df["Date"], y=df["InstitutionNetValue"] / 100_000_000, name="기관 순매매"))
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=(df["ForeignNetValue"] + df["InstitutionNetValue"]) / 100_000_000,
            mode="lines",
            name="외국인+기관 합산",
            line={"color": "#111827", "width": 2},
        )
    )
    fig.update_layout(
        title="일자별 외국인/기관 순매매 거래대금",
        yaxis_title="억원",
        barmode="relative",
        height=360,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return fig


def make_investor_cumulative_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["ForeignCumNetValue"] / 100_000_000, mode="lines", name="외국인 누적"))
    fig.add_trace(
        go.Scatter(x=df["Date"], y=df["InstitutionCumNetValue"] / 100_000_000, mode="lines", name="기관 누적")
    )
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["SmartMoneyCumNetValue"] / 100_000_000,
            mode="lines",
            name="외국인+기관 누적",
            line={"width": 3},
        )
    )
    fig.update_layout(
        title="외국인/기관 누적 순매매",
        yaxis_title="억원",
        height=360,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return fig


def make_price_vs_flow_chart(price_df: pd.DataFrame, investor_df: pd.DataFrame) -> go.Figure:
    merged = pd.merge(
        price_df[["Date", "Close"]],
        investor_df[["Date", "SmartMoneyCumNetValue"]],
        on="Date",
        how="inner",
    )
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=merged["Date"], y=merged["Close"], mode="lines", name="종가", line={"color": "#2563eb"}),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=merged["Date"],
            y=merged["SmartMoneyCumNetValue"] / 100_000_000,
            mode="lines",
            name="외국인+기관 누적 순매매",
            line={"color": "#dc2626"},
        ),
        secondary_y=True,
    )
    fig.update_layout(title="주가 대비 수급", height=380, margin={"l": 20, "r": 20, "t": 50, "b": 20})
    fig.update_yaxes(title_text="종가", secondary_y=False)
    fig.update_yaxes(title_text="누적 순매매(억원)", secondary_y=True)
    return fig


def make_etf_price_chart(etf_df: pd.DataFrame, etf_name: str) -> go.Figure:
    return make_price_chart(etf_df, etf_name)


def make_etf_nav_deviation_chart(deviation_df: pd.DataFrame, etf_name: str) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=deviation_df["Date"], y=deviation_df["Close"], name="종가", mode="lines"), secondary_y=False)
    if "NAV" in deviation_df.columns:
        fig.add_trace(go.Scatter(x=deviation_df["Date"], y=deviation_df["NAV"], name="NAV", mode="lines"), secondary_y=False)
    fig.add_trace(
        go.Scatter(x=deviation_df["Date"], y=deviation_df["DeviationRate"], name="괴리율", mode="lines"),
        secondary_y=True,
    )
    fig.add_hline(y=1, line_dash="dash", line_color="#ef4444", secondary_y=True)
    fig.add_hline(y=-1, line_dash="dash", line_color="#ef4444", secondary_y=True)
    fig.add_hline(y=0, line_dash="dot", line_color="#64748b", secondary_y=True)
    fig.update_layout(title=f"{etf_name} NAV/괴리율", height=360, margin={"l": 20, "r": 20, "t": 50, "b": 20})
    fig.update_yaxes(title_text="가격/NAV", secondary_y=False)
    fig.update_yaxes(title_text="괴리율(%)", secondary_y=True)
    return fig


def make_etf_tracking_error_chart(tracking_df: pd.DataFrame, etf_name: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tracking_df["Date"], y=tracking_df["TrackingErrorRate"], name="추적오차율", mode="lines"))
    fig.add_hline(y=1, line_dash="dash", line_color="#f97316")
    fig.add_hline(y=3, line_dash="dash", line_color="#ef4444")
    fig.update_layout(
        title=f"{etf_name} 추적오차율",
        yaxis_title="%",
        height=320,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return fig


def make_etf_index_comparison_chart(etf_df: pd.DataFrame, tracking_df: pd.DataFrame, etf_name: str) -> go.Figure:
    fig = go.Figure()
    close = etf_df["Close"].dropna()
    if not close.empty and close.iloc[0] != 0:
        fig.add_trace(go.Scatter(x=etf_df["Date"], y=etf_df["Close"] / close.iloc[0] * 100, name="ETF 종가", mode="lines"))
    if "UnderlyingIndex" in etf_df.columns and etf_df["UnderlyingIndex"].notna().any():
        index = etf_df["UnderlyingIndex"].dropna()
        if not index.empty and index.iloc[0] != 0:
            fig.add_trace(
                go.Scatter(x=etf_df["Date"], y=etf_df["UnderlyingIndex"] / index.iloc[0] * 100, name="기초지수", mode="lines")
            )
    elif not tracking_df.empty and "IndexValue" in tracking_df.columns:
        index = tracking_df["IndexValue"].dropna()
        if not index.empty and index.iloc[0] != 0:
            fig.add_trace(
                go.Scatter(
                    x=tracking_df["Date"],
                    y=tracking_df["IndexValue"] / index.iloc[0] * 100,
                    name="기초지수",
                    mode="lines",
                )
            )
    fig.update_layout(title=f"{etf_name} 기초지수 대비", yaxis_title="기준 100", height=340)
    return fig


def make_etf_portfolio_chart(portfolio_df: pd.DataFrame, etf_name: str) -> go.Figure:
    top = portfolio_df.sort_values("Weight", ascending=False).head(10)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=top["Weight"], y=top["ComponentName"], orientation="h", name="비중"))
    fig.update_layout(
        title=f"{etf_name} PDF 상위 구성종목",
        xaxis_title="비중(%)",
        height=420,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        yaxis={"autorange": "reversed"},
    )
    return fig


def make_etf_flow_chart(flow_df: pd.DataFrame, etf_name: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=flow_df["Date"], y=flow_df["ForeignNetValue"] / 100_000_000, name="외국인 순매매"))
    fig.add_trace(go.Bar(x=flow_df["Date"], y=flow_df["InstitutionNetValue"] / 100_000_000, name="기관 순매매"))
    fig.add_trace(
        go.Scatter(
            x=flow_df["Date"],
            y=flow_df["SmartMoneyCumNetValue"] / 100_000_000,
            name="외국인+기관 누적",
            mode="lines",
        )
    )
    fig.update_layout(title=f"{etf_name} ETF 수급", yaxis_title="억원", barmode="relative", height=340)
    return fig


def make_investor_buy_sell_value_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for column, name in [
        ("ForeignBuyValue", "외국인 매수"),
        ("ForeignSellValue", "외국인 매도"),
        ("InstitutionBuyValue", "기관 매수"),
        ("InstitutionSellValue", "기관 매도"),
    ]:
        if column in df.columns and pd.to_numeric(df[column], errors="coerce").notna().any():
            fig.add_trace(go.Bar(x=df["Date"], y=pd.to_numeric(df[column], errors="coerce") / 100_000_000, name=name))
    fig.update_layout(
        title="외국인/기관 일별 매수/매도 거래대금",
        yaxis_title="억원",
        barmode="group",
        height=360,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return fig


def make_smart_money_net_chart(df: pd.DataFrame) -> go.Figure:
    smart = pd.to_numeric(df["SmartNetValue"], errors="coerce").fillna(0)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Date"], y=smart / 100_000_000, name="외국인+기관 순매수"))
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=smart.cumsum() / 100_000_000,
            mode="lines",
            name="누적 순매수",
            line={"color": "#111827", "width": 3},
        )
    )
    fig.update_layout(
        title="외국인+기관 순매수 추이",
        yaxis_title="억원",
        barmode="relative",
        height=360,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return fig


def make_foreign_institution_net_compare_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Date"], y=pd.to_numeric(df["ForeignNetValue"], errors="coerce") / 100_000_000, name="외국인 순매수"))
    fig.add_trace(go.Bar(x=df["Date"], y=pd.to_numeric(df["InstitutionNetValue"], errors="coerce") / 100_000_000, name="기관 순매수"))
    fig.update_layout(
        title="외국인 vs 기관 순매수 비교",
        yaxis_title="억원",
        barmode="relative",
        height=340,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return fig


def make_shorting_ratio_chart(df: pd.DataFrame, name: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=pd.to_numeric(df["ShortVolumeRatio"], errors="coerce"),
            mode="lines",
            name="공매도 비중",
            line={"color": "#dc2626", "width": 2},
        )
    )
    fig.update_layout(title=f"{name} 공매도 비중 추이", yaxis_title="%", height=340, margin={"l": 20, "r": 20, "t": 50, "b": 20})
    return fig


def make_price_vs_short_balance_chart(df: pd.DataFrame, name: str) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], mode="lines", name="종가", line={"color": "#2563eb"}), secondary_y=False)
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=pd.to_numeric(df["ShortBalance"], errors="coerce"),
            mode="lines",
            name="공매도 잔고",
            line={"color": "#7c3aed"},
        ),
        secondary_y=True,
    )
    fig.update_layout(title=f"{name} 주가 vs 공매도 잔고", height=360, margin={"l": 20, "r": 20, "t": 50, "b": 20})
    fig.update_yaxes(title_text="종가", secondary_y=False)
    fig.update_yaxes(title_text="공매도 잔고", secondary_y=True)
    return fig


def make_shorting_volume_ratio_chart(df: pd.DataFrame, name: str) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=df["Date"], y=pd.to_numeric(df["ShortVolume"], errors="coerce"), name="공매도 거래량"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=pd.to_numeric(df["ShortVolumeRatio"], errors="coerce"),
            mode="lines",
            name="공매도 비중",
            line={"color": "#dc2626", "width": 2},
        ),
        secondary_y=True,
    )
    fig.update_layout(title=f"{name} 공매도 거래량과 비중", height=360, margin={"l": 20, "r": 20, "t": 50, "b": 20})
    fig.update_yaxes(title_text="거래량", secondary_y=False)
    fig.update_yaxes(title_text="비중(%)", secondary_y=True)
    return fig
