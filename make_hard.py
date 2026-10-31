import json
from pathlib import Path


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


BUGS = {
"07_lru_cache": dict(
    files={
        "lru.py": '''from collections import OrderedDict


class LRUCache:
    """Least-recently-used cache. Both get() and put() count as a use."""

    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._d = OrderedDict()

    def get(self, key, default=None):
        if key not in self._d:
            return default
        return self._d[key]

    def put(self, key, value):
        if key in self._d:
            self._d.move_to_end(key)
        self._d[key] = value
        if len(self._d) > self.capacity:
            self._d.popitem(last=False)

    def __len__(self):
        return len(self._d)

    def __contains__(self, key):
        return key in self._d
''',
        "test_lru.py": '''from lru import LRUCache


def test_evicts_oldest():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    assert "a" not in c and "b" in c and "c" in c


def test_get_missing():
    assert LRUCache(1).get("x", 7) == 7
''',
    },
    hidden={
        "test_hidden.py": '''from lru import LRUCache


def test_get_counts_as_use():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    c.put("c", 3)
    assert "a" in c and "b" not in c


def test_put_existing_refreshes():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)
    c.put("c", 3)
    assert c.get("a") == 10 and "b" not in c
''',
    },
    report=dict(symptom="Entries that were just read get thrown out of the cache while untouched ones stay",
        steps_to_reproduce=["c = LRUCache(2)", "c.put('a', 1); c.put('b', 2)", "c.get('a')", "c.put('c', 3)", "'a' is gone"],
        expected="'b' is evicted because 'a' was used more recently", actual="'a' is evicted",
        suspected_area="lru.py put() eviction logic", search_keywords=["evict", "popitem", "LRUCache"], confidence=0.6)),

"08_split_invoice": dict(
    files={
        "billing.py": '''def split_bill(total_cents, n):
    """Split total_cents among n people.

    The shares must add up to total_cents exactly. Shares differ by at most one cent,
    and the earlier people in the list pay the extra cent.
    """
    share = total_cents // n
    return [share] * n
''',
        "invoice.py": '''from billing import split_bill


def format_cents(c):
    return f"{c // 100}.{c % 100:02d}"


def split_invoice(total_cents, names):
    """Return {name: formatted share}. The shares always add up to the invoice total."""
    shares = split_bill(total_cents, len(names))
    return {n: format_cents(s) for n, s in zip(names, shares)}
''',
        "test_invoice.py": '''from billing import split_bill
from invoice import split_invoice


def test_even_split():
    assert split_bill(100, 4) == [25, 25, 25, 25]


def test_invoice_even():
    assert split_invoice(300, ["a", "b"]) == {"a": "1.50", "b": "1.50"}
''',
    },
    hidden={
        "test_hidden.py": '''from billing import split_bill
from invoice import split_invoice


def test_remainder_distributed():
    assert split_bill(100, 3) == [34, 33, 33]
    assert split_bill(1, 3) == [1, 0, 0]
    assert split_bill(0, 2) == [0, 0]


def test_invoice_adds_up():
    out = split_invoice(1000, ["ann", "bob", "cy"])
    assert out == {"ann": "3.34", "bob": "3.33", "cy": "3.33"}
    assert sum(int(v.replace(".", "")) for v in out.values()) == 1000
''',
    },
    report=dict(symptom="An invoice of 10.00 split three ways only collects 9.99",
        steps_to_reproduce=["from invoice import split_invoice", "split_invoice(1000, ['ann','bob','cy'])", "every share is 3.33"],
        expected="shares add up to 10.00 (ann 3.34, bob 3.33, cy 3.33)", actual="3.33 each, one cent is lost",
        suspected_area="invoice.py format_cents rounding", search_keywords=["format_cents", "split_invoice"], confidence=0.5)),

"09_month_end_billing": dict(
    files={
        "dates_util.py": '''def add_months(d, months):
    """Add months to a date. If the day does not exist in the target month it is clamped
    to the last day of that month (Jan 31 + 1 month = Feb 28, or Feb 29 in a leap year)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return d.replace(year=year, month=month)
''',
        "subscription.py": '''from dates_util import add_months


def billing_dates(start, count):
    """The first `count` billing dates: `start`, then once a month.

    Every date is anchored to the day-of-month of `start` (clamped when a month is shorter),
    so a subscription starting on Jan 31 bills on Jan 31, Feb 28/29, Mar 31, Apr 30, ...
    """
    dates = [start]
    while len(dates) < count:
        dates.append(add_months(dates[-1], 1))
    return dates
''',
        "test_subscription.py": '''from datetime import date

from dates_util import add_months
from subscription import billing_dates


def test_add_months_simple():
    assert add_months(date(2024, 1, 15), 1) == date(2024, 2, 15)
    assert add_months(date(2024, 12, 1), 1) == date(2025, 1, 1)


def test_billing_dates_mid_month():
    assert billing_dates(date(2024, 1, 15), 3) == [date(2024, 1, 15), date(2024, 2, 15), date(2024, 3, 15)]
''',
    },
    hidden={
        "test_hidden.py": '''from datetime import date

from dates_util import add_months
from subscription import billing_dates


def test_clamps_month_end():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
    assert add_months(date(2024, 3, 31), -1) == date(2024, 2, 29)


def test_billing_anchored_to_start_day():
    assert billing_dates(date(2024, 1, 31), 4) == [
        date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30)]
''',
    },
    report=dict(symptom="Creating a subscription that starts on the 31st crashes with a ValueError",
        steps_to_reproduce=["from subscription import billing_dates", "from datetime import date",
                            "billing_dates(date(2024, 1, 31), 3)", "ValueError: day is out of range for month"],
        expected="a list of 3 monthly billing dates", actual="ValueError", suspected_area="subscription.py billing_dates()",
        search_keywords=["billing_dates", "add_months", "ValueError"], confidence=0.8)),

"10_leaderboard_ties": dict(
    files={
        "leaderboard.py": '''def rank(scores):
    """scores: dict of name -> score. Returns a list of (rank, name), highest score first.

    Ties share a rank and the next rank is skipped (competition ranking: 1, 2, 2, 4).
    Players with the same score are listed in alphabetical order.
    """
    ordered = sorted(scores.items(), key=lambda kv: -kv[1])
    out = []
    for i, (name, _score) in enumerate(ordered, 1):
        out.append((i, name))
    return out
''',
        "test_leaderboard.py": '''from leaderboard import rank


def test_no_ties():
    assert rank({"a": 3, "b": 9}) == [(1, "b"), (2, "a")]


def test_empty():
    assert rank({}) == []
''',
    },
    hidden={
        "test_hidden.py": '''from leaderboard import rank


def test_ties_share_rank_and_skip():
    assert rank({"a": 9, "b": 7, "c": 7, "d": 1}) == [(1, "a"), (2, "b"), (2, "c"), (4, "d")]


def test_ties_alphabetical():
    assert rank({"z": 5, "m": 5, "c": 3}) == [(1, "m"), (1, "z"), (3, "c")]
''',
    },
    report=dict(symptom="Two players with the same score are shown at different positions on the leaderboard",
        steps_to_reproduce=["from leaderboard import rank", "rank({'ann': 5, 'bob': 5})", "returns [(1, 'ann'), (2, 'bob')]"],
        expected="both players share the same rank", actual="they get ranks 1 and 2",
        suspected_area="leaderboard.py rank()", search_keywords=["rank", "ties"], confidence=0.85)),

"11_retry_decorator": dict(
    files={
        "retry.py": '''import functools
import time


def retry(times, exceptions=(Exception,), sleep=time.sleep, base=0.1):
    """Call the function up to `times` times in total.

    After a failed attempt number k (0-based) wait base * 2**k seconds, but do not wait after the
    last attempt. If every attempt fails, re-raise the last exception.
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last = None
            for attempt in range(times - 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last = e
                    sleep(base * 2 ** attempt)
            return None
        return wrapper
    return deco
''',
        "test_retry.py": '''from retry import retry


def test_first_try_succeeds():
    @retry(3)
    def f():
        return 5
    assert f() == 5
''',
    },
    hidden={
        "test_hidden.py": '''import pytest

from retry import retry


def test_succeeds_on_last_attempt():
    calls, slept = [], []

    @retry(3, sleep=slept.append)
    def f():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("boom")
        return "ok"

    assert f() == "ok"
    assert len(calls) == 3
    assert slept == [0.1, 0.2]


def test_reraises_last_exception():
    slept = []

    @retry(3, sleep=slept.append)
    def f():
        raise KeyError("x")

    with pytest.raises(KeyError):
        f()
    assert slept == [0.1, 0.2]
''',
    },
    report=dict(symptom="A flaky API call that works on the third try returns None instead of its result",
        steps_to_reproduce=["wrap a function that fails twice then returns 'ok' with @retry(3)", "call it", "gets None"],
        expected="'ok'", actual="None", suspected_area="retry.py wrapper()",
        search_keywords=["retry", "wrapper"], confidence=0.8)),

"12_checkout": dict(
    files={
        "requirements.txt": "pytest\n",
        "conftest.py": "",
        "README.md": "# shop\n\nSmall checkout library. All money amounts are integer cents.\n",
        "shop/__init__.py": "",
        "shop/models.py": '''from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    sku: str
    price_cents: int
    qty: int = 1
    taxable: bool = True
''',
        "shop/pricing.py": '''TAX_RATE_PERCENT = 20


def subtotal(items):
    return sum(i.price_cents * i.qty for i in items)


def taxable_subtotal(items):
    return sum(i.price_cents * i.qty for i in items if i.taxable)


def tax_cents(taxable_cents):
    """Tax on an amount, rounded half up."""
    return (taxable_cents * TAX_RATE_PERCENT + 50) // 100
''',
        "shop/coupons.py": '''def discount_cents(coupon, subtotal_cents):
    """coupon is ('percent', 10) or ('fixed', 500). A discount never exceeds the subtotal."""
    kind, value = coupon
    if kind == "percent":
        return subtotal_cents * value // 100
    if kind == "fixed":
        return min(value, subtotal_cents)
    raise ValueError(f"unknown coupon kind {kind}")
''',
        "shop/checkout.py": '''from .coupons import discount_cents
from .pricing import subtotal, tax_cents, taxable_subtotal


def checkout(items, coupon=None):
    """All amounts are integer cents. total = subtotal - discount + tax.

    The discount is spread over taxable and non-taxable items in proportion to their value:
    taxable_discount = discount * taxable_subtotal // subtotal (integer floor division).
    Tax is charged on the taxable part AFTER its share of the discount.
    """
    sub = subtotal(items)
    discount = discount_cents(coupon, sub) if coupon else 0
    tax = tax_cents(taxable_subtotal(items))
    return {"subtotal": sub, "discount": discount, "tax": tax, "total": sub - discount + tax}
''',
        "tests/test_checkout.py": '''from shop.checkout import checkout
from shop.models import Item


def test_no_coupon():
    r = checkout([Item("a", 1000, 2)])
    assert r == {"subtotal": 2000, "discount": 0, "tax": 400, "total": 2400}


def test_non_taxable_item():
    r = checkout([Item("a", 1000), Item("b", 500, taxable=False)])
    assert r["tax"] == 200 and r["total"] == 1700


def test_coupon_discount_amount():
    r = checkout([Item("a", 1000, 2)], ("percent", 10))
    assert r["discount"] == 200
''',
        "tests/test_coupons.py": '''import pytest

from shop.coupons import discount_cents


def test_percent():
    assert discount_cents(("percent", 10), 2000) == 200


def test_fixed_capped():
    assert discount_cents(("fixed", 5000), 2000) == 2000


def test_unknown():
    with pytest.raises(ValueError):
        discount_cents(("bogus", 1), 100)
''',
    },
    hidden={
        "tests/test_hidden.py": '''from shop.checkout import checkout
from shop.models import Item

MIXED = [Item("a", 1000), Item("b", 1000, taxable=False)]


def test_percent_coupon_reduces_tax():
    r = checkout(MIXED, ("percent", 10))
    assert r == {"subtotal": 2000, "discount": 200, "tax": 180, "total": 1980}


def test_fixed_coupon_reduces_tax():
    r = checkout(MIXED, ("fixed", 500))
    assert r == {"subtotal": 2000, "discount": 500, "tax": 150, "total": 1650}


def test_full_discount_means_no_tax():
    r = checkout([Item("a", 1000)], ("percent", 100))
    assert r["tax"] == 0 and r["total"] == 0


def test_empty_cart_with_coupon():
    assert checkout([], ("percent", 10))["total"] == 0
''',
    },
    report=dict(symptom="Customers who use a coupon are still charged tax on the full price",
        steps_to_reproduce=["from shop.checkout import checkout", "from shop.models import Item",
                            "checkout([Item('a', 1000), Item('b', 1000, taxable=False)], ('percent', 10))",
                            "total is 2000"],
        expected="total 1980: tax should be 180 because the discount also lowers the taxable amount",
        actual="total 2000, tax is 200", suspected_area="shop/coupons.py discount_cents()",
        search_keywords=["coupon", "discount", "tax"], confidence=0.6)),
}

for name, b in BUGS.items():
    root = Path("bugs") / name
    for fname, text in b["files"].items():
        w(root / "repo" / fname, text)
    for fname, text in b["hidden"].items():
        w(root / "hidden" / fname, text)
    w(root / "report.json", json.dumps(b["report"], indent=2))
print(f"Created {len(BUGS)} harder bugs in bugs/ (with hidden tests)")