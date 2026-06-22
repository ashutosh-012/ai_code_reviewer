import ast

class _ASTConfig:
    fn_length = 50

cfg = _ASTConfig()
SECRET_NAMES = ["password", "passwd", "pwd", "secret", "api_key", "token", "private_key"]

def _dfs_walk(tree):
    stack = [tree]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(ast.iter_child_nodes(node))

def _check_secrets(node, fn):
    issues = []
    if not isinstance(node, ast.Assign):
        return issues
    for target in node.targets:
        if not isinstance(target, ast.Name):
            continue
        name = target.id.lower()
        if any(s in name for s in SECRET_NAMES):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                issues.append({
                    "file": fn, "line": node.lineno, "sev": "CRITICAL",
                    "agent": "security", "rule": "SEC001",
                    "msg": f"Hardcoded secret in '{target.id}'",
                    "fix": f"Use os.getenv('{target.id.upper()}')"
                })
    return issues

def _check_fn_quality(node, fn):
    issues = []
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return issues

    if len(node.name) < 4 and node.name not in {"run", "get", "set", "new", "add", "log"}:
        issues.append({
            "file": fn, "line": node.lineno, "sev": "LOW",
            "agent": "style", "rule": "NAME001",
            "msg": f"'{node.name}' is too short — use a descriptive name", "fix": ""
        })

    if len(node.args.args) > 5:
        issues.append({
            "file": fn, "line": node.lineno, "sev": "MEDIUM",
            "agent": "style", "rule": "NAME002",
            "msg": f"'{node.name}' has {len(node.args.args)} params — use a dataclass",
            "fix": "Group params into @dataclass"
        })

    end = getattr(node, "end_lineno", node.lineno)
    if (end - node.lineno) > cfg.fn_length:
        issues.append({
            "file": fn, "line": node.lineno, "sev": "MEDIUM",
            "agent": "complexity", "rule": "COMP001",
            "msg": f"'{node.name}' is {end - node.lineno} lines (max {cfg.fn_length})",
            "fix": "Split into smaller focused functions"
        })

    has_doc = (node.body and isinstance(node.body[0], ast.Expr)
               and isinstance(node.body[0].value, ast.Constant))
    if not has_doc and not node.name.startswith("_"):
        issues.append({
            "file": fn, "line": node.lineno, "sev": "LOW",
            "agent": "style", "rule": "NAME003",
            "msg": f"'{node.name}' has no docstring", "fix": 'Add """one line description."""'
        })
    return issues

def _check_loop_patterns(for_node, fn):
    issues = []
    for node in _dfs_walk(for_node):
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
            issues.append({
                "file": fn, "line": node.lineno, "sev": "MEDIUM",
                "agent": "performance", "rule": "PERF001",
                "msg": "String concat inside loop is O(n²)",
                "fix": "Collect in list then ''.join(items)"
            })
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "append":
                issues.append({
                    "file": fn, "line": node.lineno, "sev": "LOW",
                    "agent": "performance", "rule": "PERF002",
                    "msg": "list.append in loop — use list comprehension",
                    "fix": "result = [transform(x) for x in items]"
                })
    return issues

def run_ast(content: str, fn: str) -> list:
    if not fn.endswith(".py"):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return [{"file": fn, "line": e.lineno or 1, "sev": "HIGH",
                 "agent": "style", "rule": "SYNTAX001",
                 "msg": f"Syntax error: {e.msg}", "fix": "Fix syntax before review"}]

    issues = []
    loop_depth = [0]

    for node in _dfs_walk(tree):
        issues.extend(_check_secrets(node, fn))
        issues.extend(_check_fn_quality(node, fn))
        if isinstance(node, ast.For):
            loop_depth[0] += 1
            issues.extend(_check_loop_patterns(node, fn))
            if loop_depth[0] >= 3:
                issues.append({
                    "file": fn, "line": node.lineno, "sev": "HIGH",
                    "agent": "performance", "rule": "PERF003",
                    "msg": "Triple-nested loop — O(n³)", "fix": "Flatten with itertools or redesign"
                })
            loop_depth[0] -= 1

    return issues