# Storyboard AI: Web UI (Giai đoạn 1)

Ngày: 2026-08-26
Trạng thái: chờ duyệt

## 1. Mục tiêu

Thay giao diện CLI tương tác của `genai-pipeline/pipeline.py` bằng một web app: nhập
tham số, chạy pipeline, theo dõi tiến trình realtime, xem lại ảnh/audio/video của
từng scene, và quản lý các lần chạy cũ.

Giai đoạn 1 chạy một người trên localhost. Giai đoạn 2 (auth, hàng đợi nhiều người,
hạn mức) không nằm trong spec này, nhưng mọi ranh giới ở đây được cắt để GĐ2 bọc
thêm mà không phải viết lại.

### Ngoài phạm vi

- Đăng nhập, phân quyền, hạn mức theo người dùng
- Điểm dừng duyệt/sửa giữa chừng (xem mục 10)
- Sửa logic pipeline, đổi model, thay nhà cung cấp API
- Tự host SAM 3

## 2. Ràng buộc quyết định thiết kế

**R1. Client Gemini là biến toàn cục lúc import.** `tools/utils.py` tạo
`genai.Client(api_key=GEMINI_API_KEY)` ở cấp module. Mỗi tiến trình Python vì vậy chỉ
ôm được một API key. Muốn mỗi job dùng key riêng thì mỗi job phải là một tiến trình
riêng.

**R2. Pipeline ghi artifact theo thư mục làm việc.** `pipeline.py:81` dùng
`os.path.join(os.getcwd(), "output", f"run_{timestamp}")`. Đặt `cwd` của tiến trình
con thành thư mục job là artifact tự động nằm đúng chỗ, không sửa code.

**R3. Tiến trình đã có sẵn dạng text có cấu trúc.** 66 lệnh `print` trong
`pipeline.py` theo khuôn ổn định:

```
Step 1: Performing Web-Grounded Research (Fast)...
Step 2: Director Planning & Scene Writing...
Director planned 4 scenes. Tone: inspiring, Arc: adventure
--- Processing Scene 2/4 ---
Scene 2: Generating image...
  [X] SKIPPING Scene 2: Image generation failed - no valid image produced.
```

Đủ để dựng thanh tiến trình thật mà không đụng vào pipeline.

**R4. Job chạy nhiều phút và tốn tiền thật.** Phải huỷ được, phải sống sót qua việc
đóng tab, và không được mất log khi mạng đứt.

## 3. Kiến trúc

```
Browser ──POST /api/jobs──► FastAPI (server.py) ──► jobs.py
                                                     │ ghi job.json
                                                     │ Popen(runner.py,
                                                     │       cwd=job_dir,
                                                     │       env={GEMINI_API_KEY, model overrides},
                                                     │       start_new_session=True)
                                                     ▼
                                                runner.py ──► run_pipeline(...)
                                                     │ stdout+stderr ──► log.txt
                                                     ▼
Browser ◄──SSE /api/jobs/{id}/events──── progress.py đọc log.txt theo byte offset
```

Web server không bao giờ gọi pipeline trong tiến trình của chính nó. Nó chỉ sinh
tiến trình con, đọc file, và phục vụ file.

### Bố cục thư mục

```
storyboard-ai/
├── genai-pipeline/              # chỉ sửa config.py, 3 dòng (mục 5)
├── web/
│   ├── server.py                # FastAPI app, routes, phục vụ dist/
│   ├── jobs.py                  # vòng đời job: tạo, spawn, kill, hàng đợi, quét mồ côi
│   ├── progress.py              # parse dòng log thành sự kiện có cấu trúc
│   ├── runner.py                # chạy trong tiến trình con
│   ├── schemas.py               # model Pydantic cho request/response
│   └── frontend/
│       ├── index.html
│       ├── vite.config.ts
│       ├── package.json
│       └── src/
└── output/jobs/<job_id>/
    ├── job.json
    ├── log.txt
    └── output/run_<ts>/         # artifact do pipeline sinh ra (R2)
```

## 4. Mô hình dữ liệu

`job.json`, đọc/ghi nguyên file, ghi qua file tạm rồi `os.replace` để không đọc phải
file nửa vời.

```json
{
  "id": "j_20260826_153012_a3f9",
  "status": "queued",
  "created_at": "2026-08-26T15:30:12+07:00",
  "started_at": null,
  "finished_at": null,
  "params": {
    "context": "Lịch sử chữ Quốc ngữ (strictly 3 scenes)",
    "language": "vietnamese",
    "research_mode": "web",
    "use_internet_image_search": true,
    "fast_mode": true,
    "enable_veo": false,
    "veo_direction_by_director": false
  },
  "models": {
    "MODEL_NAME": "gemini-2.5-flash",
    "IMAGE_GEN_MODEL": "gemini-3.1-flash-image",
    "TTS_MODEL": null
  },
  "key_source": "server",
  "pid": null,
  "exit_code": null,
  "result_video": null,
  "error": null,
  "progress": { "step": null, "scene": null, "total_scenes": null }
}
```

