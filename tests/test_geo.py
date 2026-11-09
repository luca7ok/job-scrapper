import pytest

from tracker.geo import countries_from_names, europe_countries, europe_country

CASES = [
    ("Berlin, Germany", ["DE"]),
    ("Munich, Germany +2", ["DE"]),
    ("München", ["DE"]),
    ("Köln, Germany", ["DE"]),
    ("Berlin, DE", ["DE"]),
    ("Stuttgart, Baden-Württemberg, Germany", ["DE"]),
    ("Germany, Munich", ["DE"]),
    ("Zürich, Switzerland", ["CH"]),
    ("Zurich, Zurich, Switzerland", ["CH"]),
    ("Kraków, Poland", ["PL"]),
    ("Wrocław", ["PL"]),
    ("Remote - Lublin, Poland", ["PL"]),
    ("Iași", ["RO"]),
    ("Cluj-Napoca, Romania", ["RO"]),
    ("Bucureşti", ["RO"]),
    ("paris, île-de-france, france", ["FR"]),
    ("Grenoble, Auvergne-rhône-alpes, France", ["FR"]),
    ("Amsterdam, The Netherlands", ["NL"]),
    ("Best, Noord-Brabant", ["NL"]),
    ("Dublin, Ireland", ["IE"]),
    ("Belfast, Northern Ireland", ["GB"]),
    ("London, UK", ["GB"]),
    ("Remote in UK", ["GB"]),
    ("Newtownabbey, UK", ["GB"]),
    ("Lisbon, PT", ["PT"]),
    ("Vilnius, Lithuania", ["LT"]),
    ("Skopje", ["MK"]),
    ("Belgrade, Serbia", ["RS"]),
    ("Lviv", ["UA"]),
    ("Leonding, Upper Austria, Austria", ["AT"]),
    ("Athens, Greece +1", ["GR"]),
    ("Remote - Europe", ["EU"]),
    ("EMEA", ["EU"]),
    ("Amsterdam; Berlin", ["NL", "DE"]),
    ("Zurich; Munich; Paris; Dublin; Stockholm", ["CH", "DE", "FR", "IE", "SE"]),
    ("Remote in Germany; Shakopee, MN", ["DE"]),
    ("Birmingham, AL", []),
    ("Cambridge, MA", []),
    ("Paris, TX", []),
    ("Dublin, CA", []),
    ("London, ON, Canada", []),
    ("Sydney, New South Wales", []),
    ("Providence, Rhode Island", []),
    ("Shanghai, China", []),
    ("San Francisco, CA", []),
    ("Remote, US", []),
    ("Bengaluru, Karnataka, India", []),
    ("Istanbul, Turkey", []),
    ("Remote", []),
    ("Hybrid", []),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_europe_countries(text, expected):
    assert europe_countries(text) == expected


def test_at_least_30_cases():
    assert len(CASES) >= 30


def test_turkey_opt_in():
    assert europe_country("Istanbul, Turkey", include_tr=True) == "TR"
    assert europe_country("Istanbul, Turkey") is None


def test_single_helper():
    assert europe_country("Tallinn") == "EE"
    assert europe_country("New York, NY") is None


@pytest.mark.parametrize("text,expected", [
    ("Netherlands", ["NL"]),
    ("Czechia", ["CZ"]),
    ("UK", ["GB"]),
    ("Switzerland, Germany, France, Ireland, Sweden", ["CH", "DE", "FR", "IE", "SE"]),
    ("North Macedonia", ["MK"]),
    ("Czechia, Germany, Netherlands, Poland, Serbia, Spain, Cyprus", ["CZ", "DE", "NL", "PL", "RS", "ES", "CY"]),
])
def test_manual_country_names(text, expected):
    assert countries_from_names(text) == expected


@pytest.mark.parametrize("locs,expected", [
    (["Bucharest", "Romania", "Bucharest, Romania"], "Bucharest, Romania"),
    (["Romania, Bucharest", "Bucharest, Romania"], "Romania, Bucharest"),
    (["Basel", "Switzerland", "Basel, Switzerland"], "Basel, Switzerland"),
    (["Amsterdam", "Berlin"], "Amsterdam; Berlin"),
    (["Cork, Ireland", "Cork, County Cork, Ireland"], "Cork, County Cork, Ireland"),
])
def test_clean_locations(locs, expected):
    from tracker.geo import clean_locations
    assert clean_locations(locs) == expected
