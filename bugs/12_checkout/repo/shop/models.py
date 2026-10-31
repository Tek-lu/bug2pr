from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    sku: str
    price_cents: int
    qty: int = 1
    taxable: bool = True
