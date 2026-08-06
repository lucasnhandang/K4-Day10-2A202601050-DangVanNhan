# BÁO CÁO CÁ NHÂN — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Bùi Công Hậu |
| MSSV | 2A202601877 |
| Khóa/Lớp | K4 |
| Tên nhóm/dự án | K4-Day10-2A202601050-DangVanNhan |
| Vai trò chính | Role 5 — Evaluation & Observability |
| Repository | <https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo.git> |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data quality checks | `src/observability/quality.py::run_data_quality_checks` | Clean/corrupted/repaired DataFrame và `Settings` | Quality JSON chứa 12 checks, pass/fail và observed value | Hoàn thành |
| Freshness monitoring | `src/observability/quality.py::build_freshness_report` | `published`, `age_days`, ngưỡng 180 ngày | Freshness JSON: latest/oldest, stale rows, `fresh/stale/unknown` | Hoàn thành |
| Kiểm thử observability | `tests/test_observability_quality.py` | DataFrame in-memory và temporary paths | 6 test cases cho clean, corrupted, thiếu schema, stale/invalid/empty data | Hoàn thành |
| Evaluation test set | `src/evaluation/testset.py`, `data/eval/test_set.json` | Clean DataFrame có stable `paper_id` | Frozen test set 10 câu và ground-truth document IDs | Hoàn thành |
| Evaluation metrics | `src/evaluation/metrics.py`, `data/results/*_metrics.json` | Frozen test set, RAG index/agent | Retrieval hit, token F1, judge accuracy/score và answers chi tiết | Hoàn thành |
| Báo cáo bằng chứng | `data/quality/`, `data/reports/` | Metrics, quality và freshness artifacts | Baseline report và corruption/repair comparison report | Hoàn thành |

Phạm vi của tôi bắt đầu khi Role 3 bàn giao clean schema và Role 4 bàn giao index. Output evaluation/observability được Role 1 sử dụng để quyết định pipeline đã hoàn thành và sinh báo cáo tổng hợp.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Chốt CP0 contract và artifact paths | Role 1 — Pipeline integrator | Thống nhất frozen test set, stable `paper_id`, ba trạng thái không ghi đè nhau |
| Kiểm tra clean schema trước evaluation | Role 3 — Cleaning | Xác nhận cần `paper_id`, title, summary, authors, categories, published và age/text fields |
| Kiểm tra lineage test set/index | Role 4 — RAG | `ground_truth_doc_ids` lấy từ clean `paper_id`, không tạo ID giả |
| Viết báo cáo nhóm | Cả nhóm | Hoàn thiện `report/group_report.md` từ artifact và số liệu thực tế |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây dựng 12 quality gates | `run_data_quality_checks` | Baseline/repaired pass 12/12; corrupted fail đúng 4 checks | Đọc `data/quality/*_quality.json` |
| Xây dựng freshness report | `build_freshness_report` | Baseline/repaired `fresh`; corrupted `stale` với 2 dòng stale | Đọc `data/quality/*freshness*.json` |
| Kiểm thử trường hợp lỗi | `tests/test_observability_quality.py` | 6 test bao phủ clean, corrupted, missing columns, stale, invalid và empty | Chạy pytest |
| Bảo đảm test set không có ground truth rỗng/NaN | `src/evaluation/testset.py`, `tests/test_evaluation_testset.py` | Chỉ sinh question type có dữ liệu; JSON đọc được an toàn | Test `test_skips_question_types_with_blank_ground_truth` |
| Đóng băng evaluation set | `data/eval/test_set.json` | 10 câu thuộc `summary`, `authors`, `date`, dùng chung ba trạng thái | So question ID trong ba answer files |
| Đối chiếu tác động corruption/repair | `data/results/*_metrics.json`, `data/reports/corruption_report.md` | Retrieval hit 0,90 → 0,70 → 0,90; quality 12/12 → 8/12 → 12/12 | So sánh ba metrics/quality JSON |

Output tiêu biểu của tôi là `data/quality/corrupted_quality.json`. Artifact này không chỉ ghi `FAIL` mà còn chỉ ra chính xác bốn check lỗi: `paper_id_unique`, `summary_not_blank`, `summary_minimum_length` và `age_days_within_freshness_threshold`, kèm observed value bằng 2 cho từng lỗi. Nhờ đó có thể nối corruption log với suy giảm retrieval thay vì chỉ dựa vào cảm nhận từ câu trả lời của agent.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline báo “chạy xong” chưa đủ để chứng minh dữ liệu phù hợp cho RAG. Cần một lớp observability phát hiện schema thiếu, ID trùng, text rỗng, ngày sai hoặc dữ liệu stale; đồng thời cần evaluation contract để đo cùng một mục tiêu trước và sau corruption/repair. Nếu ground truth rỗng, chứa NaN hoặc dùng document ID không có trong index, metric sẽ không còn đáng tin cậy.

### Cách triển khai

