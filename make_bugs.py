import json
from pathlib import Path

BUGS = {
"01_pagination": dict(
    files={
        "paginate.py": '''def paginate(items, page, per_page):
    """Return the items on the given 1-based page."""
    start = (page - 1) * per_page
    end = start + per_page - 1
    return items[start:end]


def total_pages(n_items, per_page):
    return -(-n_items // per_page)
''',
        "test_paginate.py": '''from paginate import paginate, total_pages


def test_total_pages():
    assert total_pages(10, 3) == 4


def test_empty():
    assert paginate([], 1, 5) == []
''',
    },
    report=dict(symptom="Every page is missing its last item",
        steps_to_reproduce=["from paginate import paginate", "paginate([1,2,3,4,5,6], 1, 3)", "returns [1, 2] instead of [1, 2, 3]"],
        expected="paginate([1,2,3,4,5,6], 1, 3) == [1, 2, 3]", actual="returns [1, 2]",
        suspected_area="paginate.py paginate()", search_keywords=["paginate", "page", "per_page"], confidence=0.9)),
"02_discount": dict(
    files={
        "pricing.py": '''def apply_discount(price, percent):
    """Apply a percentage discount. percent is 0-100, e.g. 20 means 20% off."""
    return round(price * (1 - percent), 2)
''',
        "test_pricing.py": '''from pricing import apply_discount


def test_no_discount():
    assert apply_discount(100.0, 0) == 100.0
''',
    },
    report=dict(symptom="A 20% discount produces a huge negative price",
        steps_to_reproduce=["from pricing import apply_discount", "apply_discount(50.0, 20)", "returns -950.0"],
        expected="40.0", actual="-950.0", suspected_area="pricing.py apply_discount()",
        search_keywords=["apply_discount", "percent"], confidence=0.9)),
"03_mutable_default": dict(
    files={
        "tags.py": '''def add_tag(tag, tags=[]):
    """Add a tag to a list of tags and return the list. Starts a fresh list if none is given."""
    tags.append(tag)
    return tags
''',
        "test_tags.py": '''from tags import add_tag


def test_add_to_existing():
    assert add_tag("a", ["x"]) == ["x", "a"]
''',
    },
    report=dict(symptom="Tags from earlier calls leak into later calls",
        steps_to_reproduce=["from tags import add_tag", "add_tag('a')", "add_tag('b')", "second call returns ['a', 'b']"],
        expected="['b']", actual="['a', 'b']", suspected_area="tags.py add_tag()",
        search_keywords=["add_tag", "tags"], confidence=0.85)),
"04_empty_average": dict(
    files={
        "stats.py": '''def average(values):
    """Mean of values. Returns 0.0 for an empty list or None."""
    return sum(values) / len(values)
''',
        "test_stats.py": '''from stats import average


def test_average():
    assert average([1, 2, 3]) == 2
''',
    },
    report=dict(symptom="average() crashes on empty input",
        steps_to_reproduce=["from stats import average", "average([])", "ZeroDivisionError", "average(None) raises TypeError"],
        expected="0.0 for [] and None", actual="ZeroDivisionError / TypeError", suspected_area="stats.py average()",
        search_keywords=["average", "ZeroDivisionError"], confidence=0.9)),
"05_two_file_cache": dict(
    files={
        "cache.py": '''class Cache:
    def __init__(self):
        self._data = {}

    @staticmethod
    def make_key(user_id, lang):
        return str(user_id)

    def get(self, user_id, lang):
        return self._data.get(self.make_key(user_id, lang))

    def set(self, user_id, lang, value):
        self._data[self.make_key(user_id, lang)] = value
''',
        "service.py": '''from cache import Cache

GREETINGS = {"en": "Hello", "fr": "Bonjour"}


class GreetingService:
    def __init__(self):
        self.cache = Cache()

    def greet(self, user_id, name, lang="en"):
        cached = self.cache.get(user_id, lang)
        if cached:
            return cached
        msg = f"{GREETINGS[lang]}, {name}!"
        self.cache.set(user_id, lang, msg)
        return msg
''',
        "test_service.py": '''from service import GreetingService


def test_greet_english():
    assert GreetingService().greet(1, "Ann") == "Hello, Ann!"
''',
    },
    report=dict(symptom="A user who switches language still gets the greeting in the old language",
        steps_to_reproduce=["s = GreetingService()", "s.greet(1, 'Ann', 'en') -> 'Hello, Ann!'", "s.greet(1, 'Ann', 'fr') -> still 'Hello, Ann!'"],
        expected="'Bonjour, Ann!' for French", actual="'Hello, Ann!'", suspected_area="service.py greet() language handling",
        search_keywords=["greet", "lang", "cache"], confidence=0.7)),
"06_misleading_report": dict(
    files={
        "utils.py": '''def clean(name):
    return name.strip().lower()
''',
        "inventory.py": '''from utils import clean


def needs_reorder(stock, threshold):
    """An item needs reordering when stock is at or below the threshold."""
    return stock < threshold


def low_items(inventory, threshold):
    return sorted(clean(n) for n, s in inventory.items() if needs_reorder(s, threshold))
''',
        "test_inventory.py": '''from inventory import needs_reorder, low_items


def test_needs_reorder_basic():
    assert needs_reorder(0, 5)
    assert not needs_reorder(10, 5)


def test_low_items_names_cleaned():
    assert low_items({" Pen ": 1, "Ink": 50}, 5) == ["pen"]
''',
    },
    report=dict(symptom="Items whose stock is exactly at the threshold are not listed as low",
        steps_to_reproduce=["from inventory import low_items", "low_items({'Pen': 5, 'Ink': 50}, 5)", "returns [] but 'pen' should be listed"],
        expected="['pen']", actual="[]", suspected_area="utils.py clean() name normalization drops the item",
        search_keywords=["clean", "low_items", "utils"], confidence=0.6)),
}

for name, b in BUGS.items():
    root = Path("bugs") / name
    (root / "repo").mkdir(parents=True, exist_ok=True)
    for fname, text in b["files"].items():
        (root / "repo" / fname).write_text(text, encoding="utf-8", newline="\n")
    (root / "report.json").write_text(json.dumps(b["report"], indent=2), encoding="utf-8")
print(f"Created {len(BUGS)} bugs in bugs/")