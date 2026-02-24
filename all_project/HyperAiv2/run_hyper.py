"""
╔══════════════════════════════════════════════════════════════════╗
║              run_hyper.py  —  HYPER AI GUI Launcher              ║
║                                                                  ║
║  Activation (no wake word):                                      ║
║    ⌨️  Alt+Shift+1  — global hotkey                              ║
║    🖱  Mic button   — click in GUI                               ║
║    ⌨️  Type a command and press Enter                            ║
║                                                                  ║
║  Usage:  python run_hyper.py                                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import hyper_ai
from hyper_gui import HyperGUI


class HyperPipeline:
    """
    Connects HyperGUI to hyper_ai without modifying hyper_ai.py.

    Monkey-patches speak() and command() so the GUI reflects every
    state change.  Activation fires hyper_ai._WAKE_EVENT via:
      - Alt+Shift+1 hotkey  (hyper_ai._hotkey_thread)
      - Mic button click    (self.trigger_manually)
      - Typed text          (self.process_text_command — skips voice)
    """

    def __init__(self, gui: HyperGUI):
        self._gui          = gui
        self._running      = True
        self._orig_speak   = hyper_ai.speak
        self._orig_command = hyper_ai.command

    def _patched_speak(self, text: str):
        self._gui.update_state("speaking")
        self._gui.add_message(f"Hyper: {text}", "hyper")
        self._orig_speak(text)
        if self._gui._state == "speaking":
            self._gui.update_state("sleeping")

    def _patched_command(self, *args, **kwargs):
        self._gui.update_state("listening")
        result = self._orig_command(*args, **kwargs)
        self._gui.update_state("processing")
        return result

    def _install_patches(self):
        _p = self
        hyper_ai.speak   = lambda text:        _p._patched_speak(text)
        hyper_ai.command = lambda *a, **kw:    _p._patched_command(*a, **kw)

    def _remove_patches(self):
        hyper_ai.speak   = self._orig_speak
        hyper_ai.command = self._orig_command

    def start(self):
        self._install_patches()
        threading.Thread(target=self._ai_loop, daemon=True).start()

    def stop(self):
        self._running = False
        hyper_ai._WAKE_EVENT.set()
        self._remove_patches()

    def _ai_loop(self):
        print("""
╔══════════════════════════════════════════════════════╗
║          HYPER AI v2.0 — GUI Mode Active             ║
║                                                      ║
║   🖱  Click mic button  OR  ⌨️  Press Alt+Shift+1    ║
╚══════════════════════════════════════════════════════╝
        """, flush=True)

        hyper_ai._get_whisper()
        threading.Thread(target=hyper_ai._hotkey_thread, daemon=True).start()

        hyper_ai.speak(
            "Hello! I am Hyper AI version 2. "
            "Press Alt Shift 1 or click the mic button to activate me."
        )

        while self._running:
            self._gui.update_state("sleeping")
            hyper_ai._wait_for_activation()

            if not self._running:
                break

            query = hyper_ai.command()
            if not query:
                continue

            self._gui.add_message(f"You: {query}", "user")

            should_exit = hyper_ai.route_query(query)
            if should_exit:
                self._running = False
                self._gui._root.after(0, self._gui._on_close)
                return

    def process_text_command(self, text: str):
        """Typed command from GUI — skips voice, routes directly."""
        self._gui.update_state("processing")
        should_exit = hyper_ai.route_query(text.lower().strip())
        if should_exit:
            self._running = False
            self._gui._root.after(0, self._gui._on_close)
            return
        self._gui.update_state("sleeping")

    def trigger_manually(self):
        """Mic button click — fires _WAKE_EVENT exactly like the hotkey."""
        if not hyper_ai._MIC_BUSY.is_set():
            hyper_ai._WAKE_EVENT.set()


if __name__ == "__main__":
    gui      = HyperGUI()
    pipeline = HyperPipeline(gui)

    gui.pipeline = pipeline
    gui.build()        # create widgets on main thread
    pipeline.start()   # patch + launch background thread
    gui.run()          # tkinter mainloop — blocks until window closes
