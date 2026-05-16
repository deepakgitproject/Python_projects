import streamlit as st
import easyocr
import numpy as np
from PIL import Image
from transformers import (
    T5Tokenizer, T5ForConditionalGeneration,
    BartTokenizer, BartForConditionalGeneration,
)
import torch
import re

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Image Summarizer",
    page_icon="📄",
    layout="centered"
)

# ─────────────────────────────────────────────
#  MODEL REGISTRY
# ─────────────────────────────────────────────
OCR_MODELS = {
    "🟢 EasyOCR  |  ~100MB  |  Printed text, receipts, screenshots": {
        "id": "easyocr",
        "size": "~100MB",
        "speed": "Fast",
        "best_for": "Printed text, receipts, screenshots",
        "phone_req": "Any phone"
    },
}

SUMMARIZATION_MODELS = {
    "🟢 T5-Small  |  ~240MB  |  Default — lightweight, runs on any device": {
        "id": "t5-small",
        "size": "~240MB",
        "speed": "Fast",
        "best_for": "Short to medium text",
        "phone_req": "Any phone"
    },
    "🟡 DistilBART  |  ~900MB  |  Better summaries, moderate size": {
        "id": "sshleifer/distilbart-cnn-12-6",
        "size": "~900MB",
        "speed": "Medium",
        "best_for": "Articles, documents, longer text",
        "phone_req": "Mid-range phone or above"
    },
    "🔴 BART-Large-CNN  |  ~1.6GB  |  Best quality, heavy": {
        "id": "facebook/bart-large-cnn",
        "size": "~1.6GB",
        "speed": "Slow",
        "best_for": "Long documents, best accuracy",
        "phone_req": "High-end phone (8GB+ RAM)"
    },
}

# ─────────────────────────────────────────────
#  LOADERS
# ─────────────────────────────────────────────
@st.cache_resource
def load_easyocr():
    return easyocr.Reader(['en'], gpu=False)

@st.cache_resource
def load_t5():
    tokenizer = T5Tokenizer.from_pretrained("t5-small")
    model = T5ForConditionalGeneration.from_pretrained("t5-small")
    model.eval()
    return tokenizer, model

@st.cache_resource
def load_distilbart():
    tokenizer = BartTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6")
    model = BartForConditionalGeneration.from_pretrained("sshleifer/distilbart-cnn-12-6")
    model.eval()
    return tokenizer, model

@st.cache_resource
def load_bart_large():
    tokenizer = BartTokenizer.from_pretrained("facebook/bart-large-cnn")
    model = BartForConditionalGeneration.from_pretrained("facebook/bart-large-cnn")
    model.eval()
    return tokenizer, model

# ─────────────────────────────────────────────
#  RUN OCR
# ─────────────────────────────────────────────
def run_ocr(image: Image.Image) -> str:
    reader = load_easyocr()
    arr = np.array(image.convert("RGB"))
    results = reader.readtext(arr)
    return " ".join([t for (_, t, conf) in results if conf > 0.3]).strip()

# ─────────────────────────────────────────────
#  RUN SUMMARIZATION
# ─────────────────────────────────────────────
def run_summarization(text: str, model_id: str) -> str:
    if model_id == "t5-small":
        tokenizer, model = load_t5()
        input_text = "summarize: " + text[:500]
        inputs = tokenizer.encode(input_text, return_tensors="pt", max_length=512, truncation=True)
        with torch.no_grad():
            outputs = model.generate(inputs, max_length=150, min_length=30,
                                     length_penalty=2.0, num_beams=4, early_stopping=True)
        return tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

    elif model_id == "sshleifer/distilbart-cnn-12-6":
        tokenizer, model = load_distilbart()
        inputs = tokenizer.encode(text[:1024], return_tensors="pt", max_length=1024, truncation=True)
        with torch.no_grad():
            outputs = model.generate(inputs, max_length=150, min_length=30,
                                     length_penalty=2.0, num_beams=4, early_stopping=True)
        return tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

    elif model_id == "facebook/bart-large-cnn":
        tokenizer, model = load_bart_large()
        inputs = tokenizer.encode(text[:1024], return_tensors="pt", max_length=1024, truncation=True)
        with torch.no_grad():
            outputs = model.generate(inputs, max_length=150, min_length=30,
                                     length_penalty=2.0, num_beams=4, early_stopping=True)
        return tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