**API key không bao giờ được ghi vào `job.json`.** Key chỉ tồn tại trong `env` của
tiến trình con. `key_source` chỉ ghi nhận nguồn (`server` đọc từ `.env`, `user` do
người dùng dán vào form), không ghi giá trị.

### Chuyển trạng thái

```
queued ──► running ──► done
   │          ├──────► failed        (exit code != 0)
   │          ├──────► cancelled     (người dùng bấm huỷ)
   │          └──────► interrupted   (server chết giữa chừng, pid không còn)
   └──────► cancelled                (huỷ khi còn trong hàng đợi)
```

Trạng thái kết thúc là bất biến. Đã `done` thì không quay lại `running`.

## 5. Thay đổi duy nhất ở phía pipeline

`genai-pipeline/config.py`, ba dòng, cho phép ghi đè model qua biến môi trường:

```python
MODEL_NAME      = os.getenv("SB_MODEL_NAME", "gemini-2.5-pro")
IMAGE_GEN_MODEL = os.getenv("SB_IMAGE_GEN_MODEL", "gemini-3.1-flash-image")
TTS_MODEL       = os.getenv("SB_TTS_MODEL", "gemini-3.1-flash-tts-preview")
```

Giá trị mặc định giữ nguyên hành vi hiện tại, nên CLI cũ chạy y như cũ.

## 6. API

Mọi route trả lỗi theo khuôn `{"error": {"code": str, "message": str}}`.

| Method | Route | Việc |
|---|---|---|
| `POST` | `/api/jobs` | Tạo job. Body gồm `params`, `models` tuỳ chọn, `api_key` tuỳ chọn. Trả `201 {id}`. |
| `GET` | `/api/jobs` | Danh sách job, mới nhất trước. Hỗ trợ `?status=`. |
| `GET` | `/api/jobs/{id}` | Toàn bộ `job.json`. |
| `GET` | `/api/jobs/{id}/events` | SSE. Xem mục 7. |
| `POST` | `/api/jobs/{id}/cancel` | Huỷ. `409` nếu job đã kết thúc. |
| `GET` | `/api/jobs/{id}/artifacts` | Cây artifact đã nhóm theo scene. |
| `GET` | `/api/jobs/{id}/file?path=` | Phục vụ một artifact. Xem mục 9 về path traversal. |
| `DELETE` | `/api/jobs/{id}` | Xoá job và toàn bộ artifact. `409` nếu đang chạy. |
| `GET` | `/api/health` | Có `ffmpeg` không, có key server không, số job đang chạy. |

`POST /api/jobs` validate trước khi spawn: `context` không rỗng, `research_mode` thuộc
`{deep, web, none}`, và phải có key (từ `.env` hoặc từ body). Thiếu thì `400`, không
sinh tiến trình.

## 7. Giao thức tiến trình (SSE)

`GET /api/jobs/{id}/events` phát các sự kiện đã đặt tên. Client gửi
`Last-Event-ID` là byte offset trong `log.txt` để đọc tiếp sau khi mất kết nối, nhờ
vậy đóng tab rồi mở lại không mất gì.

| Sự kiện | Payload | Sinh ra từ |
|---|---|---|
| `log` | `{offset, line}` | mọi dòng stdout |
| `step` | `{n, label}` | dòng khớp `^Step (\d+): (.+)` |
| `scene` | `{current, total}` | dòng khớp `^--- Processing Scene (\d+)/(\d+) ---` |
| `activity` | `{scene, label}` | dòng khớp `^Scene (\d+): (.+)` |
| `warning` | `{scene, message}` | dòng khớp `^\s*\[X\] SKIPPING Scene (\d+): (.+)` |
| `status` | `{status, ...}` | `job.json` đổi trạng thái |

`progress.py` chỉ làm một việc: dòng vào, sự kiện ra. Không I/O, không trạng thái.
Nhờ vậy test được bằng bảng chuỗi mẫu, không cần chạy pipeline.

Thanh tiến trình tính từ `scene.current / scene.total`, chưa biết tổng thì hiện dạng
không xác định.

## 8. Xử lý lỗi

