from dates_util import add_months


def billing_dates(start, count):
    """The first `count` billing dates: `start`, then once a month.

    Every date is anchored to the day-of-month of `start` (clamped when a month is shorter),
    so a subscription starting on Jan 31 bills on Jan 31, Feb 28/29, Mar 31, Apr 30, ...
    """
    dates = [start]
    while len(dates) < count:
        dates.append(add_months(dates[-1], 1))
    return dates
