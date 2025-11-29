import cv2
import sys
import time
import json
import numpy as np
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
from pathlib import Path

import serial
import threading
from queue import Queue

# Load environment variables - try .env.local first, fall back to .env
if os.path.exists('.env.local'):
    load_dotenv('.env.local', override=True)
else:
    load_dotenv('.env')

# Configuration from .env
MOTION_ENABLED = os.getenv('MOTION_ENABLED', 'true').lower() == 'true'
MOTION_THRESHOLD = int(os.getenv('MOTION_THRESHOLD', '1000'))
FRAMES_BEFORE_DEPARTURE = int(os.getenv('FRAMES_BEFORE_DEPARTURE', '10'))

SCALE_ENABLED = os.getenv('SCALE_ENABLED', 'false').lower() == 'true'
WEIGHT_THRESHOLD = int(os.getenv('WEIGHT_THRESHOLD', '5'))
SCALE_WAIT_TIME = float(os.getenv('SCALE_WAIT_TIME', '1.0'))
SCALE_REFERENCE_UNIT = float(os.getenv('SCALE_REFERENCE_UNIT', '-388.929792'))

# Scale type: 'direct' for HX711 connected to Pi GPIO, 'serial' for Pico over USB
SCALE_TYPE = os.getenv('SCALE_TYPE', 'serial')  # 'direct' or 'serial'

# Serial Pico config
PICO_SERIAL_PORT = os.getenv('PICO_SERIAL_PORT', '/dev/ttyACM0')
PICO_SERIAL_BAUD = int(os.getenv('PICO_SERIAL_BAUD', '115200'))
PICO_TIMEOUT = float(os.getenv('PICO_TIMEOUT', '2.0'))

# Cloud upload config
ENABLE_CLOUD_UPLOAD = os.getenv('ENABLE_CLOUD_UPLOAD', 'false').lower() == 'true'
UPLOAD_SERVICE_URL = os.getenv('UPLOAD_SERVICE_URL', '')
USER_ID = os.getenv('USER_ID', 'anonymous')
FEEDER_LOCATION = os.getenv('FEEDER_LOCATION', '')

# File paths
IMAGES_DIR = os.getenv('IMAGES_DIR', './images')
PHOTO_COOLDOWN = float(os.getenv('PHOTO_COOLDOWN', '5.0'))

# Import scale library only if needed for direct connection
if SCALE_ENABLED and SCALE_TYPE == 'direct':
    try:
        import RPi.GPIO as GPIO
        from hx711 import HX711
    except ImportError:
        print("Warning: Scale enabled but RPi.GPIO/HX711 not available")
        SCALE_ENABLED = False

class SerialWeightSensor:
    """Interface for Pico weight sensor over serial USB"""
    
    def __init__(self, port, baudrate=115200, timeout=2.0):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.latest_weight = None
        self.connected = False
        self.reader_thread = None
        self.running = False
        
        self.connect()
    
    def connect(self):
        """Connect to Pico serial port"""
        try:
            print(f"Connecting to Pico on {self.port}...")
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1.0)
            time.sleep(2)  # Wait for Pico to initialize
            
            # Clear any startup messages
            self.serial.reset_input_buffer()
            
            # Wait for READY message
            start_time = time.time()
            while time.time() - start_time < 5:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8').strip()
                    if line == "READY":
                        print("Pico weight sensor ready!")
                        self.connected = True
                        break
                time.sleep(0.1)
            
            if not self.connected:
                raise RuntimeError("Pico didn't send READY signal")
            
            # Start reader thread
            self.running = True
            self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.reader_thread.start()
            
        except Exception as e:
            print(f"Failed to connect to Pico: {e}")
            self.connected = False
            raise
    
    def _read_loop(self):
        """Background thread to continuously read weight from serial"""
        while self.running:
            try:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8').strip()
                    
                    if line.startswith("WEIGHT:"):
                        try:
                            weight = float(line.split(":")[1])
                            self.latest_weight = weight
                        except ValueError:
                            pass
                    
                    elif line.startswith("ERROR:"):
                        error = line.split(":")[1]
                        if error != "NO_READING":
                            print(f"Pico error: {error}")
                    
                    elif line == "TARED":
                        print("Pico: Scale tared successfully")
                    
                    elif line == "TARING":
                        print("Pico: Taring scale...")
                
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Serial read error: {e}")
                time.sleep(0.1)
    
    def get_weight(self):
        """Get latest weight reading"""
        return self.latest_weight
    
    def tare(self):
        """Send tare command to Pico"""
        if self.connected and self.serial:
            try:
                self.serial.write(b"TARE\n")
                self.serial.flush()
                time.sleep(1)
            except Exception as e:
                print(f"Failed to send tare command: {e}")
    
    def close(self):
        """Clean shutdown of serial connection"""
        self.running = False
        if self.reader_thread:
            self.reader_thread.join(timeout=1)
        if self.serial:
            self.serial.close()
        print("Serial connection closed")

