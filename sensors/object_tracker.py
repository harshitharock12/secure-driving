import time
from collections import deque


#  Configuration 
# All tunable parameters live here at the top so you can adjust them easily
# during the demo without hunting through the logic below.

# Distance thresholds (cm) — these define the raw zones
DISTANCE_CRITICAL   = 15    # Anything closer than this is immediately dangerous
DISTANCE_WARNING    = 40    # Approaching objects enter caution here
DISTANCE_MAX        = 100   # Readings beyond this are likely noise or empty space

# Hysteresis offsets (cm) — how far back an object must retreat before
# an alert clears. Prevents flickering when something hovers at a boundary.
HYSTERESIS_CRITICAL = 5     # Must go back to 20cm before critical clears
HYSTERESIS_WARNING  = 8     # Must go back to 48cm before warning clears

# Approach velocity (cm/s) — negative velocity means something is getting closer
VELOCITY_CAUTION    = -15   # Gentle approach (e.g. someone walking toward you)
VELOCITY_WARNING    = -40   # Fast approach (jogging, slow driving)
VELOCITY_CRITICAL   = -80   # Rapid approach (running, fast vehicle)

# Time-to-Collision (TTC) thresholds in seconds
TTC_WARNING         = 3.0   # Object will arrive in under 3 seconds
TTC_CRITICAL        = 1.0   # Object will arrive in under 1 second

# Persistence — how many consecutive readings must confirm an object before
# we trust it. Filters out single-ping noise from the ultrasonic sensor.
PERSISTENCE_MIN     = 3     # Need 3 consecutive valid readings

# Tracking history — how many past readings to keep for velocity calculations.
# More readings = smoother velocity, but slower to react. 5 is a good balance.
HISTORY_SIZE        = 5

# Sensor loop interval in seconds — must match what sensor_main.py uses
# so velocity calculations are accurate.
LOOP_INTERVAL       = 0.5


