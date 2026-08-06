# BÁO CÁO CÁ NHÂN — DAY 10: DATA PIPELINE & DATA OBSERVABILITY

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Trương Ngọc Mai |
| MSSV | 2A202601652 |
| Khóa/Lớp | K4 |
| Tên nhóm | Quái Kiệt Mộng Mơ |
| Vai trò chính | RAG & Agent Owner |
| Repository | https://github.com/lucasnhandang/K4-Day10-QuaiKietMongMo |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Embedding wrapper | `src/retrieval/embeddings.py` — `MiniLMEmbeddings` class | Text list, model name `sentence-transformers/all-MiniLM-L6-v2` | 384-dimensional normalized embedding vectors qua `embed_documents()` và `embed_query()` | Hoàn thành |
| Vector store (ChromaDB) | `src/retrieval/index.py` — `VectorStore` class | Clean DataFrame với `text_for_embedding` column | ChromaDB persistent collection với HNSW cosine index; ingestion, query, get_relevant_context | Hoàn thành |
| Local embedding index | `src/retrieval/index.py` — `LocalEmbeddingIndex` class | Clean DataFrame, Settings, embeddings output path | ChromaDB collection + JSON manifest; semantic search, exact lookup theo `paper_id`/title | Hoàn thành |
| Multi-provider LLM factory | `src/retrieval/llm.py` — `build_llm()` | Settings với `LLM_PROVIDER` | LLM instance (ChatGoogleGenerativeAI, ChatOpenAI, ChatAnthropic, ChatOllama) với temperature configurable | Hoàn thành |
| RAG agent với tool trace | `src/retrieval/agent.py` — `build_agent()`, `run_agent_question()` | Settings, LocalEmbeddingIndex, retrieval_trace list | LangChain agent với 2 tools: `semantic_search_papers`, `lookup_paper`; normalized plain text answer | Hoàn thành |
| QA fallback không LLM | `src/retrieval/qa.py` — `answer_question()` | Question string, Settings, LocalEmbeddingIndex | `AnswerResult` với answer, retrieved_doc_ids, contexts, titles; keyword-based routing | Hoàn thành |
| Embedding manifests | `data/embeddings/` | Embedding JSON output paths | `papers_embeddings.json`, `papers_embeddings_corrupted.json`, `papers_embeddings_repaired.json` | Hoàn thành |
| ChromaDB persistent storage | `data/chroma/` | HNSW index từ LocalEmbeddingIndex.build() | 3 collections: `papers-baseline`, `papers-corrupted`, `papers-repaired` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Xác nhận contract CP0 và artifact paths | Nhân (Pipeline Integrator) | Thống nhất 3 collection name tách biệt, frozen test set dùng chung, paper_id ổn định |
| Cung cấp embedding index cho evaluation | Hậu (Evaluation & Observability) | Hậu dùng `LocalEmbeddingIndex` từ module của tôi để chạy `evaluate_pipeline()` với retrieval hit, token F1 và judge |
| Rebuild index cho corrupted/repaired | Hậu (Evaluation & Observability) | Đã cung cấp `LocalEmbeddingIndex.build()` với `embeddings_output_path` khác nhau để tạo 3 collection riêng biệt |
| Hỗ trợ corruption flow rebuild | Phụng (Cleaning & Corruption Owner) | `corruption_flow.py` gọi `LocalEmbeddingIndex.build()` với corrupted/repaired DataFrame để rebuild index mới |
| Xác nhận schema cho agent tools | Hậu (Evaluation & Observability) | `retrieval_trace` ghi chính xác tool_name, tool_input, tool_output để evaluation tính retrieval hit |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây dựng MiniLM embedding wrapper | `src/retrieval/embeddings.py` — `MiniLMEmbeddings` | 384-dimensional normalized vectors, lru_cache tối đa 4 models, LangChain `Embeddings` subclass | Đọc source code; kiểm tra `embed_documents()` trả về `list[list[float]]` với dim=384 |
| Xây dựng LocalEmbeddingIndex.build() | `src/retrieval/index.py` — `LocalEmbeddingIndex.build()` | ChromaDB collection mới với HNSW cosine, JSON manifest chứa documents/metadata | Kiểm tra `data/chroma/` có 3 thư mục collection; `data/embeddings/` có 3 manifest JSON |
| Xây dựng VectorStore với ingest/query | `src/retrieval/index.py` — `VectorStore` class | `ingest()` upsert DataFrame vào ChromaDB, `query()` trả về top-k với score = 1 - distance | Đọc source code, kiểm tra `get_relevant_context()` format context string đúng |
| Xây dựng multi-provider LLM factory | `src/retrieval/llm.py` — `build_llm()` | 6 providers: gemini, openai, anthropic, openrouter, ollama, custom; temperature=0.0 mặc định | Đọc source code; `normalized_provider()` và `require_llm_credentials()` validate provider |
| Xây dựng RAG agent với 2 tools | `src/retrieval/agent.py` — `build_agent()` | `semantic_search_papers` (top_k=4), `lookup_paper` (exact match); `retrieval_trace` list cho evaluation | Kiểm tra `run_agent_question()` normalize content blocks về plain text |
| Xây dựng QA fallback không LLM | `src/retrieval/qa.py` — `answer_question()` | Keyword-based routing: authors, date, categories, summary; exact lookup + semantic search | Đọc source code, kiểm tra `_extract_answer()` trả về đúng field theo question type |
| Rebuild index baseline/corrupted/repaired | `data/chroma/`, `data/embeddings/` | 3 collections tách biệt, 3 manifest JSON, mỗi collection dùng `embeddings_output_path` riêng | Kiểm tra collection name: `papers-baseline`, `papers-corrupted`, `papers-repaired` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`data/embeddings/papers_embeddings.json` là embedding manifest chứa cấu trúc `{backend, embedding_model, persist_path, collection_name, documents}`. Mỗi document trong `documents` array chứa `record_id`, `paper_id`, `title`, `content`, và `metadata` với các trường cần thiết để truy vết. Manifest này đảm bảo có thể tái index mỗi khi cần mà không phải chạy lại embedding model.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần một lớp retrieval chất lượng cao để kết nối clean DataFrame với LLM agent. Thách thức chính là: (1) tạo embedding chuẩn hóa từ `text_for_embedding` với model nhẹ nhưng hiệu quả (MiniLM, 384-dim), (2) lưu và truy vấn vector theo cosine similarity với ChromaDB HNSW, (3) cung cấp tool cho agent để semantic search và exact lookup, và (4) đảm bảo mỗi trạng thái (baseline/corrupted/repaired) có collection riêng để so sánh chính xác. Nếu không tách collection, so sánh baseline và corrupted sẽ bị sai lineage vì cùng một vector store.

