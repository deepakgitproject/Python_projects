import datetime
import os
import sys
import time
import webbrowser
import pyautogui
import pyttsx3 #!pip install pyttsx3
import speech_recognition as sr
import json
import pickle
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences
import random
import numpy as np
import psutil 
import subprocess
import speech_recognition as sr
import threading
import screen_brightness_control as sbc
import re
import warnings
import logging
import nltk
from nltk.corpus import words

# Download the words dataset if not already downloaded




with open("intents.json") as file:
    data = json.load(file)

model = load_model("chat_model.h5")

with open("tokenizer.pkl", "rb") as f:
    tokenizer=pickle.load(f)

with open("label_encoder.pkl", "rb") as encoder_file:
    label_encoder=pickle.load(encoder_file)

#implement schedule control later
#implement more pyautogui functions later like open close minimize maximize screenshot etc.
# volume percent control using pyautogui
# keyboard shortcuts using pyautogui
# app opening using pyautogui search and enter or dicret open using os.system


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
    # time.sleep(0.2)



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





# Silence sbc warnings
logging.getLogger("screen_brightness_control").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning)





#1 brightness_control


def brightness_control(query):
    query = query.lower().strip()

    try:
        # Safer: don't specify display index
        current = sbc.get_brightness()[0]
    except Exception:
        speak("I cannot control brightness on this device.")
        print("Brightness control not supported.", flush=True)
        return

    # --- SET BRIGHTNESS TO X%
    match = re.search(r"(\d+)\s*(percent|%)", query)
    if match:
        value = int(match.group(1))
        value = max(0, min(100, value))

        sbc.set_brightness(value)
        speak(f"Brightness set to {value} percent")
        print(f"Brightness set to {value}%", flush=True)
        return

    # --- INCREASE
    if any(word in query for word in [
        "increase brightness", "brightness up", "make it brighter", "brighten"
    ]):
        new_value = min(current + 20, 100)
        sbc.set_brightness(new_value)
        speak(f"Increasing brightness to {new_value} percent")
        print(f"Increasing brightness to {new_value}%", flush=True)
        return

    # --- DECREASE
    if any(word in query for word in [
        "decrease brightness", "brightness down", "make it dimmer",
        "dim", "lower brightness"
    ]):
        new_value = max(current - 20, 0)
        sbc.set_brightness(new_value)
        speak(f"Decreasing brightness to {new_value} percent")
        print(f"Decreasing brightness to {new_value}%", flush=True)
        return

    speak("Brightness command not recognized.")
    print("Brightness command not recognized.", flush=True)




# 2  bing search 

def bing_search():
    nltk.download('words')

    # Get a list of English words
    english_word_list = words.words()

    # Number of tabs to open
    num_tabs = 10

    # Iterate over the specified number of tabs
    for tab_number in range(num_tabs):
        # Get a random word from the list
        random_word = random.choice(english_word_list)

        # Construct a Google search query using the random word
        search_query = f'https://www.google.com/search?q={random_word}'

        # Open the browser and perform the initial 
        webbrowser.open(search_query)
        time.sleep(2)  # Adjust the delay if needed

        # Simulate pressing Ctrl + t to open a new tab
        pyautogui.hotkey('ctrl', 't')
        time.sleep(2)  # Adjust the delay if needed

        # Type the random word in the new tab's search bar
        pyautogui.typewrite(random_word)
        pyautogui.press('enter')

        # Introduce a delay of 10 seconds before opening the next tab
        time.sleep(10)



# 3 wishme
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




# 4 screen shot
def take_screenshot(name=None):
    try:
        # Get Windows Downloads folder
        downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        if name:
            filename = f"{name}_{timestamp}.png"
        else:
            filename = f"screenshot_{timestamp}.png"

        filepath = os.path.join(downloads_folder, filename)

        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)

        speak("Screenshot taken and saved to Downloads.")
        print(f"Screenshot saved as {filepath}", flush=True)

    except Exception as e:
        speak("Failed to take screenshot.")
        print(f"Screenshot error: {e}", flush=True)

def handle_screenshot_command(query):
    query = query.lower().strip()

    # --- Named screenshot
    match = re.search(r"(named|name it|call it)\s+(\w+)", query)

    if match:
        name = match.group(2)
        take_screenshot(name)
        return

    # --- Instant screenshot
    if any(word in query for word in [
        "take screenshot", "screenshot", "capture screen", "screen shot"
    ]):
        take_screenshot()
        return

    speak("I didn't understand the screenshot command.")






