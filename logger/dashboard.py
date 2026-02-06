from flask import Flask, request, jsonify
from verifier import verify_message
from storage import init_db, store_event, get_recent_events, get_total_rejected, clear_events
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import LOGGER_PORT

EVENT_LABELS = {
    "normal":             "Normal",
    "distance_alert":     "Distance Alert",
    "motion_detected":    "Motion Detected",
    "collision_warning":  "Collision Warning",
    "crash_detected":     "Crash Detected",
    "lane_departure":     "Lane Departure",
    "spoof_attempt":      "Sensor Spoofing Attempt",
}


app = Flask(__name__)
init_db()   # Create table on startup

clear_events()


@app.route("/receive", methods=["POST"])
def receive():
    """Endpoint that signer server POSTs signed messages to."""
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

@app.route("/events")
def events():
    events = get_recent_events(50) or []

    def format_row(e):
        status = e.get("status", "rejected")
        row_class = "valid-row" if status == "valid" else "rejected-row"
        badge = "✓ VALID" if status == "valid" else "✗ REJECTED"
        badge_class = "badge-valid" if status == "valid" else "badge-rejected"

        received_at = e.get("received_at", 0)
        # If received_at is not a unix timestamp, this might throw -> caught below
        time_str = datetime.fromtimestamp(received_at).strftime("%H:%M:%S")

        reason = e.get("reject_reason") or "—"
        reason_html = f"<span class='reason'>{reason}</span>" if e.get("reject_reason") else "—"
        raw_type = e.get("event_type")
        event_type = EVENT_LABELS.get(raw_type, raw_type.replace("_", " ").title() if raw_type else "—")

        return f"""
        <tr class="{row_class}">
            <td>{time_str}</td>
            <td>{event_type}</td>
            <td><span class="badge {badge_class}">{badge}</span></td>
            <td>{reason_html}</td>
        </tr>"""

    reject_count = get_total_rejected()

    rows = []
    for e in events:
        try:
            rows.append(format_row(e))
        except Exception as ex:
            # Don't break the whole dashboard if one row is malformed
            rows.append(f"""
            <tr class="rejected-row">
                <td>--</td>
                <td>render_error</td>
                <td><span class="badge badge-rejected">✗ ERROR</span></td>
                <td><span class="reason">{str(ex)}</span></td>
            </tr>""")

    rows_html = "".join(rows)

    last_id = events[0].get("id", 0) if events else 0

    return jsonify({
        "reject_count": reject_count,
        "rows_html": rows_html,
        "last_id": last_id
    })


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
        event_type = EVENT_LABELS.get(e["event_type"], e["event_type"].replace("_", " ").title() if e["event_type"] else "—")
        rows_html += f"""
        <tr class="{row_class}">
            <td>{time_str}</td>
            <td>{event_type}</td>
            <td><span class="badge {badge_class}">{badge}</span></td>
            <td>{reason_html}</td>
        </tr>"""

    valid_count   = sum(1 for e in events if e["status"] == "valid")
    reject_count  = sum(1 for e in events if e["status"] == "rejected")

    return f"""
    <!DOCTYPE html><html><head><title>Drive Secure Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap">
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
            font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0B3C5D 0%, #005DAA 55%, #4BB7E6 100%);
            color: #FFFFFF;
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
            background: rgba(255, 255, 255, 0.12);
            border-radius: 15px;
            border-left: 6px solid #FFFFFF;
            box-shadow: 0 8px 28px rgba(0, 0, 0, 0.25);
        }}
        .header h1 {{
            font-size: 2.6em;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #FFFFFF;
        }}
        .header p {{
            font-weight: 500;
            color: #E6EEF5;
            margin-top: 10px;
            font-size: 1em;
        }}
        .stats {{ 
            display: flex; 
            gap: 20px;
            justify-content: center;
            margin-bottom: 0px;
            flex-wrap: wrap;
        }}
        .stat-box {{
            margin: 20px auto 32px auto;
            width: min(520px, 100%);
            background: #FFFFFF;
            padding: 15px;
            border-radius: 16px;
            border: none;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
            position: relative;
            overflow: hidden;
        }}
        .stat-box::before {{
            content: "";
            position: absolute;
            inset: -2px;
            background: radial-gradient(circle at 20% 20%, rgba(0, 212, 255, 0.22), transparent 55%),
                        radial-gradient(circle at 80% 40%, rgba(233, 69, 96, 0.18), transparent 55%);
            opacity: 0.9;
            pointer-events: none;
        }}

        .stat-box:hover {{
            transform: translateY(-4px);
            border-color: rgba(0, 212, 255, 0.45);
            box-shadow: 0 14px 38px rgba(0, 0, 0, 0.45);
        }}
        .stat-box h3 {{
            font-weight: 700;
            font-size: 0.9em;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            color: #0B3C5D;
        }}
        .stat-box h2 {{
            font-size: 3.4em;
            font-weight: 800;
            letter-spacing: -1px;
            margin: 6px 0;
        }}
        .stat-valid h2 {{ color: #00ff88; }}
        .stat-rejected h2 {{
            font-size: 3.2em;
            font-weight: 800;
            color: #005DAA;
            text-align: center;
        }}
        .stat-total h2 {{ color: #00d4ff; }}
        .stat-sub {{
            margin-top: 6px;
            font-size: 0.95em;
            font-weight: 500;
            color: #1f2d3d;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            margin-bottom: 0;
        }}
        .panel {{
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 18px;
            padding: 20px;
            box-shadow: 0 16px 48px rgba(0,0,0,0.28);
            backdrop-filter: blur(10px);

            margin-bottom: 22px; 
        }}
        .panel table {{
            margin-top: 18px;
        }}

        .topbar{{
            display:flex; align-items:center; justify-content:space-between;
            padding:14px 16px; margin-bottom:18px;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 16px;
            backdrop-filter: blur(10px);
        }}
        .brand{{ display:flex; gap:12px; align-items:center; }}
        .dot{{
            width:10px; height:10px; border-radius:999px;
            background:#00ff88; box-shadow: 0 0 18px rgba(0,255,136,0.7);
        }}
        .brand-title{{ font-weight:800; letter-spacing:-0.3px; }}
        .brand-sub{{ font-size:0.9em; color:#E6EEF5; opacity:0.9; }}
        .meta{{ display:flex; gap:12px; align-items:center; }}
        .pill{{
            padding:6px 10px; border-radius:999px;
            background: rgba(0,255,136,0.14);
            border: 1px solid rgba(0,255,136,0.35);
            font-weight:700; letter-spacing:0.6px;
        }}
        .meta-text{{ color:#E6EEF5; font-size:0.92em; }}

        table {{ 
            width: 100%; 
            border-collapse: collapse;
            background: rgba(0, 0, 0, 0.4);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        th {{
            background: #005DAA;
            color: #FFFFFF;
            padding: 16px 12px;
            font-weight: 600;
            font-size: 0.95em;
            letter-spacing: 0.3px;
        }}
        td {{
            padding: 14px 12px;
            font-size: 0.95em;
            font-weight: 500;
            color: #E6EEF5;
        }}
        tr:hover {{ background: rgba(0, 212, 255, 0.08); }}
        tr:last-child td {{ border-bottom: none; }}
        .valid-row {{ background: rgba(0, 212, 255, 0.10); }}
        td, th {{ border-bottom: 1px solid rgba(255,255,255,0.08); }}
        thead th {{ position: sticky; top: 0; z-index: 2; }}
        tbody tr {{ transition: background 160ms ease; }}

        .rejected-row {{background: rgba(11, 60, 93, 0.20); }}
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
    </head><body>
    <div class="container">
        <div class="topbar">
            <div class="brand">
                <div class="dot"></div>
                <div>
                <div class="brand-title">Drive Secure</div>
                <div class="brand-sub">Authenticated Vehicle Sensor System</div>
                </div>
            </div>
            <div class="meta">
                <span class="pill" id="livePill">LIVE</span>
                <span class="meta-text">Last update: <span id="lastUpdated">—</span></span>
                
            </div>
        </div>
        <div class="header">
            <h1>Drive Secure — Live Dashboard</h1>
            <p>Authenticated Vehicle Sensor System | Real-time Verification</p>
            <p style="margin-top:8px; font-size:0.9em; opacity:0.85;">
                
            </p>
        </div>
        <div class="panel">
            <div class="stats">
                <div class="stat-box stat-rejected">
                    <h3>Blocked / Fabricated Messages</h3>
                    <h2 id="rejectCount">{reject_count}</h2>
                    <div class="stat-sub">Total rejected signature checks (last 50 displayed below)</div>
                </div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Event Type</th>
                    <th>Status</th>
                    <th>Rejection Reason</th>
                </tr>
            </thead>
            <tbody id="eventsBody">
                {rows_html}
            </tbody>
        </table>
    </div>
    <script>
    const LIVE_WINDOW_MS = 3000;
    let lastEventTs = null;
    let lastId = null;
    let delayMs = 800;

    async function refreshEvents() {{
        try {{
            const res = await fetch("/events", {{ cache: "no-store" }});
            if (!res.ok) return;
            const data = await res.json();

            if (lastId !== data.last_id) {{
                lastId = data.last_id;

                const counter = document.getElementById("rejectCount");
                if (counter) counter.textContent = data.reject_count;

                const body = document.getElementById("eventsBody");
                if (body) body.innerHTML = data.rows_html;

                const lu = document.getElementById("lastUpdated");
                if (lu) lu.textContent = new Date().toLocaleTimeString();

                lastEventTs = Date.now();
            }}
        }} catch (e) {{
            // ignore
        }} finally {{
            setTimeout(refreshEvents, delayMs);
        }}
    }}

    function updateLivePill() {{
        const pill = document.getElementById("livePill");
        if (!pill) return;
        if (lastEventTs && (Date.now() - lastEventTs) < LIVE_WINDOW_MS) {{
            pill.style.display = "inline-block";
        }} else {{
            pill.style.display = "none";
        }}
    }}

    setInterval(updateLivePill, 300);
    refreshEvents();
    </script>

    </body></html>"""


if __name__ == "__main__":
    print(f"[Logger] Dashboard running on http://0.0.0.0:{LOGGER_PORT}")
    app.run(host="0.0.0.0", port=LOGGER_PORT, debug=False)
