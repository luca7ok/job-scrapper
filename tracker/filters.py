from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULTS = {
    "swe_strong": r"software (engineer|dev)|developer|\bSWE\b|\bSDE\b|full[- ]?stack|back[- ]?end|front[- ]?end|site reliability|forward deployed",
    "swe_broad": r"programm(er|ier|ing)|programist|programator|platform eng|infrastructure eng|cloud eng|mobile|\bios\b|android|web eng|application (dev|eng)|systems eng|developpeur|développeur|entwickl|informatik|machine learning eng|\bML eng|\bAI eng|security eng|test eng|\bQA\b|automation eng|devops|mlops|data eng|\bgame|gameplay|tools eng|compiler|embedded software|firmware|engineering intern|graduate engineer",
    "swe_strong_exclude": r"process developer|business develop|finance and accounting|developer relations manager",
    "swe_broad_exclude": r"mechanical|electrical|electronic|elektronik|elektrotechnik|mechanik|maschinenbau|civil|structural|chemical|process eng|manufactur|hardware|silicon|asic|\brtl\b|analog|\bRF\b|\bsales\b|\baccount|marketing|finance|\baudit|\btax\b|\blegal\b|\bHR\b|trader|quantitative research|research scientist|aerospace|biomed|clinical|supply chain|procurement|logistics|consult(ant|ing)|business analyst|product manag|design verification|physical design|validation eng|optical|photonic|materials|environmental",
    "always_exclude": r"apprentic|duales studium|unsolicited|spontaneous application|candidature spontan|initiativbewerbung|uopfordret|talent pool|talent community|dual(es)? studium|werkstudent|working student|\b(senior|sr\.?|staff|principal|lead|manager|director|head of|III|IV|experienced|architect)\b|fpga|layout",
    "intern": r"\bintern\b|\binterns\b|internship|\bstage\b|stagiaire|praktik|stagiu|\bsummer\b|placement|\bco-?op\b|tirocinio|\bbeca\b|becario|staż|\bstaz\b",
    "new_grad": r"graduate|new grad|\bjunior\b|\bjr\.?\b|\bentry\b|entry[- ]level|early career|associate software|academy|trainee|\bprogram(me)?\b|absolvent|berufseinsteiger|\bjeune diplom",
    "phd": r"\bph\.?d\b|doctoral|\bdoktorand",
    "drop_years": r"\b(2024|2025)\b|(summer|spring|winter|fall|autumn)\s*2026|2026\s*(start|intern)",
}


@dataclass
class FilterSet:
    swe_strong: re.Pattern
    swe_broad: re.Pattern
    swe_strong_exclude: re.Pattern
    swe_broad_exclude: re.Pattern
    always_exclude: re.Pattern
    intern: re.Pattern
    new_grad: re.Pattern
    phd: re.Pattern
    drop_years: re.Pattern

    @classmethod
    def from_config(cls, cfg: dict | None = None) -> "FilterSet":
        merged = dict(DEFAULTS)
        for key, value in (cfg or {}).items():
            if key in merged and value:
                merged[key] = value
        return cls(**{k: re.compile(v, re.I) for k, v in merged.items()})

    def is_swe(self, title: str) -> bool:
        t = title or ""
        if self.always_exclude.search(t):
            return False
        if self.swe_strong.search(t):
            return not self.swe_strong_exclude.search(t)
        return bool(self.swe_broad.search(t)) and not self.swe_broad_exclude.search(t)

    def kind(self, title: str) -> str | None:
        t = title or ""
        if self.phd.search(t):
            return "PhD / research"
        if self.intern.search(t):
            return "Internship"
        if self.new_grad.search(t):
            return "New grad"
        return None

    def is_entry_level(self, title: str) -> bool:
        return self.kind(title) is not None

    def is_2027_relevant(self, title: str) -> bool:
        return not self.drop_years.search(title or "")


_default: FilterSet | None = None


def default() -> FilterSet:
    global _default
    if _default is None:
        _default = FilterSet.from_config()
    return _default


def is_swe(title: str) -> bool:
    return default().is_swe(title)


def is_entry_level(title: str) -> bool:
    return default().is_entry_level(title)


def is_2027_relevant(title: str) -> bool:
    return default().is_2027_relevant(title)


def kind_of(title: str) -> str | None:
    return default().kind(title)
