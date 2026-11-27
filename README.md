# AI Video Automation

यह GitHub Actions पर चलने वाला daily Hindi episodic video generator है।

## क्या करता है
- `IDEA.md` में दिए गए एक मुख्य विचार से हर रन में अगला भाग लिखता है।
- `story_state.json` में पिछली कहानी और पात्रों की पहचान रखता है।
- OpenAI API से स्क्रिप्ट और scene images बनाता है।
- Edge TTS से हिंदी AI narration बनाता है।
- `series.json` के अनुसार 9:16 Shorts/Reels या 16:9 वीडियो render करता है।
- शीर्षक, caption, description, hashtags और tags वाली metadata file बनाता है।
- हर दिन 20:00 IST (14:30 UTC) पर चलने के लिए schedule है; GitHub scheduled jobs कुछ देर से शुरू हो सकते हैं।
- तैयार वीडियो GitHub Actions artifact में मिलता है।

## एक बार की ज़रूरी सेटिंग
1. `IDEA.md` में अपनी सीरीज़ का मुख्य आइडिया लिखें।
2. Repository → Settings → Secrets and variables → Actions → New repository secret खोलें।
3. Secret का नाम `OPENAI_API_KEY` रखें और अपनी OpenAI API key डालें। Key को source code या chat में न डालें।
4. Actions tab में **Daily AI Video** workflow खोलकर **Run workflow** दबाएँ।

OpenAI API usage का अलग शुल्क लग सकता है। Edge TTS voice service इंटरनेट से चलती है; इसमें चुनी गई synthetic Hindi voice किसी व्यक्ति की आवाज़ की नकल नहीं करती।

## Output
हर सफल run में `output/daily_video.mp4`, `output/script.txt` और `output/metadata.json` artifact के रूप में सेव होते हैं। Artifact 14 दिन उपलब्ध रहता है। कहानी की निरंतरता `story_state.json` में commit होती है।

## सीमाएँ
- यह अभी image-based animated slideshow है, full motion AI video नहीं।
- YouTube, Instagram और Facebook पर auto-upload अभी configured नहीं है। उसके लिए platform APIs और account authorization अलग से जोड़ने होंगे।
- AI पात्रों की visual consistency की गारंटी नहीं है।
- वायरल होने की गारंटी नहीं दी जा सकती; publish करने से पहले metadata और वीडियो review करें।
