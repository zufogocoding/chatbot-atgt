# Chatbot tra cứu xử phạt giao thông

Chatbot tiếng Việt giúp người dân tra cứu mức phạt vi phạm giao thông cho **xe máy** và **ô tô**: số tiền, hình phạt bổ sung, trừ điểm GPLX, căn cứ pháp lý và thủ tục nộp phạt/khiếu nại.

- [Phạm vi, kiến trúc và kế hoạch đánh giá](docs/project-brief.md)
- [Schema catalog, quy trình dựng lại và giới hạn](data/catalog/README.md)
- [Bàn giao kiểm chứng catalog cho hai người rà soát](docs/ban-giao.md)

## Cách chạy trên Windows

Cài **Git**, **Python 3.11+** và **Node.js 20.9+**. Repo có sẵn file `data/build/catalog.db`, nên có thể chạy chatbot ngay sau khi cài thư viện.

### 1. Tải source

```powershell
git clone https://github.com/zufogocoding/chatbot-atgt.git
cd chatbot-atgt
```

Nếu đã clone repo, chạy `git fetch origin` rồi `git pull --ff-only` từ thư mục dự án.

### 2. Chạy FastAPI trong terminal thứ nhất

Chạy từ thư mục gốc của repo và giữ terminal này mở.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Kiểm tra backend tại [trang trạng thái API](http://127.0.0.1:8000/health) hoặc thử câu hỏi trong [Swagger UI](http://127.0.0.1:8000/docs).

### 3. Chạy Next.js trong terminal thứ hai

Mở terminal mới từ thư mục gốc của repo.

```powershell
cd src/web
npm.cmd ci
npm.cmd run dev
```

Mở [giao diện chatbot](http://127.0.0.1:3000) và thử hỏi “Xe máy vượt đèn đỏ bị phạt bao nhiêu?” hoặc “Nộp phạt ở đâu, thời hạn bao lâu?”. Nếu giao diện báo **Mất kết nối**, kiểm tra lại terminal FastAPI và trang `/health` ở cổng 8000.

## Chạy demo trong mạng nội bộ

Sau khi cài thư viện như trên, chạy FastAPI từ thư mục gốc trong terminal thứ nhất.

```powershell
$env:ATGT_QUESTION_LOG_PATH = Join-Path (Get-Location) 'tmp\demo\question-log.db'
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Trong terminal thứ hai, thay địa chỉ ví dụ bằng địa chỉ IPv4 nội bộ của máy chủ.

```powershell
cd src/web
npm.cmd run build
$demoIp = '192.168.1.10'
.\node_modules\.bin\next.cmd start --hostname $demoIp --port 3000
```

Truy cập `http://<IP-LAN>:3000` từ mạng nội bộ. API dùng chung địa chỉ với web qua `/api/health` và `/api/chat`.

Khi đặt `ATGT_QUESTION_LOG_PATH`, API ghi mỗi lượt chat có kết quả vào bảng SQLite `question_log`, gồm `question`, `answer_type`, `record_id`, `reason` và `timestamp` (UTC). `record_id` là mã bản ghi mức phạt trong câu trả lời, để trống nếu chưa có bản ghi. API không thu thập IP, tài khoản hay thông tin thiết bị trong bảng này. Log che email, chuỗi số định danh và biển số theo mẫu phổ biến. Tên và địa chỉ viết tự do vẫn có thể xuất hiện nếu người dùng nhập vào câu hỏi. Thư mục `tmp/` đã được Git bỏ qua.

## Trạng thái hiện tại

| Hạng mục | Giá trị |
|---|---|
| Văn bản áp dụng | 168/2024/NĐ-CP, hợp nhất với 238/2026/NĐ-CP (hiệu lực 15/08/2026) |
| Ngày snapshot | 09/11/2026 |
| Bản ghi vi phạm | 276 (Điều 6, 7, 12, 13, 14, 18, 32) — gồm người điều khiển, người được chở và chủ phương tiện |
| Alias tiếng dân | 56 nhóm, 363 cách nói (290 biến thể sau chuẩn hóa) |
| Kiểm chứng | 276/276 bản ghi khớp đối chiếu tự động. Trạng thái `draft` đến khi có hai người xác nhận khung tiền theo đề cương. |
| Dữ liệu thủ tục | 23 đoạn có dẫn nguồn cho nộp phạt và khiếu nại |
| Bộ đánh giá | 261 câu có nhãn kỳ vọng, có script chấm baseline |
| Tra cứu thử | SQLite + FTS5 + CLI |

Phạm vi catalog hiện tại: quy tắc giao thông, điều kiện phương tiện, điều kiện người lái, **Điều 12 (người được chở)** và **Điều 32 (chủ phương tiện)** — bao gồm sang tên/không chính chủ, giao xe cho người không đủ điều kiện, biển số/đăng ký, cải tạo xe, khoản 5–6 (phạt trên mỗi người vượt quá, có trần) và các điểm 238/2026 thêm mới 9a.a/11.e/13.e. Chưa gồm: điểm b khoản 9a (thiết bị ghi nhận hình ảnh người lái xe, hiệu lực 01/01/2028), Điều 17 và các điều vận tải 20–24.

Dữ liệu thủ tục nằm trong [`data/procedures/`](data/procedures/) và được lập chỉ mục BM25 trong [`data/build/catalog.db`](data/build/catalog.db). SQLite chứa bảng `procedures`, `procedure_sources` và `procedure_citations` để tra đoạn thủ tục và căn cứ. Kết quả và cách chạy golden set nằm trong [`data/eval/README.md`](data/eval/README.md).

## Dựng lại catalog và tra cứu bằng CLI

Yêu cầu: Python 3.11+ (không cần thư viện ngoài cho phần catalog).

```bash
# 1. Parse văn bản 168 (đã có file parsed, chạy lại nếu cần)
python3 scripts/parse_168.py

# 2. Trích xuất bản nháp từ 168
python3 scripts/extract_violations.py

# 3. Hợp nhất sửa đổi 238/2026
python3 scripts/apply_amendments_238.py

# 4. Kiểm tra catalog + alias
python3 scripts/validate_catalog.py

# 5. Build SQLite + FTS5
python3 scripts/build_db.py

# 6. Đối chiếu khung tiền và chạy golden set
python3 scripts/audit_fines.py
python3 scripts/evaluate_dataset.py
```

Tra thử:

```bash
python3 scripts/query_catalog.py search "xe máy vượt đèn đỏ"
python3 scripts/query_catalog.py answer "ô tô quá tốc độ"
python3 scripts/query_catalog.py answer "vượt đèn đỏ"          # hỏi lại loại xe
python3 scripts/query_catalog.py answer "xe máy không chính chủ" # chủ phương tiện (Điều 32)
python3 scripts/query_catalog.py answer "người ngồi sau xe máy không đội mũ" # người được chở (Điều 12)
python3 scripts/query_catalog.py record nd168-d7-k7-c
python3 scripts/query_catalog.py procedure "thời hiệu khiếu nại quyết định xử phạt" --limit 1
python3 scripts/query_catalog.py stats
```

## Backend FastAPI

`GET /health` kiểm tra catalog. `POST /chat` nhận JSON có `question`, có thể nhận `vehicle_type` là `xe_may` hoặc `o_to`, và `record_id` khi người dùng bấm chọn một phương án do API trả về.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat `
  -ContentType 'application/json; charset=utf-8' `
  -Body (@{ question = 'Nộp phạt ở đâu, thời hạn bao lâu?' } | ConvertTo-Json -Compress)
```

`answer_type` cho biết kết quả là `penalty`, `procedure`, `clarify` hoặc `refuse`. Kết quả tra mức phạt có `penalty` để hiển thị số tiền và căn cứ; `penalty.source_quote` là đoạn luật áp dụng để người dùng đối chiếu, `penalty.guidance` gồm các bước nộp phạt và khiếu nại kèm trích dẫn, và `related` gợi ý mức phạt tương ứng cho loại xe còn lại khi alias xác định duy nhất một bản ghi. Kết quả thủ tục có `procedure_ids` và `sources`. Các số `[1]`, `[2]` trong câu trả lời trỏ đến thứ tự trong `sources`. Khi API hỏi lại, gửi câu hỏi đầy đủ kèm chi tiết bổ sung; nếu chọn từ `options` hoặc `related`, gửi `record_id` tương ứng để API trả thẳng bản ghi đó. API kiểm tra lại loại xe và trả `clarify` nếu bản ghi không thuộc loại xe đã chọn.

Backend đọc `data/build/catalog.db` ở chế độ chỉ đọc. Có thể đặt biến môi trường `CATALOG_DB_PATH` để trỏ đến một bản catalog khác. Nhánh mức phạt dùng quy tắc chọn bản ghi và alias, nhánh thủ tục dùng các đoạn nguồn trong SQLite với truy xuất BM25 khi cần. API trả ngày snapshot qua `as_of`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/evaluate_dataset.py --api-url http://127.0.0.1:8000/chat
```

## Giao diện Next.js

Các câu hỏi mẫu gửi yêu cầu đến FastAPI. Thẻ trả lời hiển thị khung tiền, điểm GPLX, nguồn và mục **Nộp phạt và khiếu nại** với hạn nộp, nơi nộp và thời hiệu khiếu nại; phần “Đoạn luật áp dụng” mở ra nguyên văn căn cứ để đối chiếu. Câu trả lời thủ tục có số tham chiếu mở thẳng đến nguồn tương ứng. Khi API hỏi loại xe, chọn **Xe máy** hoặc **Ô tô** để gửi lại câu hỏi với thông tin đó. Khi API đưa ra các phương án hoặc gợi ý loại xe còn lại, bấm vào phương án để tra thẳng bản ghi đó.

Next.js chuyển tiếp `/api/chat` và `/api/health` sang `http://127.0.0.1:8000`. Đặt biến môi trường `ATGT_API_URL` trong terminal chạy Next.js nếu backend dùng địa chỉ khác.

```powershell
npm.cmd run typecheck
npm.cmd run build
```

## Cấu trúc

```
data/raw/          PDF/DOCX gốc từ nguồn chính thức
data/parsed/       Text + cấu trúc điều/khoản/điểm
data/amendments/   Patch sửa đổi (238/2026)
data/catalog/      violations.jsonl, penalty-rules.jsonl, aliases.json
data/procedures/   Các đoạn hướng dẫn thủ tục và danh mục nguồn chính thức
data/eval/         Golden set và kết quả baseline
data/overrides/    Điều kiện hình phạt thủ công
data/build/        SQLite sinh tự động (không sửa tay)
scripts/           Parse, extract, consolidate, validate, build, query
src/api/           FastAPI, định tuyến, tra cứu và soạn câu trả lời
src/web/           Next.js, giao diện chat và chuyển tiếp API
docs/              Project brief
```

## Nguyên tắc

1. Không có nguồn → không trả lời.
2. Con số và căn cứ lấy từ catalog, không do LLM sinh.
3. Thiếu loại xe hoặc thiếu mức vi phạm → hỏi lại.
4. Hình phạt có điều kiện phải hiển thị "có thể bị... nếu...".
5. Văn bản luật thay đổi → cập nhật patch + chạy lại validation/golden set.

> Thông tin trong repo dùng cho đồ án và tra cứu tham khảo, không thay thế tư vấn pháp lý.
