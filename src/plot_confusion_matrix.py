import os
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay

# ============================================================
# 1. Behaviour classes
# ============================================================
classes = [
    "Head_Down",
    "Looking_Away",
    "Looking_Toward",
    "Writing"
]

# ============================================================
# 2. Load confusion matrix from latest experiment
# ============================================================
eval_data_path = "results/lstm_eval_data.npz"

if os.path.exists(eval_data_path):
    data = np.load(eval_data_path)
    cm = data["confusion_matrix"]
    print("Loaded confusion matrix from:", eval_data_path)
else:
    # Fallback to recorded matrix
    cm = np.array([
        [0, 78, 0, 122],
        [29, 0, 8, 178],
        [0, 98, 208, 0],
        [119, 15, 3, 217]
    ])
    print("Using default confusion matrix.")

print("\nConfusion Matrix:")
print(cm)

# ============================================================
# 3. Create figure (Count & Normalized)
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

# Plot raw counts
disp_raw = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=classes
)
disp_raw.plot(
    ax=axes[0],
    cmap="Blues",
    values_format="d",
    xticks_rotation=30
)
axes[0].set_title("LSTM Confusion Matrix (Sample Counts)\n10-Fold Leave-One-Video-Out", fontsize=12)
axes[0].set_xlabel("Predicted Behaviour", fontsize=11)
axes[0].set_ylabel("Actual Behaviour", fontsize=11)

# Plot normalized by true class support (Recall per class)
cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)
cm_norm = np.nan_to_num(cm_norm)

disp_norm = ConfusionMatrixDisplay(
    confusion_matrix=cm_norm,
    display_labels=classes
)
disp_norm.plot(
    ax=axes[1],
    cmap="Blues",
    values_format=".2f",
    xticks_rotation=30
)
axes[1].set_title("LSTM Normalized Confusion Matrix (Proportions)\n10-Fold Leave-One-Video-Out", fontsize=12)
axes[1].set_xlabel("Predicted Behaviour", fontsize=11)
axes[1].set_ylabel("Actual Behaviour", fontsize=11)

plt.tight_layout()

# ============================================================
# 4. Save figure
# ============================================================
os.makedirs("figures", exist_ok=True)
output_path = "figures/lstm_confusion_matrix.png"

plt.savefig(
    output_path,
    dpi=300,
    bbox_inches="tight"
)

print("\nSaved confusion matrix plot to:", output_path)
plt.close(fig)