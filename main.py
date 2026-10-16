"""
============================================================
HUDL TAGGING TOOLS - UNIVERSAL DASHBOARD
============================================================

Launch this file to access all Hudl automation tools from one
central dashboard.

Run:
    python main.py

The dashboard intentionally launches each tool as an independent
window/process. This keeps each existing tool's Tkinter/OpenCV
event loop isolated and prevents one tool from breaking another.
"""

from __future__ import annotations

import ctypes
import math
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import keyboard
import pyautogui


APP_TITLE = "Hudl Tagging Tools"
APP_SUBTITLE = "Volleyball automation & sports tagging dashboard"

BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

TOOLS = {
    "jersey": {
        "name": "Jersey Number Tagger",
        "subtitle": "YOLO + EasyOCR + Vosk + Manual",
        "description": (
            "Detect and tag jersey numbers using computer vision, "
            "offline speech recognition and manual input."
        ),
        "script": "Jersey_Number_Tag.py",
        "accent": "#2563eb",
        "icon": "01",
    },
    "block": {
        "name": "Interactive Block Tagger",
        "subtitle": "Fast multi-player block tagging",
        "description": (
            "Quickly enter block player numbers and automate "
            "the Hudl confirmation and save workflow."
        ),
        "script": "blocksystem.py",
        "accent": "#7c3aed",
        "icon": "02",
    },
    "attack2d": {
        "name": "Attack Location 2D",
        "subtitle": "Randomized iteration tagger",
        "description": (
            "Generate fast randomized top-to-bottom or "
            "bottom-to-top attack locations with automatic E tagging."
        ),
        "script": "attack_location_2d_iteration.py",
        "accent": "#059669",
        "icon": "03",
    },
    "attack3d": {
        "name": "Attack Location 3D",
        "subtitle": "Court geometry & radar",
        "description": (
            "Calibrate court geometry, capture hit/landing points "
            "and visualize attack trajectories on a 2D radar."
        ),
        "script": "attack_location_3d.py",
        "accent": "#ea580c",
        "icon": "04",
    },
    "clicker": {
        "name": "Auto Mouse & Keyboard Clicker",
        "subtitle": "F6 Mouse / F7 Keyboard / F8 Sequence",
        "description": (
            "Repeat mouse clicks, keyboard keys or click-plus-key sequences. "
            "Cursor color indicates the active mode; Esc stops all automation."
        ),
        "accent": "#db2777",
        "icon": "05",
    },
}