# ─────────────────────────────────────────────
#  FORMAT BULLETS
# ─────────────────────────────────────────────
def to_bullets(summary: str) -> list:
    sentences = re.split(r'(?<=[.!?;])\s+', summary.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 10]

# ─────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────
if "downloaded" not in st.session_state:
    st.session_state.downloaded = {
        "easyocr": False,
        "t5-small": False,
        "sshleifer/distilbart-cnn-12-6": False,
        "facebook/bart-large-cnn": False,
    }

if "download_error" not in st.session_state:
    st.session_state.download_error = {}

# ─────────────────────────────────────────────
#  DOWNLOAD FUNCTION
# ─────────────────────────────────────────────
def download_model(model_id: str):
    st.session_state.download_error.pop(model_id, None)
    try:
        if model_id == "easyocr":
            load_easyocr()
        elif model_id == "t5-small":
            load_t5()
        elif model_id == "sshleifer/distilbart-cnn-12-6":
            load_distilbart()
        elif model_id == "facebook/bart-large-cnn":
            load_bart_large()
        st.session_state.downloaded[model_id] = True
    except Exception as e:
        st.session_state.download_error[model_id] = str(e)

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Model Settings")

    # ── OCR SECTION ──
    st.markdown("### 🔍 OCR Model")
    st.caption("EasyOCR is used for text extraction")

    ocr_key = list(OCR_MODELS.keys())[0]
    ocr_model = OCR_MODELS[ocr_key]
    ocr_id = ocr_model["id"]

    st.markdown(f"**{ocr_key}**")
    st.caption(f"Best for: {ocr_model['best_for']}  |  Phone: {ocr_model['phone_req']}")

    if st.session_state.downloaded[ocr_id]:
        st.success("✅ Downloaded & Ready")
    else:
        if st.session_state.download_error.get(ocr_id):
            st.error(f"❌ {st.session_state.download_error[ocr_id]}")
        if st.button(f"⬇️ Download {ocr_model['size']}", key="dl_easyocr", use_container_width=True):
            with st.spinner("Downloading EasyOCR..."):
                download_model(ocr_id)
            st.rerun()

    selected_ocr = ocr_model

    st.divider()

    # ── SUMMARIZATION SECTION ──
    st.markdown("### 📝 Summarization Model")
    st.caption("Choose your summarization model")

    sum_keys = list(SUMMARIZATION_MODELS.keys())

    for key in sum_keys:
        m = SUMMARIZATION_MODELS[key]
        mid = m["id"]
        st.markdown(f"**{key}**")
        st.caption(f"Best for: {m['best_for']}  |  Phone: {m['phone_req']}")

        if st.session_state.downloaded[mid]:
            st.success("✅ Downloaded & Ready")
        else:
            if st.session_state.download_error.get(mid):
                st.error(f"❌ {st.session_state.download_error[mid]}")
            if st.button(f"⬇️ Download {m['size']}", key=f"dl_sum_{mid}", use_container_width=True):
                with st.spinner(f"Downloading {mid.split('/')[-1]}... this may take a few minutes"):
                    download_model(mid)
                st.rerun()
        st.markdown("")

    available_sum = [k for k in sum_keys if st.session_state.downloaded[SUMMARIZATION_MODELS[k]["id"]]]
    if not available_sum:
        st.warning("⬆️ Download at least one summarization model to start.")
        selected_sum = SUMMARIZATION_MODELS[sum_keys[0]]
    else:
        selected_sum_label = st.radio(
            "Active summarization model",
            options=available_sum,
            index=0,
        )
        selected_sum = SUMMARIZATION_MODELS[selected_sum_label]

    st.divider()

    # ── SIZE WARNING ──
    sum_size_map = {
        "t5-small": 240,
        "sshleifer/distilbart-cnn-12-6": 900,
        "facebook/bart-large-cnn": 1600
    }
    total_mb = 100 + sum_size_map[selected_sum["id"]]
    total_gb = round(total_mb / 1000, 2)

    st.markdown("### 📱 Total Model Size")
    if total_mb < 500:
        st.success(f"✅ {total_gb}GB — Works on any phone")
    elif total_mb < 1200:
        st.warning(f"⚠️ {total_gb}GB — Needs a mid-range phone")
    else:
        st.error(f"🔴 {total_gb}GB — Needs a high-end phone (8GB+ RAM)")

    st.divider()
    st.caption("🟢 Default = any phone  🟡 Medium = mid-range  🔴 Heavy = flagship only")

