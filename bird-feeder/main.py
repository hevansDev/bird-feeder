# TODO
# Modular refactor into multiple files
# Don't save images locally if cloud upload enabled
# Manage process with systemd
# Add logging instead of print statements
# Simplify taring and serial scale logic

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
import threading

from scale import SerialWeightSensor, DirectWeightSensor

from kafka import KafkaProducer

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
STABLE_WAIT_TIME = float(os.getenv('STABLE_WAIT_TIME', '1.0'))  # Time to wait for stable weight after bird lands

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

# Metrics config
METRICS_INTERVAL = float(os.getenv('METRICS_INTERVAL', '10.0'))  # Send metrics every 10 seconds

KAFKA_BROKER_URL = os.getenv('KAFKA_BROKER_URL', 'bird-feeder-bird-feeder.h.aivencloud.com:13867')

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER_URL,
    security_protocol="SSL",
    ssl_cafile="ca.pem",
    ssl_certfile="service.cert",
    ssl_keyfile="service.key",
    api_version=(3, 9, 1),
)

class BirdFeeder:
    def __init__(self):
        self.bird_present = False
        self.no_motion_frames = 0
        self.bird_approaching = False
        self.approach_time = None
        self.last_photo_time = None
        
        # Metrics tracking
        self.metrics_counter = {
            'messages': 0,
            'bytes': 0,
            'last_sent': time.time()
        }
        
        # Start metrics thread
        self.metrics_running = True
        self.metrics_thread = threading.Thread(target=self._metrics_loop, daemon=True)
        self.metrics_thread.start()
        print(f"✓ Metrics thread started (interval: {METRICS_INTERVAL}s)")
        
        Path(IMAGES_DIR).mkdir(exist_ok=True)
        
        print("Initializing camera...")
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("Failed to open camera!")

        # Initialize scale based on type
        if SCALE_ENABLED:
            if SCALE_TYPE == 'serial':
                self.scale = SerialWeightSensor(PICO_SERIAL_PORT, PICO_SERIAL_BAUD, PICO_TIMEOUT)
            else:  # direct
                self.scale = DirectWeightSensor(reference_unit=SCALE_REFERENCE_UNIT)
            
            # Tare on startup
            print("Taring scale...")
            self.scale.tare()
        
        if MOTION_ENABLED:
            self.prev_frame = None
            print("Motion detection ready! Waiting for birds...")
    
    def _metrics_loop(self):
        """Background thread to send metrics periodically"""
        while self.metrics_running:
            try:
                time.sleep(METRICS_INTERVAL)
                self.send_metrics()
            except Exception as e:
                print(f"Error in metrics loop: {e}")
                import traceback
                traceback.print_exc()
    
    def send_to_kafka(self, topic, data_dict):
        """Unified Kafka send with metrics tracking"""
        try:
            message = json.dumps(data_dict)
            message_bytes = message.encode('utf-8')
            
            future = producer.send(topic, message_bytes)
            # Wait for confirmation
            record_metadata = future.get(timeout=10)
            
            # print(f"✓ Sent to {topic}: offset={record_metadata.offset}, partition={record_metadata.partition}")
            
            # Track metrics
            self.metrics_counter['messages'] += 1
            self.metrics_counter['bytes'] += len(message_bytes)
            
        except Exception as e:
            print(f"✗ FAILED to send to {topic}: {e}")
    
    def send_metrics(self):
        """Send aggregated metrics to Kafka"""
        elapsed = time.time() - self.metrics_counter['last_sent']
        
        if elapsed == 0:
            return
        
        metrics = {
            'userId': USER_ID,
            'location': FEEDER_LOCATION if FEEDER_LOCATION else None,
            'messagesPerSec': round(self.metrics_counter['messages'] / elapsed, 2),
            'bytesPerSec': round(self.metrics_counter['bytes'] / elapsed, 2),
            'kbPerSec': round((self.metrics_counter['bytes'] / 1024) / elapsed, 2),
            'totalMessages': self.metrics_counter['messages'],
            'totalBytes': self.metrics_counter['bytes'],
            'windowSeconds': round(elapsed, 2),
            'timestamp': datetime.now().isoformat()
        }
        
        # Send metrics without tracking (to avoid recursion)
        message = json.dumps(metrics)
        producer.send('metrics', message.encode('utf-8'))
        
        print(f"📊 Metrics: {metrics['messagesPerSec']:.1f} msg/s, {metrics['kbPerSec']:.2f} KB/s")
        
        # Reset counters
        self.metrics_counter = {
            'messages': 0,
            'bytes': 0,
            'last_sent': time.time()
        }
    
    def read_sensors(self):
        weight = self.scale.get_weight()
        motion = self.detect_motion() if MOTION_ENABLED else 0
        current_time = time.time()

        # Send raw data to Kafka
        if SCALE_ENABLED and weight is not None:
            self.send_weight_data_to_kafka(weight, datetime.now())
        if MOTION_ENABLED:
            self.send_motion_data_to_kafka(motion, datetime.now())
        
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
                    self.on_bird_landed("motion-only")
            
            # Weight detected (with or without motion)
            elif weight_detected and not self.bird_present:
                self.bird_present = True
                self.bird_approaching = False
                self.no_motion_frames = 0
                self.on_bird_landed("scale")
            
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
                self.on_bird_landed(detection_type)
            
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
        
        # Stop metrics thread
        self.metrics_running = False
        if hasattr(self, 'metrics_thread'):
            self.metrics_thread.join(timeout=2)
        
        # Send final metrics before closing
        if self.metrics_counter['messages'] > 0:
            self.send_metrics()
        
        self.cap.release()
        producer.close()
        
        if SCALE_ENABLED:
            if SCALE_TYPE == 'serial':
                self.scale.close()
            else:
                self.hx.power_down()
        
        print("Bye!")
        sys.exit()

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
            print("Photo cooldown")
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
                    self.send_bird_data_to_kafka(weight, detection_type, datetime.now())
                
                print(f"Photo: {filename}")
                self.last_photo_time = current_time
                return True
        return False
    
    def send_bird_data_to_kafka(self, weight, detection_type, timestamp):
        """Send bird detection data to Kafka topic"""
        data = {
            'userId': USER_ID,
            'weight': float(weight) if weight is not None else None,
            'detectionType': detection_type,
            'timestamp': timestamp.isoformat(),
            'location': FEEDER_LOCATION if FEEDER_LOCATION else None
        }
        self.send_to_kafka("bird-data", data)
    
    def send_weight_data_to_kafka(self, weight, timestamp):
        """Send weight data to Kafka topic"""
        data = {
            'userId': USER_ID,
            'weight': float(weight) if weight is not None else None,
            'timestamp': timestamp.isoformat(),
            'location': FEEDER_LOCATION if FEEDER_LOCATION else None
        }
        self.send_to_kafka("weight", data)

    def send_motion_data_to_kafka(self, motion, timestamp):
        """Send motion data to Kafka topic"""
        data = {
            'userId': USER_ID,
            'motion': int(motion),  # Convert numpy int64 to Python int
            'timestamp': timestamp.isoformat(),
            'location': FEEDER_LOCATION if FEEDER_LOCATION else None
        }
        self.send_to_kafka("motion", data)

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

    def on_bird_landed(self, detection_type):
        """Called when a bird lands. detection_type: 'scale', 'motion', or 'motion-only'"""
        time.sleep(STABLE_WAIT_TIME)  # Wait a moment for stable reading
        if self.scale.get_weight() > WEIGHT_THRESHOLD:
            weight = self.scale.get_weight()
            timestamp = datetime.now()
            weight_str = f"{weight:.2f}g" if weight is not None else "N/A"
            print(f"Bird landed at {timestamp.isoformat()}! Weight: {weight_str} (detected by: {detection_type})")
            self.take_photo(weight, detection_type)
        else:
            print(f"Weight didn't stabilize above threshold after {STABLE_WAIT_TIME} seconds, ignoring.")


    def on_bird_left(self):
        """Called when a bird leaves the feeder"""
        print("Bird left!")
        
        if SCALE_ENABLED:
            self.scale.tare()

birdFeeder = BirdFeeder()

while True:
    try:
        birdFeeder.read_sensors()
        time.sleep(0.2)
    except (KeyboardInterrupt, SystemExit):
        birdFeeder.cleanAndExit()
