from utils import clean


def needs_reorder(stock, threshold):
    """An item needs reordering when stock is at or below the threshold."""
    return stock < threshold


def low_items(inventory, threshold):
    return sorted(clean(n) for n, s in inventory.items() if needs_reorder(s, threshold))
