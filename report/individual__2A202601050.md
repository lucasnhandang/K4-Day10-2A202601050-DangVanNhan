# BÁO CÁO CÁ NHÂN — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đặng Văn Nhân |
| MSSV | 2A202601050 |
| Khóa/Lớp | K4 |
| Tên nhóm/dự án | Quái Kiệt Mộng Mơ |
| Vai trò chính | Role 1 — Pipeline Integrator |
| Repository | <https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo> |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Central configuration | `src/core/config.py::load_settings` | `.env` file, project root | `Settings` dataclass với paths, LLM provider/model, API keys, embedding model, collection names, Crossref query, freshness threshold | Hoàn thành |
| Utility functions | `src/core/utils.py::write_json`, `read_json`, `write_csv`, `write_text`, `now_utc`, `normalize_whitespace`, `safe_slug`, `compact_join`, `first_sentence` | Input data, file paths | Output files, formatted strings, normalized data | Hoàn thành |
| Baseline pipeline | `src/pipelines/phase1.py` | Raw Crossref records, clean schema, embedding model | 8-step pipeline: fetch, clean, build index, test set, evaluate, quality, freshness, report | Hoàn thành |
| Corruption/repair pipeline | `src/pipelines/corruption_flow.py` | Frozen baseline artifacts, raw snapshot | 8-step flow: corrupt, rebuild, evaluate, repair, rebuild repaired, verify, comparison report | Hoàn thành |
| Entry points | `script/run_phase1.py`, `script/run_corruption_flow.py`, `script/run_ui.py` | Command line arguments | Pipeline execution, UI launch | Hoàn thành |
| NiceGUI web application | `src/ui/app.py::PaperMind` | Artifact paths, settings | 3-page web UI: /rag, /data-health, /comparison | Hoàn thành |

Phạm vi của tôi bắt đầu từ contract CP0 và kéo dài xuyên suốt toàn bộ pipeline: từ cấu hình paths/settings, ghép luồng baseline 8 bước, ghép luồng corruption/repair 8 bước, quản lý entry points và giao diện demo. Tôi chịu trách nhiệm tổng thể về integration và đảm bảo tất cả modules hoạt động nhịp nhàng.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Review và merge PRs từ các thành viên khác | Role 2 (Thịnh), Role 3 (Phụng), Role 4 (Mai), Role 5 (Hậu) | Đảm bảo contract alignment: (a) Thịnh: xác nhận PaperRecord frozen dataclass có đủ 11 trường, paper_id từ DOI slug hoạt động đúng; (b) Phụng: xác nhận clean schema khớp REQUIRED_COLUMNS trong quality.py, corruption scenarios nhắm đúng frozen test set; (c) Mai: xác nhận 3 collection name tách biệt, embedding manifest chứa đúng metadata; (d) Hậu: xác nhận frozen test set SHA256 hash, 12 quality gates khớp contract |
| Kiểm tra artifact bắt buộc trước khi chuyển phase | Cả nhóm | Tránh ghi đè baseline, đảm bảo lineage đúng |
| Chốt contract CP0 | Cả nhóm | Stable `paper_id`, raw snapshot cố định, tách ba trạng thái, không đưa secret vào Git |
| Viết báo cáo nhóm | Cả nhóm | Hoàn thiện `report/group_report.md` từ artifact và số liệu thực tế |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây dựng central configuration | `src/core/config.py::load_settings`, `Settings` dataclass | 40+ artifact paths, LLM provider/model settings, API key validation per provider, Crossref query config, freshness threshold 180 ngày | Đọc `src/core/config.py` và `.env` |
| Xây dựng utility functions | `src/core/utils.py` | 9 functions: ensure_parent, write_json/read_json, write_csv, write_text, now_utc, normalize_whitespace, safe_slug, compact_join, first_sentence | Chạy unit tests, kiểm tra output |
| Ghép baseline pipeline 8 bước | `src/pipelines/phase1.py` | Luồng: load/fetch raw → clean → build index → load/build test set → evaluate → quality → freshness → report | Chạy `python script/run_phase1.py` |
| Ghép corruption/repair pipeline 8 bước | `src/pipelines/corruption_flow.py` | Luồng: corrupt → rebuild corrupted index + evaluate → quality/freshness corrupted → repair from raw → rebuild repaired index + evaluate → quality/freshness repaired → verify frozen test set (SHA256) → comparison report | Chạy `python script/run_corruption_flow.py` |
| Tạo entry points | `script/run_phase1.py`, `script/run_corruption_flow.py`, `script/run_ui.py` | 3 scripts chạy pipeline và UI từ command line | Chạy mỗi script, kiểm tra output |
| Xây dựng NiceGUI web UI | `src/ui/app.py` | PaperMind với 3 trang: /rag (RAG Research Assistant), /data-health (artifact inventory + corpus stats), /comparison (3-state metric comparison table) | Mở browser, kiểm tra UI |
| Kiểm tra artifact bắt buộc trước phase | Kiểm tra trong pipeline | Tránh ghi đè baseline, đảm bảo raw/test_set/chroma artifacts tồn tại | Đọc pipeline logs, kiểm tra artifact |

