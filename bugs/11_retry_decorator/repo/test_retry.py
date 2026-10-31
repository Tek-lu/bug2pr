from retry import retry


def test_first_try_succeeds():
    @retry(3)
    def f():
        return 5
    assert f() == 5
