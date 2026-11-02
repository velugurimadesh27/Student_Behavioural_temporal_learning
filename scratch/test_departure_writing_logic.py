import time
import numpy as np

class DepartureAndWritingTester:
    def __init__(self):
        self.writing_score = 0
        self.state = "Looking_Toward"
        self.disappeared = 0
        self.exit_detected = False

    def update(self, has_face, motion_pct, centroid, frame_w=1280):
        cx, cy = centroid

        # 1. Exit / Departure Detection
        # If face is moving towards edge or large body transit occurs (>18% motion)
        is_near_edge = (cx < frame_w * 0.15 or cx > frame_w * 0.85)
        is_large_body_transit = (motion_pct > 18.0)

        if is_large_body_transit or is_near_edge:
            self.exit_detected = True

        if has_face:
            self.disappeared = 0
            self.exit_detected = False
            return "Present (Facing Camera)"

        # Face is NOT visible
        self.disappeared += 1

        # If person showed exit signs and face is gone for > 25 frames (~0.8s) -> Person has left!
        if self.exit_detected and self.disappeared > 25:
            return "Person Left (Seat Vacant)"

        # If person is gone for > 150 frames (~5s) without any face -> Departed
        if self.disappeared > 150:
            return "Person Left (Timeout)"

        # Person is still present (in seat with head down / writing)
        # 2. Writing vs Head Down analysis
        # Writing must be:
        # a) in the realistic writing range: 1.5% <= motion <= 15.0%
        # b) sustained for at least 6 score points (~1.2 seconds)
        if 1.5 <= motion_pct <= 15.0:
            self.writing_score = min(20, self.writing_score + 2)
        else:
            self.writing_score = max(0, self.writing_score - 1)

        is_writing = (self.writing_score >= 6)

        if is_writing:
            return "Writing"
        else:
            return "Head_Down"

if __name__ == "__main__":
    t = DepartureAndWritingTester()

    # Test 1: Sitting and putting head down with slight hand shake (motion = 0.8%)
    print("--- Test 1: Head Down with slight hand shaking (0.8%) ---")
    for i in range(10):
        status = t.update(has_face=False, motion_pct=0.8, centroid=(600, 400))
    print(f"Result after 10 frames of shaking: {status} (writing_score={t.writing_score})")
    assert status == "Head_Down", f"Expected Head_Down, got {status}"

    # Test 2: Active handwriting (motion = 4.5% for 8 frames)
    print("\n--- Test 2: Active handwriting (4.5% motion) ---")
    for i in range(8):
        status = t.update(has_face=False, motion_pct=4.5, centroid=(600, 400))
    print(f"Result after 8 frames of writing: {status} (writing_score={t.writing_score})")
    assert status == "Writing", f"Expected Writing, got {status}"

    # Test 3: Person stands up and leaves (burst of 25% motion as they stand, then face disappears)
    print("\n--- Test 3: Person stands up and leaves ---")
    t.update(has_face=False, motion_pct=25.0, centroid=(600, 200)) # standing up
    for i in range(30):
        status = t.update(has_face=False, motion_pct=0.0, centroid=(600, 200))
    print(f"Result after leaving: {status}")
    assert status == "Person Left (Seat Vacant)", f"Expected Person Left, got {status}"

    print("\nALL 3 LOGIC TESTS PASSED SUCCESSFULLY!")