Output tiêu biểu của tôi là `src/pipelines/corruption_flow.py`. Pipeline này điều phối toàn bộ luồng corruption/repair: tạo lỗi có kiểm soát từ raw snapshot, rebuild corrupted index, chạy evaluation, repair bằng cách re-run cleaning từ raw, rebuild repaired index, và sinh comparison report. Pipeline kiểm tra SHA256 của frozen test set để đảm bảo evaluation không bị thay đổi giữa các trạng thái.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline RAG cần được ghép từ nhiều modules độc lập (ingestion, cleaning, retrieval, evaluation, observability). Mỗi module có contract riêng nhưng cần hoạt động nhịp nhàng trong một luồng end-to-end. Cần đảm bảo:
- Paths và settings nhất quán qua tất cả modules
- Raw snapshot cố định để repair có thể phục hồi từ nguồn đáng tin cậy
- Ba trạng thái (baseline, corrupted, repaired) tách biệt, không ghi đè nhau
- Frozen test set được giữ nguyên để comparison có ý nghĩa
- Không đưa secret (API keys) vào Git

### Cách triển khai

**Trong `src/core/config.py`:**
- Tạo `Paths` dataclass chứa 40+ artifact paths, tất cả resolve từ project root
- Tạo `Settings` dataclass chứa LLM provider/model, API keys, embedding model, collection names, Crossref query, freshness threshold
- `load_settings()` đọc `.env`, resolve paths, validate API keys theo provider
- `require_llm_credentials()` kiểm tra API key hợp lệ cho Gemini/OpenAI/etc.

**Trong `src/pipelines/phase1.py`:**
- 8 bước pipeline với artifact dependency checks
- Bước 1: Load raw records từ `data/raw/crossref_records.json` hoặc fetch mới từ Crossref
- Bước 2: Clean bằng `build_clean_dataframe` từ Role 3
- Bước 3: Build ChromaDB index với embedding model từ Role 4
- Bước 4: Load frozen test set hoặc build mới từ clean data
- Bước 5: Evaluate bằng agent từ Role 4 và metrics từ Role 5
- Bước 6: Quality checks từ Role 5
- Bước 7: Freshness report từ Role 5
- Bước 8: Sinh Markdown report

**Trong `src/pipelines/corruption_flow.py`:**
- 8 bước corruption/repair với verification
- Bước 1: Tạo corruption từ frozen test set documents (blank summary, stale date, add noise, duplicates)
- Bước 2: Rebuild corrupted index + evaluate
- Bước 3: Quality/freshness cho corrupted
- Bước 4: Repair từ raw snapshot (re-run cleaning)
- Bước 5: Rebuild repaired index + evaluate
- Bước 6: Quality/freshness cho repaired
- Bước 7: Verify frozen test set unchanged (SHA256 check)
- Bước 8: Sinh comparison report từ ba metrics JSON

**Trong `src/ui/app.py`:**
- NiceGUI web app với 3 trang, custom CSS với Merriweather font
- /rag: RAG Research Assistant với optional LLM agent
- /data-health: Artifact inventory + corpus stats + freshness
- /comparison: 3-state metric comparison table + report

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `.env` (API keys), `data/raw/crossref_records.json`, clean schema từ Role 3, embedding model từ Role 4, evaluation metrics từ Role 5 |
| Output | Baseline/corrupted/repaired artifacts, quality JSON, freshness JSON, comparison report, web UI |
| Module phụ thuộc | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `src/retrieval/index.py`, `src/evaluation/metrics.py`, `src/observability/quality.py` |
| Contract CP0 | Stable `paper_id` (DOI-derived slug), raw snapshot cố định tại `data/raw/crossref_records.json`, ba collection tách biệt (`papers-baseline`, `papers-corrupted`, `papers-repaired`), không đưa secret vào Git |

### Cách xác minh

```bash
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp
```

