class _Node:
    def __init__(self):
        self.ch = {}
        self.meta = None
        self.end = False

class RuleTrie:
    def __init__(self):
        self.root = _Node()

    def insert(self, code, meta):
        node = self.root
        for c in code:
            if c not in node.ch:
                node.ch[c] = _Node()
            node = node.ch[c]
        node.end = True
        node.meta = meta

    def prefix_search(self, prefix):
        node = self.root
        for c in prefix:
            if c not in node.ch:
                return []
            node = node.ch[c]
        results = []
        queue = [node]
        while queue:
            curr = queue.pop(0)
            if curr.end and curr.meta:
                results.append(curr.meta)
            queue.extend(curr.ch.values())
        return results

rule_trie = RuleTrie()

_rules = [
    ("B101", {"sev": "MEDIUM", "cat": "security", "msg": "assert used — disabled in optimized mode"}),
    ("B106", {"sev": "HIGH",   "cat": "security", "msg": "hardcoded password in function arg"}),
    ("B608", {"sev": "CRITICAL","cat": "security","msg": "SQL injection via string format"}),
    ("F401", {"sev": "MEDIUM", "cat": "style",    "msg": "imported but unused"}),
]

for code, meta in _rules:
    rule_trie.insert(code, {**meta, "code": code})