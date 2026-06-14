# Storyboard AI

An intelligent agentic pipeline that automates the creation of high-quality, fully narrated whiteboard animation videos from a simple text prompt.

## Overview

Storyboard AI is a complete end-to-end framework. It takes in a high-level topic or context and handles everything: researching the topic, writing a compelling narrative script, planning the visual storyboard, generating custom whiteboard-style artwork, animating the drawing process, synthesizing voiceover narration, and burning perfectly timed subtitles.

It operates autonomously using an agentic approach, meaning the Director Agent breaks down the user request into manageable scenes, delegates tasks to specialized sub-agents/tools, and finally stitches everything back together.

### Demo Video: *What is Adhik Maas and its relation with Shalivahan Shaka (HINDI)  (strictly 4 scenes)*

> [!IMPORTANT]
> The entire demo video below was generated automatically from a **single input prompt/instruction**: the title itself.

https://github.com/user-attachments/assets/433e86bc-7ad4-433b-8b09-117e1f3af9e9

**Major Pipeline Steps Executed:**
1. **Web-search (not deepresearch)**: Performed web-grounded research to gather facts about Adhik Maas and Shalivahan Shaka.
2. **Grounded Image Generation**: Generated custom whiteboard illustrations utilizing internet-grounded reference images for scene visual accuracy.
3. **Whiteboard Animation + Veo**: Segmented objects and calculated vector sketch contours using SAM 3 for custom drawing animation, alongside Veo video generation to stitch dynamic segments.
4. **Gemini Native Audio TTS**: Synthesized high-quality narration audio in Hindi natively.

---

---

## Core Features

- **Full Gemini Stack**: Uses the latest Gemini models for planning (LLM), custom whiteboard image prompt expansion, and narrating (TTS).
- **Web Search & Deep Research Options**: Supports both quick Google Search web grounding and comprehensive Deep Research agents to write highly detailed and factual scripts.
- **Reference Image Grounding**: Automatically searches the web for reference images of real-world entities (e.g., historical figures or landmarks) for each scene and feeds them to the image generator to maintain accurate structural accuracy.
- **Multi-lingual Support**: Prompts the Director, generates script narration, and creates subtitles dynamically across multiple languages (e.g., Hindi, English, Spanish).
- **SAM 3 Integration**: Integrates the state-of-the-art **Segment Anything Model 3** to isolate object boundaries.
- **Custom Animation Engine**: Translates segmented object contours into fluid, custom stroke-by-stroke hand-drawn whiteboard animations.
- **Veo Video Generation Integration**: Optionally integrates with Veo video generation models to insert rich AI-generated video segments dynamically into planned scenes.

---

## ⚡ Key Advantages

- **Grounded & Dynamic Videos**: Requires **only a single text instruction or prompt** to start. The Director Agent autonomously handles research, scriptwriting, scene composition, image/video generation, audio pacing, and compilation.
- **Huge Cost Savings**: Stretches and paces static line-art animations dynamically to match the audio narration length. For example, a 4-scene project requires only 32 seconds of total raw visual sequences (8 seconds * 4 scenes), but the animation engine stretches and times the sketch paths to create a complete, high-quality **2 min 30 sec video** without expensive video-generation API calls.

---

## ⚙️ Setup & Configuration

### 1. Environment Configuration (`.env`)
Create a `.env` file in the `genai-pipeline` folder (or copy `.env.example`) and configure the following variables:

```ini
# Google API Key for LLM, TTS, Image Gen, and Veo Video Gen
GOOGLE_API_KEY="your-google-api-key-here"

# Hugging Face Access Token (Required to download SAM 3 model weights)
HF_API_KEY="your-huggingface-token-here"

# Set to TRUE if using Vertex AI, or FALSE to use Google Developer API (default)
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

### 2. SAM 3 Model Hosting (FastAPI & GCP Cloud Run)
The whiteboard drawing sequence generator depends on instance segmentation. We host a self-contained FastAPI server that wraps the **Segment Anything Model 3 (SAM 3)**.
- For complete setup instructions on obtaining weights, configuring the Docker container, and deploying to Google Cloud Run with GPU accelerators (NVIDIA L4), please refer to the detailed [SAM 3 Hosting Guide](./sam3-hosting/README.md).

### 3. Pipeline Configuration Settings (`config.py`)
Core configuration parameters are set in [genai-pipeline/config.py](./genai-pipeline/config.py):
- **`SAM_API_URL`**: Set this to your deployed SAM 3 Cloud Run endpoint (e.g., `https://sam3-service-xxxx-xx.a.run.app/predict`).
- **`MODEL_NAME`**: The model used for the Director Agent (default: `gemini-2.5-pro`).
- **`IMAGE_GEN_MODEL`**: The image generation model used for drawing line art (default: `gemini-3-pro-image`).
- **`VEO_MODEL`**: The video generation model (default: `veo-3.1-generate-preview`).

