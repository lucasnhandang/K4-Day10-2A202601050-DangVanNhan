# BÁO CÁO CÁ NHÂN — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Giáp Hoàng Thịnh |
| MSSV | 2A202601492 |
| Khóa/Lớp | K4 |
| Tên nhóm/dự án | K4-Day10-2A202601050-DangVanNhan |
| Vai trò chính | Role 2 — Ingestion owner |
| Repository | <https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo.git> |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Schema paper record | `src/ingestion/crossref.py::PaperRecord` | Item JSON từ Crossref | Dataclass chuẩn hóa 11 trường dùng chung cho cleaning | Hoàn thành |
| Sinh stable document ID | `src/ingestion/crossref.py::_doi_to_paper_id` | DOI thô | `paper_id` dạng slug ổn định trong snapshot; DOI gốc được lưu riêng để truy vết URL nguồn | Hoàn thành |
| Parse payload Crossref | `src/ingestion/crossref.py::parse_crossref_payload`, `_extract_date`, `_extract_authors`, `_extract_url`, `_clean_text` | Raw JSON response | Danh sách `PaperRecord` đã làm sạch HTML, chuẩn hóa ngày và tác giả | Hoàn thành |
| Fetch có retry/backoff | `src/ingestion/crossref.py::fetch_source_records` | `Settings` (query, filter, max_results) | Raw response + raw records lưu trên đĩa, có cache nếu đã tồn tại | Hoàn thành |
| Raw lineage | `data/raw/crossref_response.json`, `data/raw/crossref_records.json`, `crossref.py::load_raw_records` | — | 24 raw records làm nguồn duy nhất cho cleaning và cho bước repair | Hoàn thành |

Phạm vi của tôi dừng lại ở raw layer: tôi không tự ý làm sạch hay suy diễn field nghiệp vụ, chỉ đảm bảo dữ liệu từ Crossref được lấy đầy đủ, đúng định dạng và có thể tái tạo lại từ snapshot đã lưu, để Role 3 không phải đoán dữ liệu khi cleaning.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thống nhất raw schema tại CP0 | Role 3 — Cleaning | Xác nhận `title`, `summary`, `authors`, `categories`, `published`/`updated`, `abs_url`/`pdf_url` đủ để cleaning không cần fetch lại Crossref |
| Giải thích cơ chế cache raw | Role 1 — Pipeline integrator | Xác nhận `fetch_source_records` chỉ gọi API khi `refresh_source=True` hoặc chưa có file, giúp orchestration Phase 1 chạy lại nhanh khi debug |
| Kiểm tra `paper_id` ổn định qua nhiều lần chạy | Role 4, Role 5 | Xác nhận cùng DOI luôn sinh cùng `paper_id`, không đổi giữa các lần fetch lại |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chuẩn hóa `PaperRecord` với 11 trường cố định | `crossref.py::PaperRecord` (frozen dataclass) | Schema đầu vào ổn định cho `cleaning.py` | Đọc `data/raw/crossref_records.json`, đối chiếu field với dataclass |
| Retry/backoff cho lỗi tạm thời | `fetch_source_records` | Không crash khi Crossref trả 429/500/503, timeout hoặc connection error | Đọc log khi chạy fetch; test thủ công bằng cách giả lập status lỗi |
| Lưu raw response trước khi parse | `fetch_source_records` | `data/raw/crossref_response.json` (114.390 bytes) tồn tại độc lập với `crossref_records.json` | Kiểm tra hai file tồn tại và `response` chứa nguyên `payload["message"]["items"]` |
| Parse an toàn, bỏ qua record thiếu field bắt buộc | `parse_crossref_payload` | 24/24 record hợp lệ được parse; record thiếu DOI/title/abstract bị skip có log | So `len(items)` trong response với số record parse được |
| Cache raw để tránh gọi API lặp lại | `fetch_source_records`, `load_raw_records` | Chạy lại Phase 1 nhiều lần không tốn thêm request tới Crossref trừ khi chủ động `refresh_source=1` | Chạy lại `run_phase1.py` hai lần liên tiếp, quan sát không có request mới |

