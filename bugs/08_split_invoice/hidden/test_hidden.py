from billing import split_bill
from invoice import split_invoice


def test_remainder_distributed():
    assert split_bill(100, 3) == [34, 33, 33]
    assert split_bill(1, 3) == [1, 0, 0]
    assert split_bill(0, 2) == [0, 0]


def test_invoice_adds_up():
    out = split_invoice(1000, ["ann", "bob", "cy"])
    assert out == {"ann": "3.34", "bob": "3.33", "cy": "3.33"}
    assert sum(int(v.replace(".", "")) for v in out.values()) == 1000
