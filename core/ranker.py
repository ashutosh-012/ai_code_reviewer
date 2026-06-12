import heapq

SEV = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

class IssueRanker:
    def __init__(self):
        self._heap = []
        self._counter = 0

    def push(self, issue):
        score = SEV.get(issue.get("sev", "LOW"), 1)
        heapq.heappush(self._heap, (-score, self._counter, issue))
        self._counter += 1

    def pop_all(self):
        result = []
        while self._heap:
            _, _, issue = heapq.heappop(self._heap)
            result.append(issue)
        return result

    def size(self):
        return len(self._heap)