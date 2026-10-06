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

import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


APP_TITLE = "Hudl Tagging Tools"
APP_SUBTITLE = "Volleyball automation & sports tagging dashboard"

BASE_DIR = Path(__file__).resolve().parent

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
}


class HudlDashboard:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.processes: dict[str, subprocess.Popen] = {}
        self.status_var = tk.StringVar(value="System ready")

        self._configure_window()
        self._build_ui()
        self._refresh_process_states()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _configure_window(self):
        self.root.title(APP_TITLE)
        self.root.geometry("940x720")
        self.root.minsize(820, 650)
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
        ]

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

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

    def launch_tool(self, key: str):
        tool = TOOLS[key]
        script_path = BASE_DIR / tool["script"]

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
            try:
                existing.terminate()
            except Exception:
                pass
            self.status_var.set(f"{tool['name']} is already running")
            return

        try:
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
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

        self.root.destroy()


def main():
    root = tk.Tk()
    HudlDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
