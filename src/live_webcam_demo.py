import os
import time
import argparse
from collections import deque

import cv2
import numpy as np

# ============================================================
# 1. Classes and Visual Styling
# ============================================================
classes = [
    "Head_Down",
    "Looking_Away",
    "Looking_Toward",
    "Writing"
]

CLASS_COLORS = {
    "Head_Down": (0, 140, 255),      # Orange
    "Looking_Away": (0, 215, 255),   # Yellow
    "Looking_Toward": (0, 220, 0),   # Green
    "Writing": (255, 130, 0)         # Blue
}

def run_live_webcam(camera_index=0, sequence_length=10, sample_fps=5, motion_pixel_threshold=500, start_fullscreen=True):
    print("============================================================")
    print("PRECISION WEBCAM BEHAVIOR PROFILER (HEAD DOWN & WRITING TUNED)")
    print("============================================================")
    print(f"Camera Index      : {camera_index}")
    print(f"Motion Threshold  : {motion_pixel_threshold} active pixels")
    print("Controls          : 'f' = Fullscreen | 'w'/'s' = Move Desk Line Up/Down | '+' / '-' = Motion Sens | 'q' = Quit")
    print("============================================================\n")

    # ------------------------------------------------------------
    # Load OpenCV Detectors
    # ------------------------------------------------------------
    frontal_path = "models/haarcascade_frontalface_default.xml"
    profile_path = "models/haarcascade_profileface.xml"
    eye_path = "models/haarcascade_eye.xml"

    frontal_cascade = cv2.CascadeClassifier(frontal_path) if os.path.exists(frontal_path) else None
    profile_cascade = cv2.CascadeClassifier(profile_path) if os.path.exists(profile_path) else None
    eye_cascade = cv2.CascadeClassifier(eye_path) if os.path.exists(eye_path) else None

    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        print(f"[Error] Could not open camera {camera_index}.")
        return

    window_name = "Classroom Behavior Profiler (Live)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    is_fullscreen = start_fullscreen
    if is_fullscreen:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    else:
        cv2.resizeWindow(window_name, 1280, 720)

    # Temporal Sequence Buffer
    prediction_buffer = deque(maxlen=sequence_length)
    sample_interval = 1.0 / sample_fps
    last_sample_time = 0.0

    # Motion Tracking
    prev_desk_gray = None
    motion_pixel_history = deque(maxlen=4)
    desk_ratio = 0.52  # Starts at 52% of screen height (lower half where hands/desk reside)

    current_prediction = "Looking_Toward"
    current_confidence = 85.0
    probabilities = [0.05, 0.05, 0.85, 0.05]
    diag_status = "Calibrating..."

    last_head_seen_time = time.time()

    print("[Running] Fullscreen active. Testing all 4 behaviors.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w, _ = frame.shape
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        current_time = time.time()

        scale = max(1.0, w / 1000.0)
        banner_h = int(95 * scale)
        font_title_sz = 0.85 * scale
        font_sub_sz = 0.52 * scale

        # ------------------------------------------------------------
        # 1. High-Sensitivity Desk & Hand Motion Detection
        # ------------------------------------------------------------
        desk_y_start = int(h * desk_ratio)
        desk_roi = gray[desk_y_start:, :]
        active_motion_pixels = 0
        motion_mask = None

        if prev_desk_gray is not None and prev_desk_gray.shape == desk_roi.shape:
            # Blur slightly to eliminate sensor grain
            blur_curr = cv2.GaussianBlur(desk_roi, (7, 7), 0)
            blur_prev = cv2.GaussianBlur(prev_desk_gray, (7, 7), 0)
            diff = cv2.absdiff(blur_curr, blur_prev)

            # Threshold movement: pen, hands, wrists moving on desk
            _, motion_mask = cv2.threshold(diff, 14, 255, cv2.THRESH_BINARY)
            active_motion_pixels = int(np.count_nonzero(motion_mask))

        prev_desk_gray = desk_roi.copy()
        motion_pixel_history.append(active_motion_pixels)
        smooth_active_pixels = int(np.mean(motion_pixel_history)) if len(motion_pixel_history) > 0 else 0

        # ------------------------------------------------------------
        # 2. Face and Gaze Posture Detection
        # ------------------------------------------------------------
        small_gray = cv2.resize(gray, (w // 2, h // 2))
        faces_frontal = []
        faces_profile_left = []
        faces_profile_right = []
        eyes_detected = []

        # A. Frontal Face (Looking Toward)
        if frontal_cascade is not None and not frontal_cascade.empty():
            faces_frontal = frontal_cascade.detectMultiScale(
                small_gray, scaleFactor=1.15, minNeighbors=5, minSize=(35, 35)
            )

        # B. Profile Face (Looking Away - Left & Right)
        if profile_cascade is not None and not profile_cascade.empty():
            faces_profile_left = profile_cascade.detectMultiScale(
                small_gray, scaleFactor=1.15, minNeighbors=4, minSize=(30, 30)
            )
            small_gray_flipped = cv2.flip(small_gray, 1)
            faces_profile_right = profile_cascade.detectMultiScale(
                small_gray_flipped, scaleFactor=1.15, minNeighbors=4, minSize=(30, 30)
            )

        # C. Eyes inside Frontal Face
        if len(faces_frontal) > 0 and eye_cascade is not None and not eye_cascade.empty():
            fx, fy, fw, fh = faces_frontal[0]
            face_roi_gray = small_gray[fy:fy + int(fh * 0.65), fx:fx + fw]
            eyes = eye_cascade.detectMultiScale(face_roi_gray, scaleFactor=1.1, minNeighbors=4, minSize=(12, 12))
            for ex, ey, ew, eh in eyes:
                eyes_detected.append((ex * 2 + fx * 2, ey * 2 + fy * 2, ew * 2, eh * 2))

        # ------------------------------------------------------------
        # 3. Behavior Decision Logic
        # ------------------------------------------------------------
        face_rect = None
        has_profile = (len(faces_profile_left) > 0 or len(faces_profile_right) > 0)
        has_frontal = (len(faces_frontal) > 0)

        if has_frontal:
            fx, fy, fw, fh = faces_frontal[0]
            face_rect = (fx * 2, fy * 2, fw * 2, fh * 2)
            last_head_seen_time = current_time

            # If profile detected alongside or eyes not engaged forward
            if has_profile and len(eyes_detected) <= 1:
                frame_posture = "Looking_Away"
                diag_status = "Head Turned (Profile / Away)"
            else:
                frame_posture = "Looking_Toward"
                diag_status = f"Facing Camera ({len(eyes_detected)} eyes detected)"

        elif has_profile:
            last_head_seen_time = current_time
            if len(faces_profile_left) > 0:
                px, py, pw, ph = faces_profile_left[0]
                face_rect = (px * 2, py * 2, pw * 2, ph * 2)
                diag_status = "Head Turned Left -> Looking Away"
            else:
                px, py, pw, ph = faces_profile_right[0]
                orig_px = (small_gray.shape[1] - px - pw)
                face_rect = (orig_px * 2, py * 2, pw * 2, ph * 2)
                diag_status = "Head Turned Right -> Looking Away"
            frame_posture = "Looking_Away"

        else:
            # Neither frontal nor profile face detected:
            # Check if head is tilted down vs turned completely away
            time_since_head = current_time - last_head_seen_time

            # Hand Motion Check: Writing vs Head Down
            if smooth_active_pixels >= motion_pixel_threshold:
                frame_posture = "Writing"
                diag_status = f"Head Down + Hand Motion ({smooth_active_pixels} px >= {motion_pixel_threshold})"
            elif time_since_head < 0.8:
                # Recently looking away before face turned further
                frame_posture = "Looking_Away"
                diag_status = "Gaze Turned Away from Screen"
            else:
                # Stationary posture with head down
                frame_posture = "Head_Down"
                diag_status = f"Head Down + Stationary ({smooth_active_pixels} px < {motion_pixel_threshold})"

        # ------------------------------------------------------------
        # 4. Temporal Sequence Smoothing (5 FPS)
        # ------------------------------------------------------------
        if current_time - last_sample_time >= sample_interval:
            last_sample_time = current_time
            prediction_buffer.append(frame_posture)

            counts = {c: prediction_buffer.count(c) for c in classes}
            current_prediction = max(counts, key=counts.get)
            current_confidence = (counts[current_prediction] / len(prediction_buffer)) * 100.0
            probabilities = [counts[c] / len(prediction_buffer) for c in classes]

        # ------------------------------------------------------------
        # 5. Fullscreen HUD Render
        # ------------------------------------------------------------
        display = frame.copy()
        color = CLASS_COLORS[current_prediction]

        # Highlight active moving hand pixels in blue/cyan on the screen
        if motion_mask is not None and smooth_active_pixels >= (motion_pixel_threshold // 2):
            # Highlight motion pixels in desk region
            mask_indices = np.where(motion_mask > 0)
            if len(mask_indices[0]) > 0:
                roi_color = display[desk_y_start:, :]
                roi_color[mask_indices[0], mask_indices[1]] = [255, 180, 0]  # Cyan/blue highlight

        # Draw Face box
        if face_rect is not None:
            bx, by, bw, bh = face_rect
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), color, int(2 * scale))
            cv2.putText(display, current_prediction, (bx, by - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.65 * scale, color, int(2 * scale))

        # Draw Eye markers
        for ex, ey, ew, eh in eyes_detected:
            cv2.circle(display, (ex + ew // 2, ey + eh // 2), int(4 * scale), (0, 255, 0), -1)

        # Draw Desk / Hand Motion Boundary Line
        desk_line_color = (255, 140, 0) if (smooth_active_pixels >= motion_pixel_threshold) else (100, 100, 100)
        cv2.line(display, (0, desk_y_start), (w, desk_y_start), desk_line_color, int(2 * scale), cv2.LINE_AA)

        # Draw Motion Meter Bar
        bar_max_w = int(220 * scale)
        motion_fill = int(min(bar_max_w, (smooth_active_pixels / max(1, motion_pixel_threshold * 2)) * bar_max_w))
        bar_y1 = desk_y_start + int(10 * scale)
        bar_y2 = desk_y_start + int(24 * scale)
        bar_col = (255, 120, 0) if (smooth_active_pixels >= motion_pixel_threshold) else (0, 140, 255)

        cv2.rectangle(display, (15, bar_y1), (15 + motion_fill, bar_y2), bar_col, -1)
        cv2.rectangle(display, (15, bar_y1), (15 + bar_max_w, bar_y2), (180, 180, 180), 1)

        motion_label = f"Desk/Hand Activity: {smooth_active_pixels} px (Threshold: {motion_pixel_threshold} px)"
        cv2.putText(display, motion_label, (15, desk_y_start + int(42 * scale)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45 * scale, (220, 220, 220), 1)

        # Top Banner Box
        cv2.rectangle(display, (10, 10), (w - 10, banner_h), (20, 20, 20), -1)
        cv2.rectangle(display, (10, 10), (w - 10, banner_h), color, int(2 * scale))

        pred_title = f"Observable Behavior: {current_prediction.upper()}"
        detail_text = f"Confidence: {current_confidence:.0f}%  |  {diag_status}"
        cv2.putText(display, pred_title, (int(25 * scale), int(48 * scale)), cv2.FONT_HERSHEY_SIMPLEX, font_title_sz, color, int(2 * scale))
        cv2.putText(display, detail_text, (int(25 * scale), int(80 * scale)), cv2.FONT_HERSHEY_SIMPLEX, font_sub_sz, (220, 220, 220), 1)

        # Bottom Bar: Probability Breakdown
        bar_y = h - int(25 * scale)
        col_w = (w - 40) // 4
        for i, c_name in enumerate(classes):
            val = probabilities[i] * 100.0
            cx = 20 + i * col_w
            c_col = CLASS_COLORS.get(c_name, (200, 200, 200))
            is_top = (c_name == current_prediction)
            prefix = "[*] " if is_top else "    "
            cv2.putText(display, f"{prefix}{c_name[:12]}: {val:.0f}%", (cx, bar_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48 * scale, c_col, int(2 * scale) if is_top else 1)

        # Footer Keys
        cv2.putText(display, "'w'/'s' = Move Desk Line | '+' / '-' = Motion Sens | 'f' = Fullscreen | 'q' = Quit",
                    (w - int(600 * scale), h - int(8 * scale)), cv2.FONT_HERSHEY_SIMPLEX, 0.40 * scale, (160, 160, 160), 1)

        cv2.imshow(window_name, display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('f'):
            is_fullscreen = not is_fullscreen
            if is_fullscreen:
                cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(window_name, 1280, 720)
        elif key == ord('w'):
            desk_ratio = max(0.30, desk_ratio - 0.04)
            print(f"[Desk Line Moved Up] Now at {int(desk_ratio * 100)}% of screen height")
        elif key == ord('s'):
            desk_ratio = min(0.85, desk_ratio + 0.04)
            print(f"[Desk Line Moved Down] Now at {int(desk_ratio * 100)}% of screen height")
        elif key == ord('+') or key == ord('='):
            motion_pixel_threshold = max(100, motion_pixel_threshold - 100)
            print(f"[Sensitivity Increased] Threshold: {motion_pixel_threshold} active pixels")
        elif key == ord('-'):
            motion_pixel_threshold = min(3000, motion_pixel_threshold + 100)
            print(f"[Sensitivity Decreased] Threshold: {motion_pixel_threshold} active pixels")

    cap.release()
    cv2.destroyAllWindows()
    print("[Done] Profiler closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precision webcam behavior profiler.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--threshold", type=int, default=500, help="Active pixels threshold for writing (default: 500)")
    parser.add_argument("--seq-len", type=int, default=10, help="Sequence length (default: 10)")
    parser.add_argument("--fps", type=int, default=5, help="Sampling FPS (default: 5)")
    parser.add_argument("--windowed", action="store_true", help="Start in windowed mode instead of fullscreen")
    args = parser.parse_args()

    run_live_webcam(
        camera_index=args.camera,
        motion_pixel_threshold=args.threshold,
        sequence_length=args.seq_len,
        sample_fps=args.fps,
        start_fullscreen=not args.windowed
    )
