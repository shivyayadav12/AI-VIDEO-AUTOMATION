"""100% FREE: Idea -> internet research -> script -> real photos + AI images -> Hindi voice -> MP4.

Free services used: DuckDuckGo + Wikipedia (research), Wikimedia Commons (real photos),
Pollinations (free AI text + AI images), Edge-TTS / gTTS (voice), FFmpeg (video).

Usage:
    python pipeline.py "डिजिटल अरेस्ट स्कैम से कैसे बचें"
    python pipeline.py "idea" --scenes 8 --format vertical --language Hindi
"""
import argparse
import asyncio
import html
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
REAL_IMAGES = os.getenv("REAL_IMAGES", "1") != "0"
RESEARCH = os.getenv("RESEARCH", "1") != "0"

FORMATS = {
    "vertical": {"video": (1080, 1920), "image": (720, 1280)},     # Shorts / Reels
    "horizontal": {"video": (1920, 1080), "image": (1280, 720)},   # YouTube
}
UA = {"User-Agent": "Mozilla/5.0 (idea2video; +https://github.com/shivyayadav12/AI-VIDEO-AUTOMATION)"}


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


def http_json(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------- LLM (free)
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


def ask_json(system: str, user: str, check=None) -> dict:
    def go():
        data = extract_json(_chat([{"role": "system", "content": system}, {"role": "user", "content": user}]))
        if check:
            check(data)
        return data

    return retry(go, what="AI reply")


# ---------------------------------------------------------------- 0. RESEARCH
def plan_queries(idea: str) -> list[str]:
    system = ('Reply ONLY with JSON: {"queries": [str, str, str, str]}. Give 4 short English web-search '
              "queries (3-7 words each) that find accurate, current facts about the user's video idea. "
              "Include one for official/government sources and one for recent news.")
    try:
        data = ask_json(system, f"Video idea: {idea}",
                        check=lambda d: d["queries"] and isinstance(d["queries"], list))
        return [str(q) for q in data["queries"]][:4]
    except Exception:  # noqa: BLE001
        return [idea]


def web_search(query: str, n: int = 5) -> list[dict]:
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        res = DDGS().text(query, max_results=n)
        return [{"title": r.get("title", ""), "body": r.get("body", ""), "url": r.get("href", "")} for r in res]
    except Exception as e:  # noqa: BLE001
        log(f"    web search skipped ({str(e)[:80]})")
        return []


def wiki_extract(query: str, lang: str = "en") -> list[dict]:
    q = urllib.parse.quote(query)
    url = (f"https://{lang}.wikipedia.org/w/api.php?action=query&format=json&generator=search"
           f"&gsrsearch={q}&gsrlimit=2&prop=extracts&exintro=1&explaintext=1&exchars=1200&redirects=1")
    try:
        pages = http_json(url).get("query", {}).get("pages", {})
        return [{"title": p["title"], "body": p.get("extract", ""),
                 "url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(p['title'].replace(' ', '_'))}"}
                for p in pages.values() if p.get("extract")]
    except Exception as e:  # noqa: BLE001
        log(f"    wikipedia skipped ({str(e)[:80]})")
        return []


def research(idea: str) -> tuple[str, list[str]]:
    """Returns (notes text for the AI, list of source URLs)."""
    queries = plan_queries(idea)
    log("  searching: " + " | ".join(queries))
    items = []
    for q in queries:
        items += web_search(q)
        time.sleep(1)
    items += wiki_extract(queries[0], "en")
    seen, uniq = set(), []
    for it in items:
        key = it["url"] or it["title"]
        if key and key not in seen and it["body"]:
            seen.add(key)
            uniq.append(it)
    notes = "\n\n".join(f"[{i}] {it['title']} ({it['url']})\n{it['body'][:700]}" for i, it in enumerate(uniq[:12], 1))
    log(f"  found {len(uniq)} sources")
    return notes[:7000], [it["url"] for it in uniq[:8] if it["url"]]


# ---------------------------------------------------------------- 1. SCRIPT
def write_script(idea: str, scenes: int, language: str, notes: str) -> dict:
    system = (
        "You are a short-video scriptwriter for Indian viewers. Reply with ONLY valid JSON, no extra text: "
        '{"title": str, "description": str, "hashtags": [str], "style": str, '
        '"scenes": [{"narration": str, "image_prompt": str, "photo_query": str}]}. '
        f"Write title, description and narration in {language}. Each narration is 1-3 short vivid "
        "sentences (8-15 seconds when spoken). The first scene must hook the viewer. "
        "FACTS: use ONLY facts that appear in the RESEARCH NOTES. Never invent numbers, names, dates, "
        "helpline numbers or laws. If the notes do not support a claim, leave it out. "
        "image_prompt: English, one clear visual, NO text/letters/captions in the image. "
        "photo_query: 2-5 English words to find a REAL photo on Wikimedia Commons of a specific real "
        "place, object, landmark, institution or public thing shown in that scene (e.g. 'Supreme Court of India'). "
        "Use \"\" (empty) for dramatized/emotional scenes, people, or abstract ideas. Give photo_query for about "
        "a third of the scenes at most. 'style' is ONE English sentence describing a consistent art style."
    )
    user = f"Idea: {idea}\nNumber of scenes: {scenes}\n\nRESEARCH NOTES:\n{notes or '(none available - use only very well-known, safe facts)'}"

    def check(data):
        if not data.get("scenes"):
            raise ValueError("no scenes in reply")
        for s in data["scenes"]:
            if not s.get("narration") or not s.get("image_prompt"):
                raise ValueError("scene missing narration/image_prompt")

    return ask_json(system, user, check)


# ---------------------------------------------------------------- 2. IMAGES
def fallback_card(path: Path, size, idx: int):
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


def fit_on_canvas(src: Path, dst: Path, size):
    """Put a real photo on a 9:16 / 16:9 canvas: blurred copy as background, sharp photo on top."""
    from PIL import Image, ImageFilter, ImageOps

    w, h = size
    im = Image.open(src).convert("RGB")
    ratio_img, ratio_canvas = im.width / im.height, w / h
    if abs(ratio_img - ratio_canvas) / ratio_canvas < 0.15:
        ImageOps.fit(im, (w, h), Image.LANCZOS).save(dst, quality=92)
        return
    bg = ImageOps.fit(im, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
    bg = Image.eval(bg, lambda v: int(v * 0.55))
    fg = im.copy()
    fg.thumbnail((w, h), Image.LANCZOS)
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    bg.save(dst, quality=92)


def pick_commons(data: dict, min_w: int = 700):
    """Choose the best usable photo from a Wikimedia Commons API reply."""
    pages = sorted((data.get("query", {}).get("pages", {})).values(), key=lambda p: p.get("index", 99))
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if info.get("width", 0) < min_w:
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        meta = info.get("extmetadata", {})
        artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "Unknown"))
        lic = meta.get("LicenseShortName", {}).get("value", "")
        credit = f"{html.unescape(p.get('title', ''))} - {html.unescape(artist).strip()} ({lic}) {info.get('descriptionurl', '')}"
        return url, credit
    return None


