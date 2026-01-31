import cv2
import numpy as np

class MotionDetector:
    def __init__(self, threshold=25, min_area=500):
        self.cap = cv2.VideoCapture(0)   # 0 = default webcam 
        self.threshold = threshold       # Grayscale difference threshold
        self.min_area  = min_area        # Min contour area to count as motion
        self.prev_frame = None

    def detect(self):
        """Returns True if motion is detected in current frame."""
        ret, frame = self.cap.read()
        if not ret:
            return False

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)  # Reduce noise

        if self.prev_frame is None:
            self.prev_frame = gray
            return False

        # Compute absolute difference between frames
        diff = cv2.absdiff(self.prev_frame, gray)
        _, thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)

        # Find contours (regions of change)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        self.prev_frame = gray

        for contour in contours:
            if cv2.contourArea(contour) > self.min_area:
                return True
        return False

    def release(self):
        self.cap.release()
