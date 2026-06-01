import pandas as pd

from src.news_analysis import classify_news_sentiment, normalize_news_items, summarize_news, tag_news


def test_news_html_cleanup_and_dedup():
    items = [
        {"title": "<b>삼성전자</b> 호재", "description": "&quot;수주&quot;", "link": "https://a.com/1", "originallink": "https://a.com/1", "pubDate": "Mon, 01 Jan 2024 10:00:00 +0900"},
        {"title": "<b>삼성전자</b> 호재", "description": "&quot;수주&quot;", "link": "https://a.com/1", "originallink": "https://a.com/1", "pubDate": "Mon, 01 Jan 2024 10:00:00 +0900"},
    ]
    df = normalize_news_items(items, "삼성전자")
    assert len(df) == 1
    assert df.iloc[0]["Title"] == "삼성전자 호재"
    assert pd.notna(df.iloc[0]["PubDate"])


def test_tag_and_sentiment():
    tags = tag_news("대규모 수주", "실적 개선")
    assert "수주" in tags
    assert classify_news_sentiment("최대 실적 호재", "증익") == "Positive"
    assert classify_news_sentiment("리콜 악재", "소송") == "Negative"
    assert classify_news_sentiment("보도자료", "일반 공지") == "Neutral"


def test_summarize_empty_news():
    summary = summarize_news(pd.DataFrame())
    assert summary["count"] == 0
