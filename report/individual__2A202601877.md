# BÁO CÁO CÁ NHÂN — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Bùi Công Hậu |
| MSSV | 2A202601877 |
| Khóa/Lớp | K4 |
| Tên nhóm | Quái Kiệt Mộng Mơ |
| Vai trò chính | Evaluation & Observability |
| Repository | https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data quality checks | `src/observability/quality.py` — `run_data_quality_checks()` | Clean DataFrame (24 records, schema đầy đủ) | JSON 12 quality gates với pass/fail, observed_value, expected | Hoàn thành |
| Freshness monitoring | `src/observability/quality.py` — `build_freshness_report()` | Clean DataFrame với cột `published` | JSON freshness report (fresh/stale/unknown, latest_date, oldest_date, stale_rows) | Hoàn thành |
| Frozen evaluation test set | `src/evaluation/testset.py` — `build_test_set()` | Clean DataFrame (seed hardcode `RANDOM_SEED=42` trong file) | `data/eval/test_set.json` — 10 câu hỏi với ground_truth_doc_ids | Hoàn thành |
| Evaluation metrics | `src/evaluation/metrics.py` — `evaluate_pipeline()` | Test set, ChromaDB index, LLM agent | `data/results/{baseline,corrupted,repaired}_metrics.json` + `_answers.json` | Hoàn thành |
| Report generators | `src/observability/reporting.py` — `generate_phase1_report()`, `generate_corruption_report()` | Metrics JSON, quality JSON, freshness JSON | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Hoàn thành |
| Unit tests | `tests/test_observability_quality.py`, `tests/test_evaluation_testset.py` | Source modules | 7 test cases pass (6 quality + 1 testset) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Xác nhận contract CP0 | Nhân (Pipeline Integrator) | Đảm bảo frozen test set và quality gates khớp với contract paper_id |
| Kiểm tra schema cleaning | Phụng (Cleaning & Corruption Owner) | Xác nhận validate_clean_dataframe() đủ điều kiện cho quality checks |
| Xác minh corruption scenarios | Phụng (Cleaning & Corruption Owner) | Đảm bảo 4 corruption scenarios ảnh hưởng đúng frozen test-set documents |
| Rebuild index cho corrupted/repaired | Mai (RAG & Agent Owner) | Đảm bảo 3 ChromaDB collections tách biệt cho evaluation chính xác |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Tạo 12 quality gates cho clean data | `src/observability/quality.py` | 12/12 pass baseline, 8/12 corrupted, 12/12 repaired | `python -c "from src.observability.quality import run_data_quality_checks; ..."` |
| Xây dựng freshness report | `src/observability/quality.py` | Freshness fresh→stale→fresh | `data/quality/freshness_report.json` |
| Tạo frozen test set 10 câu | `src/evaluation/testset.py` | `data/eval/test_set.json` với SHA256 verification | `sha256sum data/eval/test_set.json` trước/sau corruption flow |
| Đánh giá retrieval hit rate, token F1, judge accuracy | `src/evaluation/metrics.py` | Baseline: 0,90/0,1930/0,60; Corrupted: 0,70/0,1717/0,50; Repaired: 0,90/0,1981/0,60 | `data/results/baseline_metrics.json` |
| Sinh báo cáo Markdown baseline và comparison | `src/observability/reporting.py` | `phase1_report.md` và `corruption_report.md` | Đọc file report và đối chiếu với metrics JSON |
| Viết 7 unit tests | `tests/test_observability_quality.py`, `tests/test_evaluation_testset.py` | 11/11 tests passed | `python -m pytest -q -p no:cacheprovider --basetemp .test-tmp` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

Frozen test set tại `data/eval/test_set.json` gồm 10 câu hỏi với 3 question types (summary, authors, date). Mỗi câu có `ground_truth_doc_ids` đối chiếu trực tiếp `paper_id` trong clean DataFrame. Test set được SHA256-hashed và xác minh không thay đổi sau corruption flow, đảm bảo mọi delta metric chỉ do chất lượng dữ liệu, không do thay đổi câu hỏi.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần evaluation & observability giải quyết ba vấn đề chính: (1) đo lường chính xác sự suy giảm chất lượng retrieval/answer khi dữ liệu bị corruption, (2) kiểm tra tính toàn vẹn của dữ liệu clean qua 12 quality gates, và (3) theo dõi freshness của corpus theo thời gian thực. Thách thức lớn nhất là đảm bảo cùng một test set được dùng cho cả ba trạng thái (baseline, corrupted, repaired) để các metric delta có ý nghĩa so sánh.

