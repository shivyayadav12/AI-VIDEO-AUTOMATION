# AI-VIDEO-AUTOMATION

A starter app for creating vertical Shorts/Reels (9:16) and horizontal videos (16:9).

## Current features
- Enter a video idea and write a narration script.
- If OPENAI_API_KEY is configured, generate a Hindi script from the idea using OpenAI.
- Generate Hindi synthetic narration using a selectable female or male AI voice.
- Upload scene images and assemble an MP4 slideshow with the AI narration.
- Preview and download the video.

## Voice and privacy
- The app currently uses standard synthetic Hindi voices; it does not clone or imitate the user's voice.
- Text-to-speech uses the Edge TTS online service and requires internet access. Availability and service terms can change.
- Do not enter private, sensitive, or confidential text into a third-party speech service.
- Use only content and images you own or have permission to use.

## Setup
1. Install Python 3.10 or newer.
2. Create and activate a virtual environment.
3. Install dependencies: pip install -r requirements.txt
4. Copy .env.example to .env on your own computer/server.
5. Add an OpenAI API key to .env if you want automatic script generation. Keep it secret; never commit .env.
6. Run: streamlit run app.py

Without an OpenAI API key, you can still type the script yourself and generate the Hindi AI narration.

## Not implemented yet
- Automatic AI image/video generation (scene images must currently be uploaded).
- Automatic background music and sound effects.
- YouTube, Instagram, and Facebook publishing. These require official APIs, account permissions, and user confirmation before posting.

This is an evolving starter project, not yet a fully automatic one-click video pipeline.
