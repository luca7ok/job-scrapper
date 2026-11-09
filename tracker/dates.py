from __future__ import annotations

import re
import unicodedata

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_MONTH_WORDS: dict[int, list[str]] = {
    1: ["january", "januar", "janvier", "enero", "gennaio", "styczen", "stycznia", "ianuarie", "januari"],
    2: ["february", "februar", "fevrier", "febrero", "febbraio", "luty", "lutego", "februarie", "februari"],
    3: ["march", "marz", "maerz", "mars", "marzo", "marzec", "marca", "martie", "maart"],
    4: ["april", "avril", "abril", "aprile", "kwiecien", "kwietnia", "aprilie"],
    5: ["mai", "mayo", "maggio", "maja", "mei"],
    6: ["june", "juni", "juin", "junio", "giugno", "czerwiec", "czerwca", "iunie"],
    7: ["july", "juli", "juillet", "julio", "luglio", "lipiec", "lipca", "iulie"],
    8: ["august", "aout", "agosto", "sierpien", "sierpnia", "augustus"],
    9: ["september", "septembre", "septiembre", "settembre", "wrzesien", "wrzesnia", "septembrie"],
    10: ["october", "oktober", "octobre", "octubre", "ottobre", "pazdziernik", "pazdziernika", "octombrie"],
    11: ["november", "novembre", "noviembre", "listopad", "listopada", "noiembrie"],
    12: ["december", "dezember", "decembre", "diciembre", "dicembre", "grudzien", "grudnia", "decembrie"],
}
_CASED_MONTHS: dict[int, list[str]] = {
    1: ["Jan"], 2: ["Feb"], 3: ["Mar"], 4: ["Apr"], 5: ["May"], 6: ["Jun"],
    7: ["Jul"], 8: ["Aug"], 9: ["Sep", "Sept"], 10: ["Oct"], 11: ["Nov"], 12: ["Dec"],
}

_WORD_TO_MONTH = {w: m for m, ws in _MONTH_WORDS.items() for w in ws}
_CASED_TO_MONTH = {w: m for m, ws in _CASED_MONTHS.items() for w in ws}
_MONTH_RE = re.compile(
    r"(?<![A-Za-z])(?:(?i:" + "|".join(sorted(_WORD_TO_MONTH, key=len, reverse=True)) + r")|"
    + "|".join(sorted(_CASED_TO_MONTH, key=len, reverse=True)) + r")(?![A-Za-z])"
)
_RANGE_SEP = re.compile(r"^\s*(?:\d{1,2}(?:st|nd|rd|th)?\.?\s*)?(?:,?\s*\d{4}\s*)?(?:-|–|—|to|until|till|through|thru|bis|au|a|al|do|pana la|tot|until the end of)\s*(?:the\s*)?(?:end of\s*)?(?:\d{1,2}(?:st|nd|rd|th)?\.?\s*(?:of\s*)?)?$", re.I)
_DEADLINE = re.compile(
    r"(deadline|apply by|applications? (close|due|are open until|open until)|closing|closes|close on|submit|no later than|bewerbungsschluss|bewerbungsfrist|date limite|scadenza|fecha limite|before|posted|published|updated|expires?)\W*(\w+\W+){0,4}$",
    re.I,
)
_SEASON_RE = re.compile(
    r"(?<![a-z])(summer|sommer|ete|verano|estate|lato|vara|zomer|autumn|fall|herbst|automne|otono|autunno|jesien|toamna|herfst|spring|fruhling|fruhjahr|printemps|primavera|wiosna|primavara|lente|winter|hiver|invierno|inverno|zima|iarna)(?![a-z])"
)
_SEASON_MAP = {
    "summer": "Summer", "sommer": "Summer", "ete": "Summer", "verano": "Summer", "estate": "Summer",
    "lato": "Summer", "vara": "Summer", "zomer": "Summer",
    "autumn": "Autumn", "fall": "Autumn", "herbst": "Autumn", "automne": "Autumn", "otono": "Autumn",
    "autunno": "Autumn", "jesien": "Autumn", "toamna": "Autumn", "herfst": "Autumn",
    "spring": "Spring", "fruhling": "Spring", "fruhjahr": "Spring", "printemps": "Spring",
    "primavera": "Spring", "wiosna": "Spring", "primavara": "Spring", "lente": "Spring",
    "winter": "Winter", "hiver": "Winter", "invierno": "Winter", "inverno": "Winter", "zima": "Winter", "iarna": "Winter",
}
_START_PHRASE = re.compile(
    r"(start(?:ing)?(?: date)?|starts|commenc\w*|beginn\w*|begin(?:ning)?|debut|démarrage|demarrage|inizio|comienzo|incorporaci\w*|start(?:termin|datum)|eintritt|ab)\s*(?:date)?\s*(?:is|will be|:|-|in|on|from|im|en|le|a partire da|ab|the|of|early|mid|late|\s)*\s*(?:\d{1,2}(?:st|nd|rd|th)?\.?\s*(?:of\s*)?)?$",
    re.I,
)
_FROM_PHRASE = re.compile(r"(from|von|du|de|dal|desde|od)\s*(?:the\s*)?(?:\d{1,2}(?:st|nd|rd|th)?\.?\s*(?:of\s*)?)?$", re.I)
_NUMERIC = [
    re.compile(r"\b2027-(0[1-9]|1[0-2])-\d{2}\b"),
    re.compile(r"\b\d{1,2}[./](0?[1-9]|1[0-2])[./]2027\b"),
    re.compile(r"\b(0?[1-9]|1[0-2])[./]2027\b"),
]
_YEAR = re.compile(r"(?<!\d)2027(?!\d)")
_OTHER_YEAR = re.compile(r"(?<!\d)(2024|2025|2026|2028)(?!\d)")


