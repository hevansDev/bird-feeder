# bird-feeder

This is a super simple bird feeder project that lets you use either a weight sensor, motion detection, or both to automatically snap pictures of birds on your bird feeder and optionally upload them to the cloud.

## Basic Setup

1. Clone repo

```bash
git clone https://github.com/hevansDev/bird-feeder.git
cd bird-feeder/bird-feeder
```

2. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Configure

```bash
cp .env.example .env
nano .env  # Edit with your settings
MOTION_ENABLED=true
MOTION_THRESHOLD=1000  # Adjust based on your environment

# Optional: Upload to community gallery
ENABLE_CLOUD_UPLOAD=true
USER_ID=your_username
FEEDER_LOCATION=Your City, Country
```

5. Run
```bash
python main.py
```

## Setting up the scale

For a full guide on setting up and calibrating the directly attached scale [see my blog on the topic](https://hughevans.dev/load-cell-raspberry-pi/), blog on setting up Pico scale coming soon.

## Settings

### Motion Detection

| Variable | Default | Description |
|----------|---------|-------------|
| `MOTION_ENABLED` | `true` | Enable motion-based detection |
| `MOTION_THRESHOLD` | `1000` | Pixel change threshold (higher = less sensitive) |
| `FRAMES_BEFORE_DEPARTURE` | `10` | Consecutive no-motion frames before "bird left" |
| `DEBUG_MOTION` | `false` | Print motion values for threshold tuning |

### Scale Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SCALE_ENABLED` | `false` | Enable weight-based detection |
| `SCALE_TYPE` | `serial` | `direct` (Pi GPIO) or `serial` (Pico USB) |
| `WEIGHT_THRESHOLD` | `5` | Minimum weight in grams (Goldcrest = 5g) |
| `SCALE_WAIT_TIME` | `1.0` | Seconds to wait for scale reading after motion |

**Direct GPIO Scale:**
| Variable | Default | Description |
|----------|---------|-------------|
| `SCALE_REFERENCE_UNIT` | `-388.929792` | Calibration value from calibration.py |

**Pico Serial Scale:**
| Variable | Default | Description |
|----------|---------|-------------|
| `PICO_SERIAL_PORT` | `/dev/ttyACM0` | USB serial port for Pico |
| `PICO_SERIAL_BAUD` | `115200` | Serial baud rate |
| `PICO_TIMEOUT` | `2.0` | Serial connection timeout |

### Cloud Upload

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_CLOUD_UPLOAD` | `false` | Upload photos to community gallery |
| `UPLOAD_SERVICE_URL` | `https://...` | Cloudflare Worker endpoint (pre-configured) |
| `USER_ID` | `anonymous` | Your unique username for the gallery |
| `FEEDER_LOCATION` | _(empty)_ | City, Country |
| `KAFKA_BROKER_URL` | `kafka-2a015ed7-bird-feeder-free-tier.d.aivencloud.com:19448` | Kafka broker URL for streaming bird data |


**Privacy**: Only photos, timestamps, weights, and location (if provided) are shared. No personal information is collected.

### Camera & Performance

| Variable | Default | Description |
|----------|---------|-------------|
| `CAMERA_WARMUP_FRAMES` | `5` | Frames to skip for auto-adjustment |
| `PHOTO_COOLDOWN` | `5.0` | Minimum seconds between photos |
| `IMAGES_DIR` | `./images` | Local photo storage directory |
| `SENSOR_CHECK_INTERVAL` | `0.2` | Seconds between sensor readings |

## Resources

- The motion detection code in this project is based on [this blog](https://sokacoding.medium.com/simple-motion-detection-with-python-and-opencv-for-beginners-cdd4579b2319) by [sokacoding](https://sokacoding.medium.com/).
- HX711 library: [tatobari/hx711py](https://github.com/tatobari/hx711py)
- Community uploads powered by [Cloudflare Images](https://www.cloudflare.com/products/cloudflare-images/)

# Bird Feeder Upload API

You don't need to deploy this yourself! The community worker is already running at `https://bird-upload-api.hugh-evans-dev.workers.dev` but if you want your own private gallery you can deploy your own by following the instructions in the `cloudflare-worker` dir.

