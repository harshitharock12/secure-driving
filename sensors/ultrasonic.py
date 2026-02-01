import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
TRIG_PIN = 17
ECHO_PIN = 27

def setup():
    GPIO.setup(TRIG_PIN, GPIO.OUT)
    GPIO.setup(ECHO_PIN, GPIO.IN)

def measure_distance():
    """Returns distance in centimeters (float)."""
    GPIO.output(TRIG_PIN, False)
    time.sleep(0.1)            # Let sensor settle

    GPIO.output(TRIG_PIN, True)    # Send a 10us pulse
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, False)

    start = time.time()
    while GPIO.input(ECHO_PIN) == 0:  # Wait for echo start
        pass
    while GPIO.input(ECHO_PIN) == 1:  # Wait for echo end
        pass
    elapsed = time.time() - start

    # Speed of sound = 34300 cm/s; round trip so divide by 2
    distance = (elapsed * 34300) / 2
    return round(distance, 2)

def cleanup():
    GPIO.cleanup()

