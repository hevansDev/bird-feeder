import time
from machine import Pin
from hx711 import hx711

def get_stable_reading(hx, samples_per_reading=5):
    """Get a stable reading by taking multiple samples and filtering outliers"""
    readings = []
    
    for i in range(samples_per_reading):
        reading = hx.get_value()
        if reading:
            readings.append(reading)
        time.sleep(0.05)
    
    # Sort and remove outliers
    readings.sort()
    if len(readings) >= 3:
        # Remove top and bottom reading
        trimmed = readings[1:-1]
    else:
        trimmed = readings
    
    return sum(trimmed) / len(trimmed)

# Setup HX711
print("Setting up HX711...")
hx = hx711(Pin(14), Pin(15))  # Clock on GP14, Data on GP15
hx.set_power(hx711.power.pwr_up)
hx.set_gain(hx711.gain.gain_128)
hx711.wait_settle(hx711.rate.rate_10)

print("Calibration starting...")
print("Remove all weight from scale and press Enter to tare...")
time.sleep(10)

# Get tare value
print("Taking tare readings...")
tare_readings = []
for i in range(10):
    val = hx.get_value()
    if val:
        tare_readings.append(val)
    time.sleep(0.05)

tare_value = sum(tare_readings) / len(tare_readings)
print(f"Tare complete! Tare value: {tare_value:.2f}")

# Configuration
num_readings = 30  # Number of stable readings to collect
samples_per_reading = 10  # Samples per stable reading

print(f"\nPlace known weight on scale and enter its weight in grams: ", end="")
known_weight = float(100)
time.sleep(10)

print(f"\nCollecting {num_readings} stable readings...")
print(f"Each reading uses {samples_per_reading} samples with outlier filtering")
print("-" * 60)

stable_readings = []
for i in range(num_readings):
    stable_reading = get_stable_reading(hx, samples_per_reading)
    # Subtract tare value
    tared_reading = stable_reading - tare_value
    stable_readings.append(tared_reading)
    print(f"Reading {i+1:2d}: {tared_reading:8.2f}")
    time.sleep(0.1)

print("-" * 60)

# Remove outliers from the stable readings (more aggressive filtering)
stable_readings.sort()
outliers_to_remove = max(2, num_readings // 5)  # Remove at least 2, or 20%
final_readings = stable_readings[outliers_to_remove:-outliers_to_remove]

# Calculate statistics
average = sum(final_readings) / len(final_readings)
calibration_factor = average / known_weight

# Calculate standard deviation for quality assessment
variance = sum((x - average) ** 2 for x in final_readings) / len(final_readings)
std_dev = variance ** 0.5

print(f"\nCalibration Results:")
print(f"Known weight: {known_weight}g")
print(f"Total readings collected: {num_readings}")
print(f"Readings used (after outlier removal): {len(final_readings)}")
print(f"Average reading: {average:.2f}")
print(f"Standard deviation: {std_dev:.2f}")
print(f"Coefficient of variation: {(std_dev/abs(average))*100:.1f}%")
print(f"\nTare value: {tare_value:.2f}")
print(f"Calibration factor: {calibration_factor:.6f}")

# Quality assessment
cv_percent = (std_dev/abs(average))*100
if cv_percent < 1:
    quality = "Excellent"
elif cv_percent < 3:
    quality = "Good"
elif cv_percent < 5:
    quality = "Fair"
else:
    quality = "Poor - consider using shielded cable"

print(f"Calibration quality: {quality}")

print(f"\nAdd these to your script:")
print(f"TARE_VALUE = {tare_value:.2f}")
print(f"CALIBRATION_FACTOR = {calibration_factor:.6f}")

# Test the calibration
print(f"\nTesting calibration...")
test_raw = get_stable_reading(hx, 10)
test_reading = (test_raw - tare_value) / calibration_factor

error_percent = abs((test_reading - known_weight) / known_weight) * 100
print(f"Test reading: {test_reading:.2f}g (expected: {known_weight}g)")
print(f"Error: {error_percent:.1f}%")

if error_percent < 2:
    print("✅ Calibration successful!")
elif error_percent < 5:
    print("⚠️  Calibration acceptable but could be better")
else:
    print("❌ Calibration poor - check connections and try again")

# Clean up
hx.close()
print("\nCalibration complete!")
