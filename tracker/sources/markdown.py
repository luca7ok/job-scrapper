from __future__ import annotations

import re

_HREF = re.compile(r'href="([^"]+)"')
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_TAGS = re.compile(r"<[^>]+>")


def cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*", line.strip()))


def link_of(cell: str) -> str | None:
    m = _HREF.search(cell) or _MD_LINK.search(cell)
    return m.group(1) if m else None


def plain(cell: str) -> str:
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    s = _TAGS.sub("", s)
    s = s.replace("**", "").replace("&amp;", "&").replace("<br>", "; ")
    return " ".join(s.split())


def tables(text: str):
    lines = text.splitlines()
    section = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            section = line.lstrip("#").strip()
        if line.strip().startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            header = [h.lower() for h in cells(line)]
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                if not is_separator(lines[j]):
                    row = cells(lines[j])
                    if [r.lower() for r in row[: len(header)]] != header:
                        rows.append(row)
                j += 1
            yield section, header, rows
            i = j
            continue
        i += 1
