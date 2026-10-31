import pytest

from retry import retry


def test_succeeds_on_last_attempt():
    calls, slept = [], []

    @retry(3, sleep=slept.append)
    def f():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("boom")
        return "ok"

    assert f() == "ok"
    assert len(calls) == 3
    assert slept == [0.1, 0.2]


def test_reraises_last_exception():
    slept = []

    @retry(3, sleep=slept.append)
    def f():
        raise KeyError("x")

    with pytest.raises(KeyError):
        f()
    assert slept == [0.1, 0.2]
