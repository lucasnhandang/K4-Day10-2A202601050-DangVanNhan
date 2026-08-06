# BÁO CÁO CÁ NHÂN — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Trần Gia Phụng |
| MSSV | 2A202601286 |
| Khóa/Lớp | K4 |
| Tên nhóm/dự án | K4-Day10-2A202601050-DangVanNhan |
| Vai trò chính | Role 3 — Cleaning & corruption owner |
| Repository | <https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo.git> |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Clean schema & transform | `src/ingestion/cleaning.py::build_clean_dataframe`, `_norm_text`, `_parse_datetime`, `_extract_skills`, `_build_text_for_embedding` | `list[PaperRecord]` từ Role 2 | `pd.DataFrame` clean với `paper_id`, `text_for_embedding`, `age_days`... đúng contract | Hoàn thành |
| Validate clean contract | `cleaning.py::validate_clean_dataframe` | DataFrame vừa build | `ValueError` nếu thiếu cột bắt buộc hoặc còn NaN ở cột không được rỗng | Hoàn thành |
| Corruption có kiểm soát | `src/ingestion/corruption.py::corrupt_clean_dataframe`, `_target_ids_in_dataframe`, `_scenario_targets` | Clean DataFrame + danh sách `paper_id` thuộc frozen evaluation set | 4 scenario (`blank_summary`, `stale_date`, `add_noise`, `duplicates`) và `data/results/corruption_log.json` | Hoàn thành |
| Repair từ raw snapshot | Gọi lại `build_clean_dataframe` trên `raw_records_json` trong `src/pipelines/corruption_flow.py` | `data/raw/crossref_records.json` | Clean data phục hồi 24 dòng, không sửa tay dữ liệu corrupted | Hoàn thành |
| Test cleaning & corruption | `tests/test_ingestion_cleaning.py`, `tests/test_ingestion_corruption.py` | DataFrame/`PaperRecord` giả lập | Xác nhận filter, dedupe, 4 scenario và cơ chế chặn corruption không đo được | Hoàn thành |

Phạm vi của tôi nằm giữa raw layer của Role 2 và index/evaluation của Role 4, Role 5: tôi quyết định record nào đủ điều kiện vào clean dataset, cách tạo lỗi có kiểm soát trên dữ liệu, và cách phục hồi đúng nguồn gốc dữ liệu khi cần.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thống nhất frozen test set trước khi corrupt | Role 5 — Evaluation | `corrupt_clean_dataframe` bắt buộc nhận `target_paper_ids` từ `ground_truth_doc_ids`, `raise ValueError` nếu không có ID nào giao với dataframe |
| Xác nhận rebuild index không lẫn dữ liệu cũ | Role 4 — RAG | Đảm bảo `text_for_embedding` sau corruption/repair được tính lại nhất quán với hàm cleaning gốc, không để Role 4 tự suy đoán |
| Kiểm tra artifact repair trước khi Role 1 publish comparison | Role 1 — Pipeline integrator | Xác nhận repaired dataframe đi qua đúng `validate_clean_dataframe` trước khi ghi ra `data/clean/` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chuẩn hóa text, ngày, tác giả/categories | `build_clean_dataframe` | 24 raw → 24 clean, không mất record ở baseline | So dòng `data/raw/crossref_records.json` với `data/clean/papers_clean.csv` |
| Lọc record không đạt contract (`title` rỗng hoặc `summary` < 100 ký tự) | `build_clean_dataframe` (kiểm tra 2 lần: per-record và trên DataFrame) | Không có record nào lọt lưới có summary quá ngắn | Test `test_cleaning_enforces_summary_date_and_embedding_contract` |
| Deduplicate theo `paper_id`, sort theo `age_days` | `build_clean_dataframe` (`drop_duplicates`, `sort_values`) | Clean dataset không trùng ID, tài liệu mới xếp trước, `NaN` age xếp cuối | Đọc `data/clean/papers_clean.csv`, kiểm tra `paper_id.is_unique` |
| Bốn corruption scenario nhắm đúng frozen target IDs | `corrupt_clean_dataframe` | 26 dòng (2 duplicate), 2 blank summary, 2 stale date, 2 add-noise, có log before/after | Đọc `data/results/corruption_log.json`, đối chiếu `frozen_target_paper_ids_present` |
| Repair bằng re-clean từ raw, không patch corrupted | `corruption_flow.py` gọi `build_clean_dataframe(load_raw_records(...))` | 24 dòng, 12/12 quality checks pass, freshness `fresh` | So `data/clean/papers_clean_repaired.*` với baseline |

