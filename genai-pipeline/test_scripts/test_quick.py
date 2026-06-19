import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import run_pipeline


if __name__ == "__main__":
    prompt = "What is El Nino and why is monsoon super late in India (strictly 5 scenes)"
    print(f"Testing pipeline with prompt: '{prompt}'")
    final_video = run_pipeline(
        prompt, 
        do_research=False, 
        do_web_search=True, 
        fast_mode=False, 
        language="english",
        enable_veo=True,
        veo_direction_by_director=True
    )
    if final_video:
        print(f"Pipeline SUCCESS! Final Video: {final_video}")
    else:
        print("Pipeline FAILED.")
