import time
import numpy as np
from collections import deque

class TrackedPerson:
    def __init__(self, track_id, label, bbox, sequence_length=10):
        self.track_id = track_id
        self.label = label
        self.bbox = list(bbox)  # [x, y, w, h]
        self.centroid = (bbox[0] + bbox[2] // 2, bbox[1] + bbox[3] // 2)
        self.disappeared = 0
        self.confirmed = True
        self.hit_count = 1

        self.temporal_buffer = deque(maxlen=sequence_length)
        self.current_prediction = "Looking_Toward"
        self.confidence = 85.0
        self.last_face_seen_time = time.time()
        self.is_face_visible = True

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


def clean_and_merge_boxes(boxes, frame_w=1280, min_size=40):
    if len(boxes) == 0:
        return []

    valid_boxes = [b for b in boxes if b[2] >= min_size and b[3] >= min_size]
    if len(valid_boxes) == 0:
        return []

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

            # If overlapping or close proximity of the same head
            is_same_person = (
                iou > 0.10 or
                (dist_x < max(bw, mw) * 1.1 and dist_y < max(bh, mh) * 1.1)
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

    merged = sorted(merged, key=lambda b: b[0])
    return merged


class DynamicPersonTracker:
    def __init__(self, max_disappeared=450, max_distance=180, sequence_length=10, max_persons=10):
        self.next_track_id = 0
        self.confirmed_tracks = {}   # track_id -> TrackedPerson
        self.candidate_tracks = {}   # track_id -> {'bbox': bbox, 'hits': count, 'disappeared': count}
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.sequence_length = sequence_length
        self.max_persons = max_persons

    def _get_label(self, idx):
        if idx < 26:
            return f"Person {chr(65 + idx)}"
        return f"Person {idx + 1}"

    def _reassign_labels(self):
        if len(self.confirmed_tracks) == 0:
            return
        sorted_tracks = sorted(self.confirmed_tracks.values(), key=lambda t: t.centroid[0])
        for idx, track in enumerate(sorted_tracks):
            track.label = self._get_label(idx)

    def update(self, raw_bboxes, frame_w=1280):
        clean_bboxes = clean_and_merge_boxes(raw_bboxes, frame_w=frame_w)
        if self.max_persons and len(clean_bboxes) > self.max_persons:
            clean_bboxes = sorted(clean_bboxes, key=lambda b: b[2] * b[3], reverse=True)[:self.max_persons]

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

        # Unmatched confirmed tracks (head down / face hidden)
        for idx, tid in enumerate(track_ids):
            if idx not in matched_track_ids:
                track = self.confirmed_tracks[tid]
                track.disappeared += 1
                track.is_face_visible = False
                if track.disappeared > self.max_disappeared:
                    del self.confirmed_tracks[tid]

        # Remaining detections: either register immediately (if scene empty) or check candidate confirmation
        unmatched_dets = [clean_bboxes[i] for i in range(len(clean_bboxes)) if i not in used_det_indices]

        # Update existing candidate tracks
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

                    # Confirmed if observed for 3 frames!
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
                    del self.candidate_tracks[cid]

        # New detections that didn't match candidates
        for d_idx, d_box in enumerate(unmatched_dets):
            if d_idx not in used_cand_dets:
                if self.max_persons is not None and (len(self.confirmed_tracks) + len(self.candidate_tracks)) >= self.max_persons:
                    continue

                # If no one is currently confirmed, confirm the first student immediately without delay!
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
                    # New candidate student
                    cid = f"cand_{self.next_track_id}"
                    self.candidate_tracks[cid] = {'bbox': d_box, 'hits': 1, 'disappeared': 0}
                    self.next_track_id += 1

        self._reassign_labels()
        return self.confirmed_tracks

# Run verification test
if __name__ == "__main__":
    t = DynamicPersonTracker(max_persons=5)
    # Frame 1: Person 1 enters
    res = t.update([(200, 100, 80, 80)])
    print("Frame 1 (1 student):", [p.label for p in res.values()])

    # Frame 2: Person 2 enters at x=700 (hits=1)
    res = t.update([(200, 100, 80, 80), (700, 100, 80, 80)])
    print("Frame 2:", [p.label for p in res.values()])

    # Frame 3: Person 2 still there (hits=2)
    res = t.update([(200, 100, 80, 80), (700, 100, 80, 80)])
    print("Frame 3:", [p.label for p in res.values()])

    # Frame 4: Person 2 confirmed (hits=3)
    res = t.update([(200, 100, 80, 80), (700, 100, 80, 80)])
    print("Frame 4 (2 students):", [p.label for p in res.values()])

    # Frame 5: Person 3 enters at x=1000 for 3 frames
    t.update([(200, 100, 80, 80), (700, 100, 80, 80), (1000, 100, 80, 80)])
    t.update([(200, 100, 80, 80), (700, 100, 80, 80), (1000, 100, 80, 80)])
    res = t.update([(200, 100, 80, 80), (700, 100, 80, 80), (1000, 100, 80, 80)])
    print("Frame 7 (3 students):", [p.label for p in res.values()])

    # Frame 8: Single glitch detection appears for 1 frame at x=400
    res = t.update([(200, 100, 80, 80), (400, 100, 80, 80), (700, 100, 80, 80), (1000, 100, 80, 80)])
    print("Frame 8 (with 1-frame glitch at 400):", [p.label for p in res.values()])

    # Frame 9: Glitch gone
    res = t.update([(200, 100, 80, 80), (700, 100, 80, 80), (1000, 100, 80, 80)])
    print("Frame 9 (glitch disappeared, strictly 3 students):", [p.label for p in res.values()])