### Cách triển khai

**`MiniLMEmbeddings`** (`embeddings.py`): Wrap `sentence-transformers/all-MiniLM-L6-v2` thành LangChain `Embeddings` subclass. Sử dụng `lru_cache(maxsize=4)` để tránh reload model nhiều lần. `embed_documents()` và `embed_query()` cả hai đều normalize embeddings, cho phép cosine similarity hoạt động với Hamming distance trong ChromaDB.

**`LocalEmbeddingIndex`** (`index.py`): Là class chính của RAG layer. `build()` class method thực hiện toàn bộ: (a) `_derive_collection_name()` map `embeddings_output_path` đến collection name đúng (embeddings_json -> papers-baseline, corrupted -> papers-corrupted, repaired -> papers-repaired); (b) `_build_documents()` chuyển DataFrame thành list dict với `record_id = paper_id::index`, `content = text_for_embedding`, và `metadata` chứa paper_id, title, published, authors_joined, categories_joined, summary, abs_url, pdf_url; (c) Tính embedding bằng MiniLM; (d) `client.create_collection()` với HNSW cosine; (e) `collection.add()` với ids, embeddings, documents, metadatas; (f) `write_json()` manifest. `search()` convert ChromaDB distance thành score = max(0, 1 - distance). `lookup()` tìm kiếm exact theo paper_id hoặc title (case-insensitive).

