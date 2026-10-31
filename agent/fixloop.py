import base64, difflib, io, json, os, shlex, sys, tarfile
from pathlib import Path

import modal

from llm import MODEL, chat

OUT = Path(os.environ.get("OUT_DIR", "out"))
PREFIX = os.environ.get("PATCH_PREFIX", "demo-app/")   # "" for a real repo root
TEST_CMD = os.environ.get("TEST_CMD", "python -m pytest -q")
ESCALATE = os.environ.get("ESCALATE_MODEL", "")
MAX_STEPS = int(os.environ.get("MAX_STEPS", 30))
SKIP = {"__pycache__", ".pytest_cache", ".git", ".venv", "venv", "node_modules", ".mypy_cache"}
MAX_TAR = 20_000_000

SYSTEM = """You are a careful software engineer fixing a bug in a Python repo.
You get a structured bug report. It was written from a screen recording, so it may be incomplete or
point at the wrong file: verify against the real code before trusting it. Work in this order:
1. Explore: list files, search and read the relevant code.
2. Add a NEW regression test that reproduces the bug. Run the tests and confirm it FAILS for the right reason.
3. Fix the ROOT CAUSE in the source code (not in the tests), with the smallest change that is correct.
   The fix may be in a different file than the report suggests.
4. Run the full test suite again until everything passes.
5. Reply with a short summary: the root cause and what you changed.
Never delete or weaken existing tests; only add to them. Use only the provided tools."""


def tool(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}

S = {"type": "string"}
I = {"type": "integer"}
TOOLS = [
    tool("list_files", "List all files in the repo.", {}, []),
    tool("search_code", "Search all text files for a pattern. Returns matching lines with file and line number.", {"pattern": S}, ["pattern"]),
    tool("read_file", "Read a file (path relative to repo root). For large files pass start/end (1-based line numbers).", {"path": S, "start": I, "end": I}, ["path"]),
    tool("edit_file", "Replace exactly one occurrence of old text with new text in a file.", {"path": S, "old": S, "new": S}, ["path", "old", "new"]),
    tool("write_file", "Create or overwrite a file with the given content.", {"path": S, "content": S}, ["path", "content"]),
    tool("run_tests", "Run the full test suite and return the output.", {}, []),
]


def is_test(p):
    n = Path(p).name
    return n.startswith("test_") or n.endswith("_test.py")


def pack(repo):
    """Tarball of the repo (for the sandbox) plus a dict of text-file originals (for diffing)."""
    buf, originals = io.BytesIO(), {}
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in sorted(repo.rglob("*")):
            rel = p.relative_to(repo)
            if not p.is_file() or SKIP.intersection(rel.parts) or p.stat().st_size > 2_000_000:
                continue
            tar.add(p, arcname=rel.as_posix())
            try:
                originals[rel.as_posix()] = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                pass
    blob = buf.getvalue()
    if len(blob) > MAX_TAR:
        raise RuntimeError(f"repo too large for the sandbox copy ({len(blob)} bytes)")
    return blob, originals


class Box:
    """A Modal sandbox holding a copy of the repo. The agent can only touch this copy."""

    def __init__(self, repo):
        app = modal.App.lookup("bug2pr", create_if_missing=True)
        image = modal.Image.debian_slim().pip_install("pytest")
        self.sb = modal.Sandbox.create(app=app, image=image, timeout=1800)
        self.sb.exec("mkdir", "-p", "/work").wait()
        blob, self.originals = pack(repo)
        self.touched = set()
        self.sb.filesystem.write_text(base64.b64encode(blob).decode(), "/tmp/repo.b64")
        code, out = self.sh("base64 -d /tmp/repo.b64 | tar xz -C /work && rm /tmp/repo.b64")
        if code != 0:
            raise RuntimeError("could not unpack repo in sandbox: " + out[-300:])
        _, out = self.sh("[ -f requirements.txt ] && pip install -q -r requirements.txt; "
                         "[ -f pyproject.toml -o -f setup.py ] && pip install -q -e .", timeout=900)
        print("[setup] repo copied into sandbox" + (f"; install output tail: {out[-300:]}" if out.strip() else ""))

    def sh(self, cmd, timeout=120):
        p = self.sb.exec("bash", "-c", f"cd /work && {cmd}", timeout=timeout)
        p.wait()
        return p.returncode, p.stdout.read() + p.stderr.read()

    def _safe(self, path):
        if path.startswith(("/", "\\")) or ":" in path or ".." in Path(path).parts:
            raise ValueError("path must be relative to the repo root")
        return Path(path).as_posix()

    def read(self, path):
        return self.sb.filesystem.read_text(f"/work/{self._safe(path)}")

    def write(self, path, text):
        rel = self._safe(path)
        parent = Path(rel).parent.as_posix()
        if parent != ".":
            self.sb.exec("mkdir", "-p", f"/work/{parent}").wait()
        self.sb.filesystem.write_text(text, f"/work/{rel}")

    # ---- tools the agent can call ----
    def list_files(self):
        _, out = self.sh("find . -type f -not -path './.git/*' -not -name '*.pyc' | sort | head -300")
        return out or "empty"

    def search_code(self, pattern):
        _, out = self.sh(f"grep -rIn --exclude-dir=.git --exclude-dir=__pycache__ -e {shlex.quote(pattern)} . | head -80")
        return out or "no matches"

    def read_file(self, path, start=None, end=None):
        text = self.read(path)
        if start or end:
            lines = text.splitlines()
            s, e = max(int(start or 1), 1), int(end or len(lines))
            return "\n".join(lines[s - 1:e]) + f"\n[lines {s}-{min(e, len(lines))} of {len(lines)}]"
        if len(text) > 8000:
            return text[:8000] + f"\n[truncated: {len(text)} chars, use start/end to read more]"
        return text

    def edit_file(self, path, old, new):
        text = self.read(path)
        n = text.count(old)
        if n != 1:
            return f"ERROR: old text must match exactly once, found {n} matches"
        self.write(path, text.replace(old, new))
        self.touched.add(self._safe(path))
        return "ok"

    def write_file(self, path, content):
        self.write(path, content)
        self.touched.add(self._safe(path))
        return "ok"

    def tests(self):
        return self.sh(f"{TEST_CMD} 2>&1", timeout=300)

    def run_tests(self):
        code, out = self.tests()
        return f"exit_code={code}\n{out[-4000:]}"


