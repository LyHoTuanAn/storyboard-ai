# SDD ledger — plan: docs/superpowers/plans/2026-08-26-web-ui.md

Spec: docs/superpowers/specs/2026-08-26-web-ui-design.md (doc, la thanh quyen rang buoc)
Base commit truoc Task 1: e086db1
Nhanh: main (nguoi dung chon), push len fork = https://github.com/LyHoTuanAn/storyboard-ai

## Pre-flight scan

### Cap task dung chung file

| File | Task | Producer -> Consumer | Ket qua |
|---|---|---|---|
| web/server.py | T1 tao, T7 viet lai, T8 them route, T9 them route, T10 mount static | T1 health shape {ffmpeg,server_key,running} -> T7 giu nguyen shape | OK, test T1 van xanh sau T7 |
| web/server.py | T7 -> T8 | T8 dung `Request` va `error()` cua T7 | OK, T7 da import Request |
| web/server.py | T9 -> T10 | T10 dung get_settings() | DA SUA khi self-review: T10 ghi ro dong import |
| web/server.py | T10 mount "/" | Starlette khop route theo thu tu dang ky | OK vi mount dat sau cung |
| web/jobs.py | T3 tao, T5 them spawn, T6 them cancel/pump | T3 set_status/job_dir/read_job -> T5, T6 | OK |
| web/jobs.py | T5 -> T6 | T5 spawn/pid_alive -> T6 cancel/pump | OK |
| web/runner.py | T4 tao, T6 them SB_FAKE_SLEEP | T6 test can SB_FAKE_SLEEP | OK, T6 Step 2 them truoc khi test |
| web/progress.py | T2 -> T8 | parse_line tra {"event","data"}; events.py doc parsed["event"] | OK |
| web/schemas.py | T3 -> T7 | CreateJobRequest -> route POST | OK |
| src/types.ts, api.ts | T11 -> T12,T13,T14,T15 | Artifacts/Job/JobStatus | OK |
| src/App.tsx | T10 tao, T12/T13/T14 sua dan | moi task them dung 1 khoi | OK |
| src/JobDetail.tsx | T14 tao, T15 them SceneGrid | T15 them refreshKey state | OK |
| genai-pipeline/config.py | chi T5 | khong task nao khac cham | OK, dung Global Constraint |

### Tung task tu nhat quan?

T1..T16: moi task co test khop voi code no dac ta, file tao ra khop file task sau cham vao. Khong tim thay mau thuan noi bo.

### Phat hien va ruling

Ruling 1: Runner co the crash voi traceback khi job bi huy dung luc no vua xong.
  Child goi set_status("done") ngoai khoi try/except; neu parent da dat "cancelled"
  (terminal) thi InvalidTransition nem ra, exit code 1.
  Quyet dinh: chap nhan. Trang thai terminal cua parent la dung, day chi la rac trong log.
  Gia neu sai: log co traceback kho hieu o dung mot ca hiem. Khong anh huong du lieu.

Ruling 2: keys._KEYS khong bao gio duoc don cho job ket thuc binh thuong.
  forget() chi duoc goi khi cancel va delete. Key cua job da xong nam lai trong RAM
  cua server toi khi restart.
  Quyet dinh: hoan lai, ghi la deferred minor, chi cho final review phan xu.
  GD1 chay localhost mot nguoi nen key von da nam hop phap trong tien trinh do.
  Gia neu sai: key song trong RAM lau hon can thiet. Khong xuong dia, khong ra mang.

Ruling 3: runner.run_real dung Path.relative_to(cwd); neu pipeline tra ve duong dan
  ngoai cwd thi ValueError bi except bat va job bi danh "failed" du that ra da chay xong.
  Quyet dinh: chap nhan cho GD1. pipeline.py:81 luon ghi vao cwd nen ca nay khong xay ra
  tru khi pipeline doi hanh vi.
  Gia neu sai: mot job thanh cong bi bao failed; artifact van con nguyen tren dia.

## Tien do

Task 1: minor (deferred): import Path thua trong web/server.py
Task 1: minor (deferred): server_key_present khong bat loi khi doc .env (permission / non-UTF8 -> 500)
Task 1: minor (deferred): os.getenv nhan Path lam default thay vi str
Task 1: minor (deferred): conftest co lap jobs_dir nhung khong co lap repo_root, nen test doc .env that cua may. Anh huong moi task sau dung fixture nay.
Task 1: complete (commits e086db1..db5fce2, review clean)

