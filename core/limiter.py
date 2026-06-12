import time
from collections import deque

class SlidingWindowLimiter:
    def __init__(self, max_calls=80, window_sec=60):
        self.max_calls = max_calls
        self.window = window_sec
        self._ts = deque()

    def _purge_old(self):
        cutoff = time.time() - self.window
        while self._ts and self._ts[0] < cutoff:
            self._ts.popleft()

    def allowed(self):
        self._purge_old()
        if len(self._ts) < self.max_calls:
            self._ts.append(time.time())
            return True
        return False

    def wait(self):
        while not self.allowed():
            time.sleep(0.3)

gh_limiter = SlidingWindowLimiter(max_calls=80, window_sec=60)