"""Local PII minimization before CV text is sent to a hosted parser.

This is a heuristic, not a guarantee of complete anonymization. Review extracted
text before sending real CVs to a third party.
"""

from __future__ import annotations

import re

MASKED = "[MASKED]"
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
PHONE_CANDIDATE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")
URL = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+")
HEADER_SKIP = {
    "curriculum", "vitae", "resume", "profile", "personal", "information",
    "contact", "summary", "objective", "skills", "education", "experience",
    "project", "projects", "developer", "engineer", "student", "intern",
    "thông", "tin", "cá", "nhân", "liên", "hệ", "mục", "tiêu", "tóm", "tắt",
    "kỹ", "năng", "kinh", "nghiệm", "học", "vấn", "dự", "án",
}


def redact_text(text: str, *, first_page: bool = False) -> str:
    """Mask obvious contact data and one likely candidate-name header line."""
    if first_page:
        lines = text.splitlines(keepends=True)
        nonempty = 0
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            nonempty += 1
            if nonempty > 12:
                break
            words = stripped.replace("-", " ").split()
            if (
                2 <= len(words) <= 5
                and all(word.isalpha() for word in words)
                and all(word[0].isupper() for word in words)
                and not ({word.casefold() for word in words} & HEADER_SKIP)
            ):
                lines[index] = line.replace(stripped, MASKED, 1)
                break
        text = "".join(lines)
    text = EMAIL.sub(MASKED, text)

    def mask_phone(match: re.Match[str]) -> str:
        return MASKED if 9 <= sum(char.isdigit() for char in match.group()) <= 15 else match.group()

    text = PHONE_CANDIDATE.sub(mask_phone, text)
    text = URL.sub(lambda match: match.group() if "github.com/" in match.group().casefold() else MASKED, text)
    return text