# 5 sociial media
def social_media(query):
    if "facebook" in query:
        speak("Opening Facebook")
        print("Opening Facebook...", end="", flush=True)
        webbrowser.open("https://www.facebook.com")
    elif "instagram" in query:
        speak("Opening Instagram")
        print("Opening Instagram...", end="", flush=True)
        webbrowser.open("https://www.instagram.com")
    elif "twitter" in query:
        speak("Opening Twitter")
        print("Opening Twitter...", end="", flush=True)
        webbrowser.open("https://www.twitter.com")
    elif "discord" in query:
        speak("Opening Discord")
        print("Opening Discord...", end="", flush=True)
        webbrowser.open("https://www.discord.com")
    elif "whatsapp" in query:
        speak("Opening WhatsApp")
        print("Opening WhatsApp...", end="", flush=True)
        webbrowser.open("https://web.whatsapp.com")
    elif "youtube" in query:
        speak("Opening youtube")
        print("Opening youtube...", end="", flush=True)
        webbrowser.open("https://www.youtube.com")
    else:
        speak("Social media platform not recognized.")
        print("Social media platform not recognized.", end="", flush=True)
    print("\r", end="", flush=True)




#  6  volume controll
def volume_control(query):
    query = query.lower().strip()

    # Safer intent detection
    increase_words = ["increase", "volume up", "louder", "raise volume"]
    decrease_words = ["decrease", "volume down", "quieter", "lower volume"]
    mute_words = ["mute", "silent"]
    unmute_words = ["unmute", "sound on"]

    def press_key(key, times=5):
        for _ in range(times):
            pyautogui.press(key)

    # --- UNMUTE FIRST (important: avoids "mute" inside "unmute" bug)
    if any(word in query for word in unmute_words):
        speak("Unmuting volume")
        print("Unmuting volume...", end="", flush=True)
        pyautogui.press("volumemute")
        print("\r", end="", flush=True)
        return

    # --- MUTE
    if any(word in query for word in mute_words):
        speak("Muting volume")
        print("Muting volume...", end="", flush=True)
        pyautogui.press("volumemute")
        print("\r", end="", flush=True)
        return

    # --- INCREASE
    if any(word in query for word in increase_words):
        speak("Increasing volume")
        print("Increasing volume...", end="", flush=True)
        press_key("volumeup", times=10)
        print("\r", end="", flush=True)
        return

    # --- DECREASE
    if any(word in query for word in decrease_words):
        speak("Decreasing volume")
        print("Decreasing volume...", end="", flush=True)
        press_key("volumedown", times=10)
        print("\r", end="", flush=True)
        return

    # --- FALLBACK
    speak("Volume command not recognized.")
    print("Volume command not recognized.", end="", flush=True)
    print("\r", end="", flush=True)

# 7  app opening and closing 
APPS = {
    "notepad": {"open": "notepad", "close": "notepad.exe"},
    "calculator": {"open": "calc", "close": "Calculator.exe"},
    "calc": {"open": "calc", "close": "Calculator.exe"},
    "command prompt": {"open": "cmd", "close": "cmd.exe"},
    "cmd": {"open": "cmd", "close": "cmd.exe"},
    "paint": {"open": "mspaint", "close": "mspaint.exe"},
    "wordpad": {"open": "wordpad", "close": "wordpad.exe"},
    "camera": {"open": "start microsoft.windows.camera:", "close": "WindowsCamera.exe"},
    "settings": {"open": "start ms-settings:", "close": "SystemSettings.exe"},
    "file explorer": {"open": "explorer", "close": "explorer.exe"},
    "explorer": {"open": "explorer", "close": "explorer.exe"},
    "chrome": {"open": "start chrome", "close": "chrome.exe"},
    "brave": {"open": "start brave", "close": "brave.exe"},
    "edge": {"open": "start msedge", "close": "msedge.exe"},
    "firefox": {"open": "start firefox", "close": "firefox.exe"},
    "opera": {"open": "start opera", "close": "opera.exe"},
    "vlc": {"open": "start vlc", "close": "vlc.exe"},
    "spotify": {"open": "start spotify", "close": "spotify.exe"},
    "discord": {"open": "start discord", "close": "discord.exe"},
    "teams": {"open": "start ms-teams", "close": "ms-teams.exe"},
    "zoom": {"open": "start zoom", "close": "zoom.exe"},
    "skype": {"open": "start skype", "close": "skype.exe"},
    "vs code": {"open": "code", "close": "Code.exe"},
    "visual studio": {"open": "devenv", "close": "devenv.exe"},
    "git bash": {"open": "start git-bash", "close": "git-bash.exe"},
    "powershell": {"open": "powershell", "close": "powershell.exe"},
    "task manager": {"open": "taskmgr", "close": "Taskmgr.exe"},
    "control panel": {"open": "control", "close": "control.exe"},
    "photos": {"open": "start ms-photos:", "close": "Microsoft.Photos.exe"},
    "snipping tool": {"open": "snippingtool", "close": "SnippingTool.exe"},
    "onenote": {"open": "onenote", "close": "onenote.exe"},
    "outlook": {"open": "outlook", "close": "outlook.exe"},
    "excel": {"open": "excel", "close": "excel.exe"},
    "word": {"open": "winword", "close": "winword.exe"},
    "powerpoint": {"open": "powerpnt", "close": "powerpnt.exe"},
    "steam": {"open": "start steam", "close": "steam.exe"},
    "epic games": {"open": "start epicgameslauncher", "close": "EpicGamesLauncher.exe"}
}


