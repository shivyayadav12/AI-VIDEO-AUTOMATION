"""Hindi text-to-speech using an online Edge TTS endpoint.
Creates a standard synthetic voice; it does not clone a real person.
"""
import asyncio
from pathlib import Path
import edge_tts

SUPPORTED_VOICES = {
    "हिंदी - महिला आवाज़": "hi-IN-SwaraNeural",
    "हिंदी - पुरुष आवाज़": "hi-IN-MadhurNeural",
}

async def _save_speech(text: str, voice: str, output_path: str):
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)

def generate_speech(text: str, output_path: str, voice: str = "hi-IN-SwaraNeural") -> str:
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("आवाज़ बनाने के लिए स्क्रिप्ट लिखें।")
    if voice not in SUPPORTED_VOICES.values():
        raise ValueError("चुनी गई हिंदी आवाज़ उपलब्ध नहीं है।")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_save_speech(clean_text, voice, str(target)))
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("AI आवाज़ की ऑडियो फ़ाइल नहीं बन पाई।")
    return str(target)
