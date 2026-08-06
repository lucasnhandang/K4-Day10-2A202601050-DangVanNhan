# CP0 handoff — Thành viên A (Pipeline Integrator)

## Mục tiêu chung

Hoàn thành baseline trên dữ liệu sạch trước, sau đó mới chạy corruption, repair và so sánh. Mọi kết luận phải truy được về artifact trong `data/`; không dùng kết quả hoặc metric tự tạo.

## Quy ước làm việc đã chốt cho CP0

| Nội dung | Quy ước |
| --- | --- |
| Nhánh hiện tại | `main`; trước khi sửa song song, mỗi owner tạo nhánh riêng và chỉ tích hợp sau khi Nhân review contract + artifact. |
| Nguồn baseline | Một raw snapshot Crossref cố định. Không refresh source giữa baseline, corruption và repair. |
| Định danh tài liệu | `paper_id` là DOI Crossref đã `strip().lower()`. DOI rỗng/không hợp lệ bị loại và phải có count/log. Không dùng title hoặc thứ tự dòng làm ID. |
| Lineage | Cùng `paper_id` phải xuất hiện trong raw records, cleaned data, Chroma metadata và `ground_truth_doc_ids`. |
| Tách trạng thái | Baseline, corrupted và repaired dùng file/collection riêng; corruption không được ghi đè baseline. |
| Secret | `.env` chỉ lưu cục bộ, đã bị Git ignore; không ghi API key vào code, artifact, report hoặc log. |

## Ownership và handoff

| Owner | Phạm vi | Nhận từ | Bàn giao / tiêu chí nhận |
| --- | --- | --- | --- |
| Nhân — Integrator | `src/core/`, `src/pipelines/`, release | Contract của cả nhóm | Hai entrypoint chạy theo thứ tự và chỉ báo hoàn tất khi artifact/report khớp nhau. |
| Thịnh — Ingestion | `src/ingestion/crossref.py` | Settings | `data/raw/crossref_response.json`, `crossref_records.json`; `PaperRecord.paper_id` ổn định. |
| Phụng — Cleaning & corruption | `cleaning.py`, `corruption.py` | Raw records | Clean CSV/JSON có `paper_id`, `title`, `summary`, `published`, `age_days`, `text_for_embedding`; corruption log có ID và before/after. |
| Mai — RAG & agent | `src/retrieval/` | Clean dataframe | Embedding manifest và các collection `papers-baseline`, `papers-corrupted`, `papers-repaired`; search/lookup có nguồn. |
| Hậu — Evaluation & observability | `src/evaluation/`, `src/observability/` | Clean dataframe, index | Test set cố định, answers/metrics, quality/freshness JSON và hai report Markdown. |

## Luồng artifact và điều kiện handoff

```text
Crossref API
  -> data/raw/crossref_response.json
  -> data/raw/crossref_records.json
  -> data/clean/papers_clean.{csv,json}
  -> data/embeddings/papers_embeddings.json + data/chroma/ (papers-baseline)
  -> data/eval/test_set.json
  -> data/results/baseline_{answers,metrics}.json
  -> data/quality/* + data/reports/phase1_report.md
  -> corrupted/repaired artifacts cùng test_set.json
  -> data/reports/corruption_report.md
```

1. B lưu raw response **trước** parse; B bàn giao raw records và một sample lineage.
2. C làm sạch, dedupe theo `paper_id`, ghi count/lý do bị loại; C khóa clean schema.
3. D và E chỉ bắt đầu build index/test set sau khi C xác nhận schema. E lấy `ground_truth_doc_ids` từ `paper_id` đã khóa.
4. A ghép `phase1.py`: raw → clean → index → test set → evaluate → quality/freshness → report.
5. Chỉ sau khi baseline artifacts tồn tại, C/D/E/A thực hiện corrupt → rebuild → evaluate cùng test set → repair từ raw snapshot → compare.

## Kiểm tra setup của A (CP0)

- `uv 0.11.1` có sẵn và `uv run --no-sync python --version` chọn Python `3.12.13`, phù hợp yêu cầu project `>=3.11,<3.14`.
- `python3` hệ thống là `3.9.6`, không phù hợp: dùng `uv run ...` (hoặc `.venv` tạo bởi `uv sync`), không chạy trực tiếp `python3 script/...`.
- `.env` tồn tại và bị Git ignore. Các biến API key phổ biến hiện rỗng; trước checkpoint gọi LLM cần cấu hình credential tương ứng với provider, hoặc chuẩn bị Ollama nếu dùng provider cục bộ.
- Thư mục artifact đã có `.gitkeep`, chưa có output pipeline. `main` là nhánh duy nhất hiện thấy.

## Việc tiếp theo của A

1. Sau khi bàn giao contract/schema đầu tiên, implement `src/pipelines/phase1.py` theo thứ tự ở trên.
2. Không chạy corruption flow trước khi `data/results/baseline_metrics.json`, answers, quality/freshness và `phase1_report.md` cùng tồn tại.
3. Ghi traceback cùng artifact thiếu khi entrypoint fail; không hard-code trạng thái pass hay metric.
