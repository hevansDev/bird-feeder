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
    
    # ZERO/TARE ON STARTUP
    print("ZEROING_ON_STARTUP")
    time.sleep(1.0)
    
    tare_value = take_reading(hx, samples=15)
    
    if tare_value:
        print("STARTUP_ZERO:{:.2f}".format(tare_value))
        print("READY")
    else:
        print("ERROR:STARTUP_ZERO_FAILED")
        tare_value = 0
        print("READY")
    
    # Track persistent weight for auto-tare
    low_weight_count = 0
    HIGH_WEIGHT_TARE_THRESHOLD = 100  # 10 seconds at 10Hz = 100 readings
    WEIGHT_TOLERANCE = 2.0  # If weight stays between -2g and +2g, consider it "zero"
    
    while True:
        try:
            # Get raw reading
            raw = hx.get_value()
            if raw is not None:
                # Calculate weight
                weight = (raw - tare_value) / CALIBRATION_FACTOR
                
                # Print weight (always)
                print("WEIGHT:{:.2f}".format(weight))
                
                # Check if weight is in "zero" range (-2g to +2g)
                if abs(weight) <= WEIGHT_TOLERANCE:
                    low_weight_count += 1
                    
                    # After 10 seconds of low weight, re-tare
                    if low_weight_count >= HIGH_WEIGHT_TARE_THRESHOLD:
                        print("IDLE_RETARE")
                        new_tare = take_reading(hx, samples=10)
                        if new_tare:
                            tare_value = new_tare
                            print("RETARED:{:.2f}".format(new_tare))
                        low_weight_count = 0
                
                # Weight is significantly non-zero (bird or drift)
                else:
                    low_weight_count = 0
                
                # Emergency tare on negative values (drift)
                if weight < -2.0:
                    print("NEGATIVE_RETARE")
                    new_tare = take_reading(hx, samples=10)
                    if new_tare:
                        tare_value = new_tare
                        print("RETARED:{:.2f}".format(new_tare))
                    low_weight_count = 0
            else:
                print("ERROR:NO_READING")
        
        except Exception as e:
            print("ERROR:{}".format(str(e)))
        
        time.sleep(0.1)

if __name__ == "__main__":
    main()
