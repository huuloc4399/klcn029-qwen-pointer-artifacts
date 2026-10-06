"""Exact-match field metrics for CVSchema 2.0 validation."""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from typing import Any, Callable


FIELD_EXTRACTORS: dict[str, Callable[[dict], list]] = {
    "personal_info.github_url": lambda x: [x["personal_info"]["github_url"]],
    "summary": lambda x: [x["summary"]],
    "skills.hard_skills": lambda x: x["skills"]["hard_skills"],
    "skills.soft_skills": lambda x: x["skills"]["soft_skills"],
    "experience.company": lambda x: [row["company"] for row in x["experience"]],
    "experience.job_title": lambda x: [row["job_title"] for row in x["experience"]],
    "experience.duration": lambda x: [row["duration"] for row in x["experience"]],
    "experience.description": lambda x: [
        row["description"] for row in x["experience"]
    ],
    "projects.name": lambda x: [row["name"] for row in x["projects"]],
    "projects.role": lambda x: [row["role"] for row in x["projects"]],
    "projects.technologies": lambda x: [
        technology
        for project in x["projects"]
        for technology in project["technologies"]
    ],
    "projects.details": lambda x: [row["details"] for row in x["projects"]],
    "education.university": lambda x: [
        row["university"] for row in x["education"]
    ],
    "education.degree": lambda x: [row["degree"] for row in x["education"]],
    "education.gpa": lambda x: [row["gpa"] for row in x["education"]],
    "education.year_graduated": lambda x: [
        row["year_graduated"] for row in x["education"]
    ],
    "certifications": lambda x: x["certifications"],
    "activities": lambda x: x["activities"],
    "awards": lambda x: x["awards"],
}


def normalize_value(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    return " ".join(normalized.split())


def field_items(value: dict | None, field: str) -> set[str]:
    if not isinstance(value, dict):
        return set()
    try:
        return {
            normalized
            for raw in FIELD_EXTRACTORS[field](value)
            if raw is not None and (normalized := normalize_value(raw))
        }
    except (KeyError, TypeError):
        return set()


def precision_recall_f1(tp: int, fp: int, fn: int) -> dict[str, Any]:
    support = tp + fn
    if tp + fp + fn == 0:
        return {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "support": support,
            "precision": None,
            "recall": None,
            "f1": None,
        }
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "support": support,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def compute_field_metrics(
    gold: dict[str, dict], predictions: dict[str, dict | None]
) -> dict[str, Any]:
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for sample_id, expected_value in gold.items():
        predicted_value = predictions.get(sample_id)
        for field in FIELD_EXTRACTORS:
            expected = field_items(expected_value, field)
            actual = field_items(predicted_value, field)
            counts[field][0] += len(expected & actual)
            counts[field][1] += len(actual - expected)
            counts[field][2] += len(expected - actual)

    by_field = {
        field: precision_recall_f1(*counts[field]) for field in FIELD_EXTRACTORS
    }
    aggregate = [
        sum(counts[field][index] for field in FIELD_EXTRACTORS)
        for index in range(3)
    ]
    micro = precision_recall_f1(*aggregate)
    supported_f1 = [
        values["f1"]
        for values in by_field.values()
        if values["support"] > 0 and values["f1"] is not None
    ]
    macro_supported_f1 = (
        sum(supported_f1) / len(supported_f1) if supported_f1 else None
    )
    return {
        "matching": "normalized_exact_set",
        "by_field": by_field,
        "micro": micro,
        "macro_f1_supported_fields": macro_supported_f1,
        "supported_field_count": len(supported_f1),
        "zero_gold_support_fields": [
            field for field, values in by_field.items() if values["support"] == 0
        ],
        "no_observed_items_fields": [
            field
            for field, values in by_field.items()
            if values["tp"] + values["fp"] + values["fn"] == 0
        ],
    }


def mismatch_details(prediction: dict | None, gold: dict) -> dict[str, Any]:
    details = {}
    for field in FIELD_EXTRACTORS:
        expected = field_items(gold, field)
        actual = field_items(prediction, field)
        if expected != actual:
            details[field] = {
                "extra": sorted(actual - expected),
                "missing": sorted(expected - actual),
            }
    return details
