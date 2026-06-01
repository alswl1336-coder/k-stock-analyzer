from __future__ import annotations

import html
import re
from urllib.parse import urlparse

import pandas as pd
from bs4 import BeautifulSoup


NEWS_KEYWORDS = [
    "실적", "어닝서프라이즈", "어닝쇼크", "수주", "공급계약", "증설", "투자", "배당", "자사주",
    "유상증자", "무상증자", "감자", "합병", "분할", "소송", "제재", "리콜", "파업", "환율", "유가",
    "반도체", "2차전지", "바이오", "방산", "조선", "자동차", "은행", "증권", "보험",
]

POSITIVE_WORDS = [
    "호재", "수주", "최대 실적", "흑자전환", "증익", "상향", "증설", "배당 확대", "자사주 매입", "계약 체결",
]
NEGATIVE_WORDS = [
    "악재", "적자전환", "감익", "하향", "손실", "제재", "소송", "리콜", "파업", "유상증자", "감사의견 거절",
]


def clean_html_text(value: str) -> str:
    text = BeautifulSoup(value or "", "html.parser").get_text(" ")
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def infer_source(link: str) -> str:
    if not link:
        return ""
    host = urlparse(link).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def normalize_news_items(items: list[dict], query: str = "") -> pd.DataFrame:
    rows = []
    for item in items:
        raw_title = item.get("title", "")
        raw_desc = item.get("description", "")
        link = item.get("link", "")
        original = item.get("originallink") or link
        rows.append(
            {
                "Title": clean_html_text(raw_title),
                "Description": clean_html_text(raw_desc),
                "Link": link,
                "OriginalLink": original,
                "PubDate": pd.to_datetime(item.get("pubDate"), errors="coerce"),
                "Source": infer_source(original or link),
                "Query": query,
                "RawTitle": raw_title,
                "RawDescription": raw_desc,
            }
        )
    if not rows:
        return pd.DataFrame(columns=["Title", "Description", "Link", "OriginalLink", "PubDate", "Source", "Query", "RawTitle", "RawDescription"])
    df = pd.DataFrame(rows)
    return df.drop_duplicates(subset=["Title", "Link"]).sort_values("PubDate", ascending=False).reset_index(drop=True)


def tag_news(title: str, description: str) -> list[str]:
    text = f"{title} {description}"
    return [keyword for keyword in NEWS_KEYWORDS if keyword in text]


def score_news_sentiment(title: str, description: str) -> int:
    text = f"{title} {description}"
    score = 0
    score += sum(1 for word in POSITIVE_WORDS if word in text)
    score -= sum(1 for word in NEGATIVE_WORDS if word in text)
    return score


def classify_news_sentiment(title: str, description: str) -> str:
    score = score_news_sentiment(title, description)
    if score > 0:
        return "Positive"
    if score < 0:
        return "Negative"
    return "Neutral"


def enrich_news(news_df: pd.DataFrame) -> pd.DataFrame:
    if news_df.empty:
        return news_df.copy()
    result = news_df.copy()
    result["Tags"] = result.apply(lambda row: tag_news(row["Title"], row["Description"]), axis=1)
    result["TagText"] = result["Tags"].apply(lambda tags: ", ".join(tags))
    result["Sentiment"] = result.apply(lambda row: classify_news_sentiment(row["Title"], row["Description"]), axis=1)
    return result


def summarize_news(news_df: pd.DataFrame) -> dict:
    enriched = enrich_news(news_df)
    if enriched.empty:
        return {"count": 0, "positive": 0, "negative": 0, "top_tag": "-", "latest_pub_date": pd.NaT}
    tags = [tag for tags in enriched["Tags"] for tag in tags]
    top_tag = pd.Series(tags).value_counts().index[0] if tags else "-"
    return {
        "count": len(enriched),
        "positive": int((enriched["Sentiment"] == "Positive").sum()),
        "negative": int((enriched["Sentiment"] == "Negative").sum()),
        "top_tag": top_tag,
        "latest_pub_date": enriched["PubDate"].max(),
    }


def make_news_timeline(news_df: pd.DataFrame) -> pd.DataFrame:
    if news_df.empty or "PubDate" not in news_df.columns:
        return pd.DataFrame(columns=["Date", "Count"])
    result = news_df.copy()
    result["Date"] = pd.to_datetime(result["PubDate"], errors="coerce").dt.date
    return result.dropna(subset=["Date"]).groupby("Date").size().reset_index(name="Count")
