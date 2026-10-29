import difflib, json, os, shlex, sys
from pathlib import Path

import modal
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"])
MODEL = os.environ["LLM_MODEL"]
REPO_DIR = Path("demo-app")
MAX_STEPS = 20
SKIP = {"__pycache__", ".pytest_cache", ".git"}

SYSTEM = """You are a careful software engineer fixing a bug in a small Python repo.
You get a structured bug report. Work in this order:
1. Search and read the relevant code.
2. Add a NEW regression test that reproduces the bug. Run the tests and confirm it FAILS for the right reason.
3. Make the smallest possible fix in the source code (not in the tests).
4. Run the tests again until everything passes.
5. Reply with a short summary: the root cause and what you changed.
Never delete or weaken existing tests. Use only the provided tools."""


def tool(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}

S = {"type": "string"}
TOOLS = [
    tool("search_code", "Search Python files for a pattern. Returns matching lines with file and line number.", {"pattern": S}, ["pattern"]),
    tool("read_file", "Read a file (path relative to the repo root).", {"path": S}, ["path"]),
    tool("edit_file", "Replace exactly one occurrence of old text with new text in a file.", {"path": S, "old": S, "new": S}, ["path", "old", "new"]),
    tool("write_file", "Create or overwrite a file with the given content.", {"path": S, "content": S}, ["path", "content"]),
    tool("run_tests", "Run the full pytest suite and return the output.", {}, []),
]


def is_test(p):
    n = Path(p).name
    return n.startswith("test_") or n.endswith("_test.py")


class Box:
    """A Modal sandbox holding a copy of the repo. The agent can only touch this copy."""

    def __init__(self, repo):
        app = modal.App.lookup("bug2pr", create_if_missing=True)
        image = modal.Image.debian_slim().pip_install("pytest")
        self.sb = modal.Sandbox.create(app=app, image=image, timeout=900)
        self.sb.exec("mkdir", "-p", "/work").wait()
        self.originals, self.touched = {}, set()
        for p in sorted(repo.rglob("*")):
            if p.is_file() and not SKIP.intersection(p.parts):
                rel = p.relative_to(repo).as_posix()
                text = p.read_text(encoding="utf-8")
                self.originals[rel] = text
                self.write(rel, text)

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
    def search_code(self, pattern):
        _, out = self.sh(f"grep -rn --include='*.py' -e {shlex.quote(pattern)} . | head -50")
        return out or "no matches"

    def read_file(self, path):
        return self.read(path)

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
        return self.sh("python -m pytest -q 2>&1", timeout=180)

    def run_tests(self):
        code, out = self.tests()
        return f"exit_code={code}\n{out[-4000:]}"


def dispatch(box, name, raw_args):
    fn = {"search_code": box.search_code, "read_file": box.read_file, "edit_file": box.edit_file,
          "write_file": box.write_file, "run_tests": box.run_tests}.get(name)
    if fn is None:
        return f"ERROR: unknown tool {name}"
    try:
        return str(fn(**json.loads(raw_args or "{}")))[:6000]
    except Exception as e:
        return f"ERROR: {e}"


def run_agent(box, report):
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Bug report:\n" + json.dumps(report, indent=2)}]
    for step in range(1, MAX_STEPS + 1):
        resp = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
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
            result = dispatch(box, c.function.name, c.function.arguments)
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
    print("Reached the step limit")
    return messages


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
    }


def make_patch(box, fixed):
    chunks = []
    for p in sorted(fixed):
        old = box.originals.get(p)
        a = (old or "").splitlines(keepends=True)
        b = fixed[p].splitlines(keepends=True)
        chunks.append("".join(difflib.unified_diff(
            a, b,
            fromfile=f"a/demo-app/{p}" if old is not None else "/dev/null",
            tofile=f"b/demo-app/{p}")))
    return "".join(chunks)


def main(report_path):
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    box = Box(REPO_DIR)
    try:
        messages = run_agent(box, report)
        fixed, checks = verify(box)
    finally:
        box.sb.terminate()
    Path("out").mkdir(exist_ok=True)
    with open("out/fix.patch", "w", encoding="utf-8", newline="\n") as f:
        f.write(make_patch(box, fixed))
    Path("out/result.json").write_text(json.dumps({"checks": checks, "messages": messages}, indent=2))
    print("\nVERIFICATION:", json.dumps(checks, indent=2))
    print("Patch saved to out/fix.patch")


if __name__ == "__main__":
    main(sys.argv[1])