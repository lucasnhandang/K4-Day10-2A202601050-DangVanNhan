# Role 5 — CP0 Evaluation & Observability Contract

## 1. Mục tiêu CP0

Tài liệu này khóa contract đầu vào/đầu ra cuối cùng cho vai trò **Evaluation & Observability** của thành viên 5 theo cấu hình Nhóm 5 trong file phân công HTML.

CP0 chỉ thiết kế contract, tiêu chí kiểm tra, artifact checklist và kế hoạch test. Không tạo test set hoặc metrics giả trong `data/`.

## 2. Phạm vi sở hữu

### File phụ trách chính

```text
src/evaluation/testset.py
src/evaluation/metrics.py
src/observability/quality.py
src/observability/reporting.py
```

### Hàm cần hoàn thiện ở các checkpoint sau

```text
build_test_set()
run_data_quality_checks()
build_freshness_report()
generate_phase1_report()
generate_corruption_report()
```

### Phần cần audit

- `evaluate_pipeline()` và các metrics được sinh ra.
- LLM judge thật so với heuristic fallback.
- Ragas enabled/skipped/error status.
- Tính nhất quán giữa JSON, CSV và Markdown reports.

## 3. Clean-data input contract

Evaluation và observability nhận một `pandas.DataFrame` với các cột sau:

| Cột | Kiểu mong đợi | Bắt buộc | Mục đích |
|---|---|---:|---|
| `paper_id` | `str` | Có | Document identity và ground-truth ID |
| `title` | `str` | Có | Tạo câu hỏi và exact lookup |
| `summary` | `str` | Có | Ground truth cho câu hỏi summary |
| `authors_joined` | `str` | Có | Ground truth cho câu hỏi authors |
| `categories_joined` | `str` | Có | Ground truth cho câu hỏi categories |
| `published` | ISO datetime string | Có | Ground truth cho câu hỏi date và freshness |
| `age_days` | `float` hoặc `NaN` | Có | Freshness signal |
| `summary_chars` | `int` | Có | Summary-length quality signal |
| `text_for_embedding` | `str` | Có | Xác minh document có thể được index |
| `abs_url` | `str` | Có với `LocalEmbeddingIndex` | Metadata lookup/index |
| `pdf_url` | `str` | Có với `LocalEmbeddingIndex` | Metadata lookup/index |

### Invariants

- `paper_id` không null, không rỗng và unique trong clean baseline.
- `title`, `summary` và `text_for_embedding` không rỗng trong clean baseline.
- `published` parse được về ngày; cleaning hiện xuất dạng `YYYY-MM-DDT00:00:00` khi input chỉ có ngày.
- `age_days` là số thực và `age_days >= 0` trong baseline; giá trị `NaN` phải làm freshness/quality fail thay vì được coi là fresh.
- `summary_chars == len(summary)` sau khi summary đã được chuẩn hóa.
- Chroma metadata phải giữ nguyên `paper_id` từ clean dataframe.
- Cleaning owner không đổi `paper_id` giữa clean, corrupted và repaired data, ngoại trừ record bị corruption xóa khỏi dataset.

### Quyết định contract đã khóa

- Clean dataframe bắt buộc sử dụng đúng tên và kiểu cột trong bảng trên; không hỗ trợ alias cột ở evaluation/observability layer.
- Chroma metadata bắt buộc chứa `paper_id` giống hệt clean dataframe. `LocalEmbeddingIndex` hiện đã thỏa contract này trong `_build_documents()`.
- Test set không được rebuild giữa baseline, corrupted và repaired; pipeline chỉ tạo lại khi người chạy chủ động bật `REFRESH_TEST_SET=true` trước baseline.
- Nếu upstream output vi phạm contract, pipeline phải fail rõ ràng tại boundary thay vì tự đoán, tự đổi ID hoặc âm thầm bỏ field.
- Canonical `paper_id` là DOI đã slug hóa bằng `_doi_to_paper_id()` trong `crossref.py`, ví dụ `10.1145/3442188.3445922` thành `10-1145-3442188-3445922`. Raw, clean, Chroma metadata và `ground_truth_doc_ids` phải dùng cùng slug này.

