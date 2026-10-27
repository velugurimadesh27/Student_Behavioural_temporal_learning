import os
import sys
import argparse

try:
    from src.multi_person_profiler import run_multi_person_profiler
except ModuleNotFoundError:
    from multi_person_profiler import run_multi_person_profiler

def run_live_webcam(camera_index=0, max_persons=1, sequence_length=10, sample_fps=5,
                    motion_threshold=0.80, start_fullscreen=True):
    """
    Precision Live Classroom Behavior Profiler.
    Uses robust face/gaze detection and localized desk/hand motion
    to accurately profile Head_Down, Writing, Looking_Toward, and Looking_Away.
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
    parser = argparse.ArgumentParser(description="Precision Live Classroom Behavior Profiler.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--max-persons", type=int, default=1, help="Max students to profile (default: 1, use 2 for multi-person)")
    parser.add_argument("--threshold", type=float, default=0.80, help="Motion threshold percent for writing (default: 0.80)")
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
