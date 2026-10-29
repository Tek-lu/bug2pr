import base64, json, os, re, subprocess, sys, tempfile
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"])
MODEL = os.environ["LLM_MODEL"]
MAX_FRAMES = 8  # Muse Spark Open accepts at most 8 images per request

SCHEMA_HINT = """Return ONLY a JSON object with these keys:
symptom (string), steps_to_reproduce (list of strings), expected (string),
actual (string), suspected_area (string), search_keywords (list of strings),
confidence (number from 0 to 1)."""


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def duration(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", video],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def extract_audio(video, out_wav):
    run(["ffmpeg", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", out_wav])


def extract_frames(video, out_dir):
    fps = MAX_FRAMES / duration(video)
    run(["ffmpeg", "-y", "-i", video, "-vf", f"fps={fps:.4f},scale=1280:-2",
         "-frames:v", str(MAX_FRAMES), f"{out_dir}/frame_%02d.jpg"])
    return sorted(Path(out_dir).glob("frame_*.jpg"))


def data_url(path, mime):
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


def transcribe(wav):
    r = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": [
        {"type": "text", "text": "Transcribe this recording word for word. Output only the transcript."},
        {"type": "audio_url", "audio_url": {"url": data_url(wav, "audio/wav")}},
    ]}])
    return r.choices[0].message.content.strip()


def parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON found")
    return json.loads(m.group(0))


def build_report(transcript, frames):
    content = [{"type": "text", "text":
        "A developer screen-recorded a software bug and narrated it.\n"
        f"Narration transcript:\n{transcript}\n\n"
        "The images are frames from the recording in time order. "
        "Read any code, commands and output visible on screen.\n\n" + SCHEMA_HINT}]
    for f in frames:
        content.append({"type": "image_url",
                        "image_url": {"url": data_url(f, "image/jpeg"), "detail": "auto"}})
    for _ in range(2):  # one retry if the model wraps or breaks the JSON
        r = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": content}])
        try:
            return parse_json(r.choices[0].message.content)
        except ValueError:
            continue
    raise RuntimeError("Model did not return valid JSON")


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        wav = f"{tmp}/audio.wav"
        extract_audio(video, wav)
        frames = extract_frames(video, tmp)
        print(f"{len(frames)} frames extracted")
        transcript = transcribe(wav)
        print("TRANSCRIPT:", transcript, "\n")
        report = build_report(transcript, frames)
    out = Path("samples") / (Path(video).stem + ".report.json")
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])