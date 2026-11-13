"""The three tools AutoDocs needs: read the diff, open a file, write a docstring."""

import ast
import shutil
import subprocess
from pathlib import Path

from autodocs.tools import Tool, ToolError

MAX_DIFF_CHARS = 60_000
MAX_LINES_PER_READ = 300


class Workspace:
    """A fresh clone of the target repo on the branch being documented."""

    def __init__(self, source_repo: str, branch: str, base: str, root: Path):
        """Clone source_repo at branch into root, so edits never touch the original."""
        root = root.resolve()  # absolute, so git's working folder never changes its meaning
        self.branch, self.base, self.root = branch, base, root
        if root.exists():
            shutil.rmtree(root)
        root.parent.mkdir(parents=True, exist_ok=True)
        self.git("clone", "--quiet", "--branch", branch, str(Path(source_repo).resolve()),
                 str(root), cwd=root.parent)
        self.git("fetch", "--quiet", "origin", f"{base}:{base}")

    def git(self, *args: str, cwd: Path | None = None) -> str:
        """Run a git command and return its output."""
        result = subprocess.run(["git", *args], cwd=cwd or self.root, check=True,
                                capture_output=True, text=True)
        return result.stdout

    def changed_files(self) -> list[str]:
        """Paths changed on the branch, relative to the repo root."""
        return self.git("diff", "--name-only", f"{self.base}...HEAD").split()

    def resolve(self, path: str) -> Path | None:
        """Turn a repo-relative path into a real path, refusing anything outside the repo."""
        full = (self.root / path).resolve()
        if not full.is_relative_to(self.root.resolve()) or not full.is_file():
            return None
        return full

    def changed_functions(self) -> dict:
        """Application functions the branch adds or changes, and files that do not parse."""
        changed, unparseable = [], []
        for path in self.changed_files():
            if not path.endswith(".py") or path.startswith(("tests/", "migrations/")):
                continue
            head = self.resolve(path)
            if head is None:  # deleted or renamed away
                continue
            try:
                head_functions = functions_in(head.read_text())
            except SyntaxError:
                unparseable.append(path)
                continue
            try:
                base_functions = functions_in(self.git("show", f"{self.base}:{path}"))
            except subprocess.CalledProcessError:  # new file
                base_functions = {}
            changed += [f"{path}::{name}" for name, body in head_functions.items()
                        if base_functions.get(name) != body]
        return {"functions": changed, "unparseable": unparseable}

    def docstring_patch(self) -> str:
        """The docstring edits the agent made, as a diff."""
        return self.git("diff")


def make_repo_tools(workspace: Workspace) -> list[Tool]:
    """Build the three tools, bound to one workspace."""

    def read_diff() -> str:
        """Return the branch's full diff against the base branch. Call this first."""
        diff = workspace.git("diff", f"{workspace.base}...HEAD")
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS] + f"\n[diff cut at {MAX_DIFF_CHARS} characters]"
        broken = [f"{path} ({problem})" for path in workspace.changed_files()
                  if (problem := parse_problem(workspace.resolve(path)))]
        if broken:
            diff += "\n[NOTE: these changed files do not parse: " + "; ".join(broken) + "]"
        return diff

    def open_file(path: str, start_line: int = 1, end_line: int = 200) -> str:
        """Return numbered lines of a branch file (path from the repo root, max 300 lines).
        Use it to read code the diff calls but does not show."""
        full = workspace.resolve(path)
        if full is None:
            raise ToolError(f"{path} is not a file in this repository")
        lines = full.read_text().splitlines()
        start = max(start_line, 1)
        end = min(end_line, start + MAX_LINES_PER_READ - 1, len(lines))
        numbered = [f"{n:5d}  {lines[n - 1]}" for n in range(start, end + 1)]
        header = f"{path} lines {start}-{end} of {len(lines)}"
        if problem := parse_problem(full):
            header += f" [NOTE: this file does not parse: {problem}]"
        return header + "\n" + "\n".join(numbered)

    def write_docstring(path: str, function_name: str, docstring: str) -> str:
        """Replace or add a function's docstring in a file changed on this branch ('Class.method').
        Pass one or two plain sentences; only when the docstring is missing or wrong."""
        if path not in workspace.changed_files():
            raise ToolError(f"{path} is not changed on this branch; only changed files are edited")
        full = workspace.resolve(path)
        if full is None:
            raise ToolError(f"{path} is not a file in this repository")
        source = full.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise ToolError(
                f"{path} does not parse (line {exc.lineno}: {exc.msg}); not edited") from None
        node = find_function(tree, function_name)
        if node is None:
            raise ToolError(f"no function {function_name} in {path}")
        text = docstring.strip().strip('"')
        if ast.get_docstring(node) == text:
            return f"{function_name} already has exactly this docstring; nothing changed"
        new_source = set_docstring(source, node, text)
        ast.parse(new_source)  # never write a file that no longer parses
        full.write_text(new_source)
        return f"docstring set for {function_name} in {path}"

    return [Tool.from_function(f) for f in (read_diff, open_file, write_docstring)]


def parse_problem(path: Path | None) -> str | None:
    """Return 'line N: message' if a Python file does not parse, else None."""
    if path is None or path.suffix != ".py":
        return None
    try:
        ast.parse(path.read_text())
    except SyntaxError as exc:
        return f"line {exc.lineno}: {exc.msg}"
    return None


def functions_in(source: str) -> dict[str, str]:
    """Map each function's qualified name to its code, ignoring its docstring."""
    found = {}

    def visit(nodes: list, prefix: str) -> None:
        """Collect functions, descending into classes."""
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                visit(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body[1:] if ast.get_docstring(node) else node.body
                found[prefix + node.name] = ast.dump(ast.Module(body=body, type_ignores=[])) \
                    + ast.dump(node.args)
    visit(ast.parse(source).body, "")
    return found


def find_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    """Find a top-level function, or Class.method, by name."""
    parts = name.split(".")
    scope = tree.body
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        wanted = (ast.FunctionDef, ast.AsyncFunctionDef) if last else (ast.ClassDef,)
        match = next((n for n in scope if isinstance(n, wanted) and n.name == part), None)
        if match is None:
            return None
        if last:
            return match
        scope = match.body
    return None


def set_docstring(source: str, node: ast.FunctionDef, docstring: str) -> str:
    """Return source with the function's docstring replaced or inserted."""
    lines = source.splitlines(keepends=True)
    first = node.body[0]
    indent = " " * first.col_offset
    new_line = f'{indent}"""{docstring}"""\n'
    has_docstring = (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                     and isinstance(first.value.value, str))
    if has_docstring:
        lines[first.lineno - 1:first.end_lineno] = [new_line]
    else:
        lines.insert(first.lineno - 1, new_line)
    return "".join(lines)
