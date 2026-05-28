# Storyboard AI

An intelligent agentic pipeline that automates the creation of high-quality, fully narrated whiteboard animation videos from a simple text prompt.

## Overview

Storyboard AI is a complete end-to-end framework. It takes in a high-level topic or context and handles everything: researching the topic, writing a compelling narrative script, planning the visual storyboard, generating custom whiteboard-style artwork, animating the drawing process, synthesizing voiceover narration, and burning perfectly timed subtitles.

It operates autonomously using an agentic approach, meaning the Director Agent breaks down the user request into manageable scenes, delegates tasks to specialized sub-agents/tools, and finally stitches everything back together.

### Demo Video

Here is an example of what Storyboard AI can generate:




https://github.com/user-attachments/assets/0ecebc9c-d983-4d8d-b832-54a3ba53ffb6


---

## Core Internal Technology

The system has been completely redesigned around state-of-the-art multimodal AI and agentic workflows. 

### 1. Agentic Pipeline & LLMs (Gemini)
- **Deep Research & Web Grounding**: Leverages Gemini's deep research models and Google Search tools to pull real-world facts, dates, and historical context into the script automatically.
- **The Director Agent (Gemini 2.5 Pro)**: Acts as the creative writer. It plans the narrative arc, decides the number of scenes, writes the voiceover script, and describes the visual setups.
- **Image Prompter**: Translates director visions into strict whiteboard animation prompts optimized for lines, selective coloring, and white backgrounds.

### 2. Custom Whiteboard Image Generation
- Uses **Gemini Image Models** (like Gemini Flash Image) strictly instructed to produce clean, hand-drawn line art.
- **Reference Grounding**: Automatically searches Wikipedia/Google for real-world entities (e.g., historical figures or places) and feeds them into the image generator to maintain accurate structural subjects in the whiteboard style.

### 3. Instance Segmentation (SAM 3)
- Uses a **SAM 3 Endpoint** deployed on Google Cloud Run.
- The pipeline segments the generated image frames into individual objects. This allows the whiteboard animation script to intelligently draw the scene object-by-object, mimicking a real artist rather than just doing a simple raster scan reveal.

### 4. Whiteboard Animation Engine
- A highly customized OpenCV/Python script that takes an image and its SAM masks, calculates drawing paths (contours and shading lines), and generates a fluid animation of the image being physically sketched onto a whiteboard.

### 5. Audio, TTS & Subtitling
- **Google Cloud TTS / Gemini TTS**: Generates rich, properly paced narrations based on the Director's script.
- **Audio Transcription (Whisper/Similar)**: Transcribes the generated audio to get precise word-level timestamps.
- **Narration Refiner**: An intelligent step that adjusts script pacing if the drawing animation takes significantly longer or shorter than the spoken voiceover.

### 6. FFmpeg Video Stitching
- Handles the complex synchronization of the whiteboard sketch video, the narration audio tracks, and burns the subtitles directly into the final video file (`storyboard_final_video.mp4`).

---

## Quick Start

```bash
# Navigate to the core agent directory
cd genai-pipeline

# Run the pipeline interactive CLI
python pipeline.py
```

The system will prompt you for a context, ask what research mode you want to use, and whether to enable internet image searches for aesthetic references. All output (videos, audio, internal prompts, generated images) is saved under `adk-agent/output/run_<timestamp>/`.
