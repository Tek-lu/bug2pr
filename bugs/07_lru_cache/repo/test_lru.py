from lru import LRUCache


def test_evicts_oldest():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    assert "a" not in c and "b" in c and "c" in c


def test_get_missing():
    assert LRUCache(1).get("x", 7) == 7