### Cách triển khai

**Quality checks** sử dụng cấu trúc standardized: mỗi check có `name`, `success` (boolean), `observed_value`, `expected`, và `message`. 12 checks bao gồm: required columns present, row count ≥ 3, paper_id not blank, paper_id unique, title not blank, summary not blank, summary ≥ 50 chars, summary_chars consistent, text_for_embedding not blank, published parseable, age_days ≥ 0, và age_days ≤ 180 (freshness threshold). Mỗi check report `observed_value` cụ thể (ví dụ: `paper_id_unique` fail với observed_value=2 cho biết chính xác có 2 duplicate values), giúp debug nhanh nguyên nhân根.

**Frozen test set** dùng `build_test_set(df, output_path)` với seed hardcode `RANDOM_SEED=42` trong file `testset.py`. Hàm sample 10 papers từ clean DataFrame, tạo câu hỏi cho mỗi question type (summary, authors, date, categories) chỉ khi ground truth không rỗng. Mỗi item có deterministic hash ID để đảm bảo reproducibility. Test set bị giới hạn: chỉ 10 câu, 3 question types (summary, authors, date), thiếu categories type — đây là hạn chế nghiêm trọng nhất cần cải thiện.

**Evaluation pipeline** chạy agent trên mỗi test question, ghi lại retrieval_trace (tool calls), kiểm tra ground-truth doc có trong top-k results không (retrieval hit), tính token F1 giữa answer và ground truth, và dùng LLM judge để đánh giá accuracy (1/0) và score (1-5). Judge model: dùng cùng `build_llm()` với answer generation (mặc định Gemini 2.5 Flash, temperature=0.0). Hạn chế: cùng model cho answer và judge có thể tạo bias — judge đánh giá cao câu trả lời cùng style/model. Hướng cải thiện: tách judge model khỏi answer model (ví dụ: answer bằng Gemini, judge bằng GPT-4o hoặc Claude).

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Clean DataFrame (24 records, schema includes paper_id, title, summary, authors, categories, published, age_days, summary_chars, text_for_embedding) |
| Output | `baseline_metrics.json` (retrieval_hit_rate, mean_token_f1, judge_accuracy, mean_judge_score), `baseline_quality.json` (12 checks pass/fail), `freshness_report.json` (fresh/stale status) |
| Module phụ thuộc | `src/ingestion/cleaning.py` (clean DataFrame schema), `src/retrieval/index.py` (ChromaDB collections), `src/retrieval/agent.py` (agent + retrieval_trace) |
| Module sử dụng output | `src/pipelines/phase1.py` (orchestration), `src/pipelines/corruption_flow.py` (comparison flow), `src/ui/app.py` (dashboard display) |
| Điều kiện lỗi cần xử lý | Ground truth blank/NaN trong test set (categories type), ChromaDB collection chưa tồn tại, LLM judge timeout/fallback |

### Cách xác minh

```bash
python -m pytest tests/test_observability_quality.py tests/test_evaluation_testset.py -v
```

