"""
╔══════════════════════════════════════════════════════════════════╗
║                   HYPER AI  —  Dark Theme GUI                    ║
║  Adapted from NOVA GUI · Tkinter · Same structure, new branding  ║
╚══════════════════════════════════════════════════════════════════╝

Drop this file next to hyper_ai.py, then run:
    python run_hyper.py
"""

import tkinter as tk
from tkinter import scrolledtext, font as tkfont
import threading
import time
import math
import logging
import sys
import os

logger = logging.getLogger(__name__)


class HyperGUI:
    """
    HYPER AI's dark theme GUI built with tkinter.

    Identical feature set to NOVA GUI:
    ─ Animated status indicator  (sleeping / listening / processing / speaking / error)
    ─ Conversation log with colour-coded messages
    ─ Microphone amplitude waveform bars
    ─ Live system info bar  (time · CPU · RAM · battery)
    ─ Text input + mic button
    ─ System tray icon  (optional — needs pystray + Pillow)

    pipeline  (optional): any object that implements:
        pipeline.process_text_command(text: str)
        pipeline.trigger_manually()
        pipeline.stop()
    """

    # ── Colour Scheme ────────────────────────────────────────────────
    BG           = "#1a1a2e"
    SECONDARY_BG = "#16213e"
    CARD_BG      = "#0f3460"
    ACCENT       = "#e94560"   # hot pink — same as NOVA
    TEXT         = "#eaeaea"
    DIM_TEXT     = "#8888aa"
    GREEN        = "#00e676"
    BLUE         = "#448aff"
    ORANGE       = "#ff9100"
    GREY         = "#666680"

    def __init__(self, pipeline=None):
        self.pipeline          = pipeline
        self._root             = None
        self._canvas           = None
        self._log_widget       = None
        self._status_label     = None
        self._info_bar         = None
        self._waveform_canvas  = None
        self._input_entry      = None
        self._state            = "sleeping"
        self._pulse_angle      = 0
        self._running          = False
        self._tray_icon        = None
        self._amplitude        = 0.0

    # ═══════════════════════════════════════════════════════════════
    #  BUILD
    # ═══════════════════════════════════════════════════════════════
    def build(self):
        """Construct every widget.  Call this from the main thread."""
        self._root = tk.Tk()
        self._root.title("HYPER AI — AI Voice Assistant")
        self._root.geometry("480x680")
        self._root.minsize(420, 560)
        self._root.configure(bg=self.BG)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Optional window icon
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "assets", "icon.ico")
            if os.path.exists(icon_path):
                self._root.iconbitmap(icon_path)
        except Exception:
            pass

        # ── Fonts ───────────────────────────────────────────────────
        self._title_font  = tkfont.Font(family="Segoe UI", size=22, weight="bold")
        self._status_font = tkfont.Font(family="Segoe UI", size=11)
        self._log_font    = tkfont.Font(family="Consolas", size=10)
        self._info_font   = tkfont.Font(family="Segoe UI", size=9)

        # ── Header ──────────────────────────────────────────────────
        header = tk.Frame(self._root, bg=self.BG, pady=15)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="✦ HYPER AI",
            font=self._title_font,
            fg=self.ACCENT,
            bg=self.BG,
        ).pack()

        tk.Label(
            header,
            text="AI Voice Assistant",
            font=tkfont.Font(family="Segoe UI", size=10),
            fg=self.DIM_TEXT,
            bg=self.BG,
        ).pack()

        # ── Status Indicator (animated canvas) ──────────────────────
        canvas_frame = tk.Frame(self._root, bg=self.BG)
        canvas_frame.pack(pady=10)

        self._canvas = tk.Canvas(
            canvas_frame,
            width=160, height=160,
            bg=self.BG, highlightthickness=0,
        )
        self._canvas.pack()

        # ── Status Text ─────────────────────────────────────────────
        self._status_label = tk.Label(
            self._root,
            text="● Sleeping — Press Alt+Shift+1 to activate",
            font=self._status_font,
            fg=self.GREY,
            bg=self.BG,
        )
        self._status_label.pack(pady=(0, 5))

        # ── Waveform Bars ───────────────────────────────────────────
        waveform_frame = tk.Frame(self._root, bg=self.BG, height=40)
        waveform_frame.pack(fill=tk.X, padx=30, pady=5)
        waveform_frame.pack_propagate(False)

        self._waveform_canvas = tk.Canvas(
            waveform_frame,
            bg=self.BG, height=40, highlightthickness=0,
        )
        self._waveform_canvas.pack(fill=tk.X)

        # ── Conversation Log ────────────────────────────────────────
        log_frame = tk.Frame(self._root, bg=self.SECONDARY_BG, padx=2, pady=2)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        tk.Label(
            log_frame,
            text="  Conversation Log",
            font=tkfont.Font(family="Segoe UI", size=10, weight="bold"),
            fg=self.DIM_TEXT,
            bg=self.SECONDARY_BG,
            anchor="w",
        ).pack(fill=tk.X, pady=(5, 0), padx=5)

        self._log_widget = scrolledtext.ScrolledText(
            log_frame,
            font=self._log_font,
            bg=self.CARD_BG,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            selectbackground=self.ACCENT,
            relief=tk.FLAT,
            wrap=tk.WORD,
            state=tk.DISABLED,
            height=12,
            padx=10,
            pady=8,
        )
        self._log_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Colour tags
        self._log_widget.tag_configure("user",   foreground="#64b5f6")   # blue
        self._log_widget.tag_configure("hyper",  foreground="#81c784")   # green
        self._log_widget.tag_configure("system", foreground=self.DIM_TEXT)
        self._log_widget.tag_configure("error",  foreground=self.ACCENT)

        # ── Input Bar ───────────────────────────────────────────────
        input_frame = tk.Frame(self._root, bg=self.BG)
        input_frame.pack(fill=tk.X, padx=15, pady=(0, 5))

        self._input_entry = tk.Entry(
            input_frame,
            font=self._status_font,
            bg=self.SECONDARY_BG,
            fg=self.DIM_TEXT,
            insertbackground=self.TEXT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor=self.ACCENT,
            highlightbackground=self.GREY,
        )
        self._input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 5))
        self._input_entry.insert(0, "Type a command...")
        self._input_entry.bind("<FocusIn>",  self._on_input_focus)
        self._input_entry.bind("<FocusOut>", self._on_input_unfocus)
        self._input_entry.bind("<Return>",   self._on_input_submit)

        # Mic button
        self._mic_btn = tk.Button(
            input_frame,
            text="🎤",
            font=tkfont.Font(size=14),
            bg=self.ACCENT,
            fg="white",
            relief=tk.FLAT,
            activebackground="#c62048",
            command=self._on_mic_click,
            width=3,
            cursor="hand2",
        )
        self._mic_btn.pack(side=tk.RIGHT)

        # ── System Info Bar ─────────────────────────────────────────
        self._info_bar = tk.Label(
            self._root,
            text="",
            font=self._info_font,
            fg=self.DIM_TEXT,
            bg=self.SECONDARY_BG,
            anchor="w",
            padx=10,
        )
        self._info_bar.pack(fill=tk.X, side=tk.BOTTOM, ipady=4)

        # ── Tkinter Hotkey (bring window to front) ───────────────────
        self._root.bind("<Alt-Shift-KeyPress-exclam>", self._on_hotkey)

        # ── Start Animations & Info Polling ─────────────────────────
        self._running = True
        self._animate_status()
        self._update_info_bar()
        self._animate_waveform()

        # Start system tray (optional)
        self._start_tray()

        # Welcome message
        self.add_message(
            "Hyper: Ready! Say 'Hey Hyper' or press Alt+Shift+1 to activate.",
            "hyper",
        )

    # ═══════════════════════════════════════════════════════════════
    #  RUN / CLOSE
    # ═══════════════════════════════════════════════════════════════
    def run(self):
        """Start the tkinter main loop (blocks — call from main thread)."""
        if self._root:
            self._root.mainloop()

    def _on_close(self):
        self._running = False
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        if self.pipeline:
            try:
                self.pipeline.stop()
            except Exception:
                pass
        if self._root:
            try:
                self._root.destroy()
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════
    #  PUBLIC STATE API  (called from pipeline / worker threads)
    # ═══════════════════════════════════════════════════════════════
    _STATUS_MAP = {
        "sleeping":   ("● Sleeping — Press Alt+Shift+1 to activate", "#666680"),
        "listening":  ("◉ Listening...",                              "#448aff"),
        "processing": ("⟳ Processing...",                             "#00e676"),
        "speaking":   ("♪ Speaking...",                               "#ff9100"),
        "error":      ("✕ Error",                                     "#e94560"),
    }

    def update_state(self, state: str):
        """
        Thread-safe state change.
        Valid states: 'sleeping' | 'listening' | 'processing' | 'speaking' | 'error'
        Also accepts enum objects with a .value attribute (for NOVA-style enums).
        """
        if hasattr(state, "value"):
            state = state.value
        self._state = str(state)
        text, color = self._STATUS_MAP.get(self._state, ("● Unknown", self.GREY))

        if self._root and self._status_label:
            try:
                self._root.after(0, lambda t=text, c=color:
                    self._status_label.configure(text=t, fg=c))
            except Exception:
                pass

    def add_message(self, message: str, tag: str = "system"):
        """Thread-safe: append a line to the conversation log."""
        if not self._log_widget:
            return

        def _add():
            try:
                # Auto-detect tag from message prefix
                if message.startswith("You:"):
                    t = "user"
                elif message.lower().startswith("hyper:"):
                    t = "hyper"
                elif tag == "error":
                    t = "error"
                else:
                    t = tag

                self._log_widget.configure(state=tk.NORMAL)
                self._log_widget.insert(tk.END, message + "\n", t)
                self._log_widget.see(tk.END)
                self._log_widget.configure(state=tk.DISABLED)
            except Exception:
                pass

        if self._root:
            try:
                self._root.after(0, _add)
            except Exception:
                pass

    def set_amplitude(self, value: float):
        """Feed real-time mic amplitude (0.0–1.0) for waveform display."""
        self._amplitude = max(0.0, min(1.0, float(value)))

    # ═══════════════════════════════════════════════════════════════
    #  INPUT HANDLERS
    # ═══════════════════════════════════════════════════════════════
    def _on_input_focus(self, _event):
        if self._input_entry.get() == "Type a command...":
            self._input_entry.delete(0, tk.END)
            self._input_entry.configure(fg=self.TEXT)

    def _on_input_unfocus(self, _event):
        if not self._input_entry.get():
            self._input_entry.insert(0, "Type a command...")
            self._input_entry.configure(fg=self.DIM_TEXT)

    def _on_input_submit(self, _event):
        text = self._input_entry.get().strip()
        if text and text != "Type a command...":
            self.add_message(f"You: {text}", "user")
            self._input_entry.delete(0, tk.END)
            if self.pipeline:
                threading.Thread(
                    target=self.pipeline.process_text_command,
                    args=(text,),
                    daemon=True,
                ).start()

    def _on_mic_click(self):
        """Mic button — same as saying the wake word."""
        if self.pipeline:
            self.pipeline.trigger_manually()

    def _on_hotkey(self, _event=None):
        if self._root:
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()

    # ═══════════════════════════════════════════════════════════════
    #  ANIMATIONS
    # ═══════════════════════════════════════════════════════════════
    def _animate_status(self):
        """Redraw the animated status circle every 50 ms."""
        if not self._running or not self._canvas:
            return
        try:
            self._canvas.delete("all")
            cx, cy   = 80, 80
            base_r   = 40
            colors   = {
                "sleeping":   self.GREY,
                "listening":  self.BLUE,
                "processing": self.GREEN,
                "speaking":   self.ORANGE,
                "error":      self.ACCENT,
            }
            color = colors.get(self._state, self.GREY)

            self._pulse_angle = (self._pulse_angle + 4) % 360
            pulse = math.sin(math.radians(self._pulse_angle))

            if self._state == "sleeping":
                r = base_r
                self._canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                         outline=color, width=3, fill="")
                self._canvas.create_oval(cx-5, cy-5, cx+5, cy+5,
                                         fill=color, outline="")

            elif self._state == "listening":
                r = base_r + pulse * 10
                for i in range(3):
                    gr = r + i * 8
                    self._canvas.create_oval(cx-gr, cy-gr, cx+gr, cy+gr,
                                             outline=color, width=2, fill="")
                self._canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                         outline=color, width=3, fill="")
                self._canvas.create_oval(cx-8, cy-8, cx+8, cy+8,
                                         fill=color, outline="")

            elif self._state == "processing":
                r = base_r
                for i in range(3):
                    start = (self._pulse_angle * 3 + i * 120) % 360
                    self._canvas.create_arc(
                        cx-r-i*6, cy-r-i*6, cx+r+i*6, cy+r+i*6,
                        start=start, extent=60, outline=color, width=3, style="arc")
                self._canvas.create_oval(cx-8, cy-8, cx+8, cy+8,
                                         fill=color, outline="")

            elif self._state == "speaking":
                r = base_r
                self._canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                         outline=color, width=3, fill="")
                for i in range(3):
                    wr = r + 12 + i * 10 + pulse * 5
                    for start_deg in (30, 210):
                        self._canvas.create_arc(
                            cx-wr, cy-wr, cx+wr, cy+wr,
                            start=start_deg, extent=120,
                            outline=color, width=2, style="arc")
                self._canvas.create_oval(cx-8, cy-8, cx+8, cy+8,
                                         fill=color, outline="")

            else:  # error
                r = base_r
                self._canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                         outline=color, width=3, fill="")
                self._canvas.create_line(cx-15, cy-15, cx+15, cy+15,
                                         fill=color, width=3)
                self._canvas.create_line(cx+15, cy-15, cx-15, cy+15,
                                         fill=color, width=3)

            self._root.after(50, self._animate_status)
        except Exception:
            pass

    def _animate_waveform(self):
        """Animate mic amplitude bars every 80 ms."""
        if not self._running or not self._waveform_canvas:
            return
        try:
            import random
            self._waveform_canvas.delete("all")
            w        = self._waveform_canvas.winfo_width()
            h        = 40
            num_bars = 30
            bar_w    = max(3, (w - num_bars) // num_bars)
            gap      = 2

            if self._state == "listening":
                for i in range(num_bars):
                    amp  = self._amplitude * 0.7 + random.random() * 0.3 * self._amplitude
                    cf   = 1.0 - abs(i - num_bars / 2) / (num_bars / 2) * 0.3
                    bh   = max(2, int(h * amp * cf))
                    x    = i * (bar_w + gap)
                    yt   = (h - bh) // 2
                    self._waveform_canvas.create_rectangle(
                        x, yt, x + bar_w, yt + bh,
                        fill=self.BLUE, outline="")
            else:
                y = h // 2
                for i in range(num_bars):
                    x = i * (bar_w + gap)
                    self._waveform_canvas.create_rectangle(
                        x, y-1, x + bar_w, y+1,
                        fill=self.GREY, outline="")

            self._root.after(80, self._animate_waveform)
        except Exception:
            pass

    def _update_info_bar(self):
        """Refresh the bottom status bar every 2 s."""
        if not self._running or not self._info_bar:
            return
        try:
            import psutil
            from datetime import datetime

            now  = datetime.now().strftime("%I:%M %p")
            cpu  = psutil.cpu_percent(interval=0)
            ram  = psutil.virtual_memory().percent
            text = f"  {now}   │   CPU: {cpu:.0f}%   │   RAM: {ram:.0f}%"

            batt = psutil.sensors_battery()
            if batt:
                plug  = "⚡" if batt.power_plugged else "🔋"
                text += f"   │   {plug} {batt.percent:.0f}%"

            self._info_bar.configure(text=text)
        except Exception:
            pass

        if self._root:
            self._root.after(2000, self._update_info_bar)

    # ═══════════════════════════════════════════════════════════════
    #  SYSTEM TRAY  (optional — needs pystray + Pillow)
    # ═══════════════════════════════════════════════════════════════
    def _start_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw

            img  = Image.new("RGB", (64, 64), self.BG)
            draw = ImageDraw.Draw(img)
            draw.ellipse([12, 12, 52, 52], fill=self.ACCENT)
            draw.text((20, 18), "H", fill="white")

            menu = pystray.Menu(
                pystray.MenuItem("Show Hyper AI", self._tray_show),
                pystray.MenuItem("Quit",          self._tray_quit),
            )
            self._tray_icon = pystray.Icon("HyperAI", img, "Hyper AI", menu)

            threading.Thread(target=self._tray_icon.run, daemon=True).start()
        except ImportError:
            logger.info("pystray not installed — no system tray icon.")
        except Exception as e:
            logger.warning(f"System tray error: {e}")

    def _tray_show(self, *_):
        if self._root:
            self._root.after(0, lambda: (
                self._root.deiconify(),
                self._root.lift(),
                self._root.focus_force(),
            ))

    def _tray_quit(self, *_):
        if self._tray_icon:
            self._tray_icon.stop()
        if self._root:
            self._root.after(0, self._on_close)
