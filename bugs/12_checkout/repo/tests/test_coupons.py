import pytest

from shop.coupons import discount_cents


def test_percent():
    assert discount_cents(("percent", 10), 2000) == 200


def test_fixed_capped():
    assert discount_cents(("fixed", 5000), 2000) == 2000


def test_unknown():
    with pytest.raises(ValueError):
        discount_cents(("bogus", 1), 100)
