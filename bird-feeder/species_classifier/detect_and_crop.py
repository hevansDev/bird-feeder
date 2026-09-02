"""
Bird localization for the species classifier.

The secretbatcave UK-Bird-Classifier models (see classify.py) were trained
on images tightly cropped to the bird -- the author's own writeup
(https://www.secretbatcave.co.uk/projects/classifying-birds/) explains that
uncropped photos confuse the model into keying on background (grass, sky)
rather than the bird. Our feeder photos are wide shots of the whole feeder
through a plastic dome, so the bird is often a small fraction of the frame.

This module runs a small, generic object detector (MobileNet-SSD, trained
on PASCAL VOC, which includes a "bird" class) to find the bird's bounding
box and crop to it (with padding) before classification. If no bird is
detected, the original full frame is returned unchanged so classification
still runs (just less accurately).

Model files are not committed to this repo -- run download_models.sh first.
"""

import os

import cv2
import numpy as np

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
_PROTOTXT = os.path.join(_MODEL_DIR, "deploy.prototxt")
_CAFFEMODEL = os.path.join(_MODEL_DIR, "mobilenet_iter_73000.caffemodel")

_VOC_CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus",
    "car", "cat", "chair", "cow", "diningtable", "dog", "horse", "motorbike",
    "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor",
]
_BIRD_CLASS_ID = _VOC_CLASSES.index("bird")

_net = None


def _get_net():
    global _net
    if _net is None:
        if not (os.path.exists(_PROTOTXT) and os.path.exists(_CAFFEMODEL)):
            raise FileNotFoundError(
                f"Detector model files not found in {_MODEL_DIR}. "
                "Run species_classifier/download_models.sh first."
            )
        _net = cv2.dnn.readNetFromCaffe(_PROTOTXT, _CAFFEMODEL)
    return _net


def detect_bird_box(image, conf_thresh=0.15):
    """
    Find the highest-confidence bird bounding box in an image.

    Args:
        image: a BGR numpy array (as returned by cv2.imread / cv2.VideoCapture)
        conf_thresh: minimum detector confidence to accept a box

    Returns:
        (confidence, (x1, y1, x2, y2)) for the best bird detection, or None
        if no bird was detected above conf_thresh.
    """
    net = _get_net()
    h, w = image.shape[:2]
    blob = cv2.dnn.blobFromImage(
        image, 0.007843, (300, 300), (127.5, 127.5, 127.5), swapRB=False
    )
    net.setInput(blob)
    detections = net.forward()

    best = None
    for i in range(detections.shape[2]):
        class_id = int(detections[0, 0, i, 1])
        conf = float(detections[0, 0, i, 2])
        if class_id == _BIRD_CLASS_ID and conf > conf_thresh:
            box = detections[0, 0, i, 3:7] * [w, h, w, h]
            if best is None or conf > best[0]:
                best = (conf, box)
    return best


def crop_to_bird(image, pad_frac=0.15, conf_thresh=0.15):
    """
    Crop an image to its detected bird, with padding.

    Args:
        image: a BGR numpy array
        pad_frac: extra padding around the detected box, as a fraction of
            the box's width/height
        conf_thresh: minimum detector confidence to accept a box

    Returns:
        (cropped_image, was_cropped). If no bird is detected, returns the
        original image unchanged and was_cropped=False.
    """
    h, w = image.shape[:2]
    best = detect_bird_box(image, conf_thresh=conf_thresh)
    if best is None:
        return image, False

    _, box = best
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    x1 = max(0, x1 - bw * pad_frac)
    y1 = max(0, y1 - bh * pad_frac)
    x2 = min(w, x2 + bw * pad_frac)
    y2 = min(h, y2 + bh * pad_frac)
    crop = image[int(y1):int(y2), int(x1):int(x2)]
    return crop, True
