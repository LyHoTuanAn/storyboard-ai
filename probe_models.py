"""
Dò xem key Gemini hiện tại dùng được model nào, và model nào bị chặn vì quota/tier.

Chạy:  .venv/bin/python probe_models.py
Đọc GEMINI_API_KEY từ genai-pipeline/.env
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "genai-pipeline"))

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "genai-pipeline", ".env"))

key = os.getenv("GEMINI_API_KEY")
if not key:
    sys.exit("Chua co GEMINI_API_KEY trong genai-pipeline/.env")

client = genai.Client(api_key=key)

# ---------- 1. Liet ke model key nay nhin thay ----------
print("=" * 70)
print("MODEL KEY NAY TRUY CAP DUOC")
print("=" * 70)
names = []
try:
    for m in client.models.list():
        n = m.name.replace("models/", "")
        names.append(n)
        print(f"  {n}")
except Exception as e:
    print(f"  Khong liet ke duoc: {e}")

# ---------- 2. Thu goi that, moi loai 1 lan ----------
def probe(label, fn):
    print(f"\n--- {label} ---")
    try:
        fn()
        print("  OK - dung duoc")
    except Exception as e:
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            print("  HET QUOTA / khong co trong free tier")
        elif "NOT_FOUND" in msg or "404" in msg:
            print("  KHONG TON TAI voi key nay")
        elif "PERMISSION" in msg or "403" in msg:
            print("  KHONG CO QUYEN (can bat billing)")
        else:
            print(f"  LOI: {msg[:200]}")

def text(model):
    def f():
        r = client.models.generate_content(model=model, contents="Say OK")
        print(f"  -> {r.text.strip()[:60]}")
    return f

def image(model):
    def f():
        r = client.models.generate_content(
            model=model,
            contents="A simple black line drawing of a circle on a white background.",
        )
        got = any(p.inline_data is not None for p in r.parts)
        if not got:
            raise RuntimeError("khong tra ve anh (chi co text)")
        print("  -> nhan duoc anh")
    return f

def tts(model):
    def f():
        r = client.models.generate_content(
            model=model,
            contents="Hello.",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                    )
                ),
            ),
        )
        part = r.candidates[0].content.parts[0]
        if part.inline_data is None:
            raise RuntimeError("khong tra ve audio")
        print(f"  -> nhan duoc audio ({len(part.inline_data.data)} bytes)")
    return f

print("\n" + "=" * 70)
print("THU GOI THAT")
print("=" * 70)

TEXT_CANDIDATES  = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"]
IMAGE_CANDIDATES = [n for n in names if "image" in n] or ["gemini-2.5-flash-image"]
TTS_CANDIDATES   = [n for n in names if "tts" in n] or ["gemini-2.5-flash-preview-tts"]

for m in TEXT_CANDIDATES:
    probe(f"TEXT  {m}", text(m))
for m in IMAGE_CANDIDATES[:4]:
    probe(f"IMAGE {m}", image(m))
for m in TTS_CANDIDATES[:3]:
    probe(f"TTS   {m}", tts(m))

print("\nXong. Dat model nao bao OK vao genai-pipeline/config.py")
