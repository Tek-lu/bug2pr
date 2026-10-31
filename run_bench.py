# import json, os, subprocess, sys, time
# from concurrent.futures import ThreadPoolExecutor
# from pathlib import Path

# ROOT = Path(__file__).resolve().parent


# def run(bug):
#     out = ROOT / "out" / "bench" / bug.name
#     out.mkdir(parents=True, exist_ok=True)
#     for f in out.glob("*"):
#         f.unlink()
#     env = {**os.environ, "OUT_DIR": str(out), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PATCH_PREFIX": ""}
#     t = time.time()
#     p = subprocess.run([sys.executable, "-u", str(ROOT / "agent" / "fixloop.py"),
#                         str(bug / "report.json"), str(bug / "repo")],
#                        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
#     (out / "log.txt").write_text(p.stdout + p.stderr, encoding="utf-8")
#     row = {"bug": bug.name, "secs": round(time.time() - t), "ok": False, "model": "-", "steps": 0, "failed": []}
#     res = out / "result.json"
#     if p.returncode != 0 or not res.exists():
#         row["failed"] = ["crashed: see " + str(out / "log.txt")]
#         return row
#     data = json.loads(res.read_text(encoding="utf-8"))
#     row["ok"] = all(data["checks"].values())
#     row["model"] = data.get("model_used", "-")
#     row["steps"] = sum(1 for m in data["messages"] if m.get("tool_calls"))
#     row["failed"] = [k for k, v in data["checks"].items() if not v]
#     return row


# def main():
#     bugs = sorted(p for p in (ROOT / "bugs").iterdir() if (p / "report.json").exists())
#     if len(sys.argv) > 1:
#         bugs = [b for b in bugs if any(a in b.name for a in sys.argv[1:])]
#     with ThreadPoolExecutor(int(os.environ.get("BENCH_WORKERS", 3))) as ex:
#         rows = list(ex.map(run, bugs))
#     print(f"\n{'bug':<24}{'result':<8}{'steps':<7}{'secs':<6}{'model':<22}failed checks")
#     for r in rows:
#         print(f"{r['bug']:<24}{'PASS' if r['ok'] else 'FAIL':<8}{r['steps']:<7}{r['secs']:<6}{r['model']:<22}{', '.join(r['failed'])}")
#     n = sum(r["ok"] for r in rows)
#     print(f"\n{n}/{len(rows)} fixed and verified")
#     (ROOT / "out" / "bench" / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


# if __name__ == "__main__":
#     main()

import json, os, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def hidden_check(bug, out):
    """Apply the agent's patch to a fresh copy of the repo and run the tests the agent never saw."""
    hidden = bug / "hidden"
    if not hidden.exists():
        return None
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(bug / "repo", work)
        patch = out / "fix.patch"
        if patch.exists() and patch.read_text(encoding="utf-8").strip():
            p = subprocess.run(["git", "apply", "--ignore-whitespace", str(patch.resolve())],
                               cwd=work, capture_output=True, text=True)
            if p.returncode != 0:
                (out / "hidden.txt").write_text("git apply failed:\n" + p.stderr, encoding="utf-8")
                return False
        shutil.copytree(hidden, work, dirs_exist_ok=True)
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                               cwd=work, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            (out / "hidden.txt").write_text("hidden tests timed out", encoding="utf-8")
            return False
        (out / "hidden.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
        return r.returncode == 0


def run(bug):
    out = ROOT / "out" / "bench" / bug.name
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*"):
        if f.is_file():
            f.unlink()
    env = {**os.environ, "OUT_DIR": str(out), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PATCH_PREFIX": ""}
    t = time.time()
    p = subprocess.run([sys.executable, "-u", str(ROOT / "agent" / "fixloop.py"),
                        str(bug / "report.json"), str(bug / "repo")],
                       cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (out / "log.txt").write_text(p.stdout + p.stderr, encoding="utf-8")
    row = {"bug": bug.name, "secs": round(time.time() - t), "agent_ok": False, "hidden": None,
           "model": "-", "steps": 0, "failed": []}
    res = out / "result.json"
    if p.returncode != 0 or not res.exists():
        row["failed"] = ["crashed: see " + str(out / "log.txt")]
        return row
    data = json.loads(res.read_text(encoding="utf-8"))
    row["agent_ok"] = all(data["checks"].values())
    row["model"] = data.get("model_used", "-")
    row["steps"] = sum(1 for m in data["messages"] if m.get("tool_calls"))
    row["failed"] = [k for k, v in data["checks"].items() if not v]
    row["hidden"] = hidden_check(bug, out)
    return row


def label(v):
    return "-" if v is None else ("PASS" if v else "FAIL")


def main():
    bugs = sorted(p for p in (ROOT / "bugs").iterdir() if (p / "report.json").exists())
    if len(sys.argv) > 1:
        bugs = [b for b in bugs if any(a in b.name for a in sys.argv[1:])]
    with ThreadPoolExecutor(int(os.environ.get("BENCH_WORKERS", 3))) as ex:
        rows = list(ex.map(run, bugs))
    print(f"\n{'bug':<24}{'agent':<8}{'hidden':<8}{'steps':<7}{'secs':<6}{'model':<20}notes")
    for r in rows:
        note = ", ".join(r["failed"])
        if r["agent_ok"] and r["hidden"] is False:
            note = "FALSE POSITIVE: checks passed but hidden tests failed (see hidden.txt)"
        print(f"{r['bug']:<24}{label(r['agent_ok']):<8}{label(r['hidden']):<8}{r['steps']:<7}{r['secs']:<6}{r['model']:<20}{note}")
    real = sum(1 for r in rows if r["agent_ok"] and r["hidden"] is not False)
    fp = sum(1 for r in rows if r["agent_ok"] and r["hidden"] is False)
    print(f"\n{real}/{len(rows)} fixed, verified and passing hidden tests; {fp} false positive(s)")
    (ROOT / "out" / "bench").mkdir(parents=True, exist_ok=True)
    (ROOT / "out" / "bench" / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()