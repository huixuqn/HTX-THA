import time
from pathlib import Path
from PIL import Image
from typing import Tuple, Dict, Any


SMALL_SIZE = (256, 256)
MEDIUM_SIZE = (512, 512)

ORIGINALS_DIR = Path("data") / "originals"
THUMBS_DIR = Path("data") / "thumbs"


def ensure_dirs() -> None:
    ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)


def make_thumbnails(image_path: Path, image_id: str) -> Tuple[str, str]:
    """
    Returns (small_thumb_path, medium_thumb_path) as strings.
    """
    ensure_dirs()
    small_path = THUMBS_DIR / f"{image_id}_small.jpg"
    medium_path = THUMBS_DIR / f"{image_id}_medium.jpg"

    with Image.open(image_path) as im:
        im = im.convert("RGB")

        small = im.copy()
        small.thumbnail(SMALL_SIZE)
        small.save(small_path, format="JPEG", quality=85)

        medium = im.copy()
        medium.thumbnail(MEDIUM_SIZE)
        medium.save(medium_path, format="JPEG", quality=90)

    return str(small_path), str(medium_path)


def extract_metadata(image_path: Path, size_bytes: int) -> Dict[str, Any]:
    with Image.open(image_path) as im:
        return {
            "width": im.width,
            "height": im.height,
            "format": (im.format or "").upper(),
            "size_bytes": size_bytes,
        }


from functools import lru_cache
from transformers import BlipProcessor, BlipForConditionalGeneration
import torch

@lru_cache(maxsize=1)
def _load_blip():
    # Loads once per process; cached so background tasks don't reload every time
    model_id = "Salesforce/blip-image-captioning-base"
    processor = BlipProcessor.from_pretrained(model_id)
    model = BlipForConditionalGeneration.from_pretrained(model_id)
    model.eval()
    return processor, model

def generate_caption_local(image_path: Path) -> str:
    processor, model = _load_blip()
    with Image.open(image_path) as im:
        im = im.convert("RGB")

    # Prompt to reduce hallucinated context

    prompt = "Describe only what is visually present in this image."

    inputs = processor(
        images=im,
        text=prompt,
        return_tensors="pt"
    )

    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=20,
            do_sample=False,
            num_beams=3,
            repetition_penalty=1.2
        )

    caption = processor.decode(out[0], skip_special_tokens=True).strip()

    # Remove the prompt if it appears in output
    if caption.lower().startswith(prompt.lower()):
        caption = caption[len(prompt):].strip(" .:")

    return caption or "No caption generated."

