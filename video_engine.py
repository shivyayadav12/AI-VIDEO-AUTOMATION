from pathlib import Path
from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

def build_slideshow(image_paths, voice_path, output_path, size=(1080, 1920), music_path=None):
    """
    Build a simple image-based video with the user's own recorded narration.
    This starter engine does not clone voices or generate images.
    """
    if not image_paths:
        raise ValueError("कम से कम एक तस्वीर अपलोड करें।")
    if not voice_path:
        raise ValueError("अपनी आवाज़ की रिकॉर्डिंग अपलोड करें।")

    voice = AudioFileClip(str(voice_path))
    duration = max(voice.duration, 1)
    per_image = duration / len(image_paths)
    clips = []

    for image_path in image_paths:
        clip = (
            ImageClip(str(image_path))
            .with_duration(per_image)
            .resized(height=size[1])
            .with_position("center")
        )
        # Fit/crop each still image to the selected aspect ratio.
        clip = clip.cropped(
            x_center=clip.w / 2,
            y_center=clip.h / 2,
            width=min(clip.w, size[0]),
            height=min(clip.h, size[1]),
        )
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    if video.duration > duration:
        video = video.subclipped(0, duration)

    video = video.with_audio(voice)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(output_path),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
    )

    video.close()
    voice.close()
    for clip in clips:
        clip.close()
    return str(output_path)
