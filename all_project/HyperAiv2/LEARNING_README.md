# HYPER AI v2.0 — Learning Guide

> **How the code actually works, end to end.**
> Read this to understand every step from startup to completed task — so you can build diagrams, debug anything, and add new features confidently.

---

## Table of Contents

1. [The Big Picture — Three Layers](#1-the-big-picture--three-layers)
2. [Startup Flow — What Happens When You Run](#2-startup-flow--what-happens-when-you-run)
3. [Activation Flow — How a Command Begins](#3-activation-flow--how-a-command-begins)
4. [Voice Pipeline — Audio to Text](#4-voice-pipeline--audio-to-text)
5. [Routing Flow — Text to Action](#5-routing-flow--text-to-action)
6. [Every Feature — Internal Step-by-Step](#6-every-feature--internal-step-by-step)
7. [GUI State Machine — What the Animations Mean](#7-gui-state-machine--what-the-animations-mean)
8. [The Monkey-Patch — How GUI Connects to Engine](#8-the-monkey-patch--how-gui-connects-to-engine)
9. [Threading Model — What Runs Where](#9-threading-model--what-runs-where)
10. [The Config System — How Settings Flow Through Code](#10-the-config-system--how-settings-flow-through-code)
11. [Error Handling Philosophy](#11-error-handling-philosophy)
12. [Diagram Prompts — Draw These Yourself](#12-diagram-prompts--draw-these-yourself)

---

## 1. The Big Picture — Three Layers

Hyper AI has three separate layers that talk to each other. Understanding the boundary between them is the most important thing.

```
┌─────────────────────────────────────────────────────┐
│                   run_hyper.py                       │
│            HyperPipeline (the glue)                  │
│  ┌───────────────────┐    ┌───────────────────────┐  │
│  │    hyper_gui.py   │    │     hyper_ai.py        │  │
│  │    HyperGUI       │◄───│  features + routing    │  │
│  │    (the window)   │    │  (the brain)           │  │
│  └───────────────────┘    └───────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Layer 1 — hyper_ai.py (the brain):**
Knows nothing about any GUI. Just functions. Takes audio input, produces text output via `speak()`. Has no `import tkinter` anywhere.

**Layer 2 — hyper_gui.py (the window):**
Knows nothing about hyper_ai.py. Just a tkinter window. Calls `pipeline.trigger_manually()` when mic is clicked. Calls `pipeline.process_text_command()` when Enter is pressed. That's it.

**Layer 3 — run_hyper.py (the glue):**
Knows both. Imports both. Connects them. Patches `hyper_ai.speak` so GUI gets notified of every response. Runs hyper_ai's loop in a background thread. Runs the GUI on the main thread.

**Why this separation matters:** You can run `hyper_ai.py` alone (no GUI) and it works fine via terminal. You can swap out `hyper_gui.py` for a web interface and only change `run_hyper.py`. The brain doesn't care what displays its output.

---

## 2. Startup Flow — What Happens When You Run

```
python run_hyper.py
│
├── Python imports hyper_ai
│   ├── All imports run (pyttsx3, numpy, etc.)
│   ├── _load_cfg() reads config.json into CFG dict
│   ├── _WHISPER_SIZE = CFG.get("whisper_model", "base.en")
│   ├── _WAKE_EVENT = threading.Event()   ← starts cleared (not set)
│   └── _MIC_BUSY  = threading.Event()   ← starts cleared
│
├── Python imports HyperGUI from hyper_gui
│   └── Class is defined, no window yet
│
├── gui = HyperGUI() created
│   └── All instance variables set to None / defaults
│
├── pipeline = HyperPipeline(gui) created
│   └── Saves references to original speak() and command()
│
├── gui.pipeline = pipeline   ← GUI can now call pipeline methods
│
├── gui.build()   ← MAIN THREAD — creates all tkinter widgets
│   ├── Creates root window, sets title, size, background
│   ├── Builds header, canvas, status label, waveform, log, input, info bar
│   ├── Starts _animate_status() loop (fires every 50ms via root.after)
│   ├── Starts _animate_waveform() loop (fires every 80ms)
│   ├── Starts _update_info_bar() loop (fires every 2000ms)
│   ├── Tries to start system tray icon (fails silently if no pystray)
│   └── Writes "Hyper: Ready! Press Alt+Shift+1..." to conversation log
│
├── pipeline.start()
│   ├── _install_patches()
│   │   ├── hyper_ai.speak   = speak_wrapper    ← PATCHED
│   │   └── hyper_ai.command = command_wrapper  ← PATCHED
│   └── Launches _ai_loop() in a daemon Thread
│       ├── Prints banner to terminal
│       ├── _get_whisper() — loads/downloads Whisper model
│       │   ├── If already loaded: returns cached model instantly
│       │   └── If first time: downloads ~150MB, loads into RAM
│       ├── Launches _hotkey_thread() as daemon
│       │   └── keyboard.add_hotkey("alt+shift+1", _on_hotkey)
│       │       └── keyboard.wait() blocks this thread forever
│       └── hyper_ai.speak("Hello! I am Hyper AI...")
│           └── This calls speak_wrapper (patched)
│               ├── gui.update_state("speaking")  → orange animation
│               ├── gui.add_message("Hyper: Hello!...")  → log
│               ├── original speak() → pyttsx3 speaks aloud
│               └── gui.update_state("sleeping")  → grey animation
│
└── gui.run()   ← MAIN THREAD BLOCKS HERE
    └── tkinter mainloop() — processes all GUI events forever
        until window is closed
```

---

## 3. Activation Flow — How a Command Begins

There are two activation paths. Both end at the same place.

### Path A — Keyboard Hotkey (Alt+Shift+1)

```
User presses Alt+Shift+1
│
├── OS sends key event to keyboard library
├── _hotkey_thread (running on its own thread) catches it
├── _on_hotkey() is called
│   └── hyper_ai._WAKE_EVENT.set()   ← EVENT IS NOW SET
│
└── _ai_loop (blocked at _wait_for_activation()) unblocks
    └── _WAKE_EVENT.wait() returns immediately when event is set
```

### Path B — Mic Button Click

```
User clicks 🎤 button in GUI
│
├── tkinter calls mic_btn's command → gui._on_mic_click()
├── gui._on_mic_click() calls pipeline.trigger_manually()
├── trigger_manually() calls hyper_ai._WAKE_EVENT.set()
│
└── Same as above — _ai_loop unblocks
```

### Path C — Typed Command (skips voice entirely)

```
User types "open youtube" in text box, presses Enter
│
├── tkinter calls gui._on_input_submit()
├── gui.add_message("You: open youtube", "user")  → log
├── gui._input_entry is cleared
└── threading.Thread(target=pipeline.process_text_command,
                     args=("open youtube",)).start()
    │
    └── process_text_command("open youtube")
        ├── gui.update_state("processing")
        ├── hyper_ai.route_query("open youtube")  ← ROUTES DIRECTLY
        └── gui.update_state("sleeping")
```

Path C never touches the microphone or `_WAKE_EVENT` at all.

---

## 4. Voice Pipeline — Audio to Text

This is the most complex part of the system. Runs inside `command()` in hyper_ai.py.

```
command() is called
│
├── _MIC_BUSY.set()   ← blocks _hotkey_thread from re-triggering
│
├── _get_whisper()    ← get cached model (already loaded at startup)
│
├── WHISPER PATH (if faster-whisper installed):
│   │
│   ├── ATTEMPT 1:
│   │   ├── sd.rec(10 seconds, 16000Hz, mono, float32)
│   │   │   └── sounddevice records raw audio into numpy array
│   │   ├── sd.wait()   ← blocks until recording finishes
│   │   ├── audio_np.flatten()   ← 2D array → 1D
│   │   │
│   │   ├── ENERGY CHECK:
│   │   │   ├── energy = np.abs(audio_np)   ← magnitude of each sample
│   │   │   ├── threshold = mean(energy) * 0.5
│   │   │   └── if all silence → retry or return None
│   │   │
│   │   ├── TRIM SILENCE:
│   │   │   ├── nonsilent = indices where energy > threshold
│   │   │   └── cut array at last non-silent + 0.3s padding
│   │   │
│   │   ├── NOISE REDUCTION (noisereduce):
│   │   │   └── nr.reduce_noise(audio, stationary=False, prop_decrease=0.75)
│   │   │       removes background hiss/hum, keeps speech natural
│   │   │
│   │   ├── VAD CHECK (webrtcvad):
│   │   │   ├── Split audio into 30ms chunks
│   │   │   ├── Ask WebRTC: "is this chunk speech?"
│   │   │   └── if < 15% chunks are speech → skip (just noise)
│   │   │
│   │   ├── CONVERT TO WAV:
│   │   │   ├── float32 → int16 (multiply by 32767)
│   │   │   └── write WAV header + PCM data to bytes
│   │   │
│   │   ├── WRITE TEMP FILE:
│   │   │   └── %TEMP%\_hyper_cmd.wav
│   │   │
│   │   ├── WHISPER TRANSCRIPTION:
│   │   │   ├── whisper.transcribe(wav_path, beam_size=5, language="en")
│   │   │   ├── Whisper processes audio on CPU (int8 quantized = 4x faster)
│   │   │   └── Returns list of Segment objects with .text
│   │   │
│   │   ├── JOIN SEGMENTS:
│   │   │   └── " ".join(seg.text for seg in segments).strip()
│   │   │
│   │   └── return query.lower().strip()
│   │
│   └── ATTEMPT 2 (if attempt 1 got nothing): same process, retry once
│
├── GOOGLE STT FALLBACK (if faster-whisper not installed):
│   ├── sr.Recognizer() with energy_threshold=200
│   ├── sr.Microphone() context manager opens mic
│   ├── r.adjust_for_ambient_noise() calibrates for 0.3s
│   ├── r.listen() records until silence detected
│   ├── r.recognize_google(audio, language="en-IN")
│   │   └── sends audio bytes to Google's servers (needs internet)
│   └── Falls back to "en-US" if en-IN fails
│
└── _MIC_BUSY.clear()   ← releases the mic lock
```

**Key insight about Whisper vs Google STT:**
Whisper runs 100% offline on your CPU. Google STT sends audio to Google's servers. Whisper is more accurate for accented English but slower on weak CPUs. Both produce the same output: a lowercase string.

---

## 5. Routing Flow — Text to Action

After `command()` returns a string (e.g. `"open youtube"`), the AI loop calls `route_query()`.

```
route_query("open youtube")
│
├── INTENT CORRECTION CHECK:
│   └── if NOT any(kw in query for kw in _KNOWN_KW):
│       └── "youtube" IS in _KNOWN_KW → skip intent correction
│
├── Check brightness keywords → no match
├── Check time/date keywords  → no match
├── Check screen keywords     → no match
├── Check social media keywords → "youtube" matches!
│   └── social_media("open youtube")
│       ├── loops through sites dict
│       ├── finds "youtube" → url = "https://www.youtube.com"
│       ├── speak("Opening Youtube")
│       └── webbrowser.open(url)  ← opens in default browser
│
└── return False   ← no shutdown needed
```

### What happens with a garbled/unrecognised query?

```
route_query("brit ness up")
│
├── INTENT CORRECTION CHECK:
│   └── "brit" not in _KNOWN_KW, "ness" not in _KNOWN_KW...
│       → NONE match → call interpret_intent("brit ness up")
│           │
│           ├── _or_call([system_prompt, user="brit ness up"])
│           │   └── POST to https://openrouter.ai/api/v1/chat/completions
│           │       model: "openrouter/auto"
│           │       returns: "increase brightness"
│           │
│           └── query is now "increase brightness"
│
├── Check brightness keywords → "brightness" matches!
└── brightness_control("increase brightness")
```

### What if no rule matches at all?

```
route_query("tell me something interesting")
│
├── All rule checks fail — nothing matches
└── ai_chat("tell me something interesting")
    │
    ├── _or_call([system_prompt, user="tell me something interesting"])
    │   └── OpenRouter returns a short response string
    └── speak(response)
```

---

## 6. Every Feature — Internal Step-by-Step

### Feature 1 — Brightness Control

```
User says: "set brightness to 70 percent"
↓
brightness_control("set brightness to 70 percent")
├── sbc.get_brightness()[0]  → gets current brightness (e.g. 50)
├── re.search(r"(\d+)\s*(percent|%)", query) → finds "70"
├── value = max(0, min(100, 70)) = 70   ← clamp to 0-100
├── sbc.set_brightness(70)   → OS call changes screen brightness
└── speak("Brightness set to 70 percent")
```

If no number: checks for "increase"/"decrease" words, adjusts by ±20.

### Feature 3 — Time / Date / Greeting

```
User says: "good morning"
↓
wishme()
├── now = datetime.datetime.now()
├── hour = now.hour  (e.g. 9)
├── 0 ≤ 9 < 12 → greeting_time = "Good Morning"
├── t = "09:30 AM"
├── day = "Monday"
└── speak("Good Morning Boss! It's 09:30 AM on Monday. How can I assist you?")
```

### Feature 4a — Screen Analysis

```
User says: "what on my screen"
↓
route_query detects "what on" → handle_screenshot_command("analyze what on my screen")
│
├── "analyze" is in the query → takes screenshot first
│   ├── pyautogui.screenshot()  → captures full screen as PIL Image
│   ├── saves to ~/Downloads/screenshot_2025-01-01_12-00-00.png
│   └── returns filepath
│
└── analyze_screenshot(filepath)
    ├── open(filepath, "rb") → reads image bytes
    ├── base64.b64encode(bytes) → converts to base64 string
    ├── _or_call(messages, vision=True)
    │   └── POST to OpenRouter with:
    │       model: "meta-llama/llama-4-scout:free"
    │       content: [text prompt, image_url as data:image/png;base64,...]
    │       → returns description of what's visible
    └── speak(result[:580])   ← speaks first 580 chars, full result in terminal
```

### Feature 4b — Plain Screenshot

```
User says: "take a screenshot"
↓
handle_screenshot_command("take a screenshot")
├── No analysis keywords detected
├── No name match in regex
└── take_screenshot()  → saves to Downloads, speaks confirmation
```

### Feature 6 — Volume Control

```
User says: "volume up"
↓
volume_control("volume up")
├── "increase" is in query (from "volume up")
├── speak("Increasing volume")
└── for _ in range(10): pyautogui.press("volumeup")
    └── simulates 10 presses of the volume-up media key
```

No OS audio API. Uses keyboard simulation via pyautogui.

### Feature 7 — Open App

```
User says: "open chrome"
↓
route_query detects "open" → open_app("open chrome")
├── loops through APPS dict
├── "chrome" found → cmds["open"] = "start chrome"
├── speak("Opening Chrome")
└── os.system("start chrome")   ← Windows shell command
```

### Feature 8 — Browsing / Search

```
User says: "search python tutorial"
↓
browsing("search python tutorial")
├── "search" in query
├── speak("What should I search for?")
├── command()  ← records ANOTHER voice input
│   └── user says "python tutorial"
│   └── returns "python tutorial"
├── speak("Searching for python tutorial")
└── webbrowser.open("https://www.google.com/search?q=python tutorial")
```

Note: `browsing()` calls `command()` a second time to get the search term. This is the only feature with two voice turns.

### Feature 9 — System Condition

```
User says: "system condition"
↓
speak("Checking the system condition.")
condition()
├── psutil.cpu_percent(interval=1)  → waits 1s, measures CPU
├── speak("CPU usage is at 34 percent")
├── psutil.virtual_memory()  → RAM stats
├── speak("RAM usage is 67 percent. 10 gigabytes used out of 16...")
├── psutil.sensors_battery()  → battery info (None on desktop)
└── speak("Battery level is at 82 percent. Currently charging.")
    + advice based on battery level
```

### Feature 10 — Sleep Mode

```
User says: "sleep in 30 minutes"
↓
handle_sleep_command("sleep in 30 minutes")
├── re.search(r"(\d+)\s*(minute|...)", query) → finds "30", "minutes"
├── delay = 30  (minutes)
└── go_to_sleep(30)
    ├── speak("Okay, I will put the system to sleep in 30 minutes.")
    └── threading.Timer(30*60, sleep_action).start()
        └── after 1800 seconds:
            ├── speak("Going to sleep now. Goodbye!")
            └── os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
```

### Feature 14 — Calculator

```
User says: "what is 45 times 12"
↓
calculate("what is 45 times 12")
├── str replacements:
│   "what is"  → ""    →  "45 times 12"
│   "times"    → "*"   →  "45 * 12"
├── allowed = "0123456789+-*/(). "
├── all chars in "45 * 12" are allowed → safe to eval
├── result = eval("45 * 12") = 540
└── speak("The answer is 540.")
```

`eval()` is used here. The `allowed` character check prevents code injection.

### Feature 15 — Wikipedia

```
User says: "tell me about Python"
↓
wikipedia_search("tell me about python")
├── re.sub("tell me about|who is|...", "", query) → "python"
├── speak("Searching Wikipedia for python.")
├── wiki_api.summary("python", sentences=3)
│   └── requests Wikipedia's API, returns 3-sentence summary
└── speak(summary)
```

### Feature 16 — Weather

```
User says: "weather in Mumbai"
↓
get_weather("weather in mumbai")
├── re.sub("weather|what is the|...", "", query) → "mumbai"
├── speak("Checking weather for mumbai.")
├── requests.get("https://wttr.in/mumbai?format=j1")
│   └── wttr.in is a free public weather API — no key needed
│   └── returns JSON with current conditions
├── cur = response["current_condition"][0]
└── speak("Weather in mumbai: Partly Cloudy. Temperature 32 degrees Celsius,
          feels like 38. Humidity 72 percent. Wind 14 kilometres per hour.")
```

### Feature 17 — Reminders

```
User says: "remind me in 10 minutes to drink water"
↓
set_reminder("remind me in 10 minutes to drink water")
├── re.search(r"(\d+)\s*(minute|...)", query) → "10", "minutes"
├── seconds = 10 * 60 = 600
├── finds " to " in query → task = "drink water"
├── speak("Got it. I will remind you in 10 minutes to drink water.")
└── threading.Timer(600, lambda: speak("Reminder! Time to drink water.")).start()
    └── non-blocking — returns immediately
    └── after 600 seconds on a separate thread: speaks the reminder
```

### Feature 21 — Custom Commands

```
config.json has: "open my project": "code C:\\projects\\myapp"

User says: "open my project"
↓
run_custom_command("open my project")
├── loops CFG["custom_commands"]
├── "open my project" is in query
├── speak("Running open my project.")
├── os.system("code C:\\projects\\myapp")   ← runs your shell command
└── return True   ← tells route_query this was handled
```

### AI Chat Fallback

```
User says: "what do you think about AI?"
↓
No keyword matches in route_query
↓
ai_chat("what do you think about ai?")
├── messages = [
│     system: "You are Hyper AI, a friendly voice assistant.
│              Reply in 1-2 short spoken sentences. No markdown."
│     user: "what do you think about ai?"
│   ]
├── _or_call(messages)
│   └── POST to OpenRouter → model: "openrouter/auto"
│   └── returns: "AI is a fascinating field that's reshaping the world!"
└── speak("AI is a fascinating field that's reshaping the world!")
```

---

## 7. GUI State Machine — What the Animations Mean

The status circle (`_canvas`) has 5 states. Each has a different animation and colour.

```
          ┌─────────────────────────────────┐
          │                                 │
          ▼                                 │
      SLEEPING ──────► LISTENING ──────► PROCESSING
      (grey dot)      (blue pulse)     (green spinning)
          ▲                                 │
          │                                 ▼
          └────────── SPEAKING ◄────────────┘
                     (orange waves)

      ERROR (red X) — can come from anywhere, not in normal flow
```

**State transitions triggered by:**

| Who triggers | From → To |
|---|---|
| `_ai_loop` at top of loop | any → `sleeping` |
| `_wait_for_activation()` returns | sleeping → (AI loop starts command) |
| patched `command()` starts | sleeping → `listening` |
| patched `command()` returns | listening → `processing` |
| patched `speak()` starts | processing → `speaking` |
| patched `speak()` finishes | speaking → `sleeping` |

**The animation loop** runs via `root.after(50, _animate_status)` — tkinter's timer. This schedules a callback on the main thread every 50ms. The callback redraws the canvas based on `self._state`. This is why state changes must use `root.after(0, lambda: ...)` — so the update happens on the main thread, not the background AI thread.

---

## 8. The Monkey-Patch — How GUI Connects to Engine

This is the most unusual design decision in the codebase. Understand it deeply.

**The problem:** `hyper_ai.py` calls `speak(text)` throughout its code. How do we make the GUI show those messages without putting any GUI code in `hyper_ai.py`?

**The solution:** In Python, module-level names are just dictionary entries. `hyper_ai.speak` is just a key in `hyper_ai`'s namespace. You can replace it.

```python
# In run_hyper.py:

original_speak = hyper_ai.speak   # save the real function

def speak_wrapper(text):
    gui.update_state("speaking")        # tell GUI: now speaking
    gui.add_message(f"Hyper: {text}")   # show text in log
    original_speak(text)                # do the actual TTS
    gui.update_state("sleeping")        # tell GUI: done

hyper_ai.speak = speak_wrapper   # replace the module attribute
```

Now when ANY code in `hyper_ai.py` calls `speak("hello")`, it actually calls `speak_wrapper("hello")`. The engine has no idea. It just calls a name. We replaced what that name points to.

**Important:** The wrapper saves and calls the original. If it didn't, pyttsx3 would never speak. The wrapper adds GUI behaviour around the existing behaviour.

**The same pattern for `command()`:**

```python
def command_wrapper(*args, **kwargs):
    gui.update_state("listening")       # show blue animation
    result = original_command(*args, **kwargs)  # do actual recording
    gui.update_state("processing")      # show green animation
    return result                       # pass result through unchanged
```

`*args, **kwargs` means "accept whatever arguments the caller passes and forward them exactly". This makes the wrapper transparent — callers don't know or care.

---

## 9. Threading Model — What Runs Where

This is critical. tkinter crashes if you touch it from a non-main thread. Audio recording blocks if run on the main thread. Both have to happen simultaneously.

```
MAIN THREAD:
├── gui.build()     → creates all widgets
├── gui.run()       → tkinter mainloop
│   ├── Processes all GUI events (clicks, keypresses)
│   ├── Runs root.after() callbacks (animations, info bar)
│   └── NEVER blocks — must stay responsive
│
└── All GUI updates use root.after(0, lambda: ...) to queue work safely

BACKGROUND THREAD 1 — _ai_loop (daemon):
├── _wait_for_activation()  ← blocks here most of the time (0% CPU)
├── hyper_ai.command()      ← blocks while recording (up to 10s)
├── hyper_ai.route_query()  ← runs feature functions
│   ├── speak()             ← blocks while TTS speaks
│   └── (feature actions)
└── loops back to _wait_for_activation()

BACKGROUND THREAD 2 — _hotkey_thread (daemon):
├── keyboard.add_hotkey(...)
└── keyboard.wait()   ← blocks forever, fires callback on keypress

BACKGROUND THREAD 3+ — threading.Timer for reminders/sleep:
└── fire once after N seconds, call speak(), then die

DAEMON THREADS:
└── All background threads are daemon=True
    → they die automatically when the main thread exits
    → you don't need to manually kill them
```

**Why you must never call tkinter from a background thread:**

tkinter is not thread-safe. If two threads call tkinter at the same time, the GUI crashes with an unpredictable error. The solution is `root.after(0, fn)` — this puts `fn` into tkinter's event queue to be called on the main thread at the next opportunity.

```python
# WRONG — called from background thread, will crash:
self._status_label.configure(text="Listening...")

# CORRECT — queued to run on main thread:
self._root.after(0, lambda: self._status_label.configure(text="Listening..."))
```

---

## 10. The Config System — How Settings Flow Through Code

```
config.json on disk
│
├── hyper_ai._load_cfg()  reads it at import time
└── CFG = { "openrouter_api_key": "...", "whisper_model": "base.en", ... }

CFG is used in:
├── _WHISPER_SIZE = CFG.get("whisper_model", "base.en")
│   └── Passed to WhisperModel() constructor at startup
│
├── _HOTKEY_COMBO = CFG.get("hotkey", "alt+shift+1")
│   └── Passed to keyboard.add_hotkey() in _hotkey_thread
│
├── _or_call() reads CFG.get("openrouter_api_key", "")
│   └── Used as Bearer token in Authorization header
│
├── get_weather() reads CFG.get("default_city", "New Delhi")
│   └── Used when no city name in voice query
│
└── run_custom_command() reads CFG.get("custom_commands", {})
    └── Loops all entries, checks if key is in voice query
```

**If config.json doesn't exist:** `_load_cfg()` returns `{}`. Every `CFG.get(key, default)` returns the default. The program still runs but API-dependent features show the "add API key" message.

**If config.json has invalid JSON:** `json.load()` raises an exception, caught and printed. Same result — `{}` returned, defaults used.

---

## 11. Error Handling Philosophy

The code has three error handling patterns:

**1. Silent fallback (audio/noise reduction):**
```python
def _reduce_noise(audio_np):
    if _HAS_NR:
        try:
            return nr.reduce_noise(...)
        except Exception:
            pass   # ← if it fails, just return unmodified audio
    return audio_np
```
If noise reduction fails, the audio is still usable. Don't crash, just degrade gracefully.

**2. Speak + return (feature functions):**
```python
def brightness_control(query):
    try:
        current = sbc.get_brightness()[0]
    except Exception:
        speak("I cannot control brightness on this device.")
        return   # ← tell the user, stop this feature
```
The user hears what went wrong. The loop continues to the next command.

**3. GUI animation error suppression:**
```python
def _animate_status(self):
    try:
        # all drawing code
        self._root.after(50, self._animate_status)
    except Exception:
        pass   # ← if window is closing, don't crash on missing widget
```
Animation loops run forever. When the window closes, widgets get destroyed. Calling `.after()` on a destroyed widget raises an exception. Catching it silently lets the loop stop gracefully.

---

## 12. Diagram Prompts — Draw These Yourself

Draw each of these as a flowchart or sequence diagram. This will lock the understanding in.

**Diagram 1 — Startup Sequence**
Show: `run_hyper.py → imports → gui.build() → pipeline.start() → gui.run()`
Include: what runs on main thread vs background thread. Mark the point where main thread blocks.

**Diagram 2 — Voice Command Lifecycle**
Show: user speaks → activation → recording → noise reduction → VAD → Whisper → routing → feature → speak → back to sleeping
Include: all the state changes in the GUI circle.

**Diagram 3 — Monkey-Patch Call Chain**
Show: `route_query calls speak("hello")` → this is now `speak_wrapper` → gui.update_state("speaking") → gui.add_message → `original_speak("hello")` → pyttsx3 → gui.update_state("sleeping")
Include: the fact that `route_query` doesn't know any of this happened.

**Diagram 4 — Threading Model**
Show: 3 boxes (main thread, AI loop thread, hotkey thread). Show what blocks each thread and what unblocks it. Show `_WAKE_EVENT` connecting hotkey thread to AI loop thread.

**Diagram 5 — route_query Decision Tree**
Show: the full if/elif chain as a binary decision tree. Input: voice query string. Each branch leads to a feature function or AI fallback.

**Diagram 6 — Config Flow**
Show: config.json → `_load_cfg()` → `CFG` dict → which variables read from it at startup vs at runtime.

**Diagram 7 — Screen Analysis Feature**
Show: "what on my screen" → `route_query` → `handle_screenshot_command` → `take_screenshot` → `analyze_screenshot` → base64 encode → OpenRouter API → `speak(result)`
Include: the Llama vision model receiving the image as base64 in the request body.
