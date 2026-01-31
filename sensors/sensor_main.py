import time, json, requests, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import SENSOR_HOST, SIGNER_PORT
from sensors.ultrasonic import setup as us_setup, measure_distance, cleanup
from sensors.motion_camera import MotionDetector

DISTANCE_ALERT_THRESHOLD = 30   # cm — trigger alert if object < 30cm away
LOOP_INTERVAL = 0.5             # Read the  sensors every 0.5 seconds
sequence_num = 0

def build_event(distance, motion_detected):
    global sequence_num
    sequence_num += 1
    event_type = "normal"
    if distance < DISTANCE_ALERT_THRESHOLD:
        event_type = "distance_alert"
    if motion_detected:
        event_type = "motion_detected" if event_type == "normal" else "collision_warning"

    return {
        "sensor_id":    "pi_sensor_01",
        "event_type":   event_type,
        "payload":      { "distance_cm": distance, "motion": motion_detected },
        "timestamp":    time.time(),
        "sequence_num": sequence_num
    }

def main():
    us_setup()
    detector = MotionDetector()
    signer_url = f"http://{SENSOR_HOST}:{SIGNER_PORT}/sign"

    print("[Sensor] Starting sensor loop... ")
    while True:
        distance = measure_distance()
        motion  = detector.detect()
        event   = build_event(distance, motion)

        print(f"[Sensor] {event['event_type']} | dist={distance}cm | motion={motion}")

        try:
            requests.post(signer_url, json=event, timeout=2)
        except Exception as e:
            print(f"[Sensor] Failed to send: {e}")

        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    main()

