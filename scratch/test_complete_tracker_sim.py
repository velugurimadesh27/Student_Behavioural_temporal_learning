import time
import numpy as np

class CompleteStudentTrackerTest:
    def __init__(self, frame_w=1280, frame_h=720):
        self.frame_w = frame_w
        self.frame_h = frame_h
        self.writing_score = 0
        self.disappeared = 0
        self.last_centroid = None
        self.is_departing = False
        self.status = "Searching for students..."

    def update(self, face_bbox=None, motion_pct=0.0):
        # 1. If face is detected:
        if face_bbox is not None:
            bx, by, bw, bh = face_bbox
            cx = bx + bw // 2
            cy = by + bh // 2
            
            # Check if student is near frame boundary / walking out
            if cx < self.frame_w * 0.15 or cx > self.frame_w * 0.85 or cy < self.frame_h * 0.15:
                self.is_departing = True
            else:
                self.is_departing = False

            self.last_centroid = (cx, cy)
            self.disappeared = 0
            self.writing_score = 0
            self.status = "Present: Looking_Toward"
            return self.status

        # 2. No face detected this frame:
        self.disappeared += 1

        # Check departure signals:
        # A. Large motion (person standing up / moving out of seat)
        if motion_pct > 16.0:
            self.is_departing = True

        # B. If person was near edge or showed departure motion:
        if self.is_departing and self.disappeared > 20: # ~0.7 seconds
            self.status = "Student Left (Empty Chair)"
            return self.status

        # C. General timeout if completely absent for > 150 frames (~5s)
        if self.disappeared > 150:
            self.status = "Student Left (Timeout)"
            return self.status

        # 3. Person is still in seat with head down / writing
        # Filter slight hand shaking: only count motion if in 1.5% - 15.0% range
        if 1.5 <= motion_pct <= 15.0:
            self.writing_score = min(20, self.writing_score + 2)
        else:
            self.writing_score = max(0, self.writing_score - 1)

        if self.writing_score >= 6:
            self.status = "Writing"
        else:
            self.status = "Head_Down"

        return self.status

if __name__ == "__main__":
    sim = CompleteStudentTrackerTest()

    # Scenario 1: Person sitting, looking toward camera
    for _ in range(5):
        st = sim.update(face_bbox=(500, 200, 100, 100), motion_pct=0.1)
    print("Scenario 1 (Normal face):", st)
    assert "Looking_Toward" in st

    # Scenario 2: Person puts head down quietly (motion = 0.2%)
    for _ in range(15):
        st = sim.update(face_bbox=None, motion_pct=0.2)
    print("Scenario 2 (Head down):", st)
    assert st == "Head_Down"

    # Scenario 3: Hands slightly shaking while head down (motion = 0.9%)
    for _ in range(10):
        st = sim.update(face_bbox=None, motion_pct=0.9)
    print("Scenario 3 (Head down + shaking):", st)
    assert st == "Head_Down", f"Expected Head_Down, got {st}"

    # Scenario 4: Student begins writing notes (motion = 4.2% sustained)
    for _ in range(8):
        st = sim.update(face_bbox=None, motion_pct=4.2)
    print("Scenario 4 (Active writing):", st)
    assert st == "Writing", f"Expected Writing, got {st}"

    # Scenario 5: Student stands up and leaves (burst of 22% motion as they stand, then gone)
    sim.update(face_bbox=None, motion_pct=22.0)
    for _ in range(25):
        st = sim.update(face_bbox=None, motion_pct=0.0)
    print("Scenario 5 (Person leaves):", st)
    assert "Student Left" in st

    print("\nALL 5 SCENARIOS VERIFIED AND PASSED!")
