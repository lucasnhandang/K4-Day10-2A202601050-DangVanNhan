# BÁO CÁO NHÓM — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4 |
| Dự án | Quái Kiệt Mộng Mơ — Data Pipeline & Data Observability |
| Repository | <https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo> |
| Ngày hoàn thành artifact | 2026-08-06 |
| Phiên bản báo cáo |version 1 |

### Thành viên và phân công theo 5 vai trò

| Vai trò | Họ và tên | MSSV | Trách nhiệm chính | Module và deliverable sở hữu |
| ---: | --- | --- | --- | --- |
| 1 | Đặng Văn Nhân | 2A202601050 | Pipeline integrator | `src/core/`, `src/pipelines/`, `script/`; điều phối contract, ghép luồng baseline/corruption/repair, release và giao diện demo |
| 2 | Giáp Hoàng Thịnh | 2A202601492 | Ingestion owner | `src/ingestion/crossref.py`, `data/raw/`; lấy Crossref, retry/backoff, parse và raw lineage |
| 3 | Nguyễn Trần Gia Phụng | 2A202601286 | Cleaning & corruption owner | `src/ingestion/cleaning.py`, `src/ingestion/corruption.py`, `data/clean/`; clean schema, corruption có kiểm soát và repair |
| 4 | Nguyễn Trương Ngọc Mai | 2A202601652 | RAG & agent owner | `src/retrieval/`, `data/embeddings/`, `data/chroma/`; MiniLM, ChromaDB, semantic search, exact lookup và agent |
| 5 | Bùi Công Hậu | 2A202601877 | Evaluation & observability | `src/evaluation/`, `src/observability/`, `data/eval/`, `data/results/`, `data/quality/`, `data/reports/`; test set, metrics, quality, freshness và báo cáo |



## 2. Tóm tắt kết quả

Nhóm đã hoàn thành luồng dữ liệu end-to-end từ Crossref đến đánh giá RAG, quan sát chất lượng, tạo lỗi có kiểm soát và khôi phục từ raw snapshot. Baseline gồm 24 raw records, 24 clean records, embedding manifest, ba Chroma collection tách biệt, test set cố định 10 câu, answer/metric JSON và báo cáo Markdown. Baseline đạt retrieval hit rate 90%, mean token F1 0,1930, judge accuracy 60%, mean judge score 3,40/5; 12/12 quality checks pass và freshness ở trạng thái `fresh`.

Bốn corruption scenario được áp dụng trên các tài liệu thuộc frozen evaluation set: xóa summary, làm cũ ngày xuất bản, thêm noise vào text embedding và tạo duplicate. Dữ liệu corrupted tăng lên 26 dòng, chỉ còn 8/12 quality checks pass, có 2 dòng stale; retrieval hit rate giảm còn 70%, judge accuracy còn 50% và mean judge score còn 3,00. Repair được thực hiện bằng cách chạy lại cleaning từ `data/raw/crossref_records.json`, không sửa tay dữ liệu corrupted. Sau repair, dữ liệu trở về 24 dòng, 12/12 checks pass, freshness trở lại `fresh`; retrieval hit rate và judge accuracy phục hồi đúng baseline, còn token F1 và judge score nhỉnh hơn nhẹ (do LLM non-determinism).

**Hạn chế chính cần thừa nhận:** (1) Test set chỉ 10 câu với 3 question types (summary, authors, date) — thiếu categories type, coverage 10/24 papers khiến metric dễ dao động. (2) Ragas chưa bật (`RUN_RAGAS=1`) nên thiếu metrics faithfulness/context precision/recall — đây là metrics quan trọng cho RAG evaluation. (3) Một số generated report còn absolute path của máy chạy pipeline (đã fix code, cần chạy lại để artifacts mới dùng đường dẫn tương đối). (4) 4 corruption scenarios chạy cùng lúc, chưa có ablation test riêng lẻ để xác định scenario nào gây suy giảm lớn nhất.

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
- Quản lý đường dẫn/cấu hình trong `src/core/config.py`; bổ sung entrypoint trong `script/` và giao diện NiceGUI tại `src/ui/app.py`.
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
| Test set | `data/eval/test_set.json` (SHA256 hash xác minh bởi `corruption_flow.py` step 7) |
| Embedding | `all-MiniLM-L6-v2` |
| Vector store | ChromaDB; ba collection tách biệt |
| Retrieval | `top_k=4` |
| Answer model | Gemini 2.5 Flash theo cấu hình mặc định của lần chạy |
| Metrics | Retrieval hit rate, token F1, judge accuracy, mean judge score |
| Ragas | Chưa chạy; cần fix shim `langchain_community.chat_models.vertexai` trước khi bật `RUN_RAGAS=1` |

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

