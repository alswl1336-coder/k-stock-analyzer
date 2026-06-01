from __future__ import annotations

import pandas as pd


ACCOUNT_ALIASES = {
    "Revenue": ["매출액", "수익(매출액)", "영업수익", "매출"],
    "OperatingIncome": ["영업이익", "영업손익"],
    "NetIncome": ["당기순이익", "분기순이익", "반기순이익", "당기순손익"],
    "Assets": ["자산총계", "자산총액"],
    "Liabilities": ["부채총계", "부채총액"],
    "Equity": ["자본총계", "자본총액"],
    "OperatingCashFlow": ["영업활동현금흐름", "영업활동으로 인한 현금흐름"],
}


def normalize_account_name(name: str) -> str:
    text = str(name).replace(" ", "")
    for key, aliases in ACCOUNT_ALIASES.items():
        if any(alias.replace(" ", "") in text for alias in aliases):
            return key
    return str(name)


def extract_key_financials(financial_df: pd.DataFrame) -> pd.DataFrame:
    if financial_df.empty:
        return pd.DataFrame()
    df = financial_df.copy()
    df["NormalizedAccount"] = df["AccountName"].map(normalize_account_name)
    df = df[df["NormalizedAccount"].isin(ACCOUNT_ALIASES.keys())]
    if df.empty:
        return pd.DataFrame()
    return (
        df.sort_values(["BusinessYear", "ReportCode", "Ord"])
        .drop_duplicates(["BusinessYear", "ReportCode", "NormalizedAccount"], keep="first")
        .pivot_table(index=["BusinessYear", "ReportCode"], columns="NormalizedAccount", values="CurrentAmount", aggfunc="first")
        .reset_index()
        .sort_values(["BusinessYear", "ReportCode"])
    )


def calculate_financial_ratios(key_df: pd.DataFrame) -> pd.DataFrame:
    result = key_df.copy()
    for column in ["Revenue", "OperatingIncome", "NetIncome", "Assets", "Liabilities", "Equity", "OperatingCashFlow"]:
        if column not in result.columns:
            result[column] = pd.NA
    result["RevenueYoY"] = result["Revenue"].pct_change() * 100
    result["OperatingIncomeYoY"] = result["OperatingIncome"].pct_change() * 100
    result["NetIncomeYoY"] = result["NetIncome"].pct_change() * 100
    result["OperatingMargin"] = result["OperatingIncome"] / result["Revenue"] * 100
    result["NetMargin"] = result["NetIncome"] / result["Revenue"] * 100
    result["DebtRatio"] = result["Liabilities"] / result["Equity"] * 100
    result["ROE"] = result["NetIncome"] / result["Equity"] * 100
    result["OCFToNetIncome"] = result["OperatingCashFlow"] / result["NetIncome"] * 100
    return result


def summarize_latest_financials(financial_df: pd.DataFrame, fundamental_df: pd.DataFrame | None = None) -> dict:
    key = extract_key_financials(financial_df)
    ratios = calculate_financial_ratios(key) if not key.empty else pd.DataFrame()
    latest = ratios.iloc[-1].to_dict() if not ratios.empty else {}
    if fundamental_df is not None and not fundamental_df.empty:
        f = fundamental_df.iloc[-1].to_dict()
        latest.update({k: f.get(k) for k in ["PER", "PBR", "EPS", "BPS", "DPS"]})
    return latest


def classify_earnings_trend(summary: dict) -> dict:
    conditions = [
        ("매출 YoY 증가", summary.get("RevenueYoY", 0) > 0, 15),
        ("영업이익 YoY 증가", summary.get("OperatingIncomeYoY", 0) > 0, 20),
        ("순이익 YoY 증가", summary.get("NetIncomeYoY", 0) > 0, 15),
        ("영업이익률 5% 이상", summary.get("OperatingMargin", 0) >= 5, 15),
        ("부채비율 200% 이하", summary.get("DebtRatio", 9999) <= 200, 10),
        ("영업현금흐름 양수", summary.get("OperatingCashFlow", 0) > 0, 15),
    ]
    score = min(100, sum(points for _label, ok, points in conditions if ok))
    matched = [label for label, ok, _points in conditions if ok]
    if score >= 70:
        grade = "개선"
    elif score >= 45:
        grade = "유지"
    elif score > 0:
        grade = "악화"
    else:
        grade = "데이터 부족"
    return {"grade": grade, "score": score, "matched_conditions": matched, "warning": "실적 추세 점수는 정량 보조 지표이며 투자 추천이 아닙니다."}


def load_fundamental_by_date(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    try:
        from pykrx import stock
        df = stock.get_market_fundamental_by_date(start_date.replace("-", ""), end_date.replace("-", ""), ticker)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    return df.reset_index().rename(columns={"날짜": "Date"})


def load_latest_fundamental(ticker: str) -> dict:
    end = pd.Timestamp.today()
    start = end - pd.Timedelta(days=60)
    df = load_fundamental_by_date(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    return df.iloc[-1].to_dict() if not df.empty else {}
