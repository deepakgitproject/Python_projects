import tkinter as tk
import threading
import time

from core import speak, command, chat_response, wishme
import system


class NovaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Nova Assistant")
        self.root.geometry("520x560")

        self.root.resizable(False, False)

        self.running = False
        self.thread = None

        # ---------- UI ----------
        self.status = tk.Label(root, text="Status: Idle", font=("Arial", 12))
        self.status.pack(pady=5)

        # Conversation box
        self.chat_box = tk.Text(root, height=14, width=60, state="disabled", wrap="word")
        self.chat_box.pack(padx=10, pady=5)

        # Scrollbar
        self.scrollbar = tk.Scrollbar(root, command=self.chat_box.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.chat_box.config(yscrollcommand=self.scrollbar.set)

        # Buttons
        self.start_btn = tk.Button(root, text="Start Assistant", width=20, command=self.start)
        self.start_btn.pack(pady=5)

        self.stop_btn = tk.Button(root, text="Stop Assistant", width=20, command=self.stop, state="disabled")
        self.stop_btn.pack(pady=5)

        self.exit_btn = tk.Button(root, text="Exit", width=20, command=self.exit_app)
        self.exit_btn.pack(pady=5)

    # ---------- UI HELPERS ----------
    def set_status(self, text):
        self.root.after(0, lambda: self.status.config(text=f"Status: {text}"))

    def add_message(self, sender, message):
        def _add():
            self.chat_box.config(state="normal")
            self.chat_box.insert("end", f"{sender}: {message}\n")
            self.chat_box.see("end")
            self.chat_box.config(state="disabled")

        self.root.after(0, _add)

    def speak_and_display(self, text):
        self.add_message("Nova", text)
        self.set_status("Speaking...")
        speak(text)
        self.set_status("Listening...")

    # ---------- BUTTON HANDLERS ----------
    def start(self):
        if self.running:
            return

        self.running = True
        self.set_status("Listening...")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.set_status("Idle")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def exit_app(self):
        self.running = False
        self.root.destroy()

    # ---------- MAIN LOOP ----------
    def run_loop(self):
        # Greet once
        wishme()

        while self.running:
            query = command()

            if not query:
                continue

            self.add_message("You", query)
            self.set_status("Processing...")

            # ---------- BRIGHTNESS ----------
            if any(word in query for word in ["brightness", "brighter", "dimmer", "dim", "bright"]):
                system.brightness_control(query, speak)
                self.set_status("Listening...")
                continue

            # ---------- BING SEARCH ----------
            if any(k in query for k in ["collect points", "collect reward"]):
                self.speak_and_display("Opening random tabs")
                system.bing_search()
                self.speak_and_display("Bing search completed")
                continue

            # ---------- WISH ME ----------
            if any(k in query for k in ["wishme", "wish me", "time", "date", "good morning", "good afternoon", "good evening"]):
                wishme()
                self.set_status("Listening...")
                continue

            # ---------- SCREENSHOT ----------
            if any(word in query for word in ["screenshot", "capture screen", "screen shot"]):
                system.handle_screenshot_command(query, speak)
                self.set_status("Listening...")
                continue

            # ---------- SOCIAL MEDIA ----------
            if any(word in query for word in ["facebook", "instagram", "twitter", "discord", "whatsapp", "youtube"]):
                system.social_media(query, speak)
                self.set_status("Listening...")
                continue

            # ---------- VOLUME ----------
            if any(word in query for word in ["volume", "mute", "unmute", "sound", "louder", "quieter", "increase", "decrease"]):
                system.volume_control(query, speak)
                self.set_status("Listening...")
                continue

            # ---------- OPEN APPS ----------
            if query.startswith("open"):
                system.open_app(query, speak)
                self.set_status("Listening...")
                continue

            # ---------- CLOSE APPS ----------
            if query.startswith("close"):
                system.close_app(query, speak)
                self.set_status("Listening...")
                continue

            # ---------- BROWSING ----------
            if any(word in query for word in ["search", "browse"]):
                system.browsing(query, command, speak)
                self.set_status("Listening...")
                continue

            # ---------- SYSTEM STATUS ----------
            if any(word in query for word in ["system condition", "system status", "battery status", "cpu usage"]):
                system.condition(speak)
                self.set_status("Listening...")
                continue

            # ---------- SLEEP MODE ----------
            if any(word in query for word in ["sleep", "sleep mode", "go to sleep"]):
                system.handle_sleep_command(query, command, speak)
                self.set_status("Listening...")
                continue

            # ---------- EXIT ----------
            if any(word in query for word in ["exit", "quit", "shutdown", "bye", "goodbye"]):
                self.speak_and_display("Shutting down. Goodbye!")
                self.running = False
                self.root.after(1000, self.root.destroy)
                return

            # ---------- ML CHAT FALLBACK ----------
            response = chat_response(query)
            if response:
                self.speak_and_display(response)
            else:
                self.speak_and_display("I'm not sure I understood that. Can you rephrase?")

        self.set_status("Idle")


def launch_gui():
    root = tk.Tk()
    app = NovaGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
