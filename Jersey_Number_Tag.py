"""
Hudl Hybrid Auto-Tagger Pro (Fast Launch Edition)
Lazy-loads PyTorch, YOLO, EasyOCR, and Vosk to ensure < 0.5s GUI launch time.
"""

import json
import os
import queue
import re
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import Toplevel, messagebox
import pyautogui

# ============================================================
# GLOBAL SETTINGS & FILE PATHS
# ============================================================

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.04

GLOBAL_CONFIG_FILE = "hudl_global_config.json"
MODEL_PATH = Path(__file__).resolve().parent / "vosk"
SAMPLE_RATE = 16000
MANUAL_AUTO_SUBMIT_DELAY_MS = 600

SPEED_LEVELS = [0.5, 1.0, 1.5, 2.0, 2.5]
DEFAULT_SPEED_INDEX = 1  # 1.0x


# ============================================================
# CONFIGURATION HELPERS
# ============================================================

def load_global_config():
    if os.path.exists(GLOBAL_CONFIG_FILE):
        try:
            with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Config] Error loading config: {e}")
    return {
        "shared_ui": {
            "speed_menu": {},
            "video_neutral_click": [1200, 600]
        },
        "taggers": {
            "block": {
                "player_select_box": [1691, 392],
                "confirm_key": "y",
                "save_key": "e"
            }
        },
        "jersey_tagger": {
            "jersey_coords": None,
            "extra_coords": None,
            "video_roi": None
        }
    }

def save_global_config(config_data):
    try:
        with open(GLOBAL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"[Config] Error saving config: {e}")


# ============================================================
# SPOKEN NUMBER WORDS
# ============================================================

