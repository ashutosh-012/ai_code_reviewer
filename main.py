import json
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from github.webhook_validator import verify
from config import cfg
from agents.graph import review_graph

app = FastAPI(title="AI Code Reviewer", version="1.0.0")

def _bg_review(owner, repo, pr_num, sha, title, author):
    print(f"✅ Successfully caught PR #{pr_num} from {owner}/{repo}")
    print("⏳ Starting LangGraph Analysis Pipeline...")
    
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
        review_graph.invoke(initial_state)
        print(f"🎯 Finished processing PR #{pr_num}")
    except Exception as e:
        print(f"❌ Graph execution failed: {e}")

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