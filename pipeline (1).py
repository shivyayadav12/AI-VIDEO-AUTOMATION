"""100% FREE explainer-Reel maker.

Idea -> internet research -> script -> cartoon scenes + info cards + HUD counters + captions
-> Hindi voice -> final 9:16 MP4.

Free services: DuckDuckGo + Wikipedia (research), Pollinations (free AI text + images),
Edge-TTS / gTTS (voice), Pillow (cards, captions), FFmpeg (video).

Usage:
    python pipeline.py "Agar 10 crore cash mil jaye to kya hoga"
    python pipeline.py "idea" --scenes 12 --format vertical --language Hindi
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
RESEARCH = os.getenv("RESEARCH", "1") != "0"
MIN_SCENES = int(os.getenv("MIN_SCENES", "10"))
CHARACTER = os.getenv(
    "CHARACTER",
    "the same cartoon hero in every scene: simple round white face with dot eyes, black beanie, "
    "red jacket, black trousers, white sneakers",
)
ART_STYLE = os.getenv(
    "ART_STYLE",
    "dark moody 2D cartoon illustration, thick black outlines, flat colours, dramatic cinematic "
    "lighting, vertical 9:16, no text, no letters, no watermark",
)

FORMATS = {
    "vertical": {"video": (720, 1280), "image": (720, 1280)},      # Shorts / Reels
    "horizontal": {"video": (1280, 720), "image": (1280, 720)},    # YouTube
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


# ---------------------------------------------------------------- free LLM
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
    with urllib.request.urlopen(req, timeout=150) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]


def ask_json(system: str, user: str, check=None) -> dict:
    def go():
        data = extract_json(_chat([{"role": "system", "content": system}, {"role": "user", "content": user}]))
        if check:
            check(data)
        return data

    return retry(go, what="AI reply")


# ---------------------------------------------------------------- 1. RESEARCH
def plan_queries(idea: str) -> list[str]:
    system = ('Reply ONLY with JSON: {"queries": [str, str, str, str]}. Give 4 short English web-search '
              "queries (3-7 words each) that find accurate, current facts about the user's video idea. "
              "Include one for official/government sources (laws, rules, limits, helplines) and one for recent news.")
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


def research(idea: str):
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


# ---------------------------------------------------------------- 2. SCRIPT
EXAMPLE = """{
 "title": "10 Crore cash mil gaye to?",
 "description": "...",
 "hashtags": ["#money", "#facts"],
 "hud_labels": ["CASH", "BANKED", "RISK"],
 "scenes": [
  {"type": "illustration", "voice": "मान लो तुम्हें अभी-अभी दस करोड़ रुपये कैश मिल गए!",
   "caption": "Maan lo tumhe abhi-abhi 10 Crore cash mil gaye!",
   "image_prompt": "hero standing on a huge pile of cash bundles under a single spotlight in a dark room, shocked face",
   "hud": ["Rs 10,00,00,000", "Rs 0", "0%"]},
  {"type": "card", "voice": "...", "caption": "...",
   "card": {"theme": "light", "title": "CASH WEIGHT BREAKDOWN", "big": "2,00,000 NOTES",
            "rows": [], "footer": "= 220 KG", "tone": "amber"},
   "hud": ["Rs 10,00,00,000", "Rs 0", "0%"]},
  {"type": "card", "voice": "...", "caption": "...",
   "card": {"theme": "dark", "title": "THE SMURFING PLAN", "big": "",
            "rows": ["BANK 1 | Rs 4,00,000", "BANK 2 | Rs 4,00,000"], "footer": "TOTAL: Rs 8,00,000", "tone": "red"},
   "hud": ["Rs 10,00,00,000", "Rs 8 Lakh", "35%"]}
 ]
}"""


def write_script(idea: str, scenes: int, language: str, notes: str) -> dict:
    hindi = language.lower().startswith("hi")
    voice_rule = ("'voice' = narration in Hindi written in DEVANAGARI script (for the text-to-speech). "
                  "'caption' = the same sentence in Hinglish (Hindi written in English letters), short and punchy."
                  if hindi else
                  f"'voice' and 'caption' = the same sentence in {language}.")
    system = (
        "You write viral 'what-if / explainer' Reels in the style of a dark cartoon story with info cards. "
        "Reply with ONLY valid JSON (no extra text) shaped exactly like this example:\n" + EXAMPLE + "\n\n"
        f"RULES: exactly {scenes} scenes. About 55% type 'illustration' (cartoon hero scene) and 45% type 'card' "
        "(info card with a title, optional 'big' number, optional 'rows' as 'LEFT | RIGHT' strings, and a 'footer'). "
        "Scene 1 = illustration with a strong hook. Last scene = a cliffhanger plus 'comment for Part 2'. "
        + voice_rule + " Each voice line is 1-2 short sentences (5-12 seconds). Build tension: situation -> "
        "problem -> twist -> what really happens -> what to do. "
        "FACTS: use ONLY facts, numbers, rules and names found in the RESEARCH NOTES. Never invent numbers, laws, "
        "limits or helplines; if unsure, leave it out. Cards must show real facts from the notes. "
        "'hud' = 3 short values for the 3 hud_labels that change as the story moves (money, risk %, etc.); "
        "if the idea has no changing numbers use \"hud_labels\": [] and omit hud. "
        "image_prompt: English, one clear visual featuring the hero; NEVER ask for text, letters or numbers in it. "
        "Keep card text short (title max 4 words, rows max 5 rows)."
    )
    user = (f"Idea: {idea}\n\nRESEARCH NOTES:\n"
            f"{notes or '(none available - use only very well-known, safe facts)'}")

    def check(data):
        sc = data.get("scenes")
        if not sc or len(sc) < 3:
            raise ValueError("too few scenes")
        for s in sc:
            if not s.get("voice") or not s.get("caption"):
                raise ValueError("scene missing voice/caption")
            if s.get("type") == "card":
                if not isinstance(s.get("card"), dict):
                    raise ValueError("card scene without card")
            elif not s.get("image_prompt"):
                raise ValueError("illustration without image_prompt")
            else:
                s["type"] = "illustration"

    return ask_json(system, user, check)


# ---------------------------------------------------------------- 3. CARDS / HUD / CAPTIONS (Pillow)
FONT_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"]
FONT_REG = [p.replace("-Bold", "").replace(" Bold", "").replace("arialbd", "arial") for p in FONT_BOLD]
_font_cache = {}
HAS_TTF = {"v": None}

THEMES = {
    "dark": {"bg": (23, 24, 28), "box": (36, 37, 44), "line": (78, 78, 90), "text": (245, 245, 245),
             "pill": (62, 62, 72), "pill_text": (210, 210, 220)},
    "light": {"bg": (232, 226, 212), "box": (250, 248, 242), "line": (200, 190, 165), "text": (35, 35, 35),
              "pill": (214, 203, 176), "pill_text": (70, 62, 45)},
}
TONES = {"red": (231, 76, 60), "green": (46, 204, 113), "amber": (241, 196, 15), "white": (245, 245, 245)}


def font(size: int, bold: bool = True):
    from PIL import ImageFont

    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    f = None
    for path in (FONT_BOLD if bold else FONT_REG):
        try:
            f = ImageFont.truetype(path, size)
            HAS_TTF["v"] = True
            break
        except Exception:  # noqa: BLE001
            continue
    if f is None:
        try:
            f = ImageFont.load_default(size=size)
        except TypeError:
            f = ImageFont.load_default()
        HAS_TTF["v"] = False
    _font_cache[key] = f
    return f


def clean(text: str) -> str:
    text = str(text or "")
    if HAS_TTF["v"] is False:               # built-in font may lack the rupee sign
        text = text.replace("₹", "Rs ")
    return text.strip()


def text_w(draw, text, f):
    return draw.textlength(text, font=f)


def fit_font(draw, text, max_w, start, min_size=16, bold=True):
    size = start
    while size > min_size:
        f = font(size, bold)
        if text_w(draw, text, f) <= max_w:
            return f
        size -= 2
    return font(min_size, bold)


def wrap(draw, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_w(draw, t, f) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_card(card: dict, size, path: Path):
    from PIL import Image, ImageDraw

    w, h = size
    th = THEMES.get(card.get("theme"), THEMES["dark"])
    tone = TONES.get(card.get("tone"), TONES["amber"])
    img = Image.new("RGB", size, th["bg"])
    d = ImageDraw.Draw(img)
    bw = int(w * 0.80)
    x0 = (w - bw) // 2

    # build list of blocks first so we can centre the whole stack vertically
    title = clean(card.get("title", "")).upper()
    big = clean(card.get("big", ""))
    rows = [clean(r) for r in (card.get("rows") or [])][:6]
    footer = clean(card.get("footer", ""))
    blocks = []
    if title:
        blocks.append(("title", title, 62))
    if big:
        blocks.append(("big", big, 150))
    for r in rows:
        blocks.append(("row", r, 74))
    if footer:
        blocks.append(("footer", footer, 108))
    gap = 26
    total = sum(b[2] for b in blocks) + gap * (len(blocks) - 1)
    region_top, region_bottom = int(h * 0.10), int(h * 0.80)
    y = region_top + max(0, (region_bottom - region_top - total) // 2)

    for kind, text, bh in blocks:
        if kind == "title":
            f = fit_font(d, text, bw - 60, 30, 18)
            tw = text_w(d, text, f)
            pw = int(tw + 60)
            d.rounded_rectangle([(w - pw) // 2, y, (w + pw) // 2, y + bh], 16, fill=th["pill"])
            d.text((w // 2, y + bh // 2), text, font=f, fill=th["pill_text"], anchor="mm")
        elif kind == "big":
            d.rounded_rectangle([x0, y, x0 + bw, y + bh], 20, fill=th["box"], outline=th["line"], width=3)
            f = fit_font(d, text, bw - 50, 64, 24)
            d.text((w // 2, y + bh // 2), text, font=f, fill=th["text"], anchor="mm")
        elif kind == "row":
            d.rounded_rectangle([x0, y, x0 + bw, y + bh], 14, fill=th["box"], outline=th["line"], width=2)
            left, _, right = text.partition("|")
            f = fit_font(d, left.strip(), bw * 0.5, 28, 16)
            d.text((x0 + 24, y + bh // 2), left.strip(), font=f, fill=th["text"], anchor="lm")
            if right.strip():
                f2 = fit_font(d, right.strip(), bw * 0.42, 30, 16)
                d.text((x0 + bw - 24, y + bh // 2), right.strip(), font=f2, fill=tone, anchor="rm")
        elif kind == "footer":
            d.rounded_rectangle([x0, y, x0 + bw, y + bh], 20, fill=(20, 20, 24), outline=tone, width=4)
            f = fit_font(d, text, bw - 50, 46, 20)
            d.text((w // 2, y + bh // 2), text, font=f, fill=tone, anchor="mm")
        y += bh + gap
    img.save(path, quality=95)


def overlay_png(size, hud_labels, hud_vals, caption: str, path: Path):
    """Transparent layer: HUD chips on top + caption near the bottom."""
    from PIL import Image, ImageDraw

    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if hud_labels and hud_vals:
        lab_f, val_f = font(max(12, w // 52), True), font(max(18, w // 30), True)
        colors = [(245, 245, 245), (46, 204, 113), (231, 76, 60)]
        x, y = 14, 14
        chips = []
        for k, lab in enumerate(hud_labels[:3]):
            val = clean(hud_vals[k]) if k < len(hud_vals) else ""
            lab = clean(lab).upper()
            cw = int(max(text_w(d, lab, lab_f), text_w(d, val, val_f)) + 26)
            chips.append((lab, val, cw, colors[k % 3]))
        scale = min(1.0, (w - 28 - 8 * (len(chips) - 1)) / max(1, sum(c[2] for c in chips)))
        for lab, val, cw, col in chips:
            cw = int(cw * scale)
            d.rounded_rectangle([x, y, x + cw, y + int(w * 0.085)], 10, fill=(16, 16, 20, 225), outline=(70, 70, 80, 255))
            d.text((x + 12, y + 8), lab, font=lab_f, fill=(150, 150, 160, 255))
            d.text((x + 12, y + int(w * 0.036)), val, font=fit_font(d, val, cw - 20, max(18, w // 30), 11), fill=col + (255,))
            x += cw + 8

    cap = clean(caption)
    if cap:
        f = font(max(26, int(w * 0.047)), True)
        lines = wrap(d, cap, f, int(w * 0.88))[:3]
        lh = int(f.size * 1.3) if hasattr(f, "size") else 40
        bottom = int(h * 0.86)
        y = bottom - lh * len(lines)
        for ln in lines:
            d.text((w // 2, y), ln, font=f, fill=(255, 255, 255, 255), anchor="ma",
                   stroke_width=max(3, w // 180), stroke_fill=(0, 0, 0, 255))
            y += lh
    img.save(path)


def caption_chunks(caption: str, max_words: int = 6) -> list[str]:
    words = caption.split()
    if len(words) <= max_words:
        return [caption]
    n = -(-len(words) // max_words)
    size = -(-len(words) // n)
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


# ---------------------------------------------------------------- 4. ILLUSTRATIONS (free AI)
def fallback_card(path: Path, size, idx: int):
    from PIL import Image, ImageDraw

    w, h = size
    random.seed(idx * 7)
    c1, c2 = (14, 15, 20), (random.randint(40, 90), random.randint(30, 60), random.randint(60, 110))
    img = Image.new("RGB", size)
    px = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(c1[k] * (1 - t) + c2[k] * t) for k in range(3)))
    img.save(path)


def ai_image(prompt: str, size, dst: Path):
    w, h = size
    q = urllib.parse.quote(prompt[:900])
    attempt = {"n": 0}

    def fetch():
        attempt["n"] += 1
        seed = random.randint(1, 99999)
        model = "flux" if attempt["n"] % 2 else "turbo"
        if POLL_KEY:
            url = f"https://gen.pollinations.ai/image/{q}?width={w}&height={h}&seed={seed}&nologo=true&key={POLL_KEY}"
        else:
            url = f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&seed={seed}&nologo=true&model={model}"
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
        if len(data) < 5000:
            raise ValueError("image too small / not an image")
        dst.write_bytes(data)

    retry(fetch, tries=4, wait=10, what="AI image")


def make_visuals(script: dict, fmt: str, out: Path):
    """Returns list of (image_path, kind). Cards are drawn by us (always work); cartoons come from free AI."""
    size = FORMATS[fmt]["image"]
    scenes = script["scenes"]
    res = [None] * len(scenes)
    for i, sc in enumerate(scenes, 1):
        log(f"  visual {i}/{len(scenes)} ({sc['type']})")
        if sc["type"] == "card":
            p = out / f"scene_{i:02d}.png"
            render_card(sc["card"], size, p)
            res[i - 1] = (p, "card")
            continue
        p = out / f"scene_{i:02d}.jpg"
        prompt = f"{sc['image_prompt']}. {CHARACTER}. {ART_STYLE}"
        try:
            ai_image(prompt, size, p)
            res[i - 1] = (p, "image")
        except Exception as e:  # noqa: BLE001
            log(f"    AI image failed ({str(e)[:80]})")
        time.sleep(8)  # free AI service is rate-limited: go slowly

    good = [(k, r) for k, r in enumerate(res) if r and r[1] == "image"]
    for i, r in enumerate(res):                       # never leave a blank screen
        if r is None:
            if good:
                k, near = min(good, key=lambda kr: abs(kr[0] - i))
                res[i] = near
                log(f"    scene {i + 1}: reusing the image of scene {k + 1}")
            else:
                p = out / f"scene_{i + 1:02d}.png"
                fallback_card(p, size, i + 1)
                res[i] = (p, "image")
    return res


# ---------------------------------------------------------------- 5. VOICE
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
        text = scene["voice"]
        try:
            retry(lambda: asyncio.run(_edge(text, p)), tries=3, wait=4, what="edge-tts")
            if not p.exists() or p.stat().st_size < 1000:
                raise ValueError("empty audio")
        except Exception:  # noqa: BLE001
            log("    edge-tts unavailable, using gTTS")
            retry(lambda: _gtts(text, p, language), tries=3, wait=4, what="gTTS")
        paths.append(p)
    return paths


# ---------------------------------------------------------------- 6. VIDEO
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{r.stderr[-1800:]}")
    return r.stdout


def duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def render_scene(i, base: Path, kind: str, voice: Path, overlays, fmt: str, out: Path) -> Path:
    w, h = FORMATS[fmt]["video"]
    fps = 25
    dur = duration(voice) + 0.4
    frames = int(dur * fps)
    cmd = ["ffmpeg", "-y"]
    if kind == "card":
        cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.2f}", "-i", str(base)]
        bg = f"[0:v]scale={w}:{h},setsar=1,format=yuv420p[bg]"
    else:
        cmd += ["-i", str(base)]  # one frame in; zoompan makes all the frames (smooth Ken Burns)
        z = "min(zoom+0.0007,1.22)" if i % 2 else "if(eq(on,0),1.22,max(zoom-0.0007,1.0))"
        bg = (f"[0:v]scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
              f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps},"
              "setsar=1,format=yuv420p[bg]")
    cmd += ["-i", str(voice)]
    for ov, _, _ in overlays:
        cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.2f}", "-i", str(ov)]
    chain, prev = bg, "bg"
    for k, (_, s, e) in enumerate(overlays):
        chain += f";[{prev}][{2 + k}:v]overlay=0:0:enable='between(t,{s:.2f},{e:.2f})'[o{k}]"
        prev = f"o{k}"
    chain += f";[{prev}]format=yuv420p[v]"
    clip = out / f"clip_{i:02d}.mp4"
    cmd += ["-filter_complex", chain, "-map", "[v]", "-map", "1:a", "-af", "apad", "-t", f"{dur:.2f}",
            "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", str(clip)]
    run(cmd)
    return clip


def render_video(script: dict, visuals, voices, fmt: str, out: Path) -> Path:
    size = FORMATS[fmt]["video"]
    labels = script.get("hud_labels") or []
    clips = []
    for i, (sc, (img, kind), voice) in enumerate(zip(script["scenes"], visuals, voices), 1):
        log(f"  render scene {i}/{len(voices)}")
        dur = duration(voice) + 0.4
        chunks = caption_chunks(str(sc["caption"]))
        weights = [max(1, len(c.split())) for c in chunks]
        total, t, overlays = sum(weights), 0.0, []
        for k, (c, wgt) in enumerate(zip(chunks, weights)):
            span = dur * wgt / total
            ov = out / f"ov_{i:02d}_{k}.png"
            overlay_png(size, labels, sc.get("hud") or [], c, ov)
            overlays.append((ov, t, t + span + (0.05 if k < len(chunks) - 1 else 0.5)))
            t += span
        clips.append(render_scene(i, img, kind, voice, overlays, fmt, out))

    listfile = out / "clips.txt"
    listfile.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    final = out / "final_video.mp4"
    log("  joining scenes")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
         "-c", "copy", "-movflags", "+faststart", str(final)])
    return final


# ---------------------------------------------------------------- MAIN
def generate(idea: str, scenes: int = 12, fmt: str = "vertical",
             language: str = "Hindi", out_dir: str = "output") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scenes = max(scenes, MIN_SCENES)

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

    log("3/5 Making cartoon scenes and info cards...")
    visuals = make_visuals(script, fmt, out)

    log("4/5 Creating voice...")
    voices = make_voices(script, out, language)

    log("5/5 Making video (HUD + captions)...")
    final = render_video(script, visuals, voices, fmt, out)

    meta = {"title": script.get("title"), "description": script.get("description"),
            "hashtags": script.get("hashtags"), "sources": sources}
    (out / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"\nDone! Video: {final}")
    return final


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("idea", help="Your video idea (any language)")
    ap.add_argument("--scenes", type=int, default=12)
    ap.add_argument("--format", choices=FORMATS.keys(), default="vertical")
    ap.add_argument("--language", default="Hindi")
    ap.add_argument("--out", default="output")
    a = ap.parse_args()
    generate(a.idea, a.scenes, a.format, a.language, a.out)