**`VectorStore`** (`index.py`): Wrapper chuẩn hơn cho usage thông thường. `ingest()` upsert (không phải add), cho phép rebuild không bị duplicate. `get_relevant_context()` format top-k hits thành numbered reference blocks với title, authors, score và content. `reset()` delete và tạo lại collection.

**`build_agent()`** (`agent.py`): Tạo LangChain agent với 2 tools. `semantic_search_papers` gọi `index.search()` với `top_k=4` mặc định, ghi kết quả vào `retrieval_trace`. `lookup_paper` gọi `index.lookup()` với paper_id hoặc title. `retrieval_trace` là list caller-owned, cho phép evaluation reset và ghi đúng documents agent đã sử dụng. `run_agent_question()` invoke agent và normalize content blocks (string, list of strings/dicts/objects) về plain text.

**`build_llm()`** (`llm.py`): Multi-provider factory. `normalized_provider()` fix common typos (ví dụ: "anthorpic" -> "anthropic"). `require_llm_credentials()` validate API key trước khi tạo LLM. Hỗ trợ: gemini (ChatGoogleGenerativeAI), openai (ChatOpenAI), anthropic (ChatAnthropic), openrouter (ChatOpenAI với custom base_url), ollama (ChatOllama), custom (ChatOpenAI với custom base_url).

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Clean DataFrame với `paper_id`, `title`, `text_for_embedding`, `authors_joined`, `categories_joined`, `published`, `age_days`, `summary`, `abs_url`, `pdf_url` |
| Output | `data/embeddings/*.json` (manifest), `data/chroma/` (persistent HNSW index), `AnswerResult` (QA), plain text answer (agent) |
| Module phụ thuộc | `core.config.Settings` (embedding_model, collection names, paths, top_k, LLM config), `core.utils` (read_json, write_json, safe_slug, first_sentence) |
| Module sử dụng output | `src/evaluation/metrics.py` (evaluate_pipeline dùng LocalEmbeddingIndex), `src/pipelines/phase1.py` (gọi LocalEmbeddingIndex.build), `src/pipelines/corruption_flow.py` (gọi LocalEmbeddingIndex.build cho corrupted/repaired) |
| Điều kiện lỗi cần xử lý | DataFrame empty (trả về 0 documents), ChromaDB collection không tồn tại (get_or_create), LLM provider không hỗ trợ (RuntimeError), API key thiếu (RuntimeError), query rỗng (trả về empty list) |

### Cách xác minh

```bash
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp
```

- **Kết quả mong đợi:** Tất cả unit tests pass, embedding dimensions đúng, ChromaDB collections tạo đúng tên.
- **Kết quả thực tế:** `11 passed in 11.95s` trên Python 3.13.14.
- **Artifact/log:** `data/embeddings/`, `data/chroma/`, `data/results/` chứa embedding manifests và answer files; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quyết định cách tách embedding index giữa baseline, corrupted và repaired để so sánh chính xác. Nếu dùng cùng một Chroma collection và chỉ upsert, corrupted và repaired sẽ overwrite baseline, không thể đo delta metrics cho từng trạng thái.
- **Các phương án đã cân nhắc:**
  - Phương án 1: Dùng một collection duy nhất, upsert lại mỗi khi thay đổi dữ liệu. Đơn giản nhưng không thể so sánh.
  - Phương án 2: Tách 3 collection riêng biệt với tên định nghĩa trong Settings, mỗi trạng thái build collection mới với `embeddings_output_path` khác.
  - Phương án 3: Tách 3 collection bằng cách append suffix vào tên (ví dụ: papers-baseline-v1). Phức tạp, dễ bị confusion.
