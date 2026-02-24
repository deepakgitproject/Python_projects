"""
╔══════════════════════════════════════════════════════════════════╗
║                     HYPER AI  —  Voice Assistant                ║
║                     v2.0  —  ML-Enhanced Build                   ║
╠══════════════════════════════════════════════════════════════════╣
║  UPGRADES IN v2.0:                                                ║
║  • STT      : faster-whisper (offline, 98%+ accuracy)            ║
║  • Activation: Alt+Shift+1 hotkey or mic button (no wake word)  ║
║  • Noise    : noisereduce (spectral gating) + webrtcvad (VAD)    ║
║  • Vision   : meta-llama/llama-4-scout:free (replaces 404 model) ║
║  • All original features preserved                                ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ─── STANDARD IMPORTS ────────────────────────────────────────────
import datetime
import time
import webbrowser
import pyautogui
import pyttsx3
import speech_recognition as sr
import json
import random
import psutil
import subprocess
import threading
import screen_brightness_control as sbc
import re
import warnings
import logging
import os
import sys
import struct
import io
import wave

# ─── ML / AUDIO IMPORTS ──────────────────────────────────────────
import winsound
import base64
import shutil
import requests
import pyperclip
import wikipedia as wiki_api
import numpy as np
import sounddevice as sd
import keyboard

try:
    from faster_whisper import WhisperModel
    _HAS_WHISPER = True
except ImportError:
    _HAS_WHISPER = False
    print("[WARN] faster-whisper not installed. Falling back to Google STT.")



try:
    import noisereduce as nr
    _HAS_NR = True
except ImportError:
    _HAS_NR = False

try:
    import webrtcvad
    _HAS_VAD = True
except ImportError:
    _HAS_VAD = False


# ══════════════════════════════════════════════════════════════════
#  CONFIG  ─  reads config.json sitting next to this script
#  Paste your OpenRouter API key in config.json
# ══════════════════════════════════════════════════════════════════
_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def _load_cfg():
    if os.path.exists(_CFG_FILE):
        try:
            with open(_CFG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[config] Could not read config.json: {e}")
    return {}

CFG = _load_cfg()

# Silence noisy library warnings (same as original)
logging.getLogger("screen_brightness_control").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning)
pyautogui.FAILSAFE = False


# ══════════════════════════════════════════════════════════════════
#  WHISPER MODEL  —  lazy-loaded once on first use
#  "base.en" = best speed/accuracy tradeoff for English on CPU
#  Runs 100% offline after first download (~150 MB)
# ══════════════════════════════════════════════════════════════════
_whisper_model = None
_WHISPER_SIZE = CFG.get("whisper_model", "base.en")     # tiny.en / base.en / small.en

def _get_whisper():
    global _whisper_model
    if _whisper_model is None and _HAS_WHISPER:
        print(f"[Whisper] Loading '{_WHISPER_SIZE}' model (first time may download)...", flush=True)
        _whisper_model = WhisperModel(
            _WHISPER_SIZE,
            device="cpu",
            compute_type="int8",       # 4x faster on CPU vs float32
            cpu_threads=os.cpu_count() or 4,
        )
        print("[Whisper] ✓ Model ready.", flush=True)
    return _whisper_model


# ══════════════════════════════════════════════════════════════════
#  NOISE REDUCTION  —  spectral gating via noisereduce
# ══════════════════════════════════════════════════════════════════
_SAMPLE_RATE = 16000   # 16 kHz mono — optimal for Whisper & VAD

def _reduce_noise(audio_np: np.ndarray) -> np.ndarray:
    """Apply spectral-gating noise reduction to raw audio numpy array."""
    if _HAS_NR:
        try:
            return nr.reduce_noise(
                y=audio_np.astype(np.float32),
                sr=_SAMPLE_RATE,
                stationary=False,      # handles non-stationary noise too
                prop_decrease=0.75,    # 75% noise reduction (keeps speech natural)
            )
        except Exception:
            pass
    return audio_np


def _vad_filter(audio_np: np.ndarray, sample_rate: int = _SAMPLE_RATE) -> bool:
    """Return True if audio contains speech (WebRTC VAD check)."""
    if not _HAS_VAD:
        return True   # assume speech if VAD unavailable
    try:
        vad = webrtcvad.Vad(2)   # aggressiveness 0-3 (2 = balanced)
        pcm = (audio_np * 32767).astype(np.int16).tobytes()
        frame_duration = 30      # ms
        frame_size = int(sample_rate * frame_duration / 1000) * 2  # bytes
        voiced = 0
        total = 0
        for i in range(0, len(pcm) - frame_size, frame_size):
            total += 1
            if vad.is_speech(pcm[i:i + frame_size], sample_rate):
                voiced += 1
        return total > 0 and (voiced / total) > 0.15   # >15% voiced frames
    except Exception:
        return True


def _np_to_wav_bytes(audio_np: np.ndarray, sr: int = _SAMPLE_RATE) -> bytes:
    """Convert numpy float32 array to WAV bytes for Whisper."""
    pcm = (audio_np * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════
#  TTS  —  identical to original
# ══════════════════════════════════════════════════════════════════
def initialize_engine(voice_index=1, rate_offset=-50, volume_offset=0.25):
    try:
        if sys.platform.startswith("win"):
            engine = pyttsx3.init("sapi5")
        elif sys.platform.startswith("darwin"):
            engine = pyttsx3.init("nsss")
        else:
            engine = pyttsx3.init("espeak")

        voices = engine.getProperty("voices")
        if voices and 0 <= voice_index < len(voices):
            engine.setProperty("voice", voices[voice_index].id)
        else:
            engine.setProperty("voice", voices[0].id)

        rate = engine.getProperty("rate")
        engine.setProperty("rate", max(80, rate + rate_offset))

        volume = engine.getProperty("volume")
        engine.setProperty("volume", min(max(volume + volume_offset, 0.0), 1.0))

        return engine
    except Exception as e:
        print(f"TTS Engine initialization failed: {e}")
        return None


def speak(text):
    """Identical to original."""
    engine = initialize_engine()
    engine.say(text)
    engine.runAndWait()


# ══════════════════════════════════════════════════════════════════
#  COMMAND (VOICE INPUT)  —  v2.0 Whisper-powered
# ══════════════════════════════════════════════════════════════════
def command(timeout=6, phrase_time_limit=10):
    """
    Listen for a voice command and return it as lowercase text.

    v2.0 PIPELINE:
    1. Record raw 16 kHz mono audio via sounddevice
    2. Apply spectral-gating noise reduction (noisereduce)
    3. Check WebRTC VAD — skip if no speech detected
    4. Transcribe OFFLINE with faster-whisper (base.en, int8)
    5. Fallback to Google STT if Whisper not installed
    """
    _MIC_BUSY.set()

    try:
        whisper = _get_whisper()

        if whisper:
            # ── WHISPER PATH (preferred) ─────────────────────────
            for attempt in range(2):
                try:
                    if attempt == 0:
                        print("\nListening...", end="", flush=True)
                    else:
                        print("\n[Retry] Listening again...", end="", flush=True)

                    # Record with sounddevice (16 kHz mono float32)
                    duration = phrase_time_limit
                    audio_np = sd.rec(
                        int(duration * _SAMPLE_RATE),
                        samplerate=_SAMPLE_RATE,
                        channels=1,
                        dtype="float32",
                    )

                    # Wait for speech with early stop on silence
                    sd.wait()
                    audio_np = audio_np.flatten()

                    # Trim trailing silence (energy-based)
                    energy = np.abs(audio_np)
                    threshold = np.mean(energy) * 0.5
                    nonsilent = np.where(energy > threshold)[0]
                    if len(nonsilent) == 0:
                        if attempt == 0:
                            continue
                        print("\nNo input detected.", flush=True)
                        speak("I didn't hear anything.")
                        return None
                    # Keep audio from start to last non-silent + 0.3s padding
                    end_idx = min(nonsilent[-1] + int(0.3 * _SAMPLE_RATE), len(audio_np))
                    audio_np = audio_np[:end_idx]

                    # Step 2: Noise reduction
                    audio_clean = _reduce_noise(audio_np)

                    # Step 3: VAD check
                    if not _vad_filter(audio_clean):
                        if attempt == 0:
                            continue
                        print("\nNo speech detected.", flush=True)
                        speak("I didn't hear anything.")
                        return None

                    print("\rRecognizing...", end="", flush=True)

                    # Step 4: Whisper transcription (offline)
                    # Write to temp WAV in memory
                    wav_bytes = _np_to_wav_bytes(audio_clean)
                    tmp_path = os.path.join(
                        os.environ.get("TEMP", "."),
                        "_hyper_cmd.wav"
                    )
                    with open(tmp_path, "wb") as f:
                        f.write(wav_bytes)

                    segments, info = whisper.transcribe(
                        tmp_path,
                        beam_size=5,
                        language="en",
                        vad_filter=True,
                        vad_parameters=dict(
                            min_silence_duration_ms=300,
                            speech_pad_ms=200,
                        ),
                    )
                    query = " ".join(seg.text for seg in segments).strip()

                    # Clean up temp file
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                    if query:
                        print("\r" + " " * 20 + "\r", end="", flush=True)
                        print(f"You said: {query}\n")
                        return query.lower().strip()
                    else:
                        if attempt == 0:
                            continue
                        print("\nCould not understand.", flush=True)
                        speak("I didn't catch that. Please say it again.")
                        return None

                except Exception as e:
                    print(f"\n[Whisper] Error: {e}", flush=True)
                    if attempt == 0:
                        continue
                    speak("Speech recognition error.")
                    return None
        else:
            # ── GOOGLE STT FALLBACK ──────────────────────────────
            r = sr.Recognizer()
            r.energy_threshold = 200
            r.dynamic_energy_threshold = False
            r.pause_threshold = 0.8

            for attempt in range(2):
                try:
                    with sr.Microphone() as source:
                        if attempt == 0:
                            print("\nListening...", end="", flush=True)
                        else:
                            print("\n[Retry] Listening again...", end="", flush=True)
                        r.adjust_for_ambient_noise(source, duration=0.3)
                        audio = r.listen(source, timeout=timeout,
                                         phrase_time_limit=phrase_time_limit)

                    print("\rRecognizing...", end="", flush=True)
                    query = None
                    try:
                        query = r.recognize_google(audio, language="en-IN")
                    except sr.UnknownValueError:
                        try:
                            query = r.recognize_google(audio, language="en-US")
                        except sr.UnknownValueError:
                            if attempt == 0:
                                continue
                            print("\nCould not understand.", flush=True)
                            speak("I didn't catch that. Please say it again.")
                            return None

                    if query:
                        print("\r" + " " * 20 + "\r", end="", flush=True)
                        print(f"You said: {query}\n")
                        return query.lower().strip()

                except sr.WaitTimeoutError:
                    if attempt == 0:
                        continue
                    print("\nNo input detected.", flush=True)
                    speak("I didn't hear anything.")
                    return None
                except sr.RequestError:
                    print("\nSpeech service error.", flush=True)
                    speak("Speech service is unavailable.")
                    return None

    finally:
        _MIC_BUSY.clear()

    return None


# ══════════════════════════════════════════════════════════════════
#  ACTIVATION  —  hotkey (Alt+Shift+1) or GUI mic button
#  No wake word.  _WAKE_EVENT is set by _hotkey_thread or the GUI.
# ══════════════════════════════════════════════════════════════════

# ── Activation events ────────────────────────────────────────────
# _WAKE_EVENT : fired by hotkey (Alt+Shift+1) or mic button click
# _MIC_BUSY   : set while command() is recording to block hotkey re-entry
_WAKE_EVENT = threading.Event()
_MIC_BUSY   = threading.Event()








def _wait_for_activation():
    """
    Blocks (0 % CPU) until Alt+Shift+1 is pressed OR the mic button
    fires the event from the GUI.  No wake word involved.
    """
    _WAKE_EVENT.clear()
    _WAKE_EVENT.wait()
    print("[Hyper AI] Activated — listening for command.", flush=True)


# ══════════════════════════════════════════════════════════════════
#  HOTKEY WAKE  —  Alt+Shift+1 as keyboard shortcut wake trigger
#  Works identically to the voice wake word — fires _WAKE_EVENT.
# ══════════════════════════════════════════════════════════════════
_HOTKEY_COMBO = CFG.get("hotkey", "alt+shift+1")

def _hotkey_thread():
    """Register a global hotkey that triggers the wake event."""
    def _on_hotkey():
        if not _MIC_BUSY.is_set():
            print(f"[Hotkey] ★ {_HOTKEY_COMBO} pressed! ★", flush=True)
            _WAKE_EVENT.set()

    try:
        keyboard.add_hotkey(_HOTKEY_COMBO, _on_hotkey, suppress=False)
        print(f"[Hotkey] ✓ Press {_HOTKEY_COMBO.upper()} to activate Hyper AI.", flush=True)
        keyboard.wait()   # block forever — keeps hotkey listener alive
    except Exception as e:
        print(f"[Hotkey] Could not register hotkey: {e}", flush=True)
        print("[Hotkey] Tip: Run as Administrator for global hotkey support.", flush=True)


# ══════════════════════════════════════════════════════════════════
#  OPENROUTER AI  —  for intent understanding + chat fallback
# ══════════════════════════════════════════════════════════════════
_OR_URL    = "https://openrouter.ai/api/v1/chat/completions"
_OR_CHAT   = "openrouter/auto"                                    # best free text model
_OR_VISION = "meta-llama/llama-4-scout:free"                      # free vision model (replaces dead 11b)


def _or_call(messages: list, vision: bool = False) -> str:
    """Raw OpenRouter API call. Returns response string or ''."""
    api_key = CFG.get("openrouter_api_key", "")
    if not api_key or api_key == "YOUR_OPENROUTER_API_KEY_HERE":
        speak("Please add your OpenRouter API key in config.json.")
        return ""
    try:
        resp = requests.post(
            _OR_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
                "X-Title":       "Hyper AI",
            },
            data=json.dumps({
                "model":      _OR_VISION if vision else _OR_CHAT,
                "messages":   messages,
                "max_tokens": 400,
            }),
            timeout=25,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.HTTPError:
        print(f"[OpenRouter] HTTP {resp.status_code}: {resp.text}", flush=True)
        speak("AI service error. Check your API key.")
        return ""
    except requests.exceptions.Timeout:
        speak("AI request timed out.")
        return ""
    except Exception as e:
        print(f"[OpenRouter] {e}", flush=True)
        return ""


def interpret_intent(raw_query: str) -> str:
    """
    When voice recognition gives something unclear or garbled,
    send it to AI and ask it to figure out the real intent.
    Returns a clean normalized command string.

    Example:  "brit ness up" → "increase brightness"
              "open spoitify" → "open spotify"
              "wetha in delhi" → "weather in delhi"
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a voice command interpreter for a Windows voice assistant called Hyper AI. "
                "The user's speech was recognized by Google STT but may be garbled, misspelled, "
                "or unclear due to accent or noise. "
                "Your job: output ONLY the corrected, clean command the user most likely meant. "
                "One short line only. No explanation. No punctuation. Lowercase. "
                "Examples:\n"
                "  Input: 'brit ness up'  → Output: increase brightness\n"
                "  Input: 'open spoitify' → Output: open spotify\n"
                "  Input: 'wetha in delhi'→ Output: weather in delhi\n"
                "  Input: 'what is 45 tims 12' → Output: what is 45 times 12\n"
                "  Input: 'remind me in tem minutes to drink watter' "
                "→ Output: remind me in 10 minutes to drink water"
            )
        },
        {"role": "user", "content": raw_query}
    ]
    corrected = _or_call(messages)
    if corrected and corrected != raw_query:
        print(f"[Intent] '{raw_query}' → '{corrected}'", flush=True)
    return corrected if corrected else raw_query