# ─────────────────────────────────────────────
#  MAIN PAGE
# ─────────────────────────────────────────────
st.title("📄 Image Summarizer")
st.write("Upload an image with text — we'll read it and summarize it into bullet points.")
st.divider()

uploaded_file = st.file_uploader(
    "Upload an image (JPG, JPEG, PNG)",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:

    image = Image.open(uploaded_file)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.image(image, caption="Uploaded Image", width=280)
    with col2:
        st.markdown("**Selected Models**")
        st.write(f"🔍 OCR: `easyocr`")
        st.write(f"📝 Summary: `{selected_sum['id'].split('/')[-1]}`")
        st.write(f"💾 Total size: `{total_gb}GB`")
        st.write(f"🖥️ Device: `CPU`")
        st.write(f"📐 Image: `{image.size[0]}x{image.size[1]}px`")

    st.divider()

    ocr_ready = st.session_state.downloaded["easyocr"]
    sum_ready = st.session_state.downloaded[selected_sum["id"]]

    if not ocr_ready or not sum_ready:
        missing = []
        if not ocr_ready:
            missing.append("EasyOCR")
        if not sum_ready:
            missing.append(selected_sum["id"].split("/")[-1])
        st.warning(f"⚠️ Please download first: {', '.join(missing)}")
    else:
        if st.button("🚀 Extract & Summarize", use_container_width=True, type="primary"):

            with st.spinner("🔍 Reading text from image..."):
                try:
                    extracted_text = run_ocr(image)
                except Exception as e:
                    st.error(f"OCR failed: {e}")
                    st.stop()

            if not extracted_text:
                st.error("❌ No text found. Try a clearer image with visible printed text.")
                st.stop()

            st.subheader("📝 Extracted Text")
            st.text_area("Raw OCR output", value=extracted_text, height=150)

            st.divider()

            with st.spinner(f"🤖 Summarizing with {selected_sum['id'].split('/')[-1]}..."):
                try:
                    summary = run_summarization(extracted_text, selected_sum["id"])
                    bullets = to_bullets(summary)
                except Exception as e:
                    st.error(f"Summarization failed: {e}")
                    st.stop()

            st.subheader("✅ Summary")
            for bullet in bullets:
                st.markdown(f"• {bullet}")

            st.divider()

            c1, c2, c3 = st.columns(3)
            c1.metric("Words extracted", len(extracted_text.split()))
            c2.metric("Words in summary", len(summary.split()))
            compression = round((1 - len(summary.split()) / max(len(extracted_text.split()), 1)) * 100)
            c3.metric("Compression", f"{compression}%")

else:
    st.info("👆 Upload an image to get started.")
    st.markdown("""
**Good images to test with:**
- 📄 Printed document or article
- 🧾 Receipt or invoice
- 📸 Screenshot of text
- 📝 Typed or handwritten notes
    """)