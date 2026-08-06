# BÁO CÁO CÁ NHÂN — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Trương Ngọc Mai |
| MSSV | 2A202601652 |
| Khóa/Lớp | K4 |
| Tên nhóm/dự án | K4-Day10-2A202601050-DangVanNhan |
| Vai trò chính | Role 4 — RAG & agent owner |
| Repository | <https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo.git> |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Embedding MiniLM | `src/retrieval/embeddings.py::MiniLMEmbeddings`, `_load_model` | `text_for_embedding` từ clean DataFrame (Role 3) | Vector embedding chuẩn hóa (`normalize_embeddings=True`) cho document và query | Hoàn thành |
| Chỉ mục ChromaDB | `src/retrieval/index.py::LocalEmbeddingIndex` (`build`, `load`, `search`, `lookup`), `_derive_collection_name` | Clean DataFrame + `Settings` | Ba collection tách biệt `papers-baseline`/`papers-corrupted`/`papers-repaired` và manifest JSON tương ứng | Hoàn thành |
| Semantic search & exact lookup | `LocalEmbeddingIndex.search`, `LocalEmbeddingIndex.lookup` | Câu hỏi tự nhiên hoặc `paper_id`/title | `SearchResult` có `score`, `content`, `metadata`; lookup chính xác không qua semantic | Hoàn thành |
| Agent có tool trace | `src/retrieval/agent.py::build_agent`, `semantic_search_papers`, `lookup_paper`, `run_agent_question` | Câu hỏi + index đã build | Câu trả lời của agent kèm `retrieval_trace` ghi lại đúng document đã dùng | Hoàn thành |
| QA rule-based & LLM dispatch | `src/retrieval/qa.py::answer_question`, `src/retrieval/llm.py::build_llm` | Câu hỏi, index, `Settings` provider/model | `AnswerResult` (đường rule-based, không gọi LLM) và `ChatGoogleGenerativeAI`/provider khác cho đường agent | Hoàn thành |

Phạm vi của tôi bắt đầu khi Role 3 bàn giao `text_for_embedding` và kết thúc khi trả về document/answer có thể truy vết được cho Role 5 đánh giá. Tôi đảm bảo mỗi trạng thái dữ liệu (baseline/corrupted/repaired) có index riêng, độc lập, không lẫn vector giữa các lần rebuild.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Xác nhận đường dẫn manifest ↔ tên collection | Role 1 — Pipeline integrator | Thống nhất `_derive_collection_name` map đúng ba path artifact (`embeddings_json`/`corrupted_embeddings_json`/`repaired_embeddings_json`) sang ba collection cố định |
| Đảm bảo `retrieval_trace` phục vụ evaluation | Role 5 — Evaluation | Trace được caller-owned và reset theo từng câu hỏi, để evaluator biết chính xác document nào agent đã dùng khi tính retrieval hit |
| Kiểm tra `text_for_embedding` sau corruption/repair | Role 3 — Cleaning & corruption | Xác nhận index rebuild đọc đúng giá trị mới nhất của `text_for_embedding`, không dùng cache cũ |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Load MiniLM có cache theo model name | `embeddings.py::_load_model` (`@lru_cache(maxsize=4)`) | Không load lại `SentenceTransformer` mỗi khi tạo `MiniLMEmbeddings` mới | Đọc code, xác nhận decorator `lru_cache` trên hàm module-level |
| Build/rebuild index xóa-rồi-tạo lại đúng collection | `LocalEmbeddingIndex.build` | Mỗi lần build baseline/corrupted/repaired đều là collection sạch, không lẫn vector cũ | So `collection_name` trong `data/embeddings/papers_embeddings.json`, `_corrupted.json`, `_repaired.json` |
| Semantic search trả về score đã chuẩn hóa | `LocalEmbeddingIndex.search` (`max(0.0, 1.0 - distance)`) | Điểm số không âm, phù hợp để hiển thị và ngưỡng lọc | Gọi `search()` thử với vài câu hỏi, kiểm tra `score` trong khoảng `[0, 1]` |
| Exact lookup theo `paper_id`/title, case-insensitive | `LocalEmbeddingIndex.lookup` | Trả đúng document khi agent cần tra chính xác thay vì semantic | Test thủ công `lookup("  Some Title  ")` và `lookup(paper_id.upper())` |
| Agent tool-call trace phục vụ evaluation | `agent.py::semantic_search_papers`, `lookup_paper` | `retrieval_trace` ghi đúng `SearchResult` (kể cả từ lookup, gán `score=1.0`) đã dùng trong câu trả lời | `tests/test_retrieval_agent.py::test_run_agent_question_normalizes_provider_content_blocks` |

