import subprocess
import json
import sys

def run_bandit(content: str, fn: str) -> list:
    if not fn.endswith(".py"):
        return []
    try:
        r = subprocess.run(
            [sys.executable, "-m", "bandit", "-", "-f", "json", "-q"],
            input=content,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30
        )
        if not r.stdout.strip():
            return []
        data = json.loads(r.stdout)
        issues = []
        for item in data.get("results", []):
            if item.get("issue_confidence") == "LOW":
                continue
            sev_map = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}
            issues.append({
                "file": fn,
                "line": item.get("line_number", 0),
                "sev": sev_map.get(item.get("issue_severity", "LOW"), "LOW"),
                "agent": "security",
                "rule": item.get("test_id", ""),
                "msg": item.get("issue_text", ""),
                "fix": item.get("more_info", "")
            })
        return issues
    except Exception as e:
        print(f"bandit error: {e}")
        return []