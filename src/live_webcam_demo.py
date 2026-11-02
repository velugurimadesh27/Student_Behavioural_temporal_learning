import os
import sys
import argparse

try:
    from src.multi_person_profiler import run_multi_person_profiler
except ModuleNotFoundError:
    from multi_person_profiler import run_multi_person_profiler

def run_live_webcam(camera_index=0, max_persons=10, sequence_length=10, sample_fps=5,
                    motion_threshold=1.50, start_fullscreen=True):
    """
    Precision Live Classroom Behavior Profiler.
    Dynamically detects and tracks however many students appear in front of the camera
    (Person A, Person B, Person C, Person D...), profiling Head_Down, Writing,
    Looking_Toward, and Looking_Away for each person independently.
    Detects when a person leaves the camera view, removing them within ~1 second.
    Filters slight hand shaking in Head_Down from being misclassified as Writing.
    """
    run_multi_person_profiler(
        source=camera_index,
        max_persons=max_persons,
        sequence_length=sequence_length,
        sample_fps=sample_fps,
        motion_threshold=motion_threshold,
        start_fullscreen=start_fullscreen
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precision Dynamic Multi-Person Classroom Behavior Profiler.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--max-persons", type=int, default=10, help="Max students to profile dynamically (default: 10)")
    parser.add_argument("--threshold", type=float, default=1.50, help="Motion threshold percent for writing (default: 1.50)")
    parser.add_argument("--seq-len", type=int, default=10, help="Sequence length (default: 10)")
    parser.add_argument("--fps", type=int, default=5, help="Sampling FPS (default: 5)")
    parser.add_argument("--windowed", action="store_true", help="Start in windowed mode instead of fullscreen")
    args = parser.parse_args()

    run_live_webcam(
        camera_index=args.camera,
        max_persons=args.max_persons,
        sequence_length=args.seq_len,
        sample_fps=args.fps,
        motion_threshold=args.threshold,
        start_fullscreen=not args.windowed
    )
