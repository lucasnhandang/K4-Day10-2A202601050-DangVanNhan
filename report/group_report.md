# BÁO CÁO NHÓM — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4 |
| Dự án | K4-Day10-2A202601050-DangVanNhan |
| Repository | <https://github.com/lucasnhandang/K4-Day10-2A202601050-DangVanNhan> |
| Ngày hoàn thành artifact | 2026-08-06 |
| Phiên bản báo cáo | Dựa trên commit `cbc86ca` (`feat: update phase 2`) |

### Thành viên và phân công theo 5 vai trò

| Vai trò | Thành viên | Trách nhiệm chính | Module và deliverable sở hữu |
| ---: | --- | --- | --- |
| 1 | Đặng Văn Nhân | Pipeline integrator | `src/core/`, `src/pipelines/`, `script/`; điều phối contract, ghép luồng baseline/corruption/repair, release và giao diện demo |
| 2 | Giáp Hoàng Thịnh | Ingestion owner | `src/ingestion/crossref.py`, `data/raw/`; lấy Crossref, retry/backoff, parse và raw lineage |
| 3 | Nguyễn Trần Gia Phụng | Cleaning & corruption owner | `src/ingestion/cleaning.py`, `src/ingestion/corruption.py`, `data/clean/`; clean schema, corruption có kiểm soát và repair |
| 4 | Mai | RAG & agent owner | `src/retrieval/`, `data/embeddings/`, `data/chroma/`; MiniLM, ChromaDB, semantic search, exact lookup và agent |
| 5 | Bùi Công Hậu | Evaluation & observability | `src/evaluation/`, `src/observability/`, `data/eval/`, `data/results/`, `data/quality/`, `data/reports/`; test set, metrics, quality, freshness và báo cáo |

> MSSV của các thành viên và họ tên đầy đủ của Mai chưa được ghi trong repository. Nhóm cần bổ sung trước khi nộp chính thức.

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành luồng dữ liệu end-to-end từ Crossref đến đánh giá RAG, quan sát chất lượng, tạo lỗi có kiểm soát và khôi phục từ raw snapshot. Baseline gồm 24 raw records, 24 clean records, embedding manifest, ba Chroma collection tách biệt, test set cố định 10 câu, answer/metric JSON và báo cáo Markdown. Baseline đạt retrieval hit rate 90%, mean token F1 0,1930, judge accuracy 60%, mean judge score 3,40/5; 12/12 quality checks pass và freshness ở trạng thái `fresh`.

Bốn corruption scenario được áp dụng trên các tài liệu thuộc frozen evaluation set: xóa summary, làm cũ ngày xuất bản, thêm noise vào text embedding và tạo duplicate. Dữ liệu corrupted tăng lên 26 dòng, chỉ còn 8/12 quality checks pass, có 2 dòng stale; retrieval hit rate giảm còn 70%, judge accuracy còn 50% và mean judge score còn 3,00. Repair được thực hiện bằng cách chạy lại cleaning từ `data/raw/crossref_records.json`, không sửa tay dữ liệu corrupted. Sau repair, dữ liệu trở về 24 dòng, 12/12 checks pass, freshness trở lại `fresh`; retrieval hit rate và judge accuracy phục hồi đúng baseline, còn token F1 và judge score nhỉnh hơn nhẹ. Giới hạn chính là tập đánh giá chỉ có 10 câu, chưa có câu `categories`, Ragas chưa bật và một số artifact báo cáo đang lưu absolute path của máy đã chạy pipeline.

## 3. Kiến trúc, luồng dữ liệu và trách nhiệm 5 role

### Luồng end-to-end

```text
Crossref REST API
  -> raw response + parsed raw records                      [Role 2]
  -> cleaning, schema validation, stable paper_id          [Role 3]
  -> MiniLM embeddings + ChromaDB index                    [Role 4]
  -> frozen test set + agent evaluation                    [Role 5]
  -> quality/freshness checks + baseline report            [Role 5]
  -> orchestration và kiểm tra artifact                    [Role 1]
  -> controlled corruption                                 [Role 3]
  -> corrupted index + evaluation                          [Role 4 + Role 5]
  -> repair từ raw snapshot                                [Role 3]
  -> repaired index + evaluation + comparison report       [Role 1 + Role 4 + Role 5]
```

### Kết quả theo từng vai trò

#### Role 1 — Pipeline integrator: Nhân

- Chốt contract CP0: stable `paper_id`, raw snapshot cố định, tách ba trạng thái và không đưa secret vào Git.
- Ghép `src/pipelines/phase1.py` theo 8 bước: load/fetch raw, clean, build index, load/build test set, evaluate, quality, freshness, report.
- Ghép `src/pipelines/corruption_flow.py`: corrupt, rebuild, evaluate, repair từ raw, rebuild/evaluate repaired và sinh comparison report.
- Quản lý đường dẫn/cấu hình trong `src/core/config.py`; bổ sung entrypoint trong `script/` và giao diện Streamlit tại `src/ui/app.py`.
- Kiểm tra các artifact bắt buộc tồn tại trước khi chuyển phase, tránh ghi đè baseline.

