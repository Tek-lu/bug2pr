from cart import Cart

def test_add_updates_total():
    c = Cart()
    c.add("apple", 2.0, 3)
    assert c.total() == 6.0