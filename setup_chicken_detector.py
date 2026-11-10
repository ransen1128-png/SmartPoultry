"""Download the separate detector explicitly, never from a page request."""
from pathlib import Path
import os

root = Path(__file__).resolve().parent
os.environ.setdefault('HF_HOME', str(root / '.cache-huggingface'))

from transformers import OwlViTProcessor, OwlViTForObjectDetection

destination = root / 'ml_models' / 'chicken_owlvit'
checkpoint = 'google/owlvit-base-patch32'
OwlViTProcessor.from_pretrained(checkpoint).save_pretrained(destination)
OwlViTForObjectDetection.from_pretrained(checkpoint).save_pretrained(destination)
print(f'Detector saved to {destination}. Restart Django to load it.')
