from service import GreetingService


def test_greet_english():
    assert GreetingService().greet(1, "Ann") == "Hello, Ann!"