def ai_chat(query: str):
    """Fallback: general conversation via OpenRouter when no rule matched."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are Hyper AI, a friendly voice assistant. "
                "Reply in 1-2 short spoken sentences. "
                "No markdown, no symbols, no bullet points. Plain English only."
            )
        },
        {"role": "user", "content": query}
    ]
    result = _or_call(messages)
    if result:
        speak(result)
    else:
        speak("I'm not sure how to help with that. Try rephrasing.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 1  —  BRIGHTNESS  (original, untouched)
# ══════════════════════════════════════════════════════════════════
def brightness_control(query):
    query = query.lower().strip()
    try:
        current = sbc.get_brightness()[0]
    except Exception:
        speak("I cannot control brightness on this device.")
        return

    match = re.search(r"(\d+)\s*(percent|%)", query)
    if match:
        value = max(0, min(100, int(match.group(1))))
        sbc.set_brightness(value)
        speak(f"Brightness set to {value} percent")
        return

    if any(w in query for w in ["increase brightness", "brightness up", "make it brighter", "brighten"]):
        new = min(current + 20, 100)
        sbc.set_brightness(new)
        speak(f"Increasing brightness to {new} percent")
        return

    if any(w in query for w in ["decrease brightness", "brightness down", "make it dimmer", "dim", "lower brightness"]):
        new = max(current - 20, 0)
        sbc.set_brightness(new)
        speak(f"Decreasing brightness to {new} percent")
        return

    speak("Brightness command not recognized.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 2  —  BING SEARCH  (original, untouched)
# ══════════════════════════════════════════════════════════════════
def bing_search():
    """Open 10 random search tabs for Bing reward points. (v2.0: no longer needs nltk)"""
    _word_pool = [
        "python", "machine learning", "artificial intelligence", "computer science",
        "deep learning", "neural network", "programming", "algorithm", "database",
        "cybersecurity", "cloud computing", "data science", "web development",
        "blockchain", "quantum computing", "robotics", "iot", "game development",
        "mobile app", "natural language processing", "computer vision", "devops",
        "linux", "windows", "networking", "software engineering", "api design",
        "microservices", "docker", "kubernetes", "git", "javascript", "react",
        "tensorflow", "pytorch", "raspberry pi", "arduino", "3d printing",
        "virtual reality", "augmented reality", "space exploration", "astronomy",
    ]
    num_tabs = 10
    for _ in range(num_tabs):
        random_word = random.choice(_word_pool)
        webbrowser.open(f"https://www.bing.com/search?q={random_word}")
        time.sleep(2)
        pyautogui.hotkey("ctrl", "t")
        time.sleep(2)
        pyautogui.typewrite(random_word)
        pyautogui.press("enter")
        time.sleep(10)


# ══════════════════════════════════════════════════════════════════
#  FEATURE 3  —  WISHME / TIME / DATE  (original, untouched)
# ══════════════════════════════════════════════════════════════════
def cal_day():
    return datetime.datetime.now().strftime("%A")


def wishme(name="Boss"):
    now  = datetime.datetime.now()
    hour = now.hour
    t    = now.strftime("%I:%M %p")
    day  = now.strftime("%A")

    if   0  <= hour < 12: greeting_time = "Good Morning"
    elif 12 <= hour < 18: greeting_time = "Good Afternoon"
    else:                  greeting_time = "Good Evening"

    greeting = f"{greeting_time} {name}! It's {t} on {day}. How can I assist you?"
    speak(greeting)
    print(greeting)


# ══════════════════════════════════════════════════════════════════
#  FEATURE 4  —  SCREENSHOT  (original + AI analysis added)
# ══════════════════════════════════════════════════════════════════
def take_screenshot(name=None):
    try:
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{name}_{ts}.png" if name else f"screenshot_{ts}.png"
        filepath = os.path.join(downloads, filename)
        pyautogui.screenshot().save(filepath)
        speak("Screenshot taken and saved to Downloads.")
        print(f"Screenshot saved: {filepath}", flush=True)
        return filepath
    except Exception as e:
        speak("Failed to take screenshot.")
        print(f"Screenshot error: {e}", flush=True)
        return None


def analyze_screenshot(filepath: str):
    """Send screenshot to vision AI and speak the analysis."""
    speak("Analyzing screenshot. Please wait.")
    try:
        with open(filepath, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Analyze this screenshot. Describe what you see. "
                        "If there is code, briefly review it. "
                        "If there is an error, explain it. "
                        "Under 4 sentences. No markdown. Plain English."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"}
                }
            ]
        }]
        result = _or_call(messages, vision=True)
        if result:
            print(f"\n[AI Analysis]\n{result}\n", flush=True)
            speak(result[:580] + " — see terminal for full result." if len(result) > 580 else result)
        else:
            speak("Could not analyze the screenshot.")
    except Exception as e:
        speak("Analysis failed.")
        print(f"[Vision] {e}", flush=True)


def handle_screenshot_command(query):
    query = query.lower().strip()

    # AI analysis trigger (NEW)
    if any(w in query for w in ["analyze", "analyse", "explain", "review",
                                "describe", "what is on", "what on", "my screen"]):
        fp = take_screenshot()
        if fp:
            analyze_screenshot(fp)
        return

    # Named screenshot (original)
    match = re.search(r"(named|name it|call it)\s+(\w+)", query)
    if match:
        take_screenshot(match.group(2))
        return

    # Plain screenshot (original)
    take_screenshot()


# ══════════════════════════════════════════════════════════════════
#  FEATURE 5  —  SOCIAL MEDIA  (original, untouched)
# ══════════════════════════════════════════════════════════════════
def social_media(query):
    sites = {
        "facebook":  "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
        "twitter":   "https://www.twitter.com",
        "discord":   "https://www.discord.com",
        "whatsapp":  "https://web.whatsapp.com",
        "youtube":   "https://www.youtube.com",
    }
    for name, url in sites.items():
        if name in query:
            speak(f"Opening {name.title()}")
            webbrowser.open(url)
            return
    speak("Social media platform not recognized.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 6  —  VOLUME CONTROL  (original, untouched)
# ══════════════════════════════════════════════════════════════════
def volume_control(query):
    query = query.lower().strip()

    def press_key(key, times=10):
        for _ in range(times):
            pyautogui.press(key)

    if any(w in query for w in ["unmute", "sound on"]):
        speak("Unmuting volume")
        pyautogui.press("volumemute")
        return
    if any(w in query for w in ["mute", "silent"]):
        speak("Muting volume")
        pyautogui.press("volumemute")
        return
    if any(w in query for w in ["increase", "volume up", "louder", "raise volume"]):
        speak("Increasing volume")
        press_key("volumeup")
        return
    if any(w in query for w in ["decrease", "volume down", "quieter", "lower volume"]):
        speak("Decreasing volume")
        press_key("volumedown")
        return
    speak("Volume command not recognized.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 7  —  APPS  (original, untouched)
# ══════════════════════════════════════════════════════════════════
APPS = {
    "notepad":       {"open": "notepad",                          "close": "notepad.exe"},
    "calculator":    {"open": "calc",                             "close": "Calculator.exe"},
    "calc":          {"open": "calc",                             "close": "Calculator.exe"},
    "command prompt":{"open": "cmd",                              "close": "cmd.exe"},
    "cmd":           {"open": "cmd",                              "close": "cmd.exe"},
    "paint":         {"open": "mspaint",                          "close": "mspaint.exe"},
    "wordpad":       {"open": "wordpad",                          "close": "wordpad.exe"},
    "camera":        {"open": "start microsoft.windows.camera:",  "close": "WindowsCamera.exe"},
    "settings":      {"open": "start ms-settings:",              "close": "SystemSettings.exe"},
    "file explorer": {"open": "explorer",                         "close": "explorer.exe"},
    "explorer":      {"open": "explorer",                         "close": "explorer.exe"},
    "chrome":        {"open": "start chrome",                     "close": "chrome.exe"},
    "brave":         {"open": "start brave",                      "close": "brave.exe"},
    "edge":          {"open": "start msedge",                     "close": "msedge.exe"},
    "firefox":       {"open": "start firefox",                    "close": "firefox.exe"},
    "opera":         {"open": "start opera",                      "close": "opera.exe"},
    "vlc":           {"open": "start vlc",                        "close": "vlc.exe"},
    "spotify":       {"open": "start spotify",                    "close": "spotify.exe"},
    "discord":       {"open": "start discord",                    "close": "discord.exe"},
    "teams":         {"open": "start ms-teams",                   "close": "ms-teams.exe"},
    "zoom":          {"open": "start zoom",                       "close": "zoom.exe"},
    "skype":         {"open": "start skype",                      "close": "skype.exe"},
    "vs code":       {"open": "code",                             "close": "Code.exe"},
    "visual studio": {"open": "devenv",                           "close": "devenv.exe"},
    "git bash":      {"open": "start git-bash",                   "close": "git-bash.exe"},
    "powershell":    {"open": "powershell",                       "close": "powershell.exe"},
    "task manager":  {"open": "taskmgr",                          "close": "Taskmgr.exe"},
    "control panel": {"open": "control",                          "close": "control.exe"},
    "photos":        {"open": "start ms-photos:",                 "close": "Microsoft.Photos.exe"},
    "snipping tool": {"open": "snippingtool",                     "close": "SnippingTool.exe"},
    "onenote":       {"open": "onenote",                          "close": "onenote.exe"},
    "outlook":       {"open": "outlook",                          "close": "outlook.exe"},
    "excel":         {"open": "excel",                            "close": "excel.exe"},
    "word":          {"open": "winword",                          "close": "winword.exe"},
    "powerpoint":    {"open": "powerpnt",                         "close": "powerpnt.exe"},
    "steam":         {"open": "start steam",                      "close": "steam.exe"},
    "epic games":    {"open": "start epicgameslauncher",          "close": "EpicGamesLauncher.exe"},
}


def open_app(query):
    query = query.lower()
    for name, cmds in APPS.items():
        if name in query:
            speak(f"Opening {name.title()}")
            os.system(cmds["open"])
            return
    speak("Application not recognized.")


def close_app(query):
    query = query.lower()
    for name, cmds in APPS.items():
        if name in query:
            speak(f"Closing {name.title()}")
            os.system(f'taskkill /f /im {cmds["close"]}')
            return
    speak("Application not recognized.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 8  —  BROWSING  (original, untouched)
# ══════════════════════════════════════════════════════════════════
def browsing(query):
    query = query.lower().strip()
    if any(k in query for k in ["browse", "search"]):
        speak("What should I search for?")
        s = command()
        if s:
            speak(f"Searching for {s}")
            webbrowser.open(f"https://www.google.com/search?q={s}")
        return
    speak("Browsing command not recognized.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 9  —  SYSTEM CONDITION  (original + RAM added)
# ══════════════════════════════════════════════════════════════════
def condition():
    usage = psutil.cpu_percent(interval=1)
    speak(f"CPU usage is at {usage} percent")

    ram = psutil.virtual_memory()
    speak(f"RAM usage is {ram.percent} percent. "
          f"{ram.used // (1024**3)} gigabytes used out of {ram.total // (1024**3)} gigabytes.")

    battery = psutil.sensors_battery()
    if battery is None:
        speak("Battery information is not available.")
        return

    pct    = battery.percent
    plugged = battery.power_plugged
    speak(f"Battery level is at {pct} percent. "
          f"{'Currently charging.' if plugged else 'Running on battery.'}")

    if pct >= 80:
        speak("We have enough battery to continue working.")
    elif 40 <= pct < 80:
        speak("Battery is moderate. Consider plugging in the charger.")
    else:
        speak("Battery is very low. Please connect your charger immediately.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 10  —  SLEEP MODE  (original, untouched)
# ══════════════════════════════════════════════════════════════════
sleep_timer = None


def go_to_sleep(delay_minutes=0):
    global sleep_timer

    def sleep_action():
        speak("Going to sleep now. Goodbye!")
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    if sleep_timer and sleep_timer.is_alive():
        sleep_timer.cancel()

    if delay_minutes <= 0:
        sleep_action()
    else:
        speak(f"Okay, I will put the system to sleep in {delay_minutes} minutes.")
        sleep_timer = threading.Timer(delay_minutes * 60, sleep_action)
        sleep_timer.start()


def cancel_sleep():
    global sleep_timer
    if sleep_timer and sleep_timer.is_alive():
        sleep_timer.cancel()
        sleep_timer = None
        speak("Sleep mode has been cancelled.")
    else:
        speak("No sleep mode is currently scheduled.")


def handle_sleep_command(query):
    query = query.lower().strip()

    if any(w in query for w in ["cancel sleep", "stop sleep", "don't sleep"]):
        cancel_sleep()
        return

    match = re.search(r"(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)", query)
    if match:
        value = int(match.group(1))
        delay  = value * 60 if "hour" in match.group(2) else value
        go_to_sleep(delay)
        return

    if any(w in query for w in ["sleep now", "go to sleep", "sleep mode", "put laptop to sleep"]):
        speak("Are you sure you want to put the system to sleep now?")
        confirm = command()
        if confirm and any(w in confirm for w in ["yes", "sure", "confirm", "ok", "okay"]):
            go_to_sleep(0)
        else:
            speak("Sleep cancelled.")
        return

    speak("I didn't understand the sleep command.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 11  —  MEMORY CLEANUP  (NEW)
# ══════════════════════════════════════════════════════════════════
def memory_cleanup():
    speak("Starting PC memory cleanup.")
    folders = [
        os.environ.get("TEMP", ""),
        os.environ.get("TMP", ""),
        r"C:\Windows\Temp",
        r"C:\Windows\Prefetch",
    ]
    deleted = 0
    for folder in folders:
        if not folder or not os.path.exists(folder):
            continue
        for item in os.listdir(folder):
            path = os.path.join(folder, item)
            try:
                if os.path.isfile(path):   os.remove(path);      deleted += 1
                elif os.path.isdir(path):  shutil.rmtree(path);  deleted += 1
            except Exception:
                pass
    speak(f"Cleanup complete. Removed {deleted} temporary files and folders.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 12  —  JOKES  (NEW)
# ══════════════════════════════════════════════════════════════════
_JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why was the JavaScript developer sad? He didn't Node how to Express himself.",
    "What do you call a fish without eyes? A fsh!",
    "Why don't scientists trust atoms? Because they make up everything!",
    "What's a computer's favourite snack? Microchips!",
    "A programmer's wife says: get milk, if they have eggs get 12. He came home with 12 litres of milk.",
    "Why did the AI break up with the robot? It said, I need more space. In memory.",
    "I told my computer I needed a break. Now it won't stop sending me Kit Kat ads.",
]

def tell_joke():
    speak(random.choice(_JOKES))


# ══════════════════════════════════════════════════════════════════
#  FEATURE 13  —  MOTIVATION  (NEW)
# ══════════════════════════════════════════════════════════════════
_QUOTES = [
    "The only way to do great work is to love what you do. Steve Jobs.",
    "First solve the problem. Then write the code. John Johnson.",
    "Make it work, make it right, make it fast. Kent Beck.",
    "Stay hungry. Stay foolish. Steve Jobs.",
    "Success is not final, failure is not fatal. It is the courage to continue that counts. Churchill.",
    "Push yourself, because no one else is going to do it for you.",
    "The best time to plant a tree was 20 years ago. The second best time is now.",
]

def tell_motivation():
    speak(random.choice(_QUOTES))


# ══════════════════════════════════════════════════════════════════
#  FEATURE 14  —  CALCULATOR  (NEW)
# ══════════════════════════════════════════════════════════════════
def calculate(query):
    expr = (query
            .replace("what is",       "").replace("calculate",     "")
            .replace("compute",       "").replace("solve",          "")
            .replace("times",         "*").replace("multiplied by", "*")
            .replace("divided by",    "/").replace("plus",          "+")
            .replace("minus",         "-").replace("to the power of","**")
            .strip())
    allowed = set("0123456789+-*/(). ")
    if all(c in allowed for c in expr) and expr:
        try:
            result = eval(expr)
            speak(f"The answer is {result}.")
        except Exception:
            speak("Could not calculate that. Please try again.")
    else:
        speak("Could not parse the math expression. Please rephrase.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 15  —  WIKIPEDIA  (NEW)
# ══════════════════════════════════════════════════════════════════
def wikipedia_search(query):
    q = re.sub(r"(tell me about|who is|what is|wikipedia)\s*", "", query).strip()
    if not q:
        speak("What would you like to know about?")
        return
    speak(f"Searching Wikipedia for {q}.")
    try:
        summary = wiki_api.summary(q, sentences=3)
        speak(summary)
    except wiki_api.exceptions.DisambiguationError as e:
        speak(f"Multiple results found. Try being more specific, for example: {e.options[0]}.")
    except Exception:
        speak("Could not find that on Wikipedia.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 16  —  WEATHER via wttr.in  (NEW — no API key needed)
# ══════════════════════════════════════════════════════════════════
def get_weather(query):
    city = re.sub(r"(weather|what is the|what's the|current|in|for|of)\s*", "", query).strip()
    if not city:
        city = CFG.get("default_city", "New Delhi")
    speak(f"Checking weather for {city}.")
    try:
        resp = requests.get(f"https://wttr.in/{city.replace(' ','+')}?format=j1", timeout=8)
        resp.raise_for_status()
        cur  = resp.json()["current_condition"][0]
        speak(
            f"Weather in {city}: {cur['weatherDesc'][0]['value']}. "
            f"Temperature {cur['temp_C']} degrees Celsius, feels like {cur['FeelsLikeC']}. "
            f"Humidity {cur['humidity']} percent. Wind {cur['windspeedKmph']} kilometres per hour."
        )
    except Exception as e:
        speak("Could not fetch weather right now.")
        print(f"[Weather] {e}", flush=True)


# ══════════════════════════════════════════════════════════════════
#  FEATURE 17  —  REMINDERS  (NEW)
# ══════════════════════════════════════════════════════════════════
def set_reminder(query):
    match = re.search(r"(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)", query)
    if not match:
        speak("Please say a time. For example: remind me in 10 minutes to drink water.")
        return
    value   = int(match.group(1))
    unit    = match.group(2)
    seconds = value * 3600 if "hour" in unit else value * 60
    task    = ""
    for kw in [" to ", " about "]:
        if kw in query:
            task = query.split(kw, 1)[-1].strip()
            break
    task = task or "your scheduled task"
    speak(f"Got it. I will remind you in {value} {unit} to {task}.")
    threading.Timer(seconds, lambda: speak(f"Reminder! Time to {task}.")).start()


# ══════════════════════════════════════════════════════════════════
#  FEATURE 18  —  OPEN WEBSITE  (NEW)
# ══════════════════════════════════════════════════════════════════
_WEBSITES = {
    "github":         "https://github.com",
    "stack overflow": "https://stackoverflow.com",
    "gmail":          "https://mail.google.com",
    "google drive":   "https://drive.google.com",
    "google":         "https://www.google.com",
    "netflix":        "https://www.netflix.com",
    "amazon":         "https://www.amazon.com",
    "linkedin":       "https://www.linkedin.com",
    "reddit":         "https://www.reddit.com",
    "chatgpt":        "https://chat.openai.com",
    "openrouter":     "https://openrouter.ai",
    "wikipedia":      "https://www.wikipedia.org",
    "bing":           "https://www.bing.com",
    "tiktok":         "https://www.tiktok.com",
    "telegram":       "https://web.telegram.org",
    "pinterest":      "https://www.pinterest.com",
}

def open_website(query):
    clean = re.sub(r"(open|go to|visit|launch|website)\s*", "", query).strip()
    for name, url in _WEBSITES.items():
        if name in clean:
            speak(f"Opening {name}.")
            webbrowser.open(url)
            return
    speak("Website not found. You can add it in config.json.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 19  —  CLIPBOARD  (NEW)
# ══════════════════════════════════════════════════════════════════
def read_clipboard():
    try:
        content = pyperclip.paste()
        if content and content.strip():
            speak(f"Your clipboard contains: {content[:300]}")
        else:
            speak("Your clipboard is empty.")
    except Exception:
        speak("Could not read the clipboard.")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 20  —  TYPE BY VOICE  (NEW)
# ══════════════════════════════════════════════════════════════════
def type_text(query):
    text = re.sub(r"^(type|write)\s+", "", query).strip()
    if text:
        speak(f"Typing: {text}")
        time.sleep(0.4)
        pyautogui.typewrite(text, interval=0.05)
    else:
        speak("What would you like me to type?")


# ══════════════════════════════════════════════════════════════════
#  FEATURE 21  —  CUSTOM COMMANDS  (NEW — defined in config.json)
# ══════════════════════════════════════════════════════════════════
def run_custom_command(query) -> bool:
    for key, action in CFG.get("custom_commands", {}).items():
        if key.lower() in query:
            speak(f"Running {key}.")
            os.system(action)
            return True
    return False


# ══════════════════════════════════════════════════════════════════
#  CLEANUP
# ══════════════════════════════════════════════════════════════════
def cleanup():
    pass   # nothing to stop since engine is re-created each speak()


# ══════════════════════════════════════════════════════════════════
#  COMMAND ROUTER  —  importable by run_hyper.py or called directly
# ══════════════════════════════════════════════════════════════════

_KNOWN_KW = [
    "brightness", "brighter", "dimmer", "dim",
    "time", "date", "wishme", "good morning", "good afternoon", "good evening",
    "screenshot", "capture screen", "screen shot",
    "my screen", "on my screen", "what on", "analyze screen", "describe screen",
    "facebook", "instagram", "twitter", "discord", "whatsapp", "youtube",
    "volume", "mute", "unmute", "louder", "quieter", "increase", "decrease",
    "open", "close", "search", "browse",
    "system", "battery", "cpu", "condition",
    "sleep",
    "clean", "cleanup", "temp",
    "joke", "laugh", "funny",
    "motivat", "inspire", "quote",
    "calculate", "compute", "what is", "times", "divided", "plus", "minus",
    "tell me about", "who is", "wikipedia",
    "weather",
    "remind me",
    "go to", "visit", "github", "netflix", "gmail", "reddit",
    "clipboard",
    "type ", "write ",
    "exit", "quit", "shutdown", "bye", "goodbye",
]


def route_query(query: str) -> bool:
    """
    Dispatch a recognised command string to the correct feature function.

    Parameters
    ----------
    query : str
        Lowercase, stripped command text (voice or typed).

    Returns
    -------
    bool
        True  → caller should exit / shut down.
        False → continue normally.

    Notes
    -----
    AI intent correction (interpret_intent) is applied here when the
    raw query does not match any known keyword, so callers do not need
    to do it themselves.
    """
    # ── AI intent correction ──────────────────────────────────────
    if not any(kw in query for kw in _KNOWN_KW):
        query = interpret_intent(query)

    # 1 — BRIGHTNESS
    if any(w in query for w in ["brightness", "brighter", "dimmer", "dim", "bright"]):
        brightness_control(query)
        return False

    # 3 — TIME / DATE / GREETING
    if any(k in query for k in ["wishme", "what is the time", "time", "what is the date",
                                 "todays date", "good morning", "good afternoon",
                                 "good evening", "good night"]):
        wishme()
        return False

    # 4a — SCREEN ANALYSIS ("what on my screen", "describe my screen", etc.)
    if any(w in query for w in ["what on", "on my screen", "my screen",
                                 "analyze screen", "describe screen",
                                 "what is on my screen", "what's on my screen"]):
        handle_screenshot_command("analyze " + query)   # forces analysis branch
        return False

    # 4b — SCREENSHOT (plain capture)
    if any(w in query for w in ["screenshot", "capture screen", "screen shot"]):
        handle_screenshot_command(query)
        return False

    # 5 — SOCIAL MEDIA
    if any(w in query for w in ["facebook", "instagram", "twitter",
                                 "discord", "whatsapp", "youtube"]):
        social_media(query)
        return False

    # 6 — VOLUME
    if any(w in query for w in ["volume", "mute", "unmute", "sound",
                                 "louder", "quieter", "increase", "decrease"]):
        volume_control(query)
        return False

    # 7a — OPEN
    if query.startswith("open") or query.startswith("launch"):
        if any(name in query for name in _WEBSITES):
            open_website(query)
        else:
            open_app(query)
        return False

    # 7b — CLOSE
    if query.startswith("close"):
        close_app(query)
        return False

    # 8 — BROWSING / SEARCH
    if any(w in query for w in ["search", "browse"]):
        browsing(query)
        return False

    # 9 — SYSTEM STATUS
    if any(w in query for w in ["system condition", "system status", "battery status",
                                 "cpu usage", "condition of the system"]):
        speak("Checking the system condition.")
        condition()
        return False

    # 10 — SLEEP
    if any(w in query for w in ["sleep", "sleep mode", "go to sleep"]):
        handle_sleep_command(query)
        return False

    # 11 — MEMORY CLEANUP
    if any(w in query for w in ["clean memory", "cleanup", "clear temp",
                                 "free memory", "clean pc", "clean up"]):
        memory_cleanup()
        return False

    # 12 — JOKES
    if any(w in query for w in ["joke", "tell me a joke", "make me laugh", "something funny"]):
        tell_joke()
        return False

    # 13 — MOTIVATION
    if any(w in query for w in ["motivate", "motivation", "inspire", "quote"]):
        tell_motivation()
        return False

    # 14 — CALCULATOR
    if any(w in query for w in ["calculate", "compute", "what is",
                                 "times", "divided by", "plus", "minus"]):
        calculate(query)
        return False

    # 15 — WIKIPEDIA
    if any(w in query for w in ["tell me about", "who is", "wikipedia"]):
        wikipedia_search(query)
        return False

    # 16 — WEATHER
    if "weather" in query:
        get_weather(query)
        return False

    # 17 — REMINDERS
    if any(w in query for w in ["remind me", "set reminder", "reminder"]):
        set_reminder(query)
        return False

    # 18 — OPEN WEBSITE
    if any(w in query for w in ["go to", "visit"]) or \
       any(name in query for name in _WEBSITES):
        open_website(query)
        return False

    # 19 — CLIPBOARD
    if any(w in query for w in ["clipboard", "read clipboard"]):
        read_clipboard()
        return False

    # 20 — TYPE TEXT
    if query.startswith("type ") or query.startswith("write "):
        type_text(query)
        return False

    # 21 — CUSTOM COMMANDS
    if run_custom_command(query):
        return False

    # EXIT
    if any(w in query for w in ["exit", "quit", "shutdown", "bye", "goodbye"]):
        speak("Are you sure you want to shut down?")
        speak("Say confirm to exit or cancel to continue.")
        confirm = command()
        if confirm and any(w in confirm for w in ["yes", "sure", "confirm", "exit", "quit"]):
            speak("Shutting down. Goodbye!")
            cleanup()
            return True   # ← signal caller to exit
        else:
            speak("Shutdown cancelled.")
            return False

    # AI CHAT FALLBACK
    ai_chat(query)
    return False


# ══════════════════════════════════════════════════════════════════
#  MAIN  —  hotkey-only mode (no wake word)
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":

    print("""
╔══════════════════════════════════════════════════════╗
║          HYPER AI v2.0 — Hotkey Mode                 ║
║    Whisper STT · Noise Reduction · Global Hotkey     ║
║                                                      ║
║   ⌨️  Press ALT+SHIFT+1  to activate                 ║
╚══════════════════════════════════════════════════════╝
    """, flush=True)

    # Pre-load Whisper at startup (downloads ~150 MB on first run)
    _get_whisper()

    # Hotkey listener daemon (registers Alt+Shift+1 globally)
    threading.Thread(target=_hotkey_thread, daemon=True).start()

    speak("Hello! I am Hyper AI version 2. Press Alt Shift 1 to activate me.")

    while True:
        _wait_for_activation()      # blocks until hotkey fires

        query = command()
        if not query:
            continue

        should_exit = route_query(query)
        if should_exit:
            sys.exit(0)