Output tiêu biểu của tôi là `data/raw/crossref_records.json`. Đây là snapshot duy nhất mà `_require_phase1_artifacts` (Role 1) và bước repair trong `corruption_flow.py` (Role 3) dùng làm nguồn để rebuild dữ liệu sạch — nếu raw layer sai hoặc thiếu field, toàn bộ khả năng "repair từ nguồn đáng tin cậy" của bài lab sẽ sụp đổ.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Crossref REST API trả về JSON lồng nhiều tầng, có thể chứa HTML/XML trong abstract (JATS tags), thiếu field ở một số item, và có thể trả lỗi 429/5xx hoặc timeout khi gọi thật. Nếu ingestion không xử lý các trường hợp này, cleaning ở bước sau sẽ nhận dữ liệu bẩn hoặc pipeline crash giữa chừng khi gọi API. Ngoài ra, cần một document ID ổn định qua nhiều lần fetch để `paper_id` không đổi giữa các lần chạy — nếu không, `ground_truth_doc_ids` trong evaluation set của Role 5 sẽ không còn khớp index.

### Cách triển khai

`fetch_source_records` gọi `requests.get(..., timeout=30)` trong vòng lặp tối đa `_MAX_RETRIES = 5` lần; nếu status nằm trong `_RETRY_STATUSES = {429, 500, 503}`, hoặc gặp `requests.exceptions.Timeout`/`ConnectionError`, thì chờ theo backoff hàm mũ `_BACKOFF_BASE ** attempt` (2s, 4s, 8s, 16s, 32s) rồi thử lại; các lỗi HTTP khác gọi thẳng `response.raise_for_status()` và không retry. Nếu hết `_MAX_RETRIES` mà vẫn lỗi, hàm `raise RuntimeError` rõ ràng thay vì để lỗi mạng lan truyền mơ hồ lên tầng trên.

Raw response được ghi ra đĩa (`raw_api_response`) **trước** khi parse, để nếu logic parse sau này thay đổi hoặc có bug, vẫn có thể parse lại từ response gốc mà không cần gọi lại API. `parse_crossref_payload` duyệt từng item, bỏ qua item thiếu DOI/title/abstract (log số lượng skip), dùng `_clean_text` để strip tag HTML/XML bằng regex và gộp khoảng trắng, `_extract_authors` chỉ giữ tác giả có `family` name, `_extract_date` thử nhiều nguồn ngày theo thứ tự ưu tiên (`published` → `published-print` → `published-online` → `created`).