def _strip(text: str) -> str:
    text = (text or "").replace("ß", "ss").replace("ł", "l").replace("Ł", "L")
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _month_of(token: str) -> int:
    return _CASED_TO_MONTH.get(token) or _WORD_TO_MONTH[token.lower()]


def _sentence_start(text: str, pos: int, limit: int = 90) -> int:
    lo = max(0, pos - limit)
    seg = text[lo:pos]
    cut = max(seg.rfind(". "), seg.rfind("\n"), seg.rfind("! "), seg.rfind("? "), seg.rfind("; "))
    return lo + cut + 1 if cut >= 0 else lo


def _months_in(seg: str, base: int, full: str) -> list[tuple[int, int, int]]:
    out = []
    for m in _MONTH_RE.finditer(seg):
        token = m.group(0)
        start = base + m.start()
        if _DEADLINE.search(full[max(0, start - 60):start]):
            continue
        out.append((start, start + len(token), _month_of(token)))
    return out


def _group(months: list[tuple[int, int, int]], text: str) -> tuple[list[int], list[tuple[int, int]]]:
    singles: list[int] = []
    ranges: list[tuple[int, int]] = []
    i = 0
    while i < len(months):
        if i + 1 < len(months):
            between = text[months[i][1]:months[i + 1][0]]
            if _RANGE_SEP.match(between):
                ranges.append((months[i][2], months[i + 1][2]))
                i += 2
                continue
        singles.append(months[i][2])
        i += 1
    return singles, ranges


def _bucket(singles: list[int], ranges: list[tuple[int, int]]) -> str:
    if 7 in singles or any(a <= 7 <= b for a, b in ranges if a <= b):
        return "july"
    allm = singles + [a for a, _ in ranges]
    if any(m in (6, 8) for m in allm):
        return "summer"
    return "other"


def _label(singles: list[int], ranges: list[tuple[int, int]], year: str, day: str | None) -> str:
    suffix = f" {year}" if year else ""
    if ranges and not singles:
        a, b = ranges[0]
        if a == b:
            return f"{MONTH_NAMES[a - 1]}{suffix}"
        return f"{MONTH_NAMES[a - 1]} – {MONTH_NAMES[b - 1]}{suffix}"
    ms = sorted(set(singles + [a for a, _ in ranges]))
    if len(ms) == 1:
        if day:
            return f"{int(day)} {MONTH_NAMES[ms[0] - 1]}{suffix}"
        return f"{MONTH_NAMES[ms[0] - 1]}{suffix}"
    names = [MONTH_NAMES[m - 1] for m in ms]
    return ", ".join(names[:-1]) + " or " + names[-1] + suffix


def _explicit(text: str) -> tuple[list[int], list[tuple[int, int]], str | None] | None:
    found: list[tuple[int, int, int]] = []
    day = None
    for ym in _YEAR.finditer(text):
        pos = ym.start()
        lo = _sentence_start(text, pos)
        seg = text[lo:pos]
        months = _months_in(seg, lo, text)
        months = [m for m in months if not _OTHER_YEAR.search(text[m[1]:pos])]
        if not months:
            continue
        last = months[-1]
        if pos - last[1] > 40:
            continue
        keep = [last]
        for prev in reversed(months[:-1]):
            if keep[0][0] - prev[1] <= 40:
                keep.insert(0, prev)
            else:
                break
        found.extend(keep)
        if day is None:
            around = text[max(0, keep[0][0] - 12):keep[0][1] + 6]
            dm = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\.?\s*(?:of\s*)?$", text[max(0, keep[0][0] - 12):keep[0][0]]) or re.search(r"^\s*(\d{1,2})(?:st|nd|rd|th)?\b", text[keep[0][1]:keep[0][1] + 6])
            if dm and len(keep) == 1:
                day = dm.group(1)
            del around
    for pat in _NUMERIC:
        for nm in pat.finditer(text):
            if _DEADLINE.search(text[max(0, nm.start() - 60):nm.start()]):
                continue
            found.append((nm.start(), nm.end(), int(nm.group(1))))
    if not found:
        return None
    found = sorted(set(found))
    singles, ranges = _group(found, text)
    return singles, ranges, day


