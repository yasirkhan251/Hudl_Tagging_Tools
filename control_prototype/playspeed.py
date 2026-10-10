"""Standalone Hudl playback-speed prototype.

Global shortcuts: O decreases speed, P increases speed.
During calibration, LEFT-CLICK each target to capture its coordinates.
Coordinates are stored locally in coordinates.json and reused on next launch.
"""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

import keyboard
import pyautogui
from pynput import mouse

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "coordinates.json"
SPEEDS = ("0.5x", "1x", "1.5x", "2x", "2.5x")
DEFAULT_SPEED_INDEX = 1
IDLE_CLOSE_MS = 3000
MENU_RENDER_DELAY_MS = 350
NEXT_CLICK_DELAY_MS = 120


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
    return isinstance(points, dict) and all(valid_point(points.get(speed)) for speed in SPEEDS)


class PlaySpeedApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Hudl PlaySpeed — Prototype")
        self.root.geometry("610x500")
        self.root.minsize(560, 460)

        self.config_data: dict[str, Any] | None = self.load_config()
        self.current_speed_index = DEFAULT_SPEED_INDEX
        self.menu_open = False
        self.processing_queue = False
        self.speed_queue: list[int] = []
        self.idle_job: str | None = None
        self.calibration_stage: str | None = None
        self.calibration_data: dict[str, Any] = {
            "version": 1, "menu": None, "speeds": {}, "exit_menu": None
        }
        self.hotkeys: list[Any] = []
        self.listener_started = False
        self.mouse_listener: mouse.Listener | None = None
        self.closed = False

        self.status_var = tk.StringVar()
        self.speed_var = tk.StringVar(value=f"Current speed: {SPEEDS[self.current_speed_index]}")
        self.coordinate_vars: dict[str, tk.StringVar] = {}
        self._build_ui()
        self._refresh_status()
        self._refresh_coordinates()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Hudl PlaySpeed", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(
            outer, text="O = slower     P = faster     Default starting speed = 1x",
            wraplength=550,
        ).pack(anchor="w", pady=(4, 8))
        ttk.Label(outer, textvariable=self.speed_var, font=("Segoe UI", 13, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        buttons = ttk.Frame(outer)
        buttons.pack(anchor="w", pady=(0, 10))
        self.listener_button = ttk.Button(
            buttons, text="Start global shortcuts", command=self.toggle_listener
        )
        self.listener_button.pack(side="left", padx=(0, 8))
        ttk.Button(
            buttons, text="Calibrate / change coordinates", command=self.begin_calibration
        ).pack(side="left")

        ttk.Label(outer, text="Saved / captured coordinates",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        coords = ttk.Frame(outer, padding=(0, 5, 0, 8))
        coords.pack(fill="x")
        for key, label in (
            ("menu", "Menu button"), ("0.5x", "Speed 0.5x"), ("1x", "Speed 1x"),
            ("1.5x", "Speed 1.5x"), ("2x", "Speed 2x"), ("2.5x", "Speed 2.5x"),
            ("exit_menu", "Close menu"),
        ):
            row = ttk.Frame(coords)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label, width=18).pack(side="left")
            var = tk.StringVar(value="Not set")
            self.coordinate_vars[key] = var
            ttk.Label(row, textvariable=var).pack(side="left")

        ttk.Separator(outer).pack(fill="x", pady=7)
        ttk.Label(outer, textvariable=self.status_var, wraplength=550).pack(anchor="w")
        ttk.Label(
            outer,
            text="During calibration, LEFT-CLICK each target on Hudl to capture coordinates. "
                 "The click may select a speed, so the menu is reopened between speed captures.",
            wraplength=550,
        ).pack(anchor="w", pady=(8, 0))

    def load_config(self) -> dict[str, Any] | None:
        if not CONFIG_PATH.exists():
            return None
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return data if validate_config(data) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _coordinate_for(self, key: str) -> Any:
        data = self.calibration_data if self.calibration_stage else self.config_data
        if not data:
            return None
        return data.get("speeds", {}).get(key) if key in SPEEDS else data.get(key)

    def _refresh_coordinates(self) -> None:
        for key, var in self.coordinate_vars.items():
            point = self._coordinate_for(key)
            var.set(f"({point[0]}, {point[1]})" if valid_point(point) else "Not set")

    def save_config(self) -> None:
        if not validate_config(self.calibration_data):
            raise ValueError("Calibration is incomplete. Capture every coordinate before saving.")
        CONFIG_PATH.write_text(
            json.dumps(self.calibration_data, indent=2) + "\n", encoding="utf-8"
        )
        self.config_data = json.loads(json.dumps(self.calibration_data))
        self._refresh_coordinates()

    def _refresh_status(self) -> None:
        self.speed_var.set(f"Current speed: {SPEEDS[self.current_speed_index]}")
        if self.calibration_stage:
            self.status_var.set(f"CALIBRATION: {self._stage_instructions(self.calibration_stage)}")
        elif not self.config_data:
            self.status_var.set("Coordinates not configured. Click “Calibrate / change coordinates” first.")
        elif self.listener_started:
            self.status_var.set("Ready. O = slower, P = faster. Keep Hudl/Chrome focused.")
        else:
            self.status_var.set("Coordinates loaded. Start global shortcuts when ready.")

    def _start_listener(self) -> bool:
        if self.listener_started:
            return True
        try:
            self.hotkeys.append(keyboard.add_hotkey(
                "o", lambda: self._queue_speed_change(-1), suppress=False
            ))
            self.hotkeys.append(keyboard.add_hotkey(
                "p", lambda: self._queue_speed_change(1), suppress=False
            ))
            self.mouse_listener = mouse.Listener(on_click=self._on_global_mouse_click)
            self.mouse_listener.start()
            self.listener_started = True
            self.listener_button.configure(text="Stop global shortcuts")
            return True
        except Exception as exc:
            self._stop_listener()
            messagebox.showerror(
                "Global input unavailable",
                f"Could not start global keyboard/mouse listeners.\n\n{exc}\n\n"
                "Install requirements and check OS permissions.", parent=self.root
            )
            return False

    def _on_global_mouse_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        if pressed and button == mouse.Button.left and self.calibration_stage and not self.closed:
            try:
                self.root.after(0, self._accept_calibration_point, [int(x), int(y)])
            except RuntimeError:
                pass

    def toggle_listener(self) -> None:
        if self.listener_started:
            self._stop_listener()
        else:
            self._start_listener()
        self._refresh_status()

    def _stop_listener(self) -> None:
        for hotkey in self.hotkeys:
            try:
                keyboard.remove_hotkey(hotkey)
            except Exception:
                pass
        self.hotkeys.clear()
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception:
                pass
            self.mouse_listener = None
        self.listener_started = False
        if hasattr(self, "listener_button"):
            self.listener_button.configure(text="Start global shortcuts")

    def _queue_speed_change(self, delta: int) -> None:
        if self.closed:
            return
        try:
            self.root.after(0, self._handle_speed_key, delta)
        except RuntimeError:
            pass

    def _handle_speed_key(self, delta: int) -> None:
        if self.closed or self.calibration_stage:
            return
        if not self.config_data:
            self.status_var.set("No valid coordinates. Calibrate before using O/P.")
            return
        self.speed_queue.append(delta)
        self._restart_idle_timer()
        if not self.processing_queue:
            self._process_next_speed_change()

    def _process_next_speed_change(self) -> None:
        if self.closed or self.processing_queue or not self.speed_queue:
            return
        if not self.config_data:
            self.speed_queue.clear()
            return
        self.processing_queue = True
        if not self.menu_open:
            try:
                pyautogui.click(*self.config_data["menu"])
                self.menu_open = True
                # Wait longer than the observed Hudl dropdown animation.
                self.root.after(MENU_RENDER_DELAY_MS, self._apply_one_speed_change)
            except Exception as exc:
                self.processing_queue = False
                self.status_var.set(f"Could not click the playback menu: {exc}")
        else:
            self._apply_one_speed_change()

    def _apply_one_speed_change(self) -> None:
        if self.closed or not self.config_data:
            self.processing_queue = False
            return
        if not self.speed_queue:
            self.processing_queue = False
            return
        delta = self.speed_queue.pop(0)
        new_index = max(0, min(len(SPEEDS) - 1, self.current_speed_index + delta))
        try:
            pyautogui.click(*self.config_data["speeds"][SPEEDS[new_index]])
            self.current_speed_index = new_index
            self.speed_var.set(f"Current speed: {SPEEDS[self.current_speed_index]}")
            self.status_var.set(
                f"Set playback speed to {SPEEDS[self.current_speed_index]}. "
                "Menu closes after 3 seconds of inactivity."
            )
        except Exception as exc:
            self.status_var.set(f"Could not click a speed option: {exc}")
        finally:
            self.processing_queue = False
        if self.speed_queue:
            self.root.after(NEXT_CLICK_DELAY_MS, self._process_next_speed_change)
        else:
            self._restart_idle_timer()

    def _restart_idle_timer(self) -> None:
        if self.idle_job:
            try:
                self.root.after_cancel(self.idle_job)
            except tk.TclError:
                pass
        self.idle_job = self.root.after(IDLE_CLOSE_MS, self._close_menu_after_idle)

    def _close_menu_after_idle(self) -> None:
        self.idle_job = None
        if self.closed or not self.menu_open or self.processing_queue or self.speed_queue:
            return
        if not self.config_data:
            return
        try:
            pyautogui.click(*self.config_data["exit_menu"])
            self.menu_open = False
            self.status_var.set("Playback menu closed after 3 seconds of inactivity.")
        except Exception as exc:
            self.status_var.set(f"Could not close the playback menu: {exc}")

    def _stage_instructions(self, stage: str) -> str:
        if stage == "menu":
            return "LEFT-CLICK the Hudl playback menu button to capture its coordinates."
        if stage == "exit_menu":
            return "LEFT-CLICK a safe point outside the dropdown to capture its close-menu coordinate."
        return f"LEFT-CLICK the {stage} option to capture its coordinates."

    def begin_calibration(self) -> None:
        if self.calibration_stage:
            return
        if not self._start_listener():
            return
        if self.menu_open and self.config_data:
            try:
                pyautogui.click(*self.config_data["exit_menu"])
            except Exception:
                pass
            self.menu_open = False
        self.speed_queue.clear()
        self.processing_queue = False
        self.calibration_data = {
            "version": 1, "menu": None, "speeds": {}, "exit_menu": None
        }
        self.calibration_stage = "menu"
        self._refresh_coordinates()
        self.status_var.set("CALIBRATION: LEFT-CLICK the playback menu button in Hudl.")
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(800, lambda: self.root.attributes("-topmost", False))

    def _accept_calibration_point(self, point: list[int]) -> None:
        stage = self.calibration_stage
        if not stage:
            return
        if stage == "menu":
            self.calibration_data["menu"] = point
            self.menu_open = True
            self._refresh_coordinates()
            self.status_var.set(f"Menu button captured at {tuple(point)}. Waiting for menu animation…")
            self.root.after(MENU_RENDER_DELAY_MS, lambda: self._set_calibration_stage(SPEEDS[0]))
        elif stage in SPEEDS:
            self.calibration_data["speeds"][stage] = point
            self._refresh_coordinates()
            next_index = SPEEDS.index(stage) + 1
            if next_index < len(SPEEDS):
                self.status_var.set(f"{stage} captured at {tuple(point)}. Reopening menu…")
                self.root.after(150, self._reopen_menu_for_calibration)
            else:
                self.status_var.set(f"{stage} captured at {tuple(point)}. Reopening menu for exit-point capture…")
                self.root.after(150, self._reopen_menu_for_exit_capture)
        elif stage == "exit_menu":
            self.calibration_data["exit_menu"] = point
            self.menu_open = False
            try:
                self.save_config()
            except Exception as exc:
                self._abort_calibration(f"Could not save calibration: {exc}")
                return
            self.calibration_stage = None
            self._refresh_coordinates()
            self._refresh_status()
            messagebox.showinfo(
                "Calibration saved", f"Coordinates saved to:\n{CONFIG_PATH}\n\n"
                "All saved coordinates are displayed in the main window.",
                parent=self.root
            )

    def _reopen_menu_for_calibration(self) -> None:
        if not self.calibration_stage or not self.calibration_data.get("menu"):
            return
        try:
            pyautogui.click(*self.calibration_data["menu"])
            self.menu_open = True
            next_index = sum(1 for speed in SPEEDS if speed in self.calibration_data["speeds"])
            self.root.after(
                MENU_RENDER_DELAY_MS,
                lambda: self._set_calibration_stage(SPEEDS[next_index])
            )
        except Exception as exc:
            self._abort_calibration(f"Could not reopen the playback menu: {exc}")

    def _reopen_menu_for_exit_capture(self) -> None:
        if not self.calibration_stage or not self.calibration_data.get("menu"):
            return
        try:
            pyautogui.click(*self.calibration_data["menu"])
            self.menu_open = True
            self.root.after(
                MENU_RENDER_DELAY_MS, lambda: self._set_calibration_stage("exit_menu")
            )
        except Exception as exc:
            self._abort_calibration(f"Could not reopen the playback menu: {exc}")

    def _set_calibration_stage(self, stage: str) -> None:
        self.calibration_stage = stage
        self._refresh_coordinates()
        self.status_var.set("CALIBRATION: " + self._stage_instructions(stage))

    def _abort_calibration(self, reason: str) -> None:
        self.calibration_stage = None
        self._refresh_coordinates()
        self.status_var.set("Calibration failed. Please try again.")
        messagebox.showerror("Calibration failed", reason, parent=self.root)

    def close(self) -> None:
        self.closed = True
        if self.idle_job:
            try:
                self.root.after_cancel(self.idle_job)
            except tk.TclError:
                pass
        self._stop_listener()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    pyautogui.PAUSE = 0.03
    pyautogui.FAILSAFE = True
    PlaySpeedApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
