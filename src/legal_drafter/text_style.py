from __future__ import annotations

import re

FORMATTING_PATTERN = re.compile(r"[*_`]")
LIST_PREFIX_PATTERN = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s+")
SPACE_PATTERN = re.compile(r"\s+")
SENTENCE_ENDINGS = ("다.", "니다.", "습니다.", "정합니다.", "합니다.", "할 수 있습니다.", "하여야 합니다.")


def normalize_legal_text(text: str, *, heading: str | None = None) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    lines: list[str] = []
    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        line = FORMATTING_PATTERN.sub("", line)
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^>\s*", "", line)
        line = LIST_PREFIX_PATTERN.sub("", line)
        line = SPACE_PATTERN.sub(" ", line).strip()
        if not line:
            continue
        if heading and _normalize_token(line) == _normalize_token(heading):
            continue
        lines.append(line)

    if len(lines) >= 2 and not _looks_like_sentence(lines[0]):
        lines = lines[1:]
    if not lines:
        return ""

    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if not line:
            if current and _looks_like_sentence(current[-1]):
                paragraphs.append(_join_legal_lines(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(_join_legal_lines(current))
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph).strip()


def _join_legal_lines(lines: list[str]) -> str:
    parts: list[str] = []
    for line in (line.strip() for line in lines if line.strip()):
        if not parts:
            parts.append(line)
            continue
        separator = ": " if not _looks_like_sentence(parts[-1]) else " "
        parts.append(f"{separator}{line}")
    joined = "".join(parts)
    return SPACE_PATTERN.sub(" ", joined).strip()


def _looks_like_sentence(line: str) -> bool:
    return any(line.endswith(ending) for ending in SENTENCE_ENDINGS)


def _normalize_token(text: str) -> str:
    cleaned = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    return cleaned.strip().lower()
