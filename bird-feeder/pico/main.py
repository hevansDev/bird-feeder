from hx711 import hx711
from machine import Pin
import time

# HX711 Configuration
CLOCK_PIN = 14
DATA_PIN = 15
CALIBRATION_FACTOR = -284.254040

def take_reading(hx, samples=5):
    """Take multiple readings and return average"""
    readings = []
    for i in range(samples):
        val = hx.get_value()
        if val is not None:
            readings.append(val)
        time.sleep(0.02)
    return sum(readings) / len(readings) if readings else None

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
    
    # Simple loop: just report weight constantly
    consecutive_negatives = 0
    
    while True:
        try:
            # Get raw reading
            raw = hx.get_value()
            if raw is not None:
                # Calculate weight
                weight = (raw - tare_value) / CALIBRATION_FACTOR
                
                # Print weight (always)
                print(f"WEIGHT:{weight:.2f}")
                
                # Auto-tare on negative values
                if weight < -1.0:
                    consecutive_negatives += 1
                    if consecutive_negatives >= 3:
                        print("AUTO_TARE_NEGATIVE")
                        tare_value = take_reading(hx, samples=10)
                        if tare_value:
                            print(f"TARED:{tare_value:.2f}")
                        consecutive_negatives = 0
                else:
                    consecutive_negatives = 0
            else:
                print("ERROR:NO_READING")
        
        except Exception as e:
            print(f"ERROR:{str(e)}")
        
        time.sleep(0.1)  # 10Hz reporting rate

if __name__ == "__main__":
    main()
