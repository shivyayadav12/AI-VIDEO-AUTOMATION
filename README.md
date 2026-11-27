# AI-VIDEO-AUTOMATION

GitHub Actions-based daily Hindi episodic video generator.

## What is implemented
- Reads one continuing series idea from IDEA.md.
- Remembers the previous episode summary and recurring character description in story_state.json.
- Generates the next connected Hindi episode script and four scene prompts.
- Generates four scene images with OpenAI image generation.
- Generates Hindi-capable narration with OpenAI text-to-speech.
- Renders an MP4 video with FFmpeg/MoviePy.
- Creates title, caption, description, hashtags and tags in output/metadata.json.
- Runs daily at 20:00 India Standard Time (14:30 UTC), and can also be started manually from GitHub Actions.
- Saves generated files as a GitHub Actions artifact for 14 days.

## One-time setup
1. Open repository Settings → Secrets and variables → Actions.
2. Add a repository secret named OPENAI_API_KEY. Never put the key in source code or commit it.
3. Edit IDEA.md with the one-time main story idea.
4. Open Actions → Daily AI Video → Run workflow to test the first episode.
5. After a successful run, open that workflow run and download the artifact named daily-ai-video-...

## Important limitations
- OpenAI API usage is paid and subject to your account's access, usage limits and billing.
- GitHub Actions schedule can start late; exact 20:00 delivery is not guaranteed.
- The current renderer outputs a 16:9 MP4. Vertical 9:16 rendering is not yet implemented in this pipeline.
- Social publishing to YouTube, Instagram and Facebook is not yet connected. It needs official platform OAuth/API credentials and permissions. No social account is automatically posted to at this stage.
- The generated character design is guided by prompts and prior character notes; exact face/outfit consistency is not guaranteed.
- Review AI-generated content before publishing. No system can guarantee virality.

## Existing manual Streamlit app
The app.py interface remains available for manually uploading images, choosing a synthetic Hindi voice, and generating a slideshow.
