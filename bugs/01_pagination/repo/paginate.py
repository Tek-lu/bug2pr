def paginate(items, page, per_page):
    """Return the items on the given 1-based page."""
    start = (page - 1) * per_page
    end = start + per_page - 1
    return items[start:end]


def total_pages(n_items, per_page):
    return -(-n_items // per_page)