Output tiêu biểu của tôi là ba collection ChromaDB tách biệt (`papers-baseline`, `papers-corrupted`, `papers-repaired`), mỗi collection gắn với một file manifest JSON riêng trong `data/embeddings/`. Nhờ tách biệt hoàn toàn thay vì dùng một collection chung có filter theo trạng thái, Role 5 có thể đánh giá ba trạng thái độc lập mà không lo một câu query vô tình lấy nhầm vector từ trạng thái khác.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

RAG cần một tầng chuyển `text_for_embedding` thành vector, lưu trữ có thể truy vấn lại (ChromaDB), và một agent có thể vừa tìm kiếm theo ngữ nghĩa vừa tra cứu chính xác theo ID/tiêu đề. Đồng thời, vì bài lab so sánh ba trạng thái dữ liệu (baseline/corrupted/repaired), index phải đảm bảo không rò rỉ dữ liệu giữa các trạng thái — nếu không, corruption ở một trạng thái có thể vô tình ảnh hưởng đến kết quả đo ở trạng thái khác.

### Cách triển khai

`MiniLMEmbeddings` bọc `SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")` (lấy từ `Settings.embedding_model`) qua interface `Embeddings` của LangChain; `embed_documents`/`embed_query` đều gọi `model.encode(..., normalize_embeddings=True)` nên tương đồng cosine giữa các vector tương đương tích vô hướng, giúp tính điểm số nhất quán. Model được cache qua `@lru_cache(maxsize=4)` ở cấp module để nhiều lần build/rebuild index trong một lần chạy pipeline không phải load lại trọng số nhiều lần.

`LocalEmbeddingIndex.build(df, settings, embeddings_output_path)` là điểm mấu chốt cho việc tách trạng thái: `_derive_collection_name` map đường dẫn manifest output (baseline/corrupted/repaired) sang đúng tên collection cố định qua một `name_map`, sau đó `build` chủ động `client.delete_collection(name=collection_name)` (bọc trong `try/except Exception: pass` để không lỗi nếu collection chưa tồn tại) rồi `create_collection(...)` mới — đảm bảo mỗi lần build là một collection sạch hoàn toàn, không phải upsert lên dữ liệu cũ. Danh sách document được xây bằng `_build_documents(df)` với `record_id = f"{paper_id}::{index}"` để tránh đụng ID ngay cả khi có dòng duplicate (như corruption scenario `duplicates` của Role 3 tạo ra).

`search(query, top_k)` embed câu hỏi rồi gọi `collection.query(...)` của Chroma, chuyển khoảng cách cosine thành điểm bằng `max(0.0, 1.0 - distance)` để tránh điểm âm. `lookup(value)` tra trực tiếp trong hai dict `documents_by_paper_id`/`documents_by_title` đã build sẵn ở `__init__`, cả hai key đều `.strip().lower()` để không phân biệt hoa thường/khoảng trắng thừa.

