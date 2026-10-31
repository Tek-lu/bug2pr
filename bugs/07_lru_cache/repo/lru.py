from collections import OrderedDict


class LRUCache:
    """Least-recently-used cache. Both get() and put() count as a use."""

    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._d = OrderedDict()

    def get(self, key, default=None):
        if key not in self._d:
            return default
        return self._d[key]

    def put(self, key, value):
        if key in self._d:
            self._d.move_to_end(key)
        self._d[key] = value
        if len(self._d) > self.capacity:
            self._d.popitem(last=False)

    def __len__(self):
        return len(self._d)

    def __contains__(self, key):
        return key in self._d
