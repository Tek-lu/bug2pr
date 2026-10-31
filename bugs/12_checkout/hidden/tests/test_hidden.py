from shop.checkout import checkout
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