`build_agent` tạo agent LangChain với hai tool: `semantic_search_papers` gọi `index.search` và ghi kết quả vào `retrieval_trace` (list do caller truyền vào, mutate tại chỗ — chủ đích để Role 5 reset trace theo từng câu hỏi rồi đọc lại chính xác agent đã tra document nào); `lookup_paper` gọi `index.lookup`, nếu tìm thấy cũng ghi vào trace dưới dạng `SearchResult(score=1.0, ...)` để hai đường tra cứu đều để lại cùng một loại bằng chứng cho evaluation. `qa.py::answer_question` là một đường **hoàn toàn không gọi LLM**, dùng regex bắt tiêu đề trong dấu nháy đơn để lookup chính xác, kết hợp semantic search, rồi chọn câu trả lời canned dựa trên từ khóa câu hỏi (`"who authored"`, `"when was"`...) — tách biệt với đường agent dùng `llm.py::build_llm` (Gemini qua `ChatGoogleGenerativeAI` theo `Settings.llm_provider`/`model_name`).

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Clean/corrupted/repaired DataFrame có `text_for_embedding`, `paper_id`, `title`; `Settings.embedding_model`, `collection_name` tương ứng từng trạng thái |
| Output | Ba collection Chroma (`papers-baseline/corrupted/repaired`), manifest JSON (`documents`, `collection_name`, `embedding_model`), `SearchResult`, `AnswerResult`, `retrieval_trace` |
| Module phụ thuộc | `src/ingestion/cleaning.py` (Role 3), `src/core/config.py` (Settings/Paths) |
| Module sử dụng output | `src/evaluation/metrics.py` (Role 5), `src/ui/app.py` (Role 1, trang `/rag`) |
| Điều kiện lỗi cần xử lý | Query rỗng/whitespace-only, DataFrame rỗng khi ingest, collection chưa tồn tại lúc xóa, distance âm/lệch khi convert sang score, content block LLM ở nhiều định dạng (str hoặc list dict) |

### Cách xác minh

```bash
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp tests/test_retrieval_agent.py
uv run python script/run_phase1.py
```

