import hx711
from machine import Pin
import sys
import time
import uselect

# HX711 Configuration
CLOCK_PIN = 14
DATA_PIN = 15

# Just the calibration factor - tare calculated automatically
CALIBRATION_FACTOR = -172.367900

def auto_tare(hx, samples=10):
    """Take multiple readings and average for tare value"""
    tare_readings = []
    for i in range(samples):
        reading = hx.read()
        if reading is not None:
            tare_readings.append(reading)
        time.sleep(0.05)
    
    if tare_readings:
        tare_value = sum(tare_readings) / len(tare_readings)
        hx.set_offset(tare_value)
        return tare_value
    return None

def main():
    # Initialize HX711
    hx = HX711(Pin(CLOCK_PIN), Pin(DATA_PIN))
    hx.set_scale(CALIBRATION_FACTOR)
    
    # Auto-tare on startup
    tare_value = auto_tare(hx)
    if tare_value is not None:
        print(f"TARED:{tare_value:.2f}")
    else:
        print("ERROR:TARE_FAILED")
    
    print("READY")
    
    # Setup polling for stdin
    poll = uselect.poll()
    poll.register(sys.stdin, uselect.POLLIN)
    
    command_buffer = ""
    
    # Main loop
    while True:
        # Check for incoming data (non-blocking, 0ms timeout)
        events = poll.poll(0)
        if events:
            char = sys.stdin.read(1)
            if char:
                if char == '\n':
                    # Process complete command
                    cmd = command_buffer.strip()
                    if cmd == "TARE":
                        print("TARING")
                        tare_value = auto_tare(hx)
                        if tare_value is not None:
                            print(f"TARED:{tare_value:.2f}")
                        else:
                            print("ERROR:TARE_FAILED")
                    command_buffer = ""
                else:
                    command_buffer += char
        
        # Read and send weight
        try:
            weight = hx.get_units()
            if weight is not None:
                print(f"WEIGHT:{weight:.2f}")
            else:
                print("ERROR:NO_READING")
        except Exception as e:
            print(f"ERROR:{e}")
        
        time.sleep(0.2)

if __name__ == "__main__":
    main()