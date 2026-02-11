import re

from bs4 import BeautifulSoup


DISCLAIMER_PATTERNS = [
    re.compile(r"This site contains commercial content", re.IGNORECASE),
    re.compile(r"Odds are subject to change", re.IGNORECASE),
    re.compile(r"Gambling problem\?", re.IGNORECASE),
]

STAT_PATTERNS = [
    re.compile(r"\b\d{1,3}-\d{1,3}\b"),
    re.compile(r"\b\d{1,3}\.\d+%\b"),
    re.compile(r"\b(?:-?\d{3,4}|\+\d{3,4}|PK)\b", re.IGNORECASE),
    re.compile(r"\b(?:Over|Under)\s*\d{1,3}(?:\.\d)?\b", re.IGNORECASE),
]

ANGLE_HINTS = [
    "trend",
    "record",
    "against the spread",
    "ats",
    "line move",
    "closing line",
    "edge",
    "value",
    "implied probability",
    "market",
]


class ContentCleaner:
    def clean(self, raw_html_or_text: str) -> str:
        soup = BeautifulSoup(raw_html_or_text or "", "lxml")
        text = soup.get_text("\n") if soup.find() else raw_html_or_text

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        filtered = []
        for line in lines:
            if any(pattern.search(line) for pattern in DISCLAIMER_PATTERNS):
                continue
            if len(line) < 2:
                continue
            filtered.append(line)

        normalized = "\n".join(filtered)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def extract_key_points(self, clean_text: str, max_points: int = 12) -> list[str]:
        points: list[str] = []
        for line in clean_text.splitlines():
            line_compact = line.strip()
            if not line_compact:
                continue

            if any(pattern.search(line_compact) for pattern in STAT_PATTERNS):
                points.append(line_compact)
                continue

            low = line_compact.lower()
            if any(keyword in low for keyword in ANGLE_HINTS):
                points.append(line_compact)

            if len(points) >= max_points:
                break

        return points