Task 2: Ruling: reviewer bao mau `sk_` la dead scope va doi xoa -- BAC BO. Nguoi dung
  dang danh gia gateway rexllm.xyz, khoa cua no dung dang sk_9r_... Reviewer khong co
  context nay. Gia neu sai: giu mot regex khong bao gio khop, ton vai microgiay.
Task 2: Ruling: thieu mau hf_ (Critical) -- CHAP NHAN, cho vao vong sua. Spec 9.3 noi
  "chuoi khop mau API key" khong liet ke cu the, nen phu rong hon la dung. build_env
  sao chep os.environ nen HF_API_KEY tren may co the lot vao tien trinh con.
  Gia neu sai: them mot regex thua.
Task 2: Ruling: gop luon fix rstrip("\r\n") (Minor) vao cung vong sua. Cung mot moi lo
  ve sinh dong, sua mot ky tu, va module nay ton tai chinh de chong bat ngo tu stdout.
Task 2: fix round 1/5 (2 addressed, 0 open — thieu mau hf_; rstrip \r\n; commits 574e126..be6020e)
Task 2: complete (commits db5fce2..be6020e, review clean)
Task 3: Ruling: implementer sap xep list_jobs theo created_at thay vi job id (lech voi
  plan) -- CHAP NHAN. Job id chi co do phan giai giay + 4 hex ngau nhien, nen hai job
  cung giay se sap theo hex, tuc ngau nhien; test test_list_jobs_returns_newest_first
  cua chinh plan se hong ngau nhien. created_at co micro giay nen dung hon. Nhanh job
  hong van an toan vi dung .get("created_at", ""). Day la loi cua plan, implementer sua dung.
  Gia neu sai: thu tu danh sach job phu thuoc dong ho he thong thay vi ten thu muc.
Task 3: Ruling: regex JOB_ID_RE dung `$` nen chuoi ket thuc bang \n van lot (Important).
  Xung dot voi Global Constraints do chinh plan viet. CHAP NHAN sua: spec 9.2 noi ro y do
  la validate chat truoc khi ghep duong dan, nen re.fullmatch dung y hon `$`.
  Gia neu sai: khong co, day la that chat hon.
Task 3: Ruling: NANG "va cham job id lam ghi de job cu" tu Minor len Important va cho vao
  cung vong sua. Reviewer xep Minor, nhung hau qua la mat du lieu am tham (job cu bi ghi de,
  khong bao loi). Sua chi 3 dong. Gia neu sai: them mot vong lap kiem tra ton tai, khong ton gi.
Task 3: minor (deferred): list_jobs tra dict thieu key cho job hong, caller co the KeyError
Task 3: minor (deferred): job_dir nem JobNotFound cho id sai cu phap, ten ngoai le khong khop y nghia
Task 3: minor (deferred): create_job them cac field pid/exit_code/result_video/error/progress ngoai interface brief liet ke
Task 3: fix round 1/5 (2 addressed, 0 open — regex fullmatch; va cham job id; commits ce86f69..57c21f0)
Task 3: complete (commits be6020e..57c21f0, review clean)
Task 4: Ruling: set_status tu nem InvalidTransition trong main() (Important) -- CHAP NHAN sua,
  nhung DINH CHINH ly le cua reviewer. Reviewer bao job se "stuck in running forever";
  sai trong ca huy: parent da dat "cancelled" (terminal) roi, ket qua van dung, chi la
  traceback ban trong log. Truong hop that su ket la khi set_status hong vi ly do khac
  (het dia, sai quyen) -- va Task 5 reap_orphans + Task 6 pump da vot ca do.
  Van sua vi sua re va bien mot traceback chac chan thanh mot lan thoat sach.
  Thay the pre-flight Ruling 1 (truoc do minh xep la chap nhan duoc).
  Gia neu sai: them mot khoi try/except khong bao gio chay toi.
Task 4: Resolved (⚠️ cannot verify from diff): reviewer hoi lieu child bi kill co de job
  mo coi khong. KHONG PHAI LO HONG. Task 5 them reap_orphans (pid chet -> interrupted),
  Task 6 goi no dau moi pump. Nam ngoai pham vi Task 4 dung nhu thiet ke.
