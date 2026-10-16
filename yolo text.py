
import cv2
import time
import torch
from ultralytics import YOLO


# ---------------- CONFIGURATION ----------------
MODEL_PATH = "yolov8x.pt"
CAMERA_INDEX = 0
IMAGE_SIZE = 640
CONFIDENCE = 0.40
# ------------------------------------------------


def main():
    print("Loading YOLOv8x model...")

    # Automatically select NVIDIA GPU or CPU
    device = 0 if torch.cuda.is_available() else "cpu"

    if torch.cuda.is_available():
        print("CUDA available:", torch.cuda.get_device_name(0))
    else:
        print("CUDA unavailable. Running on CPU.")

    # Load pretrained YOLOv8x COCO model.
    # The weights download automatically on the first run.
    model = YOLO(MODEL_PATH)

    print(f"Model loaded. Device: {device}")
    print("Opening webcam...")

    # Open webcam
    camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

    if not camera.isOpened():
        camera.release()
        camera = cv2.VideoCapture(CAMERA_INDEX)

    if not camera.isOpened():
        print("ERROR: Cannot access webcam.")
        print("Check camera permissions or change CAMERA_INDEX.")
        return

    # Webcam resolution
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    previous_time = time.perf_counter()

    print("Detection started. Press Q to quit.")

    try:
        while True:
            success, frame = camera.read()

            if not success:
                print("Failed to capture webcam frame.")
                break

            # Run YOLO object detection
            results = model.predict(
                source=frame,
                imgsz=IMAGE_SIZE,
                conf=CONFIDENCE,
                device=device,
                half=(device != "cpu"),
                verbose=False
            )

            # Draw bounding boxes, class names and confidence
            annotated_frame = results[0].plot()

            # Calculate FPS
            current_time = time.perf_counter()
            elapsed = current_time - previous_time
            fps = 1.0 / elapsed if elapsed > 0 else 0
            previous_time = current_time

            # Count detected objects
            boxes = results[0].boxes
            object_count = len(boxes)

            # Display FPS and object count
            cv2.putText(
                annotated_frame,
                f"FPS: {fps:.1f}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            cv2.putText(
                annotated_frame,
                f"Objects detected: {object_count}",
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2
            )

            cv2.imshow("YOLOv8x - Webcam Object Detection",
                       annotated_frame)

            # Press Q or ESC to exit
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break

    except KeyboardInterrupt:
        print("\nDetection stopped.")

    except Exception as error:
        print("Runtime error:", error)

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Webcam released. Program closed.")


if __name__ == "__main__":
    main()
