import os
import time
from google.genai import types
from config import TTS_MODEL
from . import utils

def generate_tts_audio_tool_fn(text: str, speaker_one: str = None, speaker_two: str = None, language: str = "english") -> str:
    """
    Generates high-quality TTS audio from text using Gemini 2.5 Flash TTS.
    Supports up to 2 speakers for conversational text.
    
    Args:
        text: The text to convert to speech. Use 'Speaker: text' format for multi-speaker.
        speaker_one: Optional name of the first speaker (e.g., 'Joe').
        speaker_two: Optional name of the second speaker (e.g., 'Jane').
        language: The target language of the text to read (default: English).
    Returns:
        The path to the generated .wav file or an error message.
    """
    if not utils.client:
        return "Error: GEMINI_API_KEY not configured."

    print(f"Generating TTS for: {text[:50]}...")

    try:
        # Determine if we should use MultiSpeakerVoiceConfig
        speech_config = None
        if speaker_one or speaker_two:
            speaker_voice_configs = []
            if speaker_one:
                speaker_voice_configs.append(
                    types.SpeakerVoiceConfig(
                        speaker=speaker_one,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Kore')
                        )
                    )
                )
            if speaker_two:
                speaker_voice_configs.append(
                    types.SpeakerVoiceConfig(
                        speaker=speaker_two,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Puck')
                        )
                    )
                )
            
            speech_config = types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=speaker_voice_configs
                )
            )
        else:
            # Single speaker default
            speech_config = types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Kore')
                )
            )

        prompt_text = (
            f"[narration style: stable, excited, expressive storytelling, speaking in {language}, consistent high volume, no whispering]\n"
            f"{text}"
        )

        response = utils.client.models.generate_content(
            model=TTS_MODEL,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_config,
            )
        )

        # Extract audio data
        if not response.candidates or not response.candidates[0].content.parts:
            return "Error: No audio generated in response candidates."
        
        audio_part = response.candidates[0].content.parts[0]
        if audio_part.inline_data is None:
            return "Error: No inline audio data found in the response."

        data = audio_part.inline_data.data
        
        timestamp = int(time.time())
        filename = f"generated_audio_{timestamp}.wav"
        output_path = os.path.join(utils.GLOBAL_OUTPUT_DIR, filename) if utils.GLOBAL_OUTPUT_DIR else filename
        
        if utils.save_pcm_to_wav(output_path, data):
            print(f"TTS audio generated and saved to: {output_path}")
            return output_path
        
        return "Error: Failed to save wave file."

    except Exception as e:
        return f"An error occurred during TTS generation: {str(e)}"