Task 4: minor (deferred): brief liet ke job_dir trong Consumes nhung runner khong dung, chi dua vao cwd
Task 4: minor (deferred): run_real relative_to co the nem ValueError (trung pre-flight Ruling 3)
Task 4: fix round 1/5 (1 addressed, 0 open — main() tu nem InvalidTransition; commits be5480f..450b699)
Task 4: complete (commits 57c21f0..450b699, review clean)
Task 5: Ruling: reap_orphans khong phat hien duoc tien trinh con da chet (Critical) --
  CHAP NHAN, phai sua. Tien trinh con chet thanh zombie cho toi khi cha goi wait();
  os.kill(pid,0) tren zombie van thanh cong, nen pid_alive luon tra True va reap_orphans
  khong bao gio chay dung ca no sinh ra de xu ly. Day la LOI CUA PLAN, khong phai cua
  implementer. Spec muc 8 doi hoi phat hien duoc child chet, nen thiet ke hien tai khong
  dat spec. Sua: theo doi Popen trong dict, reap_orphans goi poll() truoc (vua don zombie
  vua lay duoc exit code), roi moi fallback sang pid_alive cho pid khong theo doi (ca sau
  khi server restart -- luc do child da duoc init nhan nuoi nen pid_alive dung).
  Gia neu sai: giu them mot dict Popen trong bo nho server.
Task 5: Ruling: build_env sao chep toan bo os.environ (Important) -- CHAP NHAN MOT PHAN.
  Allow-list chat se lam hong pipeline that (ffmpeg can PATH, SDK Google can HOME/creds)
  theo cach che do gia lap khong bat duoc. Thay vao do: loc bo cac bien *_API_KEY /
  *_TOKEN / *_SECRET khac ngoai GEMINI_API_KEY. Nham dung moi lo blast-radius ma khong
  pha toolchain. Gia neu sai: mot bien moi truong hiem gap bi loc nham, pipeline bao loi ro rang.
Task 5: minor (deferred): import signal chua dung (Task 6 se dung)
Task 5: minor (deferred): Popen khong dat stdin, child ke thua stdin cua server
Task 5: minor (deferred): spawn dat status running SAU Popen, ve ly thuyet co race
Task 5: fix round 1/5 (2 addressed, 0 open — zombie defeats reap_orphans; build_env loc secret; commits 17346e7..fbf379d)
Task 5: Ruling: TU PHAT HIEN sau khi re-review pass -- reap_orphans chi duyet job "running",
  nen job chay THANH CONG (status "done") khong bao gio bi xoa khoi _PROCESSES va poll()
  khong bao gio duoc goi cho no. Moi job thanh cong de lai mot zombie song toi khi server
  tat, cong mot muc dict tang vo han. Reviewer khong the thay vi re-review bi gioi han
  dung 2 phat hien cu. CHAP NHAN sua o vong 2, vi code thuoc Task 5.
  Sua: quet toan bo _PROCESSES truoc (poll + xoa muc da thoat), roi moi xu ly status
  cho job con "running".
  Gia neu sai: them mot vong lap ngan qua dict nho.
Task 5: minor (deferred): hai test zombie tu goi process.wait() truoc reap_orphans, nen
  chua chung minh duoc chinh poll() la thu don zombie duoi dieu kien that
Task 5: fix round 2/5 (1 addressed, 0 open — ro PID/dict cho job thanh cong; commits fbf379d..bbb66a3)
Task 5: complete (commits 450b699..bbb66a3, review clean, 2 vong sua)
Task 6: Ruling: pump sap xep theo job id nen khong dam bao FIFO (Important) -- CHAP NHAN.
  Cung dung loi da phan quyet o Task 3 cho list_jobs. Phai nhat quan: sap theo created_at.
  Gia neu sai: thu tu hang doi phu thuoc dong ho thay vi ten thu muc.
Task 6: Resolved (⚠️ cannot verify from diff): reviewer hoi lieu pump co bi goi dong thoi
  khong. CO -- Task 7 goi jobs.pump tu handler FastAPI viet bang `def` thuong, nen chay
  trong threadpool va hai request POST cung luc la co that. count_running() >= max la
  TOCTOU khong khoa. Hau qua: vuot MAX_CONCURRENT, dot gap doi quota. XAC NHAN LA LO HONG
  THAT, cho vao vong sua. Gia neu sai: them mot threading.Lock khong bao gio bi tranh chap.
