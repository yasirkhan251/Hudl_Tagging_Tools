# Hudl PlaySpeed Prototype

A standalone prototype for changing Hudl playback speed using global **O** and **P** shortcuts. It does not edit or import the existing tagging programs.

## Behaviour

- The speed is assumed to start at **1x** each time the prototype launches.
- Press **O** to decrease one step: `2.5x → 2x → 1.5x → 1x → 0.5x`.
- Press **P** to increase one step: `0.5x → 1x → 1.5x → 2x → 2.5x`.
- The first O/P press clicks the saved menu-button coordinate, waits briefly for the menu to open, then clicks the new speed option.
- The menu remains open for quick repeated changes. If no O/P press occurs for 3 seconds, the saved exit-menu coordinate is clicked.
- The speed state is held in memory during the session. It resets to 1x when the program restarts, as requested.
- At the minimum or maximum, another key press stays at that boundary.

## Install and run (Windows)

Open PowerShell in this folder:

```powershell
py -m pip install -r requirements.txt
py playspeed.py
```

Click **Calibrate / change coordinates** and follow the status instructions. For each target, place the mouse over the indicated Hudl control and press **F8**:

1. Playback menu button (the prototype clicks it to open the menu)
2. 0.5x
3. 1x
4. 1.5x
5. 2x
6. 2.5x
7. A safe point outside the menu to close it

The coordinates are saved to `coordinates.json` in this folder. The file is local and ignored by Git, so it is reused on this computer without recalibration. Recalibrate if the browser zoom, monitor scaling, window position, or Hudl layout changes.

Once calibrated, click **Start global shortcuts**. Keep Hudl/Chrome open and use **O/P**. Click **Stop global shortcuts** before typing O/P in other applications.

## Safety and limitations

- PyAutoGUI's fail-safe remains enabled: moving the mouse to the upper-left corner can abort an automation action.
- Global keyboard hooks can behave differently across operating systems and may require extra permissions. This prototype should be tested on the target setup before integrating it into either tagging app.
- The UI's displayed speed tracks the requested click sequence; it cannot independently verify what Hudl actually applied.
- The prototype assumes the video begins at 1x each time it starts. If Hudl remembers a different speed between sessions, set Hudl back to 1x before using the prototype.