`_doi_to_paper_id` sinh `paper_id` bằng cách thay mọi ký tự không phải chữ/số trong DOI thành `-`, strip dấu `-` ở hai đầu rồi lowercase — ví dụ `10.1145/3442188.3445922` → `10-1145-3442188-3445922`. Cách này tạo ID ổn định cho cùng một DOI và đủ phân biệt trong snapshot hiện tại. Vì phép slug hóa làm mất thông tin về các dấu phân cách, DOI gốc vẫn được lưu riêng để bảo đảm lineage và tạo chính xác URL `https://doi.org/{doi}`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `Settings.source_api`, `source_query`, `source_filter`, `max_results=24` từ `src/core/config.py` |
| Output | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` (list `PaperRecord` dạng dict qua `asdict`) |
| Module phụ thuộc | `src/core/config.py` (Settings/Paths), `src/core/utils.py` (I/O helpers) |
| Module sử dụng output | `src/ingestion/cleaning.py::build_clean_dataframe`, bước repair trong `src/pipelines/corruption_flow.py` |
| Điều kiện lỗi cần xử lý | HTTP 429/500/503, timeout, connection error, item thiếu DOI/title/abstract, tác giả thiếu `family` name, abstract chứa HTML/XML |

### Cách xác minh

```bash
uv run python script/run_phase1.py
```

- **Kết quả mong đợi:** `data/raw/crossref_response.json` và `data/raw/crossref_records.json` được tạo với 24 record hợp lệ, không còn tag HTML trong `summary`.
- **Kết quả thực tế:** Hai file tồn tại đúng như group_report mô tả (24 raw records); `data/raw/crossref_records.json` hiện có 55.898 bytes, `paper_id` mẫu dạng `10-47576-2949-1894-2026-7-7-023` xác nhận đúng thuật toán slug.
- **Artifact/log:** `data/raw/`; không chứa API key hay secret, chỉ chứa dữ liệu công khai từ Crossref.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần chọn cách sinh `paper_id` ổn định để làm khóa xuyên suốt pipeline (clean, index, evaluation ground truth), trong khi Crossref không cấp sẵn một ID ngắn gọn, ổn định qua nhiều lần fetch.
- **Các phương án đã cân nhắc:** (1) dùng thứ tự item trả về từ API (positional index) làm ID; (2) hash toàn bộ nội dung record (title+summary) làm ID; (3) chuẩn hóa DOI thành slug làm ID.
- **Phương án đã chọn:** Phương án 3 — slug hóa DOI.
- **Lý do:** DOI là ID học thuật toàn cục duy nhất, không đổi giữa các lần fetch (khác với positional index có thể đổi nếu thứ tự trả về của API thay đổi). Slug từ DOI tạo khóa ổn định cho corpus hiện tại, còn trường DOI gốc được giữ lại để truy vết chính xác về `https://doi.org/{doi}`. Hash nội dung sẽ đổi ID nếu title/summary được chuẩn hóa khác đi ở bước cleaning, phá vỡ tính ổn định.
- **Bằng chứng quyết định phù hợp:** Qua nhiều lần chạy `run_phase1.py` với cache raw, `paper_id` của cùng một DOI không đổi; đây là điều kiện tiên quyết để `ground_truth_doc_ids` trong `data/eval/test_set.json` của Role 5 luôn khớp với index của Role 4 giữa baseline, corrupted và repaired.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Một số abstract trả về từ Crossref chứa tag JATS XML dạng `<jats:p>...</jats:p>`, nếu đưa thẳng vào `summary`/`text_for_embedding` sẽ làm nhiễu nội dung đưa vào MiniLM và hiển thị sai trên UI.
- **Lệnh hoặc bước tái hiện:** Parse thử một item Crossref có field `abstract` chứa tag `<jats:p>` mà không qua bước làm sạch.
- **Nguyên nhân gốc:** Crossref trả abstract dưới dạng XML có cấu trúc (JATS), không phải plain text, trong khi pipeline downstream giả định `summary` là text thuần.
- **Cách xử lý:** Viết `_clean_text` dùng regex `<[^>]+>` để loại bỏ toàn bộ tag, sau đó gộp khoảng trắng thừa bằng một regex whitespace riêng; áp dụng cho cả `title` và `summary` ngay tại bước parse, trước khi bàn giao cho cleaning.
- **Cách xác minh sau khi sửa:** Kiểm tra `data/raw/crossref_records.json`, không còn ký tự `<`/`>` trong trường `summary`; test `tests/test_ingestion_cleaning.py` (dùng `PaperRecord` làm fixture) xác nhận input có tag JATS vẫn cho ra `summary` sạch sau `build_clean_dataframe`.
- **Điều học được:** Không nên giả định dữ liệu từ API bên ngoài đã ở dạng plain text; cần làm sạch ngay tại tầng ingestion để mọi module downstream không phải tự phòng thủ lại cùng một vấn đề.

Phần chưa xử lý xong:

- **Phạm vi bị ảnh hưởng:** `src/ingestion/crossref.py` hiện chưa có unit test riêng — file `tests/test_ingestion_cleaning.py` chỉ dùng `PaperRecord` làm fixture để test `cleaning.py`, không test trực tiếp `parse_crossref_payload`, `fetch_source_records`, retry/backoff hay `_doi_to_paper_id`.
- **Những gì đã loại trừ:** Đã xác nhận không có file `tests/test_ingestion_crossref.py` nào trong repository; không phải do file bị đặt sai tên hay bị bỏ sót khi tìm kiếm.
- **Bước tiếp theo:** Thêm `tests/test_ingestion_crossref.py` với payload Crossref giả lập (mock `requests.get`) để kiểm tra retry/backoff khi trả 429/500/503, kiểm tra `parse_crossref_payload` bỏ qua đúng item thiếu field, và kiểm tra `_doi_to_paper_id` với các DOI có ký tự đặc biệt.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Dữ liệu bắt đầu từ Crossref REST API: `fetch_source_records` gọi API với query/filter cấu hình sẵn, lưu nguyên raw response, sau đó `parse_crossref_payload` chuyển từng item thành `PaperRecord`. Role 3 nhận danh sách này, chuẩn hóa text, tính thêm các trường phái sinh và tạo `text_for_embedding`. Role 4 dùng MiniLM mã hóa `text_for_embedding` thành vector và lưu vào ChromaDB.
2. Evaluation set của Role 5 sinh câu hỏi từ clean dataframe, lấy `ground_truth_doc_ids` từ chính `paper_id` mà tôi tạo ra ở tầng raw. Vì `paper_id` ổn định qua các lần fetch, agent trả lời dựa trên retrieval trong ChromaDB có thể được đối chiếu đúng với ground truth để tính retrieval hit rate.
3. Quality checks kiểm tra tính hợp lệ tĩnh của dữ liệu tại một thời điểm (schema, ID trùng, text rỗng); freshness monitoring nhìn theo trục thời gian dựa trên `published`/`age_days` mà tôi trích xuất từ Crossref — nếu tôi trích ngày sai, cả hai lớp observability này đều sẽ cho kết quả sai theo.
4. Phải dùng cùng test set cho ba trạng thái vì corruption/repair chỉ thay đổi dữ liệu, không thay đổi câu hỏi; nếu test set đổi, không thể biết delta metric đến từ corruption hay từ câu hỏi khác.
5. Repair thành công khi dữ liệu được build lại từ đúng raw snapshot mà tôi lưu tại `data/raw/crossref_records.json`, không phải từ dữ liệu clean hay corrupted — đây chính là lý do vì sao tôi lưu raw response độc lập với raw records, và vì sao raw records không bao giờ bị pipeline ghi đè sau bước ingestion đầu tiên.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 0,90 | 0,70 | 0,90 | Phục hồi đúng bằng baseline vì repair đọc lại từ raw snapshot tôi cung cấp |
| `mean_token_f1` | 0,1930 | 0,1717 | 0,1981 | Không thuộc phạm vi raw layer nhưng cho thấy raw snapshot đủ ổn định để repair tái tạo đúng nội dung |
| `judge_accuracy` | 0,60 | 0,50 | 0,60 | Phục hồi hoàn toàn |
| `mean_judge_score` | 3,40 | 3,00 | 3,50 | Phục hồi và nhỉnh hơn baseline nhẹ, nằm ngoài kiểm soát của raw layer |
| Quality checks | 12 pass / 0 fail | 8 pass / 4 fail | 12 pass / 0 fail | 24 raw records không đổi trong suốt quá trình corrupt/repair |
| Freshness status | fresh | stale (2 dòng) | fresh | `published`/`age_days` gốc từ raw layer được khôi phục đúng sau repair |

