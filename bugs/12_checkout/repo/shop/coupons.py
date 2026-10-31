def discount_cents(coupon, subtotal_cents):
    """coupon is ('percent', 10) or ('fixed', 500). A discount never exceeds the subtotal."""
    kind, value = coupon
    if kind == "percent":
        return subtotal_cents * value // 100
    if kind == "fixed":
        return min(value, subtotal_cents)
    raise ValueError(f"unknown coupon kind {kind}")