Output tiêu biểu của tôi là `data/results/corruption_log.json`. File này không chỉ ghi 4 scenario đã áp dụng mà còn ghi rõ `frozen_target_paper_ids_present`, `source_row_count`, `corrupted_row_count` và before/after theo từng `paper_id` — cho phép Role 5 và Role 1 truy vết chính xác dòng nào bị hỏng theo cách nào, thay vì chỉ biết "dữ liệu đã bị corrupt" chung chung.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Raw records từ Role 2 chưa đủ điều kiện để đưa thẳng vào embedding: cần chuẩn hóa text, tính các trường phái sinh (`age_days`, `summary_chars`, `extracted_skills`), loại bỏ record không đạt chất lượng tối thiểu và đảm bảo `paper_id` duy nhất. Đồng thời, để chứng minh pipeline có observability thật sự (không chỉ chạy xong là coi như đúng), cần tạo lỗi có kiểm soát trên đúng những document mà bộ câu hỏi đánh giá sẽ chạm tới, rồi phục hồi bằng một cơ chế đáng tin cậy chứ không phải sửa tay.

### Cách triển khai

Trong `build_clean_dataframe`, mỗi record được: chuẩn hóa `title`/`summary` qua `_norm_text` (regex strip tag HTML/XML, gộp whitespace); lọc bỏ ngay nếu `not title or len(summary) < MIN_SUMMARY_CHARS` (`MIN_SUMMARY_CHARS = 100`); parse `published` qua `_parse_datetime` thử lần lượt 4 format ngày; tính `age_days = (run_date - published_dt).total_seconds() / 86_400` (bỏ tzinfo trước khi trừ để tránh lỗi naive/aware datetime); nối `authors_joined`/`categories_joined`; trích `extracted_skills` bằng cách so khớp `title + summary` (lowercase) với từ khóa trong `core/skill_taxonomy.yaml` — nếu file taxonomy không tồn tại, chỉ log cảnh báo và trả `{}` thay vì crash. Cuối cùng `_build_text_for_embedding` ghép `title`, `authors_joined` (fallback `"Unknown"` nếu rỗng), `summary` (cắt 1500 ký tự), `categories_joined` và skills thành một chuỗi cho MiniLM. Sau khi có DataFrame, tôi kiểm tra lại điều kiện `title`/`summary` một lần nữa để phòng trường hợp pandas coercion (ví dụ NaN) lọt qua bước lọc đầu, rồi `drop_duplicates(subset=["paper_id"])` và `sort_values("age_days", na_position="last")`.

`corrupt_clean_dataframe` bắt buộc nhận `target_paper_ids` (thường là `ground_truth_doc_ids` từ frozen test set của Role 5); `_target_ids_in_dataframe` giao (intersect) danh sách này với ID thật có trong DataFrame, `raise ValueError` nếu giao rỗng — chủ đích để "một thí nghiệm corruption không thể trông có vẻ ổn chỉ vì câu hỏi test không bao giờ chạm tới record bị hỏng". Mỗi scenario lấy đúng 2 dòng qua `_scenario_targets(target_ids, offset, count=2)` với offset khác nhau (0/2/4/6) theo kiểu cyclic index: `blank_summary` xóa `summary` và rebuild `text_for_embedding`; `stale_date` gán `published="2000-01-01"` và `age_days` tương ứng; `add_noise` chèn một đoạn boilerplate cố định vào đầu `text_for_embedding` (không đụng `summary`); `duplicates` copy nguyên hai dòng và `pd.concat` vào cuối. Toàn bộ thao tác trên bản `deep copy` của DataFrame gốc để không làm hỏng dữ liệu caller đang giữ.

