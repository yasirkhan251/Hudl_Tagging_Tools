"""
============================================================
HUDL ATTACK LOCATION 2D - RANDOM ITERATION TAGGER
============================================================

WORKFLOW:

    TOP    -> BOTTOM -> E
    OR
    BOTTOM -> TOP -> E

Example:

    1. TOP    -> BOTTOM -> E
    2. BOTTOM -> TOP    -> E
    3. TOP    -> BOTTOM -> E
    4. TOP    -> BOTTOM -> E
    5. BOTTOM -> TOP    -> E

------------------------------------------------------------
CALIBRATION
------------------------------------------------------------

You do NOT need to enter screen coordinates.

1. The default Hudl focus area is loaded automatically.
2. Press START to use the default coordinates.
3. Click "CALIBRATE / CHANGE FOCUS AREA" if your screen/layout
   uses different coordinates.
4. Drag a rectangle around the entire Hudl Location area.
5. The center line is automatically placed at 50%.
6. Press ENTER to confirm.

The selected rectangle becomes the coordinate system.

The center line is always:

    center_y = crop_top + crop_height / 2

Therefore it remains exactly centered regardless of crop size.

------------------------------------------------------------
HOTKEYS
------------------------------------------------------------

F8     = Emergency stop
ESC    = Cancel calibration
ENTER  = Confirm calibration

------------------------------------------------------------
DEPENDENCIES
------------------------------------------------------------

pip install pyautogui keyboard

============================================================
"""

import random
import threading
import time
import tkinter as tk
from tkinter import messagebox

import pyautogui


# ============================================================
# GLOBAL SETTINGS
# ============================================================

# Minimum time between first and second click.
# Lower = faster.
DEFAULT_CLICK_DELAY = 0.035

# Time after pressing E before next iteration.
# Increase this if Hudl needs more time.
DEFAULT_SET_DELAY = 0.08

# Percentage of each half kept away from the outer edge.
#
# 0.10 = 10% margin
# 0.15 = 15% margin
#
# This prevents points from being generated directly
# against the border.
DEFAULT_EDGE_MARGIN = 0.12

# Minimum distance from the previous point in the SAME half.
DEFAULT_MIN_POINT_DISTANCE = 30

# Default Hudl focus area.
#
# This is the known-good screen area shown in the calibration
# screenshot. The calibration button can still be used at any
# time to replace these coordinates.
DEFAULT_FOCUS_AREA = {
    "left": 1709,
    "top": 372,
    "right": 1808,
    "bottom": 541,
    "middle": 456,
}

# Global emergency hotkey.
STOP_HOTKEY = "f8"


# ============================================================
# GLOBAL STATE
# ============================================================

# Calibration coordinates.
#
# Start with the default Hudl focus area. The user can override
# it at any time with the calibration tool.
crop = DEFAULT_FOCUS_AREA.copy()

# Automation state.
stop_event = threading.Event()

automation_running = False

# Last generated points.
last_top_point = None
last_bottom_point = None


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def is_calibrated():
    """
    Check whether the focus area has been calibrated.
    """

    required = [
        "left",
        "top",
        "right",
        "bottom",
        "middle",
    ]

    return all(
        crop[key] is not None
        for key in required
    )


def point_distance(point_a, point_b):
    """
    Calculate distance between two screen points.
    """

    if point_a is None or point_b is None:
        return float("inf")

    dx = point_a[0] - point_b[0]
    dy = point_a[1] - point_b[1]

    return (dx * dx + dy * dy) ** 0.5


