# BÁO CÁO CÁ NHÂN — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Giáp Hoàng Thịnh |
| MSSV | 2A202601492 |
| Khóa/Lớp | K4 |
| Tên nhóm/dự án | Quái Kiệt Mộng Mơ |
| Vai trò chính | Role 2 — Ingestion Owner |
| Repository | <https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo> |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data model PaperRecord | `src/ingestion/crossref.py::PaperRecord` | Crossref JSON payload | Frozen dataclass với 11 trường: `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `abs_url`, `pdf_url`, `comment` | Hoàn thành |
| DOI-to-ID converter | `src/ingestion/crossref.py::_doi_to_paper_id` | Chuỗi DOI từ Crossref (vd: `10.1145/3442188.3445922`) | Stable `paper_id` lowercase slug (vd: `10-1145-3442188-3445922`) | Hoàn thành |
| Crossref payload parser | `src/ingestion/crossref.py::parse_crossref_payload` | Raw Crossref JSON (message.items) | `list[PaperRecord]`, bỏ item thiếu DOI/title/abstract | Hoàn thành |
| API fetcher với retry | `src/ingestion/crossref.py::fetch_source_records` | `Settings` với query, filter, max_results | Raw response JSON lưu disk + parsed records JSON; retry/backoff HTTP 429/500/503/timeout/connection | Hoàn thành |
| Snapshot loader | `src/ingestion/crossref.py::load_raw_records` | Đường dẫn `crossref_records.json` | `list[PaperRecord]` đọc từ snapshot, tránh gọi lại API | Hoàn thành |
| Raw data artifacts | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Crossref REST API | 24 raw records + raw API response | Hoàn thành |

Phạm vi của tôi bắt đầu từ việc gọi Crossref REST API và kết thúc khi bàn giao raw records cho Role 3 (Cleaning). Tôi không xử lý cleaning, embedding hay evaluation — phần đó thuộc về các role tiếp theo trong pipeline.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Chốt CP0 contract về `paper_id`, schema và artifact paths | Role 1 — Pipeline integrator (Nhân) | Thống nhất stable `paper_id` từ DOI, frozen schema 11 trường, raw snapshot phục vụ repair |
| Bàn giao trường title, summary, authors, categories, published/updated và URL | Role 3 — Cleaning (Phụng) | Cleaning không cần đoán dữ liệu, parse trực tiếp từ schema đã chuẩn hóa |
| Cung cấp raw data lineage cho corruption và repair | Role 3 — Cleaning (Phụng) | Repair đọc lại `crossref_records.json` thay vì sửa tay corrupted data |
| Xác nhận contract trước khi Role 1 tích hợp pipeline | Role 1 — Pipeline integrator (Nhân) | Pipeline phase1 gọi `fetch_source_records()` rồi `load_raw_records()` theo đúng contract |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Hiện thực PaperRecord frozen dataclass | `src/ingestion/crossref.py::PaperRecord` | Dataclass 11 trường, frozen=True, không thể thay đổi sau khởi tạo | Kiểm tra `dataclass.is_frozen(PaperRecord)` hoặc thử gán giá trị mới sẽ raise `FrozenInstanceError` |
| Tạo paper_id ổn định từ DOI | `_doi_to_paper_id()` | DOI `10.1145/3442188.3445922` -> `10-1145-3442188-3445922`; lowercase, thay ký tự không phải alphanumeric bằng hyphen, strip leading/trailing hyphen | Kiểm tra `data/raw/crossref_records.json`: tất cả `paper_id` là lowercase slug, không có ký tự đặc biệt |
| Parse Crossref payload và lọc item thiếu dữ liệu | `parse_crossref_payload()` | 24 records hợp lệ xuất ra, bỏ qua items thiếu DOI, title hoặc abstract; log số lượng skipped | Đọc log: `24 records parsed, N skipped`; kiểm tra JSON output |
| Lưu raw response trước khi parse | `fetch_source_records()` | `data/raw/crossref_response.json` được ghi TRƯỚC khi parse | So thời gian tạo file, hoặc đọc pipeline log thấy "Raw API response saved" trước "Raw records saved" |
| Retry/backoff cho lỗi mạng và server | `fetch_source_records()` | Max 5 attempts, backoff `2^attempt` giây, retry cho HTTP 429/500/503, timeout và connection error | Kiểm tra log warning khi simulate lỗi; đọc code `time.sleep(wait)` với `wait = _BACKOFF_BASE ** attempt` |
| Lưu raw records JSON cho repair lineage | `fetch_source_records()`, `load_raw_records()` | `data/raw/crossref_records.json` với 24 dicts, đọc lại thành công bằng `load_raw_records()` | Repair flow (Role 3) đọc từ file này và tái tạo clean data mà không cần gọi lại API |
| Xử lý trường metadata phong phú | `_extract_authors()`, `_extract_url()`, `_extract_date()`, comment builder | Authors dạng "Ho Ten", abs_url/pdf_url tách riêng, dates ISO, comment chứa volume/issue/page | Đọc JSON output: mỗi record có đủ authors list, URLs, dates và comment |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần một nguồn dữ liệu học thuật đáng tin cậy làm đầu vào cho toàn bộ quy trình cleaning, embedding, indexing và evaluation. Crossref REST API (`https://api.crossref.org/works`) cung cấp metadata phong phú cho hơn 150 triệu records học thuật, nhưng có several vấn đề cần giải quyết: (1) **Response structure phức tạp** — response dạng JSON lồng nhau: `message.items[]`, mỗi item chứa nhiều nested fields (`title[]`, `author[]`, `date-parts[][]`, `link[]`), cần parse chuẩn để downstream không phải guess dữ liệu. (2) **Rate limit nghiêm ngặt** — Crossref yêu cầu "polite pool" (User-Agent header có email) và限制 request频率; HTTP 429 trả về khi quá nhanh. (3) **Cần lưu raw response nguyên bản** — để truy vết và repair mà không gọi lại API, đặc biệt quan trọng khi API có thể thay đổi response theo thời gian. (4) **Paper_id cần ổn định** — dù Crossref có thể cập nhật metadata (title, authors), paper_id phải không thay đổi.

