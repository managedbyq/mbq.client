

class DjangoCacheStorage(object):

    def __init__(self, cache, timeout=None):
        self.cache = cache,
        self.timeout = timeout

    def set(self, key, value):
        self.cache.set(key, value, timeout=self.timeout)

    def get(self, key):
        return self.cache.get(key)
