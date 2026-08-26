# Web UI

## Chay lan dau

Tu thu muc goc cua repo. Buoc dau tien la tao moi truong ao Python va cai
thu vien; moi lenh Python phia sau deu chay bang `.venv/bin/...`, khong dung
`python` he thong.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd web/frontend && npm install && npm run build && cd ../..
.venv/bin/uvicorn web.server:app --port 8000
```

Mo http://127.0.0.1:8000

`requirements.txt` gom ca thu vien cua pipeline (google-genai, opencv...) va
cua tang web (fastapi, uvicorn, pydantic). Neu chi muon chay giao dien o che
do gia lap (xem duoi) thi pipeline khong duoc goi toi, nhung cach cai van la
mot lenh nhu tren.

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
de thu luong chinh (tao job, xem log realtime, xem scene, huy job) truoc khi
co GEMINI_API_KEY that. Luu y: giao dien chua co nut xoa job, nen buoc xoa
chi thu duoc bang API (`DELETE /api/jobs/{id}`), khong thu duoc tu man hinh.

Bien phu tro khi thu:

- `SB_FAKE_SLEEP=30` - keo dai job de thu nut Huy.
- `SB_FAKE_SKIP_SCENE=2` - gia lap mot scene bi bo qua (scene 2 trong vi du nay).

## Bien moi truong

| Bien | Mac dinh | Viec |
|---|---|---|
| SB_MAX_CONCURRENT | 1 | So job chay song song |
| SB_JOBS_DIR | output/jobs | Noi chua job |
| SB_REPO_ROOT | (thu muc repo) | Goc du lieu du an: noi tim `genai-pipeline/.env` va `output/`. Chi dung cho test; khong can dat khi chay that |
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
chi doc `SB_MAX_CONCURRENT`, `SB_JOBS_DIR`, `SB_REPO_ROOT`, `SB_HOST`,
`SB_PORT`.

## Xu ly su co

**Thay banner canh bao o dau trang.**
Day la health check (`GET /api/health`), no phat hien mot trong hai van de:
khong tim thay `ffmpeg` tren PATH, hoac `genai-pipeline/.env` khong co
`GEMINI_API_KEY`. Thieu ffmpeg thi cac buoc truoc (nghien cuu, sinh anh, sinh
audio) van chay binh thuong, job chi hong o buoc ghep video cuoi cung. Thieu
key server thi van tao va chay job duoc binh thuong, chi can dan key rieng
cua ban vao o "API key rieng (tuy chon)" tren form; key do chi dung cho job
vua tao va khong luu lai.

**Mot job dung mai o "Cho luot", khong bao gio chay.**
So job dang o trang thai "Dang chay" da cham `SB_MAX_CONCURRENT` (mac dinh
1). Xem danh sach "Lan chay" o giao dien de biet job nao dang chiem cho. Job
dang cho se tu chay tiep sau khi mot job dang chay ket thuc (xong, hong, hay
bi huy) - khong can lam gi them, nhung khong phai ngay lap tuc: server chay
mot vong lap nen (background task) rieng, moi 3 giay kiem tra hang doi mot
lan, nen ban co the doi toi 3 giay sau khi job truoc ket thuc thi job tiep
theo moi bat dau. Neu ban vua tao hoac vua huy mot job khac trong luc do,
hang doi cung duoc kiem tra ngay lap tuc nhu mot tac dung phu cua thao tac
do, khong can doi vong lap nen. Muon nhieu job chay song song hon thi dat
`SB_MAX_CONCURRENT` cao hon roi khoi dong lai server; bien nay chi duoc doc
mot lan luc server khoi dong, doi gia tri trong luc server dang chay khong
co tac dung.

Mot truong hop khac: job dung key rieng ban nhap tren form, va server da
khoi dong lai trong luc job con dang cho. Key rieng chi duoc giu trong bo
nho server, khong bao gio ghi xuong dia, nen sau khi restart no khong con -
job do se chuyen sang "Hong" kem loi giai thich, thay vi cho mai mai. Tao
lai job voi key la xong.

**Mot job hien "Bi ngat".**
Tien trinh thuc su chay job da chet ma khong tu bao ket qua (vi du server bi
restart giua chung, hoac tien trinh bi kill tu ben ngoai). Server phat hien
va gan trang thai nay khi vong "quet don" cac job mo coi chay: luc server
khoi dong, moi 3 giay mot lan trong vong lap nen rut hang doi, va them mot
lan nua nhu tac dung phu cua moi lan tao hoac huy job. Tuc la khong can lam
gi de mot job mo coi duoc phat hien, cham nhat khoang 3 giay.

Server nhan dien tien trinh cua job bang CA hai thu: so PID va thoi diem
tien trinh do bat dau. He dieu hanh tai su dung PID, nen chi so PID thoi la
khong du - sau khi server khoi dong lai, mot PID cu co the da thuoc ve tien
trinh khac. Neu thoi diem bat dau khong khop (hoac ban ghi cu chua luu gia
tri nay), job duoc coi la "Bi ngat" va nha cho chay ra, va nut Huy se khong
ban tin hieu vao PID do.

**Mot job hien "Loi file".**
File `job.json` cua job do khong doc duoc (dia hong, bi sua tay, ghi do dang
luc doc trung...). Ban ghi trang thai khong con doc duoc, nhung anh/audio/
video da sinh ra truoc do van con nguyen tren dia, trong thu muc cua job
(`SB_JOBS_DIR/<job_id>/`). Luu y: giao dien hien tai chua co nut xoa cho bat
ky job nao, kha nang xoa moi chi ton tai o API `DELETE /api/jobs/{id}`. API
do xoa duoc job "Loi file" (cung nhu job da xong/hong/da huy/bi ngat), chi
tu choi job dang cho hoac dang chay - huy truoc roi xoa. Neu khong muon dung
API, cu xoa thu muc cua job bang tay.

**Nhat ky ngung cap nhat giua chung mot job dai.**
Ket noi SSE (luong su kien) tu dong dong sau khoang 10 phut khong co dong
log moi nao - day khong phai loi. Giao dien hien mot dong thong bao nho
("Chua co cap nhat moi mot luc. Ket noi van dang lang nghe va se tu cap
nhat.") va trinh duyet tu ket noi lai, tiep tuc dung cho ma khong mat dong
nao da nhan truoc do. Binh thuong gap khi mot buoc sinh video keo dai (vi du
Veo).

**Khong thay gi chay ca, nhat ky chi hien khi job da xong het.**
Day la trieu chung cua viec Python dem (buffer) dau ra thay vi ghi ngay.
Tien trinh chay job duoc mo voi co `-u` (tat buffer) chinh de tranh dieu
nay; neu co nay bi bo di, dau ra se bi giu trong buffer va chi thuc su duoc
ghi xuong file log khi tien trinh ket thuc, khien toan bo SSE im lang cho
toi luc do.
