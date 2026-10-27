import os
import time
import argparse
from collections import deque

import cv2
import numpy as np

try:
    from src.person_tracker import PersonTracker
except ModuleNotFoundError:
    from person_tracker import PersonTracker

# ============================================================
# 1. Behavior Classes & Styling
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
    "Writing": (255, 140, 0)         # Deep Blue/Cyan
}

def run_multi_person_profiler(source=0, max_persons=1, sequence_length=10, sample_fps=5,
                               motion_threshold=0.80, start_fullscreen=True):
    print("============================================================")
    print("CLASSROOM BEHAVIOR PROFILER (FOOLPROOF ENGINE)")
    print("============================================================")
    print(f"Video Source         : {source}")
    print(f"Student Mode         : {'Single Student (Person A)' if max_persons == 1 else '2 Students (Person A & B)'}")
    print(f"Motion Sens Threshold: {motion_threshold:.2f}% (Desk/Hand area)")
    print("Controls             : 'm' = Toggle 1/2 Students | 'f' = Fullscreen | '+' / '-' = Motion Sens | 'r' = Reset | 'q' = Quit")
    print("============================================================\n")

    frontal_path = "models/haarcascade_frontalface_default.xml"
    profile_path = "models/haarcascade_profileface.xml"

    frontal_cascade = cv2.CascadeClassifier(frontal_path) if os.path.exists(frontal_path) else None
    profile_cascade = cv2.CascadeClassifier(profile_path) if os.path.exists(profile_path) else None

    if isinstance(source, str) and source.isdigit():
        source = int(source)

    cap = cv2.VideoCapture(source)
    if isinstance(source, int):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        print(f"[Error] Could not open video source: {source}")
        return

    window_name = "Classroom Behavior Profiler (Live)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    is_fullscreen = start_fullscreen
    if is_fullscreen:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    else:
        cv2.resizeWindow(window_name, 1280, 720)

    # Tracker preserves students when head is down for up to 60 seconds (1800 frames)
    tracker = PersonTracker(max_disappeared=1800, max_distance=220, sequence_length=sequence_length, max_persons=max_persons)

    sample_interval = 1.0 / sample_fps
    last_sample_time = 0.0

    # 5x5 kernel to completely eliminate CMOS noise speckles
    morph_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    print("[Running] Profiler active. Press 'f' for fullscreen toggle, 'm' for 1/2 students toggle, 'q' to quit.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w, _ = frame.shape
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        current_time = time.time()

        scale = max(1.0, w / 1000.0)
        banner_h = int(88 * scale)

        # ------------------------------------------------------------
        # 1. Face & Head Detection (High minNeighbors=6 to eliminate false alarms)
        # ------------------------------------------------------------
        small_w = 640
        small_h = int(640 * h / w)
        small_gray = cv2.resize(gray, (small_w, small_h))
        scale_x = w / float(small_w)
        scale_y = h / float(small_h)

        faces_frontal = []
        if frontal_cascade is not None and not frontal_cascade.empty():
            f_dets = frontal_cascade.detectMultiScale(
                small_gray, scaleFactor=1.15, minNeighbors=6, minSize=(45, 45)
            )
            for (fx, fy, fw, fh) in f_dets:
                faces_frontal.append((int(fx * scale_x), int(fy * scale_y), int(fw * scale_x), int(fh * scale_y)))

        faces_profile = []
        if profile_cascade is not None and not profile_cascade.empty():
            p_dets_l = profile_cascade.detectMultiScale(
                small_gray, scaleFactor=1.15, minNeighbors=6, minSize=(45, 45)
            )
            for (px, py, pw, ph) in p_dets_l:
                faces_profile.append((int(px * scale_x), int(py * scale_y), int(pw * scale_x), int(ph * scale_y)))

            small_gray_flipped = cv2.flip(small_gray, 1)
            p_dets_r = profile_cascade.detectMultiScale(
                small_gray_flipped, scaleFactor=1.15, minNeighbors=6, minSize=(45, 45)
            )
            for (px, py, pw, ph) in p_dets_r:
                orig_px = small_w - px - pw
                faces_profile.append((int(orig_px * scale_x), int(py * scale_y), int(pw * scale_x), int(ph * scale_y)))

        # Candidate boxes for tracker
        candidate_boxes = faces_frontal + faces_profile

        # ------------------------------------------------------------
        # 2. Update Student Tracker (Preserves Person when head is down)
        # ------------------------------------------------------------
        active_tracks = tracker.update(candidate_boxes, frame_w=w)

        display = frame.copy()

        should_sample = (current_time - last_sample_time >= sample_interval)
        if should_sample:
            last_sample_time = current_time

        sorted_tracks = sorted(active_tracks.values(), key=lambda t: t.centroid[0])
        num_students = len(sorted_tracks)

        for track in sorted_tracks:
            tx, ty, tw, th = track.bbox

            # Check if frontal or profile face is visible near this student
            has_frontal = any(
                abs(f[0] - tx) < tw * 1.2 and abs(f[1] - ty) < th * 1.2 for f in faces_frontal
            )
            has_profile = any(
                abs(p[0] - tx) < tw * 1.2 and abs(p[1] - ty) < th * 1.2 for p in faces_profile
            )

            # --------------------------------------------------------
            # Precision Desk / Hand Motion Tracking (Lower Desk Area Only)
            # --------------------------------------------------------
            # Desk area: below the chest, specifically where hands write on the table
            desk_y1 = max(int(h * 0.60), min(h - 20, ty + int(th * 1.2)))
            desk_y2 = h
            desk_x1 = max(0, tx - int(tw * 0.5))
            desk_x2 = min(w, tx + int(tw * 1.5))

            motion_pct = 0.0
            if desk_y2 > desk_y1 and desk_x2 > desk_x1:
                desk_roi = gray[desk_y1:desk_y2, desk_x1:desk_x2]
                desk_blur = cv2.GaussianBlur(desk_roi, (9, 9), 0)

                if track.prev_desk_roi is not None and track.prev_desk_roi.shape == desk_blur.shape:
                    diff = cv2.absdiff(desk_blur, track.prev_desk_roi)
                    # High threshold 24 to ignore auto-exposure and breathing
                    _, thresh = cv2.threshold(diff, 24, 255, cv2.THRESH_BINARY)
                    clean_diff = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, morph_kernel)
                    active_px = int(np.count_nonzero(clean_diff))
                    motion_pct = (active_px / float(clean_diff.size)) * 100.0

                track.prev_desk_roi = desk_blur.copy()

            track.motion_history.append(motion_pct)
            smooth_motion = float(np.mean(track.motion_history)) if len(track.motion_history) > 0 else 0.0
            track.smooth_motion = smooth_motion

            # Hand Motion Decision: Writing motion active vs Still
            is_hand_moving = smooth_motion >= motion_threshold
            track.motion_level_text = f"Hand: Active ({smooth_motion:.1f}%)" if is_hand_moving else f"Hand: Still ({smooth_motion:.1f}%)"

            # --------------------------------------------------------
            # Behavioral Classification Logic (Hierarchy)
            # --------------------------------------------------------
            # 1. Student is facing camera -> LOOKING_TOWARD
            if has_frontal:
                frame_posture = "Looking_Toward"
                track.last_face_seen_time = current_time

            # 2. Student is turned sideways -> LOOKING_AWAY
            elif has_profile:
                frame_posture = "Looking_Away"
                track.last_face_seen_time = current_time

            # 3. No face visible (Student's head is tilted down towards desk / resting)
            else:
                # Active hand movement on desk -> WRITING
                # Stillness / resting on table -> HEAD_DOWN
                if is_hand_moving:
                    frame_posture = "Writing"
                else:
                    frame_posture = "Head_Down"

            # Temporal Smoothing Buffer (5 FPS, length 10 = 2.0s window)
            if should_sample:
                track.temporal_buffer.append(frame_posture)
                counts = {c: track.temporal_buffer.count(c) for c in classes}
                track.current_prediction = max(counts, key=counts.get)
                track.confidence = (counts[track.current_prediction] / len(track.temporal_buffer)) * 100.0

            # --------------------------------------------------------
            # Clean HUD: Person Bounding Box & Behavior Tag
            # --------------------------------------------------------
            p_color = CLASS_COLORS[track.current_prediction]

            # When head is down, frame the student's resting upper body/head
            if track.current_prediction in ["Head_Down", "Writing"]:
                disp_y = min(h - th, ty + int(th * 0.35))
            else:
                disp_y = ty

            # Box around student
            box_h = int(th * 1.3)
            disp_y_bottom = min(h - 2, disp_y + box_h)
            cv2.rectangle(display, (tx, disp_y), (tx + tw, disp_y_bottom), p_color, int(2 * scale))

            # Main Tag: "Person A: LOOKING_TOWARD (90%)"
            tag_text = f"{track.label}: {track.current_prediction.upper()} ({track.confidence:.0f}%)"
            tag_w = int(len(tag_text) * 11 * scale)
            cv2.rectangle(display, (tx, max(0, disp_y - int(28 * scale))), (tx + tag_w, disp_y), (20, 20, 20), -1)
            cv2.putText(display, tag_text, (tx + 4, max(12, disp_y - int(8 * scale))),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55 * scale, p_color, int(2 * scale))

            # Motion Activity Indicator Badge below the tag
            m_badge_color = (255, 180, 0) if is_hand_moving else (140, 140, 140)
            badge_text = f"[{track.motion_level_text} | Thresh: {motion_threshold:.1f}%]"
            badge_w = int(len(badge_text) * 8.5 * scale)
            badge_y = disp_y_bottom + int(18 * scale)
            if badge_y < h - 10:
                cv2.rectangle(display, (tx, disp_y_bottom), (tx + badge_w, badge_y), (20, 20, 20), -1)
                cv2.putText(display, badge_text, (tx + 3, badge_y - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42 * scale, m_badge_color, 1)

        # ------------------------------------------------------------
        # 3. Clean Classroom Top Banner
        # ------------------------------------------------------------
        cv2.rectangle(display, (10, 10), (w - 10, banner_h), (20, 20, 20), -1)
        cv2.rectangle(display, (10, 10), (w - 10, banner_h), (70, 70, 70), int(1 * scale))

        mode_desc = f"Mode: {'1 Student (Person A)' if tracker.max_persons == 1 else '2 Students (Person A & B)'}"
        title_str = f"CLASSROOM BEHAVIOR PROFILER  |  {mode_desc}  |  Active: {num_students}"
        cv2.putText(display, title_str, (int(25 * scale), int(32 * scale)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62 * scale, (220, 220, 220), int(2 * scale))

        if num_students > 0:
            summary_parts = []
            for p in sorted_tracks:
                summary_parts.append(f"{p.label}: {p.current_prediction} ({p.confidence:.0f}%)")
            summary_str = "   |   ".join(summary_parts)
            cv2.putText(display, summary_str, (int(25 * scale), int(68 * scale)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.54 * scale, (255, 215, 0), int(1 * scale))
        else:
            cv2.putText(display, "Waiting for student to face camera...", (int(25 * scale), int(68 * scale)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52 * scale, (150, 150, 150), 1)

        # Footer Navigation
        cv2.putText(display, "Controls: 'm' = Toggle 1/2 Students | 'f' = Fullscreen | '+' / '-' = Motion Sens | 'r' = Reset | 'q' = Quit",
                    (w - int(660 * scale), h - int(10 * scale)), cv2.FONT_HERSHEY_SIMPLEX, 0.40 * scale, (160, 160, 160), 1)

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
        elif key == ord('m'):
            new_max = 2 if tracker.max_persons == 1 else 1
            tracker.max_persons = new_max
            if new_max == 1 and len(tracker.confirmed_tracks) > 1:
                # Keep only Person A
                first_k = list(tracker.confirmed_tracks.keys())[0]
                tracker.confirmed_tracks = {first_k: tracker.confirmed_tracks[first_k]}
                tracker._reassign_labels()
            print(f"[Mode Switched] Now in: {'1 Student Mode (Person A only)' if new_max == 1 else '2 Students Mode (Person A & B)'}")
        elif key == ord('+') or key == ord('='):
            motion_threshold = min(5.0, motion_threshold + 0.20)
            print(f"[Threshold Increased] Threshold: {motion_threshold:.2f}% active desk area")
        elif key == ord('-') or key == ord('_'):
            motion_threshold = max(0.20, motion_threshold - 0.20)
            print(f"[Threshold Decreased] Threshold: {motion_threshold:.2f}% active desk area")
        elif key == ord('r'):
            tracker = PersonTracker(max_disappeared=1800, max_distance=220, sequence_length=sequence_length, max_persons=tracker.max_persons)
            print("[Seats Reset] Cleared student tracks.")

    cap.release()
    cv2.destroyAllWindows()
    print("[Done] Profiler closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean Classroom Multi-Person Behavior Profiler.")
    parser.add_argument("--source", type=str, default="0", help="Camera index (e.g., 0) or path to video file")
    parser.add_argument("--max-persons", type=int, default=1, help="Max students to profile (default: 1, use 2 for multi-person)")
    parser.add_argument("--threshold", type=float, default=0.80, help="Motion threshold percent for writing (default: 0.80)")
    parser.add_argument("--seq-len", type=int, default=10, help="Temporal sequence length (default: 10)")
    parser.add_argument("--fps", type=int, default=5, help="Sampling FPS (default: 5)")
    parser.add_argument("--windowed", action="store_true", help="Start in windowed mode instead of fullscreen")
    args = parser.parse_args()

    run_multi_person_profiler(
        source=args.source,
        max_persons=args.max_persons,
        motion_threshold=args.threshold,
        sequence_length=args.seq_len,
        sample_fps=args.fps,
        start_fullscreen=not args.windowed
    )

