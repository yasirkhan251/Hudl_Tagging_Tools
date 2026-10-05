import tkinter as tk
from tkinter import messagebox
import pyautogui
import time

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

class InteractiveHudlTagger:
    def __init__(self, root):
        self.root = root
        self.root.title("Hudl Auto-Tagger")
        self.root.geometry("450x300")
        self.root.attributes("-topmost", True)
        
        # New Default Coordinates applied here
        self.target_coord = (1698, 391) 
        
        # ==========================================
        # UI Setup
        # ==========================================
        tk.Label(root, text="Hudl Interactive Tagger", font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        self.status = tk.Label(root, text="Instant: N, T, W | X to Exit | Numbers + Enter", fg="blue")
        self.status.pack(pady=5)
        
        self.entry = tk.Entry(root, font=("Consolas", 14), width=15, justify="center")
        self.entry.pack(pady=10)
        
        # Bind Enter for numbers, and KeyRelease for instant letters
        self.entry.bind("<Return>", lambda e: self.run_complex_sequence())
        self.entry.bind("<KeyRelease>", self.check_instant_keys)
        self.entry.focus_set()
        
        tk.Button(root, text="1. Set Target Box", width=20, command=self.calibrate_target).pack(pady=5)
        
    # ==========================================
    # Calibration Overlay
    # ==========================================
    def calibrate_target(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True, "-alpha", 0.3, "-topmost", True)
        self.overlay.configure(bg="black")
        self.overlay.config(cursor="crosshair")
        
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.create_text(
            50, 50, anchor="nw", fill="#00ff66", font=("Segoe UI", 16, "bold"), 
            text="Click the 'Select...' Players box. (Esc to cancel)"
        )
        
        self.overlay.bind("<ButtonPress-1>", self.on_overlay_click)
        self.overlay.bind("<Escape>", lambda e: self.overlay.destroy())

    def on_overlay_click(self, event):
        self.target_coord = (event.x_root, event.y_root)
        self.overlay.destroy()
        
        # Format the coordinates
        coord_text = f"{self.target_coord[0]}, {self.target_coord[1]}"
        
        # Print the coordinates directly to the terminal
        print(f"Calibrated Target Coordinates: ({coord_text})")
        
        # Update UI to show the coordinates
        self.status.config(text=f"Target Set: ({coord_text})\n(Copied to clipboard!)", fg="#007700")
        
        # Automatically copy them to the Windows clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(coord_text)
        
        self._refocus_app()

    # ==========================================
    # Instant Key Logic (No Enter Required)
    # ==========================================
    def check_instant_keys(self, event):
        raw_input = self.entry.get().strip().lower()
        
        # 1. Check for the Exit command first
        if raw_input == 'x':
            self.entry.delete(0, tk.END)
            self.root.destroy()
            return
            
        # 2. If the input is exactly one of our instant command letters
        if raw_input in ['n', 't', 'w']:
            # Clear the box immediately so it doesn't wait for Enter
            self.entry.delete(0, tk.END)
            self.run_instant_command(raw_input)

    def run_instant_command(self, key):
        self.status.config(text=f"Quick command. Pressed '{key.upper()}'.", fg="black")
        self.root.update()
        
        target_x, target_y = self.target_coord
        empty_y = target_y + 300
        
        # Click empty space to focus browser, then press the key
        pyautogui.click(target_x, empty_y)
        time.sleep(0.1)
        pyautogui.press(key)
        
        self._refocus_app()

    # ==========================================
    # Complex Number Sequence (Requires Enter)
    # ==========================================
    def run_complex_sequence(self):
        raw_input = self.entry.get().strip()
        
        if not raw_input:
            return
            
        target_x, target_y = self.target_coord
        empty_y = target_y + 300
        
        players = raw_input.split()
        if len(players) > 3:
            players = players[:3]
            
        self.status.config(text=f"Tagging players: {', '.join(players)}...", fg="black")
        self.root.update()
        
        try:
            # 1. Click empty space to ensure Hudl is focused
            pyautogui.click(target_x, empty_y)
            time.sleep(0.15)
            
            # 2. Press 'y' to confirm the block
            pyautogui.press('y')
            time.sleep(0.5) 
            
            # 3. Click the target box
            pyautogui.click(target_x, target_y)
            time.sleep(0.3)
            
            # 4. Insert numbers and press Tab
            for player_num in players:
                pyautogui.write(player_num)
                time.sleep(0.15)
                pyautogui.press('tab')
                time.sleep(0.15)
                
            # 5. Click 300px down
            pyautogui.click(target_x, empty_y)
            time.sleep(0.3)
            
            # 6. Save with 'e'
            pyautogui.press('e')
            
            self.status.config(text=f"Successfully tagged: {', '.join(players)}", fg="#007700")
            
        except pyautogui.FailSafeException:
            messagebox.showwarning("FailSafe", "Mouse hit the screen corner. Adjust your target coordinates.")
            self.status.config(text="Execution aborted.", fg="red")
            
        finally:
            self._refocus_app()

    # ==========================================
    # Focus Management
    # ==========================================
    def _refocus_app(self):
        self.entry.delete(0, tk.END)
        self.root.after(100, lambda: self.root.focus_force())
        self.root.after(150, lambda: self.entry.focus_set())

if __name__ == "__main__":
    root = tk.Tk()
    app = InteractiveHudlTagger(root)
    root.mainloop()