class ObjectTracker:
    """
    Tracks objects detected by the ultrasonic sensor over time.

    Each time you call update() with a new distance reading, it:
      1. Filters out noise (readings beyond max range or obviously bad)
      2. Checks persistence (is this a real object or a blip?)
      3. Computes approach velocity from recent history
      4. Predicts time-to-collision if something is approaching
      5. Applies hysteresis to prevent alert flickering
      6. Returns a severity-rated assessment
    """

    def __init__(self):
        # Rolling window of (timestamp, distance) tuples
        self.history = deque(maxlen=HISTORY_SIZE)

        # How many consecutive valid readings we've seen for the current object
        self.consecutive_valid = 0

        # Current alert state — persists across readings due to hysteresis
        # Can be: None, "caution", "warning", "critical"
        self.current_alert = None

        # Cached values from the last assessment
        self.last_velocity = 0.0
        self.last_ttc = None
        self.object_confirmed = False

    def update(self, raw_distance: float) -> dict:
        """
        Feed a new distance reading in. Returns a full assessment dict.

        Args:
            raw_distance: Distance in cm from the ultrasonic sensor.

        Returns:
            A dict containing everything sensor_main.py needs to build an event:
            {
                "object_detected": bool,
                "object_confirmed": bool,      # True once persistence threshold is met
                "distance_cm": float,
                "velocity_cm_s": float,        # Negative = approaching, positive = receding
                "ttc_seconds": float or None,  # Time to collision, None if not approaching
                "severity": str or None,       # None, "caution", "warning", "critical"
                "reasons": list[str]           # Human-readable list of why this severity was chosen
            }
        """
        now = time.time()

        #  Step 1: Filter noise 
        # The HC-SR04 sometimes returns garbage readings (0, or very large values).
        # Discard anything outside the plausible range.
        if raw_distance <= 0 or raw_distance > DISTANCE_MAX:
            self.consecutive_valid = 0
            return self._no_object(raw_distance)

        #  Step 2: Persistence check 
        # Increment consecutive valid counter. Only confirm an object once
        # we've seen enough consecutive good readings.
        self.consecutive_valid += 1
        self.history.append((now, raw_distance))

        if self.consecutive_valid < PERSISTENCE_MIN:
            # Not enough readings yet to confirm this is a real object
            self.object_confirmed = False
            return self._unconfirmed_object(raw_distance)

        # Object is confirmed as real
        self.object_confirmed = True

        #  Step 3: Compute approach velocity 
        # Velocity = change in distance / change in time
        # We use the oldest and newest readings in our history window
        # for the smoothest possible velocity estimate.
        self.last_velocity = self._compute_velocity()

        #  Step 4: Predict time-to-collision 
        # TTC only makes sense if the object is approaching (negative velocity).
        # TTC = current_distance / abs(approach_speed)
        self.last_ttc = self._compute_ttc(raw_distance)

        #  Step 5: Determine severity with hysteresis 
        severity, reasons = self._assess_severity(raw_distance)

        return {
            "object_detected":  True,
            "object_confirmed": True,
            "distance_cm":      round(raw_distance, 2),
            "velocity_cm_s":    round(self.last_velocity, 2),
            "ttc_seconds":      round(self.last_ttc, 2) if self.last_ttc else None,
            "severity":         severity,
            "reasons":          reasons
        }

    #  Internal helpers 

    def _compute_velocity(self) -> float:
        """
        Compute velocity in cm/s using the history window.
        Negative = object is getting closer.
        Positive = object is moving away.
        """
        if len(self.history) < 2:
            return 0.0

        oldest_time, oldest_dist = self.history[0]
        newest_time, newest_dist = self.history[-1]

        dt = newest_time - oldest_time
        if dt == 0:
            return 0.0

        # (new_distance - old_distance) / time
        # If object moved from 60cm to 30cm, that's (30-60)/dt = negative = approaching
        return (newest_dist - oldest_dist) / dt

    def _compute_ttc(self, current_distance: float):
        """
        Predict time-to-collision in seconds.
        Only valid when an object is actively approaching (negative velocity).
        Returns None if the object is stationary or moving away.
        """
        if self.last_velocity >= 0:
            # Not approaching — no collision to predict
            return None

        approach_speed = abs(self.last_velocity)  # Make it positive for division

        if approach_speed < 1.0:
            # Moving so slowly it's essentially stationary — don't predict
            return None

        ttc = current_distance / approach_speed
        return ttc

    def _assess_severity(self, distance: float) -> tuple:
        """
        Determine the severity level using hysteresis.

        Hysteresis works like a thermostat with two settings:
          - The alert triggers at one threshold 
          - But it doesn't clear until the object retreats past a
            different, more relaxed threshold 
        This prevents the alert from rapidly toggling on and off
        when an object hovers right at the boundary.

        Returns:
            (severity_string_or_None, list_of_reason_strings)
        """
        reasons = []
        new_severity = None

        #  Evaluate each severity tier 
        # We check from most severe to least, and the first match wins.
        # Each check considers distance, velocity, AND TTC together —
        # this is what makes it behave like a real vehicle sensor system
        # rather than just a simple threshold detector.

        # CRITICAL — immediate danger
        if (distance < DISTANCE_CRITICAL or
            (self.last_ttc is not None and self.last_ttc < TTC_CRITICAL) or
            self.last_velocity < VELOCITY_CRITICAL):

            new_severity = "critical"
            if distance < DISTANCE_CRITICAL:
                reasons.append(f"Object at {distance:.1f}cm (critical zone < {DISTANCE_CRITICAL}cm)")
            if self.last_ttc is not None and self.last_ttc < TTC_CRITICAL:
                reasons.append(f"Collision predicted in {self.last_ttc:.2f}s")
            if self.last_velocity < VELOCITY_CRITICAL:
                reasons.append(f"Rapid approach at {abs(self.last_velocity):.1f} cm/s")

        # WARNING — fast approach or close proximity
        elif (distance < DISTANCE_WARNING or
              (self.last_ttc is not None and self.last_ttc < TTC_WARNING) or
              self.last_velocity < VELOCITY_WARNING):

            new_severity = "warning"
            if distance < DISTANCE_WARNING:
                reasons.append(f"Object at {distance:.1f}cm (warning zone < {DISTANCE_WARNING}cm)")
            if self.last_ttc is not None and self.last_ttc < TTC_WARNING:
                reasons.append(f"Collision predicted in {self.last_ttc:.2f}s")
            if self.last_velocity < VELOCITY_WARNING:
                reasons.append(f"Fast approach at {abs(self.last_velocity):.1f} cm/s")

        # CAUTION — object is approaching, but not urgently
        elif self.last_velocity < VELOCITY_CAUTION:
            new_severity = "caution"
            reasons.append(f"Object approaching at {abs(self.last_velocity):.1f} cm/s")
            if self.last_ttc is not None:
                reasons.append(f"Estimated arrival in {self.last_ttc:.1f}s")

        #  Apply hysteresis 
        # If we currently have an active alert, don't let it clear unless
        # the object has retreated past the hysteresis threshold.
        if self.current_alert == "critical" and new_severity != "critical":
            if distance < DISTANCE_CRITICAL + HYSTERESIS_CRITICAL:
                # Object hasn't retreated far enough — keep critical
                new_severity = "critical"
                reasons = [f"Object still within critical hysteresis zone ({distance:.1f}cm)"]

        elif self.current_alert == "warning" and new_severity is None:
            if distance < DISTANCE_WARNING + HYSTERESIS_WARNING:
                # Object hasn't retreated far enough — keep warning
                new_severity = "warning"
                reasons = [f"Object still within warning hysteresis zone ({distance:.1f}cm)"]

        # Update current alert state
        self.current_alert = new_severity

        return new_severity, reasons

    def _no_object(self, raw_distance: float) -> dict:
        """Return assessment when no valid reading was received (noise filtered out)."""
        self.current_alert = None
        self.last_velocity = 0.0
        self.last_ttc = None
        return {
            "object_detected":  False,
            "object_confirmed": False,
            "distance_cm":      round(raw_distance, 2),
            "velocity_cm_s":    0.0,
            "ttc_seconds":      None,
            "severity":         None,
            "reasons":          ["No valid reading — filtered as noise"]
        }

    def _unconfirmed_object(self, raw_distance: float) -> dict:
        """Return assessment when readings exist but persistence threshold isn't met yet."""
        return {
            "object_detected":  True,
            "object_confirmed": False,
            "distance_cm":      round(raw_distance, 2),
            "velocity_cm_s":    0.0,
            "ttc_seconds":      None,
            "severity":         None,
            "reasons":          [f"Object detected but unconfirmed ({self.consecutive_valid}/{PERSISTENCE_MIN} readings)"]
        }
