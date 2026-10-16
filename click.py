import tkinter as tk
from tkinter import messagebox
import threading
import time
import json
import os
import pyautogui
import keyboard

# --- Maximum Speed Tuning ---
pyautogui.PAUSE = 0.0              # Zero automatic pauses
pyautogui.MINIMUM_DURATION = 0.0   # Instant zero-time cursor placement
pyautogui.FAILSAFE = True          # Emergency stop: flick cursor into any screen corner

CONFIG_FILE = "coordinates.json"


class TurboMoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Cursor Move & 'E' Spammer")
        self.root.geometry("470x590")
        self.root.resizable(False, False)

        self.coordinates = []
        self.is_calibrating = False
        self.is_running = False
        self.worker_thread = None

        self._setup_ui()
        self._load_coordinates_from_json()
        self._bind_global_hotkeys()

    def _setup_ui(self):
        # Hotkeys overview
        legend_frame = tk.LabelFrame(self.root, text="Global Hotkeys", font=("Arial", 9, "bold"), padx=10, pady=5)
        legend_frame.pack(fill=tk.X, padx=15, pady=6)

        tk.Label(
            legend_frame,
            text="• [Enter] : Save hovered coordinate (when calibration is Active)\n• [S]     : Instant Start / Stop toggle",
            justify=tk.LEFT,
            font=("Courier", 9)
        ).pack(anchor="w")

        # Mouse coordinate indicator
        self.mouse_pos_label = tk.Label(self.root, text="Mouse: X: 0 | Y: 0", font=("Arial", 9, "italic"), fg="#555")
        self.mouse_pos_label.pack(pady=2)
        self._update_live_mouse_pos()

        # Calibration controls
        calib_frame = tk.Frame(self.root)
        calib_frame.pack(pady=4)

        self.calib_btn = tk.Button(
            calib_frame,
            text="Start Calibration",
            font=("Arial", 9, "bold"),
            bg="#0275d8",
            fg="white",
            command=self.toggle_calibration
        )
        self.calib_btn.grid(row=0, column=0, padx=5)

        clear_btn = tk.Button(calib_frame, text="Clear & Reset JSON", command=self.clear_coordinates)
        clear_btn.grid(row=0, column=1, padx=5)

        # Coordinate list
        list_frame = tk.Frame(self.root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=4)

        self.coord_listbox = tk.Listbox(list_frame, font=("Courier", 10), selectmode=tk.SINGLE)
        self.coord_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.coord_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.coord_listbox.config(yscrollcommand=scrollbar.set)

        # Settings Panel
        settings_frame = tk.Frame(self.root)
        settings_frame.pack(pady=4)

        # Glide / Move duration
        tk.Label(settings_frame, text="Move glide duration (sec):", font=("Arial", 9)).grid(row=0, column=0, sticky="e", padx=3)
        self.move_duration_entry = tk.Entry(settings_frame, width=6)
        self.move_duration_entry.insert(0, "0.0")  # 0.0 for instant hop, 0.05 - 0.1 for smooth scroll
        self.move_duration_entry.grid(row=0, column=1, padx=4, pady=2)

        # Pause at each coordinate
        tk.Label(settings_frame, text="Delay at each point (sec):", font=("Arial", 9)).grid(row=1, column=0, sticky="e", padx=3)
        self.delay_entry = tk.Entry(settings_frame, width=6)
        self.delay_entry.insert(0, "0.02")  # 20ms pause after keypress
        self.delay_entry.grid(row=1, column=1, padx=4, pady=2)

        # Start/Stop toggle button
        self.toggle_btn = tk.Button(
            self.root,
            text="Start Automation (or Press 'S')",
            font=("Arial", 11, "bold"),
            bg="#5cb85c",
            fg="white",
            command=self.toggle_execution
        )
        self.toggle_btn.pack(pady=8, ipadx=10, ipady=4)

        # Status label
        self.status_label = tk.Label(self.root, text="Status: Idle", font=("Arial", 10, "bold"), fg="gray")
        self.status_label.pack(pady=4)

    def _bind_global_hotkeys(self):
        keyboard.on_press_key("enter", lambda _: self._on_enter_pressed())
        keyboard.on_press_key("s", lambda _: self.toggle_execution())

    def _update_live_mouse_pos(self):
        x, y = pyautogui.position()
        self.mouse_pos_label.config(text=f"Mouse: X: {x:<5} | Y: {y:<5}")
        self.root.after(70, self._update_live_mouse_pos)

    # --- JSON Persistence ---
    def _save_coordinates_to_json(self):
        payload = [{"index": idx + 1, "x": pt[0], "y": pt[1]} for idx, pt in enumerate(self.coordinates)]
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            print(f"Error saving to JSON: {e}")

    def _load_coordinates_from_json(self):
        if not os.path.exists(CONFIG_FILE):
            return

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.coordinates.clear()
            self.coord_listbox.delete(0, tk.END)

            for item in data:
                x, y = item["x"], item["y"]
                self.coordinates.append((x, y))
                self.coord_listbox.insert(tk.END, f"Point {len(self.coordinates):02d} -> X: {x:<5} Y: {y:<5}")
        except Exception as e:
            print(f"Error loading JSON: {e}")

    # --- Calibration Logic ---
    def toggle_calibration(self):
        if self.is_running:
            return

        self.is_calibrating = not self.is_calibrating
        if self.is_calibrating:
            self.calib_btn.config(text="Stop Calibration", bg="#f0ad4e")
            self.status_label.config(text="Status: CALIBRATING (Hover & press Enter)", fg="#f0ad4e")
        else:
            self.calib_btn.config(text="Start Calibration", bg="#0275d8")
            self.status_label.config(text="Status: Calibration Finished", fg="gray")

    def _on_enter_pressed(self):
        if not self.is_calibrating:
            return

        x, y = pyautogui.position()
        self.coordinates.append((x, y))
        self._save_coordinates_to_json()

        self.root.after(0, self._append_coordinate_ui, len(self.coordinates), x, y)

    def _append_coordinate_ui(self, count, x, y):
        self.coord_listbox.insert(tk.END, f"Point {count:02d} -> X: {x:<5} Y: {y:<5}")
        self.coord_listbox.see(tk.END)

    def clear_coordinates(self):
        if self.is_running:
            return

        self.coordinates.clear()
        self.coord_listbox.delete(0, tk.END)
        self._save_coordinates_to_json()

    # --- Automation Runner ---
    def toggle_execution(self):
        if self.is_calibrating:
            self.toggle_calibration()

        if self.is_running:
            self._stop_automation()
        else:
            self._start_automation()

    def _start_automation(self):
        if not self.coordinates:
            messagebox.showwarning("No Points", "No coordinates found. Calibrate points first.")
            return

        try:
            move_dur = float(self.move_duration_entry.get().strip())
            delay = float(self.delay_entry.get().strip())
            if move_dur < 0 or delay < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Values", "Please enter positive numbers for duration and delay.")
            return

        self.is_running = True
        self.status_label.config(text="Status: AUTO-MOVING (Press 'S' to Stop)", fg="green")
        self.toggle_btn.config(text="Stop Automation (or Press 'S')", bg="#d9534f")

        self.worker_thread = threading.Thread(
            target=self._run_move_loop,
            args=(move_dur, delay),
            daemon=True
        )
        self.worker_thread.start()

    def _stop_automation(self):
        self.is_running = False
        self.root.after(0, self._on_stopped)

    def _on_stopped(self):
        self.status_label.config(text="Status: Stopped", fg="red")
        self.toggle_btn.config(text="Start Automation (or Press 'S')", bg="#5cb85c")

    def _run_move_loop(self, move_dur, delay):
        # 0.15s buffer to prevent key chatter from 'S'
        time.sleep(0.15)

        coords = self.coordinates
        move_fn = pyautogui.moveTo
        sleep_fn = time.sleep

        while self.is_running:
            for x, y in coords:
                if not self.is_running:
                    break

                # 1. Move cursor across to target (NO clicking)
                move_fn(x=x, y=y, duration=move_dur)

                # 2. Keypress 'e' with a 15ms hold for consistent capture
                pyautogui.keyDown('e')
                sleep_fn(0.015)
                pyautogui.keyUp('e')

                # 3. Pause before advancing to next point
                if delay > 0:
                    sleep_fn(delay)

        self.root.after(0, self._on_stopped)


if __name__ == "__main__":
    root = tk.Tk()
    app = TurboMoverApp(root)
    root.mainloop()