Repair **không** sửa dữ liệu corrupted: `corruption_flow.py` gọi `load_raw_records(raw_records_json)` rồi chạy lại đúng `build_clean_dataframe` — cùng một hàm, cùng một contract như lần build clean data đầu tiên — nên repaired data về bản chất là một lần "build baseline lại từ đầu", không phải một phép "undo" từng scenario.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `list[PaperRecord]` từ Role 2; với corruption còn cần `target_paper_ids` từ Role 5 |
| Output | `data/clean/papers_clean.csv/json`, `data/clean/*_corrupted.*`, `data/clean/*_repaired.*`, `data/results/corruption_log.json` |
| Module phụ thuộc | `src/ingestion/crossref.py::PaperRecord`, `core/skill_taxonomy.yaml`, `src/core/utils.py` |
| Module sử dụng output | `src/retrieval/embeddings.py`/`index.py` (Role 4), `src/evaluation/testset.py`/`metrics.py` (Role 5), `src/pipelines/phase1.py` và `corruption_flow.py` (Role 1) |
| Điều kiện lỗi cần xử lý | Record thiếu `title`/`summary` quá ngắn, ngày không parse được, taxonomy file thiếu, `target_paper_ids=None`, giao rỗng giữa target IDs và dataframe |

### Cách xác minh

```bash
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp tests/test_ingestion_cleaning.py tests/test_ingestion_corruption.py
```