## 4. Evaluation-set contract

### Sample schema

```json
{
  "id": "summary-001",
  "question_type": "summary",
  "question": "What is the paper 'Example title' about?",
  "ground_truth": "Example summary.",
  "ground_truth_doc_ids": ["10-0000-fixture-001"]
}
```

### Trường bắt buộc

| Trường | Kiểu | Quy tắc |
|---|---|---|
| `id` | `str` | Unique và deterministic |
| `question_type` | `str` | Một trong bốn loại đã khóa |
| `question` | `str` | Không rỗng, tạo từ clean data |
| `ground_truth` | `str` | Không rỗng, lấy trực tiếp từ clean row |
| `ground_truth_doc_ids` | `list[str]` | Chứa `paper_id` có thật trong baseline index |

### Question types và templates

| Type | Template | Ground truth column |
|---|---|---|
| `summary` | `Summarize the paper: '{title}'` | `summary` |
| `authors` | `Who are the authors of '{title}'?` | `authors_joined` |
| `date` | `When was '{title}' published?` | `published` |
| `categories` | `What are the main categories of '{title}'?` | `categories_joined` |

### Generation rules

- Input phải có tối thiểu 3 paper hợp lệ, khớp `MIN_DOCUMENTS=3` trong code đã pull.
- Chọn tối đa 10 paper với `RANDOM_SEED=42`, khớp `SAMPLE_SIZE=10` trong code đã pull.
- Mỗi paper được chọn sinh một question; bốn question types được phân phối luân phiên.
- Chỉ tạo question type khi ground truth tương ứng không rỗng.
- Không dùng raw record chưa cleaning.
- Không tự bịa document ID.
- Không duplicate `id` hoặc duplicate cùng một câu hỏi.
- Tiêu đề phải đặt trong dấu nháy đơn để `answer_question()` có thể sử dụng exact-title lookup trước khi kết hợp semantic results.
- Ghi test set vào `data/eval/test_set.json` bằng `write_json()`.
- Test set chỉ được refresh khi `REFRESH_TEST_SET=true`; mặc định tái sử dụng cho cả ba trạng thái.

## 5. Evaluation-output contract

### Answer artifact

Mỗi answer record phải giữ tối thiểu:

```json
{
  "id": "summary-001",
  "question_type": "summary",
  "question": "...",
  "ground_truth": "...",
  "ground_truth_doc_ids": ["10-0000-fixture-001"],
  "answer": "...",
  "retrieved_doc_ids": ["10-0000-fixture-001"],
  "retrieved_contexts": ["..."],
  "retrieval_hit": true,
  "token_f1": 1.0,
  "judge": {
    "score": 5,
    "correct": true,
    "reasoning": "..."
  }
}
```

### Metrics artifact

```json
{
  "samples": 16,
  "retrieval_hit_rate": 1.0,
  "mean_token_f1": 1.0,
  "judge_accuracy": 1.0,
  "mean_judge_score": 5.0,
  "judge_fallback_count": 0,
  "ragas": {
    "skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."
  }
}
```

`judge_fallback_count` là field bổ sung bắt buộc để report không che giấu việc evaluator đã dùng heuristic thay cho LLM judge.

### Metric definitions

| Metric | Cách hiểu |
|---|---|
| `retrieval_hit_rate` | Tỷ lệ samples có ít nhất một retrieved ID thuộc ground-truth IDs |
| `mean_token_f1` | Trung bình token F1 giữa answer và ground truth |
| `judge_accuracy` | Tỷ lệ judge verdict có `correct=true` |
| `mean_judge_score` | Điểm judge trung bình trên thang 1–5 |
| `judge_fallback_count` | Số samples dùng heuristic fallback |
| `ragas` | Kết quả, skipped reason hoặc error reason |

