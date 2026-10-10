"""
============================================================
HUDL ATTACK LOCATION 2D - MODERN DASHBOARD EDITION
============================================================

WORKFLOW:
    TOP -> BOTTOM -> E  OR  BOTTOM -> TOP -> E

HOTKEYS:
    I  = Focus & type iterations (Numbers ONLY)
    E  = Start iterations immediately (No letters inserted!)
    S  = Stop iteration
    X  = Exit application
    F8 = Global emergency stop
============================================================
"""

import json
import os
import random
import threading
import time
import tkinter as tk
from tkinter import messagebox
import pyautogui

# ============================================================
# GLOBAL SETTINGS & FILE PATHS
# ============================================================

GLOBAL_CONFIG_FILE = "hudl_global_config.json"

DEFAULT_CLICK_DELAY = 0.035
DEFAULT_SET_DELAY = 0.08
DEFAULT_EDGE_MARGIN = 0.12
DEFAULT_MIN_POINT_DISTANCE = 30

DEFAULT_FOCUS_AREA = {
    "left": 1709,
    "top": 372,
    "right": 1808,
    "bottom": 541,
    "middle": 456,
}

STOP_HOTKEY = "f8"

# ============================================================
# CONFIGURATION HELPERS
# ============================================================

def load_global_config():
    if os.path.exists(GLOBAL_CONFIG_FILE):
        try:
            with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Config] Error loading: {e}")
    return {}

def save_global_config(config_data):
    try:
        with open(GLOBAL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"[Config] Save error: {e}")

_initial_cfg = load_global_config()
crop = _initial_cfg.get("attack_2d", {}).get("focus_area", DEFAULT_FOCUS_AREA.copy())

stop_event = threading.Event()
automation_running = False
last_top_point = None
last_bottom_point = None

# ============================================================
# RANDOM POINT GENERATION
# ============================================================

def is_calibrated():
    required = ["left", "top", "right", "bottom", "middle"]
    return all(crop.get(key) is not None for key in required)

def point_distance(point_a, point_b):
    if point_a is None or point_b is None:
        return float("inf")
    dx = point_a[0] - point_b[0]
    dy = point_a[1] - point_b[1]
    return (dx * dx + dy * dy) ** 0.5

def generate_random_point(half, edge_margin, minimum_distance):
    global last_top_point, last_bottom_point

    left = crop["left"]
    right = crop["right"]
    top = crop["top"]
    middle = crop["middle"]
    bottom = crop["bottom"]

    if half == "top":
        half_top = top
        half_bottom = middle
        previous_point = last_top_point
    else:
        half_top = middle
        half_bottom = bottom
        previous_point = last_bottom_point

    width = right - left
    height = half_bottom - half_top

    x_margin = width * edge_margin
    y_margin = height * edge_margin

    min_x = int(left + x_margin)
    max_x = int(right - x_margin)
    min_y = int(half_top + y_margin)
    max_y = int(half_bottom - y_margin)

    if min_x >= max_x:
        min_x, max_x = left, right
    if min_y >= max_y:
        min_y, max_y = half_top, half_bottom

    for _ in range(1000):
        point = (random.randint(min_x, max_x), random.randint(min_y, max_y))
        if point_distance(point, previous_point) >= minimum_distance:
            return point

    return (random.randint(min_x, max_x), random.randint(min_y, max_y))

def remember_point(half, point):
    global last_top_point, last_bottom_point
    if half == "top":
        last_top_point = point
    else:
        last_bottom_point = point

# ============================================================
# CALIBRATION OVERLAY
# ============================================================