Trong `run_data_quality_checks`, tôi chuẩn hóa mỗi check về một cấu trúc chung gồm `name`, `success`, `observed_value`, `expected` và `message`. Hàm kiểm tra required columns trước, sau đó mới thực hiện các phép tính phụ thuộc cột. Nếu thiếu schema, report vẫn được ghi với trạng thái fail thay vì làm pipeline crash giữa chừng. Các check chính gồm:

- Tối thiểu 3 dòng và đủ required columns.
- `paper_id` không rỗng, không trùng.
- `title`, `summary`, `text_for_embedding` không rỗng.
- Summary dài ít nhất 50 ký tự và `summary_chars` nhất quán.
- `published` parse được, `age_days` là số không âm và không vượt 180 ngày.

`build_freshness_report` parse cả `published` và `age_days`, đếm dòng stale/invalid, tìm ngày mới nhất/cũ nhất và trả một trong ba trạng thái: `fresh`, `stale`, `unknown`. DataFrame rỗng hoặc không đủ dữ liệu thời gian không được báo nhầm là fresh.

Đối với test set, câu hỏi chỉ được tạo khi ground truth tương ứng là text thật, không phải blank hoặc NaN. Mỗi item có `id`, `question_type`, `question`, `ground_truth` và `ground_truth_doc_ids`. Test set sau khi tạo được khóa để tái sử dụng cho baseline, corrupted và repaired.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Clean DataFrame với `paper_id`, `title`, `summary`, `published`, `age_days`, `summary_chars`, `text_for_embedding`; authors/categories khi có |
| Output | `data/eval/test_set.json`, `data/results/*`, `data/quality/*`, `data/reports/*` |
| Module phụ thuộc | `src/ingestion/cleaning.py`, `src/retrieval/index.py`, `src/retrieval/agent.py`, `src/core/config.py` |
| Module sử dụng output | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `src/observability/reporting.py` |
| Điều kiện lỗi cần xử lý | DataFrame rỗng, thiếu cột, blank/NaN ground truth, duplicate ID, invalid date/age, LLM judge không khả dụng |

### Cách xác minh

```bash
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp
```

- **Kết quả mong đợi:** Toàn bộ unit tests pass; corrupted fixture bị phát hiện đúng; empty/invalid data không làm crash report.
- **Kết quả thực tế:** `11 passed in 11.95s` trên Python 3.13.14.
- **Artifact/log:** `data/quality/`, `data/results/`, `data/reports/`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần so sánh agent trên baseline, corrupted và repaired. Nếu mỗi trạng thái tự sinh test set, thay đổi metric có thể do câu hỏi khác chứ không phải do dữ liệu.
- **Các phương án đã cân nhắc:** (1) Sinh lại test set cho từng trạng thái; (2) tạo thủ công một JSON riêng cho từng lần; (3) sinh một test set từ clean baseline, kiểm tra lineage rồi đóng băng và dùng lại.
- **Phương án đã chọn:** Phương án 3 — dùng một frozen test set tại `data/eval/test_set.json` cho cả ba trạng thái.
- **Lý do:** Giữ biến kiểm soát cố định, bảo đảm reproducibility và cho phép quy delta retrieval/answer metric về corruption/repair. `ground_truth_doc_ids` luôn đến từ stable `paper_id`, không sửa tay ID.
- **Bằng chứng quyết định phù hợp:** Cả ba answer files có 10 mẫu cùng question IDs; retrieval hit rate thay đổi 0,90 → 0,70 → 0,90 đồng thời với quality/freshness xấu đi rồi phục hồi.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi:** `test_set.json` có nguy cơ chứa question type với ground truth rỗng/NaN, đặc biệt trường `categories`; JSON có thể đọc được theo Python nhưng không an toàn cho strict JSON/evaluation và làm metric sai ý nghĩa.
- **Bước tái hiện:** Sinh test set từ clean DataFrame có `categories` trống/NaN, sau đó đọc các item và kiểm tra `ground_truth` theo từng question type.
- **Nguyên nhân gốc:** Giá trị `pandas.NaN` không được xử lý như text rỗng ở bước chọn question generator; việc sửa JSON bằng tay cũng dễ làm lệch lineage với clean data.
- **Cách xử lý:** Thêm kiểm tra non-blank text, chỉ chọn generator đủ ground truth, thêm unit test cho DataFrame có blank/NaN và tái sinh artifact từ `papers_clean.json` thay vì chỉnh JSON thủ công.
- **Cách xác minh sau khi sửa:** `test_skips_question_types_with_blank_ground_truth` pass; test set hiện có 10 câu thuộc `summary`, `authors`, `date`, không có item categories rỗng.
- **Điều học được:** Valid JSON chưa đồng nghĩa với evaluation data hợp lệ. Phải kiểm tra semantic contract của từng field và lineage đến document nguồn.

## 7. Hiểu biết về luồng end-to-end

