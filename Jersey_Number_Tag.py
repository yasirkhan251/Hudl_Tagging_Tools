"""
Hudl Hybrid Auto-Tagger
YOLOv8 + EasyOCR + Offline Vosk Voice + Manual Entry 

Install:
    python -m pip install ultralytics easyocr mss pyautogui opencv-python pillow vosk sounddevice numpy

Place the extracted Vosk model folder named 'vosk' beside this script.

Run:
    python wakeup_vosk_speech_button.py
"""

import json
import queue
import re
import threading
import time
from pathlib import Path
from blocksystem import InteractiveHudlTagger
import tkinter as tk
from tkinter import Toplevel, messagebox

import cv2
import easyocr
import mss
import numpy as np
import pyautogui
import sounddevice as sd

from ultralytics import YOLO
from vosk import Model, KaldiRecognizer


# ============================================================
# GLOBAL SETTINGS
# ============================================================

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.04

MODEL_PATH = Path(__file__).resolve().parent / "vosk"

SAMPLE_RATE = 16000

# Manual jersey-number auto-submit delay.
# Every digit typed resets this timer, so values such as 21 or 32
# can be entered naturally before the tag is submitted.
MANUAL_AUTO_SUBMIT_DELAY_MS = 1200


# ============================================================
# SPOKEN NUMBER WORDS
# ============================================================

