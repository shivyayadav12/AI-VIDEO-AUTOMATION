import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from config import OUTPUT_DIR, UPLOAD_DIR, VIDEO_PRESETS
from video_engine import build_slideshow
from voice_engine import SUPPORTED_VOICES, generate_speech

load_dotenv()
st.set_page_config(page_title="AI Video Automation", page_icon="🎬", layout="wide")
st.title("🎬 AI Video Automation")
st.caption("आइडिया → स्क्रिप्ट → AI हिंदी आवाज़ → वीडियो")
st.info("अब अपनी रिकॉर्डिंग अपलोड किए बिना हिंदी AI आवाज़ बना सकते हैं। यह सामान्य synthetic AI voice है, किसी व्यक्ति की आवाज़ की नकल नहीं।")

idea = st.text_area("वीडियो का आइडिया", placeholder="उदाहरण: एक मज़ेदार कार्टून कहानी जिसमें दो दोस्त खोया हुआ खज़ाना खोजते हैं...")
api_key = os.getenv("OPENAI_API_KEY", "").strip()

if api_key:
    if st.button("✨ मेरे आइडिया से AI स्क्रिप्ट बनाएं"):
        if not idea.strip():
            st.warning("पहले वीडियो का आइडिया लिखें।")
        else:
            try:
                with st.spinner("AI स्क्रिप्ट लिख रहा है..."):
                    client = OpenAI(api_key=api_key)
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "आप हिंदी वीडियो लेखक हैं। दिए गए आइडिया पर बोलने योग्य, स्वाभाविक हिंदी narration लिखें। केवल स्क्रिप्ट दें, शीर्षक या निर्देश नहीं। लगभग 30-60 सेकंड की स्क्रिप्ट रखें।"},
                            {"role": "user", "content": idea.strip()},
                        ],
                        temperature=0.8,
                    )
                    st.session_state["generated_script"] = response.choices[0].message.content.strip()
                st.success("स्क्रिप्ट तैयार है। आप चाहें तो इसे बदल सकते हैं।")
            except Exception as exc:
                st.error(f"स्क्रिप्ट बनाते समय समस्या आई: {exc}")
else:
    st.warning("AI से अपने-आप स्क्रिप्ट बनवाने के लिए अपने सर्वर की .env फ़ाइल में OPENAI_API_KEY सेट करें। API key को GitHub या चैट में साझा न करें। अभी आप नीचे स्क्रिप्ट खुद लिख सकते हैं।")

script = st.text_area("वीडियो की स्क्रिप्ट / बोलने वाला टेक्स्ट", value=st.session_state.get("generated_script", ""), height=180, placeholder="यहाँ हिंदी स्क्रिप्ट लिखें या ऊपर AI से बनवाएँ...")
voice_label = st.selectbox("AI हिंदी आवाज़ चुनें", list(SUPPORTED_VOICES.keys()))
preset = st.selectbox("वीडियो फॉर्मेट", list(VIDEO_PRESETS.keys()))
image_files = st.file_uploader("सीन की तस्वीरें अपलोड करें", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if st.button("🎬 AI आवाज़ के साथ वीडियो बनाएँ", type="primary"):
    if not idea.strip():
        st.error("पहले वीडियो का आइडिया लिखें।")
    elif not script.strip():
        st.error("पहले स्क्रिप्ट लिखें या AI से बनवाएँ।")
    elif not image_files:
        st.error("वीडियो बनाने के लिए कम से कम एक तस्वीर अपलोड करें।")
    else:
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            saved_images = []
            for index, uploaded in enumerate(image_files):
                image_path = UPLOAD_DIR / f"scene_{index}_{Path(uploaded.name).name}"
                image_path.write_bytes(uploaded.getvalue())
                saved_images.append(image_path)
            voice_path = OUTPUT_DIR / "ai_narration.mp3"
            output_path = OUTPUT_DIR / "my_video.mp4"
            with st.spinner("पहले AI आवाज़, फिर वीडियो तैयार हो रहा है..."):
                generate_speech(script, str(voice_path), voice=SUPPORTED_VOICES[voice_label])
                build_slideshow(saved_images, voice_path, output_path, size=VIDEO_PRESETS[preset])
            st.success("AI आवाज़ और वीडियो तैयार हैं!")
            st.audio(str(voice_path), format="audio/mp3")
            st.video(str(output_path))
            st.download_button("वीडियो डाउनलोड करें", data=output_path.read_bytes(), file_name="my_video.mp4", mime="video/mp4")
        except Exception as exc:
            st.error(f"वीडियो बनाते समय समस्या आई: {exc}")

st.divider()
st.subheader("अभी क्या-क्या काम करता है?")
st.markdown("- आइडिया से हिंदी स्क्रिप्ट: OpenAI API key सेट होने पर\n- लिखे हुए टेक्स्ट से हिंदी AI महिला या पुरुष आवाज़\n- अपलोड की गई तस्वीरों से 9:16 या 16:9 MP4 slideshow\n- वीडियो और narration को सुनकर/देखकर डाउनलोड करना\n\n**अभी बाकी:** AI से तस्वीरें/वीडियो अपने-आप बनाना और YouTube, Instagram, Facebook पर आधिकारिक API से पोस्ट करना।")