### Guardrails cần có

- Từ chối test set rỗng trước khi gọi `mean()`.
- Không coi heuristic fallback là LLM judge chạy thành công.
- Không coi Ragas error là Ragas metrics hợp lệ.
- Giữ cùng test set, embedding model và `top_k` khi so sánh ba trạng thái.

## 6. Data-quality contract

### Quality-report schema

```json
{
  "report_name": "baseline_quality",
  "success": true,
  "total_rows": 24,
  "passed_checks": 10,
  "failed_checks": 0,
  "checks": [
    {
      "name": "paper_id_unique",
      "success": true,
      "observed_value": 24,
      "expected": "all values are unique",
      "message": ""
    }
  ]
}
```

### Quality checks

| Check | Baseline expectation | Corruption được phát hiện |
|---|---|---|
| Dataframe không rỗng | `total_rows > 0` | Missing/all rows removed |
| Minimum row count | Đạt ngưỡng nhóm thống nhất | Dropped records |
| `paper_id` not null | 100% | Missing identity |
| `paper_id` unique | 100% | Duplicate rows |
| Title not blank | 100% | Blank/truncated title |
| Summary not blank | 100% | Blank summary |
| Summary minimum length | Đạt ngưỡng | Truncated/invalid summary |
| `summary_chars` consistent | Bằng độ dài summary | Helper field không được rebuild |
| `text_for_embedding` not blank | 100% | Invalid embedding input |
| Published parseable | 100% | Invalid dates |
| `age_days` valid | Numeric, non-null | Invalid/stale manipulation |
| Full-row duplicate | Không có | Duplicate injection |

Great Expectations có thể lưu detailed validation artifact trong `data/quality/gx/`; hàm vẫn phải trả một summary dict ổn định để pipeline và reports sử dụng.

## 7. Freshness contract

### Schema

```json
{
  "latest_published": "2026-07-01",
  "oldest_published": "2026-02-01",
  "stale_rows": 0,
  "total_rows": 24,
  "threshold_days": 180,
  "is_fresh": true
}
```

### Rules

- `stale_rows` là số dòng có `age_days > settings.freshness_threshold_days`.
- `is_fresh=true` khi dataframe không rỗng, dates hợp lệ và `stale_rows == 0`.
- Nếu dataframe rỗng hoặc không có ngày parse được, report phải trả trạng thái không fresh/unknown rõ ràng, không tự động pass.
- Latest/oldest dates được lấy từ dữ liệu, không hard-code theo ngày chạy.

## 8. Artifact checklist

### Baseline

```text
data/eval/test_set.json
data/results/baseline_metrics.json
data/results/baseline_answers.json
data/quality/baseline_quality.json
data/quality/freshness_report.json
data/reports/phase1_report.md
```

### Corrupted

```text
data/results/corruption_log.json
data/results/corrupted_metrics.json
data/results/corrupted_answers.json
data/quality/corrupted_quality.json
data/quality/corrupted_freshness.json
```

### Repaired và comparison

```text
data/results/repaired_metrics.json
data/results/repaired_answers.json
data/quality/repaired_quality.json
data/quality/repaired_freshness.json
data/reports/corruption_report.md
```

### Quyết định đường dẫn freshness

- Baseline giữ nguyên path đã có trong `Settings`: `data/quality/freshness_report.json`.
- Corrupted dùng `data/quality/corrupted_freshness.json`.
- Repaired dùng `data/quality/repaired_freshness.json`.
- Pipeline integrator tạo hai path sau từ `settings.paths.quality_dir`; không thay đổi chữ ký `build_freshness_report()`.
- Ba freshness reports không được ghi đè lẫn nhau.

## 9. Report outlines

### Phase 1 report

