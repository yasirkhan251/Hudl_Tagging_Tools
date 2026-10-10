"""Hudl PlaySpeed — single-file controller and calibration overlay.

Controls:
    O = decrease playback speed
    P = increase playback speed

All calibration logic and playback controls are intentionally kept in this file.
Per-machine coordinates are saved beside this file in coordinates.json.
"""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

import pyautogui

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "coordinates.json"
SPEEDS = ("0.5x", "1x", "1.5x", "2x", "2.5x")
DEFAULT_SPEED_INDEX = 1
MENU_RENDER_DELAY_MS = 350
IDLE_CLOSE_MS = 3000
NEXT_CLICK_DELAY_MS = 120

CALIBRATION_STEPS = (
    ("menu", "Playback menu button"),
    ("0.5x", "Speed option 0.5x"),
    ("1x", "Speed option 1x"),
    ("1.5x", "Speed option 1.5x"),
    ("2x", "Speed option 2x"),
    ("2.5x", "Speed option 2.5x"),
    ("exit_menu", "Safe point outside the dropdown (close menu)"),
)


def valid_point(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(n, int) and n >= 0 for n in value)
    )


def validate_config(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if not valid_point(data.get("menu")) or not valid_point(data.get("exit_menu")):
        return False
    points = data.get("speeds")
    return isinstance(points, dict) and all(valid_point(points.get(s)) for s in SPEEDS)


def read_config() -> dict[str, Any] | None:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if validate_config(data) else None
    except (OSError, json.JSONDecodeError):
        return None


def write_config(data: dict[str, Any]) -> None:
    if not validate_config(data):
        raise ValueError("Calibration is incomplete; all seven points are required.")
    CONFIG_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class CalibrationOverlay:
    """Fullscreen semi-transparent calibration overlay, styled like Jersey_Number_Tag.py."""

    def __init__(self, parent: tk.Tk, callback) -> None:
        self.parent = parent
        self.callback = callback
        self.step_index = 0
        self.start_x: int | None = None
        self.start_y: int | None = None
        self.rect_id: int | None = None
        self.captured: dict[str, Any] = {
            "version": 1, "menu": None, "speeds": {}, "exit_menu": None
        }
        self.closed = False

        self.window = tk.Toplevel(parent)
        self.window.attributes("-fullscreen", True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.30)
        self.window.configure(bg="black")

        self.canvas = tk.Canvas(
            self.window, bg="black", cursor="crosshair", highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        self.instruction_id = self.canvas.create_text(
            30, 30, anchor="nw", fill="#00ff66",
            text="", font=("Segoe UI", 18, "bold")
        )
        self.detail_id = self.canvas.create_text(
            30, 72, anchor="nw", fill="#ffffff",
            text="Click the target position on the screen. Esc cancels calibration.",
            font=("Segoe UI", 12, "bold")
        )
        self.canvas.bind("<ButtonPress-1>", self._on_click)
        self.window.bind("<Escape>", self.cancel)
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.focus_force()
        self._show_instruction()

    def _current_key(self) -> str:
        return CALIBRATION_STEPS[self.step_index][0]

    def _show_instruction(self) -> None:
        key, label = CALIBRATION_STEPS[self.step_index]
        self.canvas.itemconfig(
            self.instruction_id,
            text=f"COORDINATE SETUP — STEP {self.step_index + 1}/{len(CALIBRATION_STEPS)}\n{label}",
            fill="#33ccff" if key in SPEEDS else "#00ff66",
        )
        if key == "menu":
            detail = "Click the Hudl playback menu button. The app will open it after capture."
        elif key in SPEEDS:
            detail = f"Click the {key} option in the open Hudl menu. The app will select it and reopen the menu."
        else:
            detail = "Click a safe point outside the dropdown. The app will save all points and close the menu."
        self.canvas.itemconfig(self.detail_id, text=detail)

    def _on_click(self, event) -> None:
        if self.closed:
            return
        key = self._current_key()
        point = [int(event.x_root), int(event.y_root)]

        if key == "menu":
            self.captured["menu"] = point
            self._show_next_or_finish()
            try:
                pyautogui.click(*point)
            except Exception as exc:
                self._fail(f"Could not open Hudl's menu: {exc}")
                return
            self.parent.after(MENU_RENDER_DELAY_MS, self._show_instruction)
            return

        if key in SPEEDS:
            self.captured["speeds"][key] = point
            self._show_next_or_finish()
            # The transparent overlay captures the physical click; perform the intended
            # click on the actual Hudl window, then reopen the menu for the next point.
            try:
                pyautogui.click(*point)
            except Exception as exc:
                self._fail(f"Could not select the {key} option: {exc}")
                return
            if self.step_index < len(CALIBRATION_STEPS):
                self.parent.after(150, self._reopen_menu)
            return

        if key == "exit_menu":
            self.captured["exit_menu"] = point
            try:
                pyautogui.click(*point)
                write_config(self.captured)
            except Exception as exc:
                self._fail(f"Could not close the menu or save coordinates: {exc}")
                return
            self._finish()

    def _show_next_or_finish(self) -> None:
        if self.step_index < len(CALIBRATION_STEPS) - 1:
            self.step_index += 1
            self._show_instruction()

    def _reopen_menu(self) -> None:
        if self.closed:
            return
        try:
            pyautogui.click(*self.captured["menu"])
            self.parent.after(MENU_RENDER_DELAY_MS, self._show_instruction)
        except Exception as exc:
            self._fail(f"Could not reopen the playback menu: {exc}")

    def _finish(self) -> None:
        self.closed = True
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        self.callback(self.captured, None)

    def _fail(self, error: str) -> None:
        self.closed = True
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        self.callback(None, error)

    def cancel(self, _event=None) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        self.callback(None, "Calibration cancelled.")


class PlaySpeedApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Hudl PlaySpeed")
        self.root.geometry("650x470")
        self.root.minsize(600, 440)

        self.config_data = read_config()
        self.current_speed_index = DEFAULT_SPEED_INDEX
        self.menu_open = False
        self.processing = False
        self.speed_queue: list[int] = []
        self.idle_job: str | None = None
        self.shortcuts_active = True
        self.calibrating = False
        self.closed = False

        self.status_var = tk.StringVar()
        self.speed_var = tk.StringVar()
        self.coordinate_vars: dict[str, tk.StringVar] = {}
        self._build_ui()
        self._refresh_coordinates()
        self._refresh_status()
        # Tkinter-only shortcuts: active while this application has focus.
        self.root.bind_all("<KeyPress-o>", self._on_tk_keypress)
        self.root.bind_all("<KeyPress-O>", self._on_tk_keypress)
        self.root.bind_all("<KeyPress-p>", self._on_tk_keypress)
        self.root.bind_all("<KeyPress-P>", self._on_tk_keypress)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Hudl PlaySpeed", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(outer, text="O = slower     P = faster     Startup speed assumption = 1x").pack(
            anchor="w", pady=(4, 5)
        )
        ttk.Label(outer, textvariable=self.speed_var, font=("Segoe UI", 13, "bold")).pack(
            anchor="w", pady=(0, 9)
        )

        controls = ttk.Frame(outer)
        controls.pack(anchor="w", pady=(0, 10))
        self.shortcuts_button = ttk.Button(
            controls, text="Tkinter shortcuts enabled", command=self._show_shortcut_help
        )
        self.shortcuts_button.pack(side="left", padx=(0, 8))
        ttk.Button(
            controls, text="Set Targets / Recalibrate", command=self.begin_calibration
        ).pack(side="left")

        ttk.Label(outer, text="Saved coordinates", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        coordinates = ttk.Frame(outer, padding=(0, 5, 0, 7))
        coordinates.pack(fill="x")
        for key, label in (
            ("menu", "Playback menu"),
            ("0.5x", "Speed 0.5x"),
            ("1x", "Speed 1x"),
            ("1.5x", "Speed 1.5x"),
            ("2x", "Speed 2x"),
            ("2.5x", "Speed 2.5x"),
            ("exit_menu", "Close-menu point"),
        ):
            line = ttk.Frame(coordinates)
            line.pack(fill="x", pady=1)
            ttk.Label(line, text=label, width=19).pack(side="left")
            var = tk.StringVar(value="Not set")
            self.coordinate_vars[key] = var
            ttk.Label(line, textvariable=var).pack(side="left")

        ttk.Separator(outer).pack(fill="x", pady=7)
        ttk.Label(outer, textvariable=self.status_var, wraplength=600).pack(anchor="w")
        ttk.Label(
            outer,
            text="Calibration uses the same fullscreen 30%-opacity overlay style as the jersey-number tagger. "
                 "O/P bindings work only while this Tkinter window has focus. Coordinates are stored locally in control_prototype/coordinates.json.",
            wraplength=600,
        ).pack(anchor="w", pady=(8, 0))

    def _refresh_coordinates(self) -> None:
        for key, var in self.coordinate_vars.items():
            point = None
            if self.config_data:
                point = self.config_data.get("speeds", {}).get(key) if key in SPEEDS else self.config_data.get(key)
            var.set(f"({point[0]}, {point[1]})" if valid_point(point) else "Not set")

    def _refresh_status(self) -> None:
        self.speed_var.set(f"Current speed: {SPEEDS[self.current_speed_index]}")
        if self.calibrating:
            self.status_var.set("Calibration overlay active. Follow the instructions on the overlay.")
        elif not self.config_data:
            self.status_var.set("Coordinates not configured. Select Set Targets / Recalibrate.")
        elif self.shortcuts_active:
            self.status_var.set("Tkinter shortcuts active only while this app has focus: O slower, P faster.")
        else:
            self.status_var.set("Coordinates loaded. Click this window, then press O/P.")

    def _show_shortcut_help(self) -> None:
        messagebox.showinfo(
            "Tkinter keyboard bindings",
            "O decreases speed and P increases speed while this PlaySpeed window has focus. "
            "Tkinter cannot receive global shortcuts while Hudl/Chrome is focused.",
            parent=self.root,
        )

    def _on_tk_keypress(self, event) -> str | None:
        if self.closed or self.calibrating:
            return None
        key = event.keysym.lower()
        if key == "o":
            self._queue_speed(-1)
            return "break"
        if key == "p":
            self._queue_speed(1)
            return "break"
        return None

    def _stop_shortcuts(self) -> None:
        # No global hooks are registered; Tkinter bindings are attached to the root.
        self.shortcuts_active = False

    def begin_calibration(self) -> None:
        if self.calibrating:
            return
        self.calibrating = True
        self.speed_queue.clear()
        self.processing = False
        self._cancel_idle_timer()
        self.root.withdraw()
        self.root.after(200, lambda: CalibrationOverlay(self.root, self._calibration_done))

    def _calibration_done(self, data, error) -> None:
        self.calibrating = False
        self.root.deiconify()
        self.root.lift()
        if error:
            self.status_var.set(error)
            self._refresh_coordinates()
            return
        self.config_data = data
        self.current_speed_index = DEFAULT_SPEED_INDEX
        self.menu_open = False
        self._refresh_coordinates()
        self._refresh_status()
        messagebox.showinfo(
            "Coordinates saved",
            f"All coordinates have been saved to:\n{CONFIG_PATH}",
            parent=self.root,
        )

    def _queue_speed(self, delta: int) -> None:
        if self.closed:
            return
        try:
            self.root.after(0, self._handle_speed, delta)
        except RuntimeError:
            pass

    def _handle_speed(self, delta: int) -> None:
        if self.closed or self.calibrating:
            return
        if not self.config_data:
            self.status_var.set("No saved coordinates. Please calibrate first.")
            return
        self.speed_queue.append(delta)
        self._restart_idle_timer()
        if not self.processing:
            self._process_next()

    def _process_next(self) -> None:
        if self.closed or self.processing or not self.speed_queue or not self.config_data:
            return
        self.processing = True
        if not self.menu_open:
            try:
                pyautogui.click(*self.config_data["menu"])
                self.menu_open = True
                self.root.after(MENU_RENDER_DELAY_MS, self._apply_speed_step)
            except Exception as exc:
                self.processing = False
                self.status_var.set(f"Could not open playback menu: {exc}")
        else:
            self._apply_speed_step()

    def _apply_speed_step(self) -> None:
        if self.closed or not self.config_data:
            self.processing = False
            return
        if not self.speed_queue:
            self.processing = False
            return
        delta = self.speed_queue.pop(0)
        next_index = max(0, min(len(SPEEDS) - 1, self.current_speed_index + delta))
        try:
            pyautogui.click(*self.config_data["speeds"][SPEEDS[next_index]])
            self.current_speed_index = next_index
            self.speed_var.set(f"Current speed: {SPEEDS[next_index]}")
            self.status_var.set(f"Playback speed selected: {SPEEDS[next_index]}.")
        except Exception as exc:
            self.status_var.set(f"Could not select speed: {exc}")
        finally:
            self.processing = False
        if self.speed_queue:
            self.root.after(NEXT_CLICK_DELAY_MS, self._process_next)
        else:
            self._restart_idle_timer()

    def _restart_idle_timer(self) -> None:
        self._cancel_idle_timer()
        self.idle_job = self.root.after(IDLE_CLOSE_MS, self._close_menu_after_idle)

    def _cancel_idle_timer(self) -> None:
        if self.idle_job:
            try:
                self.root.after_cancel(self.idle_job)
            except tk.TclError:
                pass
            self.idle_job = None

    def _close_menu_after_idle(self) -> None:
        self.idle_job = None
        if self.closed or not self.menu_open or self.processing or self.speed_queue or not self.config_data:
            return
        try:
            pyautogui.click(*self.config_data["exit_menu"])
            self.menu_open = False
            self.status_var.set("Playback menu closed after 3 seconds without input.")
        except Exception as exc:
            self.status_var.set(f"Could not close playback menu: {exc}")

    def close(self) -> None:
        self.closed = True
        self._cancel_idle_timer()
        self.root.destroy()


def main() -> None:
    pyautogui.PAUSE = 0.03
    pyautogui.FAILSAFE = True
    root = tk.Tk()
    PlaySpeedApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
