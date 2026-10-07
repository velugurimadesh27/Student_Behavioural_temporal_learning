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
# This captures natural posture/action changes while yielding 1,075 sequences across videos.
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


print("Loading video features...")


for label, behaviour in enumerate(classes):

    behaviour_folder = os.path.join(
        FEATURE_DIR,
        behaviour
    )

    for video_folder in sorted(
        os.listdir(behaviour_folder)
    ):

        video_path = os.path.join(
            behaviour_folder,
            video_folder
        )

        if not os.path.isdir(video_path):
            continue

        feature_file = os.path.join(
            video_path,
            "features.npy"
        )

        if not os.path.exists(feature_file):
            continue

        features = np.load(
            feature_file
        )

        print(
            f"{video_folder}: {features.shape}"
        )

        # ----------------------------------------------------
        # Create temporal sequences
        # ----------------------------------------------------

        num_frames = len(features)

        for start in range(
            0,
            num_frames - SEQUENCE_LENGTH + 1
        ):

            end = start + SEQUENCE_LENGTH

            sequence = features[
                start:end
            ]

            sequences.append(
                sequence
            )

            labels.append(
                label
            )

            groups.append(
                video_folder
            )


# ============================================================
# 5. Convert to NumPy arrays
# ============================================================

X = np.array(
    sequences,
    dtype=np.float32
)

y = np.array(
    labels,
    dtype=np.int64
)

groups = np.array(
    groups
)


print("\n====================================")
print("Sequence dataset created")
print("====================================")

print(
    "Total sequences:",
    len(X)
)

print(
    "Sequence shape:",
    X.shape
)

print(
    "Labels shape:",
    y.shape
)

print(
    "Number of videos:",
    len(np.unique(groups))
)


# ============================================================
# 6. LSTM Model
# ============================================================

class LSTMClassifier(nn.Module):

    def __init__(
        self,
        input_size,
        hidden_size,
        num_layers,
        num_classes
    ):

        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True
        )

        self.fc = nn.Linear(
            hidden_size,
            num_classes
        )

    def forward(self, x):

        output, (hidden, cell) = self.lstm(x)

        # Final time step
        last_output = output[:, -1, :]

        output = self.fc(
            last_output
        )

        return output


# ============================================================
# 7. Dataset class
# ============================================================

class SequenceDataset(Dataset):

    def __init__(
        self,
        X,
        y
    ):

        self.X = X
        self.y = y

    def __len__(self):

        return len(self.X)

    def __getitem__(
        self,
        index
    ):

        return (
            self.X[index],
            self.y[index]
        )


# ============================================================
# 8. Device
# ============================================================

device = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


print(
    "\nDevice:",
    device
)


# ============================================================
# 9. Leave-One-Video-Out
# ============================================================

logo = LeaveOneGroupOut()

splits = list(
    logo.split(
        X,
        y,
        groups
    )
)


print(
    "Total folds:",
    len(splits)
)


# ============================================================
# 10. Storage for final results
# ============================================================

fold_accuracies = []

all_predictions = []

all_true_labels = []

fold_test_videos = []


# ============================================================
# 11. Run all folds
# ============================================================

