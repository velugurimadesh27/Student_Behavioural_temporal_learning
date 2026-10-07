import os
import csv
from PIL import Image

# ============================================================
# Paths and Classes
# ============================================================
RAW_VIDEO_DIR = "dataset/raw_videos"
FRAME_DIR = "dataset/frames"
FEATURE_DIR = "dataset/features"
OUTPUT_METADATA_CSV = "dataset/dataset_metadata.csv"
OUTPUT_FRAME_METADATA_CSV = "dataset/frame_metadata.csv"

classes = [
    "Head_Down",
    "Looking_Away",
    "Looking_Toward",
    "Writing"
]

def main():
    print("============================================================")
    print("STAGE 1 & 2: DATASET INSPECTION & METADATA PREPARATION")
    print("============================================================\n")

    # ------------------------------------------------------------
    # 1. Collect Video-Level and Frame-Level Information
    # ------------------------------------------------------------
    video_summary = []
    frame_records = []
    class_frame_counts = {c: 0 for c in classes}
    total_frames = 0
    all_resolutions = set()

    for class_idx, class_name in enumerate(classes):
        class_folder = os.path.join(FRAME_DIR, class_name)
        if not os.path.isdir(class_folder):
            continue

        video_folders = sorted(os.listdir(class_folder))
        for video_id in video_folders:
            video_path = os.path.join(class_folder, video_id)
            if not os.path.isdir(video_path):
                continue

            frame_files = sorted([
                f for f in os.listdir(video_path)
                if f.lower().endswith((".jpg", ".png"))
            ])

            frame_count = len(frame_files)
            class_frame_counts[class_name] += frame_count
            total_frames += frame_count

            # Check image dimensions on the first frame
            if frame_files:
                sample_path = os.path.join(video_path, frame_files[0])
                with Image.open(sample_path) as img:
                    all_resolutions.add(img.size)

            # Check if cached features exist
            feat_path = os.path.join(FEATURE_DIR, class_name, video_id, "features.npy")
            features_cached = os.path.exists(feat_path)

            video_summary.append({
                "video_id": video_id,
                "class_name": class_name,
                "class_idx": class_idx,
                "frame_count": frame_count,
                "features_cached": features_cached
            })

            # Frame-level records
            for frame_idx, frame_name in enumerate(frame_files):
                frame_rel_path = os.path.join(video_path, frame_name)
                frame_records.append({
                    "video_id": video_id,
                    "class": class_name,
                    "class_idx": class_idx,
                    "frame_index": frame_idx,
                    "frame_path": frame_rel_path
                })

    # ------------------------------------------------------------
    # 2. Print Stage 1 Inspection Results
    # ------------------------------------------------------------
    print(f"Total Videos: {len(video_summary)}")
    print(f"Total Frames: {total_frames}")
    print(f"Classes ({len(classes)}): {', '.join(classes)}")
    print(f"Observed Frame Dimensions: {list(all_resolutions)}\n")

    print("------------------------------------------------------------")
    print("Frames Per Class:")
    print("------------------------------------------------------------")
    for class_name in classes:
        print(f"  {class_name:16}: {class_frame_counts[class_name]:4d} frames")
    print()

    print("------------------------------------------------------------")
    print("Frames Per Video (Video-Level Details):")
    print("------------------------------------------------------------")
    header = f"{'Video ID':20} | {'Class':15} | {'Frames':6} | {'ResNet18 Cached':15}"
    print(header)
    print("-" * len(header))
    for row in video_summary:
        cached_str = "Yes (512-dim)" if row["features_cached"] else "No"
        print(f"{row['video_id']:20} | {row['class_name']:15} | {row['frame_count']:6d} | {cached_str:15}")
    print()

    # ------------------------------------------------------------
    # 3. Save Metadata Files (Stage 2)
    # ------------------------------------------------------------
    # Save video metadata
    os.makedirs(os.path.dirname(OUTPUT_METADATA_CSV), exist_ok=True)
    with open(OUTPUT_METADATA_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "class_name", "class_idx", "frame_count", "features_cached"])
        writer.writeheader()
        writer.writerows(video_summary)
    print(f"[Saved] Video-level metadata saved to: {OUTPUT_METADATA_CSV}")

    # Save frame-level metadata
    with open(OUTPUT_FRAME_METADATA_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "class", "class_idx", "frame_index", "frame_path"])
        writer.writeheader()
        writer.writerows(frame_records)
    print(f"[Saved] Frame-level metadata saved to: {OUTPUT_FRAME_METADATA_CSV}")
    print(f"        Total indexed frame records: {len(frame_records)}\n")

    # ------------------------------------------------------------
    # 4. Sequence Formation Analysis (Stage 2 Preview)
    # ------------------------------------------------------------
    print("------------------------------------------------------------")
    print("Temporal Sequence Analysis (Within-Video Only):")
    print("------------------------------------------------------------")
    for seq_len in [10, 16]:
        total_seqs = sum(max(0, row["frame_count"] - seq_len + 1) for row in video_summary)
        print(f"Sequence Length = {seq_len:2d} (stride=1): Total sequences = {total_seqs}")
    print("============================================================\n")

if __name__ == "__main__":
    main()