| Tình huống | Xử lý |
|---|---|
| Tiến trình con thoát khác 0 | `failed`, lưu `exit_code` và 50 dòng log cuối vào `error` |
| Server khởi động lại khi job đang chạy | Quét lúc startup: job `running` mà pid không sống thì đánh `interrupted` |
| SSE đứt kết nối | Client reconnect kèm `Last-Event-ID`, server đọc tiếp từ offset đó |
| Người dùng huỷ | `os.killpg(os.getpgid(pid), SIGTERM)`, chờ 5 giây, chưa chết thì `SIGKILL` |
| Thiếu ffmpeg | `/api/health` báo, UI hiện cảnh báo cố định, vẫn cho chạy |
| Thiếu API key | `400` trước khi spawn |
| `job.json` hỏng | Job hiện trạng thái `corrupt`, cho xoá, không làm sập danh sách |

`os.killpg` là lý do tiến trình con phải spawn với `start_new_session=True`. Pipeline
gọi `ffmpeg` qua `subprocess`, giết mỗi tiến trình Python cha sẽ để lại ffmpeg mồ côi.

## 9. Bảo mật

Giai đoạn 1 chạy localhost không auth, nhưng ba chỗ vẫn phải chặt vì GĐ2 sẽ mở ra
mạng:

1. **Path traversal.** `/api/jobs/{id}/file` giải `os.path.realpath` của đường dẫn
   ghép rồi kiểm tra nó thực sự nằm trong `realpath` của thư mục job. Từ chối
   symlink trỏ ra ngoài. Trả `403` chứ không `404`.
2. **Job id.** Chỉ chấp nhận `^j_[0-9]{8}_[0-9]{6}_[0-9a-f]{4}$`, không bao giờ ghép
   thẳng chuỗi người dùng gửi vào đường dẫn.
3. **Rò rỉ key.** Log được lọc trước khi ghi: chuỗi khớp mẫu API key thay bằng
   `***`. Key không vào `job.json`, không vào response, không vào thông báo lỗi.

## 10. Chừa đường cho giai đoạn 2

| Việc của GĐ2 | Chỗ cắm sẵn |
|---|---|
| Auth | Router đã nhận một FastAPI dependency, hiện trả về người dùng ẩn danh |
| Hàng đợi thật (Celery/RQ) | `jobs.py` là module duy nhất chạm tới tiến trình |
| Hạn mức theo người | `key_source` đã có trong model; thêm `owner` là đủ |
| Điểm dừng duyệt giữa chừng | `runner.py` đã phát sự kiện theo bước; thêm trạng thái `paused` và một endpoint resume, không đổi giao thức SSE |

## 11. Giao diện

### Design read

Công cụ vận hành tự host cho một người dùng kỹ thuật, ngôn ngữ thị giác kiểu bảng
điều khiển thiết bị.

Skill `design-taste-frontend` tự khai báo ở Section 13 rằng nó không dành cho
dashboard. Phần áp dụng được là phần không phụ thuộc framework: kỷ luật typography,
khoá màu và bo góc, bắt buộc đủ trạng thái, tương phản WCAG AA, dark mode hai chiều,
motion phải có lý do, và danh sách AI tell cần tránh. Phần bố cục landing page thì bỏ.

### Dial

| Dial | Giá trị | Lý do |
|---|---|---|
| `DESIGN_VARIANCE` | 3 | Bố cục bất đối xứng làm hại công cụ. Vị trí phải cố định qua mọi lần dùng. |
| `MOTION_INTENSITY` | 3 | Chỉ chuyển trạng thái và log trôi. Không thư viện animation. |
| `VISUAL_DENSITY` | 7 | Log, trạng thái, thời lượng, số scene. Số dùng mono. |

### Nền tảng

React + Vite + Tailwind v4. Icon dùng `@phosphor-icons/react`, một họ duy nhất,
`weight="regular"` toàn cục. Font tự host qua `@fontsource-variable/geist` và
`@fontsource-variable/geist-mono` (không nhúng Google Fonts bằng thẻ `link`): Geist
cho giao diện, Geist Mono cho **mọi con số và toàn bộ log**. Không Inter, không serif.

Không dùng thư viện animation. Ở mức motion 3, CSS transition trên `transform` và
`opacity` là đủ, và mọi transition đều nằm sau `prefers-reduced-motion`.

### Bố cục

Hai cột cố định, không hero, không bento.

```
┌─────────────────┬──────────────────────────────────┐
│ Job mới         │  Job đang mở                     │
│  (form)         │   tiêu đề + trạng thái + huỷ     │
│                 │   thanh tiến trình (scene x/y)   │
│ ─────────────── │   ──────────────────────────     │
│ Lần chạy        │   Lưới scene: ảnh, audio, video  │
│  j_...  done    │   ──────────────────────────     │
│  j_...  running │   Log (mono, tự cuộn, tắt được)  │
│  j_...  failed  │                                  │
└─────────────────┴──────────────────────────────────┘
```

