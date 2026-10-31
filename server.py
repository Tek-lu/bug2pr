"""bug2pr web UI: runs the scripts as subprocesses and streams their output.

Run from the project root:
    python -m uvicorn server:app --port 8000
Do NOT use --reload.

Two modes: demo mode (no repo URL, uses demo-app) and repo mode (GitHub URL + token).
"""
import json, os, re, subprocess, sys, threading, time, uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
OUT = ROOT / "out"
WORK = ROOT / "work"
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
PR_RE = re.compile(r"https://github\.com/\S+/pull/\d+")
REPO_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+?(?:\.git)?/?$")

app = FastAPI()
JOBS = {}
BUSY = threading.Lock()  # one job at a time


def log(job, line):
    tok = job.get("token")
    job["lines"].append(line.replace(tok, "***") if tok else line)


def run_step(job, label, script, *args, env=None):
    log(job, f"=== {label} ===")
    p = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "agent" / script), *args],
        cwd=ROOT, env={**ENV, **(env or {})}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:
        log(job, line.rstrip())
    return p.wait()


def fail(job, msg):
    log(job, f"ERROR: {msg}")
    job["status"] = "error"


def pipeline(job):
    try:
        repo_mode = bool(job["repo_url"])
        job["stage"] = "understand"
        rc = run_step(job, "1/3 Understand the recording", "understand.py", job["video"])
        rp = Path(job["report_path"])
        if rc != 0 or not rp.exists():
            return fail(job, "understand step failed (see log above)")
        job["report"] = json.loads(rp.read_text(encoding="utf-8"))

        job["stage"] = "fix"
        out_dir = Path(job["out_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in (out_dir / "result.json", out_dir / "fix.patch"):
            f.unlink(missing_ok=True)

        fix_args, fix_env = [job["report_path"]], {"OUT_DIR": str(out_dir)}
        if repo_mode:
            rc = run_step(job, "2/3 Clone repository", "github_mode.py", "clone",
                          job["repo_url"], job["repo_dir"], env={"GH_TOKEN": job["token"]})
            if rc != 0:
                return fail(job, "clone failed (see log above)")
            fix_args.append(job["repo_dir"])
            fix_env["PATCH_PREFIX"] = ""
            if job["test_cmd"]:
                fix_env["TEST_CMD"] = job["test_cmd"]
        rc = run_step(job, "3/3 Fix loop and verification", "fixloop.py", *fix_args, env=fix_env)
        result = out_dir / "result.json"
        if rc != 0 or not result.exists():
            return fail(job, "fix loop failed (see log above)")
        data = json.loads(result.read_text(encoding="utf-8"))
        job["checks"] = data["checks"]
        job["summary"] = next((m["content"] for m in reversed(data["messages"])
                               if m["role"] == "assistant" and m.get("content")), "")
        patch = out_dir / "fix.patch"
        job["patch"] = patch.read_text(encoding="utf-8") if patch.exists() else ""
        job["stage"] = "verified"
        job["status"] = "ready" if all(job["checks"].values()) else "failed"
    except Exception as e:  # noqa: BLE001
        fail(job, repr(e))
    finally:
        if job["status"] != "ready":
            job["token"] = None
        BUSY.release()


def pr_pipeline(job):
    try:
        if job["repo_url"]:
            rc = run_step(job, "Open pull request", "github_mode.py", "pr", job["report_path"],
                          job["repo_dir"], job["out_dir"], env={"GH_TOKEN": job["token"]})
        else:
            rc = run_step(job, "Open pull request", "open_pr.py", job["report_path"])
        m = PR_RE.search("\n".join(job["lines"]))
        if rc == 0 and m:
            job["pr_url"] = m.group(0)
            job["stage"] = "pr"
            job["status"] = "done"
            job["token"] = None
        else:
            log(job, "ERROR: PR was not opened (see log above)")
            job["status"] = "pr_failed"
    except Exception as e:  # noqa: BLE001
        log(job, f"ERROR: {e!r}")
        job["status"] = "pr_failed"
    finally:
        BUSY.release()


@app.get("/")
def index():
    return FileResponse(ROOT / "ui.html")


@app.post("/api/upload")
def upload(file: UploadFile = File(...), repo_url: str = Form(""), token: str = Form(""),
           test_cmd: str = Form("")):
    repo_url, token, test_cmd = repo_url.strip(), token.strip(), test_cmd.strip()
    if repo_url and not REPO_RE.match(repo_url):
        raise HTTPException(400, "Repo URL must look like https://github.com/owner/name")
    if repo_url and not token:
        raise HTTPException(400, "A GitHub token is required for repo mode.")
    if not BUSY.acquire(blocking=False):
        raise HTTPException(409, "Another job is still running.")
    try:
        SAMPLES.mkdir(exist_ok=True)
        jid = uuid.uuid4().hex[:8]
        stem = f"ui_{int(time.time())}"
        video = SAMPLES / f"{stem}{Path(file.filename or 'x.mp4').suffix or '.mp4'}"
        with open(video, "wb") as f:
            while chunk := file.file.read(1 << 20):
                f.write(chunk)
        jdir = WORK / jid
        job = {"id": jid, "status": "running", "stage": "upload", "lines": [],
               "video": str(video), "report_path": str(SAMPLES / f"{stem}.report.json"),
               "repo_url": repo_url, "token": token or None, "test_cmd": test_cmd,
               "repo_dir": str(jdir / "repo"), "out_dir": str(jdir / "out") if repo_url else str(OUT),
               "report": None, "checks": None, "summary": "", "patch": "", "pr_url": None}
        JOBS[jid] = job
        threading.Thread(target=pipeline, args=(job,), daemon=True).start()
        return {"job_id": jid}
    except Exception:
        BUSY.release()
        raise


@app.get("/api/jobs/{jid}")
def get_job(jid: str, after: int = 0):
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(404, "unknown job")
    return {"status": job["status"], "stage": job["stage"],
            "lines": job["lines"][after:], "next": len(job["lines"]),
            "report": job["report"], "checks": job["checks"], "summary": job["summary"],
            "patch": job["patch"], "pr_url": job["pr_url"], "repo_url": job["repo_url"]}


@app.post("/api/jobs/{jid}/pr")
def open_pr(jid: str):
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(404, "unknown job")
    if job["status"] not in ("ready", "pr_failed") or job["pr_url"]:
        raise HTTPException(400, "This job is not ready for a PR.")
    if not BUSY.acquire(blocking=False):
        raise HTTPException(409, "Another job is still running.")
    job["status"] = "pr_opening"
    threading.Thread(target=pr_pipeline, args=(job,), daemon=True).start()
    return {"ok": True}