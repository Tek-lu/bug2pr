class Cache:
    def __init__(self):
        self._data = {}

    @staticmethod
    def make_key(user_id, lang):
        return str(user_id)

    def get(self, user_id, lang):
        return self._data.get(self.make_key(user_id, lang))

    def set(self, user_id, lang, value):
        self._data[self.make_key(user_id, lang)] = value
