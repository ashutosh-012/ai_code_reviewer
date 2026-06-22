import subprocess
import json
import sys

_sev = {"F": "HIGH", "E": "MEDIUM", "W": "LOW", "N": "MEDIUM", "C": "MEDIUM", "B": "HIGH"}

def run_ruff(content: str, fn: str) -> list:
    if not fn.endswith(".py"):
        return []
    try:
        r = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "-", "--stdin-filename", fn, "--output-format", "json", "--no-cache"],
            input=content,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30
        )
        if r.stderr.strip() and not r.stdout.strip():
            print(f"Ruff error: {r.stderr}")
            return []
        if not r.stdout.strip():
            return []
        issues = []
        for item in json.loads(r.stdout):
            code = item.get("code", "")
            issues.append({
                "file": fn,
                "line": item.get("location", {}).get("row", 0),
                "sev": _sev.get(code[0] if code else "E", "LOW"),
                "agent": "style",
                "rule": code,
                "msg": item.get("message", ""),
                "fix": (item.get("fix") or {}).get("message", "")
            })
        return issues
    except Exception as e:
        print(f"ruff error: {e}")
        return []