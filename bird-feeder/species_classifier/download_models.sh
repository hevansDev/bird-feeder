#!/usr/bin/env bash
# Downloads the model files needed by species_classifier/.
# Not committed to git -- these are ~190MB combined.
set -euo pipefail

MODEL_DIR="$(dirname "$0")/models"
mkdir -p "$MODEL_DIR"
cd "$MODEL_DIR"

echo "Downloading secretbatcave UK-Bird-Classifier models..."
curl -sL -o largeBirds4.pb "https://raw.githubusercontent.com/secretbatcave/Uk-Bird-Classifier/master/models/largeBirds4.pb"
curl -sL -o largeBirds4_labels.txt "https://raw.githubusercontent.com/secretbatcave/Uk-Bird-Classifier/master/models/largeBirds4_labels.txt"
curl -sL -o ukGardenModel.pb "https://raw.githubusercontent.com/secretbatcave/Uk-Bird-Classifier/master/models/ukGardenModel.pb"
curl -sL -o ukGardenModel_labels.txt "https://raw.githubusercontent.com/secretbatcave/Uk-Bird-Classifier/master/models/ukGardenModel_labels.txt"

echo "Downloading MobileNet-SSD bird detector (for cropping)..."
curl -sL -o deploy.prototxt "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt"
curl -sL -o mobilenet_iter_73000.caffemodel "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel"

echo "Done. Model files are in $MODEL_DIR"
