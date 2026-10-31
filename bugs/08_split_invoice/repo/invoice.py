from billing import split_bill


def format_cents(c):
    return f"{c // 100}.{c % 100:02d}"


def split_invoice(total_cents, names):
    """Return {name: formatted share}. The shares always add up to the invoice total."""
    shares = split_bill(total_cents, len(names))
    return {n: format_cents(s) for n, s in zip(names, shares)}
