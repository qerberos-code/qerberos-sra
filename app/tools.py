import os
import subprocess


def _find_posix_shell():
    """Prefer Git Bash on Windows so POSIX commands work."""
    if os.name != "nt":
        return None
    for path in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
    ):
        if os.path.exists(path):
            return path
    return None


POSIX_SHELL = _find_posix_shell()


def read_tool(file_path):
    with open(file_path, "r") as f:
        return f.read()


def write_tool(file_path, content):
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)
    return f"Successfully wrote to {file_path}"


def bash_tool(command):
    if POSIX_SHELL:
        result = subprocess.run(
            [POSIX_SHELL, "-c", command], capture_output=True, text=True
        )
    else:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


_GIT_ALLOWED = {
    "checkout_branch": lambda branch_name, **_: bash_tool(f"git checkout -b {branch_name}"),
    "add":             lambda files, **_: bash_tool(f"git add {' '.join(files) if isinstance(files, list) else files}"),
    "commit":          lambda message, **_: bash_tool(f'git commit -m "{message}"'),
    "push":            lambda branch_name, **_: bash_tool(f"git push -u origin {branch_name}"),
    "pr_create":       lambda pr_title, pr_body, base="main", **_: bash_tool(
                           f'gh pr create --title "{pr_title}" --body "{pr_body}" --base {base}'
                       ),
    "status":          lambda **_: bash_tool("git status --short"),
    "diff":            lambda **_: bash_tool("git diff HEAD"),
}


def git_tool(subcommand: str, args: dict | None = None) -> str:
    """Safe wrapper around git/gh CLI with an allowlisted set of subcommands."""
    fn = _GIT_ALLOWED.get(subcommand)
    if fn is None:
        return f"Unknown git subcommand: {subcommand}. Allowed: {', '.join(_GIT_ALLOWED)}"
    try:
        return fn(**(args or {}))
    except Exception as exc:
        return f"Error in git {subcommand}: {exc}"


_TOOL_REGISTRY = {
    "Read": {
        "handler": read_tool,
        "spec": {
            "name": "Read",
            "description": "Read and return the contents of a file",
            "input_schema": {
                "type": "object",
                "required": ["file_path"],
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to read",
                    },
                },
            },
        },
    },
    "Write": {
        "handler": write_tool,
        "spec": {
            "name": "Write",
            "description": "Write content to a file, creating parent directories as needed",
            "input_schema": {
                "type": "object",
                "required": ["file_path", "content"],
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path of the file to write to",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file",
                    },
                },
            },
        },
    },
    "Bash": {
        "handler": bash_tool,
        "spec": {
            "name": "Bash",
            "description": "Execute a shell command and return its combined stdout and stderr",
            "input_schema": {
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute",
                    },
                },
            },
        },
    },
}


_TOOL_REGISTRY["Git"] = {
    "handler": lambda subcommand, args=None: git_tool(subcommand, args),
    "spec": {
        "name": "Git",
        "description": (
            "Safe wrapper around git and gh CLI. "
            "Allowed subcommands: checkout_branch, add, commit, push, pr_create, status, diff."
        ),
        "input_schema": {
            "type": "object",
            "required": ["subcommand"],
            "properties": {
                "subcommand": {
                    "type": "string",
                    "enum": list(_GIT_ALLOWED.keys()),
                    "description": "The git operation to perform",
                },
                "args": {
                    "type": "object",
                    "description": (
                        "Parameters for the subcommand. "
                        "checkout_branch/push: {branch_name}. "
                        "add: {files: [...]}. "
                        "commit: {message}. "
                        "pr_create: {pr_title, pr_body, base}."
                    ),
                },
            },
        },
    },
}


def make_tool_registry(*names: str) -> dict:
    """Return a TOOLS dict containing only the named tools.

    Usage:
        make_tool_registry("Read", "Bash")              # sub-agents
        make_tool_registry("Read", "Write", "Bash")     # manager
    """
    return {name: _TOOL_REGISTRY[name] for name in names if name in _TOOL_REGISTRY}


def execute_tool(name: str, arguments: dict, tools: dict) -> str:
    tool = tools.get(name)
    if tool is None:
        return f"Unknown tool: {name}"
    try:
        return tool["handler"](**arguments)
    except Exception as exc:
        return f"Error executing {name}: {exc}"
