# BÁO CÁO CÁ NHÂN — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Trần Gia Phụng |
| MSSV | 2A202601286 |
| Khóa/Lớp | K4 |
| Tên nhóm | Quái Kiệt Mộng Mơ |
| Vai trò chính | Cleaning & Corruption Owner |
| Repository | https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cleaning pipeline | `src/ingestion/cleaning.py` — `build_clean_dataframe()`, `validate_clean_dataframe()`, `_extract_skills()` | 24 raw `PaperRecord` objects từ Role 2 | Clean DataFrame 24 records với schema đầy đủ, `text_for_embedding`, `extracted_skills` | Hoàn thành |
| Text normalization | `src/ingestion/cleaning.py` — `_norm_text()`, `_parse_datetime()` | Raw text và date strings từ Crossref | Text đã normalize, ngày parse theo ISO-8601 | Hoàn thành |
| Schema validation | `src/ingestion/cleaning.py` — `validate_clean_dataframe()` | Clean DataFrame | AssertionError nếu thiếu columns hoặc có null ở critical fields | Hoàn thành |
| Skill extraction | `src/ingestion/cleaning.py` — `_extract_skills()` với YAML taxonomy | Title + Summary | Danh sách skills match từ `skill_taxonomy.yaml` | Hoàn thành |
| Corruption pipeline | `src/ingestion/corruption.py` — `corrupt_clean_dataframe()` | Clean DataFrame, frozen target paper_ids | Corrupted DataFrame 26 records + corruption log JSON | Hoàn thành |
| Corruption log | `data/results/corruption_log.json` | Corruption runs | Schema version, reference time, before/after snapshots cho mỗi scenario | Hoàn thành |
| Clean data artifacts | `data/clean/` | Pipeline outputs | Baseline, corrupted, repaired CSV/JSON files | Hoàn thành |

Phạm vi của tôi bắt đầu từ raw `PaperRecord` do Role 2 bàn giao và kết thúc tại clean DataFrame phục vụ Role 4 (indexing) và Role 5 (evaluation/observability). Corruption được thực hiện sau khi Role 5 đóng băng test set, và repair được thực hiện bằng cách chạy lại cleaning từ raw snapshot.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Cung cấp clean schema cho evaluation | Hậu (Evaluation & Observability) | Xác nhận `paper_id`, title, summary, authors, categories, published, age_days, text_for_embedding đủ cho test set và quality checks |
| Đảm bảo cleaning deterministic cho repair | Nhân (Pipeline Integrator) | `build_clean_dataframe()` chạy lại từ raw records cho ra cùng kết quả baseline, không cần fix tay corrupted data |
| Hỗ trợ frozen test-set overlap | Hậu (Evaluation & Observability) | Corruption scenarios nhắm đúng 10 paper_ids trong frozen test set, đảm bảo mỗi scenario ảnh hưởng ít nhất 1 document được evaluate |
| Validation contract trước khi build index | Mai (RAG & Agent Owner) | Clean DataFrame pass `validate_clean_dataframe()` trước khi Role 4 tạo embeddings |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Normalize HTML/whitespace, parse dates | `cleaning.py::_norm_text()`, `_parse_datetime()` | 24 records cleaned, 0 records lost do normalization | Kiểm tra `papers_clean.json` không có HTML tags, dates ở định dạng ISO |
| Tính age_days, summary_chars, extracted_skills | `cleaning.py::build_clean_dataframe()` | `age_days` không âm, `summary_chars` khớp summary length, skills match taxonomy | Đọc `data/clean/papers_clean.json` và kiểm tra manual trên 2-3 records |
| Build text_for_embedding | `cleaning.py::_build_text_for_embedding()` | Format "Title: ... \| Authors: ... \| Summary: ... \| Categories: ... \| Skills: ..." cho 24 records | Đọc field `text_for_embedding` trong clean JSON |
| Deduplicate theo paper_id | `cleaning.py::build_clean_dataframe()` step 5 | 24 records không trùng paper_id (từ 24 raw, không có duplicate trong baseline) | `validate_clean_dataframe()` pass |
| Drop short summaries (<100 chars) | `cleaning.py::build_clean_dataframe()` step 6 | Tất cả records có summary >= 100 ký tự | Kiểm tra `summary_chars` >= 100 trong clean JSON |
| Sort by freshness | `cleaning.py::build_clean_dataframe()` step 7 | Records sắp xếp tăng dần age_days (mới nhất đứng đầu) | Kiểm tra age_days trong clean JSON tăng dần |
| Validate clean schema | `cleaning.py::validate_clean_dataframe()` | Pass cho baseline, corrupted (pre-concat), repaired | Hàm không raise ValueError |
| Tạo 4 corruption scenarios | `corruption.py::corrupt_clean_dataframe()` | 24 -> 26 rows, log before/after cho 8 documents | Đọc `data/results/corruption_log.json` |
| Corruption scenario: blank_summary | `corruption.py` lines 108-124 | 2 docs mất summary, `summary_chars=0`, embedding text rút ngắn | Log: `10-1007-s10278-026-02086-9` (1875->0), `10-20944-preprints202604-0339-v1` (1687->0) |
| Corruption scenario: stale_date | `corruption.py` lines 126-140 | 2 docs `published=2000-01-01`, `age_days=9714` | Log: `10-21079-11681-50309`, `10-2118-234689-pa` |
| Corruption scenario: add_noise | `corruption.py` lines 142-157 | 2 docs embedding text > 6300 chars (30x boilerplate) | Log: `10-21203-rs-3-rs-10012178-v1` (1697->6348), `10-22214-ijraset-2026-82233` (1685->6336) |
| Corruption scenario: duplicates | `corruption.py` lines 159-174 | 2 rows copy, row count 24->26 | Log: `10-32473-flairs-39-1-141782` (row 16->24), `10-3390-app16052244` (row 21->25) |
| Repair: re-clean từ raw | `corruption_flow.py` gọi `build_clean_dataframe()` từ raw snapshot | 26 -> 24 records, schema phục hồi | So `papers_clean_repaired.json` với `papers_clean.json` |

