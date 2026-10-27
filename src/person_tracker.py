import time
import numpy as np
from collections import deque

class TrackedPerson:
    """
    Maintains clean persistent tracking state and temporal behavior history
    for an individual student (Person A, Person B).
    Preserves seat occupancy continuously even when the student puts their head down.
    """
    def __init__(self, track_id, label, bbox, sequence_length=10):
        self.track_id = track_id
        self.label = label
        self.bbox = list(bbox)  # [x, y, w, h]
        self.centroid = (bbox[0] + bbox[2] // 2, bbox[1] + bbox[3] // 2)
        self.disappeared = 0
        self.confirmed = True
        self.hit_count = 1

        # Temporal behavior history (10 samples at 5 FPS = 2.0s window)
        self.temporal_buffer = deque(maxlen=sequence_length)
        self.current_prediction = "Looking_Toward"
        self.confidence = 85.0
        self.last_face_seen_time = time.time()
        self.is_face_visible = True

        # Independent motion tracking for hand / desk area
        self.prev_desk_roi = None
        self.motion_history = deque(maxlen=6)
        self.smooth_motion = 0.0
        self.motion_level_text = "Still"

    def update_bbox(self, bbox):
        alpha = 0.60
        self.bbox[0] = int(alpha * bbox[0] + (1 - alpha) * self.bbox[0])
        self.bbox[1] = int(alpha * bbox[1] + (1 - alpha) * self.bbox[1])
        self.bbox[2] = int(alpha * bbox[2] + (1 - alpha) * self.bbox[2])
        self.bbox[3] = int(alpha * bbox[3] + (1 - alpha) * self.bbox[3])
        self.centroid = (self.bbox[0] + self.bbox[2] // 2, self.bbox[1] + self.bbox[3] // 2)
        self.disappeared = 0
        self.is_face_visible = True
        self.hit_count += 1


def clean_and_merge_boxes(boxes, frame_w=1280, min_size=50):
    """
    Merges duplicate detections of the same student (e.g. frontal face + profile + ear + shoulder).
    Ensures that any detections within close proximity (< 25% of frame width) are merged
    so 1 single student NEVER gets split into multiple people.
    """
    if len(boxes) == 0:
        return []

    # Discard tiny noise boxes (reflections, background specks)
    valid_boxes = [b for b in boxes if b[2] >= min_size and b[3] >= min_size]
    if len(valid_boxes) == 0:
        return []

    # Sort largest area first
    valid_boxes = sorted(valid_boxes, key=lambda b: b[2] * b[3], reverse=True)
    merged = []

    for box in valid_boxes:
        bx, by, bw, bh = box
        bcx = bx + bw // 2
        bcy = by + bh // 2
        matched = False

        for i, m in enumerate(merged):
            mx, my, mw, mh = m
            mcx = mx + mw // 2
            mcy = my + mh // 2

            # Compute IoU
            ix1 = max(bx, mx)
            iy1 = max(by, my)
            ix2 = min(bx + bw, mx + mw)
            iy2 = min(by + bh, my + mh)

            iou = 0.0
            if ix2 > ix1 and iy2 > iy1:
                inter = (ix2 - ix1) * (iy2 - iy1)
                union = bw * bh + mw * mh - inter
                iou = inter / float(union)

            dist_x = abs(bcx - mcx)
            dist_y = abs(bcy - mcy)

            # Two detections belong to the SAME person if:
            # 1. They overlap (IoU > 0.10)
            # 2. Or their horizontal distance is within 25% of frame width (same seating position)
            is_same_person = (
                iou > 0.10 or
                dist_x < max(bw, mw) * 1.2 or
                (dist_x < frame_w * 0.25 and dist_y < frame_w * 0.20)
            )

            if is_same_person:
                nx = min(bx, mx)
                ny = min(by, my)
                nw = max(bx + bw, mx + mw) - nx
                nh = max(by + bh, my + mh) - ny
                merged[i] = (nx, ny, nw, nh)
                matched = True
                break

        if not matched:
            merged.append(box)

    # Sort merged boxes left to right
    merged = sorted(merged, key=lambda b: b[0])
    return merged


class PersonTracker:
    """
    Classroom seating tracker.
    Maintains persistent student seats even when head is down,
    so Person A is NEVER lost when resting or writing.
    Strictly enforces max_persons so 1 person is ALWAYS strictly Person A.
    """
    def __init__(self, max_disappeared=1800, max_distance=220, sequence_length=10, max_persons=1):
        self.next_track_id = 0
        self.confirmed_tracks = {}  # track_id -> TrackedPerson
        # 1800 frames at 30 FPS = 60 seconds of tolerance during Head_Down resting
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.sequence_length = sequence_length
        self.max_persons = max_persons
        self.letters = ["Person A", "Person B"]

    def _reassign_labels(self):
        """
        Sort active confirmed tracks left-to-right:
        - If 1 person: always Person A.
        - If 2 people: left is Person A, right is Person B.
        """
        if len(self.confirmed_tracks) == 0:
            return

        sorted_tracks = sorted(self.confirmed_tracks.values(), key=lambda t: t.centroid[0])
        for idx, track in enumerate(sorted_tracks):
            track.label = self.letters[idx] if idx < len(self.letters) else f"Person {idx + 1}"

    def update(self, raw_bboxes, frame_w=1280):
        """
        Updates tracker state.
        Guarantees that when max_persons=1, strictly ONLY Person A exists.
        """
        clean_bboxes = clean_and_merge_boxes(raw_bboxes, frame_w=frame_w)

        # STRICT LIMIT: Cap clean boxes to max_persons
        if len(clean_bboxes) > self.max_persons:
            clean_bboxes = sorted(clean_bboxes, key=lambda b: b[2] * b[3], reverse=True)[:self.max_persons]

        # ------------------------------------------------------------
        # 1. Update Existing Tracks
        # ------------------------------------------------------------
        track_ids = list(self.confirmed_tracks.keys())
        used_det_indices = set()
        matched_track_ids = set()

        if len(track_ids) > 0 and len(clean_bboxes) > 0:
            det_centroids = np.array([(b[0] + b[2] // 2, b[1] + b[3] // 2) for b in clean_bboxes])
            track_centroids = np.array([self.confirmed_tracks[tid].centroid for tid in track_ids])

            D = np.linalg.norm(track_centroids[:, np.newaxis] - det_centroids, axis=2)

            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            for row, col in zip(rows, cols):
                if row in matched_track_ids or col in used_det_indices:
                    continue
                if D[row, col] > self.max_distance:
                    continue

                tid = track_ids[row]
                self.confirmed_tracks[tid].update_bbox(clean_bboxes[col])
                matched_track_ids.add(row)
                used_det_indices.add(col)

        # When head is down (no face detected):
        # DO NOT DELETE THE STUDENT! Student is simply in Head_Down or Writing posture!
        for idx, tid in enumerate(track_ids):
            if idx not in matched_track_ids:
                track = self.confirmed_tracks[tid]
                track.disappeared += 1
                track.is_face_visible = False
                # Student only leaves if absent for extended time (>60s)
                if track.disappeared > self.max_disappeared:
                    del self.confirmed_tracks[tid]

        # ------------------------------------------------------------
        # 2. Register New Person (ONLY if under max_persons cap)
        # ------------------------------------------------------------
        unmatched_dets = [clean_bboxes[i] for i in range(len(clean_bboxes)) if i not in used_det_indices]

        for d_box in unmatched_dets:
            if len(self.confirmed_tracks) < self.max_persons:
                new_track = TrackedPerson(
                    track_id=self.next_track_id,
                    label=self.letters[len(self.confirmed_tracks)],
                    bbox=d_box,
                    sequence_length=self.sequence_length
                )
                self.confirmed_tracks[self.next_track_id] = new_track
                self.next_track_id += 1

        self._reassign_labels()
        return self.confirmed_tracks
