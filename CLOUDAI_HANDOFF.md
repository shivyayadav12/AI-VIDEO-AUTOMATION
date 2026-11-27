# GitHub Daily AI Video Setup

## What this repository automation does
- Reads the long-term series idea from `IDEA.md`.
- Creates the next Hindi episode using OpenAI text generation.
- Generates four scene images and Hindi narration.
- Renders an MP4 and creates title/caption/hashtags/tags metadata.
- Saves story continuity in `story_state.json`.
- Runs on GitHub Actions daily at 8:00 PM India time (14:30 UTC), and can also be started manually.
- Makes the MP4 and metadata available as a workflow artifact for 14 days.

## One-time setup required
1. Put your series idea in `IDEA.md` and commit it.
2. In GitHub open Settings -> Secrets and variables -> Actions -> New repository secret.
3. Create a secret named `OPENAI_API_KEY` with your own OpenAI API key. Never put a key in a code file or public issue.
4. Open Actions -> Daily AI Video -> Run workflow to test once.

## Important limitations
- GitHub Actions is the scheduler and runner; it is not itself an image/voice AI provider. This pipeline uses OpenAI API services, so API billing and model availability apply.
- The generated video is 16:9 MP4 with four AI-generated still scenes and narration; it is not full motion video generation.
- The workflow stores output as an artifact; it does not yet post to YouTube, Instagram, or Facebook. Publishing needs separate official platform API/OAuth setup and permissions. Do not put social login passwords in GitHub.
- GitHub scheduled workflows can start late and are not a guaranteed exact-time scheduler.
- AI-created captions/tags do not guarantee virality. Review content and metadata before public posting.
