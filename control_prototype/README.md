# Hudl PlaySpeed

Everything is implemented in one file: `main.py`. It uses the same fullscreen, semi-transparent (30% opacity) calibration overlay style as `Jersey_Number_Tag.py`.

## Run

    py -m pip install -r requirements.txt
    py main.py

## Calibration

1. Click **Set Targets / Recalibrate**.
2. A fullscreen semi-transparent black overlay appears, matching the jersey-number tagger's calibration style.
3. Click the Hudl playback menu button.
4. Click each speed option in order: 0.5x, 1x, 1.5x, 2x, 2.5x.
5. Click a safe point outside the dropdown to capture the close-menu position.
6. All seven coordinates are saved to `coordinates.json` and shown in the main window. Press Esc to cancel calibration.

The overlay captures screen coordinates, then the app performs the actual Hudl clicks programmatically and reopens the menu between speed-option captures. The coordinates are local to your display setup and are not committed.

## Controls

- **O**: decrease speed by one step.
- **P**: increase speed by one step.
- First speed-change press opens the menu and waits **350 ms** before selecting.
- Menu closes after **3 seconds** without further O/P input.
- The current speed is assumed to be **1x** each time the program starts. If Hudl retained another speed, set it to 1x first.

The existing tagging scripts are not modified by this prototype.