1. Source summary: API, query, filter, max results.
2. Raw/clean counts và chênh lệch.
3. Evaluation setup: sample count, question types, model, collection, `top_k`.
4. Metrics table.
5. Judge fallback/Ragas status.
6. Quality-check table.
7. Freshness summary.
8. Một retrieval hit và một miss nếu có.
9. Artifact paths và limitations.

### Corruption comparison report

1. Corruption summary và corruption-log path.
2. Baseline/corrupted/repaired metrics table.
3. Metric deltas và mức recovery.
4. Quality/freshness comparison.
5. Một answer/retrieval case xấu đi.
6. Một repaired case phục hồi hoặc chưa phục hồi.
7. Hai chuỗi corruption → signal → metric và repair → recovery.
8. Judge fallback/Ragas status và limitations.

Report chỉ được tạo từ payload/artifact thật; không hard-code số liệu hoặc kết luận.

## 10. Kế hoạch xác minh theo yêu cầu đề bài

Không lưu fixture giả trong repository. Toàn bộ artifact dùng để đánh giá và báo cáo phải được sinh từ raw snapshot Crossref và clean dataframe thật.

| Kiểm tra | Input thật | Kết quả mong đợi |
|---|---|---|
| Test-set schema | `data/clean/papers_clean.json` | Mỗi sample có đủ 5 fields |
| Test-set determinism | Chạy hai lần trên cùng clean snapshot và seed | Payload không đổi |
| Valid ground-truth IDs | Clean dataframe + Chroma manifest | Mọi ID tồn tại trong index |
| Empty ground truth | Các row thiếu authors/categories/date | Không tạo sample không thể chấm |
| Baseline quality | Clean baseline | Core checks pass hoặc fail có observed value thật |
| Corruption detection | Corrupted clean artifact + corruption log | Blank/duplicate/stale signals khớp log |
| Freshness | `published` và `age_days` thật | Latest/oldest/stale count chính xác |
| Phase-1 report | Baseline metrics/quality/freshness JSON | Markdown khớp artifact |
| Comparison report | Ba bộ metrics và quality/freshness | Bảng có đủ ba trạng thái và delta |
| Retrieval evidence | Baseline/corrupted/repaired answers | Có thể giải thích ít nhất một hit/miss thật |
| Judge fallback audit | Answers/metrics thật | Fallback được đếm và ghi rõ |

Nếu sau này bổ sung pytest để lấy bonus, test có thể tạo DataFrame tạm trong bộ nhớ. Không cần và không dùng một JSON fixture được commit làm artifact nộp bài.

## 11. Kết quả audit source sau khi pull

### Phiên bản đã audit

- Branch: `main`.
- HEAD: `33ba63c` — merge cleaning/data-modeling implementation.
- Raw snapshot đã có trong `data/raw/`; chưa có clean, eval, metrics, quality hoặc report artifacts.

### Raw-snapshot profile

| Signal | Giá trị |
|---|---:|
| Total records | 24 |
| Unique `paper_id` | 24 |
| Blank title | 0 |
| Blank summary | 0 |
| Blank authors | 0 |
| Blank categories | 24 |
| Blank published | 0 |

Kết luận: summary/authors/date questions có dữ liệu đầu vào, nhưng categories questions hiện không có ground truth hợp lệ từ raw snapshot này.

### Compatibility findings

