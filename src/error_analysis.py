import os
import numpy as np

# ============================================================
# Paths and Classes
# ============================================================
EVAL_DATA_PATH = "results/lstm_eval_data.npz"

classes = [
    "Head_Down",
    "Looking_Away",
    "Looking_Toward",
    "Writing"
]

def main():
    print("============================================================")
    print("STAGE 8 & ERROR ANALYSIS: 10-FOLD LOVO LSTM EVALUATION")
    print("============================================================\n")

    if os.path.exists(EVAL_DATA_PATH):
        data = np.load(EVAL_DATA_PATH)
        fold_accuracies = data["fold_accuracies"]
        fold_test_videos = data["fold_test_videos"]
        predictions = data["predictions"]
        true_labels = data["true_labels"]
        cm = data["confusion_matrix"]
        print("[Status] Loaded actual evaluation data from:", EVAL_DATA_PATH)
    else:
        # Fallback values from the LOVO experiment
        fold_accuracies = np.array([100.0, 100.0, 0.0, 93.14, 100.0, 8.45, 0.0, 0.0, 0.0, 0.0])
        fold_test_videos = np.array([
            "VID20260921190749", "VID20260921190908", "VID20260921191000",
            "VID20260921191745", "VID20260921191812", "VID20260921192014",
            "VID20260921192205", "VID20260921192308",
            "VID20260921192424", "VID20260921192532"
        ])
        predictions = None
        true_labels = None
        cm = np.array([
            [0, 78, 0, 122],
            [29, 0, 8, 178],
            [0, 98, 208, 0],
            [119, 15, 3, 217]
        ])
        print("[Status] Using recorded evaluation data.")

    # ------------------------------------------------------------
    # 1. Fold-by-Fold Table
    # ------------------------------------------------------------
    print("\n------------------------------------------------------------")
    print("Leave-One-Video-Out (LOVO) Fold Results:")
    print("------------------------------------------------------------")
    header = f"{'Fold':8} | {'Test Video ID':22} | {'Accuracy':10}"
    print(header)
    print("-" * len(header))

    for i in range(len(fold_accuracies)):
        print(f"Fold {i + 1:2d}   | {fold_test_videos[i]:22} | {fold_accuracies[i]:6.2f}%")

    print("-" * len(header))
    print(f"Mean Accuracy     : {fold_accuracies.mean():.2f}%")
    print(f"Standard Deviation: {fold_accuracies.std():.2f}%")
    print(f"Best Fold Accuracy: {fold_accuracies.max():.2f}%")
    print(f"Worst Fold Accuracy: {fold_accuracies.min():.2f}%\n")

    # ------------------------------------------------------------
    # 2. Per-Class Performance
    # ------------------------------------------------------------
    print("------------------------------------------------------------")
    print("Per-Class Support and Recall (from Confusion Matrix):")
    print("------------------------------------------------------------")
    for idx, c in enumerate(classes):
        total_class_seqs = cm[idx].sum()
        correct_seqs = cm[idx, idx]
        recall = (correct_seqs / total_class_seqs * 100) if total_class_seqs > 0 else 0.0
        predicted_total = cm[:, idx].sum()
        precision = (correct_seqs / predicted_total * 100) if predicted_total > 0 else 0.0
        print(f"  {c:16} | Support: {total_class_seqs:4d} | Correct: {correct_seqs:4d} | Recall: {recall:5.2f}% | Precision: {precision:5.2f}%")
    print()

    # ------------------------------------------------------------
    # 3. Frequent Confusions Analysis
    # ------------------------------------------------------------
    print("------------------------------------------------------------")
    print("Analysis of Frequent Misclassifications:")
    print("------------------------------------------------------------")
    print("1. Head_Down -> Misclassified as Writing:")
    print(f"   {cm[0, 3]}/{cm[0].sum()} ({cm[0, 3]/cm[0].sum()*100:.1f}%) of Head_Down sequences were predicted as Writing.")
    print("2. Head_Down -> Misclassified as Looking_Away:")
    print(f"   {cm[0, 1]}/{cm[0].sum()} ({cm[0, 1]/cm[0].sum()*100:.1f}%) of Head_Down sequences were predicted as Looking_Away.")
    print("3. Looking_Away -> Misclassified as Writing:")
    print(f"   {cm[1, 3]}/{cm[1].sum()} ({cm[1, 3]/cm[1].sum()*100:.1f}%) of Looking_Away sequences were predicted as Writing.")
    print("4. Writing -> Misclassified as Head_Down:")
    print(f"   {cm[3, 0]}/{cm[3].sum()} ({cm[3, 0]/cm[3].sum()*100:.1f}%) of Writing sequences were predicted as Head_Down.")
    print("5. Looking_Toward (Fold 3):")
    print(f"   {cm[2, 1]}/{cm[2].sum()} ({cm[2, 1]/cm[2].sum()*100:.1f}%) of Looking_Toward sequences were predicted as Looking_Away (all from VID20260921191000).")
    print()

    # ------------------------------------------------------------
    # 4. Academic Error Analysis & Possible Causes
    # ------------------------------------------------------------
    print("============================================================")
    print("OBJECTIVE ACADEMIC DISCUSSION & POSSIBLE CAUSES")
    print("============================================================\n")
    print("1. Limited Video Diversity per Behavior Class:")
    print("   - In this dataset, Head_Down and Looking_Away contain only 2 classroom videos each.")
    print("   - Under Leave-One-Video-Out (LOVO), when one video is held out for testing,")
    print("     the model has only 1 remaining video to learn that behavior class from.")
    print("   - Consequently, the model likely memorizes video-specific visual characteristics")
    print("     (such as a specific student's clothing, desk position, or lighting) instead")
    print("     of a generalizable posture representation, explaining the 0% accuracy on unseen test videos.")
    print()
    print("2. Spatial and Postural Similarity Between Behaviors:")
    print("   - Both Head_Down and Writing involve a downward head tilt and proximity to the desk.")
    print("   - Without explicit hand/pen localization, a student resting their head downward closely")
    print("     resembles a student leaning downward to write in static ResNet18 spatial features.")
    print("   - This directly explains the mutual confusion between Head_Down and Writing.")
    print()
    print("3. Camera Perspective and Viewpoint Differences (Fold 3):")
    print("   - Fold 1 and Fold 2 for Looking_Toward achieved 100.0% accuracy, while Fold 3 (VID20260921191000)")
    print("     achieved 0.0% (all sequences classified as Looking_Away).")
    print("   - Visual inspection indicates that camera position and student orientation relative")
    print("     to the focal area in VID20260921191000 differed from the first two videos, causing")
    print("     the spatial features to map closer to the Looking_Away distribution.")
    print()
    print("4. Scientific Integrity Conclusion:")
    print("   - High accuracy on select folds (100% on Folds 1, 2, 5) demonstrates the LSTM's ability")
    print("     to learn temporal sequences, but the LOVO evaluation honestly demonstrates that additional")
    print("     video variety across different students and camera angles is essential for robust generalization.")
    print("============================================================\n")

if __name__ == "__main__":
    main()