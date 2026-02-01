
import json

def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

def without_signature(message: dict) -> dict:
    return {k: v for k, v in message.items() if k != "signature"}