- **Phương án đã chọn:** Phương án 2 — tách 3 collection riêng biệt: `papers-baseline`, `papers-corrupted`, `papers-repaired`.
- **Lý do:** `_derive_collection_name()` trong `LocalEmbeddingIndex` map trực tiếp `embeddings_output_path` đến collection name từ `Settings`. Mỗi collection là một HNSW index độc lập, có thể rebuild không ảnh hưởng collection khác. Đảm bảo corruption flow có thể tạo corrupted collection, repair flow tạo repaired collection, và evaluation chạy riêng trên mỗi collection. Trade-off: dùng nhiều storage hơn nhưng đảm bảo reproducibility và lineage.
- **Bằng chứng quyết định phù hợp:** `corruption_flow.py` gọi `_evaluate()` với `embeddings_path` khác nhau (corrupted_embeddings_json, repaired_embeddings_json), mỗi lần gọi `LocalEmbeddingIndex.build()` tạo collection mới. 3 answer files (`baseline_answers.json`, `corrupted_answers.json`, `repaired_answers.json`) có cùng question IDs nhưng retrieval results khác nhau, xác nhận index tách biệt hoạt động đúng.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi chạy `corruption_flow.py`, corrupted index thay thế baseline collection thay vì tạo collection mới. Kết quả evaluation corrupted trả về retrieval metrics giống baseline (retrieval_hit_rate=0,90) vì dùng cùng vector data — không phản ánh tác động thực của corruption. Baseline answers bị ghi đè.
- **Lệnh hoặc bước tái hiện:** Chạy `python script/run_corruption_flow.py` trên repository đã có baseline artifacts → kiểm tra `data/chroma/` chỉ thấy 1 collection thay vì 3; `baseline_answers.json` bị thay đổi nội dung.
- **Nguyên nhân gốc:** `_derive_collection_name()` trong `src/retrieval/index.py` có logic fallback: khi `embeddings_output_path` là `None` hoặc path không khớp `name_map` keys (`embeddings_json`, `corrupted_embeddings_json`, `repaired_embeddings_json`), nó trả về `settings.baseline_collection_name` mặc định. Trongcorrupted flow, `LocalEmbeddingIndex.build()` được gọi với `embeddings_output_path = paths.corrupted_embeddings_json`, nhưng nếu path resolve không khớp name_map thì fallback về `safe_slug(stem)`, có thể trả về tên collection trùng baseline.
- **Cách xử lý:** (a) Đảm bảo `Settings.paths.corrupted_embeddings_json` resolve đúng đến `data/embeddings/papers_embeddings_corrupted.json` và `paths.repaired_embeddings_json` resolve đúng đến `data/embeddings/papers_embeddings_repaired.json`, both match name_map keys. (b) `_derive_collection_name()` map: `embeddings_json` → `papers-baseline`, `corrupted_embeddings_json` → `papers-corrupted`, `repaired_embeddings_json` → `papers-repaired`. (c) Nếu path bị thay đổi sai, fallback dùng `safe_slug()` tạo tên unique để tránh overwrite baseline collection.
- **Cách xác minh sau khi sửa:** Kiểm tra 3 collection names trong `Settings`: `papers-baseline`, `papers-corrupted`, `papers-repaired` match với name_map keys. Chạy `corruption_flow.py` → kiểm tra `data/chroma/` có 3 thư mục collection riêng biệt. Xác nhận `baseline_answers.json` không bị thay đổi sau khi rebuild corrupted index.
- **Điều học được:** (1) Cần add unit test cho `_derive_collection_name()` với mỗi loại path để đảm bảo routing đúng trước khi gọi build(). (2) Fallback logic trong naming functions có thể tạo bugs subtle — tốt nhất là raise error thay vì silent fallback khi path không match.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?** Crossref REST API trả raw response, Role 2 parse thành `PaperRecord` và lưu `crossref_records.json`. Role 3 cleaning pipeline normalize text, parse dates, tính `age_days`, tạo `text_for_embedding` và deduplicate theo `paper_id`. Clean DataFrame được truyền vào `LocalEmbeddingIndex.build()`: MiniLM model tạo 384-dimensional normalized embeddings từ `text_for_embedding`, lưu vào ChromaDB với HNSW index và cosine similarity. JSON manifest (`papers_embeddings.json`) ghi lại toàn bộ metadata để tái index.

