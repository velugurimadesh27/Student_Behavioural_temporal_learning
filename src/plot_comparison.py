import os
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# Paths and Setup
# ============================================================
os.makedirs("figures", exist_ok=True)

# 1. Fold Accuracies (LOVO 10 folds)
lstm_folds = [100.0, 100.0, 0.0, 93.14, 100.0, 8.45, 0.0, 0.0, 0.0, 0.0]
gru_folds =  [100.0, 100.0, 0.0, 89.22, 100.0, 0.0,  0.0, 0.0, 0.0, 0.97]
fold_labels = [f"Fold {i+1}" for i in range(10)]
fold_behaviors = [
    "Looking_Toward\n(VID..749)",
    "Looking_Toward\n(VID..908)",
    "Looking_Toward\n(VID..000)",
    "Writing\n(VID..745)",
    "Writing\n(VID..812)",
    "Writing\n(VID..014)",
    "Looking_Away\n(VID..205)",
    "Looking_Away\n(VID..308)",
    "Head_Down\n(VID..424)",
    "Head_Down\n(VID..532)"
]

# ============================================================
# Figure 1: Fold-by-Fold Comparison (LSTM vs GRU)
# ============================================================
x = np.arange(len(fold_labels))
width = 0.35

fig, ax = plt.subplots(figsize=(14, 6))
rects1 = ax.bar(x - width/2, lstm_folds, width, label=f"LSTM (Mean: {np.mean(lstm_folds):.2f}%)", color="#2b5c8f")
rects2 = ax.bar(x + width/2, gru_folds, width, label=f"GRU (Mean: {np.mean(gru_folds):.2f}%)", color="#d95f02")

ax.set_ylabel("Test Video Accuracy (%)", fontsize=12)
ax.set_title("Leave-One-Video-Out (LOVO) Accuracy per Fold: LSTM vs GRU", fontsize=14, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(fold_behaviors, fontsize=9)
ax.set_ylim(0, 115)
ax.grid(axis="y", linestyle="--", alpha=0.6)
ax.legend(fontsize=11)

# Annotate values
for rect in rects1:
    height = rect.get_height()
    if height > 0:
        ax.annotate(f"{height:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8)

for rect in rects2:
    height = rect.get_height()
    if height > 0:
        ax.annotate(f"{height:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8)

plt.tight_layout()
comp_path = "figures/model_comparison_folds.png"
plt.savefig(comp_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"[Saved] Fold comparison chart saved to: {comp_path}")

# ============================================================
# Figure 2: Dataset Class Distribution
# ============================================================
classes = ["Head_Down", "Looking_Away", "Looking_Toward", "Writing"]
frames_per_class = [218, 233, 333, 381]
seqs_per_class = [200, 215, 306, 354]
videos_per_class = [2, 2, 3, 3]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

# Frames bar chart
bars1 = ax1.bar(classes, frames_per_class, color="#386cb0", edgecolor="black")
ax1.set_title("Total Frames per Behavior Class", fontsize=12, fontweight="bold")
ax1.set_ylabel("Frame Count", fontsize=11)
ax1.grid(axis="y", linestyle="--", alpha=0.5)
for bar, v_cnt in zip(bars1, videos_per_class):
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2, yval + 5, f"{yval} frames\n({v_cnt} videos)", ha="center", va="bottom", fontsize=9)
ax1.set_ylim(0, 440)

# Sequences bar chart
bars2 = ax2.bar(classes, seqs_per_class, color="#4daf4a", edgecolor="black")
ax2.set_title("Extracted Sequences (L=10, stride=1)", fontsize=12, fontweight="bold")
ax2.set_ylabel("Sequence Count", fontsize=11)
ax2.grid(axis="y", linestyle="--", alpha=0.5)
for bar in bars2:
    yval = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2, yval + 5, f"{yval} seqs", ha="center", va="bottom", fontsize=9)
ax2.set_ylim(0, 410)

plt.tight_layout()
dist_path = "figures/dataset_distribution.png"
plt.savefig(dist_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"[Saved] Dataset distribution chart saved to: {dist_path}")
