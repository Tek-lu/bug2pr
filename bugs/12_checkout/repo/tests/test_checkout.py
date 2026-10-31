from shop.checkout import checkout
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