def dispatch(box, name, raw_args):
    fn = getattr(box, name, None) if name in {t["function"]["name"] for t in TOOLS} else None
    if fn is None:
        return f"ERROR: unknown tool {name}"
    try:
        return str(fn(**json.loads(raw_args or "{}")))[:9000]
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"


def run_agent(box, report, model):
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Bug report:\n" + json.dumps(report, indent=2)}]
    for step in range(1, MAX_STEPS + 1):
        resp = chat(model=model, messages=messages, tools=TOOLS)
        msg = resp.choices[0].message
        calls = msg.tool_calls or []
        entry = {"role": "assistant", "content": msg.content or ""}
        if calls:
            entry["tool_calls"] = [{"id": c.id, "type": "function",
                                    "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                   for c in calls]
        messages.append(entry)
        if not calls:
            print("\nAGENT SUMMARY:", msg.content)
            return messages
        for c in calls:
            print(f"[{step}] {c.function.name} {c.function.arguments[:100]}")
            messages.append({"role": "tool", "tool_call_id": c.id,
                             "content": dispatch(box, c.function.name, c.function.arguments)})
    print("Reached the step limit")
    return messages


def deletions(a, b):
    return sum(1 for l in difflib.ndiff(a.splitlines(), b.splitlines()) if l.startswith("- "))


def verify(box):
    fixed = {p: box.read(p) for p in sorted(box.touched)}
    code_fix, _ = box.tests()
    for p in fixed:  # put the original buggy source back, keep the new tests
        if p in box.originals and not is_test(p):
            box.write(p, box.originals[p])
    code_orig, _ = box.tests()
    for p, text in fixed.items():  # restore the fix
        box.write(p, text)
    return fixed, {
        "tests_pass_with_fix": code_fix == 0,
        "new_test_fails_on_original_code": code_orig != 0,
        "test_file_changed": any(is_test(p) for p in fixed),
        "source_file_changed": any(not is_test(p) for p in fixed),
        "existing_tests_preserved": all(deletions(box.originals[p], t) == 0
                                        for p, t in fixed.items() if is_test(p) and p in box.originals),
    }


def make_patch(fixed, originals):
    chunks = []
    for p in sorted(fixed):
        old = originals.get(p)
        if old == fixed[p]:
            continue
        a = (old or "").splitlines(keepends=True)
        b = fixed[p].splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            a, b, fromfile=f"a/{PREFIX}{p}" if old is not None else "/dev/null", tofile=f"b/{PREFIX}{p}"))
        if not diff:
            continue
        chunks.append(f"diff --git a/{PREFIX}{p} b/{PREFIX}{p}\n")
        if old is None:
            chunks.append("new file mode 100644\n")
        for line in diff:
            if not line.endswith("\n"):
                line += "\n\\ No newline at end of file\n"
            chunks.append(line)
    return "".join(chunks)


def attempt(report, repo, model):
    box = Box(repo)
    try:
        messages = run_agent(box, report, model)
        fixed, checks = verify(box)
    finally:
        box.sb.terminate()
    return box, messages, fixed, checks


def main(report_path, repo_dir):
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    repo = Path(repo_dir)
    models = [MODEL] + ([ESCALATE] if ESCALATE and ESCALATE != MODEL else [])
    for i, model in enumerate(models):
        print(f"MODEL: {model}")
        box, messages, fixed, checks = attempt(report, repo, model)
        if all(checks.values()):
            break
        if i + 1 < len(models):
            print("Verification failed; escalating to", models[i + 1])
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "fix.patch", "w", encoding="utf-8", newline="\n") as f:
        f.write(make_patch(fixed, box.originals))
    (OUT / "result.json").write_text(
        json.dumps({"checks": checks, "model_used": model, "messages": messages}, indent=2), encoding="utf-8")
    print("\nVERIFICATION:", json.dumps(checks, indent=2))
    print(f"Patch saved to {OUT / 'fix.patch'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.environ.get("REPO_DIR", "demo-app"))