def commons_photo(query: str, dst: Path):
    q = urllib.parse.quote(query + " filetype:bitmap")
    url = (f"https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6"
           f"&gsrsearch={q}&gsrlimit=8&prop=imageinfo&iiprop=url|size|mime|extmetadata&iiurlwidth=1280")
    found = pick_commons(http_json(url))
    if not found:
        return None
    img_url, credit = found
    req = urllib.request.Request(img_url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if len(data) < 5000:
        return None
    dst.write_bytes(data)
    return credit


def ai_image(prompt: str, size, dst: Path):
    w, h = size
    q = urllib.parse.quote(prompt[:900])
    seed = random.randint(1, 99999)
    if POLL_KEY:
        url = f"https://gen.pollinations.ai/image/{q}?width={w}&height={h}&seed={seed}&nologo=true&key={POLL_KEY}"
    else:
        url = f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&seed={seed}&nologo=true&model=flux"

    def fetch():
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
        if len(data) < 5000:
            raise ValueError("image too small / not an image")
        dst.write_bytes(data)

    retry(fetch, tries=3, wait=8, what="AI image")


def make_images(script: dict, fmt: str, out: Path):
    size = FORMATS[fmt]["image"]
    style = script.get("style", "")
    paths, credits = [], []
    n = len(script["scenes"])
    for i, scene in enumerate(script["scenes"], 1):
        log(f"  image {i}/{n}")
        final = out / f"scene_{i:02d}.jpg"
        done = False

        pq = (scene.get("photo_query") or "").strip()
        if REAL_IMAGES and pq:
            try:
                raw = out / f"raw_{i:02d}.img"
                credit = commons_photo(pq, raw)
                if credit:
                    fit_on_canvas(raw, final, size)
                    credits.append(credit)
                    log(f"    real photo: {pq}")
                    done = True
            except Exception as e:  # noqa: BLE001
                log(f"    real photo failed ({str(e)[:80]}), using AI image")

        if not done:
            prompt = f"{scene['image_prompt']}. {style}. cinematic, detailed, no text, no letters, no watermark"
            try:
                ai_image(prompt, size, final)
            except Exception as e:  # noqa: BLE001
                log(f"    using colour card for scene {i} ({str(e)[:80]})")
                final = out / f"scene_{i:02d}.png"
                fallback_card(final, size, i)
            time.sleep(3)
        paths.append(final)
    return paths, credits


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

    notes, sources = "", []
    if RESEARCH:
        log("1/5 Researching the internet...")
        try:
            notes, sources = research(idea)
        except Exception as e:  # noqa: BLE001
            log(f"  research failed, continuing without it ({str(e)[:100]})")
        (out / "research_notes.txt").write_text(notes, encoding="utf-8")

    log("2/5 Writing script...")
    script = write_script(idea, scenes, language, notes)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    log("3/5 Getting images (real photos + AI)...")
    images, credits = make_images(script, fmt, out)

    log("4/5 Creating voice...")
    voices = make_voices(script, out, language)

    log("5/5 Making video...")
    final = render_video(images, voices, fmt, out)

    meta = {"title": script.get("title"), "description": script.get("description"),
            "hashtags": script.get("hashtags"), "sources": sources, "image_credits": credits}
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