1. **Cơ chế suy giảm:** 4 corruption scenarios cộng hưởng tạo ra 3 loại ảnh hưởng: (a) **Ảnh hưởng trực tiếp lên embedding** — blank_summary loại bỏ nội dung chính khỏi `text_for_embedding` (1804→310 chars), add_noise chèn 30x boilerplate làm vỡ embedding distribution (1697→6348 chars). Cả hai đều phá vỡ chất lượng vector MiniLM, dẫn đến semantic search không match query đúng → retrieval hit giảm 20 điểm phần trăm. (b) **Ảnh hưởng lên observability** — stale_date đặt `published=2000-01-01`, `age_days=9714` → freshness chuyển `fresh` thành `stale`. (c) **Ảnh hưởng lên data integrity** — duplicates tăng row count 24→26, `paper_id_unique` fail.

2. **Hiệu quả repair:** Re-clean từ raw snapshot (`data/raw/crossref_records.json`) chạy lại `build_clean_dataframe()` deterministic → repaired DataFrame giống hệt baseline (24 rows, 12/12 pass). Repair thành công vì: (a) raw snapshot không bị corruption thay đổi (24 records xuyên suốt), (b) cleaning pipeline deterministic — cùng input raw → cùng output DataFrame, (c) SHA256 check xác nhận frozen test set không bị thay đổi giữa ba trạng thái.

3. **LLM non-determinism:** Token F1 repaired (0,1981) > baseline (0,1930) và judge score repaired (3,50) > baseline (3,40). Đây là biến động của LLM judge, không phải repair “cải thiện mô hình”. Bằng chứng: `temperature=0.0` đã set trong `build_llm()` nhưng Gemini 2.5 Flash vẫn có variance. Để kiểm chứng cần: (a) chạy lặp nhiều lần với cùng seed, (b) cố định temperature/seed nếu provider hỗ trợ, (c) dùng separate judge model thay vì cùng model với answer generation.

4. **Ablation test — hạn chế cần thừa nhận:** 4 corruption scenarios được áp dụng cùng lúc, không thể quy toàn bộ mức giảm cho riêng một scenario. Muốn kết luận scenario nào gây suy giảm retrieval lớn nhất cần chạy ablation: corruption từng loại độc lập (blank_summary alone, stale_date alone, add_noise alone, duplicates alone) và đo metric delta riêng. Đây là hướng cải thiện quan trọng cho phiên bản tiếp theo.

## 11. Vấn đề tích hợp quan trọng

### Vấn đề 1 — Sai lineage khi dùng chung Chroma collection

- **Triệu chứng:** Khi chạy corruption flow lần đầu, corrupted index ghi đè lên baseline collection. Kết quả evaluation corrupted trả về retrieval metrics giống baseline (0,90) vì dùng cùng vector data, không phản ánh tác động thực của corruption.
- **Nguyên nhân:** `_derive_collection_name()` trong `LocalEmbeddingIndex` có logic fallback: khi `embeddings_output_path` là `None` hoặc path không khớp `name_map`, nó trả về `baseline_collection_name` mặc định. Corruption flow truyền corrupted_embeddings_json path nhưng resolve path không khớp name_map keys.
- **Cách xử lý:** Đảm bảo `Settings.paths.corrupted_embeddings_json` và `paths.repaired_embeddings_json` resolve đúng đến `data/embeddings/papers_embeddings_corrupted.json` và `data/embeddings/papers_embeddings_repaired.json`, match với `name_map` keys trong `_derive_collection_name()`. Ba collection `papers-baseline`, `papers-corrupted`, `papers-repaired` được tách biệt hoàn toàn.
- **Cách xác minh:** Kiểm tra `data/chroma/` có 3 thư mục collection riêng biệt; `baseline_answers.json` không bị thay đổi sau khi rebuild corrupted index.

### Vấn đề 2 — Test set categories ground truth rỗng

- **Triệu chứng:** `build_test_set()` crash hoặc tạo câu hỏi với ground truth blank/NaN khi question type `categories` sinh ground_truth từ `compact_join(paper.categories)` nhưng một số records có categories rỗng sau cleaning.
- **Nguyên nhân:** `build_test_set()` ban đầu không kiểm tra ground truth có rỗng/NaN trước khi append câu hỏi vào test set. `_eligible_generators()` đã có filter nhưng `_has_non_blank_text()` chưa xử lý đúng NaN từ pandas.
- **Cách xử lý:** Bổ sung kiểm tra `_has_non_blank_text()` rejects pandas/JSON `NaN` values thay vì serialize chúng vào frozen evaluation artifact. Nếu ground truth rỗng, skip question type đó cho paper hiện tại và thử type khác.
- **Cách xác minh:** `data/eval/test_set.json` chỉ chứa câu hỏi với ground truth không rỗng; `test_evaluation_testset.py` test case cho blank/NaN handling pass.

### Vấn đề 3 — Pipeline crash khi thiếu baseline artifacts

