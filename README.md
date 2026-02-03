# DriveSecure - Authenticated Vehicle Sensor System

A cryptographically authenticated sensor platform that prevents cyberattacks on vehicle safety systems. DriveSecure uses HMAC-SHA256 digital signatures to protect collision detection sensors from spoofing, tampering, and replay attacks.

## The Problem

Modern vehicles rely on sensors for critical safety features like automatic emergency braking and collision detection. However, these sensors are vulnerable to cyberattacks:

- **Sensor Spoofing**: Attackers can inject fake sensor readings
- **Data Tampering**: Messages can be modified in transit
- **Replay Attacks**: Old sensor data can be maliciously re-sent

A successful attack could disable collision detection or trigger false emergency braking, endangering lives.


## Solution

DriveSecure implements cryptographic authentication for vehicle sensor data using HMAC-SHA256 digital signatures. Every sensor reading is signed and verified in real-time.

**How It Works:**
1. Sensors collect distance (ultrasonic) and motion (camera) data
2. Signer cryptographically signs each message with HMAC-SHA256
3. Verifier validates signatures, timestamps, and sequence numbers
4. Dashboard displays authenticated events and rejected attacks in real-time

## Key Features

- HMAC-SHA256 cryptographic authentication on all sensor data
- Timestamp validation to prevent replay attacks
- Sequence number tracking for duplicate detection
- Real-time collision detection using ultrasonic and camera sensors
- Live dashboard for monitoring events
- Built-in attack simulator for testing

## Architecture

![DriveSecure Architecture](images/Raspberry Pi (HC-SR04 + Camera) → Signer Server (HMAC-SHA256) → LoggerVerifier → Dashboard.pdf)



## Tech Stack

**Hardware:**
- Raspberry Pi 4 Model B
- HC-SR04 Ultrasonic Sensor
- USB Camera

**Software:**
- Python 3.8+
- Flask - REST API and web dashboard
- OpenCV - Computer vision and motion detection
- SQLite - Event storage
- RPi.GPIO - Hardware interface
- HMAC-SHA256 - Cryptographic authentication

## Installation

### Hardware Setup

**Ultrasonic Sensor (HC-SR04):**
- VCC → 5V
- GND → Ground
- TRIG → GPIO 17
- ECHO → GPIO 27

**Camera:** USB webcam via Raspberry Pi USB port

### Software Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/secure-driving.git
cd secure-driving
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure `config.py` with your settings

## Usage

### Running the System

Start each component in a separate terminal:

```bash
# Terminal 1 - Signer Server
python security/signer_server.py

# Terminal 2 - Logger/Dashboard
python logger/dashboard.py

# Terminal 3 - Sensor System
python sensors/sensor_main.py

# Terminal 4 - Attack Simulator (Optional)
python tools/attacker.py
```

**Access Points:**
- Dashboard: http://localhost:8080
- Signer API: http://localhost:5002/sign
- Logger API: http://localhost:5003/receive

## Demo

**Normal Operation:**
- Move hand toward ultrasonic sensor and camera
- Observe "distance_alert" events at <30cm
- Move hand quickly to trigger "collision_warning"

**Attack Detection:**
- Run the attack simulator and choose an attack type
- Watch dashboard reject malicious events
- Supported attacks: spoofing, tampering, replay, missing signature

