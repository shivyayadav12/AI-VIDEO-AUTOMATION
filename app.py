import streamlit as st
from pathlib import Path
from config import OUTPUT_DIR, UPLOAD_DIR, VIDEO_PRESETS
from video_engine import build_slideshow

st.set_page_config(page_title="AI Video Automation", page_icon="🎬", layout="wide")
st.title("🎬 AI Video Automation")
st.caption("Idea → आपकी रिकॉर्ड की हुई आवाज़ + तस्वीरें → शुरुआती वीडियो")

st.info(
    "यह पहला सुरक्षित MVP है: अभी यह आपकी अपलोड की हुई आवाज़ और तस्वीरों से वीडियो बनाता है। "
    "AI script/image/video generation और social publishing अगले चरण में API setup के बाद जोड़े जाएँगे।"
)

idea = st.text_area("वीडियो का आइडिया", placeholder="उदाहरण: एक प्रेरणादायक कहानी...")
script = st.text_area("बोलने के लिए स्क्रिप्ट", placeholder="यहाँ वह हिंदी टेक्स्ट लिखें जिसे आप अपनी आवाज़ में रिकॉर्ड करेंगे...")
preset = st.selectbox("वीडियो फॉर्मेट", list(VIDEO_PRESETS.keys()))
voice_file = st.file_uploader("अपनी आवाज़ की रिकॉर्डिंग अपलोड करें (MP3/WAV/M4A)", type=["mp3", "wav", "m4a"])
image_files = st.file_uploader("वीडियो की तस्वीरें अपलोड करें", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if st.button("वीडियो बनाएँ", type="primary"):
    if not idea.strip():
        st.error("पहले वीडियो का आइडिया लिखें।")
    elif not voice_file:
        st.error("हर वीडियो में आपकी आवाज़ रखने के लिए अपनी रिकॉर्डिंग अपलोड करें।")
    elif not image_files:
        st.error("कम से कम एक तस्वीर अपलोड करें।")
    else:
        try:
            voice_path = UPLOAD_DIR / voice_file.name
            voice_path.write_bytes(voice_file.getvalue())

            saved_images = []
            for index, uploaded in enumerate(image_files):
                image_path = UPLOAD_DIR / f"scene_{index}_{Path(uploaded.name).name}"
                image_path.write_bytes(uploaded.getvalue())
                saved_images.append(image_path)

            output_path = OUTPUT_DIR / "my_video.mp4"
            with st.spinner("आपकी वीडियो तैयार हो रही है..."):
                build_slideshow(
                    saved_images,
                    voice_path,
                    output_path,
                    size=VIDEO_PRESETS[preset],
                )
            st.success("वीडियो तैयार है!")
            st.video(str(output_path))
            st.download_button(
                "वीडियो डाउनलोड करें",
                data=output_path.read_bytes(),
                file_name="my_video.mp4",
                mime="video/mp4",
            )
        except Exception as exc:
            st.error(f"वीडियो बनाते समय समस्या आई: {exc}")

st.divider()
st.subheader("अगले चरण")
st.markdown(
    "- AI से हिंदी स्क्रिप्ट और scene prompts बनाना\n"
    "- AI image/video provider जोड़ना\n"
    "- आपकी आवाज़: अभी हर वीडियो के लिए आपकी रिकॉर्ड की हुई narration इस्तेमाल होती है\n"
    "- YouTube / Instagram / Facebook publishing: OAuth और official API permissions के बाद"
)
