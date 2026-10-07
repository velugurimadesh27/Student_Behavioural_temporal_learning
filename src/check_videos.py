import cv2
import os

# Main dataset folder
dataset_path = "dataset/raw_videos"

# Go through each behaviour folder
for behaviour in os.listdir(dataset_path):

    behaviour_path = os.path.join(dataset_path, behaviour)

    # Skip anything that is not a folder
    if not os.path.isdir(behaviour_path):
        continue

    print("\n====================================")
    print("Behaviour:", behaviour)
    print("====================================")

    # Go through videos inside the folder
    for video_name in os.listdir(behaviour_path):

        video_path = os.path.join(behaviour_path, video_name)

        # Only process MP4 videos
        if not video_name.lower().endswith(".mp4"):
            continue

        # Open video
        cap = cv2.VideoCapture(video_path)

        # Get video information
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Calculate duration
        duration = frame_count / fps if fps > 0 else 0

        # File size in MB
        file_size = os.path.getsize(video_path) / (1024 * 1024)

        print("\nVideo:", video_name)
        print("Resolution:", width, "x", height)
        print("FPS:", round(fps, 2))
        print("Frames:", frame_count)
        print("Duration:", round(duration, 2), "seconds")
        print("Size:", round(file_size, 2), "MB")

        cap.release()