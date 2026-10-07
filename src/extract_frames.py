import cv2
import os

# Folders
input_folder = "dataset/raw_videos"
output_folder = "dataset/frames"

# Frames to extract per second
target_fps = 5

# Image size for CNN
image_size = (224, 224)


# Go through each behaviour folder
for behaviour in os.listdir(input_folder):

    behaviour_path = os.path.join(input_folder, behaviour)

    if not os.path.isdir(behaviour_path):
        continue

    # Create corresponding output folder
    output_behaviour_path = os.path.join(output_folder, behaviour)
    os.makedirs(output_behaviour_path, exist_ok=True)

    print("\n====================================")
    print("Processing:", behaviour)
    print("====================================")

    # Go through videos
    for video_name in os.listdir(behaviour_path):

        if not video_name.lower().endswith(".mp4"):
            continue

        video_path = os.path.join(behaviour_path, video_name)

        # Create folder for this video's frames
        video_id = os.path.splitext(video_name)[0]

        video_output_folder = os.path.join(
            output_behaviour_path,
            video_id
        )

        os.makedirs(video_output_folder, exist_ok=True)

        # Open video
        cap = cv2.VideoCapture(video_path)

        original_fps = cap.get(cv2.CAP_PROP_FPS)

        # How many original frames to skip
        frame_interval = max(1, int(original_fps / target_fps))

        frame_number = 0
        saved_count = 0

        print("\nVideo:", video_name)

        while True:

            ret, frame = cap.read()

            if not ret:
                break

            # Save approximately 5 frames per second
            if frame_number % frame_interval == 0:

                # Resize frame
                resized_frame = cv2.resize(
                    frame,
                    image_size
                )

                # Create filename
                frame_name = f"frame_{saved_count:04d}.jpg"

                frame_path = os.path.join(
                    video_output_folder,
                    frame_name
                )

                # Save frame
                cv2.imwrite(
                    frame_path,
                    resized_frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 90]
                )

                saved_count += 1

            frame_number += 1

        cap.release()

        print("Frames saved:", saved_count)

print("\n====================================")
print("Frame extraction completed!")
print("====================================")