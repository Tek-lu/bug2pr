from pricing import apply_discount


def test_no_discount():
    assert apply_discount(100.0, 0) == 100.0
