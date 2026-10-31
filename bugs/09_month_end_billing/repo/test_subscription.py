from datetime import date

from dates_util import add_months
from subscription import billing_dates


def test_add_months_simple():
    assert add_months(date(2024, 1, 15), 1) == date(2024, 2, 15)
    assert add_months(date(2024, 12, 1), 1) == date(2025, 1, 1)


def test_billing_dates_mid_month():
    assert billing_dates(date(2024, 1, 15), 3) == [date(2024, 1, 15), date(2024, 2, 15), date(2024, 3, 15)]