class BirdFeeder:
    def __init__(self):
        self.bird_present = False
        self.no_motion_frames = 0
        self.bird_approaching = False
        self.approach_time = None
        self.last_photo_time = None
        
        Path(IMAGES_DIR).mkdir(exist_ok=True)
        
        print("Initializing camera...")
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("Failed to open camera!")

        # Initialize scale based on type
        if SCALE_ENABLED:
            if SCALE_TYPE == 'serial':
                print("Initializing Pico serial weight sensor...")
                self.scale = SerialWeightSensor(PICO_SERIAL_PORT, PICO_SERIAL_BAUD, PICO_TIMEOUT)
            else:  # direct
                print("Initializing direct HX711 scale...")
                self.hx = HX711(5, 6)
                self.hx.set_reading_format("MSB", "MSB")
                self.hx.set_reference_unit(SCALE_REFERENCE_UNIT)
                self.hx.reset()
                self.hx.tare()
                print("Scale tared! Waiting for birds...")
        
        if MOTION_ENABLED:
            self.prev_frame = None
            print("Motion detection ready! Waiting for birds...")
    
    def read_sensors(self):
        weight = self.get_weight()
        motion = self.detect_motion() if MOTION_ENABLED else 0
        current_time = time.time()
        
        # Determine detection state
        motion_detected = motion > MOTION_THRESHOLD
        weight_detected = weight is not None and weight > WEIGHT_THRESHOLD
        
        # If both sensors enabled, use smart logic
        if SCALE_ENABLED and MOTION_ENABLED:
            # Motion detected but no weight yet - bird approaching
            if motion_detected and not weight_detected and not self.bird_present:
                if not self.bird_approaching:
                    self.bird_approaching = True
                    self.approach_time = current_time
                    print("Bird approaching...")
                
                # Wait for scale reading
                elif current_time - self.approach_time > SCALE_WAIT_TIME:
                    # Waited long enough, bird didn't land on scale
                    self.bird_present = True
                    self.bird_approaching = False
                    self.no_motion_frames = 0
                    self.on_bird_landed(weight, "motion-only")
            
            # Weight detected (with or without motion)
            elif weight_detected and not self.bird_present:
                self.bird_present = True
                self.bird_approaching = False
                self.no_motion_frames = 0
                self.on_bird_landed(weight, "scale")
            
            # Bird present, check if it left
            elif self.bird_present:
                if not motion_detected and not weight_detected:
                    self.no_motion_frames += 1
                    if self.no_motion_frames >= FRAMES_BEFORE_DEPARTURE:
                        self.on_bird_left()
                        self.bird_present = False
                        self.bird_approaching = False
                        self.no_motion_frames = 0
                else:
                    self.no_motion_frames = 0
        
        # Single sensor mode (simpler logic)
        else:
            bird_detected = weight_detected or motion_detected
            
            if bird_detected and not self.bird_present:
                self.bird_present = True
                self.no_motion_frames = 0
                detection_type = "scale" if SCALE_ENABLED else "motion"
                self.on_bird_landed(weight, detection_type)
            
            elif not bird_detected and self.bird_present:
                self.no_motion_frames += 1
                if self.no_motion_frames >= FRAMES_BEFORE_DEPARTURE:
                    self.on_bird_left()
                    self.bird_present = False
                    self.no_motion_frames = 0
            
            elif bird_detected:
                self.no_motion_frames = 0

    def cleanAndExit(self):
        print("Cleaning...")
        self.cap.release()
        
        if SCALE_ENABLED:
            if SCALE_TYPE == 'serial':
                self.scale.close()
            else:
                self.hx.power_down()
        
        print("Bye!")
        sys.exit()

    def get_weight(self, samples=35):
        """Get stable weight reading. Returns float (grams) or None."""
        if not SCALE_ENABLED:
            return None
        
        if SCALE_TYPE == 'serial':
            # Just return latest reading from Pico
            return self.scale.get_weight()
        
        else:  # direct HX711
            readings = []
            for i in range(samples):
                reading = self.hx.get_weight(1)
                readings.append(reading)
                time.sleep(0.02)
            
            readings.sort()
            outliers_to_remove = max(3, int(samples * 0.4))
            trimmed = readings[outliers_to_remove:-outliers_to_remove]
            
            if len(trimmed) >= 3:
                median_index = len(trimmed) // 2
                stable_weight = trimmed[median_index]
            else:
                median_index = len(readings) // 2
                stable_weight = readings[median_index]
            
            return stable_weight

    def detect_motion(self):
        """Detect motion using frame differencing. Returns int (motion pixels)."""
        ret, frame = self.cap.read()
        if not ret:
            return 0
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if self.prev_frame is None:
            self.prev_frame = gray
            return 0
        
        frame_diff = cv2.absdiff(gray, self.prev_frame)
        motion_pixels = np.sum(frame_diff > 30)
        self.prev_frame = gray
        
        return motion_pixels

    def take_photo(self, weight, detection_type):
        """Take a photo. Returns True if photo taken, False if skipped."""
        current_time = time.time()
        
        # Cooldown check - prevent spam photos of same bird
        if (self.last_photo_time and 
            current_time - self.last_photo_time < PHOTO_COOLDOWN):
            return False
        
        if self.cap.isOpened():
            for i in range(5):
                ret, frame = self.cap.read()
            ret, frame = self.cap.read()
            if ret:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                weight_str = f"{weight:.2f}g" if weight is not None else "None"
                filename = f"bird_{timestamp}_{weight_str}_{detection_type}.jpg"
                filepath = Path(IMAGES_DIR) / filename
    
                cv2.imwrite(str(filepath), frame)

                if ENABLE_CLOUD_UPLOAD:
                    self.upload_to_cloud(filepath, filename, weight, detection_type, timestamp)
                
                print(f"Photo: {filename}")
                self.last_photo_time = current_time
                return True
        return False

    def upload_to_cloud(self, filepath, filename, weight, detection_type, timestamp):
        """Upload photo to Cloudflare Images"""
        try:
            metadata = {
                'weight': weight,
                'detectionType': detection_type,
                'timestamp': timestamp,
                'location': FEEDER_LOCATION if FEEDER_LOCATION else None,
                'filename': filename
            }
            
            with open(filepath, 'rb') as f:
                files = {'file': (filename, f, 'image/jpeg')}
                data = {
                    'user_id': USER_ID,
                    'metadata': json.dumps(metadata)
                }
                
                response = requests.post(
                    UPLOAD_SERVICE_URL,
                    files=files,
                    data=data,
                    timeout=30
                )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"Uploaded to cloud: {result['urls']['public']}")
                else:
                    print(f"Upload failed: {result.get('error')}")
            else:
                print(f"Upload failed: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"Cloud upload error: {e}")

    def on_bird_landed(self, weight, detection_type):
        """Called when a bird lands. detection_type: 'scale', 'motion', or 'motion-only'"""
        timestamp = datetime.now()
        weight_str = f"{weight:.2f}g" if weight is not None else "N/A"
        print(f"Bird landed at {timestamp.isoformat()}! Weight: {weight_str} (detected by: {detection_type})")
        self.take_photo(weight, detection_type)

    def on_bird_left(self):
        """Called when a bird leaves the feeder"""
        print("Bird left!")
        
        if SCALE_ENABLED:
            if SCALE_TYPE == 'serial':
                self.scale.tare()
            else:
                self.hx.tare()
                print("Scale tared! Waiting for birds...")

birdFeeder = BirdFeeder()

while True:
    try:
        birdFeeder.read_sensors()
        time.sleep(0.2)
    except (KeyboardInterrupt, SystemExit):
        birdFeeder.cleanAndExit()