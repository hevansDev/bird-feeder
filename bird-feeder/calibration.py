import time
import RPi.GPIO as GPIO
from hx711 import HX711

def get_stable_reading(hx, samples_per_reading=5):
    """Get a stable reading by taking multiple samples and filtering outliers"""
    readings = []
    
    for i in range(samples_per_reading):
        reading = hx.get_weight(1)
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
hx = HX711(5, 6)
hx.set_reading_format("MSB", "MSB")
hx.set_reference_unit(1)
hx.reset()

print("Calibration starting...")
print("Remove all weight from scale and press Enter to tare...")
input()
hx.tare()
print("Tare complete!")

# Configuration
num_readings = 30  # Number of stable readings to collect
samples_per_reading = 10  # Samples per stable reading

print(f"\nPlace known weight on scale and enter its weight in grams: ", end="")
known_weight = float(input())

print(f"\nCollecting {num_readings} stable readings...")
print("Each reading uses {samples_per_reading} samples with outlier filtering")
print("-" * 60)

stable_readings = []
for i in range(num_readings):
    stable_reading = get_stable_reading(hx, samples_per_reading)
    stable_readings.append(stable_reading)
    print(f"Reading {i+1:2d}: {stable_reading:8.2f}")
    time.sleep(0.1)

print("-" * 60)

# Remove outliers from the stable readings (more aggressive filtering)
stable_readings.sort()
outliers_to_remove = max(2, num_readings // 5)  # Remove at least 2, or 20%
final_readings = stable_readings[outliers_to_remove:-outliers_to_remove]

# Calculate statistics
average = sum(final_readings) / len(final_readings)
reference_unit = average / known_weight

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
print(f"\nReference unit: {reference_unit:.6f}")

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

print(f"\nAdd this to your script:")
print(f"hx.set_reference_unit({reference_unit:.6f})")

# Test the calibration
print(f"\nTesting calibration...")
hx.set_reference_unit(reference_unit)
test_reading = get_stable_reading(hx, 10)
error_percent = abs((test_reading - known_weight) / known_weight) * 100

print(f"Test reading: {test_reading:.2f}g (expected: {known_weight}g)")
print(f"Error: {error_percent:.1f}%")

if error_percent < 2:
    print("✅ Calibration successful!")
elif error_percent < 5:
    print("⚠️  Calibration acceptable but could be better")
else:
    print("❌ Calibration poor - check connections and try again")

GPIO.cleanup()