import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Models
# User referred to "flash3", likely meaning the latest Gemini 2.0 Flash
MODEL_NAME = "gemini-2.5-pro" 
# Deep Research Model
DEEP_RESEARCH_MODEL = "deep-research-preview-04-2026"
# Image Generation Model
# IMAGE_GEN_MODEL = "gemini-2.5-flash-image"
IMAGE_GEN_MODEL = "gemini-3-pro-image"
# TTS Model
TTS_MODEL = "gemini-3.1-flash-tts-preview"
# Veo Video Generation Model
VEO_MODEL = "veo-3.1-generate-preview"
# SAM Segmentation Model URL
SAM_API_URL = "https://sam3-app-1040077537378.us-east4.run.app/predict"

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in environment variables.")