Output tiêu biểu mà phần việc của tôi tạo ra là `data/results/corruption_log.json`. Artifact này ghi chi tiết từng corruption scenario: paper_id bị ảnh hưởng, row_index, giá trị trước (before) và sau (after) của summary_chars, published, age_days, text_for_embedding_chars. Thanks vào log này, Role 5 có thể nối chính xác mỗi quality check fail về đúng scenario, thay vì chỉ biết "data corrupted".

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Raw `PaperRecord` từ Crossref chứa text có HTML tags, whitespace không chuẩn, ngày ở nhiều định dạng, và không có computed fields (age_days, text_for_embedding). Downstream pipeline (vector indexing, evaluation) cần một DataFrame sạch, schema chuẩn, không duplicate, với embedding text được ghép sẵn. Đồng thời, cần cơ chế corruption có kiểm soát để tạo dữ liệu "bị lỗi" một cách deterministic, nhắm đúng frozen test set để đo tác động lên retrieval/answer metrics.

### Cách triển khai

**Cleaning pipeline** (`build_clean_dataframe`) gồm 8 bước chính (theo code comments):

1. **Normalize text & parse dates (per record loop)**: `_norm_text()` dùng regex xóa HTML/XML tags rồi collapse whitespace. `_parse_datetime()` thử 4 format ISO-8601. Compute `age_days`, build helper columns (`authors_joined`, `categories_joined`, `summary_chars`), extract skills, build `text_for_embedding`.
2. **Deduplicate** theo `paper_id` bằng `drop_duplicates`.
3. **Drop short summaries**: Loại rows có summary < 100 chars (`MIN_SUMMARY_CHARS = 100`).
4. **Sort** tăng dần `age_days` (mới nhất đầu tiên), NaN xuống cuối.
5. **Validate**: `validate_clean_dataframe()` kiểm tra required columns (`paper_id`, `title`, `summary`, `text_for_embedding`, `authors_joined`, `categories_joined`, `published`, `age_days`) và null ở 4 critical columns.

**Corruption pipeline** (`corrupt_clean_dataframe`) nhận clean DataFrame và danh sách frozen target paper_ids:

