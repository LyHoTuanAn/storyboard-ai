import os
import time
import subprocess
from google.genai import types
from config import VEO_MODEL
from . import utils

def generate_video_veo_tool_fn(image_path: str, prompt: str) -> str:
    """
    Generates an 8-second whiteboard animation video using Veo based on an input image and prompt.
    
    Args:
        image_path: Absolute path to the input image (representing the first frame).
        prompt: Scene information text prompt to animate.
        
    Returns:
        The path to the generated MP4 video or an error message.
    """
    if not utils.client:
        return "Error: GEMINI_API_KEY not configured."

    if not os.path.exists(image_path):
        return f"Error: Input image file not found at {image_path}"

    try:
        # Prepend/Append prompts to ensure clean whiteboard video style as requested
        enhanced_prompt = (
            f"Whiteboard animation video showing: {prompt}. "
            "CRITICAL: The generated video MUST be a clean whiteboard animation video with a clean white background, "
            "hand-drawn line drawings/sketches, matching the style and content of the first frame. "
            "DO NOT add any realistic hands, markers, or pens drawing on the screen. Draw only the artwork."
        )
        
        print(f"Reading first frame image bytes from: {image_path}")
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        mime_type = "image/png"
        if image_path.lower().endswith((".jpg", ".jpeg")):
            mime_type = "image/jpeg"

        print(f"Initiating Veo video generation using model {VEO_MODEL}...")
        operation = utils.client.models.generate_videos(
            model=VEO_MODEL,
            prompt=enhanced_prompt,
            image=types.Image(image_bytes=img_bytes, mime_type=mime_type),
            config=types.GenerateVideosConfig(
                aspect_ratio="16:9",
                duration_seconds=8,
                resolution="720p"
            )
        )

        print("Polling Veo operation for completion...")
        while not operation.done:
            print("Waiting for Veo video generation to complete (polling every 15s)...")
            time.sleep(15)
            operation = utils.client.operations.get(operation)

        if operation.error:
            return f"Error from Veo video generation API: {operation.error}"

        if not operation.response or not operation.response.generated_videos:
            return "Error: Veo completed with no generated videos."

        generated_video = operation.response.generated_videos[0]
        video_file = generated_video.video
        
        video_bytes = None
        if hasattr(video_file, "video_bytes") and video_file.video_bytes:
            print("Extracting video bytes directly from response.")
            video_bytes = video_file.video_bytes
        else:
            # Fallback if video_bytes is not present (though it should be)
            print(f"Downloading generated video file from {getattr(video_file, 'uri', video_file)}...")
            file_ref = video_file
            if hasattr(video_file, "name"):
                file_ref = video_file.name
            elif hasattr(video_file, "uri"):
                file_ref = video_file.uri
            video_bytes = utils.client.files.download(file=file_ref)
        
        timestamp = int(time.time())
        filename = f"veo_video_{timestamp}.mp4"
        output_path = os.path.join(utils.GLOBAL_OUTPUT_DIR, filename) if utils.GLOBAL_OUTPUT_DIR else filename
        
        with open(output_path, "wb") as f:
            f.write(video_bytes)
            
        print(f"Successfully saved Veo video to: {output_path}")

        # 1. Save audio channel separately with the same name of the Veo file (.wav format)
        audio_output_path = output_path.replace(".mp4", ".wav")
        print(f"Extracting/Generating audio to: {audio_output_path}")
        
        extract_audio_cmd = [
            "ffmpeg", "-y",
            "-i", output_path,
            "-vn",
            "-acodec", "pcm_s16le",
            audio_output_path
        ]
        res = subprocess.run(extract_audio_cmd, capture_output=True, text=True)
        
        if res.returncode != 0 or not os.path.exists(audio_output_path) or os.path.getsize(audio_output_path) < 1000:
            print("No audio channel found in Veo video. Generating a silent audio channel...")
            video_dur = utils.get_video_duration(output_path) or 8.0
            silent_audio_cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", "anullsrc=r=24000:cl=mono",
                "-t", str(video_dur),
                "-acodec", "pcm_s16le",
                audio_output_path
            ]
            subprocess.run(silent_audio_cmd, capture_output=True)
            print(f"Successfully generated silent audio track at: {audio_output_path}")
        else:
            print(f"Successfully extracted audio track to: {audio_output_path}")

        # 1b. Delete the audio channel from the veo video (.mp4) itself to make it purely silent
        temp_silent_video = output_path + "_silent.mp4"
        strip_audio_cmd = [
            "ffmpeg", "-y",
            "-i", output_path,
            "-an",
            "-vcodec", "copy",
            temp_silent_video
        ]
        print(f"Stripping audio track from veo video to {temp_silent_video}...")
        subprocess.run(strip_audio_cmd, capture_output=True)
        
        if os.path.exists(temp_silent_video):
            try:
                os.remove(output_path)
                os.rename(temp_silent_video, output_path)
                print(f"Successfully deleted audio channel from veo video at {output_path}")
            except Exception as strip_err:
                print(f"Error replacing video with audio-stripped video: {strip_err}")
                try:
                    import shutil
                    shutil.copy2(temp_silent_video, output_path)
                    os.remove(temp_silent_video)
                    print(f"Successfully copied audio-stripped video to {output_path}")
                except Exception as cp_err:
                    print(f"Error copying audio-stripped video: {cp_err}")

        # 2. Extract first frame of the generated video and replace original reference image (image_path)
        ext = ".png"
        if image_path.lower().endswith((".jpg", ".jpeg")):
            ext = ".jpg"
        temp_first_frame = output_path + "_first_frame" + ext
        extract_frame_cmd = [
            "ffmpeg", "-y",
            "-i", output_path,
            "-vframes", "1",
            "-f", "image2",
            temp_first_frame
        ]
        print(f"Extracting first frame from generated video: {' '.join(extract_frame_cmd)}")
        subprocess.run(extract_frame_cmd, capture_output=True)
        
        if os.path.exists(temp_first_frame):
            if os.path.exists(image_path):
                print(f"Deleting original reference image: {image_path}")
                try:
                    os.remove(image_path)
                except Exception as e:
                    print(f"Error removing original image: {e}")
            try:
                os.rename(temp_first_frame, image_path)
                print(f"Successfully replaced original reference image with first frame of Veo video at {image_path}")
            except Exception as e:
                print(f"Error replacing original image with first frame: {e}")
                # If rename fails due to cross-device link etc, try copy and remove
                try:
                    import shutil
                    shutil.copy2(temp_first_frame, image_path)
                    os.remove(temp_first_frame)
                    print(f"Successfully copied first frame to {image_path}")
                except Exception as cp_err:
                    print(f"Error copying first frame: {cp_err}")

        return output_path

    except Exception as e:
        return f"An error occurred during Veo video generation: {str(e)}"

