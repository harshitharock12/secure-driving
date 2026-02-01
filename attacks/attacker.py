import requests
import json
import time
import copy
import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import SENSOR_HOST, LOGGER_PORT

LOGGER_URL = f"http://{SENSOR_HOST}:{LOGGER_PORT}/receive"


def attack_spoof():
    """
    ATTACK 1: Spoofing — send a completely fake message with a made-up signature.
    The logger should reject this because the HMAC will not match.
    """
    print("[Attacker] Launching SPOOFING attack...")

    fake_event = {
        "sensor_id": "evil_sensor",
        "event_type": "emergency_brake",
        "payload": {
            "distance_cm": 1,
            "motion": True
        },
        "timestamp": time.time(),
        "sequence_num": 9999,
        "signature": "deadbeef" * 8   # Fake 64-char hex string
    }

    resp = requests.post(LOGGER_URL, json=fake_event)
    print(f"[Attacker] Response: {resp.json()}")


def attack_tamper(original_signed_event: dict):
    """
    ATTACK 2: Tampering — modify a field in a validly-signed message.
    The old signature no longer matches the new content.
    """
    print("[Attacker] Launching TAMPERING attack...")

    tampered = copy.deepcopy(original_signed_event)
    tampered["payload"]["distance_cm"] = 999
    tampered["event_type"] = "normal"

    # IMPORTANT: signature is NOT recomputed
    resp = requests.post(LOGGER_URL, json=tampered)
    print(f"[Attacker] Response: {resp.json()}")


def attack_replay(original_signed_event: dict):
    """
    ATTACK 3: Replay — re-send a previously valid message after a delay.
    The timestamp will be too old and the sequence number already seen.
    """
    print("[Attacker] Launching REPLAY attack (waiting 12s for timestamp to expire)...")

    time.sleep(12)  # Wait longer than TIMESTAMP_WINDOW (10s)
    resp = requests.post(LOGGER_URL, json=original_signed_event)
    print(f"[Attacker] Response: {resp.json()}")


def attack_missing_signature():
    """
    ATTACK 4: Missing Signature — send a valid-looking message with no signature at all.
    """
    print("[Attacker] Launching MISSING SIGNATURE attack...")

    event = {
        "sensor_id": "sneaky_sensor",
        "event_type": "emergency_brake",
        "payload": {
            "distance_cm": 5,
            "motion": True
        },
        "timestamp": time.time(),
        "sequence_num": 8888
        # No "signature" field!
    }

    resp = requests.post(LOGGER_URL, json=event)
    print(f"[Attacker] Response: {resp.json()}")


if __name__ == "__main__":

    while True:
        print("=== SecureSense Attack Simulator ===")
        print("1) Spoofing Attack")
        print("2) Missing Signature Attack")
        print("3) Tampering Attack (needs a valid signed event — run after system is live)")
        print("4) Replay Attack (needs a valid signed event — waits 12s automatically)")
        print("5) Run all attacks in sequence")
        print("6) Quit")

        choice = input("Select attack: ").strip()

        if choice == "1":
            attack_spoof()

        elif choice == "2":
            attack_missing_signature()

        elif choice in ("3", "4", "5"):
            # Paste a real signed event here (from Person 2 output)
            sample_valid = {
                "sensor_id": "pi_sensor_01",
                "event_type": "distance_alert",
                "payload": {
                    "distance_cm": 15,
                    "motion": True
                },
                "timestamp": time.time(),
                "sequence_num": 1,
                "signature": "PASTE_VALID_SIGNATURE_HERE"
            }

            if choice == "3":
                attack_tamper(sample_valid)

            elif choice == "4":
                attack_replay(sample_valid)

            else:
                attack_spoof()
                attack_missing_signature()
                attack_tamper(sample_valid)
                attack_replay(sample_valid)
        
        elif choice == "6":
            print("Exiting.")
            break

        else:
            print("Invalid choice.")