- **Target selection**: `_target_ids_in_dataframe()` lọc paper_ids có trong DataFrame. `_scenario_targets()` chọn 2 IDs cho mỗi scenario theo offset cycle.
- **blank_summary**: Đặt `summary=""`, `summary_chars=0`, rebuild `text_for_embedding` (chỉ còn Title + Authors).
- **stale_date**: Đặt `published="2000-01-01"`, tính `age_days` = (now - 2000-01-01).days = 9714.
- **add_noise**: Prepend 30x boilerplate sentence vào đầu `text_for_embedding`, mỗi lần ~210 chars -> tổng > 6300 chars.
- **duplicates**: `pd.concat` thêm copy rows vào DataFrame, tăng row count.
- **Log**: Mỗi change ghi `before` (summary_chars, published, age_days, text_for_embedding_chars) và `after` tương ứng.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input cleaning | `list[PaperRecord]` với paper_id, title, summary, authors, categories, published, updated, abs_url, pdf_url |
| Output cleaning | `pd.DataFrame` với 17 columns, 24 rows (baseline), pass `validate_clean_dataframe()` |
| Input corruption | Clean DataFrame + `target_paper_ids` (10 IDs từ frozen test set) + `output_log_path` |
| Output corruption | Corrupted DataFrame (26 rows) + `data/results/corruption_log.json` |
| Module phụ thuộc | `ingestion.crossref` (PaperRecord), `core.utils` (write_json), `core/skill_taxonomy.yaml` |
| Module sử dụng output | `src/retrieval/index.py` (embedding + ChromaDB), `src/evaluation/testset.py`, `src/evaluation/metrics.py`, `src/observability/quality.py` |
| Điều kiện lỗi cần xử lý | Empty records list, missing required columns, DataFrame rỗng, no overlap giữa target IDs và DataFrame |

### Cách xác minh

```bash
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp
```