1. Crossref trả raw response; Role 2 lưu snapshot và parse thành `PaperRecord`. Role 3 normalize/dedupe theo DOI-derived `paper_id`, tính age và tạo `text_for_embedding`. Role 4 dùng MiniLM tạo vector rồi lưu document/metadata vào ChromaDB.
2. Evaluation set tạo câu hỏi từ clean data và giữ `ground_truth_doc_ids`. Khi agent trả lời, evaluator lấy các document ID trong retrieval trace; nếu một ground-truth ID có trong top-k thì đó là retrieval hit. Câu trả lời được so với ground truth bằng token F1 và LLM judge.
3. Quality checks kiểm tra dữ liệu có đúng contract hay không: schema, null, unique, độ dài và validity. Freshness monitoring tập trung vào thời gian: ngày mới nhất/cũ nhất, tuổi dữ liệu, số dòng stale và trạng thái fresh/stale/unknown.
4. Phải dùng cùng test set để chỉ thay đổi biến dữ liệu/index. Nếu đổi câu hỏi hoặc ground truth giữa ba trạng thái thì metric không thể so sánh công bằng.
5. Repair thành công khi repaired data được tạo lại từ raw snapshot, row count/schema/quality/freshness phục hồi và agent metrics được đo lại bằng test set cũ. Trong bài này repaired có 24 dòng, 12/12 quality checks pass, freshness `fresh`, retrieval hit 0,90 và judge accuracy 0,60.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 0,90 | 0,70 | 0,90 | Corruption làm mất 20 điểm %, repair phục hồi hoàn toàn |
| `mean_token_f1` | 0,1930 | 0,1717 | 0,1981 | Giảm 0,0213 rồi phục hồi cao hơn baseline 0,0050 |
| `judge_accuracy` | 0,60 | 0,50 | 0,60 | Giảm 10 điểm % rồi phục hồi hoàn toàn |
| `mean_judge_score` | 3,40 | 3,00 | 3,50 | Giảm 0,40 rồi tăng lại 0,50 |
| Quality checks | 12 pass / 0 fail | 8 pass / 4 fail | 12 pass / 0 fail | Bốn lỗi có thể truy về corruption log |
| Freshness status | fresh, 0 stale | stale, 2 stale | fresh, 0 stale | Stale-date scenario được phát hiện và phục hồi đúng |

### Kết luận từ số liệu

1. Blank summary + duplicate + stale date + embedding noise → bốn quality checks fail và freshness chuyển sang `stale` → retrieval hit rate giảm từ 0,90 xuống 0,70, judge accuracy giảm từ 0,60 xuống 0,50.
2. Re-clean từ raw snapshot + rebuild repaired index → quality về 12/12, stale rows về 0 → retrieval hit và judge accuracy trở lại đúng baseline.

Corruption ảnh hưởng rõ nhất về observability là `stale_date`, vì nó tạo signal trực tiếp: hai dòng có ngày `2000-01-01`, `age_days=9714`, làm freshness đổi từ `fresh` sang `stale`. Xét agent metric, không thể quy toàn bộ mức giảm cho riêng một scenario vì bốn corruption được áp dụng cùng lúc; muốn kết luận scenario nào gây suy giảm retrieval lớn nhất cần chạy ablation từng loại độc lập.

Kết quả khác kỳ vọng là mean token F1 repaired 0,1981 và judge score 3,50 cao hơn nhẹ baseline 0,1930 và 3,40, dù dữ liệu đã phục hồi gần như cùng trạng thái. Tôi không xem đây là bằng chứng repair làm mô hình tốt hơn; khả năng cao đến từ tính không deterministic của LLM generation/judge. Cách kiểm tra tiếp là cố định temperature/seed nếu provider hỗ trợ và chạy nhiều lần để tính trung bình, độ lệch chuẩn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Contract giữa raw, clean, index và evaluation quan trọng hơn việc mỗi module chạy riêng lẻ; stable `paper_id` là khóa nối lineage toàn pipeline.
2. Observability tốt phải trả về observed value, expected value và artifact, không chỉ một cờ pass/fail. Các trường hợp thiếu schema/empty data cũng phải cho kết quả rõ ràng thay vì crash hoặc báo fresh giả.
3. Chất lượng dữ liệu ảnh hưởng trực tiếp đến retrieval và answer quality. Duplicate, stale metadata, blank summary và noise có thể làm index vẫn build được nhưng agent kém đi, nên cần đo cả data signals lẫn agent metrics.

### Nếu có thêm thời gian

Tôi sẽ mở rộng test set theo stratified sampling để mỗi question type có đủ mẫu, đặc biệt `categories`, đồng thời version/hash test set. Sau đó chạy ablation từng corruption và lặp evaluation nhiều lần. Cải thiện được đo bằng coverage từng question type, độ ổn định metric qua nhiều run và mức delta riêng của từng corruption.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Bùi Công Hậu

**MSSV:** 2A202601877

**Ngày xác nhận:** 2026-08-06
