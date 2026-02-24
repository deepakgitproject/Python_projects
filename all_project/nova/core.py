# speak(), command(), ML chat logic
import os
import sys
import json
import pickle
import numpy as np
import datetime

import pyttsx3
import speech_recognition as sr
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences

def resource_path(filename):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

    # First try root (for dev mode)
    direct = os.path.join(base_path, filename)
    if os.path.exists(direct):
        return direct

    # Then try nova/ subfolder (for PyInstaller mode)
    nested = os.path.join(base_path, "nova", filename)
    if os.path.exists(nested):
        return nested

    # Fallback (for debugging)
    return direct



# ---------- RESOURCE LOADING (BULLETPROOF) ----------
try:
    with open(resource_path("intents.json"), "r", encoding="utf-8") as file:
        data = json.load(file)

    model = load_model(resource_path("chat_model.h5"))

    with open(resource_path("tokenizer.pkl"), "rb") as f:
        tokenizer = pickle.load(f)

    with open(resource_path("label_encoder.pkl"), "rb") as f:
        label_encoder = pickle.load(f)

except Exception as e:
    print("Critical resource loading error:", e)
    print("Critical system files are missing. Please reinstall Nova.")
    sys.exit(1)

# ---------- TTS ----------
def initialize_engine(voice_index=1, rate_offset=-50, volume_offset=0.25):
    try:
        # Auto-select driver based on OS
        if sys.platform.startswith("win"):
            engine = pyttsx3.init("sapi5")
        elif sys.platform.startswith("darwin"):
            engine = pyttsx3.init("nsss")
        else:
            engine = pyttsx3.init("espeak")

        voices = engine.getProperty("voices")

        # --- Safe voice selection
        if voices and 0 <= voice_index < len(voices):
            engine.setProperty("voice", voices[voice_index].id)
        else:
            engine.setProperty("voice", voices[0].id)

        # --- Safe rate control
        rate = engine.getProperty("rate")
        engine.setProperty("rate", max(80, rate + rate_offset))

        # --- Safe volume control
        volume = engine.getProperty("volume")
        engine.setProperty("volume", min(max(volume + volume_offset, 0.0), 1.0))

        return engine

    except Exception as e:
        print(f"TTS Engine initialization failed: {e}")
        return None



def speak(text):
    engine = initialize_engine()
    engine.say(text)
    engine.runAndWait()


def cal_day():
    return datetime.datetime.now().strftime("%A")

def wishme(name="Boss"):
    now = datetime.datetime.now()
    hour = now.hour
    day = now.strftime("%A")
    t = now.strftime("%I:%M %p")

    if 0 <= hour < 12:
        greeting_time = "Good Morning"
    elif 12 <= hour < 18:
        greeting_time = "Good Afternoon"
    else:
        greeting_time = "Good Evening"

    message = f"It's {t} on {day}. How can I assist you?"
    greeting = f"{greeting_time} {name}! {message}"

    speak(greeting)
    print(message)


# ---------- SPEECH INPUT ----------
def command(timeout=5, phrase_time_limit=10):
    r = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            print("Listening...", end="", flush=True)

            r.adjust_for_ambient_noise(source, duration=0.5)
            r.energy_threshold = 300
            r.dynamic_energy_threshold = True
            r.pause_threshold = 0.8

            audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)

        print("\rRecognizing...", end="", flush=True)

        query = r.recognize_google(audio, language="en-in")
        print("\r", end="", flush=True)
        print(f"User said: {query}\n")

        return query.lower().strip()

    except sr.WaitTimeoutError:
        print("\nListening timed out.")
        speak("I didn't hear anything.")
        return None

    except sr.UnknownValueError:
        print("\nCould not understand audio.")
        speak("I didn't understand that.")
        return None

    except sr.RequestError:
        print("\nSpeech service error.")
        speak("Speech service is unavailable.")
        return None

# ---------- ML CHAT ----------
def chat_response(query):
    padded = pad_sequences(
        tokenizer.texts_to_sequences([query]),
        maxlen=20,
        truncating="post"
    )

    result = model.predict(padded, verbose=0)
    confidence = float(np.max(result))
    tag = label_encoder.inverse_transform([np.argmax(result)])[0]

    if confidence < 0.60:
        return None

    for intent in data["intents"]:
        if intent["tag"].lower() == tag.lower():
            return np.random.choice(intent["responses"])

    return None
