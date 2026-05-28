from pipeline import run_pipeline

if __name__ == "__main__":
    prompt = "Please sing a song in hindi praising: Jai Hanuman. "
    print(f"Testing pipeline with prompt: '{prompt}'")
    final_video = run_pipeline(prompt, do_research=False, do_web_search=False, fast_mode=True)
    if final_video:
        print(f"Pipeline SUCCESS! Final Video: {final_video}")
    else:
        print("Pipeline FAILED.")
