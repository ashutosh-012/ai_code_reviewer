import base64
import json
import re
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

    def _get_diff_lines(self, owner, repo, pr_num):
        """Parse PR diffs to find which line numbers are valid for inline comments."""
        files = self.pr_files(owner, repo, pr_num)
        diff_lines = {}
        for f in files:
            filename = f.get("filename", "")
            patch = f.get("patch", "")
            valid = set()
            if not patch:
                diff_lines[filename] = valid
                continue
            current_line = 0
            for line in patch.split("\n"):
                if line.startswith("@@"):
                    m = re.search(r'\+(\d+)', line)
                    if m:
                        current_line = int(m.group(1))
                elif line.startswith("-"):
                    pass
                elif line.startswith("+"):
                    valid.add(current_line)
                    current_line += 1
                else:
                    valid.add(current_line)
                    current_line += 1
            diff_lines[filename] = valid
        return diff_lines

    def post_review(self, owner, repo, pr_num, sha, summary, comments, has_critical):
        # Get valid diff lines so inline comments land correctly
        diff_lines = self._get_diff_lines(owner, repo, pr_num)
        print(f"DEBUG - Diff lines found for {len(diff_lines)} files")

        # Split comments into inline-able vs overflow
        inline_comments = []
        overflow_comments = []

        for issue in comments[:cfg.max_comments]:
            f = issue.get("file")
            line = issue.get("line")
            if not f or not line:
                overflow_comments.append(issue)
                continue

            agent = issue.get("agent", "").lower()
            sev = issue.get("sev", "LOW").lower()
            body = f"**[{sev} | {agent}]** {issue.get('msg', '')}"
            if issue.get("ai_note"):
                body += f"\n\n{issue['ai_note']}"
            if issue.get("fix"):
                body += f"\n\nFix: `{issue['fix']}`"

            if f in diff_lines and line in diff_lines[f]:
                inline_comments.append({
                    "path": f,
                    "line": line,
                    "side": "RIGHT",
                    "body": body
                })
            else:
                overflow_comments.append(issue)

        # Build summary with overflow issues table
        full_summary = summary
        if overflow_comments:
            full_summary += "\n\n---\n\n**Issues on lines outside the diff:**\n\n"
            full_summary += "| # | Severity | File | Line | Agent | Issue | Fix |\n"
            full_summary += "|---|----------|------|------|-------|-------|-----|\n"
            for i, issue in enumerate(overflow_comments, 1):
                sev = issue.get("sev", "LOW").lower()
                fix_text = issue.get("fix", "").replace("|", "\\|")
                msg_text = issue.get("msg", "").replace("|", "\\|")
                full_summary += (
                    f"| {i} | {sev} "
                    f"| `{issue.get('file', '')}` "
                    f"| L{issue.get('line', '?')} "
                    f"| {issue.get('agent', '').lower()} "
                    f"| {msg_text} "
                    f"| {fix_text} |\n"
                )

        url = f"{self.base}/repos/{owner}/{repo}/pulls/{pr_num}/reviews"
        payload = {
            "commit_id": sha,
            "body": full_summary,
            "event": "REQUEST_CHANGES" if has_critical else "COMMENT",
            "comments": inline_comments
        }

        print(f"DEBUG - Posting {len(inline_comments)} inline + {len(overflow_comments)} overflow")
        r = requests.post(url, json=payload, headers=self.headers, timeout=15)
        print(f"DEBUG - GitHub review response: {r.status_code}")

        if r.status_code in [200, 201]:
            print("DEBUG - Review with inline comments posted successfully!")
            return True

        print(f"DEBUG - Review failed: {r.json()}")

        # Fallback: post everything as a single issue comment
        print("DEBUG - Falling back to issue comment...")
        comment_url = f"{self.base}/repos/{owner}/{repo}/issues/{pr_num}/comments"

        lines = [summary, "", "---", ""]
        lines.append("| # | Severity | File | Line | Agent | Issue | Fix |")
        lines.append("|---|----------|------|------|-------|-------|-----|")
        for i, issue in enumerate(comments[:cfg.max_comments], 1):
            sev = issue.get("sev", "LOW").lower()
            fix_text = issue.get("fix", "").replace("|", "\\|")
            msg_text = issue.get("msg", "").replace("|", "\\|")
            lines.append(
                f"| {i} | {sev} "
                f"| `{issue.get('file', '')}` "
                f"| L{issue.get('line', '?')} "
                f"| {issue.get('agent', '').lower()} "
                f"| {msg_text} "
                f"| {fix_text} |"
            )

        body = "\n".join(lines)
        r2 = requests.post(comment_url, json={"body": body}, headers=self.headers, timeout=15)
        print(f"DEBUG - Fallback comment response: {r2.status_code}")
        return r2.status_code in [200, 201]

gh = GHClient()