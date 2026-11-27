"""100% FREE: Idea -> script -> images -> Hindi voice -> final MP4.

Uses: Pollinations (free text + image AI), Edge-TTS / gTTS (free voice), FFmpeg (free video).

Usage:
    python pipeline.py "एक गरीब लड़के की कहानी जो आसमान में उड़ना चाहता है"
    python pipeline.py "idea" --scenes 6 --format vertical --language Hindi
"""
import argparse
import asyncio
import json
import os
import random
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

VOICE = os.getenv("VOICE", "hi-IN-SwaraNeural")
POLL_KEY = os.getenv("POLLINATIONS_API_KEY", "").strip()

FORMATS = {
    "vertical": {"video": (1080, 1920), "image": (720, 1280)},     # Shorts / Reels
    "horizontal": {"video": (1920, 1080), "image": (1280, 720)},   # YouTube
}
UA = {"User-Agent": "Mozilla/5.0 (idea2video)"}


def log(msg):
    print(msg, flush=True)


def retry(fn, tries=4, wait=6, what="request"):
    last = None
    for n in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            log(f"    {what} failed ({n}/{tries}): {str(e)[:120]}")
            time.sleep(wait * n)
    raise RuntimeError(f"{what} failed after {tries} tries: {last}")


# ---------------------------------------------------------------- 1. SCRIPT
def extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON found in model reply")
    return json.loads(text[start:end + 1])


def _chat(messages: list) -> str:
    if POLL_KEY:
        url, headers = "https://gen.pollinations.ai/v1/chat/completions", {"Authorization": f"Bearer {POLL_KEY}"}
    else:
        url, headers = "https://text.pollinations.ai/openai", {}
    body = json.dumps({"model": "openai", "messages": messages, "seed": random.randint(1, 99999)}).encode()
    req = urllib.request.Request(url, data=body, headers={**UA, **headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]


def write_script(idea: str, scenes: int, language: str) -> dict:
    system = (
        "You are a short-video scriptwriter. Reply with ONLY valid JSON, no extra text, of the form: "
        '{"title": str, "description": str, "hashtags": [str], "style": str, '
        '"scenes": [{"narration": str, "image_prompt": str}]}. '
        f"Write title, description and narration in {language}. Each narration is 1-3 short vivid "
        "sentences (8-15 seconds when spoken). The first scene must hook the viewer. "
        "image_prompt must be in English, describe one clear visual, and must NOT ask for any text, "
        "letters or captions in the image. 'style' is ONE English sentence describing a consistent "
        "art style and the main characters' look."
    )
    user = f"Idea: {idea}\nNumber of scenes: {scenes}"

    def go():
        data = extract_json(_chat([{"role": "system", "content": system}, {"role": "user", "content": user}]))
        if not data.get("scenes"):
            raise ValueError("no scenes in reply")
        for s in data["scenes"]:
            if not s.get("narration") or not s.get("image_prompt"):
                raise ValueError("scene missing narration/image_prompt")
        return data

    return retry(go, what="script")


# ---------------------------------------------------------------- 2. IMAGES
def fallback_card(path: Path, size, text: str, idx: int):
    """If the free image service is down, still make a nice colour card so the video builds."""
    from PIL import Image, ImageDraw

    w, h = size
    random.seed(idx * 7)
    c1 = tuple(random.randint(20, 120) for _ in range(3))
    c2 = tuple(random.randint(100, 230) for _ in range(3))
    img = Image.new("RGB", size)
    px = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(c1[k] * (1 - t) + c2[k] * t) for k in range(3)))
    img.save(path)


