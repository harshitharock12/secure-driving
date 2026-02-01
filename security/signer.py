import hmac
import hashlib

from config import SECRET_KEY
from message import canonical_json, without_signature

def compute_hmac(message: dict) -> str:
    canonical_obj = without_signature(message)
    msg_str = canonical_json(canonical_obj)
    mac = hmac.new(
        key=SECRET_KEY.encode("utf-8"),
        msg=msg_str.encode("utf-8"),
        digestmod=hashlib.sha256
    )
    return mac.hexdigest()

def sign_message(message: dict) -> dict:
    signed = dict(message)
    signed["signature"] = compute_hmac(signed)
    return signed

def verify_locally(message: dict) -> bool:
    if "signature" not in message:
        return False
    expected = compute_hmac(message)
    return hmac.compare_digest(expected, message["signature"])
