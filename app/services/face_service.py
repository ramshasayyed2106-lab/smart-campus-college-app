import base64
import io
import pickle

import face_recognition
import numpy as np
from PIL import Image


def _decode_image(data_url):
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    raw = base64.b64decode(data_url)
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    return np.array(image)


def get_face_encoding(data_url):
    # Create exactly one face embedding from a camera image.
    image = _decode_image(data_url)
    locations = face_recognition.face_locations(image, model="hog")

    if len(locations) != 1:
        raise ValueError("Exactly one face must be visible.")

    encodings = face_recognition.face_encodings(image, locations)
    if not encodings:
        raise ValueError("Could not create a face encoding.")

    return encodings[0]


def create_face_encoding(data_url):
    return pickle.dumps(
        get_face_encoding(data_url),
        protocol=pickle.HIGHEST_PROTOCOL
    )


def verify_face(data_url, stored_encoding, tolerance=0.48):
    live_encoding = get_face_encoding(data_url)
    known = pickle.loads(stored_encoding)
    distance = face_recognition.face_distance([known], live_encoding)[0]
    return float(distance) <= tolerance


def is_face_unique(data_url, stored_encodings, tolerance=0.48):
    # 1:N uniqueness check across all registered student faces.
    new_encoding = get_face_encoding(data_url)

    for stored in stored_encodings:
        try:
            known = pickle.loads(stored)
            distance = float(
                face_recognition.face_distance([known], new_encoding)[0]
            )
            if distance <= tolerance:
                return False
        except Exception:
            continue

    return True