#### Role 2 — Ingestion owner: Thịnh

- Hiện thực `PaperRecord` và parser Crossref.
- Tạo `paper_id` ổn định từ DOI bằng chuẩn hóa lowercase/slug.
- Lưu nguyên raw response trước khi parse và xuất 24 records tại `data/raw/crossref_records.json`.
- Có retry/backoff cho HTTP 429, 500, 503, timeout và connection error.
- Bàn giao các trường title, summary, authors, categories, published/updated và URL để cleaning không phải đoán dữ liệu.

#### Role 3 — Cleaning & corruption owner: Phụng

- Chuẩn hóa text, parse ngày, nối authors/categories, tính `age_days`, `summary_chars`, `extracted_skills` và tạo `text_for_embedding`.
- Loại record không đạt contract, deduplicate theo `paper_id`, sắp xếp theo độ mới và ghi clean CSV/JSON.
- Tạo bốn corruption scenario có log before/after và ID tài liệu bị ảnh hưởng.
- Repair bằng cách nạp lại raw records rồi chạy lại `build_clean_dataframe`, không sao chép hoặc sửa tay baseline.

#### Role 4 — RAG & agent owner: Mai

- Dùng `sentence-transformers/all-MiniLM-L6-v2` để tạo embedding.
- Lưu embedding manifest và index bằng ChromaDB; tách collection `papers-baseline`, `papers-corrupted`, `papers-repaired`.
- Metadata giữ `paper_id`, title và nội dung cần thiết để truy vết kết quả.
- Cung cấp semantic search, exact lookup theo `paper_id`/title và agent có tool trace.
- Rebuild index cho corrupted/repaired để phép so sánh phản ánh đúng trạng thái dữ liệu.

#### Role 5 — Evaluation & observability: Hậu

- Tạo frozen `data/eval/test_set.json` gồm 10 câu từ clean dataframe; `ground_truth_doc_ids` lấy từ `paper_id` thật.
- Đánh giá retrieval hit, token F1 và LLM judge; lưu answers chi tiết và metrics tổng hợp cho ba trạng thái.
- Chạy 12 quality checks về schema, row count, ID, title/summary, embedding text, ngày và freshness.
- Sinh freshness report với ngưỡng 180 ngày và báo cáo baseline/comparison từ JSON thật.
- Đối chiếu cùng một test set giữa baseline, corrupted và repaired để các delta có ý nghĩa.

## 4. Cấu hình và cách tái hiện

### Cấu hình không chứa secret

| Cấu hình | Giá trị |
| --- | --- |
| Python | `>=3.11,<3.14`; lần kiểm tra báo cáo dùng Python 3.13.14 |
| `LLM_PROVIDER` mặc định | `gemini` |
| `LLM_MODEL` mặc định | `gemini-2.5-flash` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Crossref query | `agentic retrieval augmented generation large language model` |
| Số Crossref records tối đa | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày |
| Test set seed | 42 |
| Test set size | 10 |

API key chỉ cấu hình qua `.env`; không đưa giá trị secret vào báo cáo hoặc source.

### Lệnh cài đặt và chạy

```bash
uv sync
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
uv run python script/run_ui.py
```

Nếu môi trường không có `uv` nhưng đã cài package và dependency:

```bash
python -m pip install -e ".[dev]"
python script/run_phase1.py
python script/run_corruption_flow.py
python script/run_ui.py
```

Kiểm thử cục bộ:

```bash
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp
```