def open_app(query):
    query = query.lower()

    for name, cmds in APPS.items():
        if name in query:
            speak(f"Opening {name.title()}")
            print(f"Opening {name.title()}...", end="", flush=True)
            os.system(cmds["open"])
            return

    speak("Application not recognized.")
    print("Application not recognized.", end="", flush=True)


def close_app(query):
    query = query.lower()

    for name, cmds in APPS.items():
        if name in query:
            speak(f"Closing {name.title()}")
            print(f"Closing {name.title()}...", end="", flush=True)
            os.system(f'taskkill /f /im {cmds["close"]}')
            return

    speak("Application not recognized.")
    print("Application not recognized.", end="", flush=True)


#8 browsing 

def browsing(query):
    query = query.lower().strip()

    # --- SEARCH INTENT
    if any(k in query for k in ["browse","search"]):
        speak("What should I search for?")
        s = command().lower().strip()
        speak(f"Searching for {s}")
        print(f"Searching for {s}...", end="", flush=True)
        webbrowser.open(f"https://www.google.com/search?q={s}")
        return

    # --- FALLBACK
    speak("Browsing command not recognized.")
    print("Browsing command not recognized.", end="", flush=True)
#9 system condition
def condition():
    # --- CPU USAGE
    usage = psutil.cpu_percent(interval=1)
    speak(f"CPU usage is at {usage} percent")
    print(f"CPU usage: {usage}%", flush=True)

    # --- BATTERY STATUS (Safe Handling)
    battery = psutil.sensors_battery()

    if battery is None:
        speak("Battery information is not available.")
        print("Battery info not available.", flush=True)
        return

    percentage = battery.percent
    plugged = battery.power_plugged

    speak(f"Battery level is at {percentage} percent")
    print(f"Battery level: {percentage}%", flush=True)

    # --- DECISION LOGIC (FIXED THRESHOLDS)
    if plugged:
        speak("The system is currently charging.")
    else:
        speak("The system is running on battery power.")

    if percentage >= 80:
        speak("We have enough battery to continue working.")
    elif 40 <= percentage < 80:
        speak("Battery is moderate. You should consider plugging in the charger.")
    else:
        speak("Battery is very low. Please connect to a charger immediately.")

def cleanup():
    try:
        if engine:
            engine.stop()
    except:
        pass



#10  sleep mode 



sleep_timer = None

def go_to_sleep(delay_minutes=0):
    global sleep_timer

    def sleep_action():
        speak("Going to sleep now. Goodbye!")
        print("System going to sleep...", flush=True)
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    # Cancel any existing scheduled sleep
    if sleep_timer and sleep_timer.is_alive():
        sleep_timer.cancel()

    if delay_minutes <= 0:
        sleep_action()
    else:
        speak(f"Okay, I will put the system to sleep in {delay_minutes} minutes.")
        print(f"Sleep scheduled in {delay_minutes} minutes.", flush=True)

        sleep_timer = threading.Timer(delay_minutes * 60, sleep_action)
        sleep_timer.start()


def cancel_sleep():
    global sleep_timer

    if sleep_timer and sleep_timer.is_alive():
        sleep_timer.cancel()
        sleep_timer = None
        speak("Sleep mode has been cancelled.")
        print("Sleep mode cancelled.", flush=True)
    else:
        speak("No sleep mode is currently scheduled.")
        print("No sleep scheduled.", flush=True)


