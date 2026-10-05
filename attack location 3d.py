import cv2
import numpy as np
import mss
import tkinter as tk

# ==========================================
# 1. ROI CALIBRATION (SCREEN CAPTURE AREA)
# ==========================================
class ROICalibrator:
    def __init__(self):
        self.roi = None
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True, "-alpha", 0.3, "-topmost", True)
        self.root.config(cursor="crosshair")
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(50, 50, anchor="nw", fill="#00ff66", font=("Segoe UI", 16, "bold"), 
                                text="Drag over the video feed to set the tracking area. (Esc to cancel)")
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.start_x = self.start_y = 0
        self.rect_id = None
        self.root.mainloop()

    def on_press(self, event):
        self.start_x, self.start_y = event.x_root, event.y_root
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="#00ff66", width=2)

    def on_drag(self, event):
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x_root, event.y_root)

    def on_release(self, event):
        x1, x2 = sorted((self.start_x, event.x_root))
        y1, y2 = sorted((self.start_y, event.y_root))
        if x2 - x1 > 50 and y2 - y1 > 50:
            self.roi = {"top": y1, "left": x1, "width": x2 - x1, "height": y2 - y1}
        self.root.destroy()

# ==========================================
# 2. DUAL-MODE COURT GEOMETRY SETUP
# ==========================================
court_points = []
calibration_mode = 0  
point_names = []
setup_frame = None
clean_setup_frame = None

def define_court_lines(event, x, y, flags, param):
    global court_points
    if event == cv2.EVENT_LBUTTONDOWN and len(court_points) < 6:
        court_points.append((x, y))
        redraw_setup()
    elif event == cv2.EVENT_RBUTTONDOWN and len(court_points) > 0:
        court_points.pop()
        redraw_setup()

