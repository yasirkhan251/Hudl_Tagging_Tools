import tkinter as tk
from tkinter import messagebox
import pyautogui
import threading
import json
import os
import time

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

pyautogui.FAILSAFE = True
CONFIG_FILE = "hudl_tagger_config.json"

class InteractiveHudlTagger:
    def __init__(self, root):
        self.root = root
        self.root.title("Hudl Auto-Tagger Pro")
        self.root.geometry("480x420")
        self.root.attributes("-topmost", True)
        
        self.screen_width, self.screen_height = pyautogui.size()
        self.is_running = False
        self.history = []
        
        # Load saved coordinate configuration
        self.target_coord = self.load_config()

        # Speed profiles: (key_pause, step_delay)
        self.speed_profiles = {
            "Fast": (0.08, 0.2),
            "Normal": (0.12, 0.35),
            "Safe": (0.2, 0.5)
        }
        self.selected_speed = tk.StringVar(value="Normal")

        # Map instant keys to their target browser key actions
        self.instant_key_map = {
            'n': 'n',
            't': 't',
            'w': 'w',
            'j': 'left',   # Seek backward
            'l': 'right',  # Seek forward
            'k': 'space'   # Play / Pause
        }

        self.setup_ui()
        self.setup_global_hotkeys()

    # ==========================================
    # UI Setup
    # ==========================================
    def setup_ui(self):
        tk.Label(self.root, text="Hudl Interactive Tagger Pro", font=("Segoe UI", 12, "bold")).pack(pady=(10, 2))
        
        shortcut_text = "Press Shift+Space anywhere to focus tagger" if KEYBOARD_AVAILABLE else "Install 'keyboard' package for global hotkey"
        tk.Label(self.root, text=shortcut_text, font=("Segoe UI", 8), fg="#666").pack()

        self.status = tk.Label(self.root, text="Instant: N, T, W | Playback: J (◀), K (⏸/▶), L (▶) | X: Exit", fg="blue", wraplength=440)
        self.status.pack(pady=6)

        self.entry = tk.Entry(self.root, font=("Consolas", 14), width=15, justify="center")
        self.entry.pack(pady=6)
        
        # Key bindings
        self.entry.bind("<Return>", lambda e: self.trigger_complex_sequence())
        self.entry.bind("<KeyRelease>", self.check_instant_keys)
        self.entry.bind("<Up>", self.recall_previous_tag)
        self.entry.focus_set()

        # Speed Selector Frame
        speed_frame = tk.Frame(self.root)
        speed_frame.pack(pady=4)
        tk.Label(speed_frame, text="Speed: ", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        for mode in ["Fast", "Normal", "Safe"]:
            tk.Radiobutton(speed_frame, text=mode, variable=self.selected_speed, value=mode).pack(side=tk.LEFT, padx=4)

        # Coordinate button & history label
        tk.Button(self.root, text="Set Target Box", width=22, command=self.calibrate_target).pack(pady=6)
        
        self.coord_label = tk.Label(self.root, text=f"Target: {self.target_coord}", font=("Consolas", 9), fg="#555")
        self.coord_label.pack()

        self.history_label = tk.Label(self.root, text="Recent: None", font=("Segoe UI", 8), fg="#777")
        self.history_label.pack(pady=4)

    # ==========================================
    # Global Hotkey (Shift + Space)
    # ==========================================
    def setup_global_hotkeys(self):
        if KEYBOARD_AVAILABLE:
            def on_hotkey():
                self.root.after(0, self._refocus_app)
            keyboard.add_hotkey("shift+space", on_hotkey)

    # ==========================================
    # Config File Management
    # ==========================================
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    return tuple(data.get("target_coord", (1698, 391)))
            except Exception:
                pass
        return (1698, 391)

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"target_coord": self.target_coord}, f)

    # ==========================================
    # History & Recall
    # ==========================================
    def recall_previous_tag(self, event):
        if self.history:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self.history[-1])
        return "break"

    def _get_safe_empty_coord(self):
        target_x, target_y = self.target_coord
        if target_y + 300 < self.screen_height - 50:
            return target_x, target_y + 300
        return target_x, max(50, target_y - 200)

    # ==========================================
    # Calibration Overlay
    # ==========================================
    def calibrate_target(self):
        overlay = tk.Toplevel(self.root)
        overlay.attributes("-fullscreen", True, "-alpha", 0.3, "-topmost", True)
        overlay.configure(bg="black", cursor="crosshair")
        
        canvas = tk.Canvas(overlay, bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvas.create_text(
            50, 50, anchor="nw", fill="#00ff66", font=("Segoe UI", 16, "bold"), 
            text="Click the 'Select...' Players box. (Esc to cancel)"
        )
        
        def on_click(event):
            self.target_coord = (event.x_root, event.y_root)
            self.save_config()
            overlay.destroy()
            
            coord_str = f"{self.target_coord[0]}, {self.target_coord[1]}"
            self.coord_label.config(text=f"Target: {self.target_coord}")
            self.status.config(text=f"Target Saved: ({coord_str})", fg="#007700")
            
            self.root.clipboard_clear()
            self.root.clipboard_append(coord_str)
            self._refocus_app()

        overlay.bind("<ButtonPress-1>", on_click)
        overlay.bind("<Escape>", lambda e: overlay.destroy())

    # ==========================================
    # Instant Key & Navigation Controls
    # ==========================================
    def check_instant_keys(self, event):
        if self.is_running:
            return

        raw_input = self.entry.get().strip().lower()
        if raw_input == 'x':
            self.entry.delete(0, tk.END)
            self.root.destroy()
            return
            
        if raw_input in self.instant_key_map:
            target_key = self.instant_key_map[raw_input]
            display_name = raw_input.upper()
            self.entry.delete(0, tk.END)
            threading.Thread(target=self.run_instant_command, args=(target_key, display_name), daemon=True).start()

    def run_instant_command(self, key_to_press, display_name):
        self.is_running = True
        self.status.config(text=f"Sent: [{display_name}] -> {key_to_press}", fg="black")
        
        target_x, empty_y = self._get_safe_empty_coord()
        key_pause, _ = self.speed_profiles[self.selected_speed.get()]
        
        try:
            # Click empty space on browser canvas to ensure video focus
            pyautogui.click(target_x, empty_y)
            time.sleep(key_pause)
            pyautogui.press(key_to_press)
        finally:
            self.is_running = False
            self.root.after(0, self._refocus_app)

    # ==========================================
    # Complex Number Sequence (Requires Enter)
    # ==========================================
    def trigger_complex_sequence(self):
        if self.is_running:
            return
        
        raw_input = self.entry.get().strip()
        if not raw_input:
            return
            
        players = raw_input.split()[:3]
        
        joined_str = " ".join(players)
        if not self.history or self.history[-1] != joined_str:
            self.history.append(joined_str)
            if len(self.history) > 5:
                self.history.pop(0)
            self.history_label.config(text=f"Recent: {', '.join(self.history)}")

        self.entry.delete(0, tk.END)
        threading.Thread(target=self.run_complex_sequence, args=(players,), daemon=True).start()

    def run_complex_sequence(self, players):
        self.is_running = True
        self.status.config(text=f"Tagging: {', '.join(players)}...", fg="black")
        
        target_x, target_y = self.target_coord
        _, empty_y = self._get_safe_empty_coord()
        key_pause, step_delay = self.speed_profiles[self.selected_speed.get()]
        
        try:
            # 1. Focus Hudl
            pyautogui.click(target_x, empty_y)
            time.sleep(key_pause)
            
            # 2. Confirm block
            pyautogui.press('y')
            time.sleep(step_delay) 
            
            # 3. Target box
            pyautogui.click(target_x, target_y)
            time.sleep(step_delay * 0.7)
            
            # 4. Write players
            for player_num in players:
                pyautogui.write(player_num)
                time.sleep(key_pause)
                pyautogui.press('tab')
                time.sleep(key_pause)
                
            # 5. Defocus & Save
            pyautogui.click(target_x, empty_y)
            time.sleep(key_pause)
            pyautogui.press('e')
            
            self.status.config(text=f"Tagged: {', '.join(players)}", fg="#007700")
            
        except pyautogui.FailSafeException:
            self.root.after(0, lambda: messagebox.showwarning("FailSafe", "Mouse reached corner."))
            self.status.config(text="Aborted.", fg="red")
        finally:
            self.is_running = False
            self.root.after(0, self._refocus_app)

    def _refocus_app(self):
        self.entry.delete(0, tk.END)
        self.root.lift()
        self.root.focus_force()
        self.entry.focus_set()

if __name__ == "__main__":
    root = tk.Tk()
    app = InteractiveHudlTagger(root)
    root.mainloop()