WORD_TO_NUM = {
    "zero": 0, "oh": 0,
    "one": 1, "won": 1, "juan": 1,
    "two": 2, "to": 2, "too": 2,
    "three": 3, "tree": 3,
    "four": 4, "for": 4, "fore": 4,
    "five": 5, "six": 6, "sex": 6,
    "seven": 7, "eight": 8, "ate": 8,
    "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}

TENS = {20, 30, 40, 50, 60, 70, 80, 90}

def parse_spoken_number(text):
    text = text.lower().strip()
    digit = re.search(r"\b(\d{1,2})\b", text)
    if digit:
        value = int(digit.group(1))
        if 0 <= value <= 99:
            return str(value)
        return None

    words = re.findall(r"[a-z]+", text)
    nums = [WORD_TO_NUM[w] for w in words if w in WORD_TO_NUM]
    if not nums:
        return None

    for i in range(len(nums) - 1, 0, -1):
        if nums[i - 1] in TENS and 1 <= nums[i] <= 9:
            val = nums[i - 1] + nums[i]
            if 1 <= val <= 99:
                return str(val)

    value = nums[-1] if (len(nums) > 1 and nums[-1] in range(1, 20)) else nums[0]
    if 1 <= value <= 99:
        return str(value)
    return None


# ============================================================
# CALIBRATION OVERLAYS
# ============================================================

class CalibrationOverlay:
    def __init__(self, parent, mode, callback):
        self.callback = callback
        self.mode = mode
        self.step = 1
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.first_coords = None

        self.window = Toplevel(parent)
        self.window.attributes("-fullscreen", True, "-topmost", True, "-alpha", 0.3)
        self.window.configure(bg="black")

        self.canvas = tk.Canvas(self.window, bg="black", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        if mode == "targets":
            self.instruction_text = self.canvas.create_text(
                30, 30, anchor="nw", fill="#00ff66",
                text="STEP 1/2: Click the Jersey # input. (Esc to cancel)",
                font=("Segoe UI", 16, "bold")
            )
            self.canvas.bind("<ButtonPress-1>", self.on_target_click)
        else:
            self.instruction_text = self.canvas.create_text(
                30, 30, anchor="nw", fill="#33ccff",
                text="Click and drag over the video playback grid. (Esc to cancel)",
                font=("Segoe UI", 16, "bold")
            )
            self.canvas.bind("<ButtonPress-1>", self.on_roi_start)
            self.canvas.bind("<B1-Motion>", self.on_roi_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_roi_end)

        self.window.bind("<Escape>", self.cancel)
        self.window.focus_force()

    def on_target_click(self, event):
        coords = (event.x_root, event.y_root)
        if self.step == 1:
            self.first_coords = coords
            self.step = 2
            self.canvas.itemconfig(
                self.instruction_text,
                fill="#33ccff",
                text="STEP 2/2: Click neutral video/canvas location (before pressing E)."
            )
            return

        if self.step == 2:
            second_coords = coords
            self.window.destroy()
            self.callback(self.first_coords, second_coords)

    def on_roi_start(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#00ff66", width=2
        )

    def on_roi_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x_root, event.y_root)

    def on_roi_end(self, event):
        x1, x2 = sorted((self.start_x, event.x_root))
        y1, y2 = sorted((self.start_y, event.y_root))
        self.window.destroy()

        if (x2 - x1 > 50) and (y2 - y1 > 50):
            self.callback({"top": y1, "left": x1, "width": x2 - x1, "height": y2 - y1})
        else:
            self.callback(None)

    def cancel(self, event=None):
        self.window.destroy()
        if self.mode == "roi":
            self.callback(None)
        else:
            self.callback(None, None)


# ============================================================
# MAIN APPLICATION
# ============================================================

class AutoTaggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hybrid Jersey Tagger Pro")
        self.root.geometry("540x450+40+80")
        self.root.attributes("-topmost", True)

        self.current_speed_idx = DEFAULT_SPEED_INDEX
        self.menu_is_open = False
        self.close_timer = None
        self.speed_lock = threading.Lock()

        # Load shared configuration
        self.config_data = load_global_config()
        jersey_cfg = self.config_data.get("jersey_tagger", {})
        
        self.jersey_coords = tuple(jersey_cfg["jersey_coords"]) if jersey_cfg.get("jersey_coords") else None
        self.extra_coords = tuple(jersey_cfg["extra_coords"]) if jersey_cfg.get("extra_coords") else None
        self.video_roi = jersey_cfg.get("video_roi")
        self.speed_coords = self.config_data.get("shared_ui", {}).get("speed_menu", {})

        self.is_scanning = False
        self.detection_paused = False
        self.cooldown_until = 0
        self.voice_listening_active = False
        self.speech_tag_active = False
        self.voice_thread = None

        self.manual_mode = "auto"
        self.manual_submit_job = None

        # Models initialized lazily to eliminate startup freeze
        self.vosk_model = None
        self.yolo_model = None
        self.ocr_reader = None
        self.audio_queue = queue.Queue(maxsize=100)

        self._build_ui()

        self.root.bind_all("<KeyPress>", self._global_key_handler, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        tk.Label(
            self.root,
            text="YOLOv8 + Offline Voice + Speed (O/P) + Manual Tag",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=14, pady=(10, 2))

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=14, pady=5)

        tk.Button(btn_frame, text="1. Set Targets", width=12, command=self.calibrate_targets).pack(side="left", padx=(0, 4))
        tk.Button(btn_frame, text="2. Set Video ROI", width=13, command=self.calibrate_roi).pack(side="left", padx=(0, 4))

        self.manual_mode_btn = tk.Button(
            btn_frame, text="M: Auto Submit", width=13, bg="#008000", fg="white", command=self.toggle_manual_mode
        )
        self.manual_mode_btn.pack(side="left", padx=(0, 4))

        self.speech_btn = tk.Button(btn_frame, text="3. Speech (B)", width=12, command=self.toggle_speech_tag)
        self.speech_btn.pack(side="left")

        tk.Label(
            self.root,
            text="Nav: J (◀) | L (▶) | K (⏸/▶) | Speed: O (Down), P (Up) | Q: Exit\n"
                 "Hotkeys: B = Voice Toggle | C = Scan Toggle | X = Targets | V = ROI | M = Mode",
            font=("Segoe UI", 8, "bold"),
            fg="#444",
            justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 4))

        self.speed_hud_label = tk.Label(
            self.root,
            text=f"Active Playback Speed: {SPEED_LEVELS[self.current_speed_idx]}x",
            font=("Segoe UI", 10, "bold"),
            fg="#2e7d32"
        )
        self.speed_hud_label.pack(anchor="w", padx=14, pady=(0, 4))

        manual_frame = tk.Frame(self.root)
        manual_frame.pack(fill="x", padx=14, pady=6)

        tk.Label(manual_frame, text="Manual Tag:", font=("Segoe UI", 9, "bold")).pack(side="left")

        self.entry = tk.Entry(manual_frame, font=("Consolas", 12), width=10, justify="center")
        self.entry.pack(side="left", padx=8)

        validate_cmd = (self.root.register(self._validate_manual_input), "%P")
        self.entry.configure(validate="key", validatecommand=validate_cmd)
        self.entry.bind("<Return>", self.manual_submit)
        self.entry.bind("<KeyPress>", self._manual_key_pressed)
        self.entry.bind("<KeyRelease>", self._manual_key_released)

        tk.Button(manual_frame, text="Tag", width=8, command=self.manual_submit).pack(side="left")

        self.toggle_btn = tk.Button(
            self.root,
            text="Start Auto Scan (C)",
            bg="#008000",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            command=self.toggle_scanning
        )
        self.toggle_btn.pack(fill="x", padx=14, pady=(4, 6))

        tk.Button(
            self.root,
            text="Open Interactive Block Tagger",
            bg="#0055cc",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            command=self.open_block_tagger
        ).pack(fill="x", padx=14, pady=(0, 6))

        init_status = "Ready. Targets & ROI loaded from config." if (self.jersey_coords and self.video_roi) else "Set Targets & Video ROI to begin."
        self.status = tk.Label(
            self.root, text=init_status, wraplength=500, justify="left", font=("Segoe UI", 9), fg="#333"
        )
        self.status.pack(fill="x", padx=14, pady=2)

        self.timer_label = tk.Label(self.root, text="Offline voice: Standby", font=("Segoe UI", 8, "italic"), fg="#666")
        self.timer_label.pack(fill="x", padx=14, pady=(0, 6))

        self.entry.focus_set()

    def open_block_tagger(self):
        # Lazy import so blocksystem doesn't slow down initial script startup
        from blocksystem import InteractiveHudlTagger
        block_window = tk.Toplevel(self.root)
        InteractiveHudlTagger(block_window)

    def calibrate_targets(self):
        self.root.withdraw()
        self.root.after(200, lambda: CalibrationOverlay(self.root, "targets", self._on_targets_done))

    def _on_targets_done(self, jersey_coords, extra_coords):
        self.root.deiconify()
        if jersey_coords and extra_coords:
            self.jersey_coords = jersey_coords
            self.extra_coords = extra_coords
            
            self.config_data.setdefault("jersey_tagger", {})["jersey_coords"] = list(jersey_coords)
            self.config_data.setdefault("jersey_tagger", {})["extra_coords"] = list(extra_coords)
            save_global_config(self.config_data)

            self.status.config(text=f"Targets Saved: Jersey {jersey_coords} | Neutral {extra_coords}", fg="#007700")
            self.restore_focus()

    def calibrate_roi(self):
        self.root.withdraw()
        self.root.after(200, lambda: CalibrationOverlay(self.root, "roi", self._on_roi_done))

    def _on_roi_done(self, roi):
        self.root.deiconify()
        if roi:
            self.video_roi = roi
            self.config_data.setdefault("jersey_tagger", {})["video_roi"] = roi
            save_global_config(self.config_data)

            self.status.config(text=f"ROI Saved: {roi['width']}x{roi['height']} at ({roi['left']}, {roi['top']})", fg="#007700")
            self.restore_focus()

    # ========================================================
    # PLAYBACK SPEED AUTOMATION (O & P)
    # ========================================================
    def trigger_speed_change(self, direction):
        if not self.speed_coords:
            self.status.config(text="Map speed menu in Block Tagger first to load coordinates.", fg="#b30000")
            return

        if direction == "down":
            if self.current_speed_idx > 0:
                self.current_speed_idx -= 1
            else:
                self.status.config(text="Already at minimum speed (0.5x)", fg="orange")
                return
        elif direction == "up":
            if self.current_speed_idx < len(SPEED_LEVELS) - 1:
                self.current_speed_idx += 1
            else:
                self.status.config(text="Already at maximum speed (2.5x)", fg="orange")
                return

        target_speed_str = f"{SPEED_LEVELS[self.current_speed_idx]:.1f}"
        self.speed_hud_label.config(text=f"Active Playback Speed: {target_speed_str}x")
        threading.Thread(target=self._execute_smart_speed_sequence, args=(target_speed_str,), daemon=True).start()

    def _execute_smart_speed_sequence(self, speed_str):
        with self.speed_lock:
            if self.close_timer and self.close_timer.is_alive():
                self.close_timer.cancel()

            menu_btn = self.speed_coords.get("menu_btn")
            speed_coord = self.speed_coords.get(speed_str)

            try:
                if not self.menu_is_open:
                    pyautogui.click(menu_btn[0], menu_btn[1])
                    self.menu_is_open = True
                    time.sleep(0.38)

                pyautogui.click(speed_coord[0], speed_coord[1])
                self.status.config(text=f"Speed: {speed_str}x (Menu open)", fg="#007700")
                self.root.after(0, self.restore_focus)
            except Exception as e:
                self.status.config(text=f"Speed error: {str(e)}", fg="#b30000")

            self.close_timer = threading.Timer(3.0, self._close_speed_menu)
            self.close_timer.daemon = True
            self.close_timer.start()

    def _close_speed_menu(self):
        with self.speed_lock:
            if not self.menu_is_open:
                return

            exit_coord = self.speed_coords.get("menu_exit")
            if exit_coord:
                try:
                    pyautogui.click(exit_coord[0], exit_coord[1])
                except Exception:
                    pass

            self.menu_is_open = False
            self.status.config(text=f"Speed: {SPEED_LEVELS[self.current_speed_idx]}x. Menu closed.", fg="#0066cc")
            self.root.after(0, self.restore_focus)

    # ========================================================
    # RELIABLE MEDIA CONTROLS
    # ========================================================
    def send_hudl_key(self, key):
        key = key.lower()
        action_map = {"j": "left", "l": "right", "k": "space"}
        output_key = action_map.get(key, key)

        if self.extra_coords:
            click_x, click_y = self.extra_coords
        elif self.jersey_coords:
            click_x, click_y = self.jersey_coords[0], self.jersey_coords[1] + 250
        else:
            self.status.config(text="Set Targets first to enable media control clicks.", fg="#b30000")
            return

        try:
            pyautogui.click(click_x, click_y)
            time.sleep(0.06)
            pyautogui.press(output_key)

            display_names = {
                "left": "LEFT ARROW (5s back)",
                "right": "RIGHT ARROW (5s forward)",
                "space": "SPACE (play/pause)",
            }
            display = display_names.get(output_key, output_key.upper())
            self.status.config(text=f"Sent {display} to Hudl.", fg="#007700")
        except Exception as exc:
            self.status.config(text=f"Key action error: {exc}", fg="#b30000")
        finally:
            self.root.after(40, self.restore_focus)

    def _validate_manual_input(self, proposed):
        if proposed == "":
            return True
        if not re.fullmatch(r"\d{1,2}", proposed):
            return False
        return 0 <= int(proposed) <= 99

    def _global_key_handler(self, event):
        key = event.keysym.lower()

        if key == "q":
            self.close()
            return "break"
        if key == "m":
            self.toggle_manual_mode()
            return "break"
        if key == "x":
            self.calibrate_targets()
            return "break"
        if key == "v":
            self.calibrate_roi()
            return "break"
        if key == "b":
            self.toggle_speech_tag()
            return "break"
        if key == "c":
            self.toggle_scanning()
            return "break"
        if key == "o":
            self.trigger_speed_change("down")
            return "break"
        if key == "p":
            self.trigger_speed_change("up")
            return "break"
        if key in {"j", "l", "k"}:
            self.send_hudl_key(key)
            return "break"
        if len(key) == 1 and key.isalpha():
            self.send_hudl_key(key)
            return "break"

    def _manual_key_pressed(self, event):
        key = event.keysym.lower()

        if key == "q":
            self.close()
            return "break"
        if key == "m":
            self.toggle_manual_mode()
            return "break"
        if key == "x":
            self.calibrate_targets()
            return "break"
        if key == "v":
            self.calibrate_roi()
            return "break"
        if key == "b":
            self.toggle_speech_tag()
            return "break"
        if key == "c":
            self.toggle_scanning()
            return "break"
        if key == "o":
            self.trigger_speed_change("down")
            return "break"
        if key == "p":
            self.trigger_speed_change("up")
            return "break"
        if key in {"j", "l", "k"}:
            self.send_hudl_key(key)
            return "break"
        if len(key) == 1 and key.isalpha():
            self.send_hudl_key(key)
            return "break"

        if event.keysym in {"BackSpace", "Delete", "Left", "Right", "Home", "End", "Return", "KP_Enter", "Tab"}:
            return None

        if event.keysym not in "0123456789":
            return "break"

        current = self.entry.get()
        if self.entry.selection_present():
            start = self.entry.index(tk.SEL_FIRST)
            end = self.entry.index(tk.SEL_LAST)
        else:
            start = self.entry.index(tk.INSERT)
            end = start

        proposed = current[:start] + event.keysym + current[end:]
        if len(proposed) > 2:
            return "break"
        return None

    def toggle_manual_mode(self):
        if self.manual_mode == "auto":
            self.manual_mode = "enter"
            self._cancel_manual_submit_timer()
            self.manual_mode_btn.config(text="M: Enter Submit", bg="#0055cc", fg="white")
            self.status.config(text="Manual mode: ENTER SUBMIT. Type a number and press Enter.", fg="black")
        else:
            self.manual_mode = "auto"
            self.manual_mode_btn.config(text="M: Auto Submit", bg="#008000", fg="white")
            self.status.config(text=f"Manual mode: AUTO SUBMIT. Waiting {MANUAL_AUTO_SUBMIT_DELAY_MS/1000:.1f}s after digits.", fg="black")
            self._schedule_manual_submit()
        self.entry.focus_set()

    def _cancel_manual_submit_timer(self):
        if self.manual_submit_job is not None:
            try:
                self.root.after_cancel(self.manual_submit_job)
            except Exception:
                pass
            self.manual_submit_job = None

    def _manual_key_released(self, event=None):
        if self.manual_mode == "auto":
            self._schedule_manual_submit()

    def _schedule_manual_submit(self):
        self._cancel_manual_submit_timer()
        raw = self.entry.get().strip().lstrip("#").strip()
        if not re.fullmatch(r"\d{1,2}", raw) or not 0 <= int(raw) <= 99:
            return

        self.manual_submit_job = self.root.after(
            MANUAL_AUTO_SUBMIT_DELAY_MS, lambda val=raw: self._auto_submit_manual(val)
        )
        self.status.config(text=f"Waiting {MANUAL_AUTO_SUBMIT_DELAY_MS/1000:.1f}s to auto-submit #{raw}...", fg="#555")

    def _auto_submit_manual(self, expected_value):
        self.manual_submit_job = None
        if self.manual_mode != "auto":
            return
        current = self.entry.get().strip().lstrip("#").strip()
        if current != expected_value:
            self._schedule_manual_submit()
            return
        self.manual_submit()

    def manual_submit(self, event=None):
        self._cancel_manual_submit_timer()
        if not self.jersey_coords or not self.extra_coords:
            self.status.config(text="Error: Set Targets first.", fg="#b30000")
            return

        raw = self.entry.get().strip().lstrip("#").strip()
        if not re.fullmatch(r"\d{1,2}", raw) or not 0 <= int(raw) <= 99:
            self.status.config(text="Enter a jersey number from 0 to 99.", fg="#b30000")
            return

        self.entry.delete(0, tk.END)
        self.detection_paused = True
        self.status.config(text=f"Manual tagging #{raw}...", fg="black")
        threading.Thread(target=self.run_tag_and_save, args=(raw,), daemon=True).start()

    # ========================================================
    # SPEECH & AUTO-SCAN PROCESSING (LAZY LOADED)
    # ========================================================
    def toggle_speech_tag(self):
        if self.speech_tag_active:
            self.speech_tag_active = False
            self.speech_btn.config(text="3. Speech (B)", bg="SystemButtonFace", fg="black")
            self.timer_label.config(text="Speech tag: Off", fg="#666")
            self.status.config(text="Speech tagging stopped.", fg="black")
            return

        if not self.jersey_coords or not self.extra_coords:
            messagebox.showwarning("Missing Targets", "Click '1. Set Targets' first.")
            return

        self.speech_tag_active = True
        self.speech_btn.config(text="Stop Speech (B)", bg="#cc0000", fg="white")
        self.status.config(text="Loading offline Vosk voice engine...", fg="black")
        threading.Thread(target=self._start_speech_tag_worker, daemon=True).start()

    def _start_speech_tag_worker(self):
        try:
            if self.vosk_model is None:
                # Lazy import Vosk
                from vosk import Model
                if not MODEL_PATH.is_dir():
                    raise FileNotFoundError(f"Vosk model folder not found: {MODEL_PATH}")
                self.vosk_model = Model(str(MODEL_PATH))

            self.root.after(0, lambda: self.status.config(text="Speech tagging active. Say jersey # (e.g. 7)", fg="#007700"))
            self.root.after(0, self._start_voice_listener)
        except Exception as exc:
            self.speech_tag_active = False
            self.root.after(0, lambda e=str(exc): self.status.config(text=f"Speech tag error: {e}", fg="#b30000"))

    def toggle_scanning(self):
        if self.is_scanning:
            self.is_scanning = False
            self.toggle_btn.config(text="Start Auto Scan (C)", bg="#008000")
            self.status.config(text="Scan stopped.", fg="black")
            if not self.speech_tag_active:
                self.timer_label.config(text="Offline voice: Standby", fg="#666")
            return

        if not self.jersey_coords or not self.extra_coords:
            messagebox.showwarning("Missing Targets", "Calibrate click targets first.")
            return
        if not self.video_roi:
            messagebox.showwarning("Missing ROI", "Define video playback region first.")
            return

        self.is_scanning = True
        self.toggle_btn.config(text="Stop Auto Scan (C)", bg="#cc0000")
        self.status.config(text="Spinning up YOLO, EasyOCR, and Vosk in background...", fg="black")
        threading.Thread(target=self._init_and_run_worker, daemon=True).start()

    def _init_and_run_worker(self):
        try:
            # Lazy imports for heavy vision frameworks
            if self.yolo_model is None:
                from ultralytics import YOLO
                self.yolo_model = YOLO("yolov8n.pt")
            if self.ocr_reader is None:
                import easyocr
                self.ocr_reader = easyocr.Reader(["en"], gpu=True)
            if self.vosk_model is None:
                from vosk import Model
                if not MODEL_PATH.is_dir():
                    raise FileNotFoundError(f"Vosk folder missing: {MODEL_PATH}")
                self.vosk_model = Model(str(MODEL_PATH))
        except Exception as exc:
            self.root.after(0, lambda e=str(exc): self.status.config(text=f"Startup error: {e}", fg="#b30000"))
            return

        self.root.after(0, lambda: self.status.config(text="Active: scanning video feed...", fg="#007700"))
        self.root.after(0, self._start_voice_listener)

        import mss
        import cv2
        import numpy as np

        try:
            with mss.mss() as sct:
                while self.is_scanning or self.speech_tag_active:
                    if self.detection_paused or time.time() < self.cooldown_until:
                        time.sleep(0.1)
                        continue

                    frame = np.array(sct.grab(self.video_roi))
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    results = self.yolo_model(frame, classes=[0], verbose=False, conf=0.5)

                    found = False
                    for result in results:
                        if result.boxes is None:
                            continue
                        for box in result.boxes.xyxy.cpu().numpy():
                            x1, y1, x2, y2 = map(int, box)
                            h = y2 - y1
                            crop = frame[max(0, y1 + int(h * 0.10)): min(frame.shape[0], y1 + int(h * 0.70)), max(0, x1): min(frame.shape[1], x2)]
                            if crop.size == 0 or crop.shape[0] < 20 or crop.shape[1] < 20:
                                continue

                            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                            gray = clahe.apply(gray)
                            gray = cv2.copyMakeBorder(gray, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[255, 255, 255])

                            for (bbox, text, prob) in self.ocr_reader.readtext(
                                gray, allowlist="0123456789", mag_ratio=2.0, text_threshold=0.5, low_text=0.3
                            ):
                                clean = text.strip()
                                if re.fullmatch(r"\d{1,2}", clean) and 0 <= int(clean) <= 99 and prob > 0.35:
                                    self.detection_paused = True
                                    self.root.after(0, self._trigger_auto_tag, clean, "OCR")
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            break
                    time.sleep(0.08)
        except Exception as exc:
            self.root.after(0, lambda e=str(exc): self.status.config(text=f"Scan error: {e}", fg="#b30000"))

    def _start_voice_listener(self):
        if not (self.is_scanning or self.speech_tag_active) or self.voice_listening_active:
            return
        self.voice_listening_active = True
        self.voice_thread = threading.Thread(target=self._listen_for_voice, daemon=True)
        self.voice_thread.start()

    def _listen_for_voice(self):
        tag_started = False
        try:
            from vosk import KaldiRecognizer
            import sounddevice as sd

            recognizer = KaldiRecognizer(self.vosk_model, SAMPLE_RATE)
            recognizer.SetWords(True)
            self.root.after(0, lambda: self.timer_label.config(text="Speech listening: say a number (0-99)", fg="#cc6600"))

            def callback(indata, frames, time_info, status):
                try:
                    self.audio_queue.put_nowait(bytes(indata))
                except queue.Full:
                    pass

            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break

            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=4000, dtype="int16", channels=1, callback=callback):
                while self.is_scanning or self.speech_tag_active:
                    try:
                        data = self.audio_queue.get(timeout=0.25)
                    except queue.Empty:
                        continue

                    if not recognizer.AcceptWaveform(data):
                        continue

                    heard = json.loads(recognizer.Result()).get("text", "").lower().strip()
                    if not heard:
                        continue

                    number = parse_spoken_number(heard)
                    if number is not None and (self.is_scanning or self.speech_tag_active):
                        self.detection_paused = True
                        tag_started = True
                        self.root.after(0, self._trigger_auto_tag, number, "Voice")
                        break
        except Exception as exc:
            self.root.after(0, lambda e=str(exc): self.timer_label.config(text=f"Vosk error: {e}", fg="#b30000"))
        finally:
            self.voice_listening_active = False
            if (self.is_scanning or self.speech_tag_active) and not tag_started:
                self.detection_paused = False
                self.root.after(1000, self._start_voice_listener)

    def _trigger_auto_tag(self, number, source):
        self.status.config(text=f"Auto-tagging #{number} via {source}...", fg="black")
        self.timer_label.config(text=f"Recognized #{number} via {source}", fg="#007700")
        threading.Thread(target=self.run_tag_and_save, args=(number,), daemon=True).start()

    def run_tag_and_save(self, number):
        try:
            jx, jy = self.jersey_coords
            ex, ey = self.extra_coords

            pyautogui.click(jx, jy)
            time.sleep(0.10)
            pyautogui.write(str(number))
            time.sleep(0.10)
            pyautogui.press("enter")
            time.sleep(0.15)
            pyautogui.click(ex, ey)
            time.sleep(0.15)
            pyautogui.press("e")
            time.sleep(0.15)

            self.root.after(0, lambda: self.status.config(text=f"Successfully tagged #{number}.", fg="#007700"))
        except Exception as exc:
            self.root.after(0, lambda e=str(exc): self.status.config(text=f"Tagging error: {e}", fg="#b30000"))
        finally:
            self.cooldown_until = time.time() + 2.5
            self.detection_paused = False
            self.root.after(100, self.restore_focus)

            if self.is_scanning or self.speech_tag_active:
                self.root.after(1000, self._start_voice_listener)

    def restore_focus(self):
        if self.root.winfo_exists():
            self.root.lift()
            self.root.focus_force()
            self.entry.focus_set()

    def close(self):
        self._cancel_manual_submit_timer()
        self.is_scanning = False
        self.speech_tag_active = False
        self.root.destroy()


# ============================================================
# DUAL MONITOR PLACEMENT
# ============================================================

def move_to_monitor_2(root):
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        monitors = []

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
        )

        def enum_callback(hmonitor, hdc, rect, lparam):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                monitors.append((
                    info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom, bool(info.dwFlags & 1)
                ))
            return 1

        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(enum_callback), 0)

        if len(monitors) >= 2:
            non_primary = [m for m in monitors if not m[4]]
            left, top, _, _, _ = non_primary[0] if non_primary else monitors[1]
            root.geometry(f"540x450+{left + 20}+{top + 20}")
            return
    except Exception:
        pass

    root.geometry("540x450+40+80")


if __name__ == "__main__":
    root = tk.Tk()
    move_to_monitor_2(root)
    AutoTaggerApp(root)
    root.mainloop()