class FocusAreaCalibrator:
    def __init__(self, parent, on_confirm):
        self.parent = parent
        self.on_confirm = on_confirm
        self.dragging = False
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self.rectangle_id = None
        self.center_line_id = None

        self.window = tk.Toplevel(parent)
        self.window.title("Hudl Focus Area Calibration")
        self.window.attributes("-fullscreen", True, "-topmost", True, "-alpha", 0.35)
        self.window.configure(bg="#000000", cursor="crosshair")

        self.canvas = tk.Canvas(self.window, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.create_text(
            40, 35, anchor="nw", fill="#00ffcc",
            font=("Segoe UI", 16, "bold"),
            text="HUDL COURT CALIBRATION\n\nDrag a rectangle across the full court area.\nENTER = Confirm  |  ESC = Cancel"
        )

        self.canvas.bind("<ButtonPress-1>", self.mouse_down)
        self.canvas.bind("<B1-Motion>", self.mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.mouse_up)

        self.window.bind("<Return>", self.confirm)
        self.window.bind("<Escape>", lambda e: self.window.destroy())
        self.window.focus_force()

    def mouse_down(self, event):
        self.dragging = True
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.end_x = self.start_x
        self.end_y = self.start_y

        if self.rectangle_id:
            self.canvas.delete(self.rectangle_id)
        if self.center_line_id:
            self.canvas.delete(self.center_line_id)

        self.rectangle_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.end_x, self.end_y, outline="#00ffcc", width=3
        )

    def mouse_drag(self, event):
        if not self.dragging:
            return

        self.end_x = event.x_root
        self.end_y = event.y_root

        x1, x2 = min(self.start_x, self.end_x), max(self.start_x, self.end_x)
        y1, y2 = min(self.start_y, self.end_y), max(self.start_y, self.end_y)

        if self.rectangle_id:
            self.canvas.coords(self.rectangle_id, x1, y1, x2, y2)

        center_y = y1 + ((y2 - y1) / 2)
        if self.center_line_id:
            self.canvas.delete(self.center_line_id)

        self.center_line_id = self.canvas.create_line(
            x1, center_y, x2, center_y, fill="#ff007f", width=2, dash=(6, 4)
        )

    def mouse_up(self, event):
        self.dragging = False

    def confirm(self, event=None):
        x1, x2 = min(self.start_x, self.end_x), max(self.start_x, self.end_x)
        y1, y2 = min(self.start_y, self.end_y), max(self.start_y, self.end_y)
        width, height = x2 - x1, y2 - y1

        if width < 50 or height < 100:
            messagebox.showwarning(
                "Invalid Area", "Selection too small. Drag across the full location grid.",
                parent=self.window
            )
            return

        center_y = y1 + (height / 2)
        calibrated_data = {
            "left": int(x1), "top": int(y1), "right": int(x2),
            "bottom": int(y2), "middle": int(center_y)
        }
        self.window.destroy()
        self.on_confirm(calibrated_data)

# ============================================================
# MAIN APPLICATION
# ============================================================

