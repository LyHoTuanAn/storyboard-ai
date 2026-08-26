# Web UI

## Chay lan dau

```bash
cd web/frontend && npm install && npm run build && cd ../..
.venv/bin/uvicorn web.server:app --port 8000
```

Mo http://127.0.0.1:8000

## Che do phat trien

Hai cua so:

```bash
.venv/bin/uvicorn web.server:app --port 8000 --reload
cd web/frontend && npm run dev
```

Vite chay o cong 5173 va proxy /api sang 8000.

## Thu giao dien khi chua co API key

```bash
SB_FAKE_PIPELINE=1 .venv/bin/uvicorn web.server:app --port 8000
```

Pipeline gia lap in log mau va tao file gia, khong goi API nao. Day la cach
de thu toan bo luong (tao job, xem log realtime, xem scene, xoa job) truoc
khi co GEMINI_API_KEY that.

Bien phu tro khi thu:

- `SB_FAKE_SLEEP=30` - keo dai job de thu nut Huy.
- `SB_FAKE_SKIP_SCENE=2` - gia lap mot scene bi bo qua (scene 2 trong vi du nay).

## Bien moi truong

| Bien | Mac dinh | Viec |
|---|---|---|
| SB_MAX_CONCURRENT | 1 | So job chay song song |
| SB_JOBS_DIR | output/jobs | Noi chua job |
| SB_HOST | 127.0.0.1 | Dia chi lang nghe |
| SB_PORT | 8000 | Cong |
| SB_FAKE_PIPELINE | (khong dat) | Dat = 1 de chay pipeline gia lap, khong goi API nao |
| SB_FAKE_SLEEP | 0 | (chi khi SB_FAKE_PIPELINE=1) So giay ngu truoc khi bat dau, de thu nut Huy |
| SB_FAKE_SKIP_SCENE | (khong dat) | (chi khi SB_FAKE_PIPELINE=1) So thu tu scene se gia lap bi bo qua |
| SB_MODEL_NAME | gemini-2.5-pro | Ghi de model Director (genai-pipeline/config.py) |
| SB_IMAGE_GEN_MODEL | gemini-3.1-flash-image | Ghi de model sinh anh (genai-pipeline/config.py) |
| SB_TTS_MODEL | gemini-3.1-flash-tts-preview | Ghi de model TTS (genai-pipeline/config.py) |
| GEMINI_API_KEY | (rong) | Key mac dinh cua server, dat trong genai-pipeline/.env. Nguoi dung cung co the nhap key rieng tren form, chi dung cho job do va khong luu lai. |

Ghi chu: `SB_MODEL_NAME`, `SB_IMAGE_GEN_MODEL`, `SB_TTS_MODEL` doc boi
`genai-pipeline/config.py`, khong phai `web/settings.py`. `web/settings.py`
chi doc `SB_MAX_CONCURRENT`, `SB_JOBS_DIR`, `SB_HOST`, `SB_PORT`.