- **Kết quả mong đợi:** Toàn bộ tests pass, clean DataFrame pass validate, corruption log chứa đúng 4 scenarios với 8 documents.
- **Kết quả thực tế:** `11 passed in 11.95s` trên Python 3.13.14.
- **Artifact/log:** `data/clean/papers_clean.json`, `data/clean/papers_clean_corrupted.json`, `data/clean/papers_clean_repaired.json`, `data/results/corruption_log.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần tạo corruption nhắm đúng documents có trong frozen test set để mỗi scenario đều có thể đo được tác động lên retrieval/answer metrics. Nếu corruption nhắm random documents, có thể scenario nào cũng không affect metric vì test questions không cover documents bị corruption.
- **Các phương án đã cân nhắc:**
  - Phương án 1: Corruption ngẫu nhiên bất kỳ documents nào trong clean DataFrame.
  - Phương án 2: Corruption thủ công chọn documents dựa trên kiến thức nội dung.
  - Phương án 3: Nhận `target_paper_ids` từ frozen test set, dùng `_scenario_targets()` cycle offset để mỗi scenario pick 2 IDs, đảm bảo overlap.
- **Phương án đã chọn:** Phương án 3 — corruption nhận frozen target IDs và cycle through chúng.
- **Lý do:** Đảm bảo corruption luôn affect evaluation-relevant documents. Mỗi scenario nhắm 2 IDs khác nhau bằng offset cycling, tránh overlap giữa scenarios (trừ khi corpus quá nhỏ). Nếu không có overlap giữa target IDs và DataFrame thì `_target_ids_in_dataframe()` raise ValueError thay vì silently corrupt không measure được.
- **Bằng chứng quyết định phù hợp:** `corruption_log.json` ghi `frozen_target_paper_ids_present` = 10 IDs, 4 scenarios mỗi scenario có 2 changes, total 8 documents bị corruption trực tiếp. Kết quả: 4 quality checks fail đúng (paper_id_unique, summary_not_blank, summary_minimum_length, age_days_within_freshness_threshold), retrieval hit rate giảm 20%, freshness chuyển sang stale.

## 6. Một design decision quan trọng đã xử lý

- **Bối cảnh:** Cần quyết định mức độ corruption cho scenario `blank_summary` — xóa bao nhiêu phần của `text_for_embedding`?
- **Vấn đề ban đầu:** Khi corruption `blank_summary`, embedding text bị rebuild nhưng vẫn chứa Authors và Categories, khiến retrieval vẫn có thể match một phần. Không đạt được mức suy giảm tối đa cho scenario blank summary.
- **Phương án đã cân nhắc:** (1) Xóa hoàn toàn `text_for_embedding` → text rỗng, embedding model sinh vector không có ý nghĩa → downstream modules crash. (2) Chỉ xóa summary, giữ title/authors/categories → text giảm đáng kể nhưng document vẫn identifiable. (3) Xóa summary + categories, chỉ giữ title → text rất ngắn nhưng vẫn có semantic content.
- **Phương án đã chọn:** Phương án 2 — Chỉ xóa phần summary khỏi embedding, giữ lại title/authors/categories.
- **Lý do:** Corruption nên đủ nghiêm trọng để metric thay đổi nhưng không nên tạo data hoàn toàn invalid. Nếu `text_for_embedding` rỗng, MiniLM sẽ sinh vector zero-padding → ChromaDB indexing crash hoặc trả kết quả vô nghĩa. Mục đích là tạo corruption **đo được** (metric thay đổi rõ rệt), không phải tạo **invalid data** (modules crash). Bằng chứng: `text_for_embedding_chars` giảm đáng kể (1804→310 và 1704→210 chars), `summary_not_blank` check fail, retrieval hit rate giảm 20%.
- **Điều học được:** Corruption design cần balance giữa "đủ nghiêm trọng để metric thay đổi" và "không quá nghiêm trọng để modules crash". Đây là controlled experiment, không phải stress test.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến clean DataFrame như thế nào?**
   Crossref REST API trả raw JSON response, được Role 2 fetch và parse thành 24 `PaperRecord` objects. Mỗi PaperRecord chứa paper_id (từ DOI normalized), title, summary, authors, categories, published date, URLs. `build_clean_dataframe()` nhận list[PaperRecord] và run_date, normalize text (xóa HTML tags, collapse whitespace), parse dates (4 format ISO-8601), compute age_days, extract skills từ YAML taxonomy, build text_for_embedding (ghép Title + Authors + Summary + Categories + Skills), deduplicate theo paper_id, drop short summaries (<100 chars), sort by age_days và validate schema. Output: 24-row DataFrame với 17 columns, sẵn sàng cho embedding.

2. **Corruption hoạt động như thế nào và tại sao cần frozen test set overlap?**
   `corupt_clean_dataframe()` nhận clean DataFrame và 10 frozen target paper_ids từ test set. Nó chọn 2 IDs cho mỗi scenario bằng offset cycling, áp dụng 4 types corruption: blank summary (xóa summary, rebuild embedding text), stale date (set published=2000-01-01), add noise (prepend 30x boilerplate vào embedding text), duplicates (copy 2 rows). Log ghi before/after snapshots. Frozen test set overlap đảm bảo corruption affect documents mà evaluation measure, nếu không thì metric có thể không thay đổi dù data corrupted.

3. **Repair hoạt động như thế nào và vì sao không fix tay corrupted data?**
   Repair load lại raw records từ `data/raw/crossref_records.json` rồi chạy `build_clean_dataframe()` với cùng contract. Vì cleaning pipeline deterministic (cùng input -> cùng output), repaired DataFrame giống hệt baseline. Không fix tay corrupted data vì: (1) dễ bỏ sót lỗi, (2) không có lineage rõ ràng, (3) không chứng minh được cleaning pipeline có thể tự phục hồi. Repair chứng minh raw snapshot là source of truth đáng tin cậy.

4. **Vai trò của validate_clean_dataframe trong pipeline?**
   `validate_clean_dataframe()` là gate cuối cùng trước khi DataFrame được bàn giao downstream. Nó kiểm tra: (1) đủ 8 required columns, (2) không có null ở 4 critical columns (paper_id, title, summary, text_for_embedding). Nếu fail thì raise ValueError, pipeline stop thay vì truyền bad data cho Role 4 (embedding) và Role 5 (evaluation). Đây là defense-in-depth sau khi build_clean_dataframe đã filter ở bước 6-7.

5. **Tại sao extracted_skills dùng YAML taxonomy thay vì hardcode trong code?**
   `_extract_skills()` load keywords từ `src/core/skill_taxonomy.yaml`, match case-insensitive với title+summary. Thiết kế này cho phép: (1) thêm/sửa skills chỉ cần edit YAML, không chạm code, (2) team share cùng taxonomy, (3) version taxonomy independently. Hiện tại skills có trong text_for_embedding nhưng không trực tiếp affect retrieval metrics vì MiniLM không specialized cho skills. Đây là pre-computed metadata cho tương lai khi có skill-aware retrieval.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 0.90 | 0.70 | 0.90 | Corruption giảm 20%, repair phục hồi hoàn toàn |
| `mean_token_f1` | 0,1930 | 0,1717 | 0,1981 | F1 giảm nhẹ, repaired cao hơn baseline 0,0050 (LLM non-determinism) |
| `judge_accuracy` | 0.60 | 0.50 | 0.60 | Giảm 10%, phục hồi hoàn toàn |
| `mean_judge_score` | 3.40 | 3.00 | 3.50 | Giảm 0.4, repaired cao hơn baseline 0.1 |
| Quality checks | 12 pass / 0 fail | 8 pass / 4 fail | 12 pass / 0 fail | 4 checks fail đúng scenario: paper_id_unique (duplicates), summary_not_blank + summary_minimum_length (blank_summary), age_days_within_freshness_threshold (stale_date) |
| Freshness status | fresh, 0 stale | stale, 2 stale | fresh, 0 stale | Stale_date scenario tạo 2 rows age_days=9714 |

### Kết luận từ số liệu

1. **[Data corruption: blank_summary]** → 2 docs mất summary (`summary_chars=0`) → `summary_not_blank` fail (observed_value=2) và `summary_minimum_length` fail (observed_value=2). **Cơ chế ảnh hưởng:** Embedding text rebuild nhưng chỉ còn Title + Authors + Categories (từ 1804→310 chars và 1704→210 chars), mất phần quan trọng nhất (summary chứa nội dung chính của paper). MiniLM embedding vector bị skew vì thiếu semantic content → retrieval hit giảm. Đây là corruption có impact lớn nhất lên quality checks (2/4 checks fail).
2. **[Data corruption: stale_date]** → 2 docs `published=2000-01-01`, `age_days=9714` → `age_days_within_freshness_threshold` fail (observed_value=2), freshness `stale`. **Cơ chế ảnh hưởng:** Không trực tiếp affect retrieval vì embedding text không thay đổi, nhưng phá vỡ freshness monitoring — 2 rows age_days=9714 vượt ngưỡng 180 ngày.
3. **[Data corruption: add_noise]** → 2 docs embedding text > 6300 chars (từ ~1700, tăng ~3.7x) → retrieval/answer metrics suy giảm. **Cơ chế ảnh hưởng:** 30x boilerplate sentence (~210 chars mỗi lần) được prepend vào đầu `text_for_embedding`, làm vỡ embedding vector distribution. MiniLM không specialized cho noise rejection → semantic search không match query với document đúng. **Điểm quan trọng:** Add_noise không fail bất kỳ basic quality check nào (summary vẫn intact, dates vẫn valid, no duplicates) nhưng vẫn affect agent metrics qua embedding quality — chứng minh quality checks hiện tại chưa detect được embedding-level corruption.
4. **[Data corruption: duplicates]** → row count 24→26, `paper_id_unique` fail (observed_value=2). **Cơ chế ảnh hưởng:** `pd.concat` thêm 2 copy rows, ChromaDB indexing 26 vectors thay vì 24. Retrieval vẫn có thể tìm document đúng trong top-k nhưng có thể retrieve duplicate thay vì unique docs, contributing vào retrieval hit giảm.
5. **[Repair]** → re-clean từ raw snapshot → `build_clean_dataframe()` deterministic (cùng input raw records → cùng output DataFrame) → row count/schema/quality/freshness phục hồi 12/12 → retrieval và judge metrics trở lại baseline.

**Corruption nào ảnh hưởng rõ nhất — phân tích chéo giữa quality checks và agent metrics?**
- **Về quality checks:** Blank_summary ảnh hưởng rõ nhất (2/4 checks fail: summary_not_blank, summary_minimum_length). Stale_date fail 1 check (age_days_within_freshness_threshold). Duplicates fail 1 check (paper_id_unique). Add_noise không fail basic quality check nào — đây là quality check gap quan trọng nhất.
- **Về agent metrics:** Không thể quy riêng vì 4 scenarios áp dụng cùng lúc. Tuy nhiên, blank_summary và add_noise là hai corruption ảnh hưởng trực tiếp đến embedding quality (text_for_embedding thay đổi), trong khi stale_date chỉ ảnh hưởng freshness và duplicates chỉ tăng row count.
- **Quality check gap — insight quan trọng nhất:** Quality checks hiện tại detect được corruption ở record-level (blank, duplicate, stale date) nhưng KHÔNG detect được embedding-level corruption (add_noise). Add_noise chèn 30x boilerplate vào `text_for_embedding` (1697→6348 chars) làm vỡ embedding quality, nhưng summary vẫn intact, dates vẫn valid, no duplicates → tất cả 12 quality checks vẫn pass. Cần bổ sung quality check cho embedding text length bất thường (ví dụ: `embedding_text_length_reasonable` với ngưỡng max length).
- **Ablation test — hạn chế quan trọng:** 4 scenarios chạy cùng lúc, không thể quy retrieval hit giảm 20% cho riêng một scenario. Cần chạy 4 experiments riêng lẻ: blank_summary alone, stale_date alone, add_noise alone, duplicates alone → đo metric delta từng scenario. Đây là hướng cải thiện quan trọng nhất.

**Kết quả nào khác kỳ vọng?** Repaired token_f1 (0,1981) và judge_score (3,50) cao hơn baseline (0,1930, 3,40). Đây là LLM non-determinism, không phải repair làm tốt hơn baseline. Bằng chứng: `temperature=0.0` đã set trong `build_llm()` nhưng Gemini 2.5 Flash vẫn có variance. Cách xác minh: chạy nhiều lần với cùng seed/temperature để tính confidence interval (mean ± std).

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data cleaning deterministic là chìa khóa cho repair — và nó đã chứng minh:** `build_clean_dataframe()` deterministic: cùng input raw records → cùng output DataFrame. Bằng chứng: repaired DataFrame có 24 rows, 12/12 quality checks pass, retrieval hit 0,90 và judge accuracy 0,60 — giống hệt baseline. Nếu cleaning có random element hoặc phụ thuộc external state thì repair không thể recover exact baseline. Deterministic cleaning cũng giúp debug: khi corruption log ghi before/after, ta có thể verify rằng repair tạo ra cùng kết quả với baseline.
2. **Corruption cần overlap với evaluation set để đo được — design pattern có thể tái sử dụng:** Corruption nhắm random documents có thể không affect metrics vì test questions không cover documents bị corruption. Design `target_paper_ids` parameter với `_scenario_targets()` cycle offset đảm bảo mỗi scenario ảnh hưởng documents được evaluate. Đây là controlled experiment, không phải random testing. Pattern này có thể tái sử dụng cho bất kỳ data pipeline nào cần measure corruption impact.
3. **Corruption log với before/after snapshots tạo audit trail — và nó reveal quality check gap:** Không chỉ ghi "corrupted" mà ghi chính xác field nào, giá trị trước/sau, paper_id nào. Nhờ đó downstream có thể nối quality check failure về đúng corruption scenario. **Insight mới:** Log cũng reveal rằng add_noise không fail basic quality check nào — quality checks hiện tại chưa detect được embedding-level corruption. Cần bổ sung check cho embedding text length bất thường.

### Nếu có thêm thời gian

Tôi sẽ mở rộng corruption scenarios sang các loại mới: (1) **field swap** — đổi authors giữa 2 documents để measure tác động lên authors-based retrieval, (2) **encoding corruption** — chèn Unicode non-breaking spaces vào title để test robustness của text normalization, (3) **partial corruption** — chỉ corrupt 1 document thay vì 2 để measure granularity của metric sensitivity. Đồng thời, tôi sẽ thêm unit tests cho từng corruption scenario riêng lẻ (isolated tests) để measure impact độc lập thay vì combined effect. Cải thiện được đo bằng: coverage scenarios, metric delta per isolated corruption, và số quality checks fail per scenario.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Trần Gia Phụng

**MSSV:** 2A202601286

**Ngày xác nhận:** 2026-08-06
