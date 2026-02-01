import cv2
import numpy as np
from collections import deque

#  Tuning for hand/person scale demo 
# These are all sized for a hand or person moving toward a webcam at ~0.5-2m.
# If detections are too sensitive, raise MIN_CONTOUR_AREA.
# If detections are too sluggish, lower APPROACH_GROWTH_THRESHOLD.

MIN_CONTOUR_AREA        = 200       # Smallest contour we care about (pixels^2).
                                    # A hand at ~1m is roughly 200-800px^2 on a
                                    # standard webcam. Filters out dust/shadows.

HISTORY_SIZE            = 5         # How many frames of contour size we track.
                                    # More = smoother, slower to react.

APPROACH_GROWTH_THRESHOLD = 1.15    # Contour must grow by 15% across the history
                                    # window to count as "approaching." Filters
                                    # out jitter and small movements.

APPROACH_CONFIRM_STREAK = 3         # How many consecutive frames must show growth
                                    # before we confirm something is approaching.
                                    # Prevents a single expanding frame from firing.

MAGNITUDE_THRESHOLD     = 0.3       # Fraction of the frame that must be moving
                                    # to count as significant motion. At 0.3, about
                                    # 30% of the frame needs change. Good for a hand
                                    # filling part of the view.


class MotionDetector:
    def __init__(self, threshold=25):
        self.cap = cv2.VideoCapture(0)
        self.threshold = threshold          # Grayscale pixel diff threshold
        self.prev_frame = None

        # Rolling window of the largest contour area per frame.
        # Used to detect whether an object is approaching.
        self.contour_history = deque(maxlen=HISTORY_SIZE)

        # How many consecutive frames have shown the contour growing.
        self.approach_streak = 0

        # Whether we've confirmed an object is actively approaching.
        self.object_approaching = False

    def detect(self) -> dict:
        """
        Read a frame, find moving regions, score magnitude, and determine
        whether something is approaching the camera.

        Returns a dict instead of a bool so sensor_main can use the detail:
        {
            "motion_detected":   bool,    # True if any significant motion at all
            "magnitude":         float,   # 0.0 to 1.0 — how much of the frame moved
            "largest_contour":   int,     # Pixel area of the biggest moving region
            "object_approaching": bool,   # True if contour is consistently growing
            "approach_confidence": float  # 0.0 to 1.0 — how confident we are it's approaching
        }
        """
        ret, frame = self.cap.read()
        if not ret:
            return self._empty_result()

        # Get frame dimensions for magnitude calculation
        frame_h, frame_w = frame.shape[:2]
        frame_area = frame_h * frame_w

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self.prev_frame is None:
            self.prev_frame = gray
            return self._empty_result()

        #  Frame differencing 
        diff = cv2.absdiff(self.prev_frame, gray)
        _, thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)

        # Find all moving regions
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.prev_frame = gray

        #  Filter and score contours 
        # Only keep contours above our minimum size. Anything smaller is
        # noise, shadows, or compression artifacts.
        valid_contours = [c for c in contours if cv2.contourArea(c) > MIN_CONTOUR_AREA]

        if not valid_contours:
            # Nothing meaningful moving — reset approach tracking
            self.contour_history.append(0)
            self.approach_streak = 0
            self.object_approaching = False
            return self._empty_result()

        # Find the largest moving region — this is our "tracked object"
        largest_area = max(cv2.contourArea(c) for c in valid_contours)

        # Total moving area across ALL valid contours (for magnitude)
        total_moving_area = sum(cv2.contourArea(c) for c in valid_contours)

        # Magnitude: what fraction of the frame is actually moving?
        # 0.0 = nothing, 1.0 = entire frame changed
        magnitude = total_moving_area / frame_area

        # Is there enough motion to call it significant?
        motion_detected = magnitude >= MAGNITUDE_THRESHOLD

        #  Approach direction detection 
        # Track the largest contour's size over time. If it's consistently
        # getting bigger, the object is moving toward the camera.
        self.contour_history.append(largest_area)
        is_growing = self._check_approaching()

        if is_growing:
            self.approach_streak += 1
        else:
            self.approach_streak = 0

        # Only confirm "approaching" once we've seen enough consecutive
        # growing frames. Once confirmed, keep it True until streak breaks.
        if self.approach_streak >= APPROACH_CONFIRM_STREAK:
            self.object_approaching = True
        elif self.approach_streak == 0:
            self.object_approaching = False

        # Approach confidence: how sure are we? Based on streak length,
        # capped at 1.0. A streak of 5+ frames = full confidence.
        confidence = min(self.approach_streak / APPROACH_CONFIRM_STREAK, 1.0)

        return {
            "motion_detected":    motion_detected,
            "magnitude":          round(magnitude, 3),
            "largest_contour":    int(largest_area),
            "object_approaching": self.object_approaching,
            "approach_confidence": round(confidence, 2)
        }

    def _check_approaching(self) -> bool:
        """
        Look at the contour size history and determine if the object
        is growing (approaching the camera).

        Returns True if the newest reading is at least APPROACH_GROWTH_THRESHOLD
        times larger than the oldest reading in the window. This means the
        contour has grown by that percentage over the last N frames.
        """
        if len(self.contour_history) < 2:
            return False

        oldest = self.contour_history[0]
        newest = self.contour_history[-1]

        # Can't divide by zero if oldest is 0
        if oldest == 0:
            # If we went from nothing to something, that counts as growth
            return newest > MIN_CONTOUR_AREA

        growth_ratio = newest / oldest
        return growth_ratio >= APPROACH_GROWTH_THRESHOLD

    def _empty_result(self) -> dict:
        """Return a zeroed-out result when there's nothing to report."""
        return {
            "motion_detected":    False,
            "magnitude":          0.0,
            "largest_contour":    0,
            "object_approaching": self.object_approaching,  # Keep last state
            "approach_confidence": 0.0
        }

    def release(self):
        self.cap.release()