| Mức độ | Phát hiện | Quyết định/hành động |
|---|---|---|
| Blocker upstream | `cleaning.py` đọc `rec.doi` và `rec.source`, nhưng `PaperRecord` hiện không khai báo hai attributes này | Cleaning owner/integrator phải sửa contract trước khi tạo clean artifact; role 5 không tự che lỗi bằng fixture |
| Contract conflict | `CP0_HANDOFF.md` mô tả `paper_id` là DOI `strip().lower()`, trong khi `crossref.py` thực tế slug hóa DOI | Khóa implementation hiện chạy (`_doi_to_paper_id`) làm canonical identity; handoff doc cần được integrator đồng bộ |
| Evaluation risk | 24/24 raw records không có categories | CP2 phải skip categories sample có ground truth rỗng; không ghi câu hỏi rỗng vào test set |
| Evaluation risk | `testset.py` hiện chưa validate required columns và chưa skip empty ground truth | Ghi vào CP2 acceptance list; CP0 không sửa code chức năng |
| Retrieval mismatch | Question templates hiện không đặt title trong nháy đơn, trong khi `answer_question()` chỉ exact-lookup title nằm trong nháy đơn | CP2 cập nhật templates theo contract đã khóa |
| Metric risk | `evaluate_pipeline()` gọi `mean()` mà chưa guard test set rỗng | CP2 thêm fail-fast validation trước evaluation |
| Observability gap | `quality.py` và `reporting.py` vẫn còn `NotImplementedError` | Đây là phần triển khai CP1–CP3 của role 5 |
| Passed | `VectorStore` và `LocalEmbeddingIndex` đều giữ `paper_id` trong metadata | Ground-truth lineage contract khả thi, không cần chờ RAG owner sửa ở CP0 |

### Ownership đã xác nhận

Theo `CP0_HANDOFF.md`, **Hậu** sở hữu Evaluation & Observability và làm việc trên nhánh `hau`. Phạm vi trong tài liệu này khớp với handoff chung: `src/evaluation/`, `src/observability/`, evaluation artifacts, quality/freshness JSON và hai Markdown reports.

## 12. Các việc đã hoàn thành ở CP0

- [x] Đọc `testset.py`, `qa.py`, `metrics.py`, `quality.py`, `reporting.py` và `config.py`.
- [x] Khóa clean-data contract cuối cùng.
- [x] Chốt evaluation sample schema.
- [x] Chốt bốn question types và templates.
- [x] Chốt quality-report schema và checks.
- [x] Chốt freshness-report schema và rules.
- [x] Liệt kê baseline/corrupted/repaired artifacts.
- [x] Phác thảo phase-1 và comparison reports.
- [x] Thiết kế validation matrix dựa trên artifact Crossref thật.
- [x] Xác nhận đề bài không yêu cầu committed fixture; không dùng dữ liệu giả làm evidence.
- [x] Khóa clean schema và quy tắc fail-fast tại upstream boundary.
- [x] Xác minh `LocalEmbeddingIndex` hiện giữ `paper_id` trong Chroma metadata.
- [x] Khóa freshness paths cho baseline, corrupted và repaired.
- [x] Audit code và raw snapshot mới sau khi pull.
- [x] Profile 24 raw records và xác định categories ground truth đang thiếu toàn bộ.
- [x] Ghi nhận upstream cleaning blocker mà không sửa ngoài ownership.
- [x] Khóa slugged DOI làm canonical `paper_id` theo implementation thực tế.
- [x] Lập CP2 acceptance list từ các rủi ro test-set/evaluator hiện tại.

## 13. Điều kiện kết thúc CP0

CP0 của role 5 đã hoàn thành trên code mới pull. Các checkpoint tiếp theo phải tạo evaluation/quality/report artifacts từ dữ liệu Crossref thật. Việc sinh clean/test-set/baseline artifacts hiện đang bị chặn bởi mismatch `PaperRecord` ↔ `cleaning.py`; blocker này thuộc handoff với Cleaning owner/Integrator và đã được ghi rõ, không phải quyết định CP0 còn bỏ ngỏ.

## 14. Version control

- Owner branch: `hau`.
- Tài liệu contract là đầu ra CP0 cục bộ của role 5; không kèm fixture giả.
- Giữ `ROLE5_CP0_CONTRACT.md` ở trạng thái untracked theo yêu cầu hiện tại.
- Không chạy `git add`, không commit và không push tài liệu này.
- Không đưa thay đổi ngoài ownership vào Git.
