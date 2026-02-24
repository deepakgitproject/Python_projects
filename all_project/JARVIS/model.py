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
def initialize_engine():
    engine = pyttsx3.init('sapi5')
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)
    engine.setProperty('rate', engine.getProperty('rate') - 50)
    engine.setProperty('volume', min(engine.getProperty('volume') + 0.25, 1.0))
    return engine


def speak(text):
    engine = initialize_engine()
    engine.say(text)
    engine.runAndWait()
    # time.sleep(0.2)

def command():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        print("Listening.......", end="", flush=True)
        r.pause_threshold=1.0
        r.phrase_threshold=0.3
        r.sample_rate = 48000
        r.dynamic_energy_threshold=True
        r.operation_timeout=5
        r.non_speaking_duration=0.5
        r.dynamic_energy_adjustment=2
        r.energy_threshold=4000
        r.phrase_time_limit = 10
        # print(sr.Microphone.list_microphone_names())
        audio = r.listen(source)
    try:
        print("\r" ,end="", flush=True)
        print("Recognizing......", end="", flush=True)
        query = r.recognize_google(audio, language='en-in')
        print("\r" ,end="", flush=True)
        print(f"User said : {query}\n")
    except Exception as e:
        print("Say that again please")
        return "None"
    return query


def cal_day():
    day_index = datetime.datetime.today().weekday()
    day_dict = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    return day_dict[day_index]


def wishme(name):
    hour = datetime.datetime.now().hour
    day = cal_day()
    t = datetime.datetime.now().strftime("%I:%M %p")

    message = f"It's {t} on {day}. How can I assist you?"
    if 0 <= hour < 12:
        greeting = f"Good Morning{name}! {message}"
    elif 12 <= hour < 18:
        greeting = f"Good Afternoon{name}! {message}"
    else:
        greeting = f"Good Evening{name}! {message}"

    # engine.say(message)
    # engine.say(greeting)
    # engine.runAndWait()
    speak(greeting)

    print(message)

        
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

def volume_control(query):
    if "increase" in query or "up" in query or "louder" in query or "higher" in query:
        speak("Increasing volume")
        print("Increasing volume...", end="", flush=True)
        pyautogui.press("volumeup")
        # Implement volume increase logic here
    elif "decrease" in query or "down" in query or "quieter" in query or "lower" in query:
        speak("Decreasing volume")
        print("Decreasing volume...", end="", flush=True)
        pyautogui.press("volumedown")
        # Implement volume decrease logic here
    elif "mute" in query or "silent" in query:
        speak("Muting volume")
        print("Muting volume...", end="", flush=True)
        pyautogui.press("volumemute")
        # Implement mute logic here
    elif "unmute" in query or "sound on" in query:
        speak("Unmuting volume")
        print("Unmuting volume...", end="", flush=True)
        pyautogui.press("volumemute")
        # Implement unmute logic here
    # elif "set to" in query or "set volume to" in query or "volume to" in query or "set the volume to" in query:
    #     # Implement set volume logic here
    #     try:
    # else:
        speak("Volume command not recognized.")
        print("Volume command not recognized.", end="", flush=True)
    print("\r", end="", flush=True)

def open_app(query):
    # if "notepad" in query:
    #     speak("Opening Notepad")
    #     print("Opening Notepad...", end="", flush=True)
    #     pyautogui.press("win")
    #     time.sleep(0.5)
    #     pyautogui.write("notepad")
    #     time.sleep(0.5)
    #     pyautogui.press("enter")
    if "notepad" in query:
        speak("Opening Notepad")
        print("Opening Notepad...", end="", flush=True)
        os.system("notepad")
    elif "calculator" in query:
        speak("Opening Calculator")
        print("Opening Calculator...", end="", flush=True)
        os.system("calc")
    elif "command prompt" in query or "cmd" in query:
        speak("Opening Command Prompt")
        print("Opening Command Prompt...", end="", flush=True)
        os.system("cmd")
    elif "paint" in query:
        speak("Opening Paint")
        print("Opening Paint...", end="", flush=True)
        os.system("mspaint")
    elif "wordpad" in query:
        speak("Opening WordPad")
        print("Opening WordPad...", end="", flush=True)
        os.system("wordpad")
    elif "camera" in query:
        speak("Opening Camera")
        print("Opening Camera...", end="", flush=True)
        os.system("start microsoft.windows.camera:")
    elif "settings" in query:
        speak("Opening Settings")
        print("Opening Settings...", end="", flush=True)
        os.system("start ms-settings:")
    elif "file explorer" in query:
        speak("Opening File Explorer")
        print("Opening File Explorer...", end="", flush=True)
        os.system("explorer")
    elif "chrome" in query:
        speak("Opening Google Chrome")
        print("Opening Google Chrome...", end="", flush=True)
        os.system("start chrome")
    elif "brave" in query:
        speak("Opening Brave Browser")
        print("Opening Brave Browser...", end="", flush=True)
        os.system("start brave")