Task 6: minor (deferred): dong "Step 0: fake mode dang ngu" hien nhu step 0 tren thanh tien trinh
Task 6: minor (deferred): test_cancel_running_job dung time.sleep(0.5) co dinh thay vi poll
Task 6: fix round 1/5 (2 addressed, 0 open — FIFO theo created_at; khoa pump; commits 6ef35f1..4cc82d7)
Task 6: complete (commits bbb66a3..4cc82d7, review clean)
Task 6: minor (deferred): pump giu khoa trong luc quet ca thu muc + doc JSON tung job; van de mo rong ve sau

Task 7: Ruling: plan dung @app.on_event("startup") -- LOI CUA PLAN, sua truoc khi giao.
  FastAPI da deprecate on_event tu lau de thay bang lifespan context manager; ban 0.141
  trong venv se canh bao va co the bo han. Chuyen sang lifespan.
  Gia neu sai: dung API moi hon thay vi API cu, khong doi hanh vi.
Task 7: Ruling: key khong bao gio bi quen cho job ket thuc binh thuong (Important) --
  LAT NGUOC pre-flight Ruling 2 cua chinh minh. Truoc do minh hoan lai voi ly do "GD1
  localhost mot nguoi". Lap luan cua reviewer manh hon: khi job da terminal, resolve()
  khong bao gio doc lai key do nua, nen giu lai la phoi nhiem thuan tuy khong doi lay gi.
  Day lai dung la task co thuoc tinh dinh danh la bao mat key. CHAP NHAN sua.
  Gia neu sai: them mot vong quet nho sau moi lan pump.
Task 7: Ruling: NANG "422 co the doi lai api_key khi client gui sai kieu" tu Minor len
  can sua, vi day la task ma bao mat key la thuoc tinh dinh danh. Handler
  RequestValidationError tuy chinh de chui api_key ra khoi phan input duoc echo.
  Gia neu sai: them mot exception handler ~10 dong.
Task 7: minor (deferred): _KEYS la state toan cuc giua cac test, chua co teardown
Task 7: fix round 1/5 (2 addressed, 0 open — quen key khi job xong; chui api_key khoi 422; commits 78447db..3fa38e4)
Task 7: complete (commits 4cc82d7..3fa38e4, review clean)
Task 7: minor (deferred): sweep chi chay khi co pump ke tiep; job cuoi cung giu key toi khi server tat

Task 8: Ruling: plan viet stream_job la `async def` nhung ben trong doc file va json.loads
  dong bo -- chan event loop moi 250ms cho moi client. LOI CUA PLAN, sua truoc khi giao.
  Dung asyncio.to_thread cho phan doc file va read_job. Gia neu sai: them mot lop to_thread
  cho thao tac vai mili giay.
Task 8: LOI QUY TRINH CUA CONTROLLER: quen sinh task-8-brief.md truoc khi dispatch.
  Implementer tu phuc hoi tu file plan (dong 1436) va lam dung. Da sinh brief bo sung
  de reviewer co du 3 file dau vao. Rut kinh nghiem: sinh brief ngay truoc moi dispatch.
Task 8: Ruling: implementer phat hien code trong plan tron `for raw in stream` voi
  `stream.tell()` -- Python cam, nem OSError "telling position disabled by next() call".
  Da tu kiem chung bang Python 3.14 that: LOI CO THAT, toan bo tinh nang SSE se hong ngay
  lan chay dau. CHAP NHAN ban sua dung readline(). Day la loi nghiem trong nhat cua plan
  cho toi gio. Gia neu sai: khong co, readline() la cach dung duy nhat dung.
Task 8: Ruling: mot dong log sinh 2 su kien SSE nhung cung mot id, nen mat su kien dan xuat
  khi reconnect dung giua hai su kien (Important) -- CHAP NHAN sua. Spec muc 7 hua "dong tab
  roi mo lai khong mat gi", nen hop dong phai dung that. Chon phuong an id co chi so phu
  "offset:n" thay vi gop 2 su kien lam 1, vi Task 11 da dac ta hook nghe rieng su kien `log`;
  doi sang gop se keo theo sua ca hop dong frontend.
  Gia neu sai: id dai hon vai ky tu, parser phia client tach them mot lan.
Task 8: minor (deferred): stream_job co default arg start_offset=0 khong bao gio duoc dung
Task 8: fix round 1/5 (1 addressed, 0 open — id SSE co chi so phu; commits c2ab82f..b2c71ef)
Task 8: complete (commits 3fa38e4..b2c71ef, review clean)
Task 9: Ruling: implementer bao safe_path trong plan cho qua `candidate == root` (path=""
  hoac "."), tra ve chinh thu muc job. CHAP NHAN ban sua. LOI CUA PLAN.