Kết quả kiểm tra ngày 2026-08-06: **11 passed in 11.95s**. `uv` không có trong môi trường kiểm tra hiện tại nên test được chạy bằng Python 3.13.14. Lần chạy test đầu tiên không chỉ định `--basetemp` bị chặn quyền tại thư mục temp hệ thống; đây là lỗi môi trường, không phải test assertion.

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API |
| Query | `agentic retrieval augmented generation large language model` |
| Filter tại lần sinh baseline | `from-pub-date:2026-02-07,has-abstract:true` |
| Raw records | 24 |
| Clean records | 24 |
| Retryable status | 429, 500, 503; kèm retry cho timeout/connection error |
| Raw artifacts | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` |

### Clean schema

| Trường | Kiểu/ý nghĩa | Xử lý |
| --- | --- | --- |
| `paper_id` | Stable document ID | Sinh từ DOI normalized/slug; bắt buộc, unique |
| `doi` | DOI nguồn | Giữ để truy lineage |
| `title`, `summary` | Nội dung paper | Normalize whitespace; bắt buộc không rỗng |
| `authors`, `categories` | Danh sách metadata | Chuẩn hóa và có thêm bản joined |
| `published`, `updated` | Ngày nguồn | Parse về ngày chuẩn; dùng `published` tính freshness |
| `age_days` | Tuổi tài liệu | Chênh lệch giữa run time và `published`, phải không âm |
| `summary_chars` | Độ dài summary | Phải khớp summary đã normalize |
| `text_for_embedding` | Nội dung đưa vào MiniLM | Ghép title, summary và metadata có ích |
| `source` | Nguồn | Ghi Crossref để truy vết |

Các bước lọc/deduplicate không làm mất record trong baseline hiện tại: 24 raw → 24 clean. Dữ liệu được deduplicate theo `paper_id` và sắp xếp tài liệu mới trước.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 |
| `question_type` hiện có | `summary`, `authors`, `date` |
| Ground truth document | `ground_truth_doc_ids` đối chiếu `paper_id` clean/index |
| Test set | `data/eval/test_set.json` |
| Embedding | `all-MiniLM-L6-v2` |
| Vector store | ChromaDB; ba collection tách biệt |
| Retrieval | `top_k=4` |
| Answer model | Gemini 2.5 Flash theo cấu hình mặc định của lần chạy |
| Metrics | Retrieval hit rate, token F1, judge accuracy, mean judge score |
| Ragas | Chưa chạy; chỉ bật khi `RUN_RAGAS=1` |

Test set được khóa và dùng lại nguyên vẹn cho cả ba trạng thái. Nếu tái sinh test set giữa các lần chạy, câu hỏi hoặc document ID có thể thay đổi và delta không còn đo riêng tác động của corruption/repair.

## 7. Baseline artifacts và kết quả

| Artifact | Đường dẫn | Trạng thái |
| --- | --- | --- |
| Raw response/records | `data/raw/` | Có |
| Clean CSV/JSON | `data/clean/papers_clean.*` | Có, 24 dòng |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Có |
| Frozen evaluation set | `data/eval/test_set.json` | Có, 10 câu |
| Baseline answers/metrics | `data/results/baseline_*.json` | Có |
| Quality/freshness | `data/quality/baseline_quality.json`, `freshness_report.json` | Có |
| Baseline report | `data/reports/phase1_report.md` | Có |

| Metric | Baseline | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 0,90 | 9/10 câu có ground-truth document trong top-k |
| `mean_token_f1` | 0,1930 | Mức trùng token trung bình còn thấp do câu trả lời sinh dài hơn ground truth |
| `judge_accuracy` | 0,60 | 6/10 câu được judge đánh giá đúng |
| `mean_judge_score` | 3,40/5 | Chất lượng trung bình ở mức khá nhưng chưa ổn định |
| Ragas | N/A | Bị skip vì chưa bật `RUN_RAGAS=1` |

## 8. Data quality và freshness

Baseline pass **12/12** checks:

1. Đủ required columns và có ít nhất 3 dòng.
2. `paper_id` không rỗng, không trùng.
3. `title`, `summary`, `text_for_embedding` không rỗng.
4. Summary dài tối thiểu 50 ký tự và `summary_chars` nhất quán.
5. `published` parse được; `age_days` hợp lệ và không vượt 180 ngày.

| Trạng thái | Tổng dòng | Quality | Freshness | Latest | Oldest | Stale rows |
| --- | ---: | --- | --- | --- | --- | ---: |
| Baseline | 24 | 12 pass, 0 fail | fresh | 2026-08-01 | 2026-02-12 | 0 |
| Corrupted | 26 | 8 pass, 4 fail | stale | 2026-07-13 | 2000-01-01 | 2 |
| Repaired | 24 | 12 pass, 0 fail | fresh | 2026-08-01 | 2026-02-12 | 0 |

## 9. Corruption scenarios và repair

| Scenario | Tác động | Số record/event | Signal quan sát | Repair |
| --- | --- | ---: | --- | --- |
| `blank_summary` | Xóa summary và rút ngắn embedding text | 2 | `summary_not_blank` và `summary_minimum_length` fail | Re-clean từ raw summary |
| `stale_date` | Đặt `published=2000-01-01`, `age_days=9714` | 2 | Freshness stale; 2 stale rows | Re-parse ngày từ raw |
| `add_noise` | Chèn noise làm embedding text tăng lên hơn 6.300 ký tự | 2 | Retrieval/answer metric có thể suy giảm dù basic null checks vẫn pass | Rebuild embedding text từ raw clean fields |
| `duplicates` | Sao chép hai document | 2 | Rows 24 → 26; `paper_id_unique` fail với 2 duplicate values | Dedupe khi re-clean raw |

Corruption log tại `data/results/corruption_log.json` ghi schema version, reference time, source/corrupted row count, frozen target IDs và before/after cho từng thay đổi. Repair đọc lại `data/raw/crossref_records.json` rồi chạy cùng cleaning contract; vì vậy nó phục hồi từ nguồn đáng tin cậy thay vì che lỗi trong corrupted JSON.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Corruption delta | Kết quả phục hồi |
| --- | ---: | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 0,90 | 0,70 | 0,90 | -0,20 | Phục hồi hoàn toàn |
| `mean_token_f1` | 0,1930 | 0,1717 | 0,1981 | -0,0213 | Phục hồi và cao hơn baseline 0,0050 |
| `judge_accuracy` | 0,60 | 0,50 | 0,60 | -0,10 | Phục hồi hoàn toàn |
| `mean_judge_score` | 3,40 | 3,00 | 3,50 | -0,40 | Phục hồi và cao hơn baseline 0,10 |
| Quality pass/fail | 12/0 | 8/4 | 12/0 | 4 checks chuyển fail | Phục hồi hoàn toàn |
| Freshness | fresh | stale | fresh | 2 stale rows | Phục hồi hoàn toàn |

Kết luận nhân quả có bằng chứng:

1. Xóa summary, thêm noise, duplicate và stale date → 4 quality checks fail, freshness chuyển `fresh` thành `stale` → retrieval hit giảm 20 điểm phần trăm, judge accuracy giảm 10 điểm phần trăm.
2. Re-clean từ raw snapshot và rebuild index → row count/quality/freshness trở lại baseline → retrieval hit và judge accuracy phục hồi hoàn toàn.
3. Token F1 và judge score repaired cao hơn nhẹ baseline. Không nên kết luận repair “cải thiện mô hình” vì LLM judge/generation có tính biến động; cần chạy lặp nhiều seed hoặc cố định đầu ra để kiểm chứng.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Nếu mỗi role tự sinh lại test set hoặc dùng cùng một Chroma collection, so sánh baseline/corrupted/repaired sẽ bị sai lineage.
- **Nguyên nhân:** Các module phụ thuộc trực tiếp vào `paper_id`, clean schema, frozen test set và collection name.
- **Cách xử lý:** CP0 khóa contract; pipeline dùng raw snapshot/test set cố định và ba artifact/collection riêng; corruption flow kiểm tra Phase 1 artifacts trước khi chạy.
- **Cách xác minh:** 10 `ground_truth_doc_ids` tồn tại trong clean/index; answers của ba trạng thái dùng cùng question IDs; comparison report khớp ba metrics JSON.

Vấn đề môi trường khi kiểm thử báo cáo: pytest mặc định không truy cập được temp directory của tài khoản Windows. Chỉ định `--basetemp` trong workspace giúp bộ test chạy thành công 11/11.

## 12. Giới hạn và hướng cải thiện

| Giới hạn | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Test set chỉ 10 câu, không có `categories` | Coverage nhỏ, metric dễ dao động | Bổ sung clean records có categories; tạo test set cân bằng theo question type và giữ version/hash |
| Ragas bị skip | Thiếu faithfulness/context precision/recall | Chạy `RUN_RAGAS=1`, lưu đầy đủ version model và output |
| Một số report JSON/Markdown ghi absolute macOS path | Khó tái hiện trên Windows/Linux khác | Report đường dẫn tương đối theo project root và thêm test portability |
| LLM generation/judge không hoàn toàn deterministic | Token F1/judge score có thể thay đổi nhẹ | Cố định temperature/seed nếu provider hỗ trợ, chạy lặp và báo confidence interval |
| Dữ liệu chỉ 24 papers, một số nội dung đa ngôn ngữ | Chưa đại diện corpus thực tế | Mở rộng corpus theo snapshot versioned; thêm kiểm tra encoding/language |
| Chưa có test end-to-end offline toàn pipeline | Regression tích hợp có thể phụ thuộc API/model | Mock Crossref/LLM và thêm integration test dùng fixture snapshot |

## 13. Checklist trước khi nộp

- [x] Phân công 5 role khớp `CP0_HANDOFF.md` và module thực tế.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp các JSON trong `data/results/`.
- [x] Kết luận quality/freshness khớp các JSON trong `data/quality/`.
- [x] Corruption và repair có log, lineage và artifact riêng.
- [x] Bộ test hiện tại chạy thành công 11/11 trong môi trường kiểm tra.
- [x] Không đưa API key hoặc nội dung `.env` vào báo cáo.
- [ ] Bổ sung MSSV và họ tên đầy đủ còn thiếu.
- [ ] Chạy lại hai entrypoint trên máy nộp bài có `uv` và credential hợp lệ.
- [ ] Thay absolute path trong các generated report bằng đường dẫn tương đối.
- [ ] Mỗi thành viên hoàn thành báo cáo cá nhân theo role.
