import time, json, requests, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import SENSOR_HOST, SIGNER_PORT
from sensors.ultrasonic import setup as us_setup, measure_distance, cleanup
from sensors.motion_camera import MotionDetector

SIGNER_URL              = f"http://{SENSOR_HOST}:{SIGNER_PORT}/sign"
LOOP_INTERVAL           = 0.5       # Read sensors every 0.5 seconds

# Ultrasonic thresholds (cm)
DISTANCE_ALERT          = 50        # Object closer than this triggers distance alert
DISTANCE_CLOSE          = 50        # Object within this range is "nearby"

# How fast something must be closing in to count as "approaching."
ULTRASONIC_APPROACH_SPEED = 10      # cm/s toward the sensor

# How many recent readings to look back through when checking if both sensors agree. 
CORRELATION_WINDOW      = 3

sequence_num = 0


class SensorCorrelator:
    """
    Tracks recent readings from the camera and ultrasonic sensor to determine whether they
    agree that something is approaching. This is helpful to prevent possible false positives
    from possible errors in sensors. 
    """

    def __init__(self):
        # history of (distance, velocity) from ultrasonic
        self.ultrasonic_history = []
        # history of camera results
        self.camera_history = []

    def update(self, distance: float, prev_distance: float, camera_result: dict):
        """
        Feed in the latest readings from both sensors.
        Computes velocity from the last two ultrasonic readings,
        stores both histories, and trims to the correlation window.
        """
        # Compute ultrasonic velocity (cm/s). Negative = approaching.
        velocity = (distance - prev_distance) / LOOP_INTERVAL if prev_distance else 0.0

        self.ultrasonic_history.append({
            "distance": distance,
            "velocity": velocity
        })
        self.camera_history.append(camera_result)

        # Keep histories trimmed to the correlation window
        if len(self.ultrasonic_history) > CORRELATION_WINDOW:
            self.ultrasonic_history = self.ultrasonic_history[-CORRELATION_WINDOW:]
        if len(self.camera_history) > CORRELATION_WINDOW:
            self.camera_history = self.camera_history[-CORRELATION_WINDOW:]

        return velocity

    def is_correlated_approach(self) -> bool:
        """
        Check whether both sensors agree something is approaching within
        the recent correlation window.

        Ultrasonic confirms approach if ANY reading in the window shows
        the object getting closer faster than our speed threshold.

        Camera confirms approach if ANY reading in the window has
        object_approaching flagged as True.

        Both must be True for correlation to pass.
        """
        if not self.ultrasonic_history or not self.camera_history:
            return False

        # Did ultrasonic see something approaching in window
        ultrasonic_approaching = any(
            r["velocity"] < -ULTRASONIC_APPROACH_SPEED
            for r in self.ultrasonic_history
        )

        # Did the camera confirm an approaching object in window
        camera_approaching = any(
            r.get("object_approaching", False)
            for r in self.camera_history
        )

        return ultrasonic_approaching and camera_approaching


def build_event(distance: float, velocity: float, camera_result: dict,
                correlated: bool, sequence: int) -> dict:
    """
    Classify the event based on all available data and build the payload.

    Event type priority (highest to lowest):
        collision_warning   — both sensors agree something is approaching fast
        distance_alert      — ultrasonic sees something very close
        object_approaching  — camera confirmed approach but ultrasonic hasn't correlated yet
        motion_detected     — camera sees motion but can't confirm it's approaching
        normal              — nothing noteworthy
    """
    global sequence_num

    event_type = "normal"
    reasons = []

    # Correlated collision warning 
    # Both sensors independently confirmed something is approaching.
    # This is the highest confidence alert.
    
    if correlated and distance < DISTANCE_CLOSE:
        event_type = "collision_warning"
        reasons.append("Both camera and ultrasonic confirm object approaching")
        if distance < DISTANCE_ALERT:
            reasons.append(f"Object close at {distance}cm")
        if velocity < -ULTRASONIC_APPROACH_SPEED:
            reasons.append(f"Closing speed: {abs(velocity):.1f} cm/s")

    # Distance alert 
    # Something is very close on ultrasonic regardless of camera.
    
    elif distance < DISTANCE_ALERT:
        event_type = "distance_alert"
        reasons.append(f"Object detected at {distance}cm")
        if velocity < 0:
            reasons.append(f"Approaching at {abs(velocity):.1f} cm/s")

    # Camera-confirmed approach
    # Camera is confident something is approaching, but ultrasonic hasn't
    # corroborated yet. Could be at the edge of ultrasonic range.
    elif camera_result.get("object_approaching", False):
        event_type = "object_approaching"
        reasons.append(f"Camera confirmed approaching object (confidence: {camera_result.get('approach_confidence', 0)})")
        if camera_result.get("largest_contour", 0) > 0:
            reasons.append(f"Contour size: {camera_result['largest_contour']}px")

    # General motion
    # Camera sees motion but can't confirm it's approaching.
    # Could be lateral movement, background change, etc.
    elif camera_result.get("motion_detected", False):
        event_type = "motion_detected"
        reasons.append(f"Motion detected (magnitude: {camera_result.get('magnitude', 0)})")

    return {
        "sensor_id":    "pi_sensor_01",
        "event_type":   event_type,
        "payload": {
            "distance_cm":          distance,
            "velocity_cm_s":        round(velocity, 2),
            "camera_magnitude":     camera_result.get("magnitude", 0.0),
            "camera_approaching":   camera_result.get("object_approaching", False),
            "approach_confidence":  camera_result.get("approach_confidence", 0.0),
            "correlated":           correlated,
            "reasons":              reasons
        },
        "timestamp":    time.time(),
        "sequence_num": sequence
    }


def main():
    us_setup()
    detector    = MotionDetector()
    correlator  = SensorCorrelator()

    prev_distance = None
    sequence_num  = 0

    signer_url = f"http://{SENSOR_HOST}:{SIGNER_PORT}/sign"

    print("[Sensor] Starting sensor loop...")
    print(f"[Sensor] Posting to {signer_url}")
    print("-" * 60)

    while True:
        #  Read both sensors 
        distance      = measure_distance()
        camera_result = detector.detect()

        #  Feed into correlator 
        velocity   = correlator.update(distance, prev_distance, camera_result)
        correlated = correlator.is_correlated_approach()
        prev_distance = distance

        #  Build and send event 
        sequence_num += 1
        event = build_event(distance, velocity, camera_result, correlated, sequence_num)

        # Console output 
        event_type = event["event_type"]
        
        # Visual marker so you can see alerts at a glance in the terminal
        markers = {
            "normal":            "          ",
            "motion_detected":   " MOTION   ",
            "object_approaching":" APPROACH ",
            "distance_alert":    " DISTANCE ",
            "collision_warning": "!COLLISION!"
        }
        marker = markers.get(event_type, "          ")

        print(f"[{marker}] dist={distance:>6}cm | vel={velocity:>7.1f} cm/s | "
              f"cam_approach={str(camera_result.get('object_approaching', False)):>5} | "
              f"correlated={str(correlated):>5} | {event_type}")

        if event["payload"]["reasons"]:
            for reason in event["payload"]["reasons"]:
                print(f"            └─ {reason}")

        #  Send to signer 
        try:
            requests.post(signer_url, json=event, timeout=2)
        except Exception as e:
            print(f"[Sensor] Failed to send: {e}")

        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Sensor] Shutting down...")
        cleanup()
