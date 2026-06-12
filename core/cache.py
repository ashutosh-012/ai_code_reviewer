from collections import OrderedDict
import hashlib

class LRUCache:
    def __init__(self, cap=100):
        self.cap = cap
        self._data = OrderedDict()

    def get(self, key):
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key, val):
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = val
        if len(self._data) > self.cap:
            self._data.popitem(last=False)

    def make_key(self, *parts):
        raw = ":".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()

file_cache = LRUCache(cap=200)
llm_cache = LRUCache(cap=500)