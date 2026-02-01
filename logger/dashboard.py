from flask import Flask, request, jsonify
from verifier import verify_message
from storage import init_db, store_event, get_recent_events
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import LOGGER_PORT

app = Flask(__name__)
init_db()   # Create table on startup


@app.route("/receive", methods=["POST"])
def receive():
    """Endpoint that Person 2 POSTs signed messages to."""
    event = request.get_json()
    if not event:
        return jsonify({"error": "No JSON"}), 400

    valid, reason = verify_message(event)

    if valid:
        store_event(event, status="valid")
        print(f"[Logger] ACCEPTED: {event['event_type']}")
        return jsonify({"status": "accepted"}), 200
    else:
        store_event(event, status="rejected", reject_reason=reason)
        print(f"[Logger] REJECTED: {reason}")
        return jsonify({"status": "rejected", "reason": reason}), 403


@app.route("/")
def dashboard():
    """Serve the web dashboard."""
    events = get_recent_events(50)
    rows_html = ""
    for e in events:
        row_class = "valid-row" if e["status"] == "valid" else "rejected-row"
        badge = "✓ VALID" if e["status"] == "valid" else "✗ REJECTED"
        badge_class = "badge-valid" if e["status"] == "valid" else "badge-rejected"
        time_str = datetime.fromtimestamp(e["received_at"]).strftime("%H:%M:%S")
        reason = e["reject_reason"] or "—"
        reason_html = f"<span class='reason'>{reason}</span>" if e["reject_reason"] else "—"
        rows_html += f"""
        <tr class="{row_class}">
            <td>{time_str}</td>
            <td>{e['event_type']}</td>
            <td><span class="badge {badge_class}">{badge}</span></td>
            <td>{reason_html}</td>
        </tr>"""

    valid_count   = sum(1 for e in events if e["status"] == "valid")
    reject_count  = sum(1 for e in events if e["status"] == "rejected")

    return f"""
    <!DOCTYPE html><html><head><title>SecureSense Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        @keyframes carZoom {{ 
            0% {{ transform: translateX(-100px); opacity: 0; }}
            10% {{ opacity: 1; }}
            90% {{ opacity: 1; }}
            100% {{ transform: translateX(calc(100vw + 100px)); opacity: 0; }}
        }}
        @keyframes carZoomReverse {{ 
            0% {{ transform: translateX(calc(100vw + 100px)) scaleX(-1); opacity: 0; }}
            10% {{ opacity: 1; }}
            90% {{ opacity: 1; }}
            100% {{ transform: translateX(-100px) scaleX(-1); opacity: 0; }}
        }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
            overflow-x: hidden;
            position: relative;
        }}
        .car-lane {{
            position: fixed;
            width: 100%;
            height: 80px;
            pointer-events: none;
            z-index: 1;
        }}
        .car-lane-1 {{ top: 10%; }}
        .car-lane-2 {{ top: 30%; }}
        .car-lane-3 {{ top: 50%; }}
        .car-lane-4 {{ top: 70%; }}
        .car {{
            position: absolute;
            font-size: 3em;
            animation: carZoom 8s infinite linear;
        }}
        .car.reverse {{
            animation: carZoomReverse 10s infinite linear;
        }}
        .car-1 {{ animation-delay: 0s; }}
        .car-2 {{ animation-delay: 2s; }}
        .car-3 {{ animation-delay: 4s; }}
        .car-4 {{ animation-delay: 6s; }}
        .container {{ max-width: 1200px; margin: 0 auto; position: relative; z-index: 10; }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 30px 20px;
            background: linear-gradient(135deg, rgba(233, 69, 96, 0.2) 0%, rgba(15, 52, 96, 0.3) 100%);
            border-radius: 15px;
            border-left: 5px solid #e94560;
            box-shadow: 0 8px 32px rgba(233, 69, 96, 0.1);
        }}
        .header h1 {{ 
            font-size: 2.5em; 
            color: #00d4ff;
            text-shadow: 0 2px 10px rgba(0, 212, 255, 0.3);
            letter-spacing: 1px;
        }}
        .header p {{ color: #b0b0b0; margin-top: 10px; font-size: 0.95em; }}
        .stats {{ 
            display: flex; 
            gap: 20px; 
            margin-bottom: 40px;
            flex-wrap: wrap;
        }}
        .stat-box {{ 
            flex: 1;
            min-width: 200px;
            background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(233, 69, 96, 0.05) 100%);
            padding: 25px;
            border-radius: 12px;
            border: 2px solid rgba(0, 212, 255, 0.3);
            text-align: center;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }}
        .stat-box:hover {{
            transform: translateY(-5px);
            border-color: rgba(0, 212, 255, 0.6);
            box-shadow: 0 6px 25px rgba(0, 212, 255, 0.2);
        }}
        .stat-box h3 {{ 
            margin: 0 0 12px;
            color: #00d4ff;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .stat-box h2 {{ 
            font-size: 2.5em;
            font-weight: bold;
        }}
        .stat-valid h2 {{ color: #00ff88; }}
        .stat-rejected h2 {{ color: #ff6b6b; }}
        .stat-total h2 {{ color: #00d4ff; }}
        table {{ 
            width: 100%; 
            border-collapse: collapse;
            background: rgba(0, 0, 0, 0.4);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        th {{ 
            background: linear-gradient(135deg, #e94560 0%, #c72c48 100%);
            color: white; 
            padding: 16px 12px;
            text-align: left;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        td {{ 
            padding: 14px 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            color: #d0d0d0;
        }}
        tr:hover {{ background: rgba(0, 212, 255, 0.08); }}
        tr:last-child td {{ border-bottom: none; }}
        .valid-row {{ background: rgba(0, 255, 136, 0.08); }}
        .rejected-row {{ background: rgba(255, 107, 107, 0.08); }}
        .badge {{ 
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.85em;
            display: inline-block;
            letter-spacing: 0.5px;
        }}
        .badge-valid {{ 
            background: #00ff88;
            color: #000;
        }}
        .badge-rejected {{ 
            background: #ff6b6b;
            color: #fff;
        }}
        .reason {{
            color: #ffa500;
            font-size: 0.9em;
        }}
    </style>
    <meta http-equiv="refresh" content="3">
    </head><body>
    <div class="container">
        <div class="header">
            <h1>🚗 SecureSense — Live Dashboard</h1>
            <p>Authenticated Vehicle Sensor System | Real-time Verification</p>
        </div>
        <div class="stats">
            <div class="stat-box stat-valid">
                <h3>✓ Valid Events</h3>
                <h2>{valid_count}</h2>
            </div>
            <div class="stat-box stat-rejected">
                <h3>✗ Rejected Events</h3>
                <h2>{reject_count}</h2>
            </div>
            <div class="stat-box stat-total">
                <h3>📊 Total Events</h3>
                <h2>{len(events)}</h2>
            </div>
        </div>
        <table>
            <tr>
                <th>⏰ Time</th>
                <th>📡 Event Type</th>
                <th>🔐 Status</th>
                <th>ℹ️ Rejection Reason</th>
            </tr>
            {rows_html}
        </table>
    </div>
    </body></html>"""


if __name__ == "__main__":
    print(f"[Logger] Dashboard running on http://0.0.0.0:{LOGGER_PORT}")
    app.run(host="0.0.0.0", port=LOGGER_PORT, debug=False)
