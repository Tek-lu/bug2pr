TAX_RATE_PERCENT = 20


def subtotal(items):
    return sum(i.price_cents * i.qty for i in items)


def taxable_subtotal(items):
    return sum(i.price_cents * i.qty for i in items if i.taxable)


def tax_cents(taxable_cents):
    """Tax on an amount, rounded half up."""
    return (taxable_cents * TAX_RATE_PERCENT + 50) // 100
