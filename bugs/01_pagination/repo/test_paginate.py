from paginate import paginate, total_pages


def test_total_pages():
    assert total_pages(10, 3) == 4


def test_empty():
    assert paginate([], 1, 5) == []
