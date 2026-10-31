from .coupons import discount_cents
from .pricing import subtotal, tax_cents, taxable_subtotal


def checkout(items, coupon=None):
    """All amounts are integer cents. total = subtotal - discount + tax.

    The discount is spread over taxable and non-taxable items in proportion to their value:
    taxable_discount = discount * taxable_subtotal // subtotal (integer floor division).
    Tax is charged on the taxable part AFTER its share of the discount.
    """
    sub = subtotal(items)
    discount = discount_cents(coupon, sub) if coupon else 0
    tax = tax_cents(taxable_subtotal(items))
    return {"subtotal": sub, "discount": discount, "tax": tax, "total": sub - discount + tax}
