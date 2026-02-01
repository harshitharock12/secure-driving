# security/test_signer.py
import time
import time
import copy

from security.signer import sign_message, verify_locally

def main():
    test_event = {
        "sensor_id": "test_sensor",
        "event_type": "distance_alert",
        "payload": {"distance_cm": 15, "motion": True},
        "timestamp": time.time(),
        "sequence_num": 1,
    }

    signed = sign_message(test_event)
    print("Signature:", signed["signature"])
    assert verify_locally(signed) is True
    print("✓ Signature verifies")

    tampered = copy.deepcopy(signed)
    tampered["payload"]["distance_cm"] = 999
    assert verify_locally(tampered) is False
    print("✓ Tampering detected")

if __name__ == "__main__":
    main()