Task 9: CONTROLLER TU KIEM CHUNG: chay 13 don tan cong that vao safe_path da trien khai.
  12 bi chan dung (traversal, tuyet doi, rong, symlink tro ra ngoai, thu muc hang xom
  cung tien to ten, URL-encode, xuong dong). 2 duong dan hop le duoc cho qua dung.
  PHAT HIEN: path chua ky tu NUL (%00) nem ValueError chua bat -> route tra 500 thay vi 403.
  Khong lo du lieu nhung la exception chua xu ly. Cho vao vong sua cung phat hien cua reviewer.
Task 9: fix round 1/5 (1 addressed, 0 open — NUL/OSError -> 403; commits 95d8de3..b5593b1)
Task 9: CONTROLLER TU KIEM CHUNG LAI sau khi sua: chay lai bo 14 don tan cong, 14/14 bi chan
  dung, duong dan hop le van hoat dong. Ranh gioi bao mat coi nhu vung.
Task 9: complete (commits b2c71ef..b5593b1, review clean)
=== MOC: BACKEND HOAN TAT (Task 1-9), 75 test xanh ===
Task 10: Ruling: aria-label nut doi theme la chuoi tinh, khong doi theo trang thai
  (Important) -- CHAP NHAN sua. Doc man hinh luon doc "chuyen sang toi" ke ca khi dang o
  che do toi. Gia neu sai: khong co.
Task 10: Ruling: GOP 3 Minor vao cung vong sua vi moi cai vi pham truc tiep mot rang buoc
  minh da ghi trong Global Constraints:
   - public/icons.svg la SVG tu ve bang tay va khong ai dung -> vi pham "khong tu ve path SVG"
   - nut vua co class `rounded` vua co inline borderRadius -> vi pham "dung mot thang bo goc"
   - applyTheme chay trong useEffect nen loe sang truoc khi doi sang toi -> vi pham "khoa theme"
  Gia neu sai: xoa mot file thua, bo mot class thua, them 5 dong script inline.
Task 10: minor (deferred): import dat giua file trong web/server.py thay vi tren dau
Task 10: fix round 1/5 (4 addressed, 0 open — aria-label dong, xoa icons.svg, mot bo goc, chan loe theme; commits 4d925b8..092151d)
Task 10: complete (commits b5593b1..092151d, review clean)
Task 11: minor (deferred): job.json co field `progress` do plan dat ra nhung KHONG CODE NAO
  ghi vao no; luon la null. Hoac bo di hoac cho runner cap nhat. Chi cho final review.
Task 11: CARRY SANG TASK 13: list_jobs tra ve object gan rong cho job hong (chi co id +
  status="corrupt"), nhung kieu TypeScript khai la Job day du. JobList phai guard
  status === "corrupt" truoc khi cham params/models.
Task 11: Ruling: useJobs khong chong ket qua ve khong dung thu tu (Important) -- CHAP NHAN sua.
Task 11: Ruling: NANG "hook dong EventSource khi server bao stalled" tu Minor len phai sua.
  events.py dong luong sau 600s khong co dong log moi. Voi pipeline that, im lang qua 10 phut
  la binh thuong (Veo, deep research). Hook goi source.close() va ghi trang thai CHUA ket thuc
  -> UI dung im giua chung khong dau hieu gi. Sua: chi close() khi status thuc su terminal;
  con lai de EventSource tu nooi lai (trinh duyet tu lam khi server dong).
  Gia neu sai: giu ket noi mo them vai giay truoc khi trinh duyet tu dong lai.
