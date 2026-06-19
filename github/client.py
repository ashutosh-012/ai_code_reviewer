import base64
import json
import urllib.request
import urllib.parse
from typing import Optional
from config import cfg
from core.limiter import gh_limiter
from core.cache import file_cache

# Lightweight fallback HTTP functions to avoid depending on the external 'requests' package.
class _SimpleResponse:
    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self._content = content

    def json(self):
        try:
            text = self._content.decode("utf-8", errors="replace")
            return json.loads(text)
        except Exception:
            return {}

def _build_url(url: str, params: dict | None):
    if not params:
        return url
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

def _get(url: str, headers: dict | None = None, params: dict | None = None, timeout: int | None = None):
    full = _build_url(url, params)
    req = urllib.request.Request(full, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _SimpleResponse(resp.getcode(), resp.read())
    except urllib.error.HTTPError as e:
        return _SimpleResponse(e.code, e.read() or b"")
    except Exception:
        return _SimpleResponse(0, b"")

def _post(url: str, headers: dict | None = None, json_payload: dict | None = None, timeout: int | None = None):
    data = None
    headers = dict(headers or {})
    if json_payload is not None:
        body = json.dumps(json_payload).encode("utf-8")
        data = body
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _SimpleResponse(resp.getcode(), resp.read())
    except urllib.error.HTTPError as e:
        return _SimpleResponse(e.code, e.read() or b"")
    except Exception:
        return _SimpleResponse(0, b"")

# Expose a 'requests'-like API used by this module
class _RequestsShim:
    @staticmethod
    def get(url, headers=None, params=None, timeout=None):
        return _get(url, headers=headers, params=params, timeout=timeout)

    @staticmethod
    def post(url, headers=None, json=None, timeout=None):
        return _post(url, headers=headers, json_payload=json, timeout=timeout)

requests = _RequestsShim()

class GHClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"token {cfg.gh_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        self.base = "https://api.github.com"

    def _get(self, url, params=None):
        gh_limiter.wait()
        r = requests.get(url, headers=self.headers, params=params, timeout=15)
        return r

    def pr_files(self, owner, repo, pr_num):
        url = f"{self.base}/repos/{owner}/{repo}/pulls/{pr_num}/files"
        r = self._get(url)
        return r.json() if r.status_code == 200 else []

    def file_content(self, owner, repo, path, sha) -> Optional[str]:
        cache_key = file_cache.make_key(owner, repo, path, sha)
        cached = file_cache.get(cache_key)
        if cached:
            return cached

        url = f"{self.base}/repos/{owner}/{repo}/contents/{path}"
        r = self._get(url, params={"ref": sha})
        if r.status_code != 200:
            return None
        raw = base64.b64decode(r.json()["content"]).decode("utf-8", errors="replace")
        file_cache.put(cache_key, raw)
        return raw

    def post_review(self, owner, repo, pr_num, sha, summary, comments, has_critical):
        url = f"{self.base}/repos/{owner}/{repo}/pulls/{pr_num}/reviews"
        sev_emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "🔵", "LOW": "💡"}

        fmt_comments = []
        for issue in comments[:cfg.max_comments]:
            if not issue.get("file") or not issue.get("line"):
                continue
            emoji = sev_emoji.get(issue.get("sev", "LOW"), "ℹ️")
            agent = issue.get("agent", "").title()
            body = f"{emoji} **[{issue.get('sev')} — {agent}]** {issue.get('msg', '')}"
            if issue.get("ai_note"):
                body += f"\n\n{issue['ai_note']}"
            if issue.get("fix"):
                body += f"\n\n**Fix:** `{issue['fix']}`"
            fmt_comments.append({
                "path": issue["file"],
                "line": issue["line"],
                "side": "RIGHT",
                "body": body
            })

        # Attempt 1: Try posting as inline review comments
        payload = {
            "commit_id": sha,
            "body": summary,
            "event": "REQUEST_CHANGES" if has_critical else "COMMENT",
            "comments": fmt_comments
        }
        print(f"DEBUG - Posting review with {len(fmt_comments)} inline comments")
        r = requests.post(url, json=payload, headers=self.headers, timeout=15)
        print(f"DEBUG - GitHub POST review response: {r.status_code}")

        if r.status_code in [200, 201]:
            print("DEBUG - Inline review posted successfully!")
            return True

        # Attempt 2: Try without inline comments (just the summary as a review)
        print(f"DEBUG - Inline comments failed ({r.status_code}), trying summary-only review...")
        payload_no_inline = {
            "commit_id": sha,
            "body": summary,
            "event": "COMMENT",
            "comments": []
        }
        r2 = requests.post(url, json=payload_no_inline, headers=self.headers, timeout=15)
        print(f"DEBUG - Summary-only review response: {r2.status_code}")

        # Attempt 3: Post all findings as a single issue comment (always works)
        comment_url = f"{self.base}/repos/{owner}/{repo}/issues/{pr_num}/comments"
        
        body_lines = [summary, "", "---", ""]
        body_lines.append("| # | Sev | File | Line | Agent | Issue | Fix |")
        body_lines.append("|---|-----|------|------|-------|-------|-----|")
        for i, issue in enumerate(comments[:cfg.max_comments], 1):
            emoji = sev_emoji.get(issue.get("sev", "LOW"), "ℹ️")
            fix_text = issue.get("fix", "").replace("|", "\\|")
            msg_text = issue.get("msg", "").replace("|", "\\|")
            body_lines.append(
                f"| {i} | {emoji} {issue.get('sev', 'LOW')} "
                f"| `{issue.get('file', '')}` "
                f"| L{issue.get('line', '?')} "
                f"| {issue.get('agent', '').title()} "
                f"| {msg_text} "
                f"| {fix_text} |"
            )
        
        # Add AI explanations for critical issues
        critical_notes = []
        for issue in comments[:cfg.max_comments]:
            if issue.get("ai_note") and issue.get("sev") in ["CRITICAL", "HIGH"]:
                critical_notes.append(
                    f"**{sev_emoji.get(issue.get('sev'))} `{issue.get('file')}` L{issue.get('line')}** — "
                    f"{issue.get('msg')}\n> {issue.get('ai_note')}"
                )
        if critical_notes:
            body_lines.append("")
            body_lines.append("### 🔍 AI Explanations (Critical/High only)")
            body_lines.append("")
            body_lines.extend(critical_notes)

        issue_body = "\n".join(body_lines)
        r3 = requests.post(comment_url, json={"body": issue_body}, headers=self.headers, timeout=15)
        print(f"DEBUG - Issue comment response: {r3.status_code}")
        
        if r3.status_code in [200, 201]:
            print("DEBUG - Posted findings as PR comment successfully!")
            return True
        else:
            print(f"DEBUG - Issue comment failed: {r3.json()}")
            return False

gh = GHClient()