Dưới 768px thu về một cột: danh sách job trên, vùng làm việc dưới, form vào trong
một disclosure.

Không bọc card cho mọi khối. Nhóm bằng `border-t` và khoảng trắng. Chỉ dùng nền nổi
cho job đang chạy, vì ở đó độ nổi mang nghĩa thật.

### Màu

Một nền trung tính, đúng một màu nhấn dùng xuyên suốt mọi khối. Màu ngữ nghĩa chỉ
xuất hiện ở trạng thái job (`queued` / `running` / `done` / `failed` / `cancelled` /
`interrupted`). Đây cũng là ngoại lệ hợp lệ duy nhất cho chấm màu trạng thái mà skill
vốn cấm, vì nó mang trạng thái thật chứ không trang trí.

Dark mode làm từ đầu bằng biến CSS, tôn trọng `prefers-color-scheme`, có nút chuyển
tay. Một bo góc duy nhất cho toàn trang.

### Trạng thái giao diện

Đây là phần một job runner dễ làm ẩu nhất, nên liệt kê đủ:

| Trạng thái | Thể hiện |
|---|---|
| Chưa có job nào | Khối empty có hướng dẫn, trỏ vào form |
| Đang chờ tới lượt | Hiện vị trí trong hàng đợi, nút huỷ |
| Đang chạy, chưa có ảnh | Skeleton đúng tỉ lệ 16:9 của ô ảnh, không dùng spinner tròn |
| Scene bị bỏ qua | Ô scene hiện cảnh báo inline kèm lý do từ sự kiện `warning` |
| Hỏng | Thông báo lỗi inline kèm `exit_code` và log cuối, nút chạy lại với cùng tham số |
| Huỷ | Trạng thái rõ ràng, giữ nguyên artifact đã sinh được |
| Thiếu ffmpeg | Dải cảnh báo cố định trên đầu trang |

Form theo đúng mục 4.6 của skill: nhãn nằm trên ô nhập, không dùng placeholder thay
nhãn, lỗi hiện dưới ô. Ô API key là `type=password` có nút hiện/ẩn, kèm dòng ghi rõ
key chỉ được truyền cho tiến trình con và không lưu lại.

## 12. Kiểm thử

**Chế độ giả lập là phần quan trọng nhất của mục này.** `runner.py` khi thấy
`SB_FAKE_PIPELINE=1` sẽ in ra đúng chuỗi `Step` / `Scene` / `SKIPPING` mẫu, sinh vài
file ảnh và một video giả, rồi thoát. Không gọi API nào.

Nhờ vậy toàn bộ tầng web test được mà không cần API key và không đốt quota, và người
dùng bấm thử được cả giao diện trước khi có key.

**Unit**

- `progress.py`: bảng dòng vào, sự kiện ra. Gồm cả dòng rác và dòng khớp một phần.
- `jobs.py`: chuyển trạng thái hợp lệ và bất hợp lệ; ghi `job.json` nguyên tử.
- Path traversal: `../`, đường dẫn tuyệt đối, symlink trỏ ra ngoài, đều bị `403`.
- Lọc key khỏi log.

**Tích hợp** (đều chạy với `SB_FAKE_PIPELINE=1`)

- Tạo job, nhận sự kiện SSE theo đúng thứ tự, kết thúc `done`, artifact liệt kê đủ.
- Huỷ giữa chừng, kiểm tra process group đã chết và trạng thái là `cancelled`.
- Reconnect SSE kèm `Last-Event-ID`, không mất và không lặp dòng log.
- Job vượt `MAX_CONCURRENT` phải nằm `queued` rồi tự chạy khi có chỗ.
- Khởi động lại server khi có job `running` giả, phải thành `interrupted`.

**Thủ công, một lần trước khi coi là xong**

Chạy thật một job 2 scene bằng key thật, xem video cuối phát được trong trình duyệt.

## 13. Cấu hình

Đọc từ biến môi trường, có mặc định hợp lý:

| Biến | Mặc định | Việc |
|---|---|---|
| `SB_MAX_CONCURRENT` | `1` | Số job chạy song song |
| `SB_JOBS_DIR` | `output/jobs` | Nơi chứa job |
| `SB_HOST` / `SB_PORT` | `127.0.0.1` / `8000` | Địa chỉ lắng nghe |

Mặc định lắng nghe `127.0.0.1` chứ không `0.0.0.0`: GĐ1 chưa có auth, không nên vô
tình mở ra mạng LAN.
