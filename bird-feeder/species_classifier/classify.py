"""
UK garden bird species classification, using the secretbatcave
UK-Bird-Classifier models: https://github.com/secretbatcave/Uk-Bird-Classifier

Two models are available (pick via CLASSIFIER_MODEL env var):
  - "large_birds" (default): largeBirds4.pb, 51 species -- covers the common
    UK garden birds (robin, wren, blue tit, chaffinch, wood pigeon, house
    sparrow, jackdaw, nuthatch, blackbird, etc.)
  - "uk_garden": ukGardenModel.pb, a lighter 12-species model (squirrel,
    crow, wren, pigeon, cat, house sparrow, magpie, blackbird, dunnock,
    chaffinch, song thrush, robin)

Photos are cropped to the detected bird (see detect_and_crop.py) before
classification -- both models were trained on tightly-cropped images, and
skipping this step significantly hurts accuracy on our wide feeder shots.

Model files are not committed to this repo -- run download_models.sh first.
"""

import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import cv2
import numpy as np
import tensorflow.compat.v1 as tf

tf.disable_v2_behavior()

from .detect_and_crop import crop_to_bird

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

_MODEL_FILES = {
    "large_birds": ("largeBirds4.pb", "largeBirds4_labels.txt"),
    "uk_garden": ("ukGardenModel.pb", "ukGardenModel_labels.txt"),
}

_loaded = {}  # model_name -> (session, labels)


def _load_model(model_name):
    if model_name in _loaded:
        return _loaded[model_name]

    if model_name not in _MODEL_FILES:
        raise ValueError(
            f"Unknown CLASSIFIER_MODEL '{model_name}', expected one of "
            f"{list(_MODEL_FILES)}"
        )

    pb_name, labels_name = _MODEL_FILES[model_name]
    pb_path = os.path.join(_MODEL_DIR, pb_name)
    labels_path = os.path.join(_MODEL_DIR, labels_name)

    if not (os.path.exists(pb_path) and os.path.exists(labels_path)):
        raise FileNotFoundError(
            f"Classifier model files not found in {_MODEL_DIR}. "
            "Run species_classifier/download_models.sh first."
        )

    with open(labels_path) as f:
        labels = [line.strip() for line in f.readlines()]

    graph = tf.Graph()
    with graph.as_default():
        with tf.io.gfile.GFile(pb_path, "rb") as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())
            tf.import_graph_def(graph_def, name="")
    session = tf.Session(graph=graph)

    _loaded[model_name] = (session, labels)
    return session, labels


def classify_photo(image_path, model_name=None, top_k=3):
    """
    Classify the bird species in a photo.

    Args:
        image_path: path to a JPEG/PNG image containing (ideally) one bird
        model_name: "large_birds" or "uk_garden" -- defaults to the
            CLASSIFIER_MODEL env var, or "large_birds" if unset
        top_k: how many top predictions to include in the result

    Returns:
        {
            "species": <top predicted label, str>,
            "confidence": <top prediction's probability, 0-1 float>,
            "top_k": [(label, probability), ...],
            "cropped": <bool, whether a bird was detected and cropped to>,
            "model": <model_name used>,
        }
    """
    model_name = model_name or os.getenv("CLASSIFIER_MODEL", "large_birds")
    session, labels = _load_model(model_name)

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    cropped_image, was_cropped = crop_to_bird(image)
    success, encoded = cv2.imencode(".jpg", cropped_image)
    if not success:
        raise RuntimeError("Failed to encode cropped image for classification")
    image_bytes = encoded.tobytes()

    predictions = session.run(
        "final_result:0", {"DecodeJpeg/contents:0": image_bytes}
    )[0]

    top_indices = np.argsort(predictions)[-top_k:][::-1]
    top_k_results = [(labels[i], float(predictions[i])) for i in top_indices]

    return {
        "species": top_k_results[0][0],
        "confidence": top_k_results[0][1],
        "top_k": top_k_results,
        "cropped": was_cropped,
        "model": model_name,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m species_classifier.classify path/to/photo.jpg")
        sys.exit(1)

    result = classify_photo(sys.argv[1])
    print(f"Species: {result['species']} ({result['confidence']:.1%})")
    print(f"Cropped to detected bird: {result['cropped']}")
    print("Top candidates:")
    for label, prob in result["top_k"]:
        print(f"  {label}: {prob:.1%}")
