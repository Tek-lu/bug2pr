from leaderboard import rank


def test_no_ties():
    assert rank({"a": 3, "b": 9}) == [(1, "b"), (2, "a")]


def test_empty():
    assert rank({}) == []
