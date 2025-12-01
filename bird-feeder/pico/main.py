from hx711 import hx711
from machine import Pin
import time

# HX711 Configuration
CLOCK_PIN = 14
DATA_PIN = 15
CALIBRATION_FACTOR = -359.843080

def auto_tare(hx, samples=10):
    tare_readings = []
    for i in range(samples):
        reading = hx.get_value()
        if reading is not None:
            tare_readings.append(reading)
        time.sleep(0.05)
    return sum(tare_readings) / len(tare_readings) if tare_readings else None

def main():
    hx = hx711(Pin(CLOCK_PIN), Pin(DATA_PIN))
    hx.set_power(hx711.power.pwr_up)
    hx.set_gain(hx711.gain.gain_128)
    hx711.wait_settle(hx711.rate.rate_10)
    
    tare_value = auto_tare(hx)
    print(f"TARED:{tare_value:.2f}" if tare_value else "ERROR:TARE_FAILED")
    if not tare_value:
        tare_value = 0
    
    print("READY")
    
    # Track consecutive low-weight readings for aggressive taring
    low_weight_count = 0
    TARE_AFTER_LOW_READINGS = 25  # 5 seconds of readings near zero (25 * 0.2s)
    
    while True:
        try:
            raw = hx.get_value()
            if raw is not None:
                weight = (raw - tare_value) / CALIBRATION_FACTOR
                print(f"WEIGHT:{weight:.2f}")
                
                # If weight is very low (near zero or slightly negative), increment counter
                if abs(weight) < 2.0:
                    low_weight_count += 1
                    
                    # After 5 seconds of low readings, auto-tare
                    if low_weight_count >= TARE_AFTER_LOW_READINGS:
                        print("AUTO_TARING")
                        new_tare = auto_tare(hx)
                        if new_tare:
                            tare_value = new_tare
                            print(f"TARED:{tare_value:.2f}")
                        low_weight_count = 0
                else:
                    # Reset counter if bird detected
                    low_weight_count = 0
            else:
                print("ERROR:NO_READING")
        except Exception as e:
            print(f"ERROR:{e}")
        
        time.sleep(0.2)

if __name__ == "__main__":
    main()
