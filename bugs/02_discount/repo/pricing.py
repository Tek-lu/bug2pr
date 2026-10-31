def apply_discount(price, percent):
    """Apply a percentage discount. percent is 0-100, e.g. 20 means 20% off."""
    return round(price * (1 - percent), 2)