- **Kết quả mong đợi:** 7 tests passed (6 quality checks + 1 testset blank/NaN handling)
- **Kết quả thực tế:** 7/7 passed
- **Artifact/log:** `data/quality/baseline_quality.json`, `data/results/baseline_metrics.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quyết định cách thiết kế test set để baseline, corrupted và repaired metric delta có ý nghĩa so sánh.
- **Các phương án đã cân nhắc:**
  - Phương án 1: Tạo test set mới mỗi lần chạy pipeline, sử dụng câu hỏi từ dữ liệu hiện tại.
  - Phương án 2: Freeze test set cố định với SHA256 hash, tái sử dụng nguyên vẹn cho cả ba trạng thái.
- **Phương án đã chọn:** Phương án 2 — freeze test set với hash verification.
- **Lý do:** Nếu test set thay đổi giữa các trạng thái, delta metric có thể phản ánh sự thay đổi câu hỏi thay vì tác động của corruption/repair. Frozen test set đảm bảo reproducibility và fairness trong so sánh. Trade-off là test set không tự cập nhật khi corpus thay đổi, nhưng trong bài lab này điều đó chấp nhận được.
- **Bằng chứng quyết định phù hợp:** corruption_flow.py step 7 verify SHA256 hash của test set không thay đổi sau toàn bộ flow. Kết quả: hash trước = hash sau → test set frozen.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `build_test_set()` crash với `ValueError: Invalid blank ground truth for paper_id=...` khi question type `categories` sinh ground truth từ `compact_join(paper.categories)` nhưng một số papers có categories rỗng sau cleaning. Hoặc tạo câu hỏi với ground truth là NaN/empty string, phá vỡ downstream metrics pipeline.
- **Lệnh hoặc bước tái hiện:** `python -c "from src.evaluation.testset import build_test_set; from src.ingestion.cleaning import build_clean_dataframe; from src.ingestion.crossref import load_raw_records; df = build_clean_dataframe(load_raw_records()); print(build_test_set(df))"` → crash với ValueError.
- **Nguyên nhân gốc:** `build_test_set()` dùng `_eligible_generators()` để select question types, nhưng `_has_non_blank_text()` (trong `src/evaluation/testset.py`, không phải `cleaning.py`) ban đầu chỉ check `isinstance(value, str)` — không xử lý đúng pandas NaN hoặc JSON null. Question type `categories` dùng `_categories_question()` sinh ground_truth từ `compact_join(paper.categories)`, nhưng một số papers có `categories_joined=""` hoặc `NaN` → `_has_non_blank_text()` trả về True cho NaN (vì `isinstance(NaN, str)` = False, nhưng logic chưa đúng).
- **Cách xử lý:** Bổ sung `_has_non_blank_text()` rejects pandas/JSON `NaN` values: `return isinstance(value, str) and bool(value.strip())`. Nếu ground truth rỗng, `_eligible_generators()` skip question type đó cho paper hiện tại và thử type khác. Nếu không có valid question type nào, raise ValueError với message rõ ràng.
- **Cách xác minh sau khi sửa:** `python -m pytest tests/test_evaluation_testset.py -v` → 1 test passed (test case cho blank/NaN handling). `data/eval/test_set.json` chỉ chứa 10 câu hỏi với ground truth không rỗng, không có NaN values.
- **Điều học được:** (1) Luôn kiểm tra ground truth contract trước khi dùng nó làm input cho evaluation — một ground truth blank sẽ phá vỡ toàn bộ metrics pipeline downstream. (2) Pandas NaN và JSON null có thể lọt qua type checking thông thường — cần explicit rejection. (3) Test set builder cần defensive programming: skip invalid items thay vì crash.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Dữ liệu bắt đầu từ Crossref REST API, được fetch qua `fetch_source_records()` với retry/backoff. Raw response được lưu nguyên trạng (`crossref_response.json`), sau đó parse thành `PaperRecord` dataclass (`crossref_records.json`). Cleaning pipeline chuyển raw records thành clean DataFrame: normalize text, parse dates, compute `age_days`, build `text_for_embedding`, deduplicate theo `paper_id`. MiniLM model tạo 384-dimensional embeddings từ `text_for_embedding`, được lưu vào ChromaDB với HNSW index và cosine similarity.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Test set gồm 10 câu hỏi được sample từ clean DataFrame với seed=42. Mỗi câu có `ground_truth` (text answer) và `ground_truth_doc_ids` (list paper_id). Khi agent trả lời, retrieval_trace ghi lại top-k documents. Retrieval hit rate = tỷ lệ câu có ground-truth doc trong top-k. Token F1 đo trùng token giữa answer và ground truth. Judge accuracy dùng LLM hoặc heuristic đánh giá answer correctness.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   Quality checks tập trung vào tính toàn vẹn schema và dữ liệu: required columns, paper_id uniqueness, text completeness, summary length, date parseability. Freshness monitoring tập trung vào thời gian: kiểm tra `published` date có parse được không, `age_days` có hợp lệ không, và corpus có stale documents (>180 ngày) không. Quality checks phát hiện corruption ở cấp record-level; freshness phát hiện ở cấp corpus-level.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Nếu mỗi trạng thái dùng test set khác nhau, delta metric có thể phản ánh sự thay đổi câu hỏi thay vì tác động của corruption/repair. Frozen test set đảm bảo mọi thay đổi metric chỉ do chất lượng dữ liệu, không do thay đổi evaluation setup. Đây là nguyên tắc controlled experiment: chỉ thay đổi một biến (data quality) tại một thời điểm.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Repair thành công khi: (1) quality checks phục hồi 12/12 pass (cùng baseline), (2) freshness trở lại `fresh` với 0 stale rows, (3) retrieval hit rate phục hồi về 0.90, (4) judge accuracy phục hồi về 0.60, (5) corrupted quality JSON và repaired quality JSON khác nhau nhưng repaired và baseline giống nhau. Artifact verification: `data/quality/repaired_quality.json` phải giống `baseline_quality.json` về pass/fail structure.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 0.90 | 0.70 | 0.90 | Corruption giảm 20% do blank summary và noise phá vỡ embedding quality; repair phục hồi hoàn toàn |
| `mean_token_f1` | 0,1930 | 0,1717 | 0,1981 | F1 thấp overall do answer dài hơn ground truth; repaired cao hơn baseline nhẹ do LLM non-determinism |
| `judge_accuracy` | 0.60 | 0.50 | 0.60 | Corruption giảm 10%; repair phục hồi hoàn toàn |
| `mean_judge_score` | 3.40 | 3.00 | 3.50 | Score giảm 0.4 do corruption; repaired cao hơn 0.1 do LLM variability |
| Quality checks | 12/12 pass | 8/12 pass | 12/12 pass | 4 checks fail: paper_id_unique, summary_not_blank, summary_minimum_length, age_days_within_freshness_threshold |
| Freshness status | fresh | stale | fresh | Stale due to 2 docs set published=2000-01-01; repair restore from raw |

### Kết luận từ số liệu

1. **[Data corruption — quality checks giảm 33%]:** 4 scenarios cộng hưởng: `summary_not_blank` fail (observed_value=2), `summary_minimum_length` fail (2), `paper_id_unique` fail (2), `age_days_within_freshness_threshold` fail (2). Quality checks giảm từ 12/12 xuống 8/12 — 4/12 checks fail, tương đương 33% quality gate bị phá vỡ. Freshness chuyển từ `fresh` sang `stale` với 2 stale rows (age_days=9714). Observed_value cụ thể giúp debug nhanh: `paper_id_unique` fail với observed_value=2 cho biết chính xác có 2 duplicate values, không chỉ "fail".

2. **[Data corruption — agent metrics giảm]:** Retrieval hit rate giảm 20% (0,90→0,70), judge accuracy giảm 10% (0,60→0,50), mean judge score giảm 0,40 (3,40→3,00). Chỉ 8/26 records bị corruption (31% records) đã đủ giảm retrieval hit rate 20% — chứng minh data quality có ảnh hưởng proportionally đến retrieval quality. Token F1 giảm nhẹ hơn (0,1930→0,1717) vì F1 đo overlap token, không nhạy với retrieval path.

3. **[Repair action — phục hồi hoàn toàn]:** Re-clean từ raw snapshot (`data/raw/crossref_records.json`) qua `build_clean_dataframe()` deterministic → row count/quality/freshness phục hồi 12/12, fresh → retrieval hit rate và judge accuracy phục hồi về baseline (0,90 và 0,60). Repair thành công vì: (a) raw snapshot không bị corruption thay đổi, (b) cleaning pipeline deterministic, (c) frozen test set SHA256-verified.

4. **[Quality check design — strengths và gaps]:**
   - **Strengths:** 12 checks detect được corruption ở record-level (blank, duplicate, stale date). Mỗi check report `observed_value` cụ thể, giúp debug nhanh. Cấu trúc standardized (name, success, observed_value, expected, message) giúp downstream nối quality check failure về đúng corruption scenario.
   - **Gaps:** Add_noise không fail basic quality check nào (summary intact, dates valid, no duplicates) nhưng vẫn affect agent metrics qua embedding quality. Cần bổ sung quality check cho embedding text length bất thường (ví dụ: `embedding_text_length_reasonable` với ngưỡng max length ~3000 chars).
   - **Ablation test cần thiết:** 4 scenarios chạy cùng lúc, không thể quy retrieval hit giảm 20% cho riêng một scenario. Cần chạy experiments riêng lẻ để đo impact cụ thể.

**Corruption nào ảnh hưởng rõ nhất — phân tích từ quality check perspective?**
- Blank_summary: fail 2 checks (summary_not_blank, summary_minimum_length) — corruption có impact lớn nhất lên quality gates
- Stale_date: fail 1 check (age_days_within_freshness_threshold) — chỉ affect freshness, không affect retrieval
- Duplicates: fail 1 check (paper_id_unique) — tăng row count nhưng retrieval vẫn có thể tìm đúng document
- Add_noise: KHÔNG fail bất kỳ basic quality check nào — nhưng affect agent metrics qua embedding quality. **Quality check gap quan trọng nhất.**

**Judge model bias — hạn chế quan trọng:**
Judge dùng cùng model với answer generation (Gemini 2.5 Flash, temperature=0.0). Điều này có thể tạo bias: judge đánh giá cao câu trả lời cùng style/model, hoặc penalize câu trả lời khác style. Judge accuracy 60% — 4/10 câu sai. Hướng cải thiện: tách judge model khỏi answer model (ví dụ: answer bằng Gemini, judge bằng GPT-4o hoặc Claude) để tránh bias.

**Kết quả nào khác với kỳ vọng ban đầu?**
Token F1 và judge score repaired cao hơn baseline (0,1981 vs 0,1930, 3,50 vs 3,40). Kỳ vọng ban đầu là repaired sẽ giống baseline. Bằng chứng: `_judge_answer()` trong `metrics.py` dùng `build_llm(temperature=0.0)` nhưng Gemini 2.5 Flash vẫn có variance. Để kiểm chứng cần: (a) chạy lặp 5-10 lần với cùng seed, (b) tính confidence interval (mean ± std), (c) dùng separate judge model.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline — frozen test set là nguyên tắc controlled experiment:** Contract giữa các giai đoạn pipeline (raw→clean→index→evaluation) phải rõ ràng và frozen. Frozen test set với SHA256 verification đảm bảo mọi delta metric chỉ do chất lượng dữ liệu, không do thay đổi evaluation setup. Nếu mỗi role tự sinh test set, so sánh sẽ bị sai lineage. Bằng chứng: corruption_flow.py step 7 verify SHA256 hash của test set không thay đổi sau toàn bộ flow.
2. **Về data quality/observability — observed_value quan trọng hơn pass/fail:** Quality checks phải report observed_value, không chỉ pass/fail. Khi check fail, observed_value giúp debug nhanh nguyên nhân gốc: `paper_id_unique` fail với observed_value=2 cho biết chính xác có 2 duplicate values, không chỉ "fail". 12 quality gates thiết kế theo cấu trúc standardized (name, success, observed_value, expected, message) giúp downstream có thể nối quality check failure về đúng corruption scenario.
3. **Về ảnh hưởng của data đến RAG agent — proportionally và trực tiếp:** Chỉ 8/26 records bị corruption (31%) đã đủ giảm retrieval hit rate 20%. Data quality có ảnh hưởng proportionally đến retrieval quality. **Insight mới:** Quality checks hiện tại detect được corruption ở record-level (blank, duplicate, stale date) nhưng KHÔNG detect được embedding-level corruption (add_noise không fail basic quality check nào). Cần bổ sung quality check cho embedding text length bất thường.

### Nếu có thêm thời gian

1. **Mở rộng test set lên 30-50 câu hỏi** cân bằng giữa 4 question types (summary, authors, date, categories) với ground truth verified. Hiện tại chỉ có 10 câu và không có categories type — đây là hạn chế nghiêm trọng nhất. Coverage 10/24 papers khiến metric dễ dao động; judge accuracy 60% có thể không phản ánh thực tế. Cách đo cải thiện: so sánh standard deviation của metrics giữa nhiều lần chạy với test set lớn hơn.
2. **Bổ sung quality check cho embedding text length bất thường** — hiện tại add_noise không fail basic quality check nào dù text_for_embedding tăng từ ~1700 lên >6300 chars. Cần thêm check: `embedding_text_length_reasonable` với ngưỡng max length.
3. **Chạy Ragas metrics** — hiện tại bị skip vì chưa set `RUN_RAGAS=1`. Cần fix shim `langchain_community.chat_models.vertexai` trước khi chạy. Ragas cung cấp faithfulness/context precision/recall — metrics quan trọng cho RAG evaluation mà hiện tại chưa có.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Bùi Công Hậu
**Ngày xác nhận:** 2026-08-06
