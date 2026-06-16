from typing import TypedDict, List, Dict, Any

class PRState(TypedDict):
    owner: str
    repo: str
    pr_num: int
    sha: str
    files_to_check: List[Dict[str, Any]]
    issues_found: List[Dict[str, Any]]
    final_comments: List[Dict[str, Any]]
    has_critical: bool