### Kết luận từ số liệu

1. Bốn corruption scenario chỉ tác động lên bản sao clean/embedding, không đụng đến raw snapshot của tôi → khi repair đọc lại raw và chạy lại cleaning, 24 dòng, schema và giá trị `published`/`age_days` quay về đúng như trước khi corrupt.
2. Vì `paper_id` sinh từ DOI không đổi giữa các lần rebuild, retrieval hit rate và judge accuracy đo trên cùng test set phục hồi đúng 0,90 và 0,60 như baseline — không có "ID trôi" giữa các lần build lại index.

Corruption ảnh hưởng rõ nhất tới phạm vi của tôi (gián tiếp) là khả năng repair hoàn toàn dựa vào raw snapshot: nếu raw records của tôi từng bị thiếu field hoặc `paper_id` không ổn định, bước repair của Role 3 sẽ không thể phục hồi đúng 24 dòng và đúng `paper_id` như quan sát thực tế.

Kết quả khác kỳ vọng ban đầu không nằm ở raw layer — 24/24 raw records nhất quán qua toàn bộ Phase 1 và Phase 2, không có raw record nào bị mất hay đổi ID trong suốt thí nghiệm corruption/repair.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw layer là nền tảng của toàn bộ khả năng "repair đáng tin cậy" — nếu raw snapshot sai hoặc không ổn định, mọi lớp phía sau (clean, index, evaluation) đều không thể phục hồi đúng dù logic của chúng hoàn toàn chính xác.
2. Xử lý lỗi mạng (retry/backoff) và làm sạch dữ liệu bẩn từ nguồn ngoài (HTML/XML trong abstract) nên nằm ngay tại tầng ingestion, để các module downstream có thể tin tưởng schema đầu vào mà không phải tự phòng thủ lại.
3. Một ID ổn định qua nhiều lần fetch (ở đây là `paper_id` từ DOI) là điều kiện tiên quyết để mọi phép so sánh baseline/corrupted/repaired trong cả pipeline có ý nghĩa, không chỉ riêng cho module của tôi.

### Nếu có thêm thời gian

Tôi sẽ viết `tests/test_ingestion_crossref.py` dùng `unittest.mock` để giả lập `requests.get` trả về lần lượt 429 rồi 200, xác nhận đúng số lần retry và thời gian backoff dự kiến; đồng thời test `parse_crossref_payload` với payload có item thiếu DOI/title/abstract để xác nhận số lượng skip đúng như log. Cải thiện được đo bằng coverage của `crossref.py` tăng từ 0% (hiện tại không có test trực tiếp) lên có test cho retry logic và parsing edge case.

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
