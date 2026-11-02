import cv2
import numpy as np

def inspect_head_down_frame(video_path):
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("Failed to read", video_path)
        return
    
    h, w, _ = frame.shape
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Try upper body cascade
    upper_path = "models/haarcascade_upperbody.xml"
    upper_cascade = cv2.CascadeClassifier(upper_path)
    small_gray = cv2.resize(gray, (640, int(640 * h / w)))
    
    uppers = upper_cascade.detectMultiScale(small_gray, scaleFactor=1.1, minNeighbors=3, minSize=(50, 50))
    print(f"{video_path}: Upper bodies detected: {len(uppers)}")
    
    # Check edge density and texture in center region
    center_roi = small_gray[int(small_gray.shape[0]*0.2):int(small_gray.shape[0]*0.8), int(small_gray.shape[1]*0.2):int(small_gray.shape[1]*0.8)]
    edges = cv2.Canny(center_roi, 50, 150)
    edge_density = np.count_nonzero(edges) / float(edges.size) * 100.0
    print(f"{video_path}: Center Edge Density: {edge_density:.2f}% | Mean: {np.mean(center_roi):.1f} | Std: {np.std(center_roi):.1f}")

if __name__ == "__main__":
    inspect_head_down_frame("dataset/raw_videos/Head_Down/VID20260921192424.mp4")
    inspect_head_down_frame("dataset/raw_videos/Head_Down/VID20260921192532.mp4")
    inspect_head_down_frame("dataset/raw_videos/Writing/VID20260921191745.mp4")