WORD_TO_NUM = {
    "zero": 0,
    "oh": 0,

    "one": 1,
    "won": 1,
    "juan": 1,

    "two": 2,
    "to": 2,
    "too": 2,

    "three": 3,
    "tree": 3,

    "four": 4,
    "for": 4,
    "fore": 4,

    "five": 5,

    "six": 6,
    "sex": 6,

    "seven": 7,

    "eight": 8,
    "ate": 8,

    "nine": 9,

    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,

    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

TENS = {
    20,
    30,
    40,
    50,
    60,
    70,
    80,
    90,
}


# ============================================================
# PARSE SPOKEN NUMBER
# ============================================================

def parse_spoken_number(text):
    """
    Convert spoken number to a string.

    Examples:

        "7"              -> "7"
        "seven"          -> "7"
        "twenty three"   -> "23"
        "thirty five"    -> "35"

    Valid range:
        0 - 99
    """

    text = text.lower().strip()

    # --------------------------------------------------------
    # Direct numeric recognition
    # --------------------------------------------------------

    digit = re.search(
        r"\b(\d{1,2})\b",
        text
    )

    if digit:

        value = int(
            digit.group(1)
        )

        if 0 <= value <= 99:
            return str(value)

        return None

    # --------------------------------------------------------
    # Spoken words
    # --------------------------------------------------------

    words = re.findall(
        r"[a-z]+",
        text
    )

    nums = [
        WORD_TO_NUM[word]
        for word in words
        if word in WORD_TO_NUM
    ]

    if not nums:
        return None

    # --------------------------------------------------------
    # Handle:
    #
    # twenty three
    # thirty five
    # forty seven
    # --------------------------------------------------------

    for i in range(
        len(nums) - 1,
        0,
        -1
    ):

        if (
            nums[i - 1] in TENS
            and
            1 <= nums[i] <= 9
        ):

            value = (
                nums[i - 1]
                +
                nums[i]
            )

            if 1 <= value <= 99:
                return str(value)

    # --------------------------------------------------------
    # Simple number
    # --------------------------------------------------------

    value = (
        nums[-1]
        if (
            len(nums) > 1
            and
            nums[-1] in range(1, 20)
        )
        else nums[0]
    )

    if 1 <= value <= 99:
        return str(value)

    return None


# ============================================================
# CALIBRATION OVERLAY
# ============================================================

class CalibrationOverlay:

    def __init__(
        self,
        parent,
        mode,
        callback
    ):

        self.callback = callback

        self.mode = mode

        self.step = 1

        self.start_x = None
        self.start_y = None

        self.rect_id = None

        self.first_coords = None

        # ----------------------------------------------------
        # Window
        # ----------------------------------------------------

        self.window = Toplevel(
            parent
        )

        self.window.attributes(
            "-fullscreen",
            True
        )

        self.window.attributes(
            "-topmost",
            True
        )

        self.window.attributes(
            "-alpha",
            0.3
        )

        self.window.configure(
            bg="black"
        )

        # ----------------------------------------------------
        # Canvas
        # ----------------------------------------------------

        self.canvas = tk.Canvas(
            self.window,
            bg="black",
            cursor="crosshair",
            highlightthickness=0
        )

        self.canvas.pack(
            fill="both",
            expand=True
        )

        # ====================================================
        # TARGET CALIBRATION
        # ====================================================

        if mode == "targets":

            self.instruction_text = (
                self.canvas.create_text(
                    30,
                    30,
                    anchor="nw",
                    fill="#00ff66",
                    text=(
                        "STEP 1/2: "
                        "Click the Jersey # input. "
                        "(Esc to cancel)"
                    ),
                    font=(
                        "Segoe UI",
                        16,
                        "bold"
                    )
                )
            )

            self.canvas.bind(
                "<ButtonPress-1>",
                self.on_target_click
            )

        # ====================================================
        # VIDEO ROI CALIBRATION
        # ====================================================

        else:

            self.instruction_text = (
                self.canvas.create_text(
                    30,
                    30,
                    anchor="nw",
                    fill="#33ccff",
                    text=(
                        "Click and drag over the "
                        "video feed/player grid. "
                        "(Esc to cancel)"
                    ),
                    font=(
                        "Segoe UI",
                        16,
                        "bold"
                    )
                )
            )

            self.canvas.bind(
                "<ButtonPress-1>",
                self.on_roi_start
            )

            self.canvas.bind(
                "<B1-Motion>",
                self.on_roi_drag
            )

            self.canvas.bind(
                "<ButtonRelease-1>",
                self.on_roi_end
            )

        self.window.bind(
            "<Escape>",
            self.cancel
        )

        self.window.focus_force()

    # ========================================================
    # TARGET CALIBRATION
    # ========================================================

    def on_target_click(
        self,
        event
    ):

        coords = (
            event.x_root,
            event.y_root
        )

        # ----------------------------------------------------
        # STEP 1
        # Jersey number input
        # ----------------------------------------------------

        if self.step == 1:

            self.first_coords = coords

            self.step = 2

            self.canvas.itemconfig(
                self.instruction_text,
                fill="#33ccff",
                text=(
                    "STEP 2/2: "
                    "Click the second location "
                    "where the mouse should click "
                    "before pressing E."
                )
            )

            return

        # ----------------------------------------------------
        # STEP 2
        # Second mouse location
        # ----------------------------------------------------

        if self.step == 2:

            second_coords = coords

            self.window.destroy()

            self.callback(
                self.first_coords,
                second_coords
            )

    # ========================================================
    # ROI START
    # ========================================================

    def on_roi_start(
        self,
        event
    ):

        self.start_x = event.x_root

        self.start_y = event.y_root

        self.rect_id = (
            self.canvas.create_rectangle(
                event.x,
                event.y,
                event.x,
                event.y,
                outline="#00ff66",
                width=2
            )
        )

    # ========================================================
    # ROI DRAG
    # ========================================================

    def on_roi_drag(
        self,
        event
    ):

        if self.rect_id:

            self.canvas.coords(
                self.rect_id,
                self.start_x,
                self.start_y,
                event.x_root,
                event.y_root
            )

    # ========================================================
    # ROI END
    # ========================================================

    def on_roi_end(
        self,
        event
    ):

        x1, x2 = sorted(
            (
                self.start_x,
                event.x_root
            )
        )

        y1, y2 = sorted(
            (
                self.start_y,
                event.y_root
            )
        )

        self.window.destroy()

        if (
            x2 - x1 > 50
            and
            y2 - y1 > 50
        ):

            self.callback(
                {
                    "top": y1,
                    "left": x1,
                    "width": x2 - x1,
                    "height": y2 - y1
                }
            )

        else:

            self.callback(
                None
            )

    # ========================================================
    # CANCEL
    # ========================================================

    def cancel(
        self,
        event=None
    ):

        self.window.destroy()

        if self.mode == "roi":

            self.callback(
                None
            )

        else:

            self.callback(
                None,
                None
            )


# ============================================================
# MAIN APPLICATION
# ============================================================

class AutoTaggerApp:

    def __init__(
        self,
        root
    ):

        self.root = root

        self.root.title(
            "Hybrid Jersey Tagger - Offline Vosk"
        )

        self.root.geometry(
            "480x370+40+80"
        )

        self.root.attributes(
            "-topmost",
            True
        )

        # ----------------------------------------------------
        # TWO CLICK COORDINATES
        # ----------------------------------------------------

        # First click:
        # Jersey number input

        self.jersey_coords = None

        # Second click:
        # Location to click after Enter

        self.extra_coords = None

        # ----------------------------------------------------
        # VIDEO
        # ----------------------------------------------------

        self.video_roi = None

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        self.is_scanning = False

        self.detection_paused = False

        self.cooldown_until = 0

        self.voice_listening_active = False

        self.speech_tag_active = False

        self.voice_thread = None

        # ----------------------------------------------------
        # MANUAL TAG MODE
        # ----------------------------------------------------

        # "auto"   = submit automatically after a short pause
        # "enter"  = wait for Enter before submitting
        self.manual_mode = "auto"
        self.manual_submit_job = None

        # ----------------------------------------------------
        # MODELS
        # ----------------------------------------------------

        self.vosk_model = None

        self.yolo_model = None

        self.ocr_reader = None

        # ----------------------------------------------------
        # AUDIO QUEUE
        # ----------------------------------------------------

        self.audio_queue = queue.Queue(
            maxsize=100
        )

        # ----------------------------------------------------
        # UI
        # ----------------------------------------------------

        self._build_ui()

        # M toggles manual submission mode anywhere in this window.
        self.root.bind_all(
            "<KeyPress>",
            self._global_key_handler,
            add="+"
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

    # ========================================================
    # BUILD UI
    # ========================================================

    def _build_ui(self):

        tk.Label(
            self.root,
            text=(
                "YOLOv8 + Offline Voice + "
                "Manual Override + Block Trigger"
            ),
            font=(
                "Segoe UI",
                12,
                "bold"
            )
        ).pack(
            anchor="w",
            padx=14,
            pady=(10, 4)
        )

        # ----------------------------------------------------
        # TOP BUTTONS
        # ----------------------------------------------------

        btn_frame = tk.Frame(
            self.root
        )

        btn_frame.pack(
            fill="x",
            padx=14,
            pady=5
        )

        # ----------------------------------------------------
        # BUTTON 1
        # ----------------------------------------------------

        tk.Button(
            btn_frame,
            text="1. Set Targets",
            width=14,
            command=self.calibrate_targets
        ).pack(
            side="left",
            padx=(0, 6)
        )

        # ----------------------------------------------------
        # BUTTON 2
        # ----------------------------------------------------

        tk.Button(
            btn_frame,
            text="2. Set Video ROI",
            width=14,
            command=self.calibrate_roi
        ).pack(
            side="left",
            padx=(0, 6)
        )

        # ----------------------------------------------------
        # MANUAL MODE BUTTON
        # ----------------------------------------------------

        self.manual_mode_btn = tk.Button(
            btn_frame,
            text="M: Auto Submit",
            width=14,
            command=self.toggle_manual_mode
        )

        self.manual_mode_btn.pack(
            side="left",
            padx=(0, 6)
        )

        # ----------------------------------------------------
        # KEYBOARD ACTION MODE
        # ----------------------------------------------------

        tk.Label(
            btn_frame,
            text="X = Targets | V = ROI | L = Voice | M = Mode | Q = Exit",
            font=("Segoe UI", 8, "bold"),
            fg="#555555"
        ).pack(
            side="left",
            padx=(2, 0)
        )

        # ----------------------------------------------------
        # BUTTON 3
        # ----------------------------------------------------

        self.speech_btn = tk.Button(
            btn_frame,
            text="3. Speech Tag",
            width=14,
            command=self.toggle_speech_tag
        )

        self.speech_btn.pack(
            side="left"
        )

        # ----------------------------------------------------
        # MANUAL TAG
        # ----------------------------------------------------

        manual_frame = tk.Frame(
            self.root
        )

        manual_frame.pack(
            fill="x",
            padx=14,
            pady=10
        )

        tk.Label(
            manual_frame,
            text="Manual Tag:",
            font=(
                "Segoe UI",
                9,
                "bold"
            )
        ).pack(
            side="left"
        )

        self.entry = tk.Entry(
            manual_frame,
            font=(
                "Consolas",
                12
            ),
            width=12
        )

        self.entry.pack(
            side="left",
            padx=8
        )

        # Tk validation also blocks pasted letters/symbols.
        validate_cmd = (
            self.root.register(self._validate_manual_input),
            "%P"
        )

        self.entry.configure(
            validate="key",
            validatecommand=validate_cmd
        )

        self.entry.bind(
            "<Return>",
            self.manual_submit
        )

        # Keep the Manual Tag field numeric-only.
        self.entry.bind(
            "<KeyPress>",
            self._manual_key_pressed
        )

        self.entry.bind(
            "<KeyRelease>",
            self._manual_key_released
        )

        tk.Button(
            manual_frame,
            text="Tag",
            command=self.manual_submit
        ).pack(
            side="left"
        )

        # ----------------------------------------------------
        # AUTO SCAN
        # ----------------------------------------------------

        self.toggle_btn = tk.Button(
            self.root,
            text="Start Auto Scan",
            bg="#008000",
            fg="white",
            font=(
                "Segoe UI",
                10,
                "bold"
            ),
            command=self.toggle_scanning
        )

        self.toggle_btn.pack(
            fill="x",
            padx=14,
            pady=10
        )
# ----------------------------------------------------
        # BLOCK TAGGER LAUNCHER
        # ----------------------------------------------------
        tk.Button(
            self.root,
            text="Open Interactive Block Tagger",
            bg="#0055cc",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            command=self.open_block_tagger
        ).pack(fill="x", padx=14, pady=(0, 10))
        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status = tk.Label(
            self.root,
            text=(
                "Set Targets and Video ROI "
                "to begin."
            ),
            wraplength=450,
            justify="left",
            font=(
                "Segoe UI",
                9
            ),
            fg="#333333"
        )

        self.status.pack(
            fill="x",
            padx=14,
            pady=4
        )

        # ----------------------------------------------------
        # VOICE STATUS
        # ----------------------------------------------------

        self.timer_label = tk.Label(
            self.root,
            text="Offline voice: Standby",
            font=(
                "Segoe UI",
                8,
                "italic"
            ),
            fg="#666666"
        )

        self.timer_label.pack(
            fill="x",
            padx=14,
            pady=(2, 6)
        )

        self.entry.focus_set()

# ========================================================
    # OPEN BLOCK TAGGER
    # ========================================================
    def open_block_tagger(self):
        # Create a secondary window (Toplevel) to prevent mainloop conflicts
        block_window = tk.Toplevel(self.root)
        
        # Initialize the imported block system inside this new window
        InteractiveHudlTagger(block_window)



    # ========================================================
    # SET TARGETS
    # ========================================================

    def calibrate_targets(self):

        self.root.withdraw()

        self.root.after(
            200,
            lambda: CalibrationOverlay(
                self.root,
                "targets",
                self._on_targets_done
            )
        )

    # ========================================================
    # TARGETS COMPLETE
    # ========================================================

    def _on_targets_done(
        self,
        jersey_coords,
        extra_coords
    ):

        self.root.deiconify()

        if (
            jersey_coords
            and
            extra_coords
        ):

            self.jersey_coords = (
                jersey_coords
            )

            self.extra_coords = (
                extra_coords
            )

            self.status.config(
                text=(
                    "Targets calibrated successfully.\n"
                    "1. Jersey input → "
                    "2. Second click → E"
                ),
                fg="#007700"
            )

    # ========================================================
    # SET VIDEO ROI
    # ========================================================

    def calibrate_roi(self):

        self.root.withdraw()

        self.root.after(
            200,
            lambda: CalibrationOverlay(
                self.root,
                "roi",
                self._on_roi_done
            )
        )

    # ========================================================
    # ROI COMPLETE
    # ========================================================

    def _on_roi_done(
        self,
        roi
    ):

        self.root.deiconify()

        if roi:

            self.video_roi = roi

            self.status.config(
                text=(
                    f"ROI set: "
                    f"{roi['width']}x"
                    f"{roi['height']} "
                    f"at "
                    f"({roi['left']}, "
                    f"{roi['top']})"
                ),
                fg="#007700"
            )

    # ========================================================
    # MANUAL TAG MODE
    # ========================================================

    def _validate_manual_input(self, proposed):
        """
        Final safety filter for the Manual Tag field.

        Only a valid jersey-number prefix is accepted:
            ""   -> allowed while editing
            0-9  -> allowed
            00-99 -> allowed

        Letters, symbols, and values above 99
        are rejected before they enter the field.
        """

        if proposed == "":
            return True

        if not re.fullmatch(r"\d{1,2}", proposed):
            return False

        return 0 <= int(proposed) <= 99

    def _global_key_handler(self, event):
        """
        Global keyboard shortcuts.

        X = Set Targets
        V = Set Video ROI
        L = Speech Tag toggle
        M = Manual submit mode toggle
        Other alphabetic keys are forwarded to the previous Hudl window.
        P is special: it sends Space instead of P.
        """

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

        if key == "l":
            self.toggle_speech_tag()
            return "break"

        if len(key) == 1 and key.isalpha():
            self.send_hudl_key(key)
            return "break"

    def _manual_key_pressed(self, event):
        """
        Keep the Manual Tag box numeric-only.

        M toggles the mode and is never inserted.
        X/V/L trigger calibration or speech controls.
        Other letters, symbols and unsupported keys are ignored.
        """

        key = event.keysym

        # M is a control key, never a jersey-number character.
        if key.lower() == "q":
            self.close()
            return "break"

        if key.lower() == "m":
            self.toggle_manual_mode()
            return "break"

        if key.lower() == "x":
            self.calibrate_targets()
            return "break"

        if key.lower() == "v":
            self.calibrate_roi()
            return "break"

        if key.lower() == "l":
            self.toggle_speech_tag()
            return "break"

        # Any alphabetic key is an action key, never a jersey number.
        # P sends Space; every other letter sends itself.
        if len(key) == 1 and key.isalpha():
            self.send_hudl_key(key)
            return "break"

        # Normal editing/navigation keys.
        if key in {
            "BackSpace",
            "Delete",
            "Left",
            "Right",
            "Home",
            "End",
            "Return",
            "KP_Enter",
            "Tab",
        }:
            return None

        # Only digits are allowed.
        if key not in "0123456789":
            return "break"

        # Check the value that would result from this digit.
        current = self.entry.get()

        if self.entry.selection_present():
            start = self.entry.index(tk.SEL_FIRST)
            end = self.entry.index(tk.SEL_LAST)
        else:
            start = self.entry.index(tk.INSERT)
            end = start

        proposed = current[:start] + key + current[end:]

        # Maximum two digits.
        if len(proposed) > 2:
            return "break"

        return None

    def send_hudl_key(self, key):
        """
        Send a keyboard action to the previous Hudl window.

        M is handled separately as the manual-mode toggle.
        P is mapped to Space. Every other alphabetic key is
        sent unchanged.
        """

        output_key = "space" if key.lower() == "p" else key.lower()

        try:
            # The dashboard is normally over Hudl. Temporarily step
            # out of the way, switch to the previous window, send the
            # requested key, then return to the dashboard.
            self.root.attributes("-topmost", False)
            self.root.update_idletasks()

            pyautogui.hotkey("alt", "tab")
            time.sleep(0.12)
            pyautogui.press(output_key)
            time.sleep(0.05)
            pyautogui.hotkey("alt", "tab")
            time.sleep(0.12)

            self.root.attributes("-topmost", True)

            display = "SPACE" if output_key == "space" else output_key.upper()

            self.status.config(
                text=f"Sent {display} key to the previous window.",
                fg="#007700"
            )

        except Exception as exc:
            try:
                self.root.attributes("-topmost", True)
            except Exception:
                pass

            self.status.config(
                text=f"Key action error: {exc}",
                fg="#b30000"
            )

    def toggle_manual_mode(self):
        """
        Switch between:

            AUTO SUBMIT -> wait 1.2s after the last digit
            ENTER SUBMIT -> wait for Enter

        The timer is reset every time another digit is entered.
        """

        if self.manual_mode == "auto":
            self.manual_mode = "enter"

            self._cancel_manual_submit_timer()

            self.manual_mode_btn.config(
                text="M: Enter Submit",
                bg="#0055cc",
                fg="white"
            )

            self.status.config(
                text=(
                    "Manual mode: ENTER SUBMIT. "
                    "Type a jersey number and press Enter."
                ),
                fg="black"
            )

        else:
            self.manual_mode = "auto"

            self.manual_mode_btn.config(
                text="M: Auto Submit",
                bg="#008000",
                fg="white"
            )

            self.status.config(
                text=(
                    "Manual mode: AUTO SUBMIT. "
                    f"Waiting {MANUAL_AUTO_SUBMIT_DELAY_MS / 1000:.1f}s "
                    "after the last digit."
                ),
                fg="black"
            )

            # If a valid number is already in the box, start its timer.
            self._schedule_manual_submit()

        self.entry.focus_set()

    def _cancel_manual_submit_timer(self):
        """Cancel the currently scheduled manual auto-submit."""

        if self.manual_submit_job is not None:
            try:
                self.root.after_cancel(self.manual_submit_job)
            except (tk.TclError, ValueError):
                pass

            self.manual_submit_job = None

    def _manual_key_released(self, event=None):
        """
        In auto mode, reset the debounce timer after every key release.

        Example:
            2 -> wait 1.7s
            21 -> timer resets to 1.7s

        Therefore 21 is submitted as one jersey number instead of
        submitting 2 immediately.
        """

        if self.manual_mode != "auto":
            return

        self._schedule_manual_submit()

    def _schedule_manual_submit(self):
        """Schedule auto-submit for the current valid jersey number."""

        self._cancel_manual_submit_timer()

        raw = (
            self.entry
            .get()
            .strip()
            .lstrip("#")
            .strip()
        )

        if (
            not re.fullmatch(r"\d{1,2}", raw)
            or
            not 0 <= int(raw) <= 99
        ):
            return

        self.manual_submit_job = self.root.after(
            MANUAL_AUTO_SUBMIT_DELAY_MS,
            lambda value=raw: self._auto_submit_manual(value)
        )

        self.status.config(
            text=(
                f"Waiting {MANUAL_AUTO_SUBMIT_DELAY_MS / 1000:.1f}s "
                f"to auto-submit #{raw}..."
            ),
            fg="#555555"
        )

    def _auto_submit_manual(self, expected_value):
        """Submit only if the entry is unchanged when the timer expires."""

        self.manual_submit_job = None

        if self.manual_mode != "auto":
            return

        current = (
            self.entry
            .get()
            .strip()
            .lstrip("#")
            .strip()
        )

        if current != expected_value:
            # A newer digit/key change won the race; schedule again.
            self._schedule_manual_submit()
            return

        self.manual_submit()

    # ========================================================
    # MANUAL TAG
    # ========================================================

    def manual_submit(
        self,
        event=None
    ):

        # Manual submission always cancels any pending auto-submit.
        self._cancel_manual_submit_timer()

        if (
            not self.jersey_coords
            or
            not self.extra_coords
        ):

            self.status.config(
                text=(
                    "Error: "
                    "Set Targets first."
                ),
                fg="#b30000"
            )

            return

        raw = (
            self.entry
            .get()
            .strip()
            .lstrip("#")
            .strip()
        )

        if (
            not re.fullmatch(
                r"\d{1,2}",
                raw
            )
            or
            not 1 <= int(raw) <= 99
        ):

            self.status.config(
                text=(
                    "Enter a jersey number "
                    "from 0 to 99."
                ),
                fg="#b30000"
            )

            return

        self.entry.delete(
            0,
            tk.END
        )

        self.detection_paused = True

        self.status.config(
            text=(
                f"Manual override: "
                f"tagging #{raw}..."
            ),
            fg="black"
        )

        threading.Thread(
            target=self.run_tag_and_save,
            args=(raw,),
            daemon=True
        ).start()

    # ========================================================
    # SPEECH TAG BUTTON
    # ========================================================

    def toggle_speech_tag(self):

        # ----------------------------------------------------
        # STOP SPEECH
        # ----------------------------------------------------

        if self.speech_tag_active:

            self.speech_tag_active = False

            self.speech_btn.config(
                text="3. Speech Tag",
                bg="SystemButtonFace",
                fg="black"
            )

            self.timer_label.config(
                text="Speech tag: Off",
                fg="#666666"
            )

            self.status.config(
                text="Speech tagging stopped.",
                fg="black"
            )

            return

        # ----------------------------------------------------
        # CHECK TARGETS
        # ----------------------------------------------------

        if (
            not self.jersey_coords
            or
            not self.extra_coords
        ):

            messagebox.showwarning(
                "Missing Targets",
                (
                    "Click '1. Set Targets' "
                    "and set both locations first."
                )
            )

            return

        # ----------------------------------------------------
        # START SPEECH
        # ----------------------------------------------------

        self.speech_tag_active = True

        self.speech_btn.config(
            text="Stop Speech Tag",
            bg="#cc0000",
            fg="white"
        )

        self.status.config(
            text=(
                "Loading offline speech model..."
            ),
            fg="black"
        )

        threading.Thread(
            target=self._start_speech_tag_worker,
            daemon=True
        ).start()

    # ========================================================
    # START SPEECH WORKER
    # ========================================================

    def _start_speech_tag_worker(self):

        try:

            if self.vosk_model is None:

                if not MODEL_PATH.is_dir():

                    raise FileNotFoundError(
                        "Vosk model folder not found:\n"
                        f"{MODEL_PATH}"
                    )

                self.vosk_model = Model(
                    str(MODEL_PATH)
                )

            self.root.after(
                0,
                lambda: self.status.config(
                    text=(
                        "Speech tagging active.\n"
                        "Say a jersey number, "
                        "for example: 7"
                    ),
                    fg="#007700"
                )
            )

            self.root.after(
                0,
                self._start_voice_listener
            )

        except Exception as exc:

            self.speech_tag_active = False

            self.root.after(
                0,
                lambda e=str(exc):
                self._speech_start_error(e)
            )

    # ========================================================
    # SPEECH ERROR
    # ========================================================

    def _speech_start_error(
        self,
        error
    ):

        self.speech_btn.config(
            text="3. Speech Tag",
            bg="SystemButtonFace",
            fg="black"
        )

        self.status.config(
            text=(
                f"Speech tag error: {error}"
            ),
            fg="#b30000"
        )

        self.timer_label.config(
            text="Speech tag: Off",
            fg="#666666"
        )

    # ========================================================
    # AUTO SCAN TOGGLE
    # ========================================================

    def toggle_scanning(self):

        # ----------------------------------------------------
        # STOP
        # ----------------------------------------------------

        if self.is_scanning:

            self.is_scanning = False

            self.toggle_btn.config(
                text="Start Auto Scan",
                bg="#008000"
            )

            self.status.config(
                text="Scan stopped.",
                fg="black"
            )

            if not self.speech_tag_active:

                self.timer_label.config(
                    text="Offline voice: Standby",
                    fg="#666666"
                )

            return

        # ----------------------------------------------------
        # TARGET CHECK
        # ----------------------------------------------------

        if (
            not self.jersey_coords
            or
            not self.extra_coords
        ):

            messagebox.showwarning(
                "Missing Targets",
                "Calibrate the two click targets first."
            )

            return

        # ----------------------------------------------------
        # ROI CHECK
        # ----------------------------------------------------

        if not self.video_roi:

            messagebox.showwarning(
                "Missing ROI",
                "Define the video playback region first."
            )

            return

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        self.is_scanning = True

        self.toggle_btn.config(
            text="Stop Auto Scan",
            bg="#cc0000"
        )

        self.status.config(
            text=(
                "Loading YOLO, OCR, and Vosk models..."
            ),
            fg="black"
        )

        threading.Thread(
            target=self._init_and_run_worker,
            daemon=True
        ).start()

    # ========================================================
    # INITIALIZE AUTO SCAN
    # ========================================================

    def _init_and_run_worker(self):

        try:

            # ------------------------------------------------
            # YOLO
            # ------------------------------------------------

            if self.yolo_model is None:

                self.yolo_model = YOLO(
                    "yolov8n.pt"
                )

            # ------------------------------------------------
            # OCR
            # ------------------------------------------------

            if self.ocr_reader is None:

                self.ocr_reader = easyocr.Reader(
                    ["en"],
                    gpu=True
                )

            # ------------------------------------------------
            # VOSK
            # ------------------------------------------------

            if self.vosk_model is None:

                if not MODEL_PATH.is_dir():

                    raise FileNotFoundError(
                        f"Vosk model folder not found: "
                        f"{MODEL_PATH}"
                    )

                self.vosk_model = Model(
                    str(MODEL_PATH)
                )

        except Exception as exc:

            self.root.after(
                0,
                lambda e=str(exc):
                self._startup_error(e)
            )

            return

        self.root.after(
            0,
            lambda: self.status.config(
                text=(
                    "Active: scanning video feed..."
                ),
                fg="#007700"
            )
        )

        # Start voice listener too
        self.root.after(
            0,
            self._start_voice_listener
        )

        try:

            with mss.mss() as sct:

                while (
                    self.is_scanning
                    or
                    self.speech_tag_active
                ):

                    if (
                        self.detection_paused
                        or
                        time.time()
                        <
                        self.cooldown_until
                    ):

                        time.sleep(
                            0.1
                        )

                        continue

                    frame = np.array(
                        sct.grab(
                            self.video_roi
                        )
                    )

                    frame = cv2.cvtColor(
                        frame,
                        cv2.COLOR_BGRA2BGR
                    )

                    results = self.yolo_model(
                        frame,
                        classes=[0],
                        verbose=False,
                        conf=0.5
                    )

                    found = False

                    for result in results:

                        if result.boxes is None:

                            continue

                        for box in (
                            result
                            .boxes
                            .xyxy
                            .cpu()
                            .numpy()
                        ):

                            x1, y1, x2, y2 = map(
                                int,
                                box
                            )

                            h = y2 - y1

                            crop = frame[
                                max(
                                    0,
                                    y1 + int(
                                        h * 0.10
                                    )
                                ):
                                min(
                                    frame.shape[0],
                                    y1 + int(
                                        h * 0.70
                                    )
                                ),
                                max(
                                    0,
                                    x1
                                ):
                                min(
                                    frame.shape[1],
                                    x2
                                )
                            ]

                            if (
                                crop.size == 0
                                or
                                crop.shape[0] < 20
                                or
                                crop.shape[1] < 20
                            ):

                                continue

                            gray = cv2.cvtColor(
                                crop,
                                cv2.COLOR_BGR2GRAY
                            )

                            gray = cv2.resize(
                                gray,
                                None,
                                fx=3,
                                fy=3,
                                interpolation=cv2.INTER_CUBIC
                            )
                            
                            clahe = cv2.createCLAHE(
                                clipLimit=2.0, 
                                tileGridSize=(8, 8)
                            )
                            
                            gray = clahe.apply(gray)
                            
                            gray = cv2.copyMakeBorder(
                                gray, 
                                20, 20, 20, 20, 
                                cv2.BORDER_CONSTANT, 
                                value=[255, 255, 255]
                            )

                            for (
                                bbox,
                                text,
                                prob
                            ) in self.ocr_reader.readtext(
                                gray,
                                allowlist="0123456789",
                                mag_ratio=2.0,
                                text_threshold=0.5,
                                low_text=0.3
                            ):

                                clean = text.strip()

                                if (
                                    re.fullmatch(
                                        r"\d{1,2}",
                                        clean
                                    )
                                    and
                                    0 <= int(clean) <= 99
                                    and
                                    prob > 0.35
                                ):

                                    self.detection_paused = True

                                    self.root.after(
                                        0,
                                        self._trigger_auto_tag,
                                        clean,
                                        "OCR"
                                    )

                                    found = True

                                    break

                            if found:
                                break

                        if found:
                            break

                    time.sleep(
                        0.08
                    )

        except Exception as exc:

            self.root.after(
                0,
                lambda e=str(exc):
                self.status.config(
                    text=f"Scan error: {e}",
                    fg="#b30000"
                )
            )

    # ========================================================
    # STARTUP ERROR
    # ========================================================

    def _startup_error(
        self,
        error
    ):

        self.is_scanning = False

        self.toggle_btn.config(
            text="Start Auto Scan",
            bg="#008000"
        )

        self.status.config(
            text=(
                f"Startup error: {error}"
            ),
            fg="#b30000"
        )

    # ========================================================
    # START VOICE LISTENER
    # ========================================================

    def _start_voice_listener(self):

        if (
            not (
                self.is_scanning
                or
                self.speech_tag_active
            )
            or
            self.voice_listening_active
        ):

            return

        self.voice_listening_active = True

        self.voice_thread = threading.Thread(
            target=self._listen_for_voice,
            daemon=True
        )

        self.voice_thread.start()

    # ========================================================
    # VOICE LISTENER
    # ========================================================

    def _listen_for_voice(self):

        """
        Offline Vosk speech recognition.

        Say:

            7

        or:

            seven

        and it will automatically tag jersey #7.
        """

        tag_started = False

        try:

            recognizer = KaldiRecognizer(
                self.vosk_model,
                SAMPLE_RATE
            )

            recognizer.SetWords(
                True
            )

            self.root.after(
                0,
                lambda: self.timer_label.config(
                    text=(
                        "Speech listening: "
                        "say a number (0-99)"
                    ),
                    fg="#cc6600"
                )
            )

            # ------------------------------------------------
            # AUDIO CALLBACK
            # ------------------------------------------------

            def callback(
                indata,
                frames,
                time_info,
                status
            ):

                try:

                    self.audio_queue.put_nowait(
                        bytes(indata)
                    )

                except queue.Full:

                    pass

            # ------------------------------------------------
            # CLEAR OLD AUDIO
            # ------------------------------------------------

            while not self.audio_queue.empty():

                try:

                    self.audio_queue.get_nowait()

                except queue.Empty:

                    break

            # ------------------------------------------------
            # OPEN MICROPHONE
            # ------------------------------------------------

            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=4000,
                dtype="int16",
                channels=1,
                callback=callback
            ):

                # IMPORTANT:
                # Works for Speech Tag alone as well as
                # Auto Scan + Speech Tag.

                while (
                    self.is_scanning
                    or
                    self.speech_tag_active
                ):

                    try:

                        data = (
                            self.audio_queue.get(
                                timeout=0.25
                            )
                        )

                    except queue.Empty:

                        continue

                    if not recognizer.AcceptWaveform(
                        data
                    ):

                        continue

                    result = recognizer.Result()

                    heard = json.loads(
                        result
                    ).get(
                        "text",
                        ""
                    ).lower().strip()

                    if not heard:

                        continue

                    # ------------------------------------------------
                    # DIRECT NUMBER RECOGNITION
                    # ------------------------------------------------

                    number = parse_spoken_number(
                        heard
                    )

                    if number is None:

                        continue

                    # ------------------------------------------------
                    # NUMBER FOUND
                    # ------------------------------------------------

                    if (
                        self.is_scanning
                        or
                        self.speech_tag_active
                    ):

                        self.detection_paused = True

                        tag_started = True

                        self.root.after(
                            0,
                            self._trigger_auto_tag,
                            number,
                            "Voice"
                        )

                        break

        except Exception as exc:

            self.root.after(
                0,
                lambda e=str(exc):
                self.timer_label.config(
                    text=(
                        f"Vosk/microphone error: "
                        f"{e}"
                    ),
                    fg="#b30000"
                )
            )

        finally:

            self.voice_listening_active = False

            if (
                self.is_scanning
                or
                self.speech_tag_active
            ) and not tag_started:

                self.detection_paused = False

                self.root.after(
                    1000,
                    self._start_voice_listener
                )

    # ========================================================
    # TRIGGER TAG
    # ========================================================

    def _trigger_auto_tag(
        self,
        number,
        source
    ):

        self.status.config(
            text=(
                f"Auto-tagging #{number} "
                f"via {source}..."
            ),
            fg="black"
        )

        self.timer_label.config(
            text=(
                f"Recognized #{number} "
                f"via {source}"
            ),
            fg="#007700"
        )

        threading.Thread(
            target=self.run_tag_and_save,
            args=(number,),
            daemon=True
        ).start()

    # ========================================================
    # ACTUAL TAGGING AUTOMATION
    # ========================================================

    def run_tag_and_save(
        self,
        number
    ):

        try:

            # ------------------------------------------------
            # GET FIRST CLICK COORDINATE
            # ------------------------------------------------

            jx, jy = self.jersey_coords

            # ------------------------------------------------
            # GET SECOND CLICK COORDINATE
            # ------------------------------------------------

            ex, ey = self.extra_coords

            # =================================================
            # STEP 1
            # CLICK FIRST LOCATION
            # =================================================

            pyautogui.click(
                jx,
                jy
            )

            time.sleep(
                0.10
            )

            # =================================================
            # STEP 2
            # TYPE THE VALUE
            # =================================================

            pyautogui.write(
                str(number)
            )

            time.sleep(
                0.10
            )

            # =================================================
            # STEP 3
            # PRESS ENTER
            # =================================================

            pyautogui.press(
                "enter"
            )

            time.sleep(
                0.15
            )

            # =================================================
            # STEP 4
            # CLICK SECOND LOCATION
            # =================================================

            pyautogui.click(
                ex,
                ey
            )

            time.sleep(
                0.15
            )

            # =================================================
            # STEP 5
            # PRESS E
            # =================================================

            pyautogui.press(
                "e"
            )

            time.sleep(
                0.15
            )

            # =================================================
            # SUCCESS
            # =================================================

            self.root.after(
                0,
                lambda: self.status.config(
                    text=(
                        f"Successfully tagged "
                        f"#{number}."
                    ),
                    fg="#007700"
                )
            )

        except Exception as exc:

            self.root.after(
                0,
                lambda e=str(exc):
                self.status.config(
                    text=(
                        f"Tagging error: {e}"
                    ),
                    fg="#b30000"
                )
            )

        finally:

            # ------------------------------------------------
            # COOLDOWN
            # ------------------------------------------------

            self.cooldown_until = (
                time.time() + 2.5
            )

            self.detection_paused = False

            # ------------------------------------------------
            # RESTORE UI
            # ------------------------------------------------

            self.root.after(
                100,
                self.restore_focus
            )

            # ------------------------------------------------
            # RESTART VOICE LISTENER
            # ------------------------------------------------

            if (
                self.is_scanning
                or
                self.speech_tag_active
            ):

                self.root.after(
                    1000,
                    self._start_voice_listener
                )

    # ========================================================
    # RESTORE FOCUS
    # ========================================================

    def restore_focus(self):

        if self.root.winfo_exists():

            self.root.focus_force()

            self.entry.focus_set()

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self._cancel_manual_submit_timer()

        self.is_scanning = False

        self.speech_tag_active = False

        self.root.destroy()


# ============================================================
# START ON MONITOR 2
# ============================================================

def move_to_monitor_2(root):
    """Place the main window on Windows monitor 2 when available."""

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
            ctypes.c_int,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )

        def enum_callback(hmonitor, hdc, rect, lparam):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                monitors.append((
                    info.rcWork.left,
                    info.rcWork.top,
                    info.rcWork.right,
                    info.rcWork.bottom,
                    bool(info.dwFlags & 1),  # MONITORINFOF_PRIMARY
                ))
            return 1

        callback = MONITORENUMPROC(enum_callback)
        user32.EnumDisplayMonitors(None, None, callback, 0)

        if len(monitors) >= 2:
            # Do not rely on EnumDisplayMonitors() list order.
            # Prefer the monitor that Windows marks as non-primary.
            non_primary = [
                monitor for monitor in monitors
                if not monitor[4]
            ]

            if non_primary:
                left, top, right, bottom, _ = non_primary[0]
            else:
                left, top, right, bottom, _ = monitors[1]

            root.geometry(
                f"480x370+{left + 20}+{top + 20}"
            )
            return

    except Exception:
        pass

    root.geometry("480x370+40+80")


# ============================================================
# MAIN
# ============================================================

def main():

    root = tk.Tk()

    move_to_monitor_2(root)

    AutoTaggerApp(
        root
    )

    root.mainloop()


# ============================================================
# START PROGRAM
# ============================================================

if __name__ == "__main__":

    main()