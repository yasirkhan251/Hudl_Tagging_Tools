from __future__ import annotations
import os, sys, shutil, zipfile, tempfile, urllib.request, subprocess, pathlib, traceback

OWNER = "yasirkhan251"
REPO = "Hudl_Tagging_Tools"
BRANCH = "main"
APP_NAME = "Hudl Tagging Tools"
BASE = pathlib.Path(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home()))) / APP_NAME
PYTHON_VERSION = "3.11.9"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-amd64.exe"

def log(message):
    print(f"\n[Hudl Setup] {message}", flush=True)

def run(args, **kwargs):
    print(">", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)

def download(url, target):
    target = pathlib.Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    log(f"Downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "HudlTaggingToolsInstaller/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response, open(target, "wb") as out:
        shutil.copyfileobj(response, out)
    return target

def find_python():
    candidates = [
        pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python/Python311/python.exe",
        pathlib.Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Python311/python.exe",
        pathlib.Path("C:/Python311/python.exe"),
    ]
    for exe in candidates:
        if exe.is_file():
            return exe
    for name in ("py", "python", "python3"):
        found = shutil.which(name)
        if found:
            try:
                p = subprocess.run([found, "--version"], capture_output=True, text=True)
                if p.returncode == 0 and "3.11" in (p.stdout + p.stderr):
                    return pathlib.Path(found)
            except Exception:
                pass
    return None

def ensure_python():
    python = find_python()
    if python:
        log(f"Using Python: {python}")
        return python
    log("Python 3.11 was not found. Downloading and installing it for the current user.")
    installer = pathlib.Path(tempfile.gettempdir()) / "hudl-python-3.11.9.exe"
    download(PYTHON_URL, installer)
    target = pathlib.Path(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home()))) / "Programs/Python/Python311"
    run([installer, "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_launcher=0",
         "Include_test=0", f"TargetDir={target}"])
    python = target / "python.exe"
    if not python.is_file():
        raise RuntimeError("Python installer completed but python.exe was not found.")
    return python

def make_shortcut(target, shortcut):
    ps = (
        "$s=(New-Object -COM WScript.Shell).CreateShortcut('" + str(shortcut).replace("'", "''") + "');"
        "$s.TargetPath='" + str(target).replace("'", "''") + "';"
        "$s.WorkingDirectory='" + str(target.parent).replace("'", "''") + "';"
        "$s.Description='Launch Hudl Tagging Tools';$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], check=False)

def main():
    log("This installer downloads the latest public GitHub source and installs dependencies.")
    BASE.mkdir(parents=True, exist_ok=True)
    python = ensure_python()
    with tempfile.TemporaryDirectory(prefix="hudl-setup-") as tmp:
        archive = pathlib.Path(tmp) / "source.zip"
        download(f"https://codeload.github.com/{OWNER}/{REPO}/zip/refs/heads/{BRANCH}", archive)
        extracted = pathlib.Path(tmp) / "source"
        extracted.mkdir()
        log("Extracting application files...")
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extracted)
        roots = [p for p in extracted.iterdir() if p.is_dir()]
        source = next((p for p in roots if (p / "main.py").is_file()), None)
        if source is None:
            raise RuntimeError("Downloaded repository does not contain main.py at its root.")
        if BASE.exists():
            for child in BASE.iterdir():
                if child.name == "venv":
                    shutil.rmtree(child, ignore_errors=True)
                elif child.name != "venv":
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
        shutil.copytree(source, BASE, dirs_exist_ok=True)
    venv_python = BASE / "venv" / "Scripts" / "python.exe"
    log("Creating an isolated Python environment...")
    run([python, "-m", "venv", BASE / "venv"])
    run([venv_python, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    log("Installing PyTorch with NVIDIA CUDA support (CPU fallback remains available)...")
    run([venv_python, "-m", "pip", "install", "torch", "torchvision", "--index-url",
         "https://download.pytorch.org/whl/cu126"])
    packages = [
        "ultralytics", "opencv-python", "easyocr", "vosk", "mss", "keyboard",
        "pyautogui", "pillow", "numpy", "scipy", "matplotlib", "pandas",
        "requests", "pywin32"
    ]
    log("Installing application dependencies. This can take several minutes.")
    run([venv_python, "-m", "pip", "install", *packages])
    desktop = pathlib.Path(os.environ.get("USERPROFILE", str(pathlib.Path.home()))) / "Desktop"
    start_menu = pathlib.Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"
    for folder in (desktop, start_menu):
        if folder.exists():
            make_shortcut(BASE / "Launch Hudl Tagging Tools.bat", folder / "Hudl Tagging Tools.lnk")
    bat = BASE / "Launch Hudl Tagging Tools.bat"
    bat.write_text('@echo off\r\ncd /d "%~dp0"\r\n".\\venv\\Scripts\\python.exe" main.py\r\n', encoding="utf-8")
    log("Installation completed. Starting Hudl Tagging Tools...")
    subprocess.Popen([str(bat)], cwd=str(BASE), shell=True)
    input("\nSetup finished. Press Enter to close this installer...")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("\nInstallation failed. Please take a screenshot of this error. Press Enter to close...")
        sys.exit(1)
