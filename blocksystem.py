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

# PyAutoGUI Safety Settings
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

# Shared Global Config File
GLOBAL_CONFIG_FILE = "hudl_global_config.json"
SPEED_LEVELS = [0.5, 1.0, 1.5, 2.0, 2.5]
DEFAULT_SPEED_INDEX = 1  # 1.0x

# ==============================================================================
# Central Configuration Helpers (Shared across all taggers)
# ==============================================================================
def load_global_config():
    if os.path.exists(GLOBAL_CONFIG_FILE):
        try:
            with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Config] Error loading: {e}")
            
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
        }
    }

def save_global_config(config_data):
    try:
        with open(GLOBAL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"[Config] Save error: {e}")

def update_shared_speed_coords(speed_coords_dict):
    cfg = load_global_config()
    cfg.setdefault("shared_ui", {})["speed_menu"] = speed_coords_dict
    save_global_config(cfg)

def update_tagger_box(tagger_name, coord):
    cfg = load_global_config()
    cfg.setdefault("taggers", {}).setdefault(tagger_name, {})["player_select_box"] = list(coord)
    save_global_config(cfg)


# ==============================================================================
# Main Interactive Hudl Tagger
# ==============================================================================
class InteractiveHudlTagger:
    MODULE_NAME = "block"

    def __init__(self, root):
        self.root = root
        self.root.title("Hudl Auto-Tagger (Block)")
        self.root.geometry("490x460")
        self.root.attributes("-topmost", True)
        
        self.screen_width, self.screen_height = pyautogui.size()
        self.is_running = False
        self.history = []
        self.current_speed_idx = DEFAULT_SPEED_INDEX

        # State management for speed menu
        self.menu_is_open = False
        self.close_timer = None
        self.speed_lock = threading.Lock()

        # Load shared configuration
        self.sync_from_global_config()

        # Macro Delay Profiles
        self.speed_profiles = {
            "Fast": (0.08, 0.2),
            "Normal": (0.12, 0.35),
            "Safe": (0.2, 0.5)
        }
        self.selected_speed = tk.StringVar(value="Normal")

        # Instant key mappings
        self.instant_key_map = {
            'n': 'n',
            't': 't',
            'w': 'w',
            'j': 'left',   # Left arrow (seek back)
            'l': 'right',  # Right arrow (seek forward)
            'k': 'space'   # Spacebar (play/pause)
        }

        self.setup_ui()
        self.setup_global_hotkeys()

    def sync_from_global_config(self):
        config = load_global_config()
        tagger_cfg = config.get("taggers", {}).get(self.MODULE_NAME, {})
        self.target_coord = tuple(tagger_cfg.get("player_select_box", [1691, 392]))
        self.speed_coords = config.get("shared_ui", {}).get("speed_menu", {})

    def setup_ui(self):
        tk.Label(self.root, text=f"Hudl Auto-Tagger ({self.MODULE_NAME.upper()})", font=("Segoe UI", 12, "bold")).pack(pady=(8, 2))
        
        shortcut_text = "Press Shift+Space anywhere to focus tagger" if KEYBOARD_AVAILABLE else "Install 'keyboard' package for global hotkey"
        tk.Label(self.root, text=shortcut_text, font=("Segoe UI", 8), fg="#666").pack()

        self.status = tk.Label(self.root, text="Instant: N, T, W | Nav: J, K, L | Speed: O (Down), P (Up)", fg="blue", wraplength=460)
        self.status.pack(pady=4)

        self.speed_hud_label = tk.Label(self.root, text=f"Active Speed: {SPEED_LEVELS[self.current_speed_idx]}x", font=("Segoe UI", 11, "bold"), fg="#2e7d32")
        self.speed_hud_label.pack(pady=2)

        self.entry = tk.Entry(self.root, font=("Consolas", 14), width=15, justify="center")
        self.entry.pack(pady=6)
        
        self.entry.bind("<Return>", lambda e: self.trigger_complex_sequence())
        self.entry.bind("<KeyRelease>", self.check_instant_keys)
        self.entry.bind("<Up>", self.recall_previous_tag)
        self.entry.focus_set()

        # Speed Profile Frame
        speed_frame = tk.Frame(self.root)
        speed_frame.pack(pady=2)
        tk.Label(speed_frame, text="Macro Delay: ", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        for mode in ["Fast", "Normal", "Safe"]:
            tk.Radiobutton(speed_frame, text=mode, variable=self.selected_speed, value=mode).pack(side=tk.LEFT, padx=3)

        # Mapping Buttons Frame
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=6)
        tk.Button(btn_frame, text=f"1. Set {self.MODULE_NAME.title()} Box", width=16, command=self.calibrate_target).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="2. Map Speed Menu", width=18, command=self.start_speed_calibration_wizard).pack(side=tk.LEFT, padx=4)

        speed_status = "Yes" if bool(self.speed_coords) else "No"
        self.coord_label = tk.Label(self.root, text=f"{self.MODULE_NAME.title()} Box: {self.target_coord} | Shared Speed: {speed_status}", font=("Consolas", 8), fg="#555")
        self.coord_label.pack()

        self.history_label = tk.Label(self.root, text="Recent: None", font=("Segoe UI", 8), fg="#777")
        self.history_label.pack(pady=3)

    def setup_global_hotkeys(self):
        if KEYBOARD_AVAILABLE:
            def on_hotkey():
                self.root.after(0, self._refocus_app)
            keyboard.add_hotkey("shift+space", on_hotkey)

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
    # Calibration 1: Target Select Box
    # ==========================================
    def calibrate_target(self):
        overlay = tk.Toplevel(self.root)
        overlay.attributes("-fullscreen", True, "-alpha", 0.3, "-topmost", True)
        overlay.configure(bg="black", cursor="crosshair")
        
        canvas = tk.Canvas(overlay, bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvas.create_text(
            50, 50, anchor="nw", fill="#00ff66", font=("Segoe UI", 16, "bold"), 
            text=f"Click the '{self.MODULE_NAME.upper()}' Select Box. (Esc to cancel)"
        )
        
        def on_click(event):
            self.target_coord = (event.x_root, event.y_root)
            update_tagger_box(self.MODULE_NAME, self.target_coord)
            overlay.destroy()
            
            speed_status = "Yes" if bool(self.speed_coords) else "No"
            self.coord_label.config(text=f"{self.MODULE_NAME.title()} Box: {self.target_coord} | Shared Speed: {speed_status}")
            self.status.config(text=f"Saved to global config: {self.target_coord}", fg="#007700")
            self._refocus_app()

        overlay.bind("<ButtonPress-1>", on_click)
        overlay.bind("<Escape>", lambda e: overlay.destroy())

    # ==========================================
    # Calibration 2: Speed Menu Wizard
    # ==========================================
    def start_speed_calibration_wizard(self):
        steps = [
            ("menu_btn", "1/7: Click SPEED MENU button to open it"),
            ("0.5",      "2/7: Click the 0.5x option"),
            ("1.0",      "3/7: Click the 1.0x option"),
            ("1.5",      "4/7: Click the 1.5x option"),
            ("2.0",      "5/7: Click the 2.0x option"),
            ("2.5",      "6/7: Click the 2.5x option"),
            ("menu_exit", "7/7: Click where to CLOSE menu (or neutral video canvas)")
        ]
        self._wizard_index = 0
        self._temp_speed_coords = {}

        overlay = tk.Toplevel(self.root)
        overlay.attributes("-fullscreen", True, "-alpha", 0.35, "-topmost", True)
        overlay.configure(bg="black", cursor="crosshair")

        canvas = tk.Canvas(overlay, bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        prompt_id = canvas.create_text(
            50, 50, anchor="nw", fill="#00ff66", font=("Segoe UI", 16, "bold"),
            text=steps[0][1] + " (Esc to cancel)"
        )

        def on_step_click(event):
            key, _ = steps[self._wizard_index]
            self._temp_speed_coords[key] = [event.x_root, event.y_root]
            self._wizard_index += 1

            if self._wizard_index < len(steps):
                _, next_prompt = steps[self._wizard_index]
                canvas.itemconfig(prompt_id, text=next_prompt + " (Esc to cancel)")
            else:
                self.speed_coords = self._temp_speed_coords
                update_shared_speed_coords(self.speed_coords)
                overlay.destroy()
                self.coord_label.config(text=f"{self.MODULE_NAME.title()} Box: {self.target_coord} | Shared Speed: Yes")
                self.status.config(text="Shared Speed Menu Saved Globally!", fg="#007700")
                self._refocus_app()

        overlay.bind("<ButtonPress-1>", on_step_click)
        overlay.bind("<Escape>", lambda e: overlay.destroy())

    # ==========================================
    # State-Aware Speed Control (O & P)
    # ==========================================
    def trigger_speed_change(self, direction):
        if not self.speed_coords:
            self.status.config(text="Map speed menu first! Click '2. Map Speed Menu'", fg="red")
            return

        # Step speed index
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
        self.speed_hud_label.config(text=f"Active Speed: {target_speed_str}x")

        # Run click operation on background worker
        threading.Thread(target=self._execute_smart_speed_sequence, args=(target_speed_str,), daemon=True).start()

    def _execute_smart_speed_sequence(self, speed_str):
        with self.speed_lock:
            # 1. Cancel existing close timer so menu stays open while adjusting
            if self.close_timer and self.close_timer.is_alive():
                self.close_timer.cancel()

            menu_btn = self.speed_coords.get("menu_btn")
            speed_coord = self.speed_coords.get(speed_str)

            try:
                # 2. Only click the menu button if the menu is NOT already open
                if not self.menu_is_open:
                    pyautogui.click(menu_btn[0], menu_btn[1])
                    self.menu_is_open = True
                    time.sleep(0.38)

                # 3. Click directly on the target speed
                pyautogui.click(speed_coord[0], speed_coord[1])
                self.status.config(text=f"Speed: {speed_str}x (Menu open)", fg="#007700")

                # Refocus immediately to keep entry responsive
                self.root.after(0, self._refocus_app)

            except Exception as e:
                self.status.config(text=f"Speed error: {str(e)}", fg="red")

            # 4. Debounced 3-second auto-close
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
            self.status.config(text=f"Speed set to {SPEED_LEVELS[self.current_speed_idx]}x. Menu closed.", fg="#0066cc")
            self.root.after(0, self._refocus_app)

    # ==========================================
    # Instant Key & Dispatcher
    # ==========================================
    def check_instant_keys(self, event):
        if self.is_running:
            return

        raw_input = self.entry.get().strip().lower()
        if raw_input == 'x':
            self.entry.delete(0, tk.END)
            self.root.destroy()
            return

        # Speed Controls (O = Down, P = Up)
        if raw_input == 'o':
            self.entry.delete(0, tk.END)
            self.trigger_speed_change("down")
            return
        elif raw_input == 'p':
            self.entry.delete(0, tk.END)
            self.trigger_speed_change("up")
            return

        # Playback (J, K, L) & Quick tags (N, T, W)
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
            # 1. Focus video area
            pyautogui.click(target_x, empty_y)
            time.sleep(key_pause)
            
            # 2. Confirm block tag ('y')
            pyautogui.press('y')
            time.sleep(step_delay) 
            
            # 3. Focus player input box
            pyautogui.click(target_x, target_y)
            time.sleep(step_delay * 0.7)
            
            # 4. Type player jersey numbers
            for player_num in players:
                pyautogui.write(player_num)
                time.sleep(key_pause)
                pyautogui.press('tab')
                time.sleep(key_pause)
                
            # 5. Defocus & Save ('e')
            pyautogui.click(target_x, empty_y)
            time.sleep(key_pause)
            pyautogui.press('e')
            
            self.status.config(text=f"Tagged: {', '.join(players)}", fg="#007700")
            
        except pyautogui.FailSafeException:
            self.status.config(text="Aborted (Failsafe triggered).", fg="red")
        finally:
            self.is_running = False
            self.root.after(0, self._refocus_app)

    # ==========================================
    # Window Focus Management
    # ==========================================
    def _refocus_app(self):
        self.entry.delete(0, tk.END)
        self.root.lift()
        self.root.focus_force()
        self.entry.focus_set()


if __name__ == "__main__":
    root = tk.Tk()
    app = InteractiveHudlTagger(root)
    root.mainloop()