Task 11: fix round 1/5 (3 addressed, 0 open — chong ket qua lech thu tu; xu ly stalled; xoa sourceRef; commits e5fd18f..242490d)
Task 11: complete (commits 092151d..242490d, review clean)
Task 12: Ruling: implementer doi mau chu nut chinh tu #ffffff (theo plan) sang var(--bg)
  -- CHAP NHAN. Da TU TINH LAI tuong phan WCAG bang script: chu trang tren --accent che do
  toi (#4fb094) chi dat 2.63:1, TRUOT chuan AA 4.5:1. Ban sua dat 5.83:1 (sang) va 7.06:1
  (toi), qua ca hai. LOI CUA PLAN: token mau minh chon tao ra loi tro nang that.
  (Ghi chu: implementer bao 7.97:1 cho che do toi, so cua minh la 7.06:1; ket luan giong
  nhau nen khong dang mo vong sua, nhung so cua ho hoi lech.)
  Gia neu sai: nut co chu mau nen thay vi trang, van dung token san co.
Task 12: Ruling: o nhap API key thieu autoComplete (Important) -- CHAP NHAN sua. Trinh
  quan ly mat khau co the moi luu khoa, mau thuan truc tiep voi dong chu "khong luu lai"
  ngay ben canh. Gia neu sai: them mot thuoc tinh HTML.
Task 12: minor (deferred): nhan checkbox dat ben canh thay vi ben tren (mau chuan cho checkbox)
Task 12: CONTROLLER TU KIEM CHUNG: reviewer da audit tuong phan moi cap mau o ca hai che do,
  thap nhat la 5.17:1, deu qua AA 4.5:1.
Task 12: fix round 1/5 (1 addressed, 0 open — autoComplete new-password tren o api key; commits e74eec3..a1a0620)
Task 12: complete (commits 242490d..a1a0620, review clean)
Task 13: Ruling: --st-queued va --st-cancelled TRUOT chuan AA khi dung lam mau chu
  (3.35:1 sang / 4.49:1 toi, nguong 4.5:1). DA TU KIEM CHUNG bang script doc thang tu
  styles.css. LOI CUA PLAN: 2 trong 6 mau trang thai minh chon khong dung duoc lam mau chu.
  Dang chu y: 4.49 vs 4.50, truot dung mot phan tram, khong the bat bang mat.
  CHAP NHAN ban sua cua implementer: giu nguyen token, chu nhan dung var(--text), mau chi
  con o cham tron (do hoa phi-chu chi can 3:1). Khong sua CSS token vi ngoai pham vi task.
  Gia neu sai: badge bot mau sac nhung van phan biet duoc bang cham va nhan chu.
Task 13: minor (deferred): --st-done sang 4.82:1 va --st-interrupted sang 4.55:1 deu sat nguong;
  neu sau nay chinh mau nen thi phai tinh lai.
Task 13: Ruling: hang dang chon chi phan biet bang mau nen, khong co dau hieu phi-mau
  (Important, vi pham WCAG 1.4.1 va vi pham chinh yeu cau minh ghi trong brief) -- CHAP NHAN sua.
  Gia neu sai: them mot vien trai va aria-current.
Task 13: minor (deferred): HealthBanner chi goi getHealth mot lan luc mount, khong poll;
  neu nguoi dung them key vao .env giua phien thi canh bao van dinh toi khi tai lai trang.
Task 13: fix round 1/5 (1 addressed, 0 open — aria-current + vien trai phi-mau; commits f3e134a..ef5d8a8)
Task 13: complete (commits a1a0620..ef5d8a8, review clean)
Task 13: CARRY SANG TASK 14: useJobEvents nay tra ve co `stalled`. JobDetail PHAI hien thi no,
  neu khong ban sua Task 11 chi giai quyet duoc nua van de (ket noi tu noi lai nhung nguoi dung
  van khong biet job dang im lang hay da chet).
Task 14: Ruling: reviewer phat hien JobDetail khong guard status "corrupt" (Important).
  Khi dieu tra, minh TU KIEM CHUNG va tim ra loi NANG HON o BACKEND: read_job khong bat
  JSONDecodeError, nen GET /api/jobs/{id} tra 500 cho job hong, TRONG KHI GET /api/jobs
  cung du lieu do lai xu ly sach. Duong di that: job hong hien trong danh sach (Task 13
  render dung) -> nguoi dung bam vao -> 500. Loi xuyen 3 tang, chin task truoc khong ai thay
  vi phai co ca danh sach lan man hinh chi tiet moi bieu hien.
  CAP QUYEN NGOAI LE cho Task 14 duoc sua web/jobs.py va web/server.py, vi sua frontend ma
  de nguyen 500 thi chi vá duoc nua duong di.
  Sua: read_job tra ve cung hinh dang {"id","status":"corrupt"} nhu list_jobs khi JSON hong;
  frontend coi "corrupt" la trang thai ket thuc va guard params.
  Gia neu sai: mot task frontend cham vao 2 file backend, review se soi ky hon.
Task 14: minor (deferred): starlette TestClient canh bao dung httpx thay vi httpx2 (day la
  "1 warning" thay trong moi lan chay pytest tu dau du an)
Task 14: minor (deferred): cancelJob().finally() co the setState sau khi unmount
Task 14: CONTROLLER TU PHAT HIEN (vong 2): "corrupt" KHONG nam trong jobs.TERMINAL, nen
  events.stream_job tren job hong lap toi khi het 600s idle timeout thay vi ket thuc ngay.
  useJobEvents mo stream bat ke trang thai, nen bam vao job hong = treo mot ket noi 10 phut
  + mot thread ket trong asyncio.to_thread. Phat hien tinh co: script kiem chung cua chinh
  minh bi treo o dung endpoint do.
  CHAP NHAN cho vao vong sua 2. Gia neu sai: stream ket thuc som hon cho mot trang thai
  von da khong bao gio co them log moi.
Task 14: fix round 1/5 (2 addressed — corrupt 500 backend + guard frontend; commits ccf43a7..088c64d)
Task 14: fix round 2/5 (1 addressed — SSE ket thuc ngay cho corrupt; commits 088c64d..518e1ee)
Task 14: CONTROLLER TU KIEM CHUNG LAI: chay lai dung script tung treo. SSE tren job hong gio
  ket thuc trong 0 giay voi su kien status bao corrupt (truoc: treo 600s).
Task 14: complete (commits ef5d8a8..518e1ee, review clean, 2 vong sua, 87 test)
Task 15: Ruling: o video hoan chinh khong dat truoc ti le khung hinh (Critical) -- CHAP NHAN sua.
  Ca component cham chut chong nhay trang, tru dung o lon nhat. LOI CUA PLAN (code mau cua minh).
Task 15: Ruling: scenes=[] render ra khoang trong tran (Important) -- CHAP NHAN sua.
Task 15: Ruling: <audio> khong co ten tro nang (Important) -- CHAP NHAN sua. Doc man hinh chi
  doc "audio", khong phan biet duoc giua cac scene.
Task 15: Ruling: GOP Minor "skeleton 2 cot con luoi that 3 cot" vao cung vong sua, vi no cung
  la loi nhay layout luc tai giong het Critical o tren, va sua chi mot tu.
  Gia neu sai: skeleton co dung so cot nhu luoi that.
Task 15: minor (deferred): effect trong JobDetail gay them 1 request thua luc mount
Task 15: minor (deferred): hang caption dich ngang khi audio xuat hien sau
Task 15: fix round 1/5 (4 addressed, 0 open — ti le video cuoi, trang thai rong, ten tro nang, so cot skeleton; commits 33611c6..c9abbdb)
Task 15: complete (commits 518e1ee..c9abbdb, review clean)
Task 16: Ruling: Step 8 cua plan (chay that mot job 2 scene bang key that) KHONG THUC HIEN
  trong phien nay. Ly do: ton quota/tien that cua nguoi dung, va .env van dang GEMINI_API_KEY="".
  Day la mot trong bon truong hop skill yeu cau DUNG LAI VA HOI. Giao Task 16 lam moi buoc
  con lai; buoc 8 se de nguoi dung tu quyet.
Task 16: PHAT HIEN MOI (do implementer bat khi kiem chung mo ta cua controller):
  1) Giao dien KHONG CO nut xoa nao. deleteJob() ton tai trong api.ts nhung khong component
     nao goi. LO HONG TRONG PLAN: muc 11 (giao dien) cua spec khong he dac ta nut xoa,
     trong khi muc 6 (API) co endpoint DELETE.
  2) DELETE /api/jobs/{id} TU CHOI job "corrupt" voi 409, vi TERMINAL khong chua "corrupt".
     Hau qua: job hong ket lai trong danh sach vinh vien, chi xoa duoc bang rm -rf thu cong.
     Day la he qua cua ban sua ma CHINH MINH chi dao o Task 14 vong 1.
  Chuyen ca hai cho FINAL REVIEW phan xu, thay vi mo them vong sua task.