- **Kết quả mong đợi:** Toàn bộ unit tests pass; pipeline chạy end-to-end không crash; artifacts sinh ra đúng contract.
- **Kết quả thực tế:** `11 passed in 11.95s` trên Python 3.13.14.
- **Artifact/log:** `data/raw/`, `data/clean/`, `data/chroma/`, `data/eval/`, `data/results/`, `data/quality/`, `data/reports/`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần đảm bảo repair có thể phục hồi dữ liệu từ nguồn đáng tin cậy, không phải từ corrupted data. Đồng thời cần tách ba trạng thái (baseline, corrupted, repaired) để comparison có ý nghĩa.
- **Các phương án đã cân nhắc:** (1) Repair từ corrupted data (sửa lỗi trực tiếp); (2) repair từ raw snapshot (re-run cleaning); (3) repair từ clean baseline (copy baseline).
- **Phương án đã chọn:** Phương án 2 — repair từ raw snapshot tại `data/raw/crossref_records.json` bằng cách re-run cleaning pipeline.
- **Lý do:** Raw snapshot là nguồn dữ liệu nguyên bản từ Crossref, chưa qua processing. Re-run cleaning đảm bảo repaired data được tạo lại từ cùng contract với baseline, không phụ thuộc vào corrupted data. Cách này cũng reproducible: nếu raw snapshot không thay đổi thì repaired data sẽ giống hệt baseline.
- **Bằng chứng quyết định phù hợp:** Repaired data có 24 dòng, 12/12 quality checks pass, freshness `fresh`, retrieval hit 0,90 và judge accuracy 0,60 — giống hệt baseline. SHA256 check xác nhận frozen test set không bị thay đổi.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi:** Pipeline crash khi chạy corruption flow vì thiếu baseline artifacts (raw records, clean data, ChromaDB index). Mỗi role tự chạy standalone nên không kiểm tra artifact dependencies.
- **Bước tái hiện:** Chạy `python script/run_corruption_flow.py` trên repository mới clone, chưa chạy baseline pipeline.
- **Nguyên nhân gốc:** Corruption flow giả định baseline artifacts đã tồn tại, nhưng không có validation step. Nếu một role chạy standalone mà không chạy baseline trước, pipeline sẽ crash với FileNotFoundError.
- **Cách xử lý:** Thêm artifact dependency checks ở đầu `corruption_flow.py`: kiểm tra sự tồn tại của `data/raw/crossref_records.json`, `data/clean/papers_clean.json`, `data/chroma/` directory trước khi bắt đầu corruption. Nếu thiếu artifact, pipeline sẽ dừng lại và hiển thị thông báo rõ ràng thay vì crash.
- **Cách xác minh sau khi sửa:** Chạy `python script/run_corruption_flow.py` trên repository mới clone — pipeline dừng lại và hiển thị thông báo "Missing baseline artifacts. Please run phase1 pipeline first." thay vì crash.
- **Điều học được:** Pipeline integrator phải luôn validate dependencies trước khi chạy, không giả định bất kỳ artifact nào đã tồn tại. Thông báo lỗi rõ ràng giúp developer khác debug nhanh hơn.

## 7. Hiểu biết về luồng end-to-end

1. **Ingestion:** Crossref REST API trả raw response; Role 2 (Thịnh) lưu snapshot tại `data/raw/crossref_response.json`, parse thành `PaperRecord` với stable `paper_id` từ DOI, lưu `data/raw/crossref_records.json`. Retry/backoff xử lý HTTP 429, 500, 503.
2. **Cleaning:** Role 3 (Phụng) normalize text, parse ngày, nối authors/categories, tính `age_days`, `summary_chars`, `extracted_skills`, tạo `text_for_embedding`. Deduplicate theo `paper_id`, sắp xếp theo độ mới, ghi clean CSV/JSON.
3. **Indexing:** Role 4 (Mai) dùng `all-MiniLM-L6-v2` tạo embedding, lưu vào ChromaDB với ba collection tách biệt (`papers-baseline`, `papers-corrupted`, `papers-repaired`). Metadata giữ `paper_id`, title, nội dung cần thiết.
4. **Evaluation:** Role 5 (Hậu) tạo frozen test set 10 câu từ clean data, giữ `ground_truth_doc_ids`. Agent trả lời, evaluator lấy document ID trong retrieval trace, đo retrieval hit, token F1, judge accuracy/score.
5. **Orchestration (vai trò của tôi):** Tôi ghép tất cả thành pipeline end-to-end: baseline 8 bước, corruption/repair 8 bước. Kiểm tra artifact dependencies, đảm bảo contract CP0 (stable `paper_id`, raw snapshot cố định, ba trạng thái tách biệt), quản lý paths/settings, tạo entry points và web UI.
6. **Observability:** Role 5 chạy 12 quality checks, freshness report. Tôi sử dụng kết quả này để quyết định pipeline đã hoàn thành và sinh báo cáo tổng hợp.
7. **Repair:** Repair chạy từ raw snapshot bằng cách re-run cleaning, không sửa tay corrupted data. Rebuild repaired index, chạy lại evaluation, sinh comparison report.
8. **Verification:** SHA256 check đảm bảo frozen test set không bị thay đổi giữa baseline, corrupted và repaired. Comparison report so sánh ba metrics JSON để thấy tác động của corruption và hiệu quả của repair.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 0,90 | 0,70 | 0,90 | Corruption giảm 20 điểm %, repair phục hồi hoàn toàn |
| `mean_token_f1` | 0,1930 | 0,1717 | 0,1981 | Giảm 0,0213 rồi phục hồi cao hơn baseline 0,0050 |
| `judge_accuracy` | 0,60 | 0,50 | 0,60 | Giảm 10 điểm % rồi phục hồi hoàn toàn |
| `mean_judge_score` | 3,40 | 3,00 | 3,50 | Giảm 0,40 rồi tăng lại 0,50 |
| Quality checks | 12 pass / 0 fail | 8 pass / 4 fail | 12 pass / 0 fail | Bốn lỗi truy về corruption log |
| Freshness status | fresh, 0 stale | stale, 2 stale | fresh, 0 stale | Stale-date scenario được phát hiện và phục hồi đúng |

### Kết luận từ số liệu

1. **Tác động của corruption — từ góc nhìn pipeline integrator:** 4 scenarios cộng hưởng làm retrieval hit rate giảm 20 điểm phần trăm (0,90→0,70). Phân tích corruption log cho thấy 2 scenarios ảnh hưởng trực tiếp lên embedding quality: `blank_summary` loại bỏ nội dung chính (text_for_embedding 1804→310 chars) và `add_noise` chèn boilerplate (1697→6348 chars). Cả hai đều phá vỡ vector MiniLM — đây là cơ chế nhân quả rõ ràng nhất. Tuy nhiên, muốn kết luận scenario nào gây suy giảm lớn nhất cần chạy ablation: corruption từng loại độc lập và đo metric delta riêng.

2. **Pipeline orchestration — tại sao repair phục hồi hoàn toàn:** Với tư cách pipeline integrator, tôi quan sát rằng repair thành công nhờ 3 yếu tố: (a) raw snapshot không bị corruption thay đổi — `data/raw/crossref_records.json` luôn giữ 24 records xuyên suốt flow, (b) cleaning deterministic — `build_clean_dataframe()` cùng input raw → cùng output DataFrame, (c) frozen test set SHA256-verified — evaluation không bị thay đổi giữa ba trạng thái. Điều này xác nhận design decision của tôi:repair từ raw snapshot thay vì từ corrupted data.

3. **LLM non-determinism — cần separate judge model:** Token F1 repaired (0,1981) > baseline (0,1930) và judge score repaired (3,50) > baseline (3,40). Đây là biến động của LLM, không phải repair "cải thiện mô hình". Bằng chứng: `temperature=0.0` đã set nhưng Gemini 2.5 Flash vẫn variance. Judge accuracy 60% — 4/10 câu sai, có thể do cùng model cho answer và judge. Hướng cải thiện: tách judge model khỏi answer model để tránh bias.

4. **Ablation test — hạn chế quan trọng cần thừa nhận:** Không thể quy toàn bộ mức giảm cho riêng một scenario vì 4 corruption chạy cùng lúc. Cần chạy 4 experiments riêng lẻ: blank_summary alone, stale_date alone, add_noise alone, duplicates alone → đo metric delta từng scenario. Đây là hướng cải thiện quan trọng nhất cho phiên bản tiếp theo.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Contract CP0 là nền tảng — và nó đã cứu pipeline:** Stable `paper_id`, raw snapshot cố định, ba trạng thái tách biệt, không đưa secret vào Git. Nếu contract này bị phá vỡ, toàn bộ pipeline sẽ sai lineage và comparison không có ý nghĩa. Bằng chứng: corrupted data có 26 rows, 4 quality checks fail, nhưng raw records vẫn giữ nguyên 24 records — nhờ đó repair có thể phục hồi hoàn toàn.
2. **Pipeline integrator phải validate dependencies — không giả định bất kỳ artifact nào:** Khi chạy corruption flow trên repository mới clone, pipeline crash với FileNotFoundError vì thiếu baseline artifacts. Sau khi thêm dependency checks, pipeline dừng lại và hiển thị thông báo rõ ràng thay vì crash. Điều này quan trọng vì mỗi role có thể chạy standalone.
3. **Repair từ raw snapshot đáng tin cậy hơn repair từ corrupted data:** Re-run cleaning từ raw snapshot đảm bảo repaired data được tạo lại từ cùng contract với baseline, reproducible và không phụ thuộc vào corrupted data. Nếu dùng corrupted data làm source cho repair, ta chỉ "che lỗi" chứ không chứng minh cleaning pipeline có thể tự phục hồi.

### Nếu có thêm thời gian

Tôi sẽ:
- Thêm integration test end-to-end với mock Crossref/LLM để regression tích hợp không phụ thuộc API
- Thay absolute path trong generated reports bằng đường dẫn tương đối
- Thêm version/hash cho test set và raw snapshot để reproducibility tốt hơn
- Cải thiện web UI với thêm visualization cho metrics trend qua nhiều lần chạy

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