def generate_random_point(
    half,
    edge_margin,
    minimum_distance,
):
    """
    Generate a random screen coordinate inside either:

        half = "top"
        half = "bottom"

    The point is generated directly in screen coordinates.
    """

    global last_top_point
    global last_bottom_point

    left = crop["left"]
    right = crop["right"]
    top = crop["top"]
    middle = crop["middle"]
    bottom = crop["bottom"]

    # --------------------------------------------------------
    # Select half
    # --------------------------------------------------------

    if half == "top":

        half_top = top
        half_bottom = middle

        previous_point = last_top_point

    else:

        half_top = middle
        half_bottom = bottom

        previous_point = last_bottom_point

    # --------------------------------------------------------
    # Calculate margins
    # --------------------------------------------------------

    width = right - left
    height = half_bottom - half_top

    x_margin = width * edge_margin
    y_margin = height * edge_margin

    min_x = int(left + x_margin)
    max_x = int(right - x_margin)

    min_y = int(half_top + y_margin)
    max_y = int(half_bottom - y_margin)

    # Safety check.
    if min_x >= max_x:
        min_x = left
        max_x = right

    if min_y >= max_y:
        min_y = half_top
        max_y = half_bottom

    # --------------------------------------------------------
    # Try many random points
    # --------------------------------------------------------

    for _ in range(1000):

        x = random.randint(
            min_x,
            max_x
        )

        y = random.randint(
            min_y,
            max_y
        )

        point = (x, y)

        if point_distance(
            point,
            previous_point
        ) >= minimum_distance:

            return point

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    return (
        random.randint(
            min_x,
            max_x
        ),
        random.randint(
            min_y,
            max_y
        ),
    )


def remember_point(
    half,
    point
):
    """
    Store the most recently generated point
    for the corresponding half.
    """

    global last_top_point
    global last_bottom_point

    if half == "top":
        last_top_point = point
    else:
        last_bottom_point = point


# ============================================================
# FOCUS AREA CALIBRATOR
# ============================================================

