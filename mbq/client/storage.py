import json


class DjangoCacheStorage(object):

    def __init__(self, cache, timeout=None):
        self.cache = cache
        self.timeout = timeout

    def set(self, key, value):
        self.cache.set(key, value, timeout=self.timeout)

    def get(self, key):
        return self.cache.get(key)


class FileStorage(object):

    def __init__(self, filename):
        self.filename = filename
        open(self.filename, 'a').close()

    def _get_tokens_from_file(self):
        with open(self.filename, 'r') as f:
            try:
                return json.load(f)
            except ValueError:
                return {}

    def set(self, key, value):
        tokens = self._get_tokens_from_file()

        tokens[key] = value

        with open(self.filename, 'w') as f:
            json.dump(tokens, f)

    def get(self, key):
        return self._get_tokens_from_file().get(key)
