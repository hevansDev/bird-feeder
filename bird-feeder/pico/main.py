from hx711 import hx711
from machine import Pin
import time
import sys
import select

# HX711 Configuration
CLOCK_PIN = 14
DATA_PIN = 15
CALIBRATION_FACTOR = -284.254040

# Set up polling for stdin
poll = select.poll()
poll.register(sys.stdin, select.POLLIN)

def take_reading(hx, samples=5):
    """Take multiple readings and return average"""
    readings = []
    for i in range(samples):
        val = hx.get_value()
        if val is not None:
            readings.append(val)
        time.sleep(0.02)
    return sum(readings) / len(readings) if readings else None

def check_for_command():
    """Check if there's a command waiting on stdin (non-blocking)"""
    if poll.poll(0):  # 0 = non-blocking
        return sys.stdin.readline().strip()
    return None

def main():
    # Initialize HX711
    hx = hx711(Pin(CLOCK_PIN), Pin(DATA_PIN))
    hx.set_power(hx711.power.pwr_up)
    hx.set_gain(hx711.gain.gain_128)
    hx711.wait_settle(hx711.rate.rate_10)
    
    # Initial tare
    print("TARING")
    time.sleep(0.5)
    tare_value = take_reading(hx, samples=10)
    if tare_value:
        print(f"TARED:{tare_value:.2f}")
    else:
        print("ERROR:TARE_FAILED")
        tare_value = 0
    
    print("READY")
    
    while True:
        try:
            # Check for commands from Pi
            cmd = check_for_command()
            if cmd == "TARE":
                print("TARING")
                new_tare = take_reading(hx, samples=10)
                if new_tare:
                    tare_value = new_tare
                    print(f"TARED:{tare_value:.2f}")
                else:
                    print("ERROR:TARE_FAILED")
            
            # Get raw reading
            raw = hx.get_value()
            if raw is not None:
                weight = (raw - tare_value) / CALIBRATION_FACTOR
                print(f"WEIGHT:{weight:.2f}")
            else:
                print("ERROR:NO_READING")
        
        except Exception as e:
            print(f"ERROR:{str(e)}")
        
        time.sleep(0.1)  # 10Hz reporting rate

if __name__ == "__main__":
    main()