class FocusAreaCalibrator:

    def __init__(
        self,
        parent,
        on_confirm
    ):

        self.parent = parent
        self.on_confirm = on_confirm

        self.dragging = False

        self.start_x = 0
        self.start_y = 0

        self.end_x = 0
        self.end_y = 0

        self.rectangle_id = None
        self.center_line_id = None

        # ----------------------------------------------------
        # Full-screen transparent overlay
        # ----------------------------------------------------

        self.window = tk.Toplevel(
            parent
        )

        self.window.title(
            "Hudl Focus Area Calibration"
        )

        self.window.attributes(
            "-fullscreen",
            True
        )

        self.window.attributes(
            "-topmost",
            True
        )

        self.window.attributes(
            "-alpha",
            0.35
        )

        self.window.configure(
            bg="black"
        )

        self.window.config(
            cursor="crosshair"
        )

        # ----------------------------------------------------
        # Canvas
        # ----------------------------------------------------

        self.canvas = tk.Canvas(
            self.window,
            bg="black",
            highlightthickness=0
        )

        self.canvas.pack(
            fill="both",
            expand=True
        )

        # ----------------------------------------------------
        # Instructions
        # ----------------------------------------------------

        self.instruction_id = self.canvas.create_text(
            40,
            35,
            anchor="nw",
            fill="#00ff66",
            font=(
                "Segoe UI",
                17,
                "bold"
            ),
            text=(
                "HUDL FOCUS AREA CALIBRATION\n\n"
                "Drag a rectangle around the complete "
                "Location / Court area.\n\n"
                "The horizontal center line is calculated "
                "automatically.\n\n"
                "ENTER = Confirm\n"
                "ESC = Cancel"
            )
        )

        # ----------------------------------------------------
        # Mouse events
        # ----------------------------------------------------

        self.canvas.bind(
            "<ButtonPress-1>",
            self.mouse_down
        )

        self.canvas.bind(
            "<B1-Motion>",
            self.mouse_drag
        )

        self.canvas.bind(
            "<ButtonRelease-1>",
            self.mouse_up
        )

        # ----------------------------------------------------
        # Keyboard events
        # ----------------------------------------------------

        self.window.bind(
            "<Return>",
            self.confirm
        )

        self.window.bind(
            "<Escape>",
            self.cancel
        )

        self.window.focus_force()

    # ========================================================
    # MOUSE DOWN
    # ========================================================

    def mouse_down(
        self,
        event
    ):

        self.dragging = True

        self.start_x = event.x_root
        self.start_y = event.y_root

        self.end_x = self.start_x
        self.end_y = self.start_y

        # Remove old rectangle.
        if self.rectangle_id:
            self.canvas.delete(
                self.rectangle_id
            )

        if self.center_line_id:
            self.canvas.delete(
                self.center_line_id
            )

        # Create rectangle.
        self.rectangle_id = self.canvas.create_rectangle(
            self.start_x,
            self.start_y,
            self.end_x,
            self.end_y,
            outline="#00ff66",
            width=3
        )

    # ========================================================
    # MOUSE DRAG
    # ========================================================

    def mouse_drag(
        self,
        event
    ):

        if not self.dragging:
            return

        self.end_x = event.x_root
        self.end_y = event.y_root

        x1 = min(
            self.start_x,
            self.end_x
        )

        x2 = max(
            self.start_x,
            self.end_x
        )

        y1 = min(
            self.start_y,
            self.end_y
        )

        y2 = max(
            self.start_y,
            self.end_y
        )

        # ----------------------------------------------------
        # Update rectangle
        # ----------------------------------------------------

        if self.rectangle_id:

            self.canvas.coords(
                self.rectangle_id,
                x1,
                y1,
                x2,
                y2
            )

        # ----------------------------------------------------
        # AUTOMATIC CENTER LINE
        # ----------------------------------------------------

        center_y = y1 + (
            (y2 - y1) / 2
        )

        # Delete old center line.
        if self.center_line_id:

            self.canvas.delete(
                self.center_line_id
            )

        # Draw new center line.
        self.center_line_id = self.canvas.create_line(
            x1,
            center_y,
            x2,
            center_y,
            fill="#00ffff",
            width=3,
            dash=(
                8,
                5
            )
        )

        # ----------------------------------------------------
        # Display dimensions
        # ----------------------------------------------------

        width = x2 - x1
        height = y2 - y1

        self.canvas.delete(
            "dimension_text"
        )

        self.canvas.create_text(
            x1,
            y2 + 20,
            anchor="nw",
            fill="#ffffff",
            font=(
                "Segoe UI",
                12,
                "bold"
            ),
            tags="dimension_text",
            text=(
                f"Width: {width}px    "
                f"Height: {height}px    "
                f"Center Y: {int(center_y)}"
            )
        )

    # ========================================================
    # MOUSE UP
    # ========================================================

    def mouse_up(
        self,
        event
    ):

        if not self.dragging:
            return

        self.dragging = False

        self.end_x = event.x_root
        self.end_y = event.y_root

    # ========================================================
    # CONFIRM
    # ========================================================

    def confirm(
        self,
        event=None
    ):

        x1 = min(
            self.start_x,
            self.end_x
        )

        x2 = max(
            self.start_x,
            self.end_x
        )

        y1 = min(
            self.start_y,
            self.end_y
        )

        y2 = max(
            self.start_y,
            self.end_y
        )

        width = x2 - x1
        height = y2 - y1

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        if width < 50 or height < 100:

            messagebox.showwarning(
                "Invalid Focus Area",
                (
                    "The selected area is too small.\n\n"
                    "Please drag around the complete "
                    "Hudl Location / Court area."
                ),
                parent=self.window
            )

            return

        # ----------------------------------------------------
        # EXACT CENTER
        # ----------------------------------------------------

        center_y = y1 + (
            height / 2
        )

        # ----------------------------------------------------
        # Save calibration
        # ----------------------------------------------------

        calibrated_data = {
            "left": int(x1),
            "top": int(y1),
            "right": int(x2),
            "bottom": int(y2),
            "middle": int(center_y),
        }

        # ----------------------------------------------------
        # Close overlay
        # ----------------------------------------------------

        self.window.destroy()

        # ----------------------------------------------------
        # Send data to application
        # ----------------------------------------------------

        self.on_confirm(
            calibrated_data
        )

    # ========================================================
    # CANCEL
    # ========================================================

    def cancel(
        self,
        event=None
    ):

        self.window.destroy()


# ============================================================
# MAIN APPLICATION
# ============================================================

