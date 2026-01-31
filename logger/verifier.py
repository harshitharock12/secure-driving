import hmac, hashlib, json, time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import SECRET_KEY, TIMESTAMP_WINDOW

# Track the highest sequence number we have seen per sensor
seen_sequences = {}   # { sensor_id: highest_seq_num }


def recompute_hmac(message: dict) -> str:
    """Recompute HMAC the same way Person 2 does."""
    canonical = {k: v for k, v in message.items() if k != "signature"}
    canonical_str = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    mac = hmac.new(
        key=SECRET_KEY.encode("utf-8"),
        msg=canonical_str.encode("utf-8"),
        digestmod=hashlib.sha256
    )
    return mac.hexdigest()


def verify_message(message: dict):
    """
    Verify a signed message. Returns (True, None) on success,
    or (False, "reason string") on failure.
    """
    # 1. Check required fields exist
    required = ["sensor_id", "event_type", "payload", "timestamp", "sequence_num", "signature"]
    for field in required:
        if field not in message:
            return False, f"Missing field: {field}"

    # 2. Verify HMAC signature
    expected_sig = recompute_hmac(message)
    if not hmac.compare_digest(expected_sig, message["signature"]):
        return False, "Invalid signature — message may be forged or tampered"

    # 3. Check timestamp freshness
    age = time.time() - message["timestamp"]
    if age > TIMESTAMP_WINDOW or age < 0:
        return False, f"Stale timestamp — message is {age:.1f}s old (max {TIMESTAMP_WINDOW}s)"

    # 4. Check sequence number (replay protection)
    sensor_id = message["sensor_id"]
    seq = message["sequence_num"]
    if sensor_id in seen_sequences and seq <= seen_sequences[sensor_id]:
        return False, f"Replay detected — seq {seq} already seen (last: {seen_sequences[sensor_id]})"

    # All checks passed — update state
    seen_sequences[sensor_id] = seq
    return True, None