2. **Agent sử dụng tools như thế nào để trả lời câu hỏi?** `build_agent()` tạo LangChain agent với 2 tools: `semantic_search_papers` (gọi `index.search()` với top_k=4) và `lookup_paper` (gọi `index.lookup()` theo paper_id/title). Khi nhận câu hỏi, agent chọn tool phù hợp, nhận kết quả từ ChromaDB, và sử dụng `get_relevant_context()` để xây dựng numbered reference blocks. `retrieval_trace` là list caller-owned, ghi lại mỗi tool call (tool_name, tool_input, tool_output) — evaluation reset trace trước mỗi câu hỏi để đo chính xác documents agent đã sử dụng. `run_agent_question()` normalize response về plain text, hỗ trợ nhiều content block formats của LangChain.

3. **Tại sao 3 ChromaDB collection và `_derive_collection_name()` quan trọng?** Mỗi trạng thái (baseline, corrupted, repaired) cần index riêng để evaluation đo retrieval metrics chính xác. `_derive_collection_name()` map `embeddings_output_path` đến collection name từ `Settings`: `embeddings_json` → `papers-baseline`, `corrupted_embeddings_json` → `papers-corrupted`, `repaired_embeddings_json` → `papers-repaired`. Nếu chỉ dùng 1 collection, corrupted data sẽ overwrite baseline, không thể so sánh. Đây là contract nền tảng cho evaluation flow.

4. **QA fallback hoạt động như thế nào khi không có LLM?** `qa.py` cung cấp `answer_question()` mà không cần LLM. `_extract_answer()` sử dụng keyword routing: "who authored" → `authors_joined`, "when was" → `published`, "what categories" → `categories_joined`, mặc định → first sentence của `summary`. Kết hợp semantic search và exact lookup để tìm top result, trả về `AnswerResult` với answer, retrieved_doc_ids, contexts, titles.

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

1. **[Data corruption — embedding quality bị phá vỡ]** → Xóa summary (2 docs) loại bỏ nội dung chính khỏi `text_for_embedding` (1804→310 chars), add noise (2 docs) chèn boilerplate làm text tăng 3.7x (1697→6348 chars). Cả hai đều phá vỡ vector MiniLM — semantic search không match query đúng → retrieval hit rate giảm 20% (0.90→0.70). Stale date (2 docs) chỉ phá vỡ freshness monitoring, duplicates (2 docs) tăng row count nhưng retrieval vẫn có thể tìm đúng document.

2. **[Repair action — deterministic recovery]** → Re-clean từ raw snapshot qua `build_clean_dataframe()` deterministic → repaired DataFrame giống hệt baseline (24 rows, 12/12 pass). Retrieval hit rate và judge accuracy phục hồi về baseline (0.90 và 0.60). Repair thành công vì: (a) raw snapshot không bị corruption thay đổi, (b) cleaning pipeline deterministic, (c) frozen test set SHA256-verified.

**Corruption nào ảnh hưởng rõ nhất — từ góc nhìn RAG architecture?**