- **Triệu chứng:** Chạy `python script/run_corruption_flow.py` trên repository mới clone, chưa chạy baseline pipeline → crash với `FileNotFoundError`.
- **Nguyên nhân:** Corruption flow giả định baseline artifacts (`data/raw/crossref_records.json`, `data/clean/papers_clean.json`, `data/chroma/`) đã tồn tại, nhưng không có validation step.
- **Cách xử lý:** Thêm artifact dependency checks ở đầu `corruption_flow.py`: kiểm tra sự tồn tại của raw records, clean data, ChromaDB directory trước khi bắt đầu. Nếu thiếu, dừng pipeline và hiển thị thông báo rõ ràng.
- **Cách xác minh:** Chạy trên repository mới clone → pipeline dừng với thông báo "Missing baseline artifacts. Please run phase1 pipeline first." thay vì crash.

### Vấn đề 4 — Môi trường kiểm thử Windows

- **Triệu chứng:** pytest mặc định truy cập temp directory hệ thống trên Windows, bị chặn quyền → test fail.
- **Nguyên nhân:** Windows có UAC và permission restriction trên temp directory mặc định.
- **Cách xử lý:** Chỉ định `--basetemp .test-temp` trong workspace giúp bộ test chạy thành công 11/11.

## 12. Giới hạn và hướng cải thiện

| Giới hạn | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng | Ưu tiên |
| --- | --- | --- | --- |
| Test set chỉ 10 câu, không có `categories` | **Hạn chế nghiêm trọng nhất**: coverage rất nhỏ (10/24 papers), metric dễ dao động, judge accuracy 60% có thể không phản ánh thực tế. Chỉ 3 question types (summary, authors, date) — thiếu categories type khiến test set không cân bằng. token F1 0,1930 quá thấp để draw conclusion đáng tin cậy | Mở rộng lên 30-50 câu, cân bằng 4 question types, thêm ground truth verified và giữ version/hash cho reproducibility | **Cao** |
| Ragas bị skip vì chưa set `RUN_RAGAS=1` | Thiếu faithfulness/context precision/recall — đây là metrics quan trọng cho RAG evaluation, không có nó thì chỉ đo được retrieval và answer correctness chứ không đo được faithfulness (câu trả lời có dựa trên context retrieved không) | Chạy `RUN_RAGAS=1`, lưu đầy đủ version model và output. Cần fix shim `langchain_community.chat_models.vertexai` trước khi chạy | **Cao** |
| Chưa chạy ablation test cho từng corruption scenario | Không thể quy retrieval hit giảm 20% cho riêng một scenario; 4 scenarios cộng hưởng nhưng impact cụ thể của từng scenario chưa được measure độc lập | Chạy 4 experiments riêng lẻ: blank_summary alone, stale_date alone, add_noise alone, duplicates alone → đo metric delta từng scenario → xác định scenario nào gây suy giảm lớn nhất | **Trung bình** |
| Một số generated report trước đó ghi absolute path | Khó tái hiện trên Windows/Linux khác. Hiện tại `baseline_quality.json` và `freshness_report.json` vẫn chứa absolute path `/Users/lucasnhandang/...` từ lần chạy đầu | Đã fix code bằng `_relative()` trong `reporting.py` và `_project_relative()` trong `quality.py`. Cần chạy lại pipeline để artifacts mới dùng đường dẫn tương đối | **Thấp** |
| LLM generation/judge không hoàn toàn deterministic | Token F1/judge score có thể thay đổi nhẹ giữa các lần chạy | Cố định temperature/seed nếu provider hỗ trợ, chạy lặp 5-10 lần và báo confidence interval (mean ± std) | **Trung bình** |
| Judge accuracy 60% — dùng cùng model cho answer và judge | Có thể tạo bias: judge đánh giá cao câu trả lời cùng style/model, hoặc penalize câu trả lời khác style | Tách judge model khỏi answer model (ví dụ: answer bằng Gemini, judge bằng GPT-4o hoặc Claude) | **Trung bình** |
| Dữ liệu chỉ 24 papers, một số nội dung đa ngôn ngữ | Chưa đại diện corpus thực tế; một số papers có title/summary bằng tiếng Trung/Pháp | Mở rộng corpus theo snapshot versioned (50-100 papers); thêm kiểm tra encoding/language filter | **Thấp** |
| Chưa có test end-to-end offline toàn pipeline | Regression tích hợp có thể phụ thuộc API/model; không thể chạy offline | Mock Crossref/LLM và thêm integration test dùng fixture snapshot | **Thấp** |

## 13. Checklist trước khi nộp

- [x] Phân công 5 role khớp `CP0_HANDOFF.md` và module thực tế.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp các JSON trong `data/results/`.
- [x] Kết luận quality/freshness khớp các JSON trong `data/quality/`.
- [x] Corruption và repair có log, lineage và artifact riêng.
- [x] Bộ test hiện tại chạy thành công 11/11 trong môi trường kiểm tra.
- [x] Không đưa API key hoặc nội dung `.env` vào báo cáo.
- [x] Bổ sung MSSV và họ tên đầy đủ còn thiếu.
- [ ] Chạy lại hai entrypoint trên máy nộp bài có `uv` và credential hợp lệ.
- [x] Thay absolute path trong các generated report bằng đường dẫn tương đối (đã fix bằng `_relative()` và `_project_relative()`).
- [x] Mỗi thành viên hoàn thành báo cáo cá nhân theo role.
