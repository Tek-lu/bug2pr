import base64, json, os, re, subprocess, sys, tempfile, uuid
from pathlib import Path

import httpx
from openai import OpenAI

from llm import MODEL, chat

MAX_FRAMES = int(os.environ.get("MAX_FRAMES", 12))
META_BASE = "https://api.meta.ai/v1"
META_KEY = os.environ.get("META_API_KEY") or os.environ["LLM_API_KEY"]
ASR_MODEL = os.environ.get("ASR_MODEL", "muse-voice-transcribe-1.0")
ASR_MODE = os.environ.get("ASR_MODE", "DIARIZATION")
ON_META = "meta.ai" in os.environ["LLM_BASE_URL"]

SCHEMA_HINT = """Return ONLY a JSON object with these keys:
symptom (string), steps_to_reproduce (list of strings), expected (string),
actual (string), suspected_area (string), search_keywords (list of strings),
confidence (number from 0 to 1)."""


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def duration(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", video],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def extract_audio(video, out_wav):
    # Muse Voice Transcribe format: WAV, mono, 16-bit PCM, 24 kHz
    run(["ffmpeg", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le",
         "-map_metadata", "-1", out_wav])


def extract_frames(video, out_dir):
    fps = MAX_FRAMES / duration(video)
    run(["ffmpeg", "-y", "-i", video, "-vf", f"fps={fps:.4f},scale=1280:-2",
         "-frames:v", str(MAX_FRAMES), f"{out_dir}/frame_%02d.jpg"])
    return sorted(Path(out_dir).glob("frame_*.jpg"))


def data_url(path, mime):
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


# ---------- transcription: three strategies, first one that returns text wins ----------
def texts_from(obj):
    if isinstance(obj, dict) and isinstance(obj.get("transcript"), str):
        return [obj["transcript"].strip()]
    out = []
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("transcript", "text") and isinstance(v, str) and v.strip():
                    out.append(v.strip())
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return out


def asr_voice(wav):
    req = {"mode": ASR_MODE, "model": ASR_MODEL, "audioEncoding": "WAV"}
    r = httpx.post(
        f"{META_BASE}/asr/transcribe", params={"sessionId": f"b2p-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {META_KEY}"},
        files={"request": (None, json.dumps(req), "application/json"),
               "audio": ("audio.wav", Path(wav).read_bytes(), "audio/wav")},
        timeout=300)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")
    print("[asr] raw response:", r.text[:300].replace("\n", " "))
    return " ".join(texts_from(r.json()))


def asr_spark12(wav):
    if not ON_META:
        raise RuntimeError("main provider is not Meta")
    b64 = base64.b64encode(Path(wav).read_bytes()).decode()
    r = chat(model="muse-spark-1.2", max_tokens=4000, messages=[{"role": "user", "content": [
        {"type": "text", "text": "Transcribe this audio. Return only the transcript."},
        {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}}]}])
    return (r.choices[0].message.content or "").strip()


def asr_baseten(wav):
    if "STT_BASE_URL" not in os.environ:
        raise RuntimeError("STT_* not set")
    c = OpenAI(base_url=os.environ["STT_BASE_URL"], api_key=os.environ["STT_API_KEY"], timeout=300)
    r = c.chat.completions.create(model=os.environ["STT_MODEL"], messages=[{"role": "user", "content": [
        {"type": "text", "text": "Transcribe this recording word for word. Output only the transcript."},
        {"type": "audio_url", "audio_url": {"url": data_url(wav, "audio/wav")}}]}])
    return r.choices[0].message.content.strip()


def transcribe(wav):
    errors = []
    for name, fn in (("muse-voice-transcribe", asr_voice), ("muse-spark-1.2", asr_spark12),
                     ("baseten", asr_baseten)):
        try:
            text = fn(wav)
            if text:
                print(f"[asr] used {name}")
                return text
            errors.append(f"{name}: empty result")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {str(e)[:300]}")
    print("[asr] all strategies failed:\n  " + "\n  ".join(errors))
    return ""


# ---------- bug report ----------
def parse_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON found")
    return json.loads(m.group(0))


def build_report(transcript, frames):
    content = [{"type": "text", "text":
        "A developer screen-recorded a software bug and narrated it.\n"
        f"Narration transcript:\n{transcript or '(no narration available)'}\n\n"
        "The images are frames from the recording in time order. "
        "Read any code, commands and output visible on screen.\n\n" + SCHEMA_HINT}]
    for f in frames:
        content.append({"type": "image_url", "image_url": {"url": data_url(f, "image/jpeg")}})
    for _ in range(3):
        r = chat(messages=[{"role": "user", "content": content}], max_tokens=8000)
        try:
            return parse_json(r.choices[0].message.content)
        except ValueError:
            continue
    raise RuntimeError("Model did not return valid JSON")


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        wav = f"{tmp}/audio.wav"
        transcript = ""
        try:
            extract_audio(video, wav)
            transcript = transcribe(wav)
        except subprocess.CalledProcessError:
            print("[asr] no audio track found; continuing from frames only")
        frames = extract_frames(video, tmp)
        print(f"{len(frames)} frames extracted")
        print("TRANSCRIPT:", transcript, "\n")
        report = build_report(transcript, frames)
    Path("samples").mkdir(exist_ok=True)
    out = Path("samples") / (Path(video).stem + ".report.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])