def close_app(query):
    if "notepad" in query:
        speak("Closing Notepad")
        print("Closing Notepad...", end="", flush=True)
        os.system("taskkill /f /im notepad.exe")
    elif "calculator" in query:
        speak("Closing Calculator")
        print("Closing Calculator...", end="", flush=True)
        os.system("taskkill /f /im Calculator.exe")
    elif "command prompt" in query or "cmd" in query:
        speak("Closing Command Prompt")
        print("Closing Command Prompt...", end="", flush=True)
        os.system("taskkill /f /im cmd.exe")
    elif "paint" in query:
        speak("Closing Paint")
        print("Closing Paint...", end="", flush=True)
        os.system("taskkill /f /im mspaint.exe")
    elif "wordpad" in query:
        speak("Closing WordPad")
        print("Closing WordPad...", end="", flush=True)
        os.system("taskkill /f /im wordpad.exe")
    elif "camera" in query:
        speak("Closing Camera")
        print("Closing Camera...", end="", flush=True)
        os.system("taskkill /f /im WindowsCamera.exe")
    elif "settings" in query:
        speak("Closing Settings")
        print("Closing Settings...", end="", flush=True)
        os.system("taskkill /f /im SystemSettings.exe")
    elif "file explorer" in query:
        speak("Closing File Explorer")
        print("Closing File Explorer...", end="", flush=True)
        os.system("taskkill /f /im explorer.exe")
    elif "chrome" in query:
        speak("Closing Google Chrome")
        print("Closing Google Chrome...", end="", flush=True)
        os.system("taskkill /f /im chrome.exe")
    elif "brave" in query:
        speak("Closing Brave Browser")
        print("Closing Brave Browser...", end="", flush=True)
        os.system("taskkill /f /im brave.exe")
    elif "browser" in query:
        speak("closing browser")
        print("closing brower")
        os.system()
    else:
        speak("Application not recognized.")
        print("Application not recognized.", end="", flush=True)



def browsing(query):
    if 'search' in query:
        speak("Boss, what should i search on google..")
        s = command().lower()
        webbrowser.open(f"{s}")

def condition():
    usage = str(psutil.cpu_percent())
    speak(f"CPU is at {usage} percentage")
    battery = psutil.sensors_battery()
    percentage = battery.percent
    speak(f"Boss our system have {percentage} percentage battery")

    if percentage>=80:
        speak("Boss we could have enough charging to continue our recording")
    elif percentage>=40 and percentage<=75:
        speak("Boss we should connect our system to charging point to charge our battery")
    else:
        speak("Boss we have very low power, please connect to charging otherwise recording should be off...")

if __name__ == "__main__":
    # name = input("Enter your name: ")
    # wishme(name)
    wishme("Deepak")

    # speak("Hello, I am JARVIS. How can I assist you?")
    # while True:
    #     print(f"Processing command: {query}")
    # check = True
    while True:
        # query = input("Enter your command: ").lower()
        query = command().lower()
        if("facebook" in query or "instagram" in query or "twitter" in query or "discord" in query or "whatsapp" in query or "youtube" in query):
            social_media(query)
        elif("volume" in query):
            volume_control(query)
        elif("open notepad" in query or "open calculator" in query or "open command prompt" in query or "open cmd" in query or "open paint" in query
             or "open wordpad" in query or "open camera" in query or "open settings" in query or "open file explorer" in query or "open chrome" in query or "open brave" in query):
            open_app(query)
        elif("close notepad" in query or "close calculator" in query or "close command prompt" in query or "close cmd" in query or "close paint" in query
             or "close wordpad" in query or "close camera" in query or "close settings" in query or "close file explorer" in query or "close chrome" in query or "close brave" in query):
            close_app(query)
        elif ("what" in query) or ("who" in query) or ("how" in query) or ("hi" in query) or ("thanks" in query) or ("hello" in query):
                padded_sequences = pad_sequences(tokenizer.texts_to_sequences([query]), maxlen=20, truncating='post')
                result = model.predict(padded_sequences)
                tag = label_encoder.inverse_transform([np.argmax(result)])

                for i in data['intents']:
                    if i['tag'] == tag:
                        speak(np.random.choice(i['responses']))

        elif ("open google" in query) or ("open edge" in query):
                browsing(query)

        elif ("system condition" in query) or ("condition of the system" in query):
            speak("checking the system condition")
            condition()

        elif "exit" in query or "quit" in query or "stop" in query:
            speak("Shutting down. Goodbye!")
            print("Shutting down. Goodbye!", flush=True)
            sys.exit()
        