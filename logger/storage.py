import sqlite3, os, json
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DB_PATH

def init_db():
    """Create the events table if it does not exist."""
    # Ensure the directory exists
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT,
        event_type TEXT,
        payload TEXT,
        timestamp REAL,
        sequence_num INTEGER,
        signature TEXT,
        status TEXT,
        reject_reason TEXT,
        received_at REAL
    )
    """)
    conn.commit()
    conn.close()

def store_event(event: dict, status: str, reject_reason: str = None):
    """Store an event record in the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    INSERT INTO events
    (sensor_id, event_type, payload, timestamp, sequence_num,
    signature, status, reject_reason, received_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event.get("sensor_id"),
        event.get("event_type"),
        json.dumps(event.get("payload", {})),
        event.get("timestamp"),
        event.get("sequence_num"),
        event.get("signature"),
        status,
        reject_reason,
        __import__("time").time()
    ))
    conn.commit()
    conn.close()

def get_recent_events(limit=50):
    """Retrieve the most recent events for the dashboard."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM events ORDER BY received_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows