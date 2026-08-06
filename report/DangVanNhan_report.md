# BÁO CÁO CÁ NHÂN — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đặng Văn Nhân |
| MSSV | 2A202601050 |
| Khóa/Lớp | K4 |
| Tên nhóm/dự án | K4-Day10-2A202601050-DangVanNhan |
| Vai trò chính | Role 1 — Pipeline integrator |
| Repository | <https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo.git> |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cấu hình và contract CP0 | `src/core/config.py::Paths`, `Settings`, `load_settings`, `normalized_provider`, `require_llm_credentials` | `.env`, biến môi trường | `Settings`/`Paths` dùng chung cho toàn bộ pipeline, khóa đường dẫn artifact của ba trạng thái | Hoàn thành |
| Tiện ích dùng chung | `src/core/utils.py` (`write_json`, `read_json`, `write_csv`, `ensure_parent`, `now_utc`, `normalize_whitespace`, `safe_slug`, `first_sentence`...) | Giá trị/DataFrame thô từ các module | Hàm I/O và xử lý text an toàn cho mọi role | Hoàn thành |
| Orchestration Phase 1 (baseline) | `src/pipelines/phase1.py::main`, `_persist_clean_data`, `_load_or_build_test_set`, `_source_summary` | Raw source, clean/index/eval module của các role khác | 8 bước tuần tự: fetch → clean → index → test set → evaluate → quality → freshness → report | Hoàn thành |
| Orchestration Phase 2 (corruption/repair) | `src/pipelines/corruption_flow.py::main`, `_require_phase1_artifacts`, `_load_frozen_target_ids`, `_persist_dataframe`, `_evaluate` | Artifact Phase 1 đã có sẵn | Corrupted/repaired dataset, metrics và `comparison_report.md` | Hoàn thành |
| Giao diện demo | `src/ui/app.py` (NiceGUI): `home_page`, `rag_page`, `data_health_page`, `comparison_page` | Artifact trên đĩa (clean data, quality/freshness JSON, comparison report) | Ba trang demo: hỏi-đáp corpus, data health, so sánh baseline/corrupted/repaired | Hoàn thành |
| Entrypoint | `script/run_phase1.py`, `script/run_corruption_flow.py`, `script/run_ui.py` | Gọi trực tiếp `pipelines.phase1.main()`, `pipelines.corruption_flow.main()`, `ui.app.run_app()` | Lệnh chạy end-to-end thống nhất cho cả nhóm | Hoàn thành |

Phạm vi của tôi không tạo ra dữ liệu nghiệp vụ (raw, clean, embedding, metrics) mà điều phối đúng thứ tự các module do Role 2–5 sở hữu, đảm bảo artifact không bị ghi đè giữa các trạng thái và chặn báo cáo nếu điều kiện tiên quyết không thỏa.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Chốt CP0 contract (stable `paper_id`, raw snapshot cố định, ba trạng thái tách path) | Cả nhóm | Mọi module dùng chung `Settings.paths`, tránh hard-code đường dẫn |
| Kiểm tra artifact Phase 1 trước khi chạy Phase 2 | Role 3, Role 4, Role 5 | `_require_phase1_artifacts` chặn chạy corruption flow nếu thiếu clean CSV, baseline metrics, frozen test set hoặc raw snapshot |
| Hiển thị kết quả evaluation/quality/freshness lên UI | Role 5 | Trang `/data-health` và `/comparison` đọc trực tiếp JSON thật, không hard-code số liệu |
| Kiểm tra rebuild index không rò rỉ giữa các trạng thái | Role 4 | Xác nhận `LocalEmbeddingIndex.build` xóa và tạo lại đúng collection theo path artifact truyền vào |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Ghép luồng baseline 8 bước, in log `[n/8]` | `phase1.py::main` | `data/raw/`, `data/clean/`, `data/embeddings/`, `data/chroma/`, `data/eval/test_set.json`, `data/results/baseline_*`, `data/quality/`, `data/reports/phase1_report.md` | Chạy `uv run python script/run_phase1.py` rồi kiểm tra artifact tồn tại |
| Ghép luồng corruption/repair 8 bước có kiểm tra tiền điều kiện | `corruption_flow.py::main`, `_require_phase1_artifacts` | `FileNotFoundError` nếu thiếu artifact Phase 1; nếu đủ thì sinh corrupted/repaired data, metrics và comparison report | Xóa thử một artifact Phase 1 rồi chạy lại flow, quan sát lỗi rõ ràng thay vì crash mơ hồ |
| Bảo vệ tính toàn vẹn của frozen test set trong Phase 2 | `corruption_flow.py::main` (SHA-256 hash trước/sau) | Nếu test set bị thay đổi giữa quá trình, pipeline `raise RuntimeError` và không sinh comparison report | Đọc code phần hash trước bước 1 và hash lại ở bước 7 |
| Xây dựng giao diện demo NiceGUI | `src/ui/app.py` | Ba trang `/rag`, `/data-health`, `/comparison`, tự hiển thị placeholder khi thiếu artifact thay vì crash | Chạy `uv run python script/run_ui.py` và thao tác trên cả ba trang |
| Chuẩn hóa cấu hình, tránh secret trong code | `src/core/config.py::load_settings`, `require_llm_credentials` | API key chỉ đọc từ `.env`; báo lỗi rõ ràng nếu thiếu credential đúng provider | Chạy pipeline không có `.env` hợp lệ, quan sát `RuntimeError` mô tả đúng thiếu gì |

Output tiêu biểu của tôi là cơ chế hash SHA-256 trên frozen test set trong `corruption_flow.py`. Hash được lấy ngay trước khi corrupt dữ liệu và so lại sau toàn bộ 7 bước còn lại; nếu khác, hệ thống từ chối publish `comparison_report.md` với thông báo "Frozen test set changed during Phase 2; refusing to publish comparison". Đây là lớp bảo vệ trực tiếp cho tính đúng đắn của mọi kết luận baseline/corrupted/repaired trong báo cáo nhóm.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Năm role phụ thuộc trực tiếp vào output của nhau (raw → clean → index → eval → quality/report). Nếu chạy sai thứ tự, ghi đè artifact baseline khi thử corruption, hoặc vô tình làm lệch test set giữa các lần chạy, mọi so sánh baseline/corrupted/repaired sẽ mất ý nghĩa mà không ai nhận ra ngay. Cần một lớp orchestration kiểm tra tiền điều kiện, tách path artifact theo trạng thái, và chặn cứng khi phát hiện sai lệch thay vì âm thầm sinh báo cáo sai.

### Cách triển khai

`phase1.py::main()` chạy tuần tự 8 bước, mỗi bước in log `[n/8]` để dễ debug khi pipeline dừng giữa chừng: fetch source records (cache nếu đã có, không gọi lại Crossref trừ khi `refresh_source=True`) → `build_clean_dataframe` (raise `ValueError` nếu rỗng) và ghi CSV/JSON → build Chroma index qua `LocalEmbeddingIndex.build` → load test set đã đóng băng nếu có, ngược lại build mới → `evaluate_pipeline` → `run_data_quality_checks` → `build_freshness_report` → `generate_phase1_report`.

