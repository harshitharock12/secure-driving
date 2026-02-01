import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, request, jsonify
import requests

from config import SENSOR_HOST, SIGNER_PORT, LOGGER_PORT
from security.signer import sign_message


app = Flask(__name__)
LOGGER_URL = f"http://{SENSOR_HOST}:{LOGGER_PORT}/receive"

REQUIRED_FIELDS = {"sensor_id", "event_type", "payload", "timestamp", "sequence_num"}

@app.route("/sign", methods=["POST"])
def sign_endpoint():
    event = request.get_json(silent=True)
    if not event:
        return jsonify({"error": "No JSON body"}), 400

    missing = [f for f in REQUIRED_FIELDS if f not in event]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    signed = sign_message(event)
    print(f"[Signer] Signed {signed.get('event_type')} sig={signed['signature'][:16]}...")

    forwarded_status = None
    try:
        resp = requests.post(LOGGER_URL, json=signed, timeout=2)
        forwarded_status = resp.status_code
    except Exception as e:
        # Logger might not be running yet during development — that's okay
        print(f"[Signer] Logger unreachable: {e}")

    return jsonify({"status": "ok", "forwarded": forwarded_status}), 200

if __name__ == "__main__":
    print(f"[Signer] Listening on 0.0.0.0:{SIGNER_PORT}")
    app.run(host="0.0.0.0", port=SIGNER_PORT, debug=False)