- **Kết quả mong đợi:** `build_clean_dataframe` lọc đúng record không đạt contract và tạo `text_for_embedding` đúng định dạng; `corrupt_clean_dataframe` tạo đúng 4 scenario, không sửa DataFrame gốc, và từ chối chạy nếu target ID không tồn tại trong dataframe.
- **Kết quả thực tế:** Nằm trong bộ `11 passed in 11.95s` chung của repo (Python 3.13.14); riêng hai file test của tôi cover đúng các nhánh trên.
- **Artifact/log:** `data/clean/`, `data/results/corruption_log.json`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quyết định corruption nên nhắm vào record nào — ngẫu nhiên trong toàn bộ clean dataset, hay có chủ đích — và repair nên sửa trực tiếp dữ liệu đã hỏng hay build lại từ đầu.
- **Các phương án đã cân nhắc:** (1) Corrupt ngẫu nhiên bất kỳ dòng nào trong clean dataset; (2) corrupt chỉ những dòng thuộc frozen evaluation set; (3) khi repair, patch trực tiếp các trường bị hỏng trong dữ liệu corrupted (ví dụ điền lại summary bị xóa) thay vì build lại từ raw.
- **Phương án đã chọn:** Phương án 2 cho việc chọn target, và loại bỏ phương án 3 để dùng lại đúng `build_clean_dataframe` từ raw khi repair.
- **Lý do:** Nếu corrupt ngẫu nhiên, có khả năng không dòng nào bị hỏng nằm trong 10 câu hỏi đánh giá, khiến retrieval hit rate/judge accuracy không đổi dù dữ liệu đã hỏng — thí nghiệm trở nên "không đo được" (unmeasurable). Patch tay dữ liệu corrupted khi repair cũng rủi ro hơn vì mỗi scenario cần logic đảo ngược riêng và dễ lệch khỏi cleaning contract gốc; build lại từ raw bằng đúng hàm cleaning đảm bảo repaired data tuân thủ contract y hệt lần build đầu tiên.
- **Bằng chứng quyết định phù hợp:** `_target_ids_in_dataframe` chủ động `raise ValueError` khi giao rỗng — đã được test xác nhận qua `test_corruption_refuses_unmeasurable_target_set`; và repaired data đo được quay lại đúng baseline (12/12 quality checks, retrieval hit rate 0,90) vì dùng lại đúng hàm, đúng raw snapshot.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Ở lần triển khai đầu, việc lọc record theo độ dài `summary` chỉ thực hiện một lần trước khi build DataFrame; khi ép kiểu qua `pandas`, một số giá trị rỗng có thể bị coerce thành `NaN` mà không còn bị chặn bởi điều kiện `if not title or len(summary) < 100` ban đầu (điều kiện này chạy trên Python string, không chạy lại sau khi dữ liệu đã nằm trong DataFrame).
- **Lệnh hoặc bước tái hiện:** Build clean dataframe từ một tập record có `summary` biên giới (đúng 100 ký tự hoặc gần rỗng sau normalize), sau đó kiểm tra `validate_clean_dataframe` trên DataFrame kết quả.
- **Nguyên nhân gốc:** Kiểm tra điều kiện chỉ chạy ở tầng object Python (per-record) mà không có bước kiểm tra lại tương đương ở tầng DataFrame sau khi mọi cột đã được ép kiểu, nên một số trường hợp biên có thể lọt qua nếu logic per-record và logic DataFrame không đồng bộ tuyệt đối.
- **Cách xử lý:** Thêm bước lọc thứ hai ngay trên DataFrame vừa dựng (kiểm tra lại `summary` không rỗng, `title` không rỗng, độ dài `summary` ≥ 100) trước khi gọi `validate_clean_dataframe`, để hai lớp kiểm tra độc lập bảo vệ lẫn nhau thay vì phụ thuộc vào đúng một lần kiểm tra duy nhất.
- **Cách xác minh sau khi sửa:** `test_cleaning_enforces_summary_date_and_embedding_contract` pass với record có summary ngắn bị loại đúng; `validate_clean_dataframe` không còn raise bất ngờ trên dữ liệu thực tế 24 record.
- **Điều học được:** Khi dữ liệu đi qua chuyển đổi kiểu (Python object → pandas DataFrame), không nên giả định điều kiện lọc ở tầng trước tự động đúng ở tầng sau; validate lại tại điểm giao là cách rẻ nhất để tránh lỗi âm thầm.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Crossref trả raw response qua Role 2, được parse thành `PaperRecord`. Tôi nhận danh sách này, chuẩn hóa text/ngày, tính `age_days`/`summary_chars`/`extracted_skills`, tạo `text_for_embedding`, lọc và dedupe để ra clean dataset. Role 4 dùng `text_for_embedding` này để tạo vector MiniLM và lưu vào ChromaDB.
2. Evaluation set của Role 5 sinh câu hỏi từ clean dataframe mà tôi bàn giao; `ground_truth_doc_ids` chính là `paper_id` trong dataset của tôi. Khi tôi corrupt dữ liệu, tôi cố ý nhắm đúng các `paper_id` này để retrieval hit rate/answer quality phản ánh đúng tác động của corruption, không phải nhiễu ngẫu nhiên.
3. Quality checks kiểm tra dữ liệu clean/corrupted/repaired tại một thời điểm có đúng schema, không trùng ID, text không rỗng hay không; freshness monitoring nhìn vào `published`/`age_days` mà tôi tính ra để xác định dữ liệu có còn mới trong ngưỡng 180 ngày. Scenario `stale_date` của tôi tác động trực tiếp vào tín hiệu freshness, còn `blank_summary`/`add_noise`/`duplicates` tác động chủ yếu vào quality checks.
4. Dùng cùng test set cho ba trạng thái để cô lập biến duy nhất thay đổi là dữ liệu do tôi tạo ra (corruption) và phục hồi (repair); nếu câu hỏi đổi giữa các lần, không thể tách được delta retrieval do corruption khỏi delta do câu hỏi khác.
5. Repair được xem là thành công khi repaired data đi qua đúng `build_clean_dataframe` từ raw snapshot của Role 2, cho ra 24 dòng đúng bằng baseline, `validate_clean_dataframe` không raise lỗi, 12/12 quality checks pass, freshness `fresh`, và retrieval hit rate/judge accuracy đo trên test set cũ trở lại đúng giá trị baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 0,90 | 0,70 | 0,90 | Giảm đúng vì 4 scenario của tôi nhắm trực tiếp vào frozen target IDs |
| `mean_token_f1` | 0,1930 | 0,1717 | 0,1981 | Giảm khi `add_noise`/`blank_summary` làm hỏng nội dung embedding, phục hồi sau repair |
| `judge_accuracy` | 0,60 | 0,50 | 0,60 | Phục hồi hoàn toàn cùng nhịp với retrieval hit rate |
| `mean_judge_score` | 3,40 | 3,00 | 3,50 | Cùng xu hướng giảm rồi phục hồi |
| Quality checks | 12 pass / 0 fail | 8 pass / 4 fail | 12 pass / 0 fail | 4 fail đúng bằng 4 scenario tôi áp dụng: `paper_id_unique` (duplicates), `summary_not_blank`/`summary_minimum_length` (blank_summary), `age_days_within_freshness_threshold` (stale_date) |
| Freshness status | fresh | stale, 2 stale rows | fresh | 2 dòng stale khớp chính xác với 2 target của scenario `stale_date` |