def _phrase(text: str) -> tuple[list[int], list[tuple[int, int]]] | None:
    months = []
    for m in _MONTH_RE.finditer(text):
        before = text[max(0, m.start() - 45):m.start()]
        if _DEADLINE.search(before):
            continue
        if _START_PHRASE.search(before) or _FROM_PHRASE.search(before):
            after = text[m.end():m.end() + 12]
            if _OTHER_YEAR.match(after.strip()):
                continue
            months.append((m.start(), m.end(), _month_of(m.group(0))))
            nxt = _MONTH_RE.search(text, m.end(), m.end() + 30)
            if nxt and _RANGE_SEP.match(text[m.end():nxt.start()]):
                months.append((nxt.start(), nxt.end(), _month_of(nxt.group(0))))
            break
    if not months:
        return None
    singles, ranges = _group(sorted(set(months)), text)
    return singles, ranges


def _season(text: str) -> str | None:
    low = text.lower()
    for ym in _YEAR.finditer(low):
        seg = low[max(0, ym.start() - 25):ym.start()]
        hits = list(_SEASON_RE.finditer(seg))
        if hits:
            return _SEASON_MAP[hits[-1].group(1)]
    return None


def extract_start(title: str, description: str = "", assume_year: bool = False) -> tuple[str, int | None, str]:
    raw = f"{title or ''}\n{(description or '')[:3000]}"
    text = _strip(raw)

    exp = _explicit(text)
    if exp:
        singles, ranges, day = exp
        months = singles + [a for a, _ in ranges]
        return _label(singles, ranges, "2027", day), min(months), _bucket(singles, ranges)

    ph = _phrase(text)
    if ph:
        singles, ranges = ph
        months = singles + [a for a, _ in ranges]
        year = "2027" if (_YEAR.search(text) or assume_year) else ""
        return _label(singles, ranges, year, None), min(months), _bucket(singles, ranges)

    season = _season(text)
    if season:
        return f"{season} 2027", None, "summer" if season == "Summer" else "other"

    t = _strip(title or "").lower()
    if re.search(r"(?<![a-z])summer(?![a-z])", t) and not _OTHER_YEAR.search(t):
        return ("Summer 2027" if _YEAR.search(text) else "Summer"), None, "summer"

    if assume_year:
        months = []
        for m in _MONTH_RE.finditer(text):
            months.append((m.start(), m.end(), _month_of(m.group(0))))
        if months:
            singles, ranges = _group(months, text)
            ms = singles + [a for a, _ in ranges]
            return _label(singles, ranges, "", None), min(ms), _bucket(singles, ranges)
        low = text.lower()
        sm = _SEASON_RE.search(low)
        if sm:
            s = _SEASON_MAP[sm.group(1)]
            return s, None, "summer" if s == "Summer" else "other"

    if _YEAR.search(text):
        return "2027 (month not stated)", None, "other"
    return "Not stated", None, "none"


def from_label(label: str) -> tuple[str, int | None, str]:
    label = (label or "").strip()
    if not label or label.lower() == "not stated":
        return "Not stated", None, "none"
    _, month, bucket = extract_start(label, "", assume_year=True)
    if bucket == "other" and month is None and "2027" not in label:
        bucket = "other"
    return label, month, bucket


def from_term(term: str) -> tuple[str, int | None, str] | None:
    t = (term or "").strip()
    m = re.match(r"(?i)(summer|spring|fall|autumn|winter)\s*(2027)", t)
    if not m:
        return None
    season = {"fall": "Autumn"}.get(m.group(1).lower(), m.group(1).capitalize())
    return f"{season} 2027", None, "summer" if season == "Summer" else "other"


RICHNESS = {"july": 3, "summer": 2, "other": 1, "none": 0}


def richness(label: str, month: int | None, bucket: str) -> int:
    score = 0
    if month is not None:
        score += 10
    if bucket != "none":
        score += 5
    if label and "not stated" not in label.lower():
        score += 1
    return score