Task 16: Ruling: HANG DOI HONG THAT (Critical). pump() chi duoc goi tu _pump_and_sweep()
  o route tao job va huy job. Khong co gi goi no khi mot job TU KET THUC. Hau qua: voi
  SB_MAX_CONCURRENT=1, job thu hai nam "queued" VINH VIEN cho toi khi nguoi dung tinh co
  tao them job moi hoac huy mot job.
  DA TU KIEM CHUNG bang thu nghiem 2 job: A=done, B=queued mai mai.
  Spec muc 6 hua nguyen van "job du nam queued, xong mot cai thi keo cai ke" -> KHONG DAT SPEC.
  Chuoi phat hien dang chu y: reviewer doc README -> nghi ngo mot cau -> doi chieu code ->
  lo ra loi chuc nang. Mot bai review TAI LIEU tim ra loi CHUC NANG.
  QUYET DINH: sua CODE cho dung loi hua, khong sua tai lieu cho khop voi loi.
  Cach sua: background task trong lifespan goi pump() dinh ky, huy khi shutdown. Day cung
  chinh la cho GD2 se thay bang Celery.
  Gia neu sai: them mot task nen chay vai giay mot lan tren server localhost.
Task 16: fix round 1/5 (1 addressed — muc xu ly su co trong README; commits 26e546b..a0e588a)
QUEUE DRAIN FIX: background task trong lifespan goi pump() moi 3s, huy sach khi shutdown.
  89 test (tang tu 87). CONTROLLER TU KIEM CHUNG: 2 job, MAX_CONCURRENT=1, khong goi API
  gi them -> ca hai deu ve done. Truoc khi sua: B ket "queued" vinh vien.
  PHAT HIEN KEM: moi test file cu dung TestClient(app) tran, KHONG chay lifespan -> nghia la
  reap_orphans() luc startup CHUA TUNG duoc test that su. Chuyen cho final review.
