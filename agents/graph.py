from langgraph.graph import StateGraph, END
from agents.state import PRState
from agents.ai_explainer import explain_issue
from github.client import gh
from core.ranker import IssueRanker
from config import cfg

# Import our wrappers
from analyzers.bandit_runner import run_bandit
from analyzers.ruff_runner import run_ruff
from analyzers.radon_runner import run_radon
from analyzers.ast_analyzer import run_ast

def fetch_files(state: PRState):
    """Gets list of changed files and their contents."""
    files = gh.pr_files(state["owner"], state["repo"], state["pr_num"])
    to_check = []
    for f in files:
        if f.get("filename", "").endswith(".py") and f.get("status") != "removed":
            content = gh.file_content(state["owner"], state["repo"], f["filename"], state["sha"])
            if content:
                to_check.append({"name": f["filename"], "content": content})
    return {"files_to_check": to_check, "issues_found": []}

def run_security(state: PRState):
    issues = []
    for f in state["files_to_check"]:
        issues.extend(run_bandit(f["content"], f["name"]))
    return {"issues_found": issues}

def run_style(state: PRState):
    issues = []
    for f in state["files_to_check"]:
        issues.extend(run_ruff(f["content"], f["name"]))
    return {"issues_found": issues}

def run_complexity(state: PRState):
    issues = []
    for f in state["files_to_check"]:
        issues.extend(run_radon(f["content"], f["name"]))
    return {"issues_found": issues}

def run_ast_checks(state: PRState):
    issues = []
    for f in state["files_to_check"]:
        issues.extend(run_ast(f["content"], f["name"]))
    return {"issues_found": issues}

def aggregate_and_rank(state: PRState):
    """DSA: Uses HashMap for dedup and Priority Queue for ranking."""
    dedup = {}
    for issue in state["issues_found"]:
        key = f"{issue['file']}:{issue['line']}:{issue['rule']}"
        if key not in dedup:
            dedup[key] = issue
            
    ranker = IssueRanker()
    for issue in dedup.values():
        ranker.push(issue)
        
    top_issues = ranker.pop_all()
    has_crit = any(i.get("sev") in ["CRITICAL", "HIGH"] for i in top_issues)
    return {"final_comments": top_issues[:cfg.max_comments], "has_critical": has_crit}

def ai_explain(state: PRState):
    """Passes only the worst issues to the local LLM."""
    explained = []
    for issue in state["final_comments"]:
        if issue.get("sev") in ["CRITICAL", "HIGH"]:
            content = ""
            for f in state["files_to_check"]:
                if f["name"] == issue["file"]:
                    lines = f["content"].split("\n")
                    idx = max(0, int(issue["line"]) - 1)
                    content = "\n".join(lines[max(0, idx-2) : idx+3])
                    break
            
            ai_note = explain_issue(issue, content)
            issue["ai_note"] = ai_note
        explained.append(issue)
    return {"final_comments": explained}

def post_to_github(state: PRState):
    """Sends the final payload back to the PR."""
    summary = f"## AI Code Review Complete\nAnalyzed {len(state['files_to_check'])} files. Found {len(state['final_comments'])} prioritized issues."
    gh.post_review(
        state["owner"], state["repo"], state["pr_num"], state["sha"],
        summary, state["final_comments"], state["has_critical"]
    )
    return state

# --- BUILD THE DAG ---
workflow = StateGraph(PRState)

workflow.add_node("fetch", fetch_files)
workflow.add_node("security", run_security)
workflow.add_node("style", run_style)
workflow.add_node("complexity", run_complexity)
workflow.add_node("ast", run_ast_checks)
workflow.add_node("aggregate", aggregate_and_rank)
workflow.add_node("explain", ai_explain)
workflow.add_node("post", post_to_github)

workflow.set_entry_point("fetch")

# Fan-out
workflow.add_edge("fetch", "security")
workflow.add_edge("fetch", "style")
workflow.add_edge("fetch", "complexity")
workflow.add_edge("fetch", "ast")

# Fan-in
workflow.add_edge("security", "aggregate")
workflow.add_edge("style", "aggregate")
workflow.add_edge("complexity", "aggregate")
workflow.add_edge("ast", "aggregate")

# Linear finish
workflow.add_edge("aggregate", "explain")
workflow.add_edge("explain", "post")
workflow.add_edge("post", END)

# Compile
review_graph = workflow.compile()