- **Blank_summary:** Ảnh hưởng lớn nhất đến embedding quality. Khi MiniLM không có summary để tạo vector, semantic search không thể match query với document đúng. Text_for_embedding giảm từ 1804→310 chars (giảm 83%) — phần còn lại chỉ là title + authors + categories, thiếu semantic content.
- **Add_noise:** Ảnh hưởng thứ hai. Noise chèn vào đầu text (prepend 30x boilerplate), vẫn giữ phần summary gốc nhưng phá vỡ embedding distribution. Text tăng từ ~1700 lên >6300 chars — MiniLM không specialized cho noise rejection.
- **Quality check gap:** Add_noise không fail basic quality check nào (summary intact, dates valid, no duplicates) nhưng vẫn affect agent metrics — chứng minh quality checks hiện tại chưa detect được embedding-level corruption.
- **Ablation test cần thiết:** 4 scenarios chạy cùng lúc, không thể quy retrieval hit giảm 20% cho riêng một scenario. Cần chạy experiments riêng lẻ để đo impact cụ thể.

**Collection separation — tại sao là contract nền tảng?**

Khi bug xảy ra (fallback về baseline collection), toàn bộ evaluation corrupted trả về metrics giống baseline (0.90) — không phản ánh tác động thực của corruption. Cách fix: `_derive_collection_name()` map `embeddings_output_path` đến collection name từ `Settings`: `embeddings_json` → `papers-baseline`, `corrupted_embeddings_json` → `papers-corrupted`, `repaired_embeddings_json` → `papers-repaired`. Ba collection tách biệt hoàn toàn, mỗi collection rebuild độc lập.

**Kết quả nào khác với kỳ vọng ban đầu?**

Token F1 và judge score repaired (0,1981, 3,50) cao hơn baseline (0,1930, 3,40). Kỳ vọng ban đầu là repaired sẽ giống baseline. Giải thích: LLM judge/generation có tính non-deterministic; `temperature=0.0` đã set nhưng Gemini 2.5 Flash vẫn có variance. Judge accuracy 60% — 4/10 câu sai, có thể do cùng model cho answer và judge → bias. Hướng cải thiện: tách judge model khỏi answer model, chạy lặp 5-10 lần để tính confidence interval.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về RAG architecture — collection separation là contract nền tảng:** Tách embedding collection theo trạng thái dữ liệu (baseline/corrupted/repaired) là quyết định quan trọng nhất. `_derive_collection_name()` map `embeddings_output_path` đến collection name từ `Settings`. Khi bug xảy ra (fallback về baseline collection), toàn bộ evaluation corrupted trả về metrics giống baseline — không phản ánh tác động thực của corruption. Cách fix: đảm bảo path resolve đúng name_map keys, và add unit test cho routing logic.

2. **Về embedding quality — blank summary là corruption nguy hiểm nhất:** MiniLM all-MiniLM-L6-v2 với 384 dimensions và normalized embeddings là lựa chọn hiệu quả cho corpus nhỏ (24 papers). lru_cache(maxsize=4) tránh reload model, ChromaDB HNSW với cosine similarity cho kết quả nhanh. Tuy nhiên, blank summary làm giảm chất lượng embedding đáng kể (text_for_embedding từ 1804→310 chars), khiến semantic search không match query với document đúng. **Lesson:** cần kiểm tra text_for_embedding không rỗng trước khi indexing.

3. **Về agent design — retrieval trace là contract giữa retrieval và evaluation:** Mỗi tool call ghi lại (tool_name, tool_input, tool_output), cho phép evaluation xác định chính xác document nào agent đã sử dụng. `_deduplicate_trace()` giữ một evidence record per paper while preserving agent tool order. `_content_to_text()` normalize nhiều content block formats của LangChain (string, list of strings/dicts/objects) thành plain text — quan trọng vì LangChain agent có thể trả về nhiều format khác nhau tùy provider.

### Nếu có thêm thời gian

Mở rộng embedding với structured output format (JSON schema) thay vì plain text để giúp agent trả lời chính xác hơn. Hiện tại `semantic_search_papers` trả về text format, agent cần parse lại để hiểu. Cách cải thiện: thêm `output_format` parameter cho tools, hỗ trợ JSON output với structured fields. Đo cải thiện bằng số lượng tool calls cần thiết và độ chính xác của answer.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Trương Ngọc Mai
**Ngày xác nhận:** 2026-08-06
