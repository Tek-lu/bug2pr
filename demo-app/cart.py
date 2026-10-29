class Cart:
    def __init__(self):
        self.items = {}
        self._total = 0.0

    def add(self, name, price, qty=1):
        if name in self.items:
            self.items[name]["qty"] += qty
        else:
            self.items[name] = {"price": price, "qty": qty}
        self._total += price * qty

    def remove(self, name):
        if name in self.items:
            self._total -= self.items[name]["price"] * self.items[name]["qty"]
            del self.items[name]

    def total(self):
        return self._total