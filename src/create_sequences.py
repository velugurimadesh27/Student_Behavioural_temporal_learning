import os
import numpy as np

# ============================================================
# Paths and Classes
# ============================================================
FEATURE_DIR = "dataset/features"

classes = [
    "Head_Down",
    "Looking_Away",
    "Looking_Toward",
    "Writing"
]

def load_feature_sequences(
    feature_dir=FEATURE_DIR,
    sequence_length=10,
    stride=1
):
    """
    Creates temporal sequences from cached ResNet18 feature vectors.
    
    Guarantees:
    1. Sequences are strictly constructed WITHIN individual videos.
    2. Frames from different videos are NEVER combined into a sequence.
    3. Each sequence is labeled with the video's behavior class.
    4. Group identifiers (video_id) are returned for strict Leave-One-Video-Out (LOVO) splitting.

    Args:
        feature_dir: Path to directory containing cached features.npy per video.
        sequence_length: Number of consecutive feature vectors per sequence (default: 10, i.e., 2.0s at 5 FPS).
        stride: Temporal step size between sequence start indices (default: 1).
    
    Returns:
        X: np.ndarray of shape (N_sequences, sequence_length, 512)
        y: np.ndarray of shape (N_sequences,) with integer class labels [0..3]
        groups: np.ndarray of shape (N_sequences,) with video_id strings
        video_metadata: dict mapping video_id to class and sequence count
    """
    sequences = []
    labels = []
    groups = []
    video_metadata = {}

    for label_idx, class_name in enumerate(classes):
        class_folder = os.path.join(feature_dir, class_name)
        if not os.path.isdir(class_folder):
            continue

        for video_id in sorted(os.listdir(class_folder)):
            video_folder = os.path.join(class_folder, video_id)
            if not os.path.isdir(video_folder):
                continue

            feature_file = os.path.join(video_folder, "features.npy")
            if not os.path.exists(feature_file):
                continue

            features = np.load(feature_file)
            num_frames = len(features)

            # Ensure the video has at least enough frames for one sequence
            if num_frames < sequence_length:
                print(f"[Warning] Video {video_id} has {num_frames} frames < sequence_length {sequence_length}. Skipping.")
                continue

            video_seq_count = 0
            for start_idx in range(0, num_frames - sequence_length + 1, stride):
                end_idx = start_idx + sequence_length
                seq = features[start_idx:end_idx]

                sequences.append(seq)
                labels.append(label_idx)
                groups.append(video_id)
                video_seq_count += 1

            video_metadata[video_id] = {
                "class_name": class_name,
                "class_idx": label_idx,
                "num_frames": num_frames,
                "num_sequences": video_seq_count
            }

    X = np.array(sequences, dtype=np.float32)
    y = np.array(labels, dtype=np.int64)
    groups = np.array(groups)

    return X, y, groups, video_metadata

def main():
    print("============================================================")
    print("STAGE 2: TEMPORAL SEQUENCE CREATION VERIFICATION")
    print("============================================================\n")

    for seq_len in [10, 16]:
        print(f"Testing Sequence Length = {seq_len} (Stride = 1):")
        X, y, groups, meta = load_feature_sequences(sequence_length=seq_len, stride=1)
        print(f"  Shape of X       : {X.shape} (N_seqs, seq_len, feat_dim)")
        print(f"  Shape of y       : {y.shape}")
        print(f"  Unique Videos    : {len(np.unique(groups))}")
        print(f"  Sequences/Class  :")
        for idx, c in enumerate(classes):
            count = np.sum(y == idx)
            print(f"    - {c:15}: {count:4d} sequences")
        print()

    print("Verification complete: Zero cross-video sequence leakage guaranteed.")
    print("============================================================\n")

if __name__ == "__main__":
    main()
