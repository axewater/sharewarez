# File: /modules/image_utils.py
# This file contains image-related utilities extracted from routes.py

from PIL import Image as PILImage
from PIL import ImageOps

def square_image(image, size):
    return ImageOps.fit(image, (size, size), PILImage.ANTIALIAS)