from hx711 import hx711
from machine import Pin
import sys
import time
import select

# HX711 Configuration
CLOCK_PIN = 14
DATA_PIN = 15

# Calibration factor from calibration
CALIBRATION_FACTOR = -359.843080

def auto_tare(hx, samples=10):
    """Take multiple readings and average for tare value"""
    tare_readings = []
    for i in range(samples):
        reading = hx.get_value()
        if reading is not None:
            tare_readings.append(reading)
        time.sleep(0.05)
    
    if tare_readings:
        return sum(tare_readings) / len(tare_readings)
    return None

def main():
    # Initialize HX711
    hx = hx711(Pin(CLOCK_PIN), Pin(DATA_PIN))
    hx.set_power(hx711.power.pwr_up)
    hx.set_gain(hx711.gain.gain_128)
    hx711.wait_settle(hx711.rate.rate_10)
    
    # Auto-tare on startup
    tare_value = auto_tare(hx)
    if tare_value is not None:
        print(f"TARED:{tare_value:.2f}")
    else:
        print("ERROR:TARE_FAILED")
        tare_value = 0
    
    print("READY")
    
    command_buffer = ""
    
    # Main loop
    while True:
        # Check for incoming TARE commands (non-blocking)
        try:
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if r:
                char = sys.stdin.read(1)
                if char == '\n':
                    # Process command
                    if command_buffer.strip() == "TARE":
                        print("TARING")
                        new_tare = auto_tare(hx)
                        if new_tare is not None:
                            tare_value = new_tare
                            print(f"TARED:{tare_value:.2f}")
                        else:
                            print("ERROR:TARE_FAILED")
                    command_buffer = ""
                else:
                    command_buffer += char
        except:
            # If select fails, just continue
            pass
        
        # Read and send weight
        try:
            raw = hx.get_value()
            if raw is not None:
                weight = (raw - tare_value) / CALIBRATION_FACTOR
                print(f"WEIGHT:{weight:.2f}")
            else:
                print("ERROR:NO_READING")
        except Exception as e:
            print(f"ERROR:{e}")
        
        time.sleep(0.2)

if __name__ == "__main__":
    main()
