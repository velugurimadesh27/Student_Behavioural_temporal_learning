# Temporal Learning-Engagement Profiling from Classroom Videos

A deep learning project to analyze classroom video sequences and classify observable student learning and visual engagement behaviors using spatial-temporal modeling.

---

## 1. Project Overview & Scope

The system observes physical, visual engagement behaviors in classroom environments using:
1. **Spatial Representation:** ImageNet-pretrained **ResNet18** extracts 512-dimensional spatial feature representations from individual video frames.
2. **Temporal Modeling:** Recurrent Neural Networks (**LSTM** and **GRU**) model temporal transitions across consecutive frames.

### Important Boundary: Observable Behaviors Only
This project makes claims strictly based on **observable classroom behaviors**. It does **not** infer internal psychological states, emotions, concentration levels, intelligence, or mental states.

The four behavior classes are:
- `Head_Down`: Student posture oriented downward toward the desk or lap.
- `Looking_Away`: Student gaze visually oriented away from the instructional focus.
- `Looking_Toward`: Student gaze oriented toward the instructional area, teacher, or whiteboard.
- `Writing`: Student actively engaged in note-taking or hand activity on paper/desk.

---

## 2. System Architecture

```text
               CLASSROOM VIDEO
                     │
                     ▼
          Frame Extraction (5 FPS, 224x224)
                     │
                     ▼
            Pretrained ResNet18
         Spatial Feature Extraction (512-dim)
                     │
                     ▼
       Temporal Feature Sequences (L=10, stride=1)
                     │
                     ▼
             LSTM / GRU Network
          Temporal Sequence Learning
                     │
                     ▼
          Fully Connected Layer (FC)
                     │
                     ▼
         4-Class Observable Prediction
  ┌───────────────┬────────────────┬──────────────┐
  ▼               ▼                ▼              ▼
Head_Down    Looking_Away   Looking_Toward     Writing
```

---

## 3. Dataset & Metadata

The dataset consists of **10 classroom videos** with a total of **1,165 extracted frames** ($224 \times 224$ pixels):

| Video ID | Observable Class | Total Frames | Extracted Sequences ($L=10$) |
| :--- | :--- | :---: | :---: |
| `VID20260921192424` | `Head_Down` | 106 | 97 |
| `VID20260921192532` | `Head_Down` | 112 | 103 |
| `VID20260921192205` | `Looking_Away` | 112 | 103 |
| `VID20260921192308` | `Looking_Away` | 121 | 112 |
| `VID20260921190749` | `Looking_Toward` | 114 | 105 |
| `VID20260921190908` | `Looking_Toward` | 112 | 103 |
| `VID20260921191000` | `Looking_Toward` | 107 | 98 |
| `VID20260921191745` | `Writing` | 111 | 102 |
| `VID20260921191812` | `Writing` | 119 | 110 |
| `VID20260921192014` | `Writing` | 151 | 142 |
| **Total** | **4 Classes** | **1,165** | **1,075** |

- Class frame breakdown: `Head_Down` (218), `Looking_Away` (233), `Looking_Toward` (333), `Writing` (381).
- Metadata files: `dataset/dataset_metadata.csv` (video-level) and `dataset/frame_metadata.csv` (frame-level).

---

## 4. Evaluation Methodology: Zero Data Leakage

To prevent data leakage between neighboring, visually identical frames of the same video:
- Sequences are constructed **strictly within each video** (no cross-video sequences).
- Evaluation is conducted using **Leave-One-Video-Out (LOVO)** cross-validation across all 10 videos.
- In each fold, frames from the held-out test video are **completely excluded** from training.

---

## 5. Experimental Results

### 10-Fold Leave-One-Video-Out Performance

