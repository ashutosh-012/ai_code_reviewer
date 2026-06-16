from typing import TypedDict, List, Dict, Any, Annotated
import operator

class PRState(TypedDict):
    owner: str
    repo: str
    pr_num: int
    sha: str
    files_to_check: List[Dict[str, Any]]
    issues_found: Annotated[List[Dict[str, Any]], operator.add]
    final_comments: List[Dict[str, Any]]
    has_critical: bool