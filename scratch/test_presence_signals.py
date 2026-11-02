import cv2
import numpy as np

def test_presence_signals(video_path):
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return
    
    h, w, _ = frame.shape
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # 1. Edge energy in student desk/torso area
    # In a typical classroom / webcam view, student occupies 0.3*w to 0.7*w, 0.2*h to 0.9*h
    student_roi = gray[int(h*0.2):int(h*0.9), int(w*0.25):int(w*0.75)]
    edges = cv2.Canny(student_roi, 30, 100)
    edge_density = np.count_nonzero(edges) / float(edges.size) * 100.0
    
    # 2. Standard deviation of intensity (texture of clothing, hair vs flat wall/desk)
    std_dev = np.std(student_roi)
    
    # 3. Contour area of foreground objects
    # Threshold dark regions (hair, clothes)
    _, dark_thresh = cv2.threshold(student_roi, 80, 255, cv2.THRESH_BINARY_INV)
    dark_ratio = np.count_nonzero(dark_thresh) / float(student_roi.size) * 100.0
    
    print(f"[{video_path}]")
    print(f"  Edge Density: {edge_density:.2f}%")
    print(f"  Std Dev: {std_dev:.2f}")
    print(f"  Dark Pixels: {dark_ratio:.2f}%")

if __name__ == "__main__":
    test_presence_signals("dataset/raw_videos/Head_Down/VID20260921192424.mp4")
    test_presence_signals("dataset/raw_videos/Head_Down/VID20260921192532.mp4")
    test_presence_signals("dataset/raw_videos/Looking_Toward/VID20260921190749.mp4")
    test_presence_signals("dataset/raw_videos/Looking_Away/VID20260921192205.mp4")
    test_presence_signals("dataset/raw_videos/Writing/VID20260921191745.mp4")
