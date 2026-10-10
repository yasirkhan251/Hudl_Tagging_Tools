# Hudl PlaySpeed Prototype

Standalone playback-speed controller using global **O** and **P** shortcuts. Existing tagging apps are not modified.

## Behaviour

- Speed is assumed to start at **1x** whenever the prototype launches.
- **O** decreases one step: 2.5x → 2x → 1.5x → 1x → 0.5x.
- **P** increases one step: 0.5x → 1x → 1.5x → 2x → 2.5x.
- When the menu is closed, the first O/P press clicks the menu button and waits **350 ms** for Hudl's dropdown animation before selecting the new speed.
- The menu closes after 3 seconds without another O/P press.
- The main window displays every saved/captured coordinate.

## Install and run (Windows)

    py -m pip install -r requirements.txt
    py playspeed.py

## Mouse-click calibration (no F8)

1. Click **Calibrate / change coordinates** in the prototype.
2. **Left-click** the Hudl playback menu button. Its coordinates are captured and the menu opens.
3. Wait for the menu animation, then **left-click** 0.5x, 1x, 1.5x, 2x, and 2.5x in sequence. Each click captures that point and may also select the speed; the prototype reopens the menu and waits 350 ms before asking for the next point.
4. After capturing 2.5x, the prototype reopens the menu. **Left-click a safe point outside the dropdown** to capture the exit-menu coordinate.
5. The coordinates are saved to `coordinates.json`, displayed in the app, and reused next time. Recalibrate if browser zoom, display scaling, window position, or Hudl layout changes.

After calibration, click **Start global shortcuts**. Keep Hudl/Chrome open and use **O/P**. Click **Stop global shortcuts** before typing O/P in other applications.

## Safety and limitations

- PyAutoGUI fail-safe is enabled; moving the mouse to the upper-left corner can abort an automation action.
- Global keyboard/mouse hooks may require OS permissions.
- Displayed speed tracks the requested click sequence; the prototype cannot independently verify Hudl's actual playback speed.
- Set Hudl to 1x before use if it remembers a different speed from a previous session.