- **Kết quả mong đợi:** `test_run_agent_question_normalizes_provider_content_blocks` pass; sau khi chạy `run_phase1.py`, `data/embeddings/papers_embeddings.json` có `collection_name: "papers-baseline"` và 24 documents khớp clean data.
- **Kết quả thực tế:** Test nằm trong bộ `11 passed in 11.95s` chung của repo; đã đối chiếu trực tiếp `data/embeddings/papers_embeddings.json` và xác nhận 24 documents, `collection_name` đúng như thiết kế.
- **Artifact/log:** `data/embeddings/`, `data/chroma/`; không chứa secret (chỉ chứa vector và metadata công khai từ clean data).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần lưu trữ vector cho ba trạng thái dữ liệu (baseline/corrupted/repaired) sao cho việc đánh giá từng trạng thái không bị lẫn dữ liệu của trạng thái khác, trong khi vẫn phải rebuild nhanh mỗi khi Phase 2 chạy lại.
- **Các phương án đã cân nhắc:** (1) Một collection duy nhất, thêm trường `state` vào metadata rồi lọc bằng `where` mỗi lần query; (2) ba collection tên cố định, xóa-và-tạo-lại hoàn toàn mỗi lần build; (3) ba Chroma client/thư mục persist hoàn toàn tách biệt trên đĩa.
- **Phương án đã chọn:** Phương án 2 — ba collection tên cố định (`papers-baseline`, `papers-corrupted`, `papers-repaired`) trong cùng một Chroma persist directory, xóa-rồi-tạo lại mỗi lần `build`.
- **Lý do:** So với phương án 1, cách này loại bỏ hoàn toàn rủi ro quên `where` filter khi query dẫn đến lẫn dữ liệu giữa các trạng thái — một lỗi khó phát hiện vì kết quả vẫn "trông hợp lý". So với phương án 3, dùng chung một Chroma client/thư mục giúp giảm chi phí quản lý so với việc duy trì ba bộ client/kết nối riêng, trong khi vẫn giữ được sự cô lập ở cấp collection.
- **Bằng chứng quyết định phù hợp:** Ba file manifest (`papers_embeddings.json`, `_corrupted.json`, `_repaired.json`) có `collection_name` khác nhau và số document khớp đúng dòng của từng trạng thái (24/26/24); retrieval hit rate đo trên collection `papers-repaired` phục hồi đúng bằng `papers-baseline` (0,90), chứng tỏ không có vector "rò rỉ" từ collection `papers-corrupted` ảnh hưởng đến kết quả.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi build lại index cho một trạng thái đã từng build trước đó (ví dụ chạy `run_phase1.py` hai lần liên tiếp để debug), lần gọi `client.delete_collection(name=collection_name)` đầu tiên trên một collection **chưa từng tồn tại** (lần build đầu tiên trong toàn bộ vòng đời dự án) sẽ ném lỗi từ ChromaDB vì không tìm thấy collection để xóa.
- **Lệnh hoặc bước tái hiện:** Gọi `LocalEmbeddingIndex.build(...)` trên một Chroma persist directory hoàn toàn mới, chưa từng có collection nào được tạo.
- **Nguyên nhân gốc:** Logic "xóa trước khi tạo" giả định collection luôn tồn tại từ lần chạy trước, nhưng ở lần build đầu tiên của một project mới, collection chưa từng được tạo nên `delete_collection` không có gì để xóa.
- **Cách xử lý:** Bọc lời gọi `delete_collection` trong `try/except Exception: pass`, chấp nhận rằng "xóa một collection không tồn tại" là trạng thái hợp lệ (no-op) chứ không phải lỗi cần lan truyền, rồi luôn tiếp tục `create_collection(...)` ngay sau đó bất kể delete có thành công hay không.
- **Cách xác minh sau khi sửa:** Xóa toàn bộ `data/chroma/` rồi chạy `run_phase1.py` từ đầu — index build thành công ngay lần đầu tiên không cần collection tồn tại trước; chạy lại lần hai trên cùng thư mục cũng không lỗi vì lúc này collection đã tồn tại và bị xóa/tạo lại bình thường.
- **Điều học được:** Với các thao tác "dọn dẹp trước khi khởi tạo lại" (delete-then-create), cần coi trường hợp "không có gì để dọn" là một nhánh hợp lệ ngay từ đầu, đặc biệt khi component đó có thể được gọi ở trạng thái hoàn toàn sạch (fresh environment) chứ không chỉ ở trạng thái đã từng chạy qua.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Crossref → raw records (Role 2) → clean DataFrame với `text_for_embedding` (Role 3) → tôi dùng MiniLM (`all-MiniLM-L6-v2`, chuẩn hóa vector) để mã hóa từng `text_for_embedding` thành vector, lưu vào ChromaDB kèm metadata (`paper_id`, `title`, nội dung cần thiết để truy vết) trong đúng collection ứng với trạng thái dữ liệu hiện tại.
2. Evaluation set của Role 5 chứa `ground_truth_doc_ids` lấy từ `paper_id` thật trong clean data. Khi agent trả lời một câu hỏi, `semantic_search_papers`/`lookup_paper` ghi lại đúng document đã dùng vào `retrieval_trace`; evaluator so các ID trong trace với `ground_truth_doc_ids` để tính retrieval hit rate, và so nội dung câu trả lời với ground truth bằng token F1/LLM judge.
3. Quality checks kiểm tra tính hợp lệ tĩnh của dữ liệu clean (schema, ID trùng, text rỗng...) độc lập với index; freshness monitoring nhìn vào `published`/`age_days`. Cả hai không trực tiếp đọc từ ChromaDB — chúng chạy trên DataFrame trước khi tôi build index, nhưng vì index được build lại từ đúng DataFrame đó sau mỗi lần thay đổi, hai lớp observability này gián tiếp phản ánh đúng những gì đang nằm trong index tại thời điểm evaluate.
4. Dùng cùng test set cho ba trạng thái là điều kiện để phép so sánh có ý nghĩa: vì tôi rebuild index hoàn toàn độc lập cho mỗi trạng thái (ba collection riêng), biến duy nhất thay đổi giữa ba lần đánh giá là nội dung index, không phải câu hỏi hay cách agent tra cứu.
5. Repair được xem là thành công khi collection `papers-repaired` được build lại từ clean data đã repair (Role 3), có đúng 24 document như baseline, và khi Role 5 chạy lại đúng 10 câu hỏi cũ trên collection này, retrieval hit rate/judge accuracy trở lại đúng giá trị đo trên `papers-baseline` — đây là bằng chứng cho thấy index không giữ lại "tàn dư" nào từ collection `papers-corrupted`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 0,90 | 0,70 | 0,90 | Phục hồi hoàn toàn, xác nhận `papers-repaired` không lẫn dữ liệu từ `papers-corrupted` |
| `mean_token_f1` | 0,1930 | 0,1717 | 0,1981 | `add_noise` (Role 3) làm loãng `text_for_embedding`, ảnh hưởng chất lượng context truyền cho LLM, phục hồi sau rebuild |
| `judge_accuracy` | 0,60 | 0,50 | 0,60 | Phục hồi hoàn toàn cùng nhịp retrieval hit rate |
| `mean_judge_score` | 3,40 | 3,00 | 3,50 | Giảm rồi tăng nhẹ hơn baseline, nằm trong biến động LLM |
| Quality checks | 12 pass / 0 fail | 8 pass / 4 fail | 12 pass / 0 fail | Không thuộc phạm vi index trực tiếp nhưng phản ánh đúng input mà tôi mã hóa |
| Freshness status | fresh | stale, 2 stale | fresh | Metadata `published`/`age_days` tôi lưu trong Chroma phản ánh đúng dữ liệu tại thời điểm build |