for fold_number, (
    train_index,
    test_index
) in enumerate(
    splits,
    start=1
):

    print("\n\n")
    print("====================================")
    print(f"FOLD {fold_number}/{len(splits)}")
    print("====================================")


    # --------------------------------------------------------
    # Test video
    # --------------------------------------------------------

    test_video = groups[
        test_index[0]
    ]


    test_label = classes[
        y[test_index[0]]
    ]


    print(
        "Testing video:",
        test_video
    )

    print(
        "Actual behaviour:",
        test_label
    )


    print(
        "Training sequences:",
        len(train_index)
    )

    print(
        "Testing sequences:",
        len(test_index)
    )


    # --------------------------------------------------------
    # Prepare tensors
    # --------------------------------------------------------

    X_train = torch.tensor(
        X[train_index]
    )

    y_train = torch.tensor(
        y[train_index]
    )

    X_test = torch.tensor(
        X[test_index]
    )

    y_test = torch.tensor(
        y[test_index]
    )


    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------

    train_dataset = SequenceDataset(
        X_train,
        y_train
    )

    test_dataset = SequenceDataset(
        X_test,
        y_test
    )


    # --------------------------------------------------------
    # DataLoader
    # --------------------------------------------------------

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False
    )


    # --------------------------------------------------------
    # Create fresh LSTM
    # --------------------------------------------------------

    model = LSTMClassifier(
        input_size=INPUT_SIZE,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        num_classes=NUM_CLASSES
    )


    model = model.to(device)


    # --------------------------------------------------------
    # Loss
    # --------------------------------------------------------

    criterion = nn.CrossEntropyLoss()


    # --------------------------------------------------------
    # Optimizer
    # --------------------------------------------------------

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE
    )


    # --------------------------------------------------------
    # Training
    # --------------------------------------------------------

    print("\nTraining...")


    for epoch in range(
        NUM_EPOCHS
    ):

        model.train()

        running_loss = 0.0

        correct = 0

        total = 0


        for batch_X, batch_y in train_loader:

            batch_X = batch_X.to(device)

            batch_y = batch_y.to(device)


            optimizer.zero_grad()


            outputs = model(
                batch_X
            )


            loss = criterion(
                outputs,
                batch_y
            )


            loss.backward()


            optimizer.step()


            running_loss += (
                loss.item()
                * batch_X.size(0)
            )


            _, predicted = torch.max(
                outputs,
                1
            )


            total += batch_y.size(0)


            correct += (
                predicted == batch_y
            ).sum().item()


        epoch_loss = (
            running_loss / total
        )


        epoch_accuracy = (
            correct / total
        ) * 100


        # Print only selected epochs
        # to keep the output readable

        if (
            epoch == 0
            or
            epoch == 4
            or
            epoch == 9
            or
            epoch == 14
            or
            epoch == 19
        ):

            print(
                f"Epoch {epoch + 1}/{NUM_EPOCHS} | "
                f"Loss: {epoch_loss:.4f} | "
                f"Accuracy: {epoch_accuracy:.2f}%"
            )


    # --------------------------------------------------------
    # Testing
    # --------------------------------------------------------

    model.eval()


    fold_predictions = []

    fold_true_labels = []


    with torch.no_grad():

        for batch_X, batch_y in test_loader:

            batch_X = batch_X.to(device)


            outputs = model(
                batch_X
            )


            _, predicted = torch.max(
                outputs,
                1
            )


            fold_predictions.extend(
                predicted.cpu().numpy()
            )


            fold_true_labels.extend(
                batch_y.numpy()
            )


    # --------------------------------------------------------
    # Fold accuracy
    # --------------------------------------------------------

    fold_accuracy = accuracy_score(
        fold_true_labels,
        fold_predictions
    )


    fold_accuracy_percent = (
        fold_accuracy * 100
    )


    print(
        "\nFold Test Accuracy:",
        f"{fold_accuracy_percent:.2f}%"
    )


    # --------------------------------------------------------
    # Store results
    # --------------------------------------------------------

    fold_accuracies.append(
        fold_accuracy_percent
    )


    fold_test_videos.append(
        test_video
    )


    all_predictions.extend(
        fold_predictions
    )


    all_true_labels.extend(
        fold_true_labels
    )


    # --------------------------------------------------------
    # Save fold model
    # --------------------------------------------------------

    os.makedirs(
        MODEL_DIR,
        exist_ok=True
    )


    model_path = os.path.join(
        MODEL_DIR,
        f"lstm_fold{fold_number}.pth"
    )


    torch.save(
        model.state_dict(),
        model_path
    )


    print(
        "Saved model:",
        model_path
    )


