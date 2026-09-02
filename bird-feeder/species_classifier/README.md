# Species classifier

Identifies the bird species in feeder photos, using the
[secretbatcave UK-Bird-Classifier](https://github.com/secretbatcave/Uk-Bird-Classifier)
models plus an automatic crop-to-bird preprocessing step.

## Why the crop step

The classifier models were trained on images tightly cropped to the bird.
The author's own writeup on
[this project](https://www.secretbatcave.co.uk/projects/classifying-birds/)
found that uncropped training photos caused the model to key on background
(grass, sky) instead of the bird. Our feeder photos are wide shots through
a plastic dome cover, so the bird is often a small part of the frame.
`detect_and_crop.py` runs a small MobileNet-SSD detector (trained on PASCAL
VOC, which includes a "bird" class) to find and crop to the bird before
classification. If no bird is detected, the original frame is used as a
fallback.

In testing, adding this crop step took a blurry/close Robin photo from 70%
confidence to 90%+ confidence with both classifier models, with no
downside on photos that were already well-framed.

## Setup

```bash
cd bird-feeder/species_classifier
pip install -r requirements.txt
./download_models.sh   # fetches ~190MB of model files, not committed to git
```

## Usage

Standalone:

```bash
python -m species_classifier.classify path/to/photo.jpg
```

From code:

```python
from species_classifier.classify import classify_photo

result = classify_photo("path/to/photo.jpg")
print(result["species"], result["confidence"])
```

## Choosing a model

Set `CLASSIFIER_MODEL` to switch between the two bundled models:

- `large_birds` (default) -- 51 species, covers most common UK garden birds
  (robin, wren, blue tit, chaffinch, wood pigeon, house sparrow, jackdaw,
  nuthatch, blackbird, and more).
- `uk_garden` -- a lighter 12-species model (squirrel, crow, wren, pigeon,
  cat, house sparrow, magpie, blackbird, dunnock, chaffinch, song thrush,
  robin).

## Enabling in the main feeder script

Set `SPECIES_CLASSIFICATION_ENABLED=true` in your `.env` (see
`bird-feeder/main.py`). When enabled, each captured photo is classified
and the result is attached to the Kafka message and cloud-upload metadata
as `species` / `speciesConfidence`. Classification failures are caught and
logged -- they never block a photo capture or upload.

## Accuracy notes

This is not a perfect classifier. It hasn't been validated against a
labeled set of your own feeder photos, only spot-checked against a
handful of sample images. Species outside the training list (see the
labels files) can't be recognized at all. Treat `species` as a
best-effort tag, not ground truth.