class AttackLocation2DApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Attack 2D Tagger")
        self.root.geometry("390x440+40+80")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#181a20")

        self.create_interface()
        self.setup_keyboard_shortcuts()

    def _validate_numeric(self, proposed):
        """Enforces strictly numeric input (0-9 only)."""
        if proposed == "":
            return True
        return proposed.isdigit()

    def create_interface(self):
        # 1. Header Bar
        header = tk.Frame(self.root, bg="#181a20")
        header.pack(fill="x", padx=16, pady=(14, 6))

        tk.Label(
            header, text="ATTACK 2D TAGGER",
            font=("Segoe UI", 13, "bold"), fg="#ffffff", bg="#181a20"
        ).pack(side="left")

        self.badge = tk.Label(
            header, text="IDLE", font=("Segoe UI", 8, "bold"),
            bg="#2c313d", fg="#8da0b6", padx=8, pady=2
        )
        self.badge.pack(side="right")

        # 2. Main Card
        card = tk.Frame(self.root, bg="#232730", bd=0, padx=14, pady=12)
        card.pack(fill="x", padx=16, pady=4)

        # Iterations Row
        iter_row = tk.Frame(card, bg="#232730")
        iter_row.pack(fill="x", pady=4)

        tk.Label(
            iter_row, text="Iterations (I):",
            font=("Segoe UI", 10, "bold"), fg="#e0e6ed", bg="#232730"
        ).pack(side="left")

        validate_cmd = (self.root.register(self._validate_numeric), "%P")

        self.iterations_entry = tk.Entry(
            iter_row, width=7, font=("Consolas", 13, "bold"),
            justify="center", bg="#181a20", fg="#00ffcc",
            insertbackground="#ffffff", bd=1, relief="flat", highlightthickness=1,
            highlightbackground="#3b4252", highlightcolor="#00ffcc",
            validate="key", validatecommand=validate_cmd
        )
        self.iterations_entry.insert(0, "5")
        self.iterations_entry.pack(side="right")

        # Handle keys specifically inside the entry
        self.iterations_entry.bind("<KeyPress>", self._entry_key_handler)

        # Settings Row (Click Delay & Distance)
        tune_row = tk.Frame(card, bg="#232730")
        tune_row.pack(fill="x", pady=(8, 2))

        tk.Label(tune_row, text="Delay (s):", font=("Segoe UI", 8), fg="#9ba7b6", bg="#232730").pack(side="left")
        self.click_delay_entry = tk.Entry(
            tune_row, width=5, font=("Consolas", 9), justify="center",
            bg="#181a20", fg="#e0e6ed", insertbackground="#fff", bd=0, highlightthickness=1,
            highlightbackground="#3b4252"
        )
        self.click_delay_entry.insert(0, str(DEFAULT_CLICK_DELAY))
        self.click_delay_entry.pack(side="left", padx=4)

        tk.Label(tune_row, text="Dist (px):", font=("Segoe UI", 8), fg="#9ba7b6", bg="#232730").pack(side="left", padx=(10, 0))
        self.distance_entry = tk.Entry(
            tune_row, width=4, font=("Consolas", 9), justify="center",
            bg="#181a20", fg="#e0e6ed", insertbackground="#fff", bd=0, highlightthickness=1,
            highlightbackground="#3b4252"
        )
        self.distance_entry.insert(0, str(DEFAULT_MIN_POINT_DISTANCE))
        self.distance_entry.pack(side="left", padx=4)

        self.set_delay_entry = tk.Entry(self.root)
        self.set_delay_entry.insert(0, str(DEFAULT_SET_DELAY))
        self.margin_entry = tk.Entry(self.root)
        self.margin_entry.insert(0, str(DEFAULT_EDGE_MARGIN))

        # 3. Action Buttons
        btn_box = tk.Frame(self.root, bg="#181a20")
        btn_box.pack(fill="x", padx=16, pady=10)

        self.start_button = tk.Button(
            btn_box, text="START (E)", command=self.start,
            font=("Segoe UI", 10, "bold"), bg="#059669", activebackground="#10b981",
            fg="#ffffff", activeforeground="#ffffff", relief="flat", cursor="hand2", height=2
        )
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.stop_button = tk.Button(
            btn_box, text="STOP (S)", command=self.stop,
            font=("Segoe UI", 10, "bold"), bg="#dc2626", activebackground="#ef4444",
            fg="#ffffff", activeforeground="#ffffff", relief="flat", cursor="hand2", height=2, state=tk.DISABLED
        )
        self.stop_button.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # 4. Progress Card
        prog_card = tk.Frame(self.root, bg="#232730", padx=12, pady=10)
        prog_card.pack(fill="x", padx=16, pady=4)

        self.progress_label = tk.Label(
            prog_card, text="SET: 0 / 0", font=("Consolas", 15, "bold"),
            fg="#00ffcc", bg="#232730"
        )
        self.progress_label.pack()

        self.status_label = tk.Label(
            prog_card, text="Press I to type, E to start immediately",
            font=("Segoe UI", 9), fg="#9ba7b6", bg="#232730", wraplength=350
        )
        self.status_label.pack(pady=(2, 0))

        # 5. Bottom Toolbar & Calibration
        bot_bar = tk.Frame(self.root, bg="#181a20")
        bot_bar.pack(fill="x", side="bottom", padx=16, pady=(0, 10))

        self.cal_btn = tk.Button(
            bot_bar, text="Calibrate Area", command=self.start_calibration,
            font=("Segoe UI", 8), bg="#2a2e39", fg="#8da0b6", activebackground="#383e4d",
            activeforeground="#ffffff", relief="flat", cursor="hand2", pady=4
        )
        self.cal_btn.pack(side="left")

        tk.Label(
            bot_bar, text="I: Count | E: Run | S: Stop | X: Exit",
            font=("Segoe UI", 8, "bold"), fg="#5c667a", bg="#181a20"
        ).pack(side="right")

    # ========================================================
    # KEYBOARD ROUTING & DISPATCH
    # ========================================================
    def setup_keyboard_shortcuts(self):
        self.root.bind_all("<KeyPress>", self._handle_keypress)
        try:
            import keyboard
            keyboard.add_hotkey(STOP_HOTKEY, lambda: self.root.after(0, self.stop))
        except Exception:
            pass

    def _entry_key_handler(self, event):
        """Intercepts special hotkeys inside the entry so letters are never inserted."""
        key = event.keysym.lower()

        if key == "e":
            self.root.focus_set()
            if not automation_running:
                self.start()
            return "break"

        if key == "s":
            self.root.focus_set()
            if automation_running:
                self.stop()
            return "break"

        if key == "x":
            self.close_app()
            return "break"

        return None

    def _handle_keypress(self, event):
        key = event.keysym.lower()
        focused = self.root.focus_get()

        if isinstance(focused, tk.Entry):
            return

        if key == "x":
            self.close_app()
            return "break"

        if key == "s":
            if automation_running:
                self.stop()
                return "break"

        if key == "i":
            self.iterations_entry.focus_set()
            self.iterations_entry.selection_range(0, tk.END)
            return "break"

        if key == "e":
            if not automation_running:
                self.root.focus_set()
                self.start()
            return "break"

    # ========================================================
    # CALIBRATION
    # ========================================================
    def start_calibration(self):
        FocusAreaCalibrator(self.root, self.calibration_complete)

    def calibration_complete(self, data):
        global crop
        crop = data

        cfg = load_global_config()
        cfg.setdefault("attack_2d", {})["focus_area"] = crop
        save_global_config(cfg)

        self.status_label.config(text="Focus area saved to global config.", fg="#00ffcc")

    # ========================================================
    # RUN ENGINE
    # ========================================================
    def read_settings(self):
        try:
            raw_iter = self.iterations_entry.get().strip()
            iterations = int(raw_iter) if raw_iter else 5
            click_delay = float(self.click_delay_entry.get())
            set_delay = float(self.set_delay_entry.get())
            edge_margin = float(self.margin_entry.get())
            minimum_distance = float(self.distance_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Settings", "Please enter valid numeric values.")
            return None

        if iterations <= 0:
            iterations = 1
        return iterations, click_delay, set_delay, edge_margin, minimum_distance

    def start(self):
        global automation_running, last_top_point, last_bottom_point

        if not is_calibrated():
            messagebox.showwarning("Calibration Required", "Please calibrate court area first.")
            return

        settings = self.read_settings()
        if settings is None:
            return

        iterations, click_delay, set_delay, edge_margin, minimum_distance = settings

        stop_event.clear()
        last_top_point = None
        last_bottom_point = None
        automation_running = True

        self.badge.config(text="RUNNING", bg="#059669", fg="#ffffff")
        self.start_button.config(state=tk.DISABLED, bg="#2c313d")
        self.stop_button.config(state=tk.NORMAL)
        self.progress_label.config(text=f"SET: 0 / {iterations}")
        self.status_label.config(text="Tagging sets...", fg="#00ffcc")

        self.root.focus_set()

        threading.Thread(
            target=self.run_iterations,
            args=(iterations, click_delay, set_delay, edge_margin, minimum_distance),
            daemon=True
        ).start()

    def run_iterations(self, iterations, click_delay, set_delay, edge_margin, minimum_distance):
        global automation_running
        pyautogui.PAUSE = 0

        try:
            for set_number in range(1, iterations + 1):
                if stop_event.is_set():
                    break

                if random.choice([True, False]):
                    first_half, second_half = "top", "bottom"
                else:
                    first_half, second_half = "bottom", "top"

                first_point = generate_random_point(first_half, edge_margin, minimum_distance)
                second_point = generate_random_point(second_half, edge_margin, minimum_distance)

                remember_point(first_half, first_point)
                remember_point(second_half, second_point)

                direction = f"{first_half.upper()} → {second_half.upper()}"
                self.root.after(0, self.update_progress, set_number, iterations, direction)

                if stop_event.is_set():
                    break
                pyautogui.click(first_point[0], first_point[1])
                time.sleep(click_delay)

                if stop_event.is_set():
                    break
                pyautogui.click(second_point[0], second_point[1])
                time.sleep(click_delay)

                if stop_event.is_set():
                    break
                pyautogui.press("e")

                if stop_event.wait(set_delay):
                    break

        except pyautogui.FailSafeException:
            self.root.after(0, lambda: messagebox.showwarning("FailSafe", "Mouse reached corner."))
        finally:
            automation_running = False
            self.root.after(0, self.automation_finished)

    def update_progress(self, set_number, total, direction):
        self.progress_label.config(text=f"SET: {set_number} / {total}")
        self.status_label.config(text=f"{direction} → E", fg="#00ffcc")

    def stop(self):
        global automation_running
        if not automation_running:
            return
        stop_event.set()
        self.badge.config(text="STOPPING", bg="#dc2626", fg="#ffffff")
        self.status_label.config(text="Stopping...", fg="#ef4444")
        self.stop_button.config(state=tk.DISABLED)

    def automation_finished(self):
        global automation_running
        automation_running = False
        self.badge.config(text="IDLE", bg="#2c313d", fg="#8da0b6")
        self.start_button.config(state=tk.NORMAL, bg="#059669")
        self.stop_button.config(state=tk.DISABLED)

        if stop_event.is_set():
            self.status_label.config(text="Stopped. Press E to run again.", fg="#ef4444")
        else:
            self.status_label.config(text="Done! Ready for next round (E).", fg="#10b981")

        # Refocus window immediately so hotkeys (E, I, X) work right away
        self._refocus_app()

    def _refocus_app(self):
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            import ctypes
            hwnd = self.root.winfo_id()
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        self.root.focus_set()

    def close_app(self):
        stop_event.set()
        try:
            import keyboard
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self.root.destroy()

# ============================================================
# MAIN
# ============================================================

def main():
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0

    root = tk.Tk()
    app = AttackLocation2DApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()

if __name__ == "__main__":
    main()