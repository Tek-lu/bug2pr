from inventory import needs_reorder, low_items


def test_needs_reorder_basic():
    assert needs_reorder(0, 5)
    assert not needs_reorder(10, 5)


def test_low_items_names_cleaned():
    assert low_items({" Pen ": 1, "Ink": 50}, 5) == ["pen"]