### Kết luận từ số liệu

1. Corruption (đặc biệt `blank_summary` và `add_noise`) làm hỏng trực tiếp `text_for_embedding` mà tôi dùng để mã hóa vector cho collection `papers-corrupted` → retrieval hit rate giảm từ 0,90 xuống 0,70 vì vector của các document bị hỏng không còn phản ánh đúng nội dung ngữ nghĩa gốc, khiến semantic search khó khớp đúng với câu hỏi ground truth.
2. Repair rebuild collection `papers-repaired` từ clean data đã được Role 3 phục hồi hoàn toàn từ raw → retrieval hit rate và judge accuracy quay lại đúng baseline, chứng minh việc tách ba collection độc lập (quyết định kỹ thuật ở mục 5) hoạt động đúng như thiết kế: không có state nào "rò rỉ" sang state khác.

Corruption ảnh hưởng rõ nhất đến tầng retrieval của tôi là `add_noise`, vì nó chèn hơn 6.300 ký tự boilerplate vào đầu `text_for_embedding` — làm loãng tỉ trọng nội dung thật trong vector so với `blank_summary` (làm ngắn hẳn text) hay `stale_date` (không đổi text). Dù vậy, vì cả 4 scenario được áp cùng lúc trên các target khác nhau, tôi không thể tách riêng đóng góp của `add_noise` vào mức giảm retrieval hit rate chỉ từ số liệu tổng hợp hiện có.

Kết quả khác kỳ vọng của tôi là token F1/judge score của repaired cao hơn nhẹ baseline dù vector được tái tạo từ cùng `text_for_embedding` gốc. Vì embedding và retrieval của tôi là deterministic (MiniLM không có yếu tố ngẫu nhiên khi encode), tôi cho rằng chênh lệch nhỏ này không đến từ tầng retrieval mà từ tính không deterministic của bước sinh câu trả lời/LLM judge phía sau.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Cô lập dữ liệu giữa các trạng thái thí nghiệm (baseline/corrupted/repaired) nên được thiết kế ở cấp hạ tầng lưu trữ (collection riêng) chứ không chỉ dựa vào kỷ luật lập trình (nhớ thêm filter) — cách này loại bỏ cả một lớp lỗi tiềm ẩn.
2. Retrieval trace phải là first-class citizen của agent, không phải thứ suy luận ngược từ log — việc để evaluator ghi trực tiếp vào `retrieval_trace` khi tool được gọi giúp phép đo retrieval hit rate chính xác tuyệt đối với những gì agent thực sự dùng.
3. Chất lượng embedding phụ thuộc hoàn toàn vào chất lượng `text_for_embedding` đầu vào — corruption ở tầng cleaning (Role 3) luôn thể hiện rõ ở tầng retrieval của tôi, hai tầng này không thể tách rời khi phân tích nguyên nhân suy giảm chất lượng.

### Nếu có thêm thời gian

Tôi sẽ thêm unit test trực tiếp cho `embeddings.py`, `index.py` và `qa.py` (hiện chỉ có một test cho `agent.py::run_agent_question`, chưa có test cho `LocalEmbeddingIndex`, `MiniLMEmbeddings` hay `answer_question`), đặc biệt test case collection chưa tồn tại khi delete, và test `add_noise` scenario có làm giảm điểm semantic search một cách đo được (so sánh score trước/sau corruption trên cùng document) để định lượng chính xác mức ảnh hưởng của từng loại corruption lên tầng retrieval.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Trương Ngọc Mai

**MSSV:** 2A202601652

**Ngày xác nhận:** 2026-08-06
