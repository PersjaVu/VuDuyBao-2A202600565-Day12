# How to Run — Day08 RAG + Day09 Multi-Agent + Lab Assignment

## Mục lục
1. [Yêu cầu](#1-yêu-cầu)
2. [Cài đặt môi trường](#2-cài-đặt-môi-trường)
3. [Cấu hình .env](#3-cấu-hình-env)
4. [Day08 — RAG Pipeline](#4-day08--rag-pipeline)
5. [Day09 — Multi-Agent System (A2A)](#5-day09--multi-agent-system-a2a)
6. [Lab Assignment — Supervisor-Worker RAG](#6-lab-assignment--supervisor-worker-rag)
7. [Test](#7-test)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Yêu cầu

| Phần mềm | Phiên bản tối thiểu |
|---|---|
| Python | 3.11+ |
| Windows Terminal / PowerShell | 5.1+ |

**API Keys cần có:**
- `OPENROUTER_API_KEY` — dùng cho Day09 và Lab Assignment (lấy tại [openrouter.ai](https://openrouter.ai))
- `OPENAI_API_KEY` — dùng cho Day08 Task 10 (tùy chọn nếu dùng OpenRouter)
- `PAGEINDEX_API_KEY` — dùng cho Day08 Task 8 (tùy chọn)

---

## 2. Cài đặt môi trường

### 2.1 Kích hoạt virtual environment

Project dùng `.venv` với Python 3.13. **LUÔN dùng `.venv` khi chạy**, không dùng `python` hệ thống.

```powershell
# Từ thư mục gốc dự án
cd d:\VinUni\Batch02-Day9_Multi-Agent_MCP-A2A

# Kích hoạt venv
.venv\Scripts\Activate.ps1

# Kiểm tra đang dùng đúng Python
python --version          # phải thấy Python 3.13.x từ .venv
where python              # phải thấy đường dẫn chứa .venv
```

> **Lưu ý Windows:** Nếu gặp lỗi execution policy, chạy:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### 2.2 Cài gói Day09 (đã có sẵn trong .venv)

```powershell
# Kiểm tra nhanh
python -c "import langgraph, langchain_openai, a2a; print('Day09 OK')"
```

### 2.3 Cài gói Day08 (RAG dependencies)

```powershell
# Cần bootstrap pip vào venv trước (chỉ làm 1 lần)
python -m ensurepip

# Cài các gói RAG
python -m pip install numpy rank-bm25 sentence-transformers chromadb

# Kiểm tra
python -c "import numpy, chromadb, sentence_transformers, rank_bm25; print('Day08 OK')"
```

---

## 3. Cấu hình .env

Tạo file `.env` ở thư mục gốc (copy từ `.env.example`):

```powershell
Copy-Item .env.example .env
notepad .env
```

Nội dung `.env`:

```env
# Bắt buộc cho Day09 và Lab Assignment
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_MODEL=anthropic/claude-sonnet-4-5

# Registry URL (mặc định localhost)
REGISTRY_URL=http://localhost:10000

# Tùy chọn cho Day08 Task 10
OPENAI_API_KEY=sk-your_openai_key_here

# Tùy chọn cho Day08 Task 8 (PageIndex vectorless RAG)
PAGEINDEX_API_KEY=pi-your_key_here
```

---

## 4. Day08 — RAG Pipeline

Pipeline RAG xử lý văn bản pháp luật và tin tức về ma tuý Việt Nam.

### 4.1 Chuẩn bị dữ liệu (Tasks 1-3)

```powershell
# Vào thư mục Day08
cd Lab_Assignment\Day08_RAG_pipeline_cohort2

# Task 1: Thu thập văn bản pháp luật (tải PDF vào data/landing/legal/)
python src/task1_collect_legal_docs.py

# Task 2: Crawl bài báo (lưu vào data/landing/news/)
python src/task2_crawl_news.py

# Task 3: Convert sang Markdown (lưu vào data/standardized/)
python src/task3_convert_markdown.py
```

### 4.2 Build RAG Index (Task 4) — Chỉ chạy 1 lần

```powershell
# Tạo ChromaDB vector store + chunks.json (BM25 index)
python src/task4_chunking_indexing.py
```

> Sau bước này, thư mục `data/vectorstore/chroma/` và `data/standardized/chunks.json` sẽ được tạo.

### 4.3 Test từng module tìm kiếm

```powershell
# Task 5: Semantic Search (ChromaDB + embedding)
python src/task5_semantic_search.py

# Task 6: Lexical Search (BM25)
python src/task6_lexical_search.py

# Task 7: Reranking (RRF + optional cross-encoder)
python src/task7_reranking.py

# Task 8: PageIndex vectorless (cần PAGEINDEX_API_KEY)
python src/task8_pageindex_vectorless.py
```

### 4.4 Chạy Retrieval Pipeline đầy đủ (Task 9)

```powershell
python src/task9_retrieval_pipeline.py
```

Output mẫu:
```
Query: Hình phạt cho tội tàng trữ trái phép chất ma tuý
  1. [0.8523] [hybrid] Điều 249. Tội tàng trữ trái phép chất ma tuý...
  2. [0.7341] [hybrid] Hình phạt: Phạt tù từ 1 năm đến 5 năm...
  3. [0.6892] [hybrid] Tình tiết tăng nặng: khối lượng lớn...
```

### 4.5 Chạy Generation có Citation (Task 10)

```powershell
# Cần OPENAI_API_KEY hoặc OPENROUTER_API_KEY trong .env
python src/task10_generation.py
```

Output mẫu:
```
Q: Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?
A: Theo quy định tại [Điều 249 BLHS 2015], tội tàng trữ trái phép...
```

---

## 5. Day09 — Multi-Agent System (A2A)

Hệ thống multi-agent với Supervisor (Law Agent) điều phối 2 workers (Tax + Compliance).

**Cổng dịch vụ:**
| Service | Cổng |
|---|---|
| Registry | 10000 |
| Customer Agent | 10100 |
| Law Agent (Supervisor) | 10101 |
| Tax Agent (Worker) | 10102 |
| Compliance Agent (Worker) | 10103 |

### 5.1 Khởi động hệ thống (mở 5 terminal riêng biệt)

**Terminal 1 — Registry (khởi động TRƯỚC TIÊN):**
```powershell
.venv\Scripts\Activate.ps1
python -m registry
```

**Terminal 2 — Law Agent (Supervisor):**
```powershell
.venv\Scripts\Activate.ps1
python -m law_agent
```

**Terminal 3 — Tax Agent (Worker):**
```powershell
.venv\Scripts\Activate.ps1
python -m tax_agent
```

**Terminal 4 — Compliance Agent (Worker):**
```powershell
.venv\Scripts\Activate.ps1
python -m compliance_agent
```

**Terminal 5 — Customer Agent (giao diện người dùng):**
```powershell
.venv\Scripts\Activate.ps1
python -m customer_agent
```

### 5.2 Test nhanh bằng curl

```powershell
# Kiểm tra Registry
Invoke-RestMethod http://localhost:10000/health

# Xem các agents đã đăng ký
Invoke-RestMethod http://localhost:10000/agents | ConvertTo-Json

# Gửi câu hỏi qua Customer Agent
$body = @{ content = "What are the tax implications of hiding offshore accounts?" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:10100/messages -Method Post -Body $body -ContentType "application/json"
```

### 5.3 Chạy frontend (tùy chọn)

```powershell
cd frontend-demo
npm install
npm run dev
# Mở browser tại http://localhost:5173
```

### 5.4 Test bằng exercise scripts

```powershell
# Stage 1: Direct LLM
python stages/stage_1_direct_llm/main.py

# Stage 2: RAG Tools
python stages/stage_2_rag_tools/main.py

# Stage 3: Single Agent
python stages/stage_3_single_agent/main.py

# Stage 4: Multi-Agent (cần tất cả services đang chạy)
python stages/stage_4_milti_agent/main.py

# Exercise 4: Multi-agent với Privacy Agent
python exercises/exercise_4_multiagent.py
```

---

## 6. Lab Assignment — Supervisor-Worker RAG

Hệ thống cải tiến kết hợp RAG pipeline (Day08) với Supervisor-Worker pattern (Day09).

**Kiến trúc:**
```
User Query → Supervisor → check_routing → [PARALLEL]
                                          ├── Worker1: Legal Provisions
                                          ├── Worker2: Criminal Penalty
                                          └── Worker3: Rehabilitation
                                                   └── Aggregator → Answer
```

### 6.1 Chạy demo (không cần Day08 index)

```powershell
# Từ thư mục gốc
$env:PYTHONIOENCODING = "utf-8"
.venv\Scripts\python.exe Lab_Assignment\main.py

# Hoặc với câu hỏi tuỳ chỉnh
.venv\Scripts\python.exe Lab_Assignment\main.py "Hình phạt tội tàng trữ ma tuý là gì?"
```

> Nếu chưa có RAG index → Workers tự động fallback sang LLM-only. Kết quả vẫn đầy đủ.

### 6.2 Bật RAG thực (sau khi đã chạy Day08 task1-task4)

RAG tự động hoạt động sau khi có index. Không cần thay đổi code. Log sẽ hiện:
```
[Worker1-Legal] Done (4 chunks, 1409 chars)   ← có số chunks > 0 = RAG đang dùng
```

### 6.3 Câu hỏi test gợi ý theo domain

```powershell
# Test routing → chỉ gọi Worker1 + Worker2 (không gọi Worker3)
.venv\Scripts\python.exe Lab_Assignment\main.py "Điều 249 BLHS quy định gì về tội tàng trữ ma tuý?"

# Test routing → chỉ gọi Worker1 + Worker3
.venv\Scripts\python.exe Lab_Assignment\main.py "Luật PCMT 2021 quy định cai nghiện tự nguyện như thế nào?"

# Test routing → cả 3 workers (câu hỏi tổng quát)
.venv\Scripts\python.exe Lab_Assignment\main.py "Tổng quan về pháp luật phòng chống ma tuý Việt Nam"
```

---

## 7. Test

### 7.1 Test Day08 (pytest)

```powershell
cd Lab_Assignment\Day08_RAG_pipeline_cohort2

# Chạy toàn bộ test suite
python -m pytest tests/test_individual.py -v

# Chạy từng task
python -m pytest tests/test_individual.py::TestTask1 -v
python -m pytest tests/test_individual.py::TestTask5 -v
python -m pytest tests/test_individual.py::TestTask9 -v
python -m pytest tests/test_individual.py::TestTask10 -v
```

> **Lưu ý:** Các test Task4-Task9 cần RAG index đã được build. Task1-Task3 cần data đã được collect.

### 7.2 Test Day09 (manual)

```powershell
# 1. Khởi động tất cả services (xem mục 5.1)

# 2. Kiểm tra health
Invoke-RestMethod http://localhost:10000/health
Invoke-RestMethod http://localhost:10100/.well-known/agent.json | Select-Object name, description
Invoke-RestMethod http://localhost:10101/.well-known/agent.json | Select-Object name, description

# 3. Test câu hỏi pháp lý tổng quát
$body = @{ content = "What happens if a company violates SEC regulations?" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:10100/messages -Method Post -Body $body -ContentType "application/json"

# 4. Test câu hỏi thuế (→ Tax Agent được gọi)
$body = @{ content = "What are the tax penalties for offshore accounts and FBAR violations?" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:10100/messages -Method Post -Body $body -ContentType "application/json"

# 5. Test câu hỏi compliance (→ Compliance Agent được gọi)
$body = @{ content = "Explain GDPR compliance requirements for data breaches" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:10100/messages -Method Post -Body $body -ContentType "application/json"
```

### 7.3 Test Lab Assignment

```powershell
$env:PYTHONIOENCODING = "utf-8"

# Test 1: Kiểm tra routing logic (xem log để confirm đúng workers được gọi)
.venv\Scripts\python.exe Lab_Assignment\main.py "Hình phạt tội buôn bán ma tuý theo BLHS 2015"
# Kỳ vọng: Routing legal=True penalty=True rehab=False

# Test 2: Kiểm tra parallel execution (timestamp của Worker1 và Worker2 gần nhau)
.venv\Scripts\python.exe Lab_Assignment\main.py "Cai nghiện bắt buộc theo Luật PCMT 2021"
# Kỳ vọng: Routing legal=True rehab=True (có thể cả penalty tùy keyword)

# Test 3: Kiểm tra fallback (không cần RAG index)
.venv\Scripts\python.exe Lab_Assignment\main.py "Tổng quan luật phòng chống ma tuý"
# Kỳ vọng: 3 workers đều chạy, câu trả lời có trích dẫn
```

**Xác nhận hệ thống hoạt động đúng qua log:**
```
[Supervisor] Routing: legal=True  penalty=True  rehab=False  ← routing đúng
[Worker1-Legal] Done (N chunks, X chars)   ← N>0 nếu RAG có data
[Worker2-Criminal] Done (N chunks, X chars)
[Aggregator] Final answer produced (X chars)
```

---

## 8. Troubleshooting

### "No module named 'langgraph'" hoặc "No module named 'numpy'"
```powershell
# Nguyên nhân: đang dùng Python hệ thống thay vì .venv
# Giải pháp: luôn activate venv hoặc dùng đường dẫn đầy đủ
.venv\Scripts\Activate.ps1
# Hoặc:
.venv\Scripts\python.exe your_script.py
```

### "No module named 'pip'"
```powershell
# Chạy 1 lần để bootstrap pip vào venv
.venv\Scripts\python.exe -m ensurepip
```

### UnicodeEncodeError (Vietnamese characters)
```powershell
# Thêm biến môi trường trước khi chạy
$env:PYTHONIOENCODING = "utf-8"
.venv\Scripts\python.exe Lab_Assignment\main.py
```

### Registry connection refused (Day09)
```
# Đảm bảo khởi động Registry trước tất cả agents khác
python -m registry
# Chờ thấy "Starting Registry on port 10000" rồi mới khởi động agents
```

### RAG index not found (Day08 / Lab Assignment)
```powershell
# Cần chạy tuần tự: task1 → task2 → task3 → task4
cd Lab_Assignment\Day08_RAG_pipeline_cohort2
python src/task1_collect_legal_docs.py
python src/task2_crawl_news.py
python src/task3_convert_markdown.py
python src/task4_chunking_indexing.py
```

### FileNotFoundError: chunks.json (BM25 index)
```powershell
# chunks.json được tạo bởi task4. Nếu thiếu:
python src/task4_chunking_indexing.py
```

### ChromaDB collection not found
```powershell
# ChromaDB index được tạo bởi task4. Nếu thiếu:
python src/task4_chunking_indexing.py
# Kiểm tra: thư mục data/vectorstore/chroma/ phải tồn tại
```

---

## Tổng quan cổng và services

| Service | Cổng | Mô tả |
|---|---|---|
| Registry | 10000 | Agent discovery service |
| Customer Agent | 10100 | Entry point, REST `/messages` endpoint |
| Law Agent | 10101 | Supervisor trong Day09 |
| Tax Agent | 10102 | Worker trong Day09 |
| Compliance Agent | 10103 | Worker trong Day09 |
| Frontend (Vite) | 5173 | Web UI |

## Tóm tắt lệnh chạy nhanh

```powershell
# Bước 0: Activate venv (luôn làm trước)
.venv\Scripts\Activate.ps1

# Day08: Build index (1 lần)
cd Lab_Assignment\Day08_RAG_pipeline_cohort2
python src/task4_chunking_indexing.py
cd ..\..

# Day09: Chạy multi-agent (5 terminal)
python -m registry            # Terminal 1
python -m law_agent           # Terminal 2
python -m tax_agent           # Terminal 3
python -m compliance_agent    # Terminal 4
python -m customer_agent      # Terminal 5

# Lab Assignment: Supervisor-Worker RAG
$env:PYTHONIOENCODING = "utf-8"
python Lab_Assignment\main.py

# Test Day08
cd Lab_Assignment\Day08_RAG_pipeline_cohort2
python -m pytest tests/test_individual.py -v
```
