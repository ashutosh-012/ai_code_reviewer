import subprocess
import json
import sys
from config import cfg

def run_radon(content: str, fn: str) -> list:
    if not fn.endswith(".py"):
        return []
    try:
        # Use "-" to read directly from standard input (RAM)
        r = subprocess.run(
            [sys.executable, "-m", "radon", "cc", "-", "-j", "-s"],
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
        
        # Radon uses '<stdin>' as the dictionary key when reading from RAM
        funcs = data.get("<stdin>", [])
        if not funcs and data: 
            funcs = list(data.values())[0] if isinstance(data, dict) else []

        for f in funcs:
            cc = f.get("complexity", 0)
            if cc <= cfg.cc_threshold:
                continue
            rank = f.get("rank", "A")
            issues.append({
                "file": fn,
                "line": f.get("lineno", 0),
                "sev": "HIGH" if rank in ["D", "E", "F"] else "MEDIUM",
                "agent": "complexity",
                "rule": "CC001",
                "msg": f"Function '{f.get('name')}' complexity {cc} (rank {rank}, limit {cfg.cc_threshold})",
                "fix": "Split into smaller functions"
            })
        return issues
    except Exception as e:
        print(f"radon error: {e}")
        return []