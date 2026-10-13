"""Aggregates and server-side SVG bar geometry for the satisfaction admin page.

The site's Content-Security-Policy allows only same-origin scripts, so charts are plain SVG
built here (one hue, thin bars with 4px rounded data-ends anchored to the baseline, recessive
grid, native <title> tooltips) and every chart has a table next to it.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any


VIETNAM = timezone(timedelta(hours=7))
SCORE_BANDS = [("0–49", 0, 50), ("50–69", 50, 70), ("70–84", 70, 85), ("85–100", 85, 101)]


def local_time(record: dict[str, Any]) -> datetime | None:
    value = record.get("created_at") or record.get("received_at")
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(VIETNAM)


def _ratings(records: list[dict[str, Any]]) -> list[int]:
    return [int(item["rating"]) for item in records if isinstance(item.get("rating"), int) and 1 <= item["rating"] <= 5]


def _group(records: list[dict[str, Any]], key) -> list[dict[str, Any]]:
    buckets: dict[str, list[int]] = defaultdict(list)
    for record in records:
        label = key(record)
        if label is not None and isinstance(record.get("rating"), int):
            buckets[label].append(int(record["rating"]))
    rows = [{
        "label": label,
        "count": len(values),
        "mean": round(statistics.mean(values), 2),
        "satisfied": sum(value >= 4 for value in values) / len(values),
    } for label, values in buckets.items()]
    return sorted(rows, key=lambda row: (-row["count"], row["label"]))


def _score_band(record: dict[str, Any]) -> str | None:
    score = (record.get("context") or {}).get("total_score")
    if not isinstance(score, (int, float)):
        return None
    return next((band for band, low, high in SCORE_BANDS if low <= score < high), None)


def summarize(records: list[dict[str, Any]], *, today: date | None = None, days: int = 30) -> dict[str, Any]:
    ratings = _ratings(records)
    count = len(ratings)
    distribution = [{"stars": stars, "count": ratings.count(stars),
                     "share": ratings.count(stars) / count if count else 0.0} for stars in range(1, 6)]

    today = today or datetime.now(VIETNAM).date()
    per_day: dict[date, list[int]] = defaultdict(list)
    for record in records:
        stamp = local_time(record)
        if stamp and isinstance(record.get("rating"), int):
            per_day[stamp.date()].append(int(record["rating"]))
    window = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    daily = [{"day": day, "count": len(per_day.get(day, [])),
              "mean": round(statistics.mean(per_day[day]), 2) if per_day.get(day) else None} for day in window]

    context = lambda name: (lambda record: (record.get("context") or {}).get(name) or None)  # noqa: E731
    return {
        "count": count,
        "mean": round(statistics.mean(ratings), 2) if ratings else None,
        "median": statistics.median(ratings) if ratings else None,
        "satisfied": sum(value >= 4 for value in ratings) / count if count else None,
        "dissatisfied": sum(value <= 2 for value in ratings) / count if count else None,
        "with_comment": sum(1 for record in records if (record.get("comment") or "").strip()),
        "first": min((stamp for stamp in map(local_time, records) if stamp), default=None),
        "last": max((stamp for stamp in map(local_time, records) if stamp), default=None),
        "distribution": distribution,
        "daily": daily,
        "days_with_ratings": [row for row in reversed(daily) if row["count"]],
        "groups": [
            ("Ngôn ngữ CV", _group(records, context("language"))),
            ("Tuyến xử lý PDF", _group(records, lambda record: (record.get("context") or {}).get("document_route") or "web")),
            ("Mức đánh giá CV", _group(records, context("verdict"))),
            ("Điểm CV (thang 100)", sorted(_group(records, _score_band),
                                          key=lambda row: [band for band, _, _ in SCORE_BANDS].index(row["label"]))),
        ],
    }


def _tick_step(value: float, ticks: int = 4) -> int:
    """Smallest 1/2/5 x 10^k integer step so that `ticks` steps cover the value (counts are integers)."""
    raw = max(value / ticks, 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 5, 10):
        if raw <= factor * magnitude:
            return int(factor * magnitude)
    return int(raw)


def _bar_path(x: float, y: float, width: float, base: float, radius: float = 4.0) -> str:
    """Bar with rounded top corners only, anchored flat on the baseline."""
    height = base - y
    if height <= 0:
        return ""
    r = min(radius, width / 2, height)
    return (f"M{x:.1f},{base:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}"
            f"H{x + width - r:.1f}Q{x + width:.1f},{y:.1f} {x + width:.1f},{y + r:.1f}V{base:.1f}Z")


def bar_chart(items: list[tuple[str, int, str]], *, width: int = 560, height: int = 220,
              label_every: int = 1, value_labels: bool = False) -> dict[str, Any]:
    """Geometry for a single-series vertical bar chart: items are (axis label, value, tooltip)."""
    left, right, top, bottom = 34, 8, 14, 26
    plot_width, plot_height = width - left - right, height - top - bottom
    base = top + plot_height
    step = _tick_step(max((value for _, value, _ in items), default=0))
    top_value = step * 4
    slot = plot_width / max(len(items), 1)
    bar_width = max(min(slot * 0.62, 48), 3)
    bars = []
    for index, (label, value, tooltip) in enumerate(items):
        x = left + index * slot + (slot - bar_width) / 2
        y = base - plot_height * value / top_value
        bars.append({
            "path": _bar_path(x, y, bar_width, base),
            "hit_x": round(left + index * slot, 1), "hit_width": round(slot, 1),
            "label": label if index % label_every == 0 else "",
            "label_x": round(x + bar_width / 2, 1),
            "value": value, "value_y": round(y - 5, 1), "tooltip": tooltip,
        })
    ticks = [{"value": step * index, "y": round(base - plot_height * index / 4, 1)} for index in range(5)]
    return {"width": width, "height": height, "left": left, "right": width - right, "base": base,
            "top": top, "bars": bars, "ticks": ticks, "value_labels": value_labels}
