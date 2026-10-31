"""GitHub repo mode. The token comes from the GH_TOKEN env var and never reaches the sandbox.

    python agent/github_mode.py clone <repo_url> <dest_dir>
    python agent/github_mode.py pr <report.json> <repo_dir> <out_dir>
"""
import base64, json, os, re, subprocess, sys, time
from pathlib import Path

import httpx

from open_pr import build_body

TOKEN = os.environ.get("GH_TOKEN", "")
AUTH = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
GIT = ["git", "-c", f"http.extraheader=AUTHORIZATION: basic {AUTH}"]
API = "https://api.github.com"
REPO_RE = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def scrub(s):
    for secret in (TOKEN, AUTH):
        if secret:
            s = s.replace(secret, "***")
    return s


def run(*cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(scrub(f"command failed ({r.returncode}): {' '.join(cmd[-4:])}\n{r.stdout}{r.stderr}"))
    return r.stdout.strip()


def api(method, path, **kw):
    r = httpx.request(method, API + path, timeout=60, headers={
        "Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"}, **kw)
    if r.status_code >= 400:
        raise RuntimeError(scrub(f"GitHub API {method} {path} -> {r.status_code}: {r.text[:400]}"))
    return r.json()


def parse(url):
    m = REPO_RE.search(url.strip())
    if not m:
        raise RuntimeError(f"not a GitHub repo URL: {url}")
    return m.group(1), m.group(2)


def cmd_clone(url, dest):
    owner, name = parse(url)
    info = api("GET", f"/repos/{owner}/{name}")
    branch = info["default_branch"]
    perms = info.get("permissions") or {}
    if perms and not perms.get("push"):
        raise RuntimeError("this token cannot push to the repo (forks are not supported yet)")
    print(f"Repo {owner}/{name}, default branch: {branch}")
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    run(*GIT, "clone", "--depth", "1", "--branch", branch, f"https://github.com/{owner}/{name}.git", dest)
    n = sum(1 for p in Path(dest).rglob("*") if p.is_file() and ".git" not in p.parts)
    print(f"Cloned {n} files")


def cmd_pr(report_path, repo_dir, out_dir):
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    result = json.loads((Path(out_dir) / "result.json").read_text(encoding="utf-8"))
    checks = result["checks"]
    if not all(checks.values()):
        raise RuntimeError("verification did not pass, so no PR will be opened")
    summary = next((m["content"] for m in reversed(result["messages"])
                    if m["role"] == "assistant" and m.get("content")), "")
    owner, name = parse(run("git", "remote", "get-url", "origin", cwd=repo_dir))
    base = api("GET", f"/repos/{owner}/{name}")["default_branch"]
    branch = f"bug2pr/fix-{int(time.time())}"
    patch = (Path(out_dir) / "fix.patch").read_bytes().replace(b"\r\n", b"\n")
    patch_file = Path(out_dir) / "apply.patch"
    patch_file.write_bytes(patch)

    symptom = report.get("symptom", "bug fix").split(".")[0][:70]
    run("git", "checkout", "-b", branch, cwd=repo_dir)
    run("git", "apply", "--ignore-whitespace", str(patch_file.resolve()), cwd=repo_dir)
    run("git", "add", "-A", cwd=repo_dir)
    run("git", "-c", "user.name=bug2pr", "-c", "user.email=bug2pr@users.noreply.github.com",
        "commit", "-m", f"Fix: {symptom}", cwd=repo_dir)
    run(*GIT, "push", "-u", "origin", branch, cwd=repo_dir)
    pr = api("POST", f"/repos/{owner}/{name}/pulls", json={
        "title": f"Fix: {symptom}", "head": branch, "base": base,
        "body": build_body(report, summary, checks)})
    print("Pull request opened:", pr["html_url"])


if __name__ == "__main__":
    try:
        {"clone": cmd_clone, "pr": cmd_pr}[sys.argv[1]](*sys.argv[2:])
    except Exception as e:  # noqa: BLE001
        print("ERROR:", scrub(str(e)))
        sys.exit(1)