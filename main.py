import cv2
import sys
import time
import numpy as np
import RPi.GPIO as GPIO
from hx711 import HX711
from datetime import datetime

bird_present = False

MOTION_ENABLED = True
MOTION_THRESHOLD = 2 # Minimum change to trigger motion detection


SCALE_ENABLED = False
WEIGHT_THRESHOLD = 5  # Minimum weight to trigger scale, Lightest british songbird Goldcrest 5g

def cleanAndExit():
    print("Cleaning...")
    print("Bye!")
    sys.exit()

def get_stable_weight(hx, samples=35):
    """Get a stable weight reading by taking multiple samples and filtering outliers very aggressively"""
    readings = []
    
    for i in range(samples):
        reading = hx.get_weight(1)
        readings.append(reading)
        time.sleep(0.02)  # Faster sampling
    
    # Sort readings to identify outliers
    readings.sort()
    
    # Very aggressive outlier removal (remove top and bottom 40%)
    outliers_to_remove = max(3, int(samples * 0.4))
    trimmed = readings[outliers_to_remove:-outliers_to_remove]
    
    # Use median of the middle values for maximum stability
    if len(trimmed) >= 3:
        # Take median of trimmed values
        median_index = len(trimmed) // 2
        stable_weight = trimmed[median_index]
    else:
        # Fallback to overall median if too few values left
        median_index = len(readings) // 2
        stable_weight = readings[median_index]
    
    return stable_weight

def take_photo(weight):
    """Take a photo when a bird lands"""
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        # Let camera adjust
        for i in range(5):
            ret, frame = cap.read()
        ret, frame = cap.read()
        if ret:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bird_{timestamp}_{weight:.1f}g.jpg"
            cv2.imwrite("./images/"+filename, frame)
            print(f"📸 Photo: {filename}")
        cap.release()

def bird_landed(weight, timestamp):
    """Called when a bird lands on the feeder"""
    print(f"🐦 Bird landed at {timestamp.isoformat()}! Weight: {weight:.2f}g")
    take_photo(weight)

def bird_left():
    """Called when a bird leaves the feeder"""
    print(f"🦅 Bird left!")
    time.sleep(2)
    print("Tare done! Waiting for birds...")

if SCALE_ENABLED:
    # Setup HX711
    print("Initializing scale...")
    hx = HX711(5, 6)
    hx.set_reading_format("MSB", "MSB")

    referenceUnit = -388.929792
    hx.set_reference_unit(referenceUnit)

    hx.reset()
    hx.tare()
    print("Tare done! Waiting for birds...")
else:
    current_weight = 0

if MOTION_ENABLED:
    # Setup camera for motion detection
    print("Initializing camera for motion detection...")
    cap = cv2.VideoCapture(0)
    last_mean = 0
    frame_rec_count = 0

while True:
    try:
        current_time = datetime.now()
        if SCALE_ENABLED:
            # Get stable weight reading - with very aggressive filtering
            current_weight = get_stable_weight(hx, samples=10)
            
            if not bird_present and current_weight > WEIGHT_THRESHOLD:
                bird_present = True
                bird_landed(current_weight, current_time)
            
            elif bird_present and current_weight < WEIGHT_THRESHOLD:
                bird_present = False
                bird_left()
                hx.tare()

            hx.power_down()
            hx.power_up()
        
        if MOTION_ENABLED:
            ret, frame = cap.read()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            current_motion = np.abs(np.mean(gray) - last_mean)
            last_mean= np.mean(gray)

            if not bird_present and current_motion > MOTION_THRESHOLD:
                bird_present = True
                bird_landed(current_weight, current_time)
            
            elif bird_present and current_motion < MOTION_THRESHOLD:
                bird_present = False
                bird_left()


        time.sleep(0.2)

    except (KeyboardInterrupt, SystemExit):
        cleanAndExit()