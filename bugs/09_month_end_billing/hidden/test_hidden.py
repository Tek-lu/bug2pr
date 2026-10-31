from datetime import date

from dates_util import add_months
from subscription import billing_dates


def test_clamps_month_end():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
    assert add_months(date(2024, 3, 31), -1) == date(2024, 2, 29)


def test_billing_anchored_to_start_day():
    assert billing_dates(date(2024, 1, 31), 4) == [
        date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30)]
