from cart import Cart

def test_remove_updates_total():
    c = Cart()
    c.add("apple", 2, 3)  # 6
    c.add("pear", 1.5, 2)  # 3
    assert c.total() == 9.0
    c.remove("apple")
    assert c.total() == 3.0, f"Expected 3.0 after removing apple, got {c.total()}"

def test_remove_nonexistent_does_not_change_total():
    c = Cart()
    c.add("pear", 1.5, 2)
    c.remove("apple")  # not in cart
    assert c.total() == 3.0
