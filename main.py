import json
import sqlite3
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from github.webhook_validator import verify
from config import cfg
from agents.graph import review_graph
from core.database import save_issues

app = FastAPI(title="AI Code Reviewer", version="1.0.0")

def _bg_review(owner, repo, pr_num, sha, title, author):
    print(f"Successfully caught PR #{pr_num} from {owner}/{repo}")
    print("Starting LangGraph Analysis Pipeline...")
    
    initial_state = {
        "owner": owner,
        "repo": repo,
        "pr_num": pr_num,
        "sha": sha,
        "files_to_check": [],
        "issues_found": [],
        "final_comments": [],
        "has_critical": False
    }
    
    try:
        result_state = review_graph.invoke(initial_state)
        final_comments = result_state.get('final_comments', [])
        
        print(f"Finished processing PR #{pr_num}")
        print(f"DEBUG - Final Comments count: {len(final_comments)}")
        
        if final_comments:
            save_issues(f"{owner}/{repo}", pr_num, sha, final_comments)
            print("Successfully saved PR review to SQLite Database")
            
    except Exception as e:
        print(f"Graph execution failed: {e}")

@app.post("/webhook/github")
async def webhook(request: Request, bg: BackgroundTasks):
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if cfg.gh_secret and not verify(body, cfg.gh_secret, sig):
        raise HTTPException(401, "bad signature")
    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(400, "bad json")
    
    action = payload.get("action", "")
    if action not in ["opened", "synchronize", "reopened"]:
        return {"status": "ignored"}
        
    pr = payload.get("pull_request", {})
    full = payload.get("repository", {}).get("full_name", "")
    if "/" not in full:
        return {"status": "error"}
        
    owner, repo = full.split("/", 1)
    pr_num = pr.get("number", 0)
    sha = pr.get("head", {}).get("sha", "")
    title = pr.get("title", "")
    author = pr.get("user", {}).get("login", "")
    
    bg.add_task(_bg_review, owner, repo, pr_num, sha, title, author)
    
    return {"status": "queued", "pr": pr_num}

@app.get("/health")
def health():
    return {"ok": True, "model": cfg.model}

@app.get("/api/logs")
def get_logs():
    try:
        conn = sqlite3.connect("reviews.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM review_logs ORDER BY created_at DESC LIMIT 50")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return rows
    except Exception as e:
        return {"error": str(e)}

@app.get("/dashboard")
def serve_dashboard():
    return FileResponse("dashboard.html")