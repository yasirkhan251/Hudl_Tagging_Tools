import tkinter as tk
import pyautogui

def update_position():
    x, y = pyautogui.position()
    label.config(text=f"X: {x} | Y: {y}")
    # Schedule the next check in 30 ms
    root.after(30, update_position)

root = tk.Tk()
root.title("Cursor Position")
root.geometry("350x150")
root.resizable(False, False)

# Keep the window floating above all other applications
root.attributes("-topmost", True)

label = tk.Label(root, font=("Helvetica", 14, "bold"), fg="#1a73e8")
label.pack(expand=True)

update_position()
root.mainloop()