`corruption_flow.py::main()` trước tiên gọi `_require_phase1_artifacts` để xác nhận clean CSV, baseline metrics, frozen test set và raw snapshot đã tồn tại, nếu thiếu thì dừng ngay bằng `FileNotFoundError` thay vì chạy nửa chừng rồi lỗi khó hiểu. Sau đó: corrupt dữ liệu chỉ nhắm vào các `paper_id` thuộc frozen test set (nhận từ Role 3) → rebuild index + evaluate trạng thái corrupted → quality/freshness corrupted → **repair đọc lại từ `data/raw/crossref_records.json`**, hoàn toàn không dùng dữ liệu corrupted làm nguồn → rebuild index + evaluate trạng thái repaired → quality/freshness repaired → so hash test set trước/sau, nếu khớp mới `generate_corruption_report` so sánh ba trạng thái.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Artifact và module do Role 2–5 bàn giao: raw records, clean dataframe, embedding index, frozen test set, evaluation/quality/freshness function |
| Output | `Settings`/`Paths` dùng chung, artifact baseline/corrupted/repaired tách path, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`, giao diện NiceGUI |
| Module phụ thuộc | `src/ingestion/*`, `src/retrieval/*`, `src/evaluation/*`, `src/observability/*` |
| Module sử dụng output | `src/ui/app.py`, báo cáo nhóm và báo cáo cá nhân của các thành viên |
| Điều kiện lỗi cần xử lý | Thiếu artifact Phase 1, clean dataframe rỗng, test set không hợp lệ, frozen test set bị thay đổi giữa Phase 2, thiếu credential LLM |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp
```

- **Kết quả mong đợi:** Phase 1 sinh đủ artifact bắt buộc theo đúng thứ tự; Phase 2 dừng có kiểm soát nếu thiếu điều kiện tiên quyết, chỉ publish comparison report khi frozen test set không đổi.
- **Kết quả thực tế:** Cả hai entrypoint chạy hoàn chỉnh trên môi trường phát triển và sinh đủ artifact liệt kê trong `report/group_report.md`; bộ test `11 passed in 11.95s` trên Python 3.13.14.
- **Artifact/log:** `data/reports/phase1_report.md`, `data/reports/corruption_report.md`, `data/results/corruption_log.json`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Phase 2 chạy nhiều bước ghi đè dữ liệu qua nhiều lần (corrupt, rebuild, repair, rebuild lại). Nếu test set bị tái sinh hoặc chỉnh tay giữa các bước — dù vô tình — thì delta retrieval hit/judge accuracy giữa ba trạng thái không còn đo đúng tác động của corruption/repair.
- **Các phương án đã cân nhắc:** (1) không kiểm tra gì, tin tưởng quy trình thủ công của nhóm; (2) chỉ log cảnh báo nếu phát hiện thay đổi rồi vẫn tiếp tục sinh báo cáo; (3) hash SHA-256 test set trước và sau toàn bộ Phase 2, chặn cứng việc publish nếu khác.
- **Phương án đã chọn:** Phương án 3.
- **Lý do:** Toàn bộ giá trị của bài lab nằm ở việc so sánh ba trạng thái trên cùng một test set; một cảnh báo có thể bị bỏ qua, còn việc chặn cứng buộc lỗi phải được xử lý trước khi có báo cáo sai được công bố.
- **Bằng chứng quyết định phù hợp:** `comparison_report.md` chỉ tồn tại khi `corruption_flow.py::main()` chạy hết 8 bước mà không raise `RuntimeError`; trong log chạy thực tế, hash trước/sau khớp và report được sinh với đúng 10 câu hỏi giống nhau ở cả ba answer files.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Lần chạy `pytest` đầu tiên không chỉ định `--basetemp` bị chặn quyền ghi tại thư mục temp mặc định của tài khoản Windows, khiến bộ test không khởi động được dù code không có lỗi logic.
- **Lệnh hoặc bước tái hiện:** Chạy `python -m pytest -q` (không có `--basetemp`) trên máy Windows dùng tài khoản không có quyền ghi đầy đủ vào thư mục temp hệ thống.
- **Nguyên nhân gốc:** Fixture `tmp_path`/cache của pytest mặc định tạo thư mục trong `AppData/Local/Temp` của tài khoản Windows; đây là giới hạn quyền hệ điều hành, không phải lỗi assertion trong test hay trong pipeline.
- **Cách xử lý:** Chỉ định `--basetemp .test-tmp` để pytest tạo thư mục tạm ngay trong workspace, kèm `-p no:cacheprovider` để tránh ghi cache vào vị trí không có quyền.
- **Cách xác minh sau khi sửa:** `python -m pytest -q -p no:cacheprovider --basetemp .test-tmp` chạy thành công `11 passed in 11.95s` trên Python 3.13.14.
- **Điều học được:** Khi một lệnh "không chạy được", cần phân biệt rõ lỗi môi trường (quyền hệ điều hành, đường dẫn) với lỗi logic trước khi đi sâu debug code; báo cáo phải ghi đúng bản chất lỗi thay vì quy chung là "test fail".

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Role 2 gọi Crossref REST API, lưu raw response và raw records trước khi parse. Role 3 nhận raw records, chuẩn hóa text, parse ngày, tính `age_days`, tạo `text_for_embedding`, lọc và deduplicate theo `paper_id` để ra clean dataset. Role 4 dùng MiniLM sinh embedding từ `text_for_embedding` và lưu vào ChromaDB theo collection riêng cho từng trạng thái.
2. Role 5 sinh evaluation set 10 câu từ clean dataframe, `ground_truth_doc_ids` lấy từ `paper_id` thật để đảm bảo có thể đối chiếu với index. Agent của Role 4 trả lời và để lại retrieval trace; evaluator so các document ID trong trace với `ground_truth_doc_ids` để tính hit rate, đồng thời so câu trả lời với ground truth bằng token F1 và LLM judge.
3. Quality checks kiểm tra tính đúng đắn tĩnh của một snapshot dữ liệu tại một thời điểm (schema, null, unique, độ dài, tính hợp lệ của ngày). Freshness monitoring nhìn theo trục thời gian: dữ liệu có còn "mới" so với ngưỡng 180 ngày hay không, có bao nhiêu dòng stale. Hai khái niệm bổ sung cho nhau: một dataset có thể pass toàn bộ quality checks nhưng vẫn `stale`.
4. Việc tôi trực tiếp đảm bảo bằng cơ chế hash: dùng cùng test set cho cả ba trạng thái là điều kiện để biến duy nhất thay đổi giữa ba lần đánh giá là dữ liệu (baseline/corrupted/repaired), không phải câu hỏi. Nếu câu hỏi khác nhau, mọi delta metric không còn quy được về corruption hay repair.
5. Repair được xem là thành công khi: row count/schema quay lại như baseline (`data/quality/*_quality.json` pass 12/12), freshness trở lại `fresh` (0 stale rows), và retrieval hit rate/judge accuracy đo trên cùng test set trở lại đúng giá trị baseline — tất cả đối chiếu được qua `data/reports/corruption_report.md` do chính orchestration của tôi sinh ra.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 0,90 | 0,70 | 0,90 | Phục hồi hoàn toàn; xác nhận orchestration repair-từ-raw hoạt động đúng |
| `mean_token_f1` | 0,1930 | 0,1717 | 0,1981 | Giảm rồi phục hồi cao hơn baseline một chút, nằm trong biến động của LLM generation |
| `judge_accuracy` | 0,60 | 0,50 | 0,60 | Phục hồi hoàn toàn, đồng bộ với retrieval hit rate |
| `mean_judge_score` | 3,40 | 3,00 | 3,50 | Giảm rồi tăng nhẹ hơn baseline, cùng xu hướng với token F1 |
| Quality checks | 12 pass / 0 fail | 8 pass / 4 fail | 12 pass / 0 fail | Đúng như log `_require_phase1_artifacts` và pipeline mong đợi |
| Freshness status | fresh, 0 stale | stale, 2 stale | fresh, 0 stale | Khớp với scenario `stale_date` nhắm vào 2 document trong frozen set |

### Kết luận từ số liệu

1. Bốn corruption scenario áp trên các document thuộc frozen test set → 4 quality checks fail, freshness chuyển `stale` → retrieval hit rate giảm từ 0,90 xuống 0,70 vì các document bị hỏng nằm đúng trong tập câu hỏi được đo, không phải ngẫu nhiên bị bỏ qua.
2. Repair rebuild toàn bộ từ `data/raw/crossref_records.json` qua đúng orchestration Phase 1 (không patch dữ liệu corrupted) → quality/freshness về baseline → retrieval hit rate và judge accuracy phục hồi hoàn toàn trên cùng test set đã được xác nhận không đổi bằng hash.

Corruption ảnh hưởng rõ nhất đến vai trò orchestration của tôi là việc bốn scenario đều chủ động nhắm vào ID trong frozen test set (do Role 3 triển khai theo yêu cầu contract mà tôi và nhóm thống nhất ở CP0) — nếu không có ràng buộc này, retrieval hit rate có thể không đổi dù dữ liệu đã hỏng, khiến kết luận về "impact của corruption" trở nên vô nghĩa.

Kết quả khác kỳ vọng ban đầu là token F1 và judge score của repaired cao hơn nhẹ baseline dù dữ liệu gần như giống hệt. Tôi không xem đây là lỗi orchestration vì mọi artifact (row count, schema, quality, freshness) đều khớp baseline tuyệt đối; chênh lệch nhỏ này nằm ở tầng LLM generation/judge không hoàn toàn deterministic, nằm ngoài phạm vi orchestration mà tôi kiểm soát.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Một pipeline nhiều module chỉ đáng tin khi có kiểm tra tiền điều kiện tường minh (`_require_phase1_artifacts`) thay vì giả định module trước đã chạy đúng.
2. Bảo vệ tính bất biến của biến kiểm soát (frozen test set) bằng cơ chế kiểm chứng được (hash) quan trọng hơn việc chỉ quy ước bằng tài liệu — quy ước có thể bị quên, hash thì không.
3. Orchestration nên fail rõ ràng và sớm (raise lỗi có thông điệp cụ thể) thay vì âm thầm tiếp tục với dữ liệu thiếu hoặc sai, vì chi phí debug một báo cáo sai sau khi đã công bố cao hơn nhiều so với việc dừng sớm.

### Nếu có thêm thời gian

Tôi sẽ thêm một lệnh kiểm tra tổng thể (`script/verify_artifacts.py`) chạy độc lập với hai entrypoint chính, đối chiếu toàn bộ đường dẫn trong `Settings.paths` với artifact thực tế trên đĩa và in báo cáo pass/fail giống quality checks, để bất kỳ thành viên nào cũng có thể tự xác minh môi trường của mình trước khi nộp bài mà không cần chạy lại toàn bộ pipeline tốn thời gian gọi API thật.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đặng Văn Nhân

**MSSV:** 2A202601050

**Ngày xác nhận:** 2026-08-06
