import os
import numpy as np

from PIL import Image

import torch
from torchvision import transforms
from torchvision import models


# ============================================================
# 1. Paths
# ============================================================

FRAME_DIR = "dataset/frames"
FEATURE_DIR = "dataset/features"


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
# 4. Device
# ============================================================

device = torch.device(
    "cuda" if torch.cuda.is_available()
    else "cpu"
)

print("Device:", device)


# ============================================================
# 5. Load pretrained ResNet18
# ============================================================

print("\nLoading ResNet18...")

resnet = models.resnet18(weights="DEFAULT")


# Remove the final classification layer
# ResNet18 output will now be 512-dimensional features

resnet.fc = torch.nn.Identity()

resnet = resnet.to(device)

resnet.eval()


print("ResNet18 feature extractor ready.")


# ============================================================
# 6. Create feature directory
# ============================================================

os.makedirs(
    FEATURE_DIR,
    exist_ok=True
)


# ============================================================
# 7. Process all behaviours
# ============================================================

total_frames = 0


for label, behaviour in enumerate(classes):

    behaviour_folder = os.path.join(
        FRAME_DIR,
        behaviour
    )


    feature_behaviour_folder = os.path.join(
        FEATURE_DIR,
        behaviour
    )


    os.makedirs(
        feature_behaviour_folder,
        exist_ok=True
    )


    print("\n====================================")
    print("Processing:", behaviour)
    print("Label:", label)
    print("====================================")


    # --------------------------------------------------------
    # Process each video
    # --------------------------------------------------------

    for video_folder in sorted(
        os.listdir(behaviour_folder)
    ):

        video_path = os.path.join(
            behaviour_folder,
            video_folder
        )


        if not os.path.isdir(video_path):
            continue


        # Folder where features for this video will be saved

        output_video_folder = os.path.join(
            feature_behaviour_folder,
            video_folder
        )


        os.makedirs(
            output_video_folder,
            exist_ok=True
        )


        frame_files = sorted([
            file
            for file in os.listdir(video_path)
            if file.lower().endswith(".jpg")
        ])


        print(
            "\nVideo:",
            video_folder
        )

        print(
            "Frames:",
            len(frame_files)
        )


        video_features = []


        # ----------------------------------------------------
        # Extract feature from every frame
        # ----------------------------------------------------

        for frame_number, frame_file in enumerate(
            frame_files
        ):

            frame_path = os.path.join(
                video_path,
                frame_file
            )


            image = Image.open(
                frame_path
            ).convert("RGB")


            image = transform(
                image
            )


            # Add batch dimension

            image = image.unsqueeze(0)

            image = image.to(device)


            # No gradients needed

            with torch.no_grad():

                feature = resnet(
                    image
                )


            # Convert:
            # [1, 512] → [512]

            feature = feature.squeeze(0)


            feature = feature.cpu().numpy()


            video_features.append(
                feature
            )


            total_frames += 1


            # Progress message

            if (
                (frame_number + 1) % 20 == 0
                or
                frame_number + 1 == len(frame_files)
            ):

                print(
                    f"Processed "
                    f"{frame_number + 1}/"
                    f"{len(frame_files)} frames"
                )


        # ----------------------------------------------------
        # Convert list to NumPy array
        # ----------------------------------------------------

        video_features = np.array(
            video_features,
            dtype=np.float32
        )


        # ----------------------------------------------------
        # Save features
        # ----------------------------------------------------

        output_file = os.path.join(
            output_video_folder,
            "features.npy"
        )


        np.save(
            output_file,
            video_features
        )


        print(
            "Saved:",
            output_file
        )


        print(
            "Feature shape:",
            video_features.shape
        )


# ============================================================
# 8. Finished
# ============================================================

print("\n====================================")
print("Feature extraction completed!")
print("====================================")

print(
    "Total frames processed:",
    total_frames
)

print(
    "Feature size per frame: 512"
)

print(
    "Features saved in:",
    FEATURE_DIR
)