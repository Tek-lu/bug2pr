from tags import add_tag


def test_add_to_existing():
    assert add_tag("a", ["x"]) == ["x", "a"]