def redraw_setup():
    global setup_frame, clean_setup_frame, calibration_mode, court_points
    setup_frame = clean_setup_frame.copy()
    for i, pt in enumerate(court_points):
        cv2.circle(setup_frame, pt, 5, (255, 255, 255), -1)
        
    if calibration_mode == 1 and len(court_points) >= 4:
        cv2.line(setup_frame, court_points[0], court_points[1], (0, 255, 255), 2)
        cv2.line(setup_frame, court_points[1], court_points[2], (0, 255, 255), 2)
        cv2.line(setup_frame, court_points[2], court_points[3], (0, 255, 255), 2)
        cv2.line(setup_frame, court_points[3], court_points[0], (0, 255, 255), 2)
    elif calibration_mode == 2 and len(court_points) >= 4:
        cv2.line(setup_frame, court_points[0], court_points[1], (0, 255, 255), 2)
        cv2.line(setup_frame, court_points[1], court_points[2], (0, 255, 255), 2)
        cv2.line(setup_frame, court_points[2], court_points[3], (0, 255, 255), 2)
        cv2.line(setup_frame, court_points[3], court_points[0], (0, 255, 255), 2)
        mid_top = (int((court_points[0][0] + court_points[1][0]) / 2), int((court_points[0][1] + court_points[1][1]) / 2))
        mid_bottom = (int((court_points[2][0] + court_points[3][0]) / 2), int((court_points[2][1] + court_points[3][1]) / 2))
        cv2.line(setup_frame, mid_top, mid_bottom, (255, 255, 0), 2, cv2.LINE_AA)

    if len(court_points) == 6:
        cv2.line(setup_frame, court_points[4], court_points[5], (0, 0, 255), 3) 
        cv2.putText(setup_frame, "Geometry Locked! Press ANY KEY to start.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    elif len(court_points) < 6:
        cv2.putText(setup_frame, f"Next: {point_names[len(court_points)]}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.imshow("Setup Dimensions", setup_frame)


# ==========================================
# 3. MAIN CLICK-TO-TAG SCRIPT
# ==========================================
manual_start = None
manual_end = None
click_state = 0 # 0 = waiting for hit, 1 = waiting for landing

def video_mouse_callback(event, x, y, flags, param):
    global manual_start, manual_end, click_state
    if event == cv2.EVENT_LBUTTONDOWN:
        transformed_pt = cv2.perspectiveTransform(np.array([[[x, y]]], dtype=np.float32), H_matrix)
        radar_pt = (int(transformed_pt[0][0][0]), int(transformed_pt[0][0][1]))
        
        if click_state == 0:
            manual_start = (x, y)
            global radar_start
            radar_start = radar_pt
            print(f"[Hit Captured] Video: {manual_start} -> Radar 2D: {radar_start}")
            click_state = 1
        elif click_state == 1:
            manual_end = (x, y)
            global radar_end
            radar_end = radar_pt
            print(f"[Landing Captured] Video: {manual_end} -> Radar 2D: {radar_end}")
            click_state = 0


if __name__ == "__main__":
    calibrator = ROICalibrator()
    if not calibrator.roi:
        exit()

    with mss.MSS() as sct:
        clean_setup_frame = np.array(sct.grab(calibrator.roi))
        clean_setup_frame = cv2.cvtColor(clean_setup_frame, cv2.COLOR_BGRA2BGR)
        setup_frame = clean_setup_frame.copy()

    cv2.putText(setup_frame, "Press '1' for Mode 1: Baseline Box", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(setup_frame, "Press '2' for Mode 2: Attack Line Box", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.imshow("Setup Dimensions", setup_frame)

    while True:
        key = cv2.waitKey(0) & 0xFF
        if key == ord('1'):
            calibration_mode = 1
            point_names = ["Far Line Left", "Far Line Right", "Middle Line Right", "Middle Line Left", "Net Top Left", "Net Top Right"]
            radar_w, radar_h = 900, 450 
            break
        elif key == ord('2'):
            calibration_mode = 2
            point_names = ["Left Attack Line Top", "Right Attack Line Top", "Right Attack Line Bottom", "Left Attack Line Bottom", "Net Top Left", "Net Top Right"]
            radar_w, radar_h = 900, 600 
            break

    redraw_setup()
    cv2.setMouseCallback("Setup Dimensions", define_court_lines)
    cv2.waitKey(0)
    cv2.destroyWindow("Setup Dimensions")

    # Generate Homography Matrix
    src_pts = np.array(court_points[:4], dtype=np.float32)
    dst_pts = np.array([[0, 0], [radar_w, 0], [radar_w, radar_h], [0, radar_h]], dtype=np.float32)
    H_matrix, _ = cv2.findHomography(src_pts, dst_pts)

    radar_start = None
    radar_end = None

    print("\n--- Click-to-Tag Mode Active ---")
    print("1. Left-click video where the hit happens (START).")
    print("2. Left-click video where the ball lands (END).")
    print("Press 'r' to clear, 'q' to quit.")

    cv2.namedWindow("Click-to-Tag Assistant")
    cv2.setMouseCallback("Click-to-Tag Assistant", video_mouse_callback)

    with mss.MSS() as sct:
        while True:
            frame = np.array(sct.grab(calibrator.roi))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            # Radar Canvas
            radar_img = np.zeros((radar_h, radar_w, 3), dtype=np.uint8)
            cv2.line(radar_img, (int(radar_w/2), 0), (int(radar_w/2), radar_h), (255,255,255), 2)

            # Draw geometry
            cv2.line(frame, court_points[0], court_points[1], (0, 255, 255), 2)
            cv2.line(frame, court_points[1], court_points[2], (0, 255, 255), 2)
            cv2.line(frame, court_points[2], court_points[3], (0, 255, 255), 2)
            cv2.line(frame, court_points[3], court_points[0], (0, 255, 255), 2)
            cv2.line(frame, court_points[4], court_points[5], (0, 0, 255), 3)

            # Draw manual points
            if manual_start:
                cv2.circle(frame, manual_start, 10, (0, 255, 0), -1)
                cv2.putText(frame, "START", (manual_start[0]+10, manual_start[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                if radar_start: cv2.circle(radar_img, radar_start, 8, (0, 255, 0), -1)
            if manual_end:
                cv2.circle(frame, manual_end, 10, (0, 0, 255), -1)
                cv2.putText(frame, "END", (manual_end[0]+10, manual_end[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                if radar_end: cv2.circle(radar_img, radar_end, 8, (0, 0, 255), -1)
            if radar_start and radar_end:
                cv2.line(radar_img, radar_start, radar_end, (0, 255, 255), 2)

            cv2.imshow("Click-to-Tag Assistant", frame)
            cv2.imshow("2D Radar Map", radar_img)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('r'):
                manual_start, manual_end = None, None
                radar_start, radar_end = None, None
                click_state = 0
                print("Reset tags.")
            elif key == ord('q'):
                break

    cv2.destroyAllWindows()