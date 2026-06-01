from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile


WATCHLIST_PATH = Path(__file__).resolve().parents[1] / "watchlist.json"


def load_watchlist(path: Path = WATCHLIST_PATH) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    migrated = []
    for item in data:
        if not isinstance(item, dict):
            continue
        code = item.get("code") or item.get("Code")
        if not code:
            continue
        migrated.append(
            {
                "type": item.get("type") or item.get("Type") or "Stock",
                "code": code,
                "name": item.get("name") or item.get("Name") or "",
                "market": item.get("market") or item.get("Market") or "",
                "category": item.get("category") or item.get("Category") or "",
                "provider": item.get("provider") or item.get("Provider") or "",
                "memo": item.get("memo") or item.get("Memo") or "",
                "score": item.get("score") or item.get("Score") or "",
                "grade": item.get("grade") or item.get("Grade") or "",
                "positive_factors": item.get("positive_factors") or [],
                "negative_factors": item.get("negative_factors") or [],
                "score_updated_at": item.get("score_updated_at") or "",
                "added_at": item.get("added_at") or item.get("CreatedAt") or datetime.now().strftime("%Y-%m-%d %H:%M"),
                "updated_at": item.get("updated_at") or item.get("UpdatedAt") or "",
            }
        )
    return migrated


def save_watchlist(items: list[dict[str, str]], path: Path = WATCHLIST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as temp:
        json.dump(items, temp, ensure_ascii=False, indent=2)
        temp_path = Path(temp.name)
    temp_path.replace(path)


def add_watchlist_item(
    code: str,
    name: str,
    market: str,
    memo: str = "",
    item_type: str = "Stock",
    category: str = "",
    provider: str = "",
) -> bool:
    items = load_watchlist()
    if any(item["code"] == code and item.get("type", "Stock") == item_type for item in items):
        return False
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    items.append(
        {
            "type": item_type,
            "code": code,
            "name": name,
            "market": market,
            "category": category,
            "provider": provider,
            "memo": memo,
            "added_at": now,
            "updated_at": now,
        }
    )
    save_watchlist(items)
    return True


def delete_watchlist_item(code: str) -> None:
    save_watchlist([item for item in load_watchlist() if item["code"] != code])


def update_watchlist_memo(code: str, memo: str) -> None:
    items = load_watchlist()
    for item in items:
        if item["code"] == code:
            item["memo"] = memo
            item["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            break
    save_watchlist(items)


def update_watchlist_score(code: str, item_type: str, score_result: dict) -> None:
    items = load_watchlist()
    for item in items:
        if item["code"] == code and item.get("type", "Stock") == item_type:
            item["score"] = score_result.get("total_score")
            item["grade"] = score_result.get("grade", "")
            item["positive_factors"] = score_result.get("positive_factors", [])[:3]
            item["negative_factors"] = score_result.get("negative_factors", [])[:3]
            item["score_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            item["updated_at"] = item["score_updated_at"]
            break
    save_watchlist(items)
