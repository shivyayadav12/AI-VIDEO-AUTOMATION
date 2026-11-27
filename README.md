# AI-VIDEO-AUTOMATION

A starter project for creating both vertical Shorts/Reels (9:16) and horizontal long videos (16:9).

## Current MVP
- Enter a video idea and narration script.
- Upload your own recorded narration.
- Upload scene images.
- Assemble an MP4 slideshow with the narration.
- Download the finished MP4.

## Important voice note
This starter version uses an audio recording that you provide for each video. It does **not** clone a voice or create speech from a voice sample. Keep voice recordings private and only use your own voice or recordings you have permission to use. Any future voice-generation provider must be checked for age eligibility, consent, privacy, and applicable terms before use.

## Setup
1. Install Python 3.10 or newer.
2. Create and activate a virtual environment.
3. Install dependencies:
   `pip install -r requirements.txt`
4. Run:
   `streamlit run app.py`

## Secrets
- Copy `.env.example` to `.env` only on your own computer/server.
- Add API keys locally when a provider integration is implemented.
- Never commit `.env`, API keys, passwords, or access tokens.

## Planned integrations
- AI script generation
- AI image/video generation
- Optional music and sound effects from properly licensed sources
- YouTube and Meta publishing using official APIs and user-authorized OAuth

Social publishing is not enabled in this starter version. Each platform has separate account, permission, review, and quota requirements. The app should show a preview and ask for confirmation before publishing.

## Project status
Starter MVP scaffold. It is not yet a one-click fully automated AI video pipeline.
