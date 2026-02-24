# startup + main loop

# from core import speak, command, chat_response

from core import speak, command, chat_response, wishme
import system

def main():
    speak("Hello, I am Nova. How can I assist you?")

    while True:
        query = command()

        if not query:
            continue

        # ---------- BRIGHTNESS ----------
        if any(word in query for word in ["brightness", "brighter", "dimmer", "dim", "bright"]):
            system.brightness_control(query, speak)
            continue

        # ---------- BING SEARCH ----------
        if any(k in query for k in ["collect points", "collect reward"]):
            speak("Opening 10 random tabs")
            system.bing_search()
            speak("bing search completed")
            continue

        # ---------- WISH ME ----------
        if any(k in query for k in ["wish me", "time", "date", "good morning", "good afternoon", "good evening"]):
            wishme()
            continue


        # ---------- SCREENSHOT ----------
        if any(word in query for word in ["screenshot", "capture screen", "screen shot"]):
            system.handle_screenshot_command(query, speak)
            continue

        # ---------- SOCIAL MEDIA ----------
        if any(word in query for word in ["facebook", "instagram", "twitter", "discord", "whatsapp", "youtube"]):
            system.social_media(query, speak)
            continue

        # ---------- VOLUME ----------
        if any(word in query for word in ["volume", "mute", "unmute", "sound", "louder", "quieter", "increase", "decrease"]):
            system.volume_control(query, speak)
            continue

        # ---------- OPEN APPS ----------
        if query.startswith("open"):
            system.open_app(query, speak)
            continue

        # ---------- CLOSE APPS ----------
        if query.startswith("close"):
            system.close_app(query, speak)
            continue

        # ---------- BROWSING ----------
        if any(word in query for word in ["search", "browse"]):
            system.browsing(query, command, speak)
            continue

        # ---------- SYSTEM STATUS ----------
        if any(word in query for word in ["system condition", "system status", "battery status", "cpu usage"]):
            system.condition(speak)
            continue

        # ---------- SLEEP MODE ----------
        if any(word in query for word in ["sleep", "sleep mode", "go to sleep"]):
            system.handle_sleep_command(query, command, speak)
            continue

        # ---------- EXIT ----------
        if any(word in query for word in ["exit", "quit", "shutdown", "bye", "goodbye"]):
            speak("Are you confirm you want to shut down?")
            confirm = command()
            if confirm and any(word in confirm for word in ["yes", "confirm", "exit", "quit"]):
                speak("Shutting down. Goodbye!")
                break
            else:
                speak("Shutdown cancelled.")
                continue

        # ---------- ML CHAT FALLBACK ----------
        response = chat_response(query)
        if response:
            speak(response)
        else:
            speak("I'm not sure I understood that. Can you rephrase?")

if __name__ == "__main__":
    main()