# ============================================================
# 12. Overall results
# ============================================================

print("\n\n")
print("====================================")
print("FINAL 10-FOLD RESULTS")
print("====================================")


for i in range(
    len(fold_accuracies)
):

    print(
        f"Fold {i + 1}: "
        f"{fold_test_videos[i]} -> "
        f"{fold_accuracies[i]:.2f}%"
    )


# ============================================================
# 13. Mean and standard deviation
# ============================================================

mean_accuracy = np.mean(
    fold_accuracies
)

std_accuracy = np.std(
    fold_accuracies
)


print("\n------------------------------------")

print(
    f"Mean Accuracy: "
    f"{mean_accuracy:.2f}%"
)

print(
    f"Standard Deviation: "
    f"{std_accuracy:.2f}%"
)


# ============================================================
# 14. Overall classification report
# ============================================================

print("\n====================================")
print("OVERALL CLASSIFICATION REPORT")
print("====================================")


report = classification_report(
    all_true_labels,
    all_predictions,
    labels=list(range(NUM_CLASSES)),
    target_names=classes,
    zero_division=0
)


print(report)


# ============================================================
# 15. Confusion Matrix
# ============================================================

print("====================================")
print("CONFUSION MATRIX")
print("====================================")


cm = confusion_matrix(
    all_true_labels,
    all_predictions,
    labels=list(range(NUM_CLASSES))
)


print("\nRows = Actual")
print("Columns = Predicted\n")


print(
    "              ",
    classes[0],
    classes[1],
    classes[2],
    classes[3]
)


for i in range(
    NUM_CLASSES
):

    print(
        f"{classes[i]:16}",
        cm[i]
    )


# ============================================================
# 16. Save results
# ============================================================

os.makedirs(
    RESULT_DIR,
    exist_ok=True
)


results_file = os.path.join(
    RESULT_DIR,
    "lstm_10fold_results.txt"
)


with open(
    results_file,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        "LSTM 10-Fold Leave-One-Video-Out Results\n"
    )

    file.write(
        "=========================================\n\n"
    )


    file.write(
        f"Sequence length: {SEQUENCE_LENGTH}\n"
    )

    file.write(
        f"Input feature size: {INPUT_SIZE}\n"
    )

    file.write(
        f"Hidden size: {HIDDEN_SIZE}\n"
    )

    file.write(
        f"Epochs: {NUM_EPOCHS}\n\n"
    )


    for i in range(
        len(fold_accuracies)
    ):

        file.write(
            f"Fold {i + 1}: "
            f"{fold_test_videos[i]} -> "
            f"{fold_accuracies[i]:.2f}%\n"
        )


    file.write(
        f"\nMean Accuracy: "
        f"{mean_accuracy:.2f}%\n"
    )


    file.write(
        f"Standard Deviation: "
        f"{std_accuracy:.2f}%\n"
    )


    file.write(
        "\nClassification Report\n"
    )

    file.write(
        "---------------------\n"
    )

    file.write(
        report
    )


    file.write(
        "\nConfusion Matrix\n"
    )

    file.write(
        "----------------\n"
    )

    file.write(
        str(cm)
    )


print(
    "\nResults saved to:",
    results_file
)

# Save evaluation arrays for plotting and error analysis
eval_data_file = os.path.join(
    RESULT_DIR,
    "lstm_eval_data.npz"
)

np.savez(
    eval_data_file,
    predictions=np.array(all_predictions),
    true_labels=np.array(all_true_labels),
    confusion_matrix=cm,
    fold_accuracies=np.array(fold_accuracies),
    fold_test_videos=np.array(fold_test_videos),
    classes=np.array(classes)
)

print(
    "Evaluation data saved to:",
    eval_data_file
)


# ============================================================
# 17. Finished
# ============================================================

print("\n====================================")
print("ALL 10 FOLDS COMPLETED!")
print("====================================")