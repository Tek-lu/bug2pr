from cache import Cache

GREETINGS = {"en": "Hello", "fr": "Bonjour"}


class GreetingService:
    def __init__(self):
        self.cache = Cache()

    def greet(self, user_id, name, lang="en"):
        cached = self.cache.get(user_id, lang)
        if cached:
            return cached
        msg = f"{GREETINGS[lang]}, {name}!"
        self.cache.set(user_id, lang, msg)
        return msg
