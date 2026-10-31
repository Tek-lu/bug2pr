def add_months(d, months):
    """Add months to a date. If the day does not exist in the target month it is clamped
    to the last day of that month (Jan 31 + 1 month = Feb 28, or Feb 29 in a leap year)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return d.replace(year=year, month=month)