class HudlDashboard:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.processes: dict[str, subprocess.Popen] = {}
        self.clicker_app = None
        self.status_var = tk.StringVar(value="System ready")

        self._configure_window()
        self._build_ui()
        self._refresh_process_states()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _configure_window(self):
        self.root.title(APP_TITLE)
        self.root.geometry("1040x850")
        self.root.minsize(860, 700)
        self.root.configure(bg="#0b1120")

        try:
            self.root.iconname(APP_TITLE)
        except Exception:
            pass

    def _build_ui(self):
        # ---------------- Header ----------------
        header = tk.Frame(self.root, bg="#0b1120")
        header.pack(fill="x", padx=34, pady=(28, 10))

        brand = tk.Frame(header, bg="#0b1120")
        brand.pack(side="left")

        tk.Label(
            brand,
            text="🏐",
            bg="#0b1120",
            fg="white",
            font=("Segoe UI Emoji", 30),
        ).pack(side="left", padx=(0, 12))

        title_box = tk.Frame(brand, bg="#0b1120")
        title_box.pack(side="left")

        tk.Label(
            title_box,
            text=APP_TITLE,
            bg="#0b1120",
            fg="#f8fafc",
            font=("Segoe UI", 22, "bold"),
        ).pack(anchor="w")

        tk.Label(
            title_box,
            text=APP_SUBTITLE,
            bg="#0b1120",
            fg="#94a3b8",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 0))

        # Status pill
        status = tk.Label(
            header,
            textvariable=self.status_var,
            bg="#132238",
            fg="#67e8f9",
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=7,
        )
        status.pack(side="right", anchor="n")

        # ---------------- Divider ----------------
        tk.Frame(
            self.root,
            bg="#1e293b",
            height=1,
        ).pack(fill="x", padx=34, pady=(8, 22))

        # ---------------- Intro ----------------
        intro = tk.Frame(self.root, bg="#0b1120")
        intro.pack(fill="x", padx=34, pady=(0, 16))

        tk.Label(
            intro,
            text="Choose a tagging tool",
            bg="#0b1120",
            fg="#e2e8f0",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")

        tk.Label(
            intro,
            text=(
                "Each tool opens independently so its automation, keyboard "
                "hooks and OpenCV/Tkinter event loop remain isolated."
            ),
            bg="#0b1120",
            fg="#64748b",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        # ---------------- Cards ----------------
        grid = tk.Frame(self.root, bg="#0b1120")
        grid.pack(fill="both", expand=True, padx=34)

        cards = [
            ("jersey", 0, 0),
            ("block", 0, 1),
            ("attack2d", 1, 0),
            ("attack3d", 1, 1),
            ("clicker", 2, 0),
        ]

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)
        grid.rowconfigure(2, weight=1)

        for key, row, column in cards:
            self._create_tool_card(grid, key, row, column)

        # ---------------- Footer ----------------
        footer = tk.Frame(self.root, bg="#0b1120")
        footer.pack(fill="x", padx=34, pady=(18, 25))

        tk.Label(
            footer,
            text="Hudl Tagging Tools  •  Python automation suite",
            bg="#0b1120",
            fg="#475569",
            font=("Segoe UI", 8),
        ).pack(side="left")

        tk.Button(
            footer,
            text="EXIT DASHBOARD",
            command=self.close,
            bg="#1e293b",
            fg="#cbd5e1",
            activebackground="#334155",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right")

    def _create_tool_card(
        self,
        parent: tk.Frame,
        key: str,
        row: int,
        column: int,
    ):
        tool = TOOLS[key]

        outer = tk.Frame(
            parent,
            bg="#172033",
            highlightbackground="#263449",
            highlightthickness=1,
        )
        outer.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=8,
            pady=8,
        )

        # Accent strip
        tk.Frame(
            outer,
            bg=tool["accent"],
            height=5,
        ).pack(fill="x")

        content = tk.Frame(outer, bg="#172033")
        content.pack(fill="both", expand=True, padx=22, pady=20)

        top = tk.Frame(content, bg="#172033")
        top.pack(fill="x")

        badge = tk.Label(
            top,
            text=tool["icon"],
            bg=tool["accent"],
            fg="white",
            font=("Segoe UI", 9, "bold"),
            width=4,
            height=2,
        )
        badge.pack(side="left")

        title_box = tk.Frame(top, bg="#172033")
        title_box.pack(side="left", padx=12)

        tk.Label(
            title_box,
            text=tool["name"],
            bg="#172033",
            fg="#f8fafc",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")

        tk.Label(
            title_box,
            text=tool["subtitle"],
            bg="#172033",
            fg=tool["accent"],
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            content,
            text=tool["description"],
            bg="#172033",
            fg="#94a3b8",
            justify="left",
            anchor="nw",
            wraplength=360,
            font=("Segoe UI", 9),
        ).pack(fill="both", expand=True, pady=(18, 14))

        bottom = tk.Frame(content, bg="#172033")
        bottom.pack(fill="x")

        state_label = tk.Label(
            bottom,
            text="READY",
            bg="#172033",
            fg="#64748b",
            font=("Segoe UI", 8, "bold"),
        )
        state_label.pack(side="left")

        button = tk.Button(
            bottom,
            text="OPEN TOOL  →",
            command=lambda k=key: self.launch_tool(k),
            bg=tool["accent"],
            fg="white",
            activebackground=tool["accent"],
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 8, "bold"),
        )
        button.pack(side="right")

        # Keep references for live process-state updates.
        tool["state_label"] = state_label
        tool["button"] = button

        # Make the entire card surface clickable, not just the button.
        self._bind_card_surface(outer, key)

    def _bind_card_surface(self, widget: tk.Widget, key: str):
        """Bind card frames and labels to the same launch action."""
        if not isinstance(widget, tk.Button):
            try:
                widget.configure(cursor="hand2")
            except tk.TclError:
                pass
            widget.bind(
                "<Button-1>",
                lambda event, tool_key=key: self.launch_tool(tool_key),
                add="+",
            )

        for child in widget.winfo_children():
            self._bind_card_surface(child, key)

    def launch_tool(self, key: str):
        tool = TOOLS[key]

        # The clicker is embedded in main.py and runs inside this process.
        if key == "clicker":
            if self.clicker_app is not None:
                try:
                    if self.clicker_app.root.winfo_exists():
                        self.clicker_app.root.deiconify()
                        self.clicker_app.root.lift()
                        self.clicker_app.root.focus_force()
                        self.status_var.set("Auto Mouse & Keyboard Clicker is open")
                        return
                except tk.TclError:
                    self.clicker_app = None

            clicker_window = tk.Toplevel(self.root)
            self.clicker_app = AutoClickerApp(
                clicker_window,
                on_close=self._on_clicker_closed,
            )
            tool["state_label"].config(text="OPEN", fg="#22c55e")
            tool["button"].config(text="OPEN  ✓")
            self.status_var.set("Auto Mouse & Keyboard Clicker opened")
            return
        if getattr(sys, "frozen", False):
            # Packaged Windows build: each tool is its own executable.
            script_path = BASE_DIR / "tools" / (Path(tool["script"]).stem + ".exe")
            launch_command = [str(script_path)]
        else:
            script_path = BASE_DIR / tool["script"]
            launch_command = [sys.executable, str(script_path)]

        if not script_path.exists():
            self.status_var.set(f"Missing: {tool['script']}")
            messagebox.showerror(
                "Tool Not Found",
                f"Could not find:\n\n{script_path}",
                parent=self.root,
            )
            return

        existing = self.processes.get(key)
        if existing is not None and existing.poll() is None:
            self.status_var.set(f"{tool['name']} is already running")
            return

        try:
            process = subprocess.Popen(
                launch_command,
                cwd=str(BASE_DIR),
            )
            self.processes[key] = process

            tool["state_label"].config(
                text="RUNNING",
                fg="#22c55e",
            )
            tool["button"].config(
                text="RUNNING  ✓",
            )

            self.status_var.set(f"{tool['name']} launched")

        except Exception as error:
            self.status_var.set("Launch failed")
            messagebox.showerror(
                "Launch Error",
                f"Could not launch {tool['name']}.\n\n{error}",
                parent=self.root,
            )

    def _on_clicker_closed(self):
        self.clicker_app = None
        tool = TOOLS["clicker"]
        if "state_label" in tool:
            tool["state_label"].config(text="READY", fg="#64748b")
            tool["button"].config(text="OPEN TOOL  →")

    def _refresh_process_states(self):
        for key, tool in TOOLS.items():
            process = self.processes.get(key)

            if process is None:
                continue

            if process.poll() is not None:
                tool["state_label"].config(
                    text="READY",
                    fg="#64748b",
                )
                tool["button"].config(
                    text="OPEN TOOL  →",
                )

        self.root.after(750, self._refresh_process_states)

    def close(self):
        running = []

        for key, process in list(self.processes.items()):
            if process.poll() is None:
                running.append(TOOLS[key]["name"])

        if running:
            answer = messagebox.askyesno(
                "Close Dashboard",
                (
                    "These tools are still running:\n\n"
                    + "\n".join(f"• {name}" for name in running)
                    + "\n\nClose them and exit the dashboard?"
                ),
                parent=self.root,
            )

            if not answer:
                return

        for process in self.processes.values():
            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

        if self.clicker_app is not None:
            try:
                self.clicker_app.close()
            except tk.TclError:
                pass

        self.root.destroy()


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
    def __init__(self, root: tk.Toplevel, on_close=None):
        self.root = root
        self.on_close = on_close
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
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        callback = self.on_close
        self.on_close = None
        if callback:
            callback()


def main():
    root = tk.Tk()
    HudlDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
