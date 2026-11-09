import pytest

from tracker import config
from tracker.filters import FilterSet

FS = FilterSet.from_config(config.load().filters)

SWE_IN = [
    "Full-Stack Developer Graduate - Fullstack",
    "Test Engineer - Modules",
    "Compiler Engineering Intern",
    "Graduate Software Engineer",
    "Robotics Data Engineer (m/f/d) Data Generation & Curation",
    "Application Engineer Intern",
    "Software Engineer Intern - Sovereign AI Systems",
    "Machine Learning Engineer (m/f/d) VLA Training & Evaluation",
    "Automation Engineer Intern - Summer 2027",
    "Application Security Engineer (all genders)",
    "Junior Full Stack R&D Software Developer",
    "Engineering Graduate Programme - Backend",
    "AI and Software Engineer Intern - Automotive MPUs",
    "Associate Software Engineer",
    "Firmware Engineer Intern",
    "Mobile Software Developer - Android / iOS",
    "Real-Time Software Engineer Intern",
    "Technology Developer Graduate Programme",
    "Software Engineering Intern",
    "Test Software Engineer Intern",
    "Tradeweb International Intern Program - JavaScript UI Developer - Technology Division",
    "Software Engineer New Grad - Instruments team",
    "Forward Deployed Software Engineer New Grad - Commercial",
    "Site Reliability Engineer Intern",
    "Junior Software Developer for C# - m/w/d",
    "Praktikum Softwareentwicklung (m/w/d)",
    "Stage - Développeur Full Stack H/F",
    "Programista Java Junior",
    "Junior QA Engineer",
    "DevOps Engineer Intern",
    "Game Programmer Intern",
    "2027 Software Dev Engineer Intern - Netherlands",
]

SWE_OUT = [
    "Research Scientist Intern",
    "Data Analyst Project Intern - TikTok Shop - Data Science",
    "Graduate Trader",
    "Data Science Intern",
    "Customer Success Operations Associate",
    "Sales Analyst & Business Coordinator",
    "Human Resources Business Partner",
    "Digital Product Manager Apprentice",
    "Chemist/Chemical Engineer Intern - Summer 2027",
    "Shopper Insights Intern",
    "Duales Studium (B.Sc.) Wirtschaftsinformatik 2027",
    "Werkstudent (m/w/d) - Karriereberatung, Coaching und Marketing",
    "Retail Sales Specialist",
    "Senior Mechanical Engineer - Robotic Systems",
    "Quant Intern",
    "Senior AI / Reinforcement Learning Engineer (m/f/d)",
    "Principal Network Security Engineer",
    "Hardware Engineer Intern",
    "Test Engineer Apprentice",
    "Firmware/FPGA Engineer",
    "Hardware Engineer Intern - FPGA/ASIC",
    "Praktikum als HR-Manager (m/w/d)",
    "Senior Full Stack Developer (m/f/d)",
    "Quantitative Research Intern - Multiple Teams",
    "Data Scientist New Grad - Insurance Consulting",
    "Project Management Intern",
    "Programme Executive - Research",
    "UK Analyst Programme",
    "Process Developer Finance and Accounting",
    "Werkstudent Softwareentwicklung (m/w/d)",
    "Staff Software Engineer, Payments",
    "Electrical Engineering Intern",
    "Praktikum im Bereich MEMS & Elektronik – Entwicklung, Charakterisierung",
    "Uopfordret ansøgning til Software Engineering",
    "Initiativbewerbung Softwareentwickler (m/w/d)",
    "Talent Pool: Software Engineering Graduates",
]


@pytest.mark.parametrize("title", SWE_IN)
def test_swe_in(title):
    assert FS.is_swe(title), title


@pytest.mark.parametrize("title", SWE_OUT)
def test_swe_out(title):
    assert not FS.is_swe(title), title


def test_counts_meet_plan():
    assert len(SWE_IN) >= 30 and len(SWE_OUT) >= 30


@pytest.mark.parametrize("title,kind", [
    ("Software Engineer Intern", "Internship"),
    ("Software Engineering Internship 2027", "Internship"),
    ("Stage Développeur Backend", "Internship"),
    ("Praktikum Softwareentwicklung", "Internship"),
    ("Stagiu Software Developer", "Internship"),
    ("Summer Software Engineer", "Internship"),
    ("Graduate Software Engineer", "New grad"),
    ("Junior Backend Developer", "New grad"),
    ("Software Engineer, Early Career", "New grad"),
    ("Engineering Academy - Junior Backend Engineer", "New grad"),
    ("Software Engineering PhD Intern, 2027", "PhD / research"),
    ("Software Engineer", None),
    ("Internal Tools Software Engineer", None),
    ("International Payments Backend Engineer", None),
])
def test_kind(title, kind):
    assert FS.kind(title) == kind


@pytest.mark.parametrize("title,ok", [
    ("Software Engineer Intern - Summer 2027", True),
    ("Software Engineer Intern - Summer 2026", False),
    ("2025 Graduate Software Engineer", False),
    ("Software Engineer 2026 Intern", False),
    ("Software Engineer Intern (Fall 2026)", False),
    ("Graduate Software Engineer 2026/2027", True),
    ("Junior Developer", True),
])
def test_2027_relevance(title, ok):
    assert FS.is_2027_relevant(title) is ok


def test_config_override():
    fs = FilterSet.from_config({"always_exclude": r"\bjava\b"})
    assert not fs.is_swe("Java Software Engineer Intern")
    assert fs.is_swe("Senior Software Engineer")
