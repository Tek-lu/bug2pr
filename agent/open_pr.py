import json, subprocess, sys, tempfile, time
from pathlib import Path


def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stdout}{r.stderr}")
    return r.stdout.strip()


def build_body(report, summary, checks):
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(report.get("steps_to_reproduce", []), 1))
    check_lines = "\n".join(f"- {'PASS' if v else 'FAIL'}: {k.replace('_', ' ')}" for k, v in checks.items())
    return f"""## Bug (from the developer's screen recording and voice note)
**Symptom:** {report.get('symptom', '')}

**Steps to reproduce**
{steps}

**Expected:** {report.get('expected', '')}
**Actual:** {report.get('actual', '')}

## Agent's explanation
{summary}

## Verification
{check_lines}

The new test was also confirmed to fail on the original code.

---
Opened automatically by bug2pr. Please review before merging.
"""


def main(report_path):
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    result = json.loads(Path("out/result.json").read_text(encoding="utf-8"))
    checks = result["checks"]
    if not all(checks.values()):
        sys.exit("Verification did not pass, so no PR will be opened.")
    summary = next((m["content"] for m in reversed(result["messages"])
                    if m["role"] == "assistant" and m.get("content")), "")

    original = run("git", "rev-parse", "--abbrev-ref", "HEAD")
    default = run("gh", "repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name")
    branch = f"bug2pr/fix-{int(time.time())}"
    assert branch != default

    patch = Path("out/fix.patch").read_bytes().replace(b"\r\n", b"\n")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".patch") as f:
        f.write(patch)
        patch_path = f.name

    try:
        run("git", "checkout", "-b", branch)
        run("git", "apply", "--ignore-whitespace", patch_path)

        local = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd="demo-app")
        if local.returncode != 0:
            sys.exit("Tests fail locally after applying the patch. Stopping before commit.")

        run("git", "add", "demo-app")
        symptom = report.get("symptom", "bug fix").split(".")[0][:70]
        run("git", "commit", "-m", f"Fix: {symptom}")
        run("git", "push", "-u", "origin", branch)

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".md", encoding="utf-8") as f:
            f.write(build_body(report, summary, checks))
            body_path = f.name
        url = run("gh", "pr", "create", "--base", default, "--head", branch,
                  "--title", f"Fix: {symptom}", "--body-file", body_path)
        print("Pull request opened:", url)
    finally:
        run("git", "checkout", original)


if __name__ == "__main__":
    main(sys.argv[1])