import os

from PIL import Image

import torch
from torch.utils.data import Dataset, DataLoader

from torchvision import transforms
from torchvision import models

from sklearn.model_selection import LeaveOneGroupOut


# ============================================================
# 1. Dataset location
# ============================================================

FRAME_DIR = "dataset/frames"


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
# 3. Image preprocessing
# ============================================================

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


# ============================================================
# 4. Dataset class
# ============================================================

class BehaviourDataset(Dataset):

    def __init__(self, frame_paths, labels, transform=None):

        self.frame_paths = frame_paths
        self.labels = labels
        self.transform = transform

    def __len__(self):

        return len(self.frame_paths)

    def __getitem__(self, index):

        image_path = self.frame_paths[index]
        label = self.labels[index]

        image = Image.open(image_path).convert("RGB")

        if self.transform:
            image = self.transform(image)

        return image, label


# ============================================================
# 5. Collect all frames
# ============================================================

frame_paths = []
labels = []
groups = []


for label, behaviour in enumerate(classes):

    behaviour_folder = os.path.join(
        FRAME_DIR,
        behaviour
    )

    for video_folder in os.listdir(behaviour_folder):

        video_path = os.path.join(
            behaviour_folder,
            video_folder
        )

        if not os.path.isdir(video_path):
            continue

        for frame_name in os.listdir(video_path):

            if frame_name.lower().endswith(".jpg"):

                frame_path = os.path.join(
                    video_path,
                    frame_name
                )

                frame_paths.append(frame_path)
                labels.append(label)
                groups.append(video_folder)


print("Total frames:", len(frame_paths))


# ============================================================
# 6. Leave-One-Video-Out
# ============================================================

logo = LeaveOneGroupOut()

splits = list(
    logo.split(
        frame_paths,
        labels,
        groups
    )
)


print(
    "Total folds:",
    len(splits)
)


# ============================================================
# 7. Store results
# ============================================================

fold_results = []


# ============================================================
# 8. Run every fold
# ============================================================

for fold_number, (train_index, test_index) in enumerate(
    splits,
    start=1
):

    print("\n")
    print("====================================")
    print(f"FOLD {fold_number}/10")
    print("====================================")

    print(
        "Training frames:",
        len(train_index)
    )

    print(
        "Testing frames:",
        len(test_index)
    )

    test_video = groups[test_index[0]]

    print(
        "Testing video:",
        test_video
    )


    # ========================================================
    # Create train/test data
    # ========================================================

    train_paths = [
        frame_paths[i]
        for i in train_index
    ]

    train_labels = [
        labels[i]
        for i in train_index
    ]

    test_paths = [
        frame_paths[i]
        for i in test_index
    ]

    test_labels = [
        labels[i]
        for i in test_index
    ]


    train_dataset = BehaviourDataset(
        train_paths,
        train_labels,
        transform
    )

    test_dataset = BehaviourDataset(
        test_paths,
        test_labels,
        transform
    )


    train_loader = DataLoader(
        train_dataset,
        batch_size=16,
        shuffle=True
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=16,
        shuffle=False
    )


    # ========================================================
    # Load new ResNet18 for this fold
    # ========================================================

    print("\nLoading ResNet18...")

    model = models.resnet18(weights="DEFAULT")


    # Freeze pretrained layers

    for parameter in model.parameters():

        parameter.requires_grad = False


    # Replace final layer

    model.fc = torch.nn.Linear(
        model.fc.in_features,
        len(classes)
    )


    device = torch.device(
        "cuda" if torch.cuda.is_available()
        else "cpu"
    )

    model = model.to(device)


    # ========================================================
    # Loss and optimizer
    # ========================================================

    criterion = torch.nn.CrossEntropyLoss()

    optimizer = torch.optim.Adam(
        model.fc.parameters(),
        lr=0.001
    )


    # ========================================================
    # Training
    # ========================================================

    num_epochs = 5


    for epoch in range(num_epochs):

        model.train()

        running_loss = 0.0
        correct = 0
        total = 0


        for images, batch_labels in train_loader:

            images = images.to(device)
            batch_labels = batch_labels.to(device)


            optimizer.zero_grad()


            outputs = model(images)


            loss = criterion(
                outputs,
                batch_labels
            )


            loss.backward()


            optimizer.step()


            running_loss += (
                loss.item() * images.size(0)
            )


            _, predicted = torch.max(
                outputs,
                1
            )


            total += batch_labels.size(0)


            correct += (
                predicted == batch_labels
            ).sum().item()


        epoch_loss = (
            running_loss / total
        )


        epoch_accuracy = (
            correct / total
        ) * 100


        print(
            f"Epoch {epoch + 1}/5 | "
            f"Loss: {epoch_loss:.4f} | "
            f"Accuracy: {epoch_accuracy:.2f}%"
        )


    # ========================================================
    # Testing
    # ========================================================

    model.eval()

    correct = 0
    total = 0


    with torch.no_grad():

        for images, batch_labels in test_loader:

            images = images.to(device)
            batch_labels = batch_labels.to(device)


            outputs = model(images)


            _, predicted = torch.max(
                outputs,
                1
            )


            total += batch_labels.size(0)


            correct += (
                predicted == batch_labels
            ).sum().item()


    test_accuracy = (
        correct / total
    ) * 100


    print(
        f"\nFold {fold_number} Test Accuracy: "
        f"{test_accuracy:.2f}%"
    )


    print(
        f"Correct: {correct}/{total}"
    )


    # ========================================================
    # Save result
    # ========================================================

    fold_results.append(
        (
            fold_number,
            test_video,
            total,
            correct,
            test_accuracy
        )
    )


# ============================================================
# 9. Print final results
# ============================================================

print("\n")
print("====================================")
print("FINAL CNN RESULTS")
print("====================================")


total_correct = 0
total_test_frames = 0


for result in fold_results:

    fold_number = result[0]
    video = result[1]
    total = result[2]
    correct = result[3]
    accuracy = result[4]


    print(
        f"Fold {fold_number}: "
        f"{video} | "
        f"{accuracy:.2f}%"
    )


    total_correct += correct
    total_test_frames += total


overall_accuracy = (
    total_correct / total_test_frames
) * 100


print("\n====================================")

print(
    "Overall frame-level accuracy:",
    f"{overall_accuracy:.2f}%"
)

print(
    "Total correct:",
    total_correct
)

print(
    "Total test frames:",
    total_test_frames
)

print("====================================")


# ============================================================
# 10. Save results
# ============================================================

os.makedirs(
    "results",
    exist_ok=True
)


results_file = "results/cnn_results.txt"


with open(results_file, "w") as file:

    file.write("CNN Leave-One-Video-Out Results\n")
    file.write("====================================\n\n")


    for result in fold_results:

        fold_number = result[0]
        video = result[1]
        total = result[2]
        correct = result[3]
        accuracy = result[4]


        file.write(
            f"Fold {fold_number}: "
            f"{video} | "
            f"Accuracy: {accuracy:.2f}% | "
            f"Correct: {correct}/{total}\n"
        )


    file.write("\n")

    file.write(
        f"Overall frame-level accuracy: "
        f"{overall_accuracy:.2f}%\n"
    )

    file.write(
        f"Total correct: "
        f"{total_correct}\n"
    )

    file.write(
        f"Total test frames: "
        f"{total_test_frames}\n"
    )


print(
    "\nResults saved to:",
    results_file
)