### 4. Python Environment & Dependencies
Set up your Python environment (Conda environment recommended) and install the verified dependencies:
- **Core GenAI Pipeline**: Install dependencies via the root [requirements.txt](./requirements.txt).
- **SAM 3 Model Server**: Install dependencies via [sam3-hosting/requirements.txt](./sam3-hosting/requirements.txt) if not using the Docker image.
- *Refer to the [How to Run & View Outputs](#-how-to-run--view-outputs) section below for installation and CLI execution steps.*

---

## 🚀 How to Run & View Outputs

### Step 1: Install Python Dependencies
Depending on the component you are running, install the appropriate requirements:

- **For the Core GenAI Pipeline**:
  Install the main dependencies in your Python/Conda environment using the root [requirements.txt](./requirements.txt):
  ```bash
  pip install -r requirements.txt
  ```

- **For the SAM 3 Self-Hosting Server**:
  If you are running or building the SAM 3 endpoint locally (instead of using the pre-configured [Dockerfile](./sam3-hosting/Dockerfile)), install the dependencies listed in [sam3-hosting/requirements.txt](./sam3-hosting/requirements.txt):
  ```bash
  pip install -r sam3-hosting/requirements.txt
  ```

### Step 2: Run the Pipeline CLI
```bash
# Navigate to the core agent directory
cd genai-pipeline

# Run the interactive pipeline script
python pipeline.py
```

### Step 3: Interactive CLI Setup
The CLI will guide you through:
1. **Context/Prompt**: Enter the main topic for your video (e.g., "The History of Space Travel").
2. **Research Mode**: Choose between `[1]` Deep Research, `[2]` Web Search (Fast), or `[3]` None.
3. **Reference Images**: Enable or disable internet search for visual references (`Y/n`).
4. **Fast Mode**: Enable parallel image/audio generation for all scenes to save time (`Y/n`).
5. **Narration Language**: Enter the target language for the script (e.g., `hindi` or `english`).
6. **Veo Video**: Enable or disable Veo AI video generation (`y/N`).

### Step 4: Locate Outputs
All intermediate assets and final outputs are saved under the `genai-pipeline/output/run_<timestamp>/` folder:
- **`storyboard_final_video.mp4`**: The completed, stitched whiteboard animation video with narration, background drawing paths, and burned subtitles.
- **`scene_<N>/`**: Individual folders for each scene containing the raw generated images, voiceover audio (.mp3), SAM 3 segmentation masks, subtitles, and scene-level sketch videos.

---

## 🏷️ Release v1.0.0

This release marks the official launch of **Storyboard AI v1.0.0**! With this launch, the agentic whiteboard generation pipeline is fully operational with complete end-to-end automation, multimodal asset generation (images, speech pacing, video stitching), and optional GPU-accelerated SAM 3 segments hosting on GCP Cloud Run.

---

## 🗺️ Roadmap & Upcoming Features

We are actively developing new features to expand compatibility and ease of deployment:
- **Broad Model Support (Beyond Gemini)**: Expanding language model coverage starting with **Sarvam AI** support.
- **Standalone Mode (No SAM 3 Server Needed - High Priority)**: 
  - We are building an alternative operating mode that runs without requiring a dedicated SAM 3 endpoint on Google Cloud Run.
  - While this standalone mode will slightly reduce the whiteboard animation drawing paths detail (due to simplified segmentation/edge detection logic), it will allow users to run the entire project out-of-the-box using **only a Gemini AI Studio API key**.

