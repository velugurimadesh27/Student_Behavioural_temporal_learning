import time
import numpy as np
from collections import deque

class TrackedPerson:
    """
    Maintains clean persistent tracking state and temporal behavior history
    for an individual student (Person A, Person B, Person C, etc.).
    Preserves seat occupancy continuously during Head_Down, while quickly
    recognizing when a student stands up and leaves the screen.
    """
    def __init__(self, track_id, label, bbox, sequence_length=10):
        self.track_id = track_id
        self.label = label
        self.bbox = list(bbox)  # [x, y, w, h]
        self.centroid = (bbox[0] + bbox[2] // 2, bbox[1] + bbox[3] // 2)
        self.disappeared = 0
        self.confirmed = True
        self.hit_count = 1
        self.is_departing = False

        # Temporal behavior history (10 samples at 5 FPS = 2.0s window)
        self.temporal_buffer = deque(maxlen=sequence_length)
        self.current_prediction = "Looking_Toward"
        self.confidence = 85.0
        self.last_face_seen_time = time.time()
        self.is_face_visible = True

        # Independent motion and writing analysis for this student
        self.prev_desk_roi = None
        self.motion_history = deque(maxlen=6)
        self.smooth_motion = 0.0
        self.motion_level_text = "Still"
        self.writing_score = 0

    def update_bbox(self, bbox, frame_w=1280, frame_h=720):
        alpha = 0.60
        self.bbox[0] = int(alpha * bbox[0] + (1 - alpha) * self.bbox[0])
        self.bbox[1] = int(alpha * bbox[1] + (1 - alpha) * self.bbox[1])
        self.bbox[2] = int(alpha * bbox[2] + (1 - alpha) * self.bbox[2])
        self.bbox[3] = int(alpha * bbox[3] + (1 - alpha) * self.bbox[3])
        self.centroid = (self.bbox[0] + self.bbox[2] // 2, self.bbox[1] + self.bbox[3] // 2)
        
        # Check if student is near frame boundary / walking out
        cx, cy = self.centroid
        if cx < frame_w * 0.15 or cx > frame_w * 0.85 or cy < frame_h * 0.12:
            self.is_departing = True
        else:
            self.is_departing = False

        self.disappeared = 0
        self.is_face_visible = True
        self.hit_count += 1


def clean_and_merge_boxes(boxes, frame_w=1280, min_size=40):
    """
    Merges duplicate detections of the same student (e.g. frontal face + profile + ear).
    Ensures that any detections belonging to the same head/torso are merged
    so one individual student is NEVER split into multiple people.
    """
    if len(boxes) == 0:
        return []

    # Discard tiny noise specks
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

            # Two detections belong to the SAME person if overlapping or close
            is_same_person = (
                iou > 0.10 or
                (dist_x < max(bw, mw) * 1.15 and dist_y < max(bh, mh) * 1.15)
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
    Dynamic Classroom Student Tracker.
    Automatically detects and tracks as many students as are visible in the camera (Person A, B, C, D...).
    - Filters out transient 1-frame glitches so one person never gets a ghost twin.
    - Preserves student identity when putting head down.
    - Detects when a student stands up and leaves the screen, removing them within 1 second.
    """
    def __init__(self, max_disappeared=150, max_distance=180, sequence_length=10, max_persons=10):
        self.next_track_id = 0
        self.confirmed_tracks = {}   # track_id -> TrackedPerson
        self.candidate_tracks = {}   # cand_id -> {'bbox': bbox, 'hits': count, 'disappeared': count}
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.sequence_length = sequence_length
        self.max_persons = max_persons

    def _get_label(self, idx):
        if idx < 26:
            return f"Person {chr(65 + idx)}"
        return f"Person {idx + 1}"

    def _reassign_labels(self):
        """
        Sort active confirmed tracks left-to-right across the camera view:
        Leftmost is Person A, next is Person B, next is Person C, Person D, etc.
        """
        if len(self.confirmed_tracks) == 0:
            return

        sorted_tracks = sorted(self.confirmed_tracks.values(), key=lambda t: t.centroid[0])
        for idx, track in enumerate(sorted_tracks):
            track.label = self._get_label(idx)

    def update(self, raw_bboxes, frame_w=1280, frame_h=720):
        """
        Updates multi-student tracker.
        Dynamically adapts to however many people are visible in the frame.
        """
        clean_bboxes = clean_and_merge_boxes(raw_bboxes, frame_w=frame_w)

        if self.max_persons is not None and len(clean_bboxes) > self.max_persons:
            clean_bboxes = sorted(clean_bboxes, key=lambda b: b[2] * b[3], reverse=True)[:self.max_persons]

        # ------------------------------------------------------------
        # 1. Update Existing Confirmed Tracks
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
                self.confirmed_tracks[tid].update_bbox(clean_bboxes[col], frame_w=frame_w, frame_h=frame_h)
                matched_track_ids.add(row)
                used_det_indices.add(col)

        # For confirmed tracks with no face detection this frame:
        for idx, tid in enumerate(track_ids):
            if idx not in matched_track_ids:
                track = self.confirmed_tracks[tid]
                track.disappeared += 1
                track.is_face_visible = False

                # Departure Checks:
                # 1. If person was near edge or stood up to exit and disappeared for > 20 frames (~0.7s) -> REMOVE!
                if track.is_departing and track.disappeared > 20:
                    del self.confirmed_tracks[tid]
                    continue

                # 2. General timeout if completely absent for > max_disappeared frames (~5s) -> REMOVE!
                if track.disappeared > self.max_disappeared:
                    del self.confirmed_tracks[tid]
                    continue

        # ------------------------------------------------------------
        # 2. Process Unmatched Detections with Candidate Verification
        # ------------------------------------------------------------
        unmatched_dets = [clean_bboxes[i] for i in range(len(clean_bboxes)) if i not in used_det_indices]

        # Match unmatched detections against existing candidate tracks
        cand_ids = list(self.candidate_tracks.keys())
        used_cand_dets = set()

        for cid in cand_ids:
            cand = self.candidate_tracks[cid]
            c_center = (cand['bbox'][0] + cand['bbox'][2] // 2, cand['bbox'][1] + cand['bbox'][3] // 2)
            matched = False

            for d_idx, d_box in enumerate(unmatched_dets):
                if d_idx in used_cand_dets:
                    continue
                d_center = (d_box[0] + d_box[2] // 2, d_box[1] + d_box[3] // 2)
                dist = np.hypot(c_center[0] - d_center[0], c_center[1] - d_center[1])

                if dist < self.max_distance:
                    cand['bbox'] = d_box
                    cand['hits'] += 1
                    cand['disappeared'] = 0
                    used_cand_dets.add(d_idx)
                    matched = True

                    # Confirm as a new student if observed consistently for 3 frames!
                    if cand['hits'] >= 3:
                        if self.max_persons is None or len(self.confirmed_tracks) < self.max_persons:
                            new_track = TrackedPerson(
                                track_id=self.next_track_id,
                                label="",
                                bbox=d_box,
                                sequence_length=self.sequence_length
                            )
                            self.confirmed_tracks[self.next_track_id] = new_track
                            self.next_track_id += 1
                        del self.candidate_tracks[cid]
                    break

            if not matched:
                cand['disappeared'] += 1
                if cand['disappeared'] > 4:
                    # Drop transient glitch
                    del self.candidate_tracks[cid]

        # Register remaining detections
        for d_idx, d_box in enumerate(unmatched_dets):
            if d_idx not in used_cand_dets:
                if self.max_persons is not None and (len(self.confirmed_tracks) + len(self.candidate_tracks)) >= self.max_persons:
                    continue

                # If no one is currently in view, confirm the first student immediately without delay
                if len(self.confirmed_tracks) == 0:
                    new_track = TrackedPerson(
                        track_id=self.next_track_id,
                        label="",
                        bbox=d_box,
                        sequence_length=self.sequence_length
                    )
                    self.confirmed_tracks[self.next_track_id] = new_track
                    self.next_track_id += 1
                else:
                    # Add as a candidate to verify stability across 3 frames
                    cid = f"cand_{self.next_track_id}"
                    self.candidate_tracks[cid] = {'bbox': d_box, 'hits': 1, 'disappeared': 0}
                    self.next_track_id += 1

        self._reassign_labels()
        return self.confirmed_tracks
