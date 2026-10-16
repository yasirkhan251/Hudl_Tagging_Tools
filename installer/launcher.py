from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

OWNER = "yasirkhan251"
REPO = "Hudl_Tagging_Tools"
RELEASE_API = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
ASSET_NAME = "HudlTaggingToolsSetup.exe"
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DASHBOARD = APP_DIR / "HudlTaggingTools.exe"
VERSION_FILE = APP_DIR / "version.txt"


def version_tuple(value: str) -> tuple[int, ...]:
    value = value.strip().lstrip("vV")
    parts = []
    for part in value.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts or [0])


def installed_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def get_latest_release() -> tuple[str, str] | None:
    request = urllib.request.Request(
        RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "HudlTaggingTools-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        release = json.loads(response.read().decode("utf-8"))
    if release.get("draft") or release.get("prerelease"):
        return None
    tag = str(release.get("tag_name", "")).strip()
    asset = next(
        (item for item in release.get("assets", []) if item.get("name") == ASSET_NAME),
        None,
    )
    if not tag or not asset or not asset.get("browser_download_url"):
        return None
    return tag.lstrip("vV"), asset["browser_download_url"]


def download_and_run_installer(url: str) -> None:
    target_dir = Path(tempfile.gettempdir()) / "HudlTaggingToolsUpdate"
    target_dir.mkdir(parents=True, exist_ok=True)
    installer = target_dir / ASSET_NAME
    request = urllib.request.Request(url, headers={"User-Agent": "HudlTaggingTools-Updater"})
    with urllib.request.urlopen(request, timeout=30) as response, installer.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
    if installer.stat().st_size < 1_000_000:
        raise RuntimeError("The downloaded installer is unexpectedly small; update cancelled.")
    subprocess.Popen([str(installer)], cwd=str(target_dir))
    # Exit promptly so the installer can replace files from the old installation.
    root.after(150, root.destroy)


def launch_app() -> None:
    if not DASHBOARD.exists():
        messagebox.showerror(
            "Hudl Tagging Tools",
            "The dashboard executable was not found. Please reinstall Hudl Tagging Tools.",
            parent=root,
        )
        return
    try:
        subprocess.Popen([str(DASHBOARD)], cwd=str(APP_DIR))
        root.destroy()
    except OSError as exc:
        messagebox.showerror("Unable to launch", str(exc), parent=root)


def check_for_updates(auto_launch: bool = False) -> None:
    status.set("Checking GitHub for the latest release…")
    check_button.configure(state="disabled")
    launch_button.configure(state="disabled")

    def worker() -> None:
        try:
            latest = get_latest_release()
            root.after(0, lambda: finish_check(latest, None, auto_launch))
        except Exception as exc:
            root.after(0, lambda: finish_check(None, str(exc), auto_launch))

    threading.Thread(target=worker, daemon=True).start()


def finish_check(latest: tuple[str, str] | None, error: str | None, auto_launch: bool) -> None:
    check_button.configure(state="normal")
    launch_button.configure(state="normal")
    current = installed_version()

    if error:
        status.set("Could not check for updates. You can still use the installed version.")
        if auto_launch:
            launch_app()
        else:
            messagebox.showwarning(
                "Update check unavailable",
                "Couldn't reach GitHub. Check your internet connection and try again.\n\n"
                "Your installed version is unchanged.",
                parent=root,
            )
        return

    if latest is None:
        status.set("No published release asset was found. You can still use the installed version.")
        if auto_launch:
            launch_app()
        else:
            messagebox.showinfo(
                "Updates",
                "No published installer was found for the latest release.",
                parent=root,
            )
        return

    latest_version, url = latest
    if version_tuple(latest_version) <= version_tuple(current):
        status.set(f"You’re up to date — version {current}.")
        if auto_launch:
            launch_app()
        else:
            messagebox.showinfo(
                "You're up to date",
                f"Hudl Tagging Tools {current} is the latest published version.",
                parent=root,
            )
        return

    status.set(f"Update available: {current} → {latest_version}")
    if messagebox.askyesno(
        "Update available",
        f"Hudl Tagging Tools {latest_version} is available.\n"
        f"Installed version: {current}\n\n"
        "Download and run the Windows installer now?",
        parent=root,
    ):
        status.set("Downloading the installer… Please wait.")
        check_button.configure(state="disabled")
        launch_button.configure(state="disabled")

        def updater() -> None:
            try:
                download_and_run_installer(url)
            except Exception as exc:
                root.after(0, lambda: update_failed(str(exc)))

        threading.Thread(target=updater, daemon=True).start()
    elif auto_launch:
        launch_app()


def update_failed(error: str) -> None:
    check_button.configure(state="normal")
    launch_button.configure(state="normal")
    status.set("Update failed. Your installed version is unchanged.")
    messagebox.showerror(
        "Update failed",
        f"Could not download or start the update.\n\n{error}\n\n"
        "You can launch your current version or try again later.",
        parent=root,
    )


root = tk.Tk()
root.title("Hudl Tagging Tools Launcher")
root.geometry("470x250")
root.resizable(False, False)
root.configure(padx=22, pady=18)

ttk.Label(root, text="Hudl Tagging Tools", font=("Segoe UI", 17, "bold")).pack(anchor="w")
ttk.Label(root, text=f"Installed version: {installed_version()}", font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 12))
status = tk.StringVar(value="Checking for updates…")
ttk.Label(root, textvariable=status, wraplength=420).pack(anchor="w", pady=(0, 18))

buttons = ttk.Frame(root)
buttons.pack(fill="x", side="bottom")
launch_button = ttk.Button(buttons, text="Launch application", command=launch_app)
launch_button.pack(side="left")
check_button = ttk.Button(buttons, text="Check for updates", command=lambda: check_for_updates(False))
check_button.pack(side="left", padx=8)
ttk.Button(buttons, text="Exit", command=root.destroy).pack(side="right")

root.after(300, lambda: check_for_updates(True))
root.mainloop()
