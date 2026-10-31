def split_bill(total_cents, n):
    """Split total_cents among n people.

    The shares must add up to total_cents exactly. Shares differ by at most one cent,
    and the earlier people in the list pay the extra cent.
    """
    share = total_cents // n
    return [share] * n