class AttackLocation2DApp:

    def __init__(
        self,
        root
    ):

        self.root = root

        self.root.title(
            "Hudl Attack Location 2D"
        )

        self.root.geometry(
            "560x650"
        )

        self.root.resizable(
            False,
            False
        )

        self.root.attributes(
            "-topmost",
            True
        )

        # ----------------------------------------------------
        # Build interface
        # ----------------------------------------------------

        self.create_interface()

        # ----------------------------------------------------
        # F8 fallback
        # ----------------------------------------------------

        self.root.bind(
            "<F8>",
            lambda event: self.stop()
        )

        self.root.bind(
            "<Escape>",
            lambda event: None
        )

        # ----------------------------------------------------
        # Try global keyboard hotkey
        # ----------------------------------------------------

        self.setup_global_hotkey()

    # ========================================================
    # INTERFACE
    # ========================================================

    def create_interface(self):

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        title = tk.Label(
            self.root,
            text="HUDL ATTACK LOCATION 2D",
            font=(
                "Segoe UI",
                19,
                "bold"
            )
        )

        title.pack(
            pady=(20, 3)
        )

        subtitle = tk.Label(
            self.root,
            text=(
                "Random opposite-half iteration tagger"
            ),
            font=(
                "Segoe UI",
                10
            )
        )

        subtitle.pack()

        # ----------------------------------------------------
        # Settings
        # ----------------------------------------------------

        settings = tk.LabelFrame(
            self.root,
            text="Automation Settings",
            font=(
                "Segoe UI",
                10,
                "bold"
            ),
            padx=15,
            pady=10
        )

        settings.pack(
            padx=25,
            pady=20,
            fill="x"
        )

        # ----------------------------------------------------
        # Iterations
        # ----------------------------------------------------

        tk.Label(
            settings,
            text="Iterations:"
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=8,
            pady=8
        )

        self.iterations_entry = tk.Entry(
            settings,
            width=14,
            justify="center",
            font=(
                "Consolas",
                12
            )
        )

        self.iterations_entry.insert(
            0,
            "5"
        )

        self.iterations_entry.grid(
            row=0,
            column=1,
            padx=8
        )

        # ----------------------------------------------------
        # Click delay
        # ----------------------------------------------------

        tk.Label(
            settings,
            text="Click delay:"
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=8,
            pady=8
        )

        self.click_delay_entry = tk.Entry(
            settings,
            width=14,
            justify="center",
            font=(
                "Consolas",
                12
            )
        )

        self.click_delay_entry.insert(
            0,
            str(DEFAULT_CLICK_DELAY)
        )

        self.click_delay_entry.grid(
            row=1,
            column=1,
            padx=8
        )

        tk.Label(
            settings,
            text="seconds"
        ).grid(
            row=1,
            column=2
        )

        # ----------------------------------------------------
        # Set delay
        # ----------------------------------------------------

        tk.Label(
            settings,
            text="Set delay:"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=8,
            pady=8
        )

        self.set_delay_entry = tk.Entry(
            settings,
            width=14,
            justify="center",
            font=(
                "Consolas",
                12
            )
        )

        self.set_delay_entry.insert(
            0,
            str(DEFAULT_SET_DELAY)
        )

        self.set_delay_entry.grid(
            row=2,
            column=1,
            padx=8
        )

        tk.Label(
            settings,
            text="seconds"
        ).grid(
            row=2,
            column=2
        )

        # ----------------------------------------------------
        # Edge margin
        # ----------------------------------------------------

        tk.Label(
            settings,
            text="Edge margin:"
        ).grid(
            row=3,
            column=0,
            sticky="w",
            padx=8,
            pady=8
        )

        self.margin_entry = tk.Entry(
            settings,
            width=14,
            justify="center",
            font=(
                "Consolas",
                12
            )
        )

        self.margin_entry.insert(
            0,
            str(DEFAULT_EDGE_MARGIN)
        )

        self.margin_entry.grid(
            row=3,
            column=1,
            padx=8
        )

        tk.Label(
            settings,
            text="0.12 = 12%"
        ).grid(
            row=3,
            column=2
        )

        # ----------------------------------------------------
        # Minimum point distance
        # ----------------------------------------------------

        tk.Label(
            settings,
            text="Min point distance:"
        ).grid(
            row=4,
            column=0,
            sticky="w",
            padx=8,
            pady=8
        )

        self.distance_entry = tk.Entry(
            settings,
            width=14,
            justify="center",
            font=(
                "Consolas",
                12
            )
        )

        self.distance_entry.insert(
            0,
            str(DEFAULT_MIN_POINT_DISTANCE)
        )

        self.distance_entry.grid(
            row=4,
            column=1,
            padx=8
        )

        tk.Label(
            settings,
            text="pixels"
        ).grid(
            row=4,
            column=2
        )

        # ----------------------------------------------------
        # Calibration status
        # ----------------------------------------------------

        self.calibration_label = tk.Label(
            self.root,
            text=(
                "FOCUS AREA: DEFAULT\n"
                f"X: {crop['left']} → {crop['right']}\n"
                f"Y: {crop['top']} → {crop['bottom']}\n"
                f"CENTER: Y = {crop['middle']}\n"
                f"SIZE: {crop['right'] - crop['left']} × "
                f"{crop['bottom'] - crop['top']}px"
            ),
            fg="#008000",
            font=(
                "Segoe UI",
                11,
                "bold"
            ),
            justify="center"
        )

        self.calibration_label.pack(
            pady=(5, 12)
        )

        # ----------------------------------------------------
        # Calibration button
        # ----------------------------------------------------

        self.calibrate_button = tk.Button(
            self.root,
            text="CALIBRATE / CHANGE FOCUS AREA",
            command=self.start_calibration,
            font=(
                "Segoe UI",
                11,
                "bold"
            ),
            width=34,
            height=2
        )

        self.calibrate_button.pack(
            pady=5
        )

        # ----------------------------------------------------
        # Start
        # ----------------------------------------------------

        self.start_button = tk.Button(
            self.root,
            text="2. START ITERATION",
            command=self.start,
            font=(
                "Segoe UI",
                12,
                "bold"
            ),
            width=34,
            height=2
        )

        self.start_button.pack(
            pady=5
        )

        # ----------------------------------------------------
        # Stop
        # ----------------------------------------------------

        self.stop_button = tk.Button(
            self.root,
            text="STOP",
            command=self.stop,
            font=(
                "Segoe UI",
                11,
                "bold"
            ),
            width=34,
            height=2,
            state=tk.DISABLED
        )

        self.stop_button.pack(
            pady=5
        )

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        self.progress_label = tk.Label(
            self.root,
            text="SET: 0 / 0",
            font=(
                "Consolas",
                15,
                "bold"
            )
        )

        self.progress_label.pack(
            pady=(18, 5)
        )

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        self.status_label = tk.Label(
            self.root,
            text="Ready",
            font=(
                "Segoe UI",
                10
            ),
            justify="center",
            wraplength=500
        )

        self.status_label.pack(
            pady=5
        )

        # ----------------------------------------------------
        # Instructions
        # ----------------------------------------------------

        info = tk.Label(
            self.root,
            text=(
                "\nEvery set:\n"
                "TOP → BOTTOM → E\n"
                "OR\n"
                "BOTTOM → TOP → E\n\n"
                "Coordinates are randomized automatically.\n"
                "F8 = Emergency Stop"
            ),
            font=(
                "Segoe UI",
                10
            ),
            justify="center"
        )

        info.pack(
            pady=12
        )

    # ========================================================
    # GLOBAL HOTKEY
    # ========================================================

    def setup_global_hotkey(self):

        try:

            import keyboard

            keyboard.add_hotkey(
                STOP_HOTKEY,
                self.global_stop
            )

        except Exception:

            pass

    # --------------------------------------------------------

    def global_stop(self):

        self.root.after(
            0,
            self.stop
        )

    # ========================================================
    # CALIBRATION
    # ========================================================

    def start_calibration(self):

        self.status_label.config(
            text=(
                "Default focus area loaded.\n"
                "Click CALIBRATE / CHANGE FOCUS AREA to select a "
                "different area."
            )
        )

        FocusAreaCalibrator(
            self.root,
            self.calibration_complete
        )

    # ========================================================
    # CALIBRATION COMPLETE
    # ========================================================

    def calibration_complete(
        self,
        data
    ):

        global crop

        crop = data

        width = (
            crop["right"] -
            crop["left"]
        )

        height = (
            crop["bottom"] -
            crop["top"]
        )

        self.calibration_label.config(
            text=(
                "FOCUS AREA: CALIBRATED\n"
                f"X: {crop['left']} → {crop['right']}\n"
                f"Y: {crop['top']} → {crop['bottom']}\n"
                f"CENTER: Y = {crop['middle']}\n"
                f"SIZE: {width} × {height}px"
            ),
            fg="#008000"
        )

        self.status_label.config(
            text=(
                "Calibration complete.\n"
                "The center line is exactly 50% of "
                "the selected focus area."
            )
        )

    # ========================================================
    # READ SETTINGS
    # ========================================================

    def read_settings(self):

        try:

            iterations = int(
                self.iterations_entry.get()
            )

            click_delay = float(
                self.click_delay_entry.get()
            )

            set_delay = float(
                self.set_delay_entry.get()
            )

            edge_margin = float(
                self.margin_entry.get()
            )

            minimum_distance = float(
                self.distance_entry.get()
            )

        except ValueError:

            messagebox.showerror(
                "Invalid Settings",
                "Please enter valid numbers."
            )

            return None

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        if iterations <= 0:

            messagebox.showerror(
                "Invalid Iterations",
                "Iterations must be greater than 0."
            )

            return None

        if click_delay < 0:

            messagebox.showerror(
                "Invalid Click Delay",
                "Click delay cannot be negative."
            )

            return None

        if set_delay < 0:

            messagebox.showerror(
                "Invalid Set Delay",
                "Set delay cannot be negative."
            )

            return None

        if not 0 <= edge_margin < 0.5:

            messagebox.showerror(
                "Invalid Edge Margin",
                "Edge margin must be between 0 and 0.49."
            )

            return None

        if minimum_distance < 0:

            messagebox.showerror(
                "Invalid Distance",
                "Minimum distance cannot be negative."
            )

            return None

        return (
            iterations,
            click_delay,
            set_delay,
            edge_margin,
            minimum_distance,
        )

    # ========================================================
    # START
    # ========================================================

    def start(self):

        global automation_running
        global last_top_point
        global last_bottom_point

        # ----------------------------------------------------
        # Check calibration
        # ----------------------------------------------------

        if not is_calibrated():

            messagebox.showwarning(
                "Focus Area Required",
                (
                    "Please calibrate the Hudl "
                    "focus area first."
                )
            )

            return

        # ----------------------------------------------------
        # Read settings
        # ----------------------------------------------------

        settings = self.read_settings()

        if settings is None:
            return

        (
            iterations,
            click_delay,
            set_delay,
            edge_margin,
            minimum_distance,
        ) = settings

        # ----------------------------------------------------
        # Reset
        # ----------------------------------------------------

        stop_event.clear()

        last_top_point = None
        last_bottom_point = None

        automation_running = True

        # ----------------------------------------------------
        # UI
        # ----------------------------------------------------

        self.start_button.config(
            state=tk.DISABLED
        )

        self.calibrate_button.config(
            state=tk.DISABLED
        )

        self.stop_button.config(
            state=tk.NORMAL
        )

        self.progress_label.config(
            text=f"SET: 0 / {iterations}"
        )

        self.status_label.config(
            text="Starting..."
        )

        # ----------------------------------------------------
        # Run in background
        # ----------------------------------------------------

        worker = threading.Thread(
            target=self.run_iterations,
            args=(
                iterations,
                click_delay,
                set_delay,
                edge_margin,
                minimum_distance,
            ),
            daemon=True
        )

        worker.start()

    # ========================================================
    # ITERATION ENGINE
    # ========================================================

    def run_iterations(
        self,
        iterations,
        click_delay,
        set_delay,
        edge_margin,
        minimum_distance,
    ):

        global automation_running

        # Disable PyAutoGUI's built-in pause.
        pyautogui.PAUSE = 0

        try:

            for set_number in range(
                1,
                iterations + 1
            ):

                # ------------------------------------------------
                # Stop check
                # ------------------------------------------------

                if stop_event.is_set():
                    break

                # ------------------------------------------------
                # Random direction
                # ------------------------------------------------

                if random.choice(
                    [True, False]
                ):

                    first_half = "top"
                    second_half = "bottom"

                else:

                    first_half = "bottom"
                    second_half = "top"

                # ------------------------------------------------
                # Generate first coordinate
                # ------------------------------------------------

                first_point = generate_random_point(
                    first_half,
                    edge_margin,
                    minimum_distance
                )

                # ------------------------------------------------
                # Generate second coordinate
                # ------------------------------------------------

                second_point = generate_random_point(
                    second_half,
                    edge_margin,
                    minimum_distance
                )

                # ------------------------------------------------
                # Remember points
                # ------------------------------------------------

                remember_point(
                    first_half,
                    first_point
                )

                remember_point(
                    second_half,
                    second_point
                )

                # ------------------------------------------------
                # UI status
                # ------------------------------------------------

                direction = (
                    f"{first_half.upper()} "
                    f"→ "
                    f"{second_half.upper()}"
                )

                self.root.after(
                    0,
                    self.update_progress,
                    set_number,
                    iterations,
                    direction,
                    first_point,
                    second_point
                )

                # ------------------------------------------------
                # CLICK #1
                # ------------------------------------------------

                if stop_event.is_set():
                    break

                pyautogui.click(
                    first_point[0],
                    first_point[1]
                )

                time.sleep(
                    click_delay
                )

                # ------------------------------------------------
                # CLICK #2
                # ------------------------------------------------

                if stop_event.is_set():
                    break

                pyautogui.click(
                    second_point[0],
                    second_point[1]
                )

                time.sleep(
                    click_delay
                )

                # ------------------------------------------------
                # PRESS E
                # ------------------------------------------------

                if stop_event.is_set():
                    break

                pyautogui.press(
                    "e"
                )

                # ------------------------------------------------
                # Wait before next set
                # ------------------------------------------------

                if stop_event.wait(
                    set_delay
                ):
                    break

        except pyautogui.FailSafeException:

            self.root.after(
                0,
                self.show_failsafe
            )

        except Exception as error:

            self.root.after(
                0,
                self.show_error,
                str(error)
            )

        finally:

            automation_running = False

            self.root.after(
                0,
                self.automation_finished
            )

    # ========================================================
    # PROGRESS UPDATE
    # ========================================================

    def update_progress(
        self,
        set_number,
        total,
        direction,
        first_point,
        second_point
    ):

        self.progress_label.config(
            text=(
                f"SET: {set_number} / {total}"
            )
        )

        self.status_label.config(
            text=(
                f"Direction: {direction}\n\n"
                f"Point 1: {first_point}\n"
                f"Point 2: {second_point}\n\n"
                f"Click 1 → Click 2 → E"
            )
        )

    # ========================================================
    # STOP
    # ========================================================

    def stop(self):

        global automation_running

        if not automation_running:
            return

        stop_event.set()

        self.status_label.config(
            text=(
                "STOP REQUESTED\n"
                "Waiting for current action to finish..."
            )
        )

        self.stop_button.config(
            state=tk.DISABLED
        )

    # ========================================================
    # FINISHED
    # ========================================================

    def automation_finished(self):

        global automation_running

        automation_running = False

        self.start_button.config(
            state=tk.NORMAL
        )

        self.calibrate_button.config(
            state=tk.NORMAL
        )

        self.stop_button.config(
            state=tk.DISABLED
        )

        if stop_event.is_set():

            self.status_label.config(
                text="Automation stopped."
            )

        else:

            self.status_label.config(
                text="All iterations completed."
            )

    # ========================================================
    # FAILSAFE
    # ========================================================

    def show_failsafe(self):

        messagebox.showwarning(
            "PyAutoGUI Failsafe",
            (
                "Automation stopped because the "
                "mouse reached the screen corner."
            )
        )

    # ========================================================
    # ERROR
    # ========================================================

    def show_error(
        self,
        error
    ):

        messagebox.showerror(
            "Automation Error",
            error
        )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # PyAutoGUI safety
    # --------------------------------------------------------

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0

    # --------------------------------------------------------
    # Tkinter
    # --------------------------------------------------------

    root = tk.Tk()

    app = AttackLocation2DApp(
        root
    )

    # --------------------------------------------------------
    # Closing application
    # --------------------------------------------------------

    def close_application():

        stop_event.set()

        try:

            import keyboard

            keyboard.unhook_all_hotkeys()

        except Exception:

            pass

        root.destroy()

    root.protocol(
        "WM_DELETE_WINDOW",
        close_application
    )

    root.mainloop()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()