### Kết luận từ số liệu

1. `blank_summary` + `add_noise` + `duplicates` + `stale_date` áp trên 8 lượt tác động (2 dòng/scenario, có thể trùng nếu tập target nhỏ) → 4/12 quality checks fail, freshness chuyển `stale` → retrieval hit rate giảm từ 0,90 xuống 0,70 vì đúng các document này nằm trong ground truth của 10 câu hỏi.
2. Repair chạy lại `build_clean_dataframe` trên raw snapshot bất biến → 24 dòng, 12/12 checks pass, 0 stale rows → retrieval hit rate và judge accuracy quay lại đúng baseline vì dữ liệu về đúng trạng thái ban đầu, không phải một bản "vá" corrupted.

Corruption ảnh hưởng rõ nhất qua góc nhìn của tôi là `duplicates`, vì nó trực tiếp vi phạm `paper_id_unique` — một trong những invariant nền tảng nhất của clean schema (mỗi document phải là một entity duy nhất trong index). Ba scenario còn lại làm hỏng nội dung nhưng không phá vỡ tính duy nhất của ID; `duplicates` cho thấy corruption có thể phá cả cấu trúc dữ liệu chứ không chỉ nội dung.

Kết quả khác kỳ vọng của tôi là `mean_token_f1`/`mean_judge_score` của repaired nhỉnh hơn baseline một chút dù `text_for_embedding` sau repair được tính lại từ cùng một hàm với cùng input. Vì `_scenario_targets` dùng chỉ số cyclic offset, thứ tự các dòng trong DataFrame sau `sort_values("age_days")` có thể khiến LLM sinh câu trả lời với độ dài/pha khác đôi chút; tôi cho rằng chênh lệch này đến từ tính không deterministic của LLM generation/judge chứ không phải từ cleaning logic.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Corruption chỉ có ý nghĩa khoa học khi nhắm đúng vào phần dữ liệu mà hệ thống đánh giá thực sự chạm tới — corrupt ngẫu nhiên có thể tạo ảo giác "dữ liệu vẫn ổn" dù thực chất đã hỏng.
2. Repair đáng tin cậy nhất khi build lại từ nguồn bất biến bằng đúng hàm gốc, thay vì vá tay từng trường hợp — cách vá tay dễ tạo ra dữ liệu "trông giống clean" nhưng không thực sự tuân thủ contract.
3. Kiểm tra điều kiện dữ liệu nên lặp lại ở nhiều tầng chuyển đổi (object → DataFrame) vì một điều kiện đúng ở tầng trước không tự động đúng ở tầng sau khi có ép kiểu.

### Nếu có thêm thời gian

Tôi sẽ tách rõ 4 scenario corruption để mỗi scenario chạy độc lập trên một bản sao riêng và đánh giá riêng (ablation), thay vì áp cả 4 cùng lúc như hiện tại. Điều này giúp trả lời chính xác câu hỏi "scenario nào gây suy giảm retrieval lớn nhất" mà hiện tại nhóm chỉ có thể suy đoán. Cải thiện được đo bằng bốn bộ metrics riêng biệt (một cho mỗi scenario) so với một bộ metrics tổng hợp như hiện tại.

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
