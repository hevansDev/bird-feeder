"""
Raspberry Pi Pico - Serial Weight Reporter
Reads from HX711 and reports weight over USB serial
For use with bird feeder monitoring system
"""

import time
from machine import Pin
from hx711 import hx711
import sys
import select

# Your calibration values - UPDATE THESE!
TARE_VALUE = 29231.90
CALIBRATION_FACTOR = -172.367900

# Pin configuration
CLOCK_PIN = 14  # GP14
DATA_PIN = 15   # GP15

# Sampling configuration
SAMPLES_PER_READING = 5
READING_INTERVAL = 0.2  # Send reading every 200ms

class WeightSensor:
    def __init__(self):
        """Initialize HX711 with calibration"""
        self.hx = hx711(Pin(CLOCK_PIN), Pin(DATA_PIN))
        self.hx.set_power(hx711.power.pwr_up)
        self.hx.set_gain(hx711.gain.gain_128)
        hx711.wait_settle(hx711.rate.rate_10)
        
        self.tare_offset = 0  # Additional tare offset from commands
        
        print("READY")  # Signal to host that we're initialized
        sys.stdout.flush()
    
    def get_stable_reading(self, samples=5):
        """Get a stable reading by averaging multiple samples with outlier removal"""
        readings = []
        
        for i in range(samples):
            val = self.hx.get_value()
            if val:
                readings.append(val)
            time.sleep(0.05)
        
        if len(readings) < 3:
            return None
        
        # Sort and remove outliers
        readings.sort()
        if len(readings) >= 3:
            trimmed = readings[1:-1]
        else:
            trimmed = readings
        
        return sum(trimmed) / len(trimmed)
    
    def get_weight(self):
        """Get weight in grams, applying calibration and tare"""
        raw = self.get_stable_reading(SAMPLES_PER_READING)
        if raw is None:
            return None
        
        # Apply calibration and tare
        weight = (raw - TARE_VALUE - self.tare_offset) / CALIBRATION_FACTOR
        return weight
    
    def tare(self):
        """Tare the scale - set current weight as zero"""
        print("TARING")
        sys.stdout.flush()
        
        # Take several readings to get stable tare value
        readings = []
        for i in range(10):
            raw = self.get_stable_reading(3)
            if raw is not None:
                readings.append(raw)
            time.sleep(0.1)
        
        if readings:
            # Calculate new tare offset
            avg_raw = sum(readings) / len(readings)
            # This is the raw value we want to treat as zero
            self.tare_offset = avg_raw - TARE_VALUE
            print("TARED")
        else:
            print("ERROR:TARE_FAILED")
        
        sys.stdout.flush()
    
    def check_command(self):
        """Check for serial commands from host (non-blocking)"""
        # MicroPython's sys.stdin.read() is blocking, so we'll use a simple approach
        # In practice, you might want to use select/poll for non-blocking
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            cmd = sys.stdin.readline().strip()
            if cmd == "TARE":
                self.tare()
            elif cmd == "PING":
                print("PONG")
                sys.stdout.flush()

def main():
    sensor = WeightSensor()
    
    # Main loop - continuously report weight
    while True:
        try:
            weight = sensor.get_weight()
            
            if weight is not None:
                # Format: WEIGHT:<grams>
                print(f"WEIGHT:{weight:.2f}")
            else:
                print("ERROR:NO_READING")
            
            sys.stdout.flush()
            time.sleep(READING_INTERVAL)
            
        except Exception as e:
            print(f"ERROR:{e}")
            sys.stdout.flush()
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("SHUTDOWN")
        sys.stdout.flush()