import streamlit as st
import numpy as np
import pickle
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences

# Page config
st.set_page_config(page_title="Emotion Detection", layout="centered")

st.title("😊 Emotion Detection from Text")
st.write("Enter a sentence and detect the emotion.")

# Load saved objects (cached to avoid reload)
@st.cache_resource
def load_resources():
    model = load_model("emotion_model.h5")
    tokenizer = pickle.load(open("tokenizer.pkl", "rb"))
    label_encoder = pickle.load(open("label_encoder.pkl", "rb"))
    max_length = pickle.load(open("max_length.pkl", "rb"))
    return model, tokenizer, label_encoder, max_length

model, tokenizer, label_encoder, max_length = load_resources()

# User input
user_text = st.text_area("Enter text here:")

if st.button("Predict Emotion"):
    if user_text.strip() == "":
        st.warning("Please enter some text.")
    else:
        sequence = tokenizer.texts_to_sequences([user_text])
        padded = pad_sequences(sequence, maxlen=max_length)

        prediction = model.predict(padded)
        predicted_class = np.argmax(prediction[0])
        emotion = label_encoder.inverse_transform([predicted_class])[0]

        st.success(f"**Predicted Emotion:** {emotion}")
