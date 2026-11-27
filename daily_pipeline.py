"""Daily idea-to-video pipeline for GitHub Actions.

Uses OpenAI for a Hindi episodic script, generated scene images, and narration.
The finished MP4 and upload metadata are saved as a GitHub Actions artifact.
"""
import base64
import json
import os
import re
from pathlib import Path

from openai import OpenAI
from PIL import Image
from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
SCENES = OUT / "scenes"
IDEA_FILE = ROOT / "IDEA.md"
STATE_FILE = ROOT / "story_state.json"
OUT.mkdir(exist_ok=True)
SCENES.mkdir(parents=True, exist_ok=True)


def read_idea():
    idea = IDEA_FILE.read_text(encoding="utf-8").strip()
    if not idea or idea.startswith("<!--"):
        raise RuntimeError("IDEA.md में अपना वीडियो आइडिया लिखें।")
    return idea


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"part": 0, "story_summary": "यह कहानी आज से शुरू हो रही है।", "characters": ""}


def generate_episode(client, idea, state):
    part = int(state.get("part", 0)) + 1
    prompt = f"""
आप हिंदी में एक family-friendly episodic video writer हैं।
मूल विचार: {idea}
पिछली कहानी का सार: {state.get('story_summary', 'पहला भाग')}
पात्रों की निरंतरता: {state.get('characters', 'नए पात्र बनाएं और उनके कपड़े/रूप तय करें।')}
अब भाग संख्या {part} लिखें। कहानी पिछले भाग से स्वाभाविक रूप से आगे बढ़े।
लगभग 45-60 सेकंड की बोलने योग्य हिंदी narration लिखें।
ठीक 4 दृश्य बनाएं। हर दृश्य का image_prompt अंग्रेज़ी में हो, उसमें पात्रों का चेहरा,
कपड़े और visual style लगातार समान रखने के निर्देश हों। चित्र में कोई लिखावट न हो।
केवल valid JSON दें, इस schema के अनुसार:
{{
 "title":"छोटा हिंदी शीर्षक",
 "script":"पूरी हिंदी narration",
 "caption":"सोशल मीडिया के लिए आकर्षक हिंदी caption",
 "hashtags":["#..."],
 "tags":["..."],
 "characters":"पात्रों का स्थायी रूप और कपड़ों का वर्णन",
 "story_summary":"अब तक की कहानी का छोटा सार, अगले भाग के लिए उपयोगी",
 "scenes":[{{"image_prompt":"..."}}]
}}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.8,
    )
    data = json.loads(response.choices[0].message.content)
    if len(data.get("scenes", [])) != 4 or not data.get("script"):
        raise RuntimeError("AI ने अधूरी स्क्रिप्ट या 4 दृश्यों से अलग परिणाम दिया।")
    data["part"] = part
    return data


def create_images(client, scenes):
    paths = []
    for i, scene in enumerate(scenes, 1):
        result = client.images.generate(
            model="gpt-image-1",
            prompt=scene["image_prompt"] + " Cinematic, polished 3D animated film still, 16:9 composition, no text, consistent character design.",
            size="1536x1024",
        )
        raw = base64.b64decode(result.data[0].b64_json)
        path = SCENES / f"scene_{i}.png"
        path.write_bytes(raw)
        paths.append(path)
    return paths


def make_video(client, data, image_paths):
    audio_path = OUT / "narration.mp3"
    speech = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=data["script"],
        response_format="mp3",
    )
    speech.stream_to_file(str(audio_path))

    audio = AudioFileClip(str(audio_path))
    duration = max(float(audio.duration), 1.0)
    per_scene = duration / len(image_paths)
    clips = []
    for path in image_paths:
        with Image.open(path) as source:
            image = source.convert("RGB")
            target_ratio = 16 / 9
            ratio = image.width / image.height
            if ratio > target_ratio:
                new_width = int(image.height * target_ratio)
                left = (image.width - new_width) // 2
                image = image.crop((left, 0, left + new_width, image.height))
            else:
                new_height = int(image.width / target_ratio)
                top = (image.height - new_height) // 2
                image = image.crop((0, top, image.width, top + new_height))
            image = image.resize((1280, 720))
            frame_path = path.with_name(path.stem + "_frame.jpg")
            image.save(frame_path, quality=92)
        clips.append(ImageClip(str(frame_path)).with_duration(per_scene))

    video = concatenate_videoclips(clips, method="compose").with_audio(audio)
    output = OUT / "daily_video.mp4"
    video.write_videofile(
        str(output), fps=24, codec="libx264", audio_codec="aac",
        preset="medium", logger=None
    )
    video.close()
    audio.close()
    for clip in clips:
        clip.close()
    return output


def main():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GitHub repository Settings > Secrets and variables > Actions में OPENAI_API_KEY secret जोड़ें।")
    client = OpenAI(api_key=key)
    idea = read_idea()
    state = load_state()
    data = generate_episode(client, idea, state)
    images = create_images(client, data["scenes"])
    make_video(client, data, images)

    (OUT / "script.txt").write_text(data["script"], encoding="utf-8")
    metadata = {
        "title": data["title"],
        "caption": data["caption"],
        "description": data["caption"] + "\\n\\n" + " ".join(data.get("hashtags", [])),
        "hashtags": data.get("hashtags", []),
        "tags": data.get("tags", []),
        "part": data["part"],
        "note": "Generated metadata; review before publishing."
    }
    (OUT / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE_FILE.write_text(json.dumps({
        "part": data["part"],
        "story_summary": data["story_summary"],
        "characters": data["characters"]
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Part {data['part']} video generated: output/daily_video.mp4")


if __name__ == "__main__":
    main()