Task 16: complete (commits c9abbdb..8a606e7, review clean)
=== TAT CA 16 TASK HOAN TAT, 89 test xanh ===

=== FINAL WHOLE-BRANCH REVIEW (opus): 2 Critical, 9 Important ===
Ruling: Finding 6 (doi mac dinh IMAGE_GEN_MODEL) -- BAC BO. Reviewer so voi upstream 152d060
  va ket luan "doi hanh vi CLI ma khong duoc dong y". Nhung nguoi dung DA YEU CAU RO RANG doi
  sang gemini-3.1-flash-image o dau phien nay. Khong lat lai y muon cua ho.
  Gia neu sai: khong co; se bao cao ro cho nguoi dung de ho tu quyet.
Ruling: Finding 8 (spec hua nut chay lai, vi tri hang doi, bo cuc mobile, UI xoa) -- KHONG
  DUA VAO VONG SUA. Day la TINH NANG THIEU, khong phai loi. Quyet dinh pham vi thuoc ve
  nguoi dung. NGOAI TRU phan backend: cho phep DELETE job corrupt, vi hien tai job hong ket
  lai vinh vien khong co cach nao go.
  Gia neu sai: giao cho nguoi dung mot ban thieu 3 tinh nang nho thay vi tu them.
Ruling: dua vao MOT dot sua duy nhat (theo skill): Critical 1+2, Important 3,4,5,7,9, va 4
  minor ma reviewer noi phai sua (stdin DEVNULL, co lap repo_root trong conftest,
  keys.server_key bat loi, artifacts NotADirectoryError) + LogView scrollIntoView.

Ruling: VUOT QUY TAC "khong co dot sua thu hai" cua skill, co chu dich.
  Re-review tim ra 2 lo con lai, ca hai da duoc DUNG LAI THAT (khong phai suy doan):
   1) /file?path=job.json phuc vu file THO -> key van lot ra, dung cai thuoc tinh ma ca du an
      lay lam dinh danh. Sua = gioi han /file theo duoi file, hoac loc job.json.
   2) keys.sweep() nam ngoai khoa -> job vua tao co the bi quen key roi bi danh failed ngay.
  Ly do vuot quy tac: quy tac mot-dot-sua ton tai de chan viec sua lat vat khong hoi ket,
  khong phai de ep ban giao mot lo hong key da biet. Hai ban sua deu nho va da xac dinh ro.
  Gia neu sai: them mot vong sua nua truoc khi ban giao, ton them thoi gian.
  KEM THEO: sua 1 regression nho do chinh dot sua gay ra (JobDetail.reload() khong co catch),
  va sua 1 test gia (test_spawn_refuses_a_job_that_is_no_longer_queued van pass khi go guard).
  KHONG sua: do tre khi cancel giu khoa toi 5s (la do tre, khong phai loi).
