# brightness, volume, apps, browsing, sleep, screenshot

import os
import time
import webbrowser
import pyautogui
import psutil
import threading
import screen_brightness_control as sbc
import re
import warnings
import logging
import datetime
import random
from nltk.corpus import words

def bing_search():
    try:
        english_word_list = words.words()
    except LookupError:
        return

    num_tabs = 10

    for _ in range(num_tabs):
        random_word = random.choice(english_word_list)
        search_query = f'https://www.google.com/search?q={random_word}'

        webbrowser.open(search_query)
        time.sleep(2)

        pyautogui.hotkey('ctrl', 't')
        time.sleep(2)

        pyautogui.typewrite(random_word)
        pyautogui.press('enter')

        time.sleep(10)
    

# Silence sbc warnings
logging.getLogger("screen_brightness_control").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning)





#1 brightness_control


def brightness_control(query,speak):
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


# ---------- SCREENSHOT ----------
def take_screenshot(name, speak):
    try:
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{name}_{timestamp}.png" if name else f"screenshot_{timestamp}.png"
        path = os.path.join(downloads, filename)

        pyautogui.screenshot().save(path)
        speak("Screenshot taken and saved to Downloads.")

    except Exception:
        speak("Failed to take screenshot.")

def handle_screenshot_command(query, speak):
    match = re.search(r"(named|name it|call it)\s+(\w+)", query)
    if match:
        take_screenshot(match.group(2), speak)
        return

    if any(word in query for word in ["take screenshot", "screenshot", "capture screen", "screen shot"]):
        take_screenshot(None, speak)
        return

    speak("I didn't understand the screenshot command.")

# ---------- SOCIAL MEDIA ----------
def social_media(query, speak):
    sites = {
        "facebook": "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
        "twitter": "https://www.twitter.com",
        "discord": "https://www.discord.com",
        "whatsapp": "https://web.whatsapp.com",
        "youtube": "https://www.youtube.com"
    }

    for name, url in sites.items():
        if name in query:
            speak(f"Opening {name}")
            webbrowser.open(url)
            return

    speak("Social media platform not recognized.")

# ---------- VOLUME ----------
def volume_control(query,speak):
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

# ---------- APPS ----------
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


def open_app(query,speak):
    query = query.lower()

    for name, cmds in APPS.items():
        if name in query:
            speak(f"Opening {name.title()}")
            print(f"Opening {name.title()}...", end="", flush=True)
            os.system(cmds["open"])
            return

    speak("Application not recognized.")
    print("Application not recognized.", end="", flush=True)


def close_app(query,speak):
    query = query.lower()

    for name, cmds in APPS.items():
        if name in query:
            speak(f"Closing {name.title()}")
            print(f"Closing {name.title()}...", end="", flush=True)
            os.system(f'taskkill /f /im {cmds["close"]}')
            return

    speak("Application not recognized.")
    print("Application not recognized.", end="", flush=True)

# ---------- BROWSING ----------
def browsing(query, command, speak):
    if any(k in query for k in ["browse", "search"]):
        speak("What should I search for?")
        s = command()
        if s:
            speak(f"Searching for {s}")
            webbrowser.open(f"https://www.google.com/search?q={s}")
        return

    speak("Browsing command not recognized.")

# ---------- SYSTEM STATUS ----------
def condition(speak):
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

# ---------- SLEEP MODE ----------

# def cleanup():
#     try:
#         if engine:
#             engine.stop()
#     except:
#         pass
sleep_timer = None

def go_to_sleep(delay_minutes, speak):
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

def cancel_sleep(speak):
    global sleep_timer

    if sleep_timer and sleep_timer.is_alive():
        sleep_timer.cancel()
        sleep_timer = None
        speak("Sleep mode has been cancelled.")
        print("Sleep mode cancelled.", flush=True)
    else:
        speak("No sleep mode is currently scheduled.")
        print("No sleep scheduled.", flush=True)

def handle_sleep_command(query,command,speak):
    query = query.lower().strip()

    # --- CANCEL SLEEP
    if any(word in query for word in ["cancel sleep", "stop sleep", "don't sleep"]):
        cancel_sleep(speak)
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

        go_to_sleep(delay_minutes, speak)
        return

    # --- INSTANT SLEEP (WITH CONFIRMATION)
    if any(word in query for word in [
        "sleep now", "go to sleep", "sleep mode", "put laptop to sleep"
    ]):

        speak("Are you confirm you want to put the system to sleep now?")
        print("Are you confirm you want to put the system to sleep now?", flush=True)

        confirm = command()
        # confirm = input("Enter confirmation:=>  ").lower()

        if confirm and any(word in confirm for word in [
            "yes", "sure", "confirm", "ok", "okay"
        ]):
            go_to_sleep(0, speak)
        else:
            speak("Sleep cancelled.")
            print("Sleep cancelled.", flush=True)

        return

    speak("I didn't understand the sleep command.")