def handle_sleep_command(query):
    query = query.lower().strip()

    # --- CANCEL SLEEP
    if any(word in query for word in ["cancel sleep", "stop sleep", "don't sleep"]):
        cancel_sleep()
        return

    # --- DELAYED SLEEP
    match = re.search(r"(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)", query)

    if match:
        value = int(match.group(1))
        unit = match.group(2)

        if "hour" in unit:
            delay_minutes = value * 60
        else:
            delay_minutes = value

        go_to_sleep(delay_minutes)
        return

    # --- INSTANT SLEEP (WITH CONFIRMATION)
    if any(word in query for word in [
        "sleep now", "go to sleep", "sleep mode", "put laptop to sleep"
    ]):

        speak("Are you sure you want to put the system to sleep now?")
        print("Are you sure you want to put the system to sleep now?", flush=True)

        # confirm = command()
        confirm = input("Enter confirmation:=>  ").lower()

        if confirm and any(word in confirm for word in [
            "yes", "sure", "confirm", "ok", "okay"
        ]):
            go_to_sleep(0)
        else:
            speak("Sleep cancelled.")
            print("Sleep cancelled.", flush=True)

        return

    speak("I didn't understand the sleep command.")











#main program connection starts form here 





if __name__ == "__main__":

    speak("Hello, I am Nova. How can I assist you?")

    while True:
        query = command()  # voice input
        # query = query.lower().strip()
        # query = input("Enter your command: ").lower()  # text input

        if not query:
            continue
        # 1---------- BRIGHTNESS CONTROL ----------
        if any(word in query for word in ["brightness", "brighter", "dimmer", "dim", "bright"]):
            brightness_control(query)
            continue

        #2------------bing search---------
        if any(k in query for k in ["collect points","collect reward"]):
            speak("opening 10 different tabs")
            bing_search()
            continue

        #3----------wishme-----------------
        if any(k in query for k in ["wishme","what is the time","time","what is the date","todays date","Good morning","good afternoon","good evening","good night"]):
            wishme()
            continue

        #4 ---------- SCREENSHOT ----------
        if any(word in query for word in ["screenshot", "capture screen", "screen shot"]):
            handle_screenshot_command(query)
            continue

        #5 ---------- SOCIAL MEDIA ----------
        if any(word in query for word in [
            "facebook", "instagram", "twitter", "discord", "whatsapp", "youtube"
        ]):
            social_media(query)
            continue
        

        

        # 6 ---------- VOLUME CONTROL ----------
        if any(word in query for word in [
            "volume", "mute", "unmute", "sound", "louder", "quieter",
            "increase", "decrease"
        ]):
            volume_control(query)
            continue

        # 7.1 ---------- OPEN APPS ----------
        if query.startswith("open"):
            open_app(query)
            continue

        #7.2 ---------- CLOSE APPS ----------
        if query.startswith("close"):
            close_app(query)
            continue

        #8 ---------- BROWSING ----------
        if any(word in query for word in ["search", "browse"]):
            browsing(query)
            continue


        #9 ---------- SYSTEM STATUS ----------
        if any(word in query for word in [
            "system condition", "system status", "battery status",
            "cpu usage", "condition of the system"
        ]):
            speak("Checking the system condition")
            condition()
            continue


        #10 ---------- SLEEP MODE ----------
        if any(word in query for word in ["sleep", "sleep mode", "go to sleep"]):
            handle_sleep_command(query)
            continue

        



       

        # ---------- EXIT ----------
        if any(word in query for word in [
            "exit", "quit", "shutdown", "bye", "goodbye"
        ]):
            speak("Are you sure you want to shut down?")
            print("Are you sure you want to shut down?", flush=True)

            confirm = command()
            # confirm = input("Enter confermation Command:=>").lower()
            if confirm and any(word in confirm for word in [
                "yes", "sure", "confirm", "exit", "quit"
            ]):
                speak("Shutting down. Goodbye!")
                print("Shutting down. Goodbye!", flush=True)
                cleanup()
                sys.exit(0)
            else:
                speak("Shutdown cancelled.")
                continue
            

        # ---------- ML CHAT FALLBACK ----------
        padded_sequences = pad_sequences(
            tokenizer.texts_to_sequences([query]),
            maxlen=20,
            truncating="post"
        )

        result = model.predict(padded_sequences, verbose=0)
        confidence = float(np.max(result))
        tag = label_encoder.inverse_transform([np.argmax(result)])[0]

        # --- Confidence filter
        if confidence < 0.60:
            speak("I'm not sure I understood that. Can you rephrase?")
            continue

        # --- Match tag with intents.json
        matched = False
        for intent in data["intents"]:
            if intent["tag"].lower() == tag.lower():
                response = np.random.choice(intent["responses"])
                speak(response)
                matched = True
                break

        if not matched:
            speak("I didn't understand that. Try saying something else.")


        