def make_images(script: dict, fmt: str, out: Path) -> list[Path]:
    w, h = FORMATS[fmt]["image"]
    style = script.get("style", "")
    paths = []
    for i, scene in enumerate(script["scenes"], 1):
        log(f"  image {i}/{len(script['scenes'])}")
        prompt = f"{scene['image_prompt']}. {style}. cinematic, detailed, no text, no letters, no watermark"
        q = urllib.parse.quote(prompt[:900])
        seed = random.randint(1, 99999)
        if POLL_KEY:
            url = f"https://gen.pollinations.ai/image/{q}?width={w}&height={h}&seed={seed}&nologo=true&key={POLL_KEY}"
        else:
            url = f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&seed={seed}&nologo=true&model=flux"
        path = out / f"scene_{i:02d}.jpg"

        def fetch():
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            if len(data) < 5000:
                raise ValueError("image too small / not an image")
            path.write_bytes(data)

        try:
            retry(fetch, tries=3, wait=8, what=f"image {i}")
        except Exception as e:  # noqa: BLE001
            log(f"    using colour card for scene {i} ({str(e)[:80]})")
            path = out / f"scene_{i:02d}.png"
            fallback_card(path, (w, h), scene["narration"], i)
        paths.append(path)
        time.sleep(3)  # be gentle with the free service
    return paths


# ---------------------------------------------------------------- 3. VOICE
async def _edge(text: str, path: Path):
    import edge_tts

    await edge_tts.Communicate(text, VOICE).save(str(path))


def _gtts(text: str, path: Path, language: str):
    from gtts import gTTS

    gTTS(text=text, lang="hi" if language.lower().startswith("hi") else "en").save(str(path))


def make_voices(script: dict, out: Path, language: str) -> list[Path]:
    paths = []
    for i, scene in enumerate(script["scenes"], 1):
        log(f"  voice {i}/{len(script['scenes'])}")
        p = out / f"voice_{i:02d}.mp3"
        text = scene["narration"]
        try:
            retry(lambda: asyncio.run(_edge(text, p)), tries=3, wait=4, what="edge-tts")
            if not p.exists() or p.stat().st_size < 1000:
                raise ValueError("empty audio")
        except Exception:  # noqa: BLE001
            log("    edge-tts unavailable, using gTTS")
            retry(lambda: _gtts(text, p, language), tries=3, wait=4, what="gTTS")
        paths.append(p)
    return paths


# ---------------------------------------------------------------- 4. VIDEO
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{r.stderr[-1500:]}")
    return r.stdout


def duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def render_video(images: list[Path], voices: list[Path], fmt: str, out: Path) -> Path:
    w, h = FORMATS[fmt]["video"]
    fps = 25
    clips = []
    for i, (img, voice) in enumerate(zip(images, voices), 1):
        log(f"  render scene {i}/{len(images)}")
        dur = duration(voice) + 0.4
        frames = int(dur * fps)
        z = "min(zoom+0.0008,1.25)" if i % 2 else "if(eq(on,0),1.25,max(zoom-0.0008,1.0))"
        vf = (f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
              f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps},"
              "format=yuv420p")
        clip = out / f"clip_{i:02d}.mp4"
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(voice),
             "-vf", vf, "-t", f"{dur:.2f}", "-r", str(fps),
             "-af", "apad", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", "-shortest", str(clip)])
        clips.append(clip)

    listfile = out / "clips.txt"
    listfile.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    final = out / "final_video.mp4"
    log("  joining scenes")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
         "-c", "copy", "-movflags", "+faststart", str(final)])
    return final


# ---------------------------------------------------------------- MAIN
def generate(idea: str, scenes: int = 6, fmt: str = "vertical",
             language: str = "Hindi", out_dir: str = "output") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    log("1/4 Writing script...")
    script = write_script(idea, scenes, language)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    log("2/4 Creating images...")
    images = make_images(script, fmt, out)

    log("3/4 Creating voice...")
    voices = make_voices(script, out, language)

    log("4/4 Making video...")
    final = render_video(images, voices, fmt, out)

    meta = {"title": script.get("title"), "description": script.get("description"),
            "hashtags": script.get("hashtags")}
    (out / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"\nDone! Video: {final}")
    return final


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("idea", help="Your video idea (any language)")
    ap.add_argument("--scenes", type=int, default=6)
    ap.add_argument("--format", choices=FORMATS.keys(), default="vertical")
    ap.add_argument("--language", default="Hindi")
    ap.add_argument("--out", default="output")
    a = ap.parse_args()
    generate(a.idea, a.scenes, a.format, a.language, a.out)
