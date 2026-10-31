from billing import split_bill
from invoice import split_invoice


def test_even_split():
    assert split_bill(100, 4) == [25, 25, 25, 25]


def test_invoice_even():
    assert split_invoice(300, ["a", "b"]) == {"a": "1.50", "b": "1.50"}
