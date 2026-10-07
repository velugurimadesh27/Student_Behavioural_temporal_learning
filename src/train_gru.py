import os
import random
import numpy as np

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

# ============================================================
# 0. Reproducibility
# ============================================================

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

set_seed(42)

# ============================================================
# 1. Paths
# ============================================================

FEATURE_DIR = "dataset/features"
RESULT_DIR = "results"
MODEL_DIR = "models"

# ============================================================
# 2. Behaviour classes
# ============================================================

classes = [
    "Head_Down",
    "Looking_Away",
    "Looking_Toward",
    "Writing"
]

# ============================================================
# 3. Settings
# ============================================================

# At 5 FPS, sequence_length = 10 corresponds to 2.0 seconds of observable behavior.
SEQUENCE_LENGTH = 10
BATCH_SIZE = 16
NUM_EPOCHS = 20
LEARNING_RATE = 0.001
INPUT_SIZE = 512
HIDDEN_SIZE = 128
NUM_LAYERS = 1
NUM_CLASSES = len(classes)

# ============================================================
# 4. Load video features
# ============================================================

sequences = []
labels = []
groups = []

print("Loading video features for GRU...")

for label, behaviour in enumerate(classes):
    behaviour_folder = os.path.join(FEATURE_DIR, behaviour)
    for video_folder in sorted(os.listdir(behaviour_folder)):
        video_path = os.path.join(behaviour_folder, video_folder)
        if not os.path.isdir(video_path):
            continue

        feature_file = os.path.join(video_path, "features.npy")
        if not os.path.exists(feature_file):
            continue

        features = np.load(feature_file)
        num_frames = len(features)

        for start in range(0, num_frames - SEQUENCE_LENGTH + 1):
            end = start + SEQUENCE_LENGTH
            sequences.append(features[start:end])
            labels.append(label)
            groups.append(video_folder)

X = np.array(sequences, dtype=np.float32)
y = np.array(labels, dtype=np.int64)
groups = np.array(groups)

print("Total sequences:", len(X))
print("Sequence shape:", X.shape)

# ============================================================
# 5. GRU Model
# ============================================================

class GRUClassifier(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes):
        super().__init__()
        self.gru = nn.GRU(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True
        )
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        output, hidden = self.gru(x)
        last_output = output[:, -1, :]
        return self.fc(last_output)

# ============================================================
# 6. Dataset class
# ============================================================

class SequenceDataset(Dataset):
    def __init__(self, X, y):
        self.X = X
        self.y = y

    def __len__(self):
        return len(self.X)

    def __getitem__(self, index):
        return self.X[index], self.y[index]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Device:", device)

# ============================================================
# 7. Leave-One-Video-Out Evaluation
# ============================================================

logo = LeaveOneGroupOut()
splits = list(logo.split(X, y, groups))

fold_accuracies = []
all_predictions = []
all_true_labels = []
fold_test_videos = []

print(f"\nRunning {len(splits)}-Fold Leave-One-Video-Out with GRU...")

for fold_number, (train_index, test_index) in enumerate(splits, start=1):
    test_video = groups[test_index[0]]
    test_label = classes[y[test_index[0]]]

    train_loader = DataLoader(
        SequenceDataset(torch.tensor(X[train_index]), torch.tensor(y[train_index])),
        batch_size=BATCH_SIZE,
        shuffle=True
    )
    test_loader = DataLoader(
        SequenceDataset(torch.tensor(X[test_index]), torch.tensor(y[test_index])),
        batch_size=BATCH_SIZE,
        shuffle=False
    )

    model = GRUClassifier(
        input_size=INPUT_SIZE,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        num_classes=NUM_CLASSES
    ).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    for epoch in range(NUM_EPOCHS):
        model.train()
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()

    model.eval()
    fold_preds = []
    fold_targets = []
    with torch.no_grad():
        for batch_X, batch_y in test_loader:
            batch_X = batch_X.to(device)
            outputs = model(batch_X)
            _, predicted = torch.max(outputs, 1)
            fold_preds.extend(predicted.cpu().numpy())
            fold_targets.extend(batch_y.numpy())

    acc = accuracy_score(fold_targets, fold_preds) * 100
    fold_accuracies.append(acc)
    fold_test_videos.append(test_video)
    all_predictions.extend(fold_preds)
    all_true_labels.extend(fold_targets)

    print(f"Fold {fold_number:2d} | Test Video: {test_video:20} ({test_label:14}) -> Accuracy: {acc:6.2f}%")

    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(MODEL_DIR, f"gru_fold{fold_number}.pth"))

# ============================================================
# 8. Results Summary
# ============================================================

mean_accuracy = np.mean(fold_accuracies)
std_accuracy = np.std(fold_accuracies)

print("\n====================================")
print("FINAL GRU 10-FOLD RESULTS")
print("====================================")
print(f"Mean Accuracy:      {mean_accuracy:.2f}%")
print(f"Standard Deviation: {std_accuracy:.2f}%\n")

report = classification_report(
    all_true_labels,
    all_predictions,
    labels=list(range(NUM_CLASSES)),
    target_names=classes,
    zero_division=0
)
print(report)

cm = confusion_matrix(
    all_true_labels,
    all_predictions,
    labels=list(range(NUM_CLASSES))
)

os.makedirs(RESULT_DIR, exist_ok=True)
results_file = os.path.join(RESULT_DIR, "gru_10fold_results.txt")
with open(results_file, "w", encoding="utf-8") as f:
    f.write("GRU 10-Fold Leave-One-Video-Out Results\n")
    f.write("=========================================\n\n")
    f.write(f"Sequence length: {SEQUENCE_LENGTH}\n")
    f.write(f"Input feature size: {INPUT_SIZE}\n")
    f.write(f"Hidden size: {HIDDEN_SIZE}\n")
    f.write(f"Epochs: {NUM_EPOCHS}\n\n")
    for i in range(len(fold_accuracies)):
        f.write(f"Fold {i + 1}: {fold_test_videos[i]} -> {fold_accuracies[i]:.2f}%\n")
    f.write(f"\nMean Accuracy: {mean_accuracy:.2f}%\n")
    f.write(f"Standard Deviation: {std_accuracy:.2f}%\n\n")
    f.write("Classification Report\n---------------------\n" + report + "\n\n")
    f.write("Confusion Matrix\n----------------\n" + str(cm) + "\n")

print(f"Results saved to: {results_file}")
