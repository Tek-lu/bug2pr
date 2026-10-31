from leaderboard import rank


def test_ties_share_rank_and_skip():
    assert rank({"a": 9, "b": 7, "c": 7, "d": 1}) == [(1, "a"), (2, "b"), (2, "c"), (4, "d")]


def test_ties_alphabetical():
    assert rank({"z": 5, "m": 5, "c": 3}) == [(1, "m"), (1, "z"), (3, "c")]