| Fold | Held-Out Test Video | Target Behavior | LSTM Accuracy | GRU Accuracy |
| :---: | :--- | :--- | :---: | :---: |
| **1** | `VID20260921190749` | `Looking_Toward` | **100.00%** | **100.00%** |
| **2** | `VID20260921190908` | `Looking_Toward` | **100.00%** | **100.00%** |
| **3** | `VID20260921191000` | `Looking_Toward` | **0.00%** | **0.00%** |
| **4** | `VID20260921191745` | `Writing` | **93.14%** | **89.22%** |
| **5** | `VID20260921191812` | `Writing` | **100.00%** | **100.00%** |
| **6** | `VID20260921192014` | `Writing` | **8.45%** | **0.00%** |
| **7** | `VID20260921192205` | `Looking_Away` | **0.00%** | **0.00%** |
| **8** | `VID20260921192308` | `Looking_Away` | **0.00%** | **0.00%** |
| **9** | `VID20260921192424` | `Head_Down` | **0.00%** | **0.00%** |
| **10** | `VID20260921192532` | `Head_Down` | **0.00%** | **0.97%** |
| **Summary** | **Mean Accuracy** | | **40.16%** | **39.02%** |
| | **Standard Deviation** | | **47.56%** | **47.68%** |

### Overall Classification Report (LSTM)
| Observable Class | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| `Head_Down` | 0.00 | 0.00 | 0.00 | 200 |
| `Looking_Away` | 0.00 | 0.00 | 0.00 | 215 |
| `Looking_Toward` | **0.95** | **0.68** | **0.79** | 306 |
| `Writing` | **0.42** | **0.61** | **0.50** | 354 |
| **Macro Average** | **0.34** | **0.32** | **0.32** | **1,075** |
| **Weighted Average** | **0.41** | **0.40** | **0.39** | **1,075** |

### Confusion Matrix (LSTM, $N = 1,075$)
```
Actual \ Predicted   Head_Down  Looking_Away  Looking_Toward  Writing
Head_Down               0            78             0           122
Looking_Away           29             0             8           178
Looking_Toward          0            98           208             0
Writing               119            15             3           217
```

---

## 6. Academic Error Analysis & Discussion

1. **Video Scarcity in 2-Video Classes:**
   - `Head_Down` and `Looking_Away` each contain only 2 classroom videos. Under LOVO, when one video is held out for testing, only **one single video** remains in the training set.
   - The temporal model inadvertently memorizes student-specific visual details (clothing, lighting, desk distance) rather than generalized posture dynamics, resulting in 0% test accuracy on the held-out video.
2. **Postural Ambiguity (`Head_Down` vs. `Writing`):**
   - Both actions share downward torso angle and head inclination toward the desk surface.
   - Out of 200 `Head_Down` sequences, 122 (61.0%) were predicted as `Writing`. Out of 354 `Writing` sequences, 119 (33.6%) were predicted as `Head_Down`.
3. **Camera Angle Variation (`Looking_Toward` Fold 3):**
   - Folds 1 and 2 scored 100%, whereas Fold 3 scored 0% (classified as `Looking_Away`). Differences in student angle relative to the instructor displaced the spatial embeddings outside the learned class region.

---

## 7. Execution Guide

Run all pipeline stages directly from the virtual environment:

```powershell
# 1. Dataset inspection and metadata CSV generation
& .\.venv\Scripts\python.exe src/dataset_metadata.py

# 2. Extract spatial features using pretrained ResNet18 (already cached)
& .\.venv\Scripts\python.exe src/extract_features.py

# 3. Verify temporal sequence formation (L=10)
& .\.venv\Scripts\python.exe src/create_sequences.py

# 4. Run 10-Fold Leave-One-Video-Out LSTM training & evaluation
& .\.venv\Scripts\python.exe src/train_lstm.py

# 5. Plot confusion matrix (counts and normalized)
& .\.venv\Scripts\python.exe src/plot_confusion_matrix.py

# 6. Run academic error analysis
& .\.venv\Scripts\python.exe src/error_analysis.py

# 7. (Optional) Run comparative GRU experiment
& .\.venv\Scripts\python.exe src/train_gru.py

# 8. Generate comparative performance and dataset distribution charts
& .\.venv\Scripts\python.exe src/plot_comparison.py

# 9. (Live Demo) Run real-time webcam behavior profiling (Starts in Fullscreen, press 'f' to toggle)
& .\.venv\Scripts\python.exe src/live_webcam_demo.py
```
