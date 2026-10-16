"""Auto Mouse & Keyboard Clicker integrated into Hudl Tagging Tools.

Hotkeys:
    F6  Toggle mouse click repeater (red cursor)
    F7  Toggle keyboard repeater (blue cursor)
    F8  Toggle mouse + key sequence (purple cursor)
    Esc Stop every mode and restore the normal cursor
"""
from __future__ import annotations

import ctypes
import math
import shutil
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import keyboard
import pyautogui

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

IS_WINDOWS = sys.platform == "win32"
SPI_SETCURSORS = 0x0057
SYSTEM_CURSORS = (
    32512, 32513, 32514, 32515, 32516, 32640, 32641, 32642,
    32643, 32644, 32645, 32646, 32648, 32649, 32650, 32651,
)


class CursorColorManager:
    """Temporarily replace Windows system cursors and restore defaults afterward."""

    def __init__(self):
        self.user32 = ctypes.windll.user32 if IS_WINDOWS else None
        self.enabled = self.user32 is not None
        self.temp_dir = Path(tempfile.mkdtemp(prefix="hudl_cursor_colors_"))
        self.paths = {
            "red": self.temp_dir / "red.cur",
            "blue": self.temp_dir / "blue.cur",
            "purple": self.temp_dir / "purple.cur",
        }
        for name, rgb in {
            "red": (238, 45, 60),
            "blue": (40, 130, 255),
            "purple": (175, 70, 235),
        }.items():
            self._write_cursor(self.paths[name], rgb)

    @staticmethod
    def _write_cursor(path: Path, rgb: tuple[int, int, int]) -> None:
        width = height = 32
        red, green, blue = rgb

        def shape(x: int, y: int) -> bool:
            if y < 0 or y > 25 or x < 0 or x > y // 2 + 2:
                return False
            return not (y > 16 and x > 8)

        pixels, mask = bytearray(), bytearray()
        for y in range(height - 1, -1, -1):
            for x in range(width):
                filled = shape(x, y)
                edge = filled and any(
                    not shape(x + dx, y + dy)
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                    if 0 <= x + dx < width and 0 <= y + dy < height
                )
                if filled:
                    r, g, b = (18, 18, 18) if edge else (red, green, blue)
                    pixels.extend((b, g, r, 255))
                else:
                    pixels.extend((0, 0, 0, 0))

        # 1-bit transparency mask: bottom-up rows aligned to 32 bits.
        for y in range(height - 1, -1, -1):
            row = bytearray(4)
            for x in range(width):
                if not shape(x, y):
                    row[x // 8] |= 1 << (7 - x % 8)
            mask.extend(row)

        dib_header = (
            (40).to_bytes(4, "little")
            + width.to_bytes(4, "little", signed=True)
            + (height * 2).to_bytes(4, "little", signed=True)
            + (1).to_bytes(2, "little")
            + (32).to_bytes(2, "little")
            + bytes(4)
            + (len(pixels) + len(mask)).to_bytes(4, "little")
            + bytes(16)
        )
        dib = dib_header + pixels + mask
        directory = bytes(2) + (2).to_bytes(2, "little") + (1).to_bytes(2, "little")
        entry = (
            bytes((width, height, 0, 0))
            + (0).to_bytes(2, "little")
            + (0).to_bytes(2, "little")
            + len(dib).to_bytes(4, "little")
            + (22).to_bytes(4, "little")
        )
        path.write_bytes(directory + entry + dib)

    def set_color(self, color: str | None) -> None:
        if not self.enabled:
            return
        if color is None:
            self.restore()
            return

        try:
            load_cursor = self.user32.LoadCursorFromFileW
            load_cursor.argtypes = [ctypes.c_wchar_p]
            load_cursor.restype = ctypes.c_void_p
            set_cursor = self.user32.SetSystemCursor
            set_cursor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            set_cursor.restype = ctypes.c_bool
            source = str(self.paths[color])
            for cursor_id in SYSTEM_CURSORS:
                handle = load_cursor(source)
                if handle:
                    set_cursor(handle, cursor_id)
        except Exception:
            # Cursor appearance is cosmetic; don't stop automation if it fails.
            pass

    def restore(self) -> None:
        if self.enabled:
            try:
                self.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
            except Exception:
                pass

    def cleanup(self) -> None:
        self.restore()
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class AutoClickerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Auto Mouse & Keyboard Clicker")
        self.root.geometry("600x700")
        self.root.minsize(550, 650)
        self.root.configure(bg="#0b1120")

        self.cursor = CursorColorManager()
        self.modes = {"mouse": False, "keyboard": False, "sequence": False}
        self.mode_lock = threading.RLock()
        self.stop_events = {name: threading.Event() for name in self.modes}
        self.workers: dict[str, threading.Thread] = {}
        self.hotkeys_registered = False

        self.mouse_button = tk.StringVar(value="left")
        self.mouse_delay = tk.StringVar(value="00:00:00.100")
        self.keyboard_key = tk.StringVar(value="e")
        self.keyboard_delay = tk.StringVar(value="00:00:00.100")
        self.sequence_key = tk.StringVar(value="e")
        self.sequence_delay = tk.StringVar(value="00:00:00.100")
        self.status_var = tk.StringVar(value="Ready — press F6, F7 or F8 to start")
        self.cursor_var = tk.StringVar(value="Cursor: normal")

        self._build_ui()
        self._register_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#0b1120")
        header.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(
            header,
            text="Auto Mouse & Keyboard Clicker",
            bg="#0b1120",
            fg="#f8fafc",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Mouse repeater, key repeater, and click-plus-key sequence",
            bg="#0b1120",
            fg="#94a3b8",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        hotkey_box = tk.LabelFrame(
            self.root,
            text="Global hotkeys",
            bg="#111b2e",
            fg="#e2e8f0",
            padx=12,
            pady=8,
            font=("Segoe UI", 9, "bold"),
        )
        hotkey_box.pack(fill="x", padx=24, pady=10)
        for line in (
            "F6 — Toggle mouse click repeater (red cursor)",
            "F7 — Toggle keyboard repeater (blue cursor)",
            "F8 — Toggle mouse + key sequence (purple cursor)",
            "Esc — Stop all modes and restore the normal cursor",
        ):
            tk.Label(
                hotkey_box,
                text=line,
                bg="#111b2e",
                fg="#cbd5e1",
                font=("Consolas", 9),
            ).pack(anchor="w", pady=1)

        self._build_panel(
            "F6 • Mouse click repeater", "#fca5a5", "mouse", "#b91c1c",
            [("Button", self.mouse_button, ("left", "right", "middle")),
             ("Delay HH:MM:SS.mmm", self.mouse_delay, None)],
        )
        self._build_panel(
            "F7 • Keyboard repeater", "#93c5fd", "keyboard", "#1d4ed8",
            [("Key", self.keyboard_key, None),
             ("Delay HH:MM:SS.mmm", self.keyboard_delay, None)],
        )
        self._build_panel(
            "F8 • Mouse + key sequence", "#d8b4fe", "sequence", "#7e22ce",
            [("Key", self.sequence_key, None),
             ("Delay HH:MM:SS.mmm", self.sequence_delay, None)],
        )

        footer = tk.Frame(self.root, bg="#0b1120")
        footer.pack(fill="both", expand=True, padx=24, pady=(8, 18))
        tk.Label(
            footer,
            textvariable=self.cursor_var,
            bg="#0b1120",
            fg="#e9d5ff",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg="#0b1120",
            fg="#94a3b8",
            wraplength=540,
            justify="left",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(5, 8))
        tk.Button(
            footer,
            text="STOP ALL (Esc)",
            command=self.stop_all,
            bg="#334155",
            fg="white",
            relief="flat",
            padx=14,
            pady=7,
        ).pack(side="left")

    def _build_panel(self, title, fg, mode, button_color, fields):
        panel = tk.LabelFrame(
            self.root,
            text=title,
            bg="#111b2e",
            fg=fg,
            padx=12,
            pady=8,
            font=("Segoe UI", 10, "bold"),
        )
        panel.pack(fill="x", padx=24, pady=6)
        row = tk.Frame(panel, bg="#111b2e")
        row.pack(fill="x")

        for label, variable, options in fields:
            tk.Label(row, text=label + ":", bg="#111b2e", fg="#cbd5e1").pack(side="left")
            if options:
                ttk.Combobox(
                    row,
                    textvariable=variable,
                    values=options,
                    state="readonly",
                    width=8,
                ).pack(side="left", padx=(4, 10))
            else:
                tk.Entry(row, textvariable=variable, width=10).pack(side="left", padx=(4, 10))

        hotkey = {"mouse": "F6", "keyboard": "F7", "sequence": "F8"}[mode]
        tk.Button(
            panel,
            text=f"Start / Stop ({hotkey})",
            command=lambda name=mode: self.toggle_mode(name),
            bg=button_color,
            fg="white",
            relief="flat",
            padx=10,
            pady=5,
        ).pack(anchor="e", pady=(7, 0))

    @staticmethod
    def _parse_delay(value: str) -> float:
        """Parse HH:MM:SS.mmm or a delay specified in seconds."""
        value = value.strip()
        if not value:
            raise ValueError("Delay cannot be empty.")

        if ":" not in value:
            seconds = float(value)
        else:
            parts = value.split(":")
            if len(parts) != 3:
                raise ValueError("Use HH:MM:SS.mmm, for example 00:00:00.100.")
            hours, minutes = int(parts[0]), int(parts[1])
            seconds_part = float(parts[2])
            if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds_part < 60:
                raise ValueError("Hours must be non-negative; minutes and seconds must be below 60.")
            seconds = hours * 3600 + minutes * 60 + seconds_part

        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Delay must be a finite, non-negative number.")
        return seconds

    @staticmethod
    def _parse_key(value: str) -> str:
        key = value.strip().lower()
        if len(key) == 1:
            return key
        key = {"return": "enter", "del": "delete", "pgup": "pageup", "pgdn": "pagedown"}.get(key, key)
        valid = {
            "enter", "space", "tab", "backspace", "delete", "home", "end",
            "pageup", "pagedown", "up", "down", "left", "right", "insert", "esc",
            *(f"f{i}" for i in range(1, 13)),
        }
        if key not in valid:
            raise ValueError(f"Unsupported key name: {value}")
        return key

    def _register_hotkeys(self):
        try:
            keyboard.add_hotkey("f6", lambda: self.root.after(0, self.toggle_mode, "mouse"))
            keyboard.add_hotkey("f7", lambda: self.root.after(0, self.toggle_mode, "keyboard"))
            keyboard.add_hotkey("f8", lambda: self.root.after(0, self.toggle_mode, "sequence"))
            keyboard.add_hotkey("esc", lambda: self.root.after(0, self.stop_all))
            self.hotkeys_registered = True
        except Exception as exc:
            self.status_var.set(f"Global hotkeys unavailable ({exc}); use the buttons instead.")

    def _mode_settings(self, mode: str):
        if mode == "mouse":
            return self._parse_delay(self.mouse_delay.get()), None, self.mouse_button.get()
        if mode == "keyboard":
            return self._parse_delay(self.keyboard_delay.get()), self._parse_key(self.keyboard_key.get()), None
        return self._parse_delay(self.sequence_delay.get()), self._parse_key(self.sequence_key.get()), "left"

    def toggle_mode(self, mode: str):
        if self.modes[mode]:
            self._stop_mode(mode)
            return

        try:
            settings = self._mode_settings(mode)
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Invalid settings", str(exc), parent=self.root)
            return

        with self.mode_lock:
            stop_event = threading.Event()
            self.stop_events[mode] = stop_event
            self.modes[mode] = True

        worker = threading.Thread(
            target=self._run_mode,
            args=(mode, settings, stop_event),
            daemon=True,
            name=f"AutoClicker-{mode}",
        )
        self.workers[mode] = worker
        worker.start()
        self._update_cursor()
        self.status_var.set(f"{mode.title()} mode started.")

    def _stop_mode(self, mode: str):
        with self.mode_lock:
            self.modes[mode] = False
            self.stop_events[mode].set()
        self._update_cursor()
        self.status_var.set(f"{mode.title()} mode stopped.")

    def _run_mode(self, mode: str, settings, stop_event: threading.Event):
        delay, key, button = settings
        try:
            while not stop_event.is_set():
                if mode == "mouse":
                    pyautogui.click(button=button)
                elif mode == "keyboard":
                    pyautogui.press(key)
                else:
                    pyautogui.click(button=button)
                    pyautogui.press(key)

                if stop_event.wait(delay):
                    break
        except pyautogui.FailSafeException:
            self.root.after(0, self.stop_all)
        except Exception as exc:
            self.root.after(0, lambda err=str(exc): self.status_var.set(f"{mode.title()} mode error: {err}"))
            self.root.after(0, self.stop_all)

    def _update_cursor(self):
        active_modes = [name for name, enabled in self.modes.items() if enabled]
        if not active_modes:
            color, label = None, "Cursor: NORMAL"
        elif "sequence" in active_modes or len(active_modes) > 1:
            color, label = "purple", "Cursor: PURPLE (sequence / multiple modes)"
        elif active_modes[0] == "mouse":
            color, label = "red", "Cursor: RED (mouse mode)"
        else:
            color, label = "blue", "Cursor: BLUE (keyboard mode)"

        self.cursor.set_color(color)
        self.cursor_var.set(label)

    def stop_all(self):
        with self.mode_lock:
            for mode in self.modes:
                self.modes[mode] = False
                self.stop_events[mode].set()
        self._update_cursor()
        self.status_var.set("All automation stopped; normal cursor restored.")

    def close(self):
        self.stop_all()
        if self.hotkeys_registered:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
        self.cursor.cleanup()
        self.root.destroy()


def main():
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
