"""Daily Hindi episodic video pipeline for GitHub Actions.

Reads IDEA.md once, continues from story_state.json, generates scene images,
Hindi AI narration, a vertical/landscape MP4, and upload-ready metadata.
"""
import asyncio
import base64
import json
import os
from pathlib import Path

import edge_tts
from openai import OpenAI
from PIL import Image, ImageOps
from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
SCENES = OUT / "scenes"
IDEA_FILE = ROOT / "IDEA.md"
STATE_FILE = ROOT / "story_state.json"
SERIES_FILE = ROOT / "series.json"
OUT.mkdir(exist_ok=True)
SCENES.mkdir(parents=True, exist_ok=True)


def load_settings():
    defaults = {
        "language": "Hindi",
        "duration_seconds": 30,
        "aspect_ratio": "9:16",
        "scenes": 4,
        "voice": "hi-IN-MadhurNeural",
        "series_title": "Meri AI Kahani",
    }
    if SERIES_FILE.exists():
        saved = json.loads(SERIES_FILE.read_text(encoding="utf-8"))
        defaults.update({k: v for k, v in saved.items() if k in defaults and v})
    defaults["scenes"] = max(2, min(int(defaults["scenes"]), 6))
    defaults["duration_seconds"] = max(15, min(int(defaults["duration_seconds"]), 90))
    if defaults["aspect_ratio"] not in ("9:16", "16:9"):
        defaults["aspect_ratio"] = "9:16"
    return defaults


def read_idea():
    idea = IDEA_FILE.read_text(encoding="utf-8").strip()
    if not idea or idea.startswith("<!--"):
        raise RuntimeError("IDEA.md में अपना मुख्य वीडियो आइडिया लिखें।")
    return idea


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {
        "part": 0,
        "story_summary": "यह कहानी आज से शुरू हो रही है।",
        "characters": "पहले भाग में पात्रों का रूप, कपड़े और स्वभाव तय करें।",
    }


def generate_episode(client, idea, state, settings):
    part = int(state.get("part", 0)) + 1
    count = settings["scenes"]
    seconds = settings["duration_seconds"]
    prompt = f"""
आप एक अनुभवी हिंदी family-friendly animated series writer हैं।
सीरीज़ का नाम: {settings['series_title']}
मुख्य विचार: {idea}
पिछले भाग का सार: {state.get('story_summary', 'पहला भाग')}
पात्रों की स्थायी पहचान: {state.get('characters', 'पहले भाग में तय करें')}
अब भाग संख्या {part} लिखें। कहानी पिछले भाग से सीधे और स्वाभाविक रूप से आगे बढ़े।
वीडियो लगभग {seconds} सेकंड का हो। बोलने योग्य सरल, रोचक हिंदी narration लिखें।
शुरुआत में दर्शक का ध्यान खींचें और अंत में अगले भाग के लिए छोटा उत्सुकता वाला मोड़ रखें।
ठीक {count} दृश्य बनाएं। हर image_prompt अंग्रेज़ी में हो। हर दृश्य में पात्रों के चेहरे,
बाल, कपड़े, रंग और animation style बिल्कुल एक जैसे रखने का निर्देश शामिल करें।
किसी भी चित्र में टेक्स्ट, लोगो, watermark या subtitles न हों।
केवल valid JSON दें:
{{
 "title":"छोटा हिंदी शीर्षक",
 "script":"हिंदी narration",
 "caption":"छोटा आकर्षक हिंदी caption",
 "hashtags":["#HindiCartoon","#Animation"],
 "tags":["Hindi cartoon","animated story"],
 "characters":"सभी मुख्य पात्रों का स्थायी रूप, कपड़े और स्वभाव",
 "story_summary":"अब तक की कहानी का सार, अगले भाग के लिए उपयोगी",
 "scenes":[{{"image_prompt":"Detailed English visual prompt"}}]
}}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.8,
    )
    data = json.loads(response.choices[0].message.content)
    if len(data.get("scenes", [])) != count or not data.get("script"):
        raise RuntimeError(f"AI से {count} दृश्य और पूरी स्क्रिप्ट नहीं मिली।")
    data["part"] = part
    return data


def create_images(client, scenes, aspect_ratio):
    paths = []
    image_size = "1024x1536" if aspect_ratio == "9:16" else "1536x1024"
    frame = "vertical 9:16 portrait composition" if aspect_ratio == "9:16" else "horizontal 16:9 landscape composition"
    for index, scene in enumerate(scenes, 1):
        result = client.images.generate(
            model="gpt-image-1",
            prompt=(
                scene["image_prompt"]
                + f" Polished cinematic 3D animated family film still, {frame}. "
                + "Keep character appearance identical to all other scenes. No text, no logo, no watermark."
            ),
            size=image_size,
        )
        raw = base64.b64decode(result.data[0].b64_json)
        path = SCENES / f"scene_{index}.png"
        path.write_bytes(raw)
        paths.append(path)
    return paths


async def create_voice(text, output_path, voice):
    communicator = edge_tts.Communicate(text=text, voice=voice)
    await communicator.save(str(output_path))


def make_video(data, image_paths, settings):
    audio_path = OUT / "narration.mp3"
    asyncio.run(create_voice(data["script"], audio_path, settings["voice"]))

    audio = AudioFileClip(str(audio_path))
    if settings["aspect_ratio"] == "9:16":
        width, height = 1080, 1920
        target_ratio = 9 / 16
    else:
        width, height = 1280, 720
        target_ratio = 16 / 9

    duration = max(float(audio.duration), 1.0)
    per_scene = duration / len(image_paths)
    clips = []
    for path in image_paths:
        with Image.open(path) as source:
            image = ImageOps.fit(
                source.convert("RGB"),
                (width, height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            frame_path = path.with_name(path.stem + "_frame.jpg")
            image.save(frame_path, quality=92)
        clips.append(ImageClip(str(frame_path)).with_duration(per_scene))

    video = concatenate_videoclips(clips, method="compose").with_audio(audio)
    output = OUT / "daily_video.mp4"
    video.write_videofile(
        str(output),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        logger=None,
    )
    video.close()
    audio.close()
    for clip in clips:
        clip.close()
    return output


def main():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GitHub repository Settings > Secrets and variables > Actions में "
            "OPENAI_API_KEY secret जोड़ें। API key को कभी code में न लिखें।"
        )

    settings = load_settings()
    idea = read_idea()
    state = load_state()
    client = OpenAI(api_key=key)

    data = generate_episode(client, idea, state, settings)
    images = create_images(client, data["scenes"], settings["aspect_ratio"])
    video_path = make_video(data, images, settings)

    (OUT / "script.txt").write_text(data["script"], encoding="utf-8")
    hashtags = data.get("hashtags", [])
    description = (
        f"{data.get('caption', data['title'])}\n\n"
        + " ".join(hashtags)
        + f"\n\n{settings['series_title']} | भाग {data['part']}"
    )
    metadata = {
        "title": f"{data['title']} | भाग {data['part']}",
        "caption": data.get("caption", data["title"]),
        "description": description,
        "hashtags": hashtags,
        "tags": data.get("tags", []),
        "part": data["part"],
        "aspect_ratio": settings["aspect_ratio"],
        "video_file": str(video_path.relative_to(ROOT)),
        "note": "AI-generated metadata. Review before publishing; automatic social upload is not configured.",
    }
    (OUT / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Save continuity only after all media and metadata were generated successfully.
    STATE_FILE.write_text(
        json.dumps(
            {
                "part": data["part"],
                "story_summary": data["story_summary"],
                "characters": data["characters"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Part {data['part']} generated: {video_path}")


if __name__ == "__main__":
    main()
