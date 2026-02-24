# HYPER AI v2.0 — Practical Guide

> **Everything you need to set up, configure, and extend Hyper AI.**
> Start here before reading anything else.

---

## Table of Contents

1. [Folder Structure](#1-folder-structure)
2. [How to Run](#2-how-to-run)
3. [Where to Add the API Key](#3-where-to-add-the-api-key)
4. [config.json — All Options Explained](#4-configjson--all-options-explained)
5. [File Map — What Each File Does](#5-file-map--what-each-file-does)
6. [Function Map — Where Every Feature Lives](#6-function-map--where-every-feature-lives)
7. [How to Add a New Feature](#7-how-to-add-a-new-feature)
8. [Activation Methods](#8-activation-methods)
9. [Dependencies](#9-dependencies)
10. [Common Errors and Fixes](#10-common-errors-and-fixes)

---

## 1. Folder Structure

```
your_folder/
│
├── hyper_ai.py          ← Core engine: all features + routing
├── hyper_gui.py         ← GUI window (tkinter)
├── run_hyper.py         ← Launcher: connects GUI to engine
│
├── config.json          ← YOUR SETTINGS (API key goes here)
│
└── assets/              ← Optional
    └── icon.ico         ← Window & tray icon (optional)
```

All three Python files **must be in the same folder**. `config.json` must also be in the same folder as `hyper_ai.py`.

---

## 2. How to Run

```bash
# Always run this file — never run hyper_ai.py directly
python run_hyper.py
```

The GUI window will appear. The terminal will show debug output (Whisper loading, hotkey registration, errors).

---

## 3. Where to Add the API Key

### Step 1 — Create config.json

Create a file called `config.json` in the **same folder** as `hyper_ai.py`. Copy this template:

```json
{
    "openrouter_api_key": "YOUR_KEY_HERE",
    "whisper_model": "base.en",
    "hotkey": "alt+shift+1",
    "default_city": "New Delhi",
    "custom_commands": {}
}
```

### Step 2 — Get your OpenRouter API key

1. Go to [https://openrouter.ai](https://openrouter.ai)
2. Sign up / log in
3. Go to **Keys** in the top menu
4. Click **Create Key**
5. Copy the key (starts with `sk-or-...`)

### Step 3 — Paste it in config.json

```json
{
    "openrouter_api_key": "sk-or-v1-xxxxxxxxxxxxxxxxxxxx",
    ...
}
```

### What needs the API key?

| Feature | Needs API key? |
|---|---|
| Voice commands (brightness, volume, apps, etc.) | ❌ No |
| Wikipedia, Weather | ❌ No |
| Jokes, Motivation, Calculator | ❌ No |
| **AI Chat fallback** (general conversation) | ✅ Yes |
| **Screen analysis** ("what on my screen") | ✅ Yes |
| **Intent correction** (garbled speech) | ✅ Yes |

If no API key is set, only the rule-based features work. The assistant will say *"Please add your OpenRouter API key"* any time it needs the AI.

---

## 4. config.json — All Options Explained

```json
{
    "openrouter_api_key": "sk-or-...",
    
    "whisper_model": "base.en",
    
    "hotkey": "alt+shift+1",
    
    "default_city": "New Delhi",
    
    "wake_threshold": 0.5,
    
    "custom_commands": {
        "open my project": "code C:\\Users\\You\\projects\\myapp",
        "run tests":       "cd C:\\projects\\myapp && python -m pytest"
    }
}
```

| Key | Default | What it does |
|---|---|---|
| `openrouter_api_key` | `""` | Your OpenRouter key for AI chat + screen analysis |
| `whisper_model` | `"base.en"` | Whisper model size: `tiny.en` (fast), `base.en` (balanced), `small.en` (accurate) |
| `hotkey` | `"alt+shift+1"` | Global keyboard shortcut to activate listening |
| `default_city` | `"New Delhi"` | Fallback city when you say "weather" with no city name |
| `wake_threshold` | `0.5` | Reserved for future use |
| `custom_commands` | `{}` | Your own voice commands → shell commands (see below) |

### Custom Commands Example

```json
"custom_commands": {
    "open my work":   "code C:\\Users\\You\\work",
    "start server":   "cd C:\\myapp && python manage.py runserver",
    "git status":     "cmd /c git status"
}
```

Say *"open my work"* and Hyper AI runs the associated shell command.

---

## 5. File Map — What Each File Does

### `hyper_ai.py` — The Engine

This is the brain. Contains every feature function, the audio pipeline, and the command router. You **never run this file directly**. Import it.

**Top-level sections in order:**

| Lines (approx) | Section | Purpose |
|---|---|---|
| 1–13 | Module docstring | Version info |
| 15–45 | Standard imports | datetime, threading, os, etc. |
| 37–73 | ML/audio imports | Whisper, noisereduce, webrtcvad |
| 76–91 | Config loader | Reads `config.json` into `CFG` dict |
| 93–118 | Whisper model | Lazy-loads the STT model on first use |
| 120–170 | Audio utilities | Noise reduction, VAD, WAV conversion |
| 176–208 | TTS (`speak`) | Text-to-speech via pyttsx3 |
| 213–374 | `command()` | Records mic → Whisper transcription |
| 376–394 | Activation globals | `_WAKE_EVENT`, `_MIC_BUSY` |
| 396–410 | `_wait_for_activation()` | Blocks until hotkey/mic button fires |
| 412–430 | `_hotkey_thread()` | Registers Alt+Shift+1 globally |
| 432–530 | OpenRouter AI | `_or_call()`, `interpret_intent()`, `ai_chat()` |
| 532+ | Features 1–21 | All command functions |
| ~1115 | `_KNOWN_KW` | Keyword list for intent detection |
| ~1142 | `route_query()` | Central command dispatcher |
| ~1290 | `__main__` | Hotkey-only mode (no GUI) |

### `hyper_gui.py` — The Window

The `HyperGUI` class. Pure tkinter. Has no knowledge of hyper_ai.py at all — it only accepts method calls from the pipeline.

**Public methods you can call from outside:**

| Method | What it does |
|---|---|
| `gui.build()` | Creates all widgets. Must be called from main thread. |
| `gui.run()` | Starts tkinter mainloop. Blocks. |
| `gui.update_state(state)` | Changes the animated circle. States: `sleeping`, `listening`, `processing`, `speaking`, `error` |
| `gui.add_message(text, tag)` | Appends a line to the conversation log. Tags: `user`, `hyper`, `system`, `error` |
| `gui.set_amplitude(0.0–1.0)` | Feeds mic amplitude to the waveform bars |

### `run_hyper.py` — The Launcher

The glue layer. Contains `HyperPipeline` which:
- Monkey-patches `hyper_ai.speak()` so every spoken response also appears in the GUI log
- Monkey-patches `hyper_ai.command()` so the GUI shows "Listening..." while recording
- Runs the AI loop in a background thread
- Handles typed commands from the GUI text box
- Handles mic button clicks

---

## 6. Function Map — Where Every Feature Lives

All feature functions are in `hyper_ai.py`. Find them by searching for the feature number comment.

| Feature # | Voice trigger examples | Function name | Line (approx) |
|---|---|---|---|
| 1 | "brightness up", "dim screen", "set brightness to 50" | `brightness_control(query)` | ~532 |
| 2 | *(Bing rewards — unused)* | `bing_search()` | ~554 |
| 3 | "what time is it", "good morning", "today's date" | `wishme()`, `cal_day()` | ~585 |
| 4 | "take a screenshot", "what's on my screen" | `take_screenshot()`, `analyze_screenshot()`, `handle_screenshot_command()` | ~604 |
| 5 | "open youtube", "open facebook" | `social_media(query)` | ~680 |
| 6 | "volume up", "mute", "louder" | `volume_control(query)` | ~700 |
| 7 | "open chrome", "close notepad", "launch spotify" | `open_app(query)`, `close_app(query)` | ~729 |
| 8 | "search python tutorial", "browse cats" | `browsing(query)` | ~793 |
| 9 | "system condition", "cpu usage", "battery status" | `condition()` | ~808 |
| 10 | "sleep in 30 minutes", "sleep mode", "cancel sleep" | `go_to_sleep()`, `cancel_sleep()`, `handle_sleep_command()` | ~837 |
| 11 | "clean memory", "cleanup", "clear temp" | `memory_cleanup()` | ~897 |
| 12 | "tell me a joke", "make me laugh" | `tell_joke()` | ~933 |
| 13 | "motivate me", "give me a quote" | `tell_motivation()` | ~950 |
| 14 | "what is 45 times 12", "calculate 100 divided by 4" | `calculate(query)` | ~957 |
| 15 | "tell me about Einstein", "who is Elon Musk" | `wikipedia_search(query)` | ~979 |
| 16 | "weather in Mumbai", "weather" | `get_weather(query)` | ~997 |
| 17 | "remind me in 10 minutes to drink water" | `set_reminder(query)` | ~1019 |
| 18 | "open github", "go to netflix", "visit gmail" | `open_website(query)` | ~1059 |
| 19 | "read clipboard", "what's in my clipboard" | `read_clipboard()` | ~1072 |
| 20 | "type hello world", "write my email" | `type_text(query)` | ~1086 |
| 21 | *(custom — defined in config.json)* | `run_custom_command(query)` | ~1099 |
| — | *(anything else)* | `ai_chat(query)` | ~519 |

**AI utility functions** (not features, internal use):

| Function | Purpose |
|---|---|
| `_or_call(messages, vision)` | Raw OpenRouter API call |
| `interpret_intent(raw_query)` | Fixes garbled/unclear speech |
| `ai_chat(query)` | General conversation fallback |

---

## 7. How to Add a New Feature

Adding a feature requires **exactly 3 edits** to `hyper_ai.py`. No other file needs to change.

### Step 1 — Write the function

Add it anywhere before `route_query()`. Follow the pattern:

```python
# ══════════════════════════════════════════════════════════════════
#  FEATURE 22  —  YOUR FEATURE NAME
# ══════════════════════════════════════════════════════════════════
def your_feature(query):
    # query is already lowercase and stripped
    speak("Doing your thing.")
    # ... your logic here
```

### Step 2 — Add keywords to `_KNOWN_KW`

This list tells Hyper AI NOT to send the query to AI intent correction when your keyword is present. If your keyword is missing here, garbled speech will go to OpenRouter first (wasting an API call).

```python
_KNOWN_KW = [
    ...
    "your keyword", "another trigger word",   # ← add here
    ...
]
```

### Step 3 — Add a route in `route_query()`

Add your `if` block before the `# AI CHAT FALLBACK` line at the bottom:

```python
# 22 — YOUR FEATURE
if any(w in query for w in ["your keyword", "another trigger word"]):
    your_feature(query)
    return False
```

That's it. The GUI, logging, state changes, and mic handling are all automatic.

---

## 8. Activation Methods

There is no wake word. You activate Hyper AI in three ways:

| Method | How |
|---|---|
| **Keyboard hotkey** | Press `Alt+Shift+1` (configurable in config.json) |
| **Mic button** | Click the 🎤 button in the GUI |
| **Typed command** | Type in the text box and press Enter (no mic used) |

After activation via hotkey or mic button, Hyper AI records your voice for up to 10 seconds, then processes what you said.

---

## 9. Dependencies

Install all at once:

```bash
pip install pyttsx3 SpeechRecognition pyautogui psutil screen-brightness-control pyperclip wikipedia requests numpy sounddevice keyboard faster-whisper noisereduce webrtcvad
```

Optional (for system tray icon):
```bash
pip install pystray pillow
```

| Library | Used for |
|---|---|
| `pyttsx3` | Text-to-speech (offline) |
| `SpeechRecognition` | Google STT fallback only |
| `faster-whisper` | Primary speech-to-text (offline, accurate) |
| `noisereduce` | Removes background noise before transcription |
| `webrtcvad` | Detects whether audio contains speech |
| `sounddevice` | Raw microphone recording |
| `keyboard` | Global hotkey registration |
| `pyautogui` | Volume keys, screenshot, typing simulation |
| `psutil` | CPU, RAM, battery readings |
| `screen-brightness-control` | Brightness control |
| `pyperclip` | Clipboard read |
| `wikipedia` | Wikipedia searches |
| `requests` | OpenRouter API, weather from wttr.in |
| `numpy` | Audio array processing |

---

## 10. Common Errors and Fixes

| Error message | Cause | Fix |
|---|---|---|
| "Please add your OpenRouter API key" | config.json missing or key not set | Create config.json with your key (see Section 3) |
| No GUI appears, only terminal output | run_hyper.py crashed before `gui.build()` | Check terminal for the actual error — usually a missing import |
| "[Hotkey] Could not register hotkey" | Not running as Administrator | Right-click → Run as Administrator, OR change hotkey in config.json |
| "I didn't hear anything." | Mic too quiet or wrong device | Check Windows mic settings, or increase mic sensitivity |
| Whisper downloading at startup | First run — model not yet downloaded | Wait for download (~150 MB for base.en). Only happens once. |
| "Application not recognized." | App name not in APPS dict | Add it to the `APPS` dict in hyper_ai.py (Feature 7 section) |
| "Website not found." | Site not in _WEBSITES dict | Add it to the `_WEBSITES` dict (Feature 18 section) |
