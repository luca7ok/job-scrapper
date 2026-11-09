import pytest

from tracker.dates import extract_start, from_label, from_term


@pytest.mark.parametrize("title,desc,label,month,bucket", [
    ("SWE Intern", "Start date: July 1st, 2027.", "1 July 2027", 7, "july"),
    ("SWE Intern", "Internship starts 1 July 2027 in Amsterdam", "1 July 2027", 7, "july"),
    ("Intern", "Start: July 2027", "July 2027", 7, "july"),
    ("Intern", "The internship runs from 21st June - 27th August 2027.", "June – August 2027", 6, "july"),
    ("Praktikum", "Beginn: Juli 2027", "July 2027", 7, "july"),
    ("Stage", "Début : juillet 2027", "July 2027", 7, "july"),
    ("Prácticas", "Inicio julio 2027", "July 2027", 7, "july"),
    ("Stage", "inizio luglio 2027", "July 2027", 7, "july"),
    ("Staż", "od lipca 2027", "July 2027", 7, "july"),
    ("Stagiu", "începând cu iulie 2027", "July 2027", 7, "july"),
    ("Stage", "start juli 2027", "July 2027", 7, "july"),
    ("Intern", "starting in June 2027", "June 2027", 6, "summer"),
    ("Intern", "from June to September 2027", "June – September 2027", 6, "july"),
    ("Intern", "May, June or July 2027 start", "May, June or July 2027", 5, "july"),
    ("Intern", "start date: September 2027", "September 2027", 9, "other"),
    ("Summer Intern 2027", "", "Summer 2027", None, "summer"),
    ("Intern", "autumn 2027", "Autumn 2027", None, "other"),
    ("Intern", "fall 2027", "Autumn 2027", None, "other"),
    ("Intern", "Spring 2027 start", "Spring 2027", None, "other"),
    ("Intern", "winter 2027", "Winter 2027", None, "other"),
    ("Software Engineer Intern - 2027", "", "2027 (month not stated)", None, "other"),
    ("Intern", "", "Not stated", None, "none"),
    ("Summer Internship", "", "Summer", None, "summer"),
])
def test_extract(title, desc, label, month, bucket):
    assert extract_start(title, desc) == (label, month, bucket)


def test_deadline_is_not_start():
    assert extract_start("Intern", "Applications close 31 March 2027. Start in July 2027.") == ("July 2027", 7, "july")
    assert extract_start("Intern", "Apply by 15 January 2027. The programme begins in September 2027.")[1] == 9


def test_english_may_verb_ignored():
    assert extract_start("Intern", "You may join our team in 2027")[2] == "other"


def test_only_first_3000_chars():
    desc = "x" * 3100 + " July 2027"
    assert extract_start("Intern", desc)[2] == "none"


@pytest.mark.parametrize("label,month,bucket", [
    ("July 2027", 7, "july"),
    ("May, June or July 2027", 5, "july"),
    ("June 21, 2027", 6, "summer"),
    ("Summer 2027", None, "summer"),
    ("July–Sept (2026 pattern)", 7, "july"),
    ("Not stated", None, "none"),
    ("Early or late 2027", None, "other"),
])
def test_manual_labels(label, month, bucket):
    out = from_label(label)
    assert out[1:] == (month, bucket)
    assert out[0] == label


def test_terms():
    assert from_term("Summer 2027") == ("Summer 2027", None, "summer")
    assert from_term("Fall 2027") == ("Autumn 2027", None, "other")
    assert from_term("Summer 2026") is None