### Cách triển khai

**Data model:** PaperRecord được hiện thực bằng `@dataclass(frozen=True)`, đảm bảo immutable sau khi tạo. Mỗi record chứa 11 trường: `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `abs_url`, `pdf_url`, `comment`. Frozen dataclass ngăn ngừa thay đổi ngoài ý muốn và giúp debug dễ hơn vì state không đổi. Frozen=True cũng đảm bảo paper_id không thể bị ghi đè sau khi tạo — đây là defense-in-depth cho lineage integrity.

**DOI-to-paper_id:** Hàm `_doi_to_paper_id` dùng regex `re.sub(r"[^a-zA-Z0-9]+", "-", doi)` rồi `strip("-").lower()`. Ví dụ: `10.1145/3442188.3445922` -> `10-1145-3442188-3445922`. DOI được chọn làm nguồn ID vì nó là định danh duy nhất toàn cầu trong học thuật, không phụ thuộc vào metadata có thể thay đổi. Format slug giúp ID đọc được, không chứa ký tự đặc biệt gây vấn đề cho file path hay JSON key.

**Parser logic:** `parse_crossref_payload` duyệt `payload["message"]["items"]`, với mỗi item: kiểm tra DOI (bỏ nếu rỗng), trích title (bỏ nếu rỗng), trích abstract/summary (bỏ nếu rỗng). Sau đó gọi các helper `_extract_authors` (ghép given + family), `_extract_date` (parse date-parts[][] thành ISO string), `_extract_url` (tách abs_url từ DOI, pdf_url từ link array), và builder comment (volume/issue/page). Chỉ items có đủ cả ba trường DOI + title + abstract mới được tạo thành PaperRecord. Logic này loại bỏ khoảng 10-20% items từ Crossref (items thiếu abstract hoặc DOI).

**Retry/backoff:** `fetch_source_records` dùng loop `for attempt in range(1, _MAX_RETRIES + 1)` với `_MAX_RETRIES=5`, `_BACKOFF_BASE=2.0`. Với mỗi request, nếu status 200 thì break; nếu status trong `_RETRY_STATUSES={429, 500, 503}` thì sleep `2^attempt` giây rồi retry (2s, 4s, 8s, 16s, 32s); nếu Timeout hoặc ConnectionError cũng sleep và retry. Sau `_MAX_RETRIES` lần mà vẫn fail thì raise `RuntimeError` với thông báo rõ. User-Agent header `"Day10DataPipelineLab/0.1 (mailto:student@example.com; educational-use)"` đảm bảo nằm trong "polite pool" của Crossref.

**Cache/snapshot:** Sau khi gọi API thành công, raw response JSON được ghi vào `data/raw/crossref_response.json` TRƯỚC khi parse. Sau parse, records list được serialize thành `data/raw/crossref_records.json`. Nếu `REFRESH_SOURCE=false` và cả hai file đã tồn tại, `fetch_source_records` đọc lại từ disk bằng `load_raw_records()` mà không gọi API. Cơ chế này đảm bảo: (a) raw response luôn là audit trail nguyên bản, (b) repair flow có thể đọc lại raw records mà không gọi API, (c) debugging dễ dàng nếu parse logic có bug.

**Helper functions:** `_extract_date` parse `date-parts` của Crossref (dạng `[[2026, 3, 15]]`) thành ISO string `2026-03-15` (hỗ trợ YYYY, YYYY-MM, YYYY-MM-DD). `_clean_text` xoá HTML tags bằng regex `<[^>]+>` và chuẩn hóa whitespace. `_extract_authors` ghép `given` + `family` với separator ", ". `_extract_url` tách abs_url từ DOI URL pattern và pdf_url từ link array.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref REST API response JSON; query: `agentic retrieval augmented generation large language model`, filter: `from-pub-date:2026-02-07,has-abstract:true`, max 24 records |
| Output | `data/raw/crossref_response.json` (raw API response, ~200KB), `data/raw/crossref_records.json` (24 parsed PaperRecord dicts, ~50KB) |
| Contract với downstream | Role 3 (Cleaning) nhận list[PaperRecord] hoặc đọc JSON; các trường title, summary, authors, categories, published, updated, abs_url, pdf_url đều đã normalized; DOI rỗng/không hợp lệ đã bị loại |
| Module phụ thuộc | `core.config.Settings` (query, filter, paths, refresh_source), `requests` (HTTP client) |
| Điều kiện lỗi cần xử lý | Crossref API trả 429/500/503, timeout 30s, connection error, item thiếu DOI/title/abstract, raw file đã tồn tại nhưng không yêu cầu refresh |

### Cách xác minh

```bash
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp
```

- **Kết quả mong đợi:** Toàn bộ unit tests pass; parser bỏ đúng items thiếu dữ liệu; raw response lưu trước parse.
- **Kết quả thực tế:** `11 passed in 11.95s` trên Python 3.13.14.
- **Artifact/log:** `data/raw/crossref_response.json`, `data/raw/crossref_records.json` chứa 24 records; log ghi rõ số records parsed và skipped.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần tạo `paper_id` ổn định để làm khóa nối lineage xuyên suốt pipeline — từ raw records qua cleaning, indexing, evaluation đến corruption/repair. Paper_id phải không thay đổi khi metadata (title, authors, dates) thay đổi, và phải duy nhất cho mỗi paper.
- **Các phương án đã cân nhắc:** (1) Dùng title slug (dễ thay đổi nếu Crossref cập nhật title); (2) dùng MD5 hash của title + authors (opaque, khó debug, có thể collision); (3) dùng DOI slugified (global unique trong học thuật, ổn định theo thời gian, dễ debug).
- **Phương án đã chọn:** Phương án 3 — DOI slugified qua `_doi_to_paper_id`: lowercase, thay ký tự không phải alphanumeric bằng hyphen, strip leading/trailing hyphen.
- **Lý do:** DOI là định danh duy nhất toàn cầu được duy trì bởi Crossref và các nhà xuất bản. Nó không phụ thuộc vào metadata có thể thay đổi (title, authors) hay thời điểm index. Format slug giúp ID đọc được, không chứa ký tự đặc biệt gây vấn đề cho file path hay JSON key. Repair flow có thể tái tạo cùng paper_id từ cùng DOI, đảm bảo lineage không bị đứt.
- **Bằng chứng quyết định phù hợp:** 24 records trong `crossref_records.json` đều có paper_id dạng lowercase hyphen-separated; cùng một DOI luôn tạo ra cùng paper_id dù chạy lại parser nhiều lần; Role 3 dùng paper_id làm dedup key và Role 5 dùng paper_id trong `ground_truth_doc_ids`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi:** Khi gọi Crossref API lần đầu từ môi trường mạng trường, server trả HTTP 429 (Too Many Requests) liên tục trong 3 lần request đầu tiên, gây timeout pipeline.
- **Bước tái hiện:** Chạy `fetch_source_records()` với network không ổn định; log hiển thị "Crossref API HTTP 429 -> retry 1/5 after 2.0s", "...retry 2/5 after 4.0s", "...retry 3/5 after 8.0s".
- **Nguyên nhân gốc:** Crossref có rate limit nghiêm ngặt cho các request không nằm trong "polite pool" (thiếu User-Agent header hợp lệ hoặc chạy quá nhanh). Ban đầu User-Agent chưa được cấu hình đúng và không có delay giữa các request.
- **Cách xử lý:** (1) Thêm header User-Agent `"Day10DataPipelineLab/0.1 (mailto:student@example.com; educational-use)"` theo yêu cầu "polite pool" của Crossref; (2) tăng `_MAX_RETRIES` từ 3 lên 5 và `_BACKOFF_BASE` thành 2.0 để thời gian chờ giữa các retry dài hơn (2s, 4s, 8s, 16s, 32s); (3) xử lý cả Timeout và ConnectionError trong cùng retry loop thay vì raise ngay lập tức.
- **Cách xác minh sau khi sửa:** Pipeline chạy thành công từ đầu đến cuối, log ghi "Crossref API 200 OK: N bytes received" ngay từ lần đầu; `data/raw/crossref_response.json` và `data/raw/crossref_records.json` được tạo đầy đủ với 24 records.
- **Điều học được:** API bên thứ ba luôn có rate limit và downtime; retry/backoff không phải optional mà là bắt buộc cho ingestion layer. Lưu raw response trước parse cũng quan trọng vì nếu parse lỗi, ta vẫn có dữ liệu thô để debug.

## 7. Hiểu biết về luồng end-to-end

1. Crossref REST API trả raw JSON chứa metadata 24 papers. Role 2 (tôi) lưu nguyên raw response vào `data/raw/crossref_response.json` rồi parse thành 24 `PaperRecord`, mỗi record có stable `paper_id` từ DOI slug, title, summary, authors, categories, dates và URLs. Raw records lưu thành `data/raw/crossref_records.json`.
2. Role 3 (Phụng) đọc raw records, normalize text, parse ngày, tính `age_days`, tạo `text_for_embedding` và deduplicate theo `paper_id`. Output là clean CSV/JSON với 24 dòng, thêm trường `summary_chars`, `source`, `extracted_skills`.
3. Role 4 (Mai) dùng MiniLM-L6-v2 tạo embedding từ `text_for_embedding`, lưu vào ChromaDB với collection `papers-baseline`. Metadata giữ `paper_id` và title để truy vết.
4. Role 5 (Hậu) tạo frozen test set 10 câu từ clean data, chạy evaluation (retrieval hit, token F1, judge accuracy), quality checks (12 gates) và freshness monitoring.
5. Corruption (Role 3) áp dụng 4 scenario (blank summary, stale date, noise, duplicates) lên frozen documents; corrupted index rebuild (Role 4); evaluation lại trên corrupted data (Role 5). Repair đọc raw snapshot (từ artifact Role 2 tạo), chạy lại cleaning, rebuild index, evaluation — chứng minh lineage repair từ raw, không sửa tay corrupted data.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 0,90 | 0,70 | 0,90 | Corruption giảm 20 điểm %, repair phục hồi hoàn toàn về baseline |
| `mean_token_f1` | 0,1930 | 0,1717 | 0,1981 | Giảm 0,0213, repair phục hồi và nhẹ hơn baseline 0,0050 |
| `judge_accuracy` | 0,60 | 0,50 | 0,60 | Giảm 10 điểm %, repair phục hồi hoàn toàn |
| `mean_judge_score` | 3,40 | 3,00 | 3,50 | Giảm 0,40, repair tăng 0,10 so baseline |
| Quality checks | 12 pass / 0 fail | 8 pass / 4 fail | 12 pass / 0 fail | 4 check fail do corruption, repair phục hồi đúng |
| Freshness | fresh, 0 stale | stale, 2 stale | fresh, 0 stale | Stale date scenario phát hiện và repair đúng |
| Records count | 24 | 26 | 24 | Duplicate scenario tạo 2 dòng thừa, repair dedupe về 24 |
| Raw records artifact | 24 records | 24 records (không đổi) | 24 records (không đổi) | Raw snapshot Role 2 tạo không bị corruption thay đổi |

### Kết luận từ số liệu

1. **Raw snapshot — "single source of truth" xuyên suốt pipeline:** Corruption chỉ tác động lên clean DataFrame (`data/clean/papers_clean_corrupted.json`), KHÔNG chạm vào `data/raw/crossref_records.json`. Kiểm chứng: đọc `crossref_records.json` sau corruption flow vẫn trả về 24 dicts với đầy đủ 11 fields. Cách tôi lưu raw response TRƯỚC khi parse bằng `fetch_source_records()` đã tạo bản audit chính xác — `crossref_response.json` (raw API response, ~200KB) và `crossref_records.json` (parsed records, ~50KB) đều được tạo trước khi bất kỳ processing nào xảy ra. Đây là design decision quan trọng nhất của ingestion layer: raw snapshot phải bất biến, mọi processing tiếp theo đều có thể rebuild từ raw.

2. **Paper_id từ DOI slug — lineage integrity được chứng minh:** `corruption_log.json` ghi `frozen_target_paper_ids_present` = 10 IDs, 4 scenarios mỗi scenario có 2 changes, total 8 documents bị corruption trực tiếp. Trong scenario `duplicates`, `_scenario_targets()` chọn 2 paper_ids (`10-32473-flairs-39-1-141782` và `10-3390-app16052244`), `pd.concat` thêm 2 copy rows → row count 24→26. Quality check `paper_id_unique` fail với 2 duplicate values đúng như dự kiến. Repair dedupe về đúng 24 dòng gốc. Frozen dataclass (`@dataclass(frozen=True)`) đảm bảo paper_id không thể bị ghi đè — defense-in-depth cho lineage integrity.

3. **Recovery cơ chế — tại sao repair phục hồi hoàn toàn:** Cleaning pipeline `build_clean_dataframe()` nhận `list[PaperRecord]` từ `load_raw_records()`, đọc trực tiếp `crossref_records.json`. Vì raw records chứa đủ 11 trường (paper_id, title, summary, authors, categories, published, updated, abs_url, pdf_url, comment), cleaning không cần gọi lại API hay parse lại. Contract giữa Role 2 và Role 3 rõ ràng: Role 2 bàn giao raw records JSON, Role 3 đọc và transform — không có dependency ngầm. Kết quả: repaired DataFrame có 24 rows, 12/12 quality checks pass, retrieval hit 0,90 và judge accuracy 0,60 — giống hệt baseline.

4. **LLM non-determinism — không phải ingestion improvement:** Mean token F1 repaired (0,1981) > baseline (0,1930) và judge score repaired (3,50) > baseline (3,40). Đây là biến động của LLM judge, không phải ingestion tốt hơn baseline. Bằng chứng: `temperature=0.0` đã set trong `build_llm()` nhưng Gemini 2.5 Flash vẫn có variance. Judge accuracy 60% — 4/10 câu sai, có thể do cùng model cho answer và judge. Hướng cải thiện: tách judge model khỏi answer model.

5. **Ablation test — hạn chế quan trọng:** 4 corruption scenarios chạy cùng lúc, không thể quy retrieval hit giảm 20% cho riêng một scenario. Cần chạy 4 experiments riêng lẻ: blank_summary alone, stale_date alone, add_noise alone, duplicates alone → đo metric delta từng scenario. Đây là hướng cải thiện quan trọng nhất cho phiên bản tiếp theo.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Lưu raw snapshot trước parse là bắt buộc — và nó đã cứu toàn bộ repair flow:** Nếu chỉ lưu parsed records mà không lưu raw response, khi parse logic có bug hoặc contract thay đổi, ta không thể truy vết lại dữ liệu gốc. Bằng chứng cụ thể: `crossref_response.json` được ghi TRƯỚC khi gọi `parse_crossref_payload()`, đảm bảo nếu parse lỗi ta vẫn có raw response để debug. Trong corruption flow, repair đọc lại `crossref_records.json` (24 records từ Role 2) rồi chạy lại cleaning — không cần gọi lại API.
2. **Retry/backoff phải xử lý cả HTTP status code lẫn network exception — bài học từ rate limit Crossref:** Ban đầu tôi chỉ retry cho 429/500/503 nhưng bỏ qua Timeout và ConnectionError, gây crash khi mạng trường không ổn định. HTTP 429 từ Crossref liên tục 3 lần đầu vì thiếu User-Agent header hợp lệ. Sau khi: (a) thêm header `"Day10DataPipelineLab/0.1 (mailto:student@example.com; educational-use)"` theo yêu cầu "polite pool", (b) tăng `_MAX_RETRIES` từ 3 lên 5 với `_BACKOFF_BASE=2.0` (2s, 4s, 8s, 16s, 32s), (c) xử lý Timeout/ConnectionError trong cùng retry loop — pipeline chạy ổn định.
3. **Frozen dataclass cho paper_id giúp tránh bugs lineage phức tạp — và nó đã chứng minh trong corruption flow:** Khi paper_id là immutable (`@dataclass(frozen=True)`), không thể vô tình gán lại giá trị khác trong quá trình processing. Điều này quan trọng vì paper_id là khóa nối từ raw → clean → index → evaluation → repair. Bằng chứng: corruption scenario `duplicates` tạo 2 copy rows nhưng paper_id vẫn giống gốc, quality check `paper_id_unique` phát hiện chính xác 2 duplicate values, repair dedupe về đúng 24 dòng gốc.

### Nếu có thêm thời gian

Tôi sẽ bổ sung unit test riêng cho `_doi_to_paper_id` với nhiều edge cases (DOI có slash, dấu chấm, Unicode), thêm integration test mock Crossref API response để kiểm tra retry logic (giả lập 429 rồi 200), và version hóa raw snapshot bằng content hash để phát hiện khi dữ liệu thay đổi ngoài ý muốn. Cải thiện được đo bằng coverage phần ingestion, số integration test pass, và khả năng phát hiện regression khi thay đổi parser logic.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Giáp Hoàng Thịnh

**MSSV:** 2A202601492

**Ngày xác nhận:** 2026-08-06
