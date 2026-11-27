from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

VIDEO_PRESETS = {
    "Shorts / Reels (9:16)": (1080, 1920),
    "Long video (16:9)": (1920, 1080),
}
