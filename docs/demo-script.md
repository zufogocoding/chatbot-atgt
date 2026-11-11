# Kịch bản demo

**Mục đích:** kịch bản 10–12 phút để demo chatbot và chụp ảnh cho báo cáo.

**Điều kiện:** commit `d857ca6` trở lên, catalog snapshot 09/11/2026.

---

## 1. Chuẩn bị

### 1.1. Kiểm tra nhanh

Chạy từ thư mục gốc:

```bash
git pull --ff-only
git status --short
python3 -m pytest -q
```

Kỳ vọng: test pass, working tree sạch.

Kiểm tra API và web đang chạy:

```bash
curl -s http://127.0.0.1:8000/health
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/
```

Kỳ vọng: `/health` trả `status: ok`; web trả `200`.

### 1.2. Khởi động nếu chưa chạy

Terminal 1 — API:

```bash
cd /home/trongzufo/pj/chatbot-atgt
ATGT_QUESTION_LOG_PATH="$PWD/tmp/demo/question-log.db" \
python3 -m uvicorn src.api.main:app \
  --host 127.0.0.1 --port 8000 --no-access-log
```

Terminal 2 — web:

```bash
cd /home/trongzufo/pj/chatbot-atgt/src/web
npm run dev
```

Mở `http://127.0.0.1:3000`.

Windows: xem hướng dẫn PowerShell trong [`README.md`](../README.md).

### 1.3. Trước khi demo

- [ ] Đóng các tab không liên quan.
- [ ] Phóng to cửa sổ trình duyệt, dùng viewport khoảng 1440×900.
- [ ] Kiểm tra âm lượng/thông báo.
- [ ] Chuẩn bị sẵn 8–10 câu hỏi bên dưới.
- [ ] Không dùng dữ liệu cá nhân thật trong câu hỏi demo.
- [ ] Nếu chụp ảnh, đặt tên theo danh sách ở mục 6.

---

## 2. Lời dẫn mở đầu (30–45 giây)

> “Đây là chatbot tra cứu xử phạt giao thông cho người dân, phạm vi xe máy và ô tô. Hệ thống trả lời bốn thứ: mức phạt tiền, hình phạt bổ sung và điểm GPLX, căn cứ pháp lý, và hướng dẫn nộp phạt/khiếu nại. Điểm quan trọng là số tiền và căn cứ lấy từ catalog đã đối chiếu, không do AI tự sinh. Catalog hiện vẫn ở trạng thái draft, chờ hai người kiểm chứng độc lập.”

---

## 3. Kịch bản chính

### Case 1 — Một hành vi, đủ loại xe

**Hỏi:**

> Xe máy vượt đèn đỏ bị phạt bao nhiêu?

**Kỳ vọng:**

- `answer_type = penalty`
- Bản ghi `nd168-d7-k7-c`
- 4.000.000–6.000.000 đồng
- Trừ 4 điểm GPLX
- Căn cứ: Điều 7 khoản 7 điểm c Nghị định 168/2024/NĐ-CP
- Có mục “Nộp phạt và khiếu nại” và nguồn tham chiếu

**Điểm nhấn khi nói:**

- Thẻ mức phạt hiển thị tiền, điểm, căn cứ.
- Phần “Đoạn luật áp dụng” mở ra nguyên văn để đối chiếu.
- Nguồn có link đến văn bản gốc.

**Ảnh:** `01-single-penalty.png`

---

### Case 2 — Thiếu loại xe, có xem trước mức phạt

**Hỏi:**

> Vượt đèn đỏ phạt bao nhiêu?

**Kỳ vọng:**

- `answer_type = clarify`
- `reason = vehicle_type`
- Hai lựa chọn:
  - Xe máy: 4.000.000–6.000.000 đồng
  - Ô tô: 18.000.000–20.000.000 đồng

**Điểm nhấn khi nói:**

- Hệ thống không đoán loại xe.
- Người dùng thấy ngay mức tiền trước khi chọn, không phải trả lời chay.
- Bấm “Xe máy” sẽ tra thẳng bản ghi.

**Ảnh:** `02-clarify-vehicle.png`

---

### Case 3 — Biên tốc độ

**Hỏi:**

> Ô tô chạy quá tốc độ 20,1 km/h bị phạt thế nào?

**Kỳ vọng:**

- `answer_type = penalty`
- Bản ghi `nd168-d6-k6-a`
- 6.000.000–8.000.000 đồng
- Trừ 4 điểm GPLX
- Căn cứ: Điều 6 khoản 6 điểm a

**Điểm nhấn khi nói:**

- Phân biệt đúng mốc 20 km/h và 20,1 km/h.
- Số thập phân được xử lý đúng, không bị tách câu.

**Ảnh:** `03-speed-boundary.png` (tùy chọn)

---

### Case 4 — Câu nhiều vi phạm (case chính)

**Hỏi:**

> Nếu xe gắn máy tống 3 và không đội mũ bảo hiểm cả 3 người, đồng thời còn lạng lách đánh võng thì phải làm như thế nào?

**Kỳ vọng:**

- `answer_type = penalty`
- `violations` gồm 4 bản ghi:
  1. `nd168-d7-k2-g` — chở 02 người — 400.000–600.000 đồng
  2. `nd168-d7-k2-h` — người lái không đội mũ — 400.000–600.000 đồng
  3. `nd168-d7-k2-i` — chở người không đội mũ — 400.000–600.000 đồng
  4. `nd168-d7-k9-a` — lạng lách, đánh võng — 8.000.000–10.000.000 đồng
- Tổng: **9.200.000–11.800.000 đồng**
- Tổng trừ điểm: **0 điểm**
- Hình phạt bổ sung: **tước GPLX 10–12 tháng**

**Điểm nhấn khi nói:**

- Đây là câu nhiều hành vi, hệ thống tách thành 4 vi phạm độc lập.
- Mỗi vi phạm có căn cứ riêng.
- Tổng tiền chỉ là cộng các khung để tham khảo; cơ quan xử lý sẽ xác định theo hồ sơ.
- Không dùng LLM để sinh số tiền.

**Ảnh:** `04-multi-penalty.png`, `05-multi-total.png`

---

### Case 5 — Hai vi phạm, tổng điểm

**Hỏi:**

> Xe máy vượt đèn đỏ và đi ngược chiều trên đường một chiều

**Kỳ vọng:**

- `answer_type = penalty`
- 2 vi phạm:
  - `nd168-d7-k7-c` — 4.000.000–6.000.000 đồng, 4 điểm
  - `nd168-d7-k7-a` — 4.000.000–6.000.000 đồng, 2 điểm
- Tổng: **8.000.000–12.000.000 đồng**
- Tổng điểm: **6 điểm**

**Điểm nhấn khi nói:**

- Hệ thống không hỏi lại “chọn hành vi nào” mà trả cả hai.
- Tổng điểm được cộng từ catalog.

**Ảnh:** `06-two-violations.png` (tùy chọn)

---

### Case 6 — Thủ tục nộp phạt

**Hỏi:**

> Nộp phạt ở đâu, thời hạn bao lâu?

**Kỳ vọng:**

- `answer_type = procedure`
- `procedure_ids = ["nop-dia-diem", "nop-thoi-han"]`
- Có hướng dẫn nơi nộp, tài khoản Kho bạc, hạn nộp
- Có trích dẫn nguồn

**Điểm nhấn khi nói:**

- Nhánh thủ tục dùng BM25/FTS5 trên 23 đoạn nguồn.
- Mỗi đoạn có trích dẫn, không phải câu trả lời chung chung.

**Ảnh:** `07-procedure.png`

---

### Case 7 — Thời hiệu khiếu nại

**Hỏi:**

> Thời hiệu khiếu nại quyết định xử phạt bao lâu?

**Kỳ vọng:**

- `answer_type = procedure`
- `procedure_ids = ["kn-thoi-hieu"]`
- Nêu **90 ngày** kể từ ngày nhận/biết quyết định
- Có nguồn

**Điểm nhấn khi nói:**

- Câu trả lời có số liệu cụ thể, có căn cứ.
- Người dân biết mốc thời gian để khiếu nại.

**Ảnh:** `08-complaint.png` (tùy chọn)

---

### Case 8 — Ngoài phạm vi

**Hỏi:**

> Xe buýt vượt đèn đỏ

**Kỳ vọng:**

- `answer_type = refuse`
- `reason = vehicle_out_of_scope`
- Câu trả lời nêu phạm vi xe máy/ô tô cá nhân

**Điểm nhấn khi nói:**

- Hệ thống biết từ chối thay vì bịa.
- Xe buýt/xe máy chuyên dùng nằm ngoài phạm vi.

**Ảnh:** `09-refuse-scope.png`

---

### Case 9 — Catalog chưa có hành vi

**Hỏi:**

> Ô tô chở hàng cồng kềnh bị phạt bao nhiêu?

**Kỳ vọng:**

- `answer_type = refuse`
- `reason = insufficient_source`
- Câu trả lời nói chưa tìm thấy hành vi khớp có căn cứ

**Điểm nhấn khi nói:**

- Đây là guardrail “không có nguồn → không trả lời”.
- Catalog chưa bao phủ mọi hành vi; đây là giới hạn đã biết.

**Ảnh:** `10-refuse-source.png`

---

### Case 10 — Phân biệt người lái và người được chở (tùy chọn)

**Hỏi:**

> Người ngồi sau xe máy không đội mũ bảo hiểm

**Kỳ vọng:**

- `answer_type = penalty`
- Bản ghi `nd168-d12-k5-b`
- 400.000–600.000 đồng
- 0 điểm
- Căn cứ: Điều 12 khoản 5 điểm b

**Điểm nhấn khi nói:**

- Cùng là “không đội mũ” nhưng chủ thể khác nhau có khung khác nhau.
- Hệ thống phân biệt người điều khiển và người được chở.

**Ảnh:** `11-passenger-helmet.png` (tùy chọn)

---

## 4. Bảng tổng hợp nhanh

| # | Câu hỏi | Loại | Kết quả chính |
|---|---|---|---|
| 1 | Xe máy vượt đèn đỏ bị phạt bao nhiêu? | penalty | 4–6 triệu, 4 điểm |
| 2 | Vượt đèn đỏ phạt bao nhiêu? | clarify | Xe máy 4–6 triệu / Ô tô 18–20 triệu |
| 3 | Ô tô quá tốc độ 20,1 km/h | penalty | 6–8 triệu, 4 điểm |
| 4 | Câu 4 vi phạm | penalty | 9,2–11,8 triệu, 0 điểm, tước GPLX 10–12 tháng |
| 5 | Đèn đỏ + ngược chiều | penalty | 8–12 triệu, 6 điểm |
| 6 | Nộp phạt ở đâu, thời hạn? | procedure | `nop-dia-diem`, `nop-thoi-han` |
| 7 | Thời hiệu khiếu nại? | procedure | 90 ngày |
| 8 | Xe buýt vượt đèn đỏ | refuse | Ngoài phạm vi |
| 9 | Ô tô chở hàng cồng kềnh | refuse | Chưa có nguồn |
| 10 | Người ngồi sau không đội mũ | penalty | 400–600 nghìn, 0 điểm |

---

## 5. Lệnh curl để kiểm tra trước

Có thể chạy nhanh không cần giao diện:

```bash
curl -s http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Xe máy vượt đèn đỏ bị phạt bao nhiêu?"}' \
  | python3 -m json.tool
```

Câu multi:

```bash
curl -s http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Nếu xe gắn máy tống 3 và không đội mũ bảo hiểm cả 3 người, đồng thời còn lạng lách đánh võng thì phải làm như thế nào?"}' \
  | python3 -m json.tool
```

Kiểm tra nhanh các trường:

```bash
curl -s http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Xe máy vượt đèn đỏ và đi ngược chiều trên đường một chiều"}' \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r["answer_type"], [v["record_id"] for v in r["violations"]])'
```

---

## 6. Danh sách ảnh cần chụp

| Tệp | Nội dung | Bắt buộc |
|---|---|---|
| `01-single-penalty.png` | Thẻ mức phạt đơn, có tiền/điểm/căn cứ | Có |
| `02-clarify-vehicle.png` | Hỏi loại xe kèm 2 mức tiền | Có |
| `03-speed-boundary.png` | Ô tô quá tốc độ 20,1 km/h | Không |
| `04-multi-penalty.png` | Danh sách 4 vi phạm | Có |
| `05-multi-total.png` | Phần tổng hợp tiền/điểm/hình phạt bổ sung | Có |
| `06-two-violations.png` | 2 vi phạm, tổng 6 điểm | Không |
| `07-procedure.png` | Hướng dẫn nộp phạt, có nguồn | Có |
| `08-complaint.png` | Thời hiệu khiếu nại 90 ngày | Không |
| `09-refuse-scope.png` | Từ chối xe buýt | Có |
| `10-refuse-source.png` | Từ chối hành vi chưa có nguồn | Có |
| `11-passenger-helmet.png` | Người ngồi sau không đội mũ | Không |

Gợi ý chụp:

- Viewport 1440×900 cho ảnh desktop.
- Ảnh thẻ multi nên chụp cả phần đầu và phần tổng hợp; nếu dài, chụp 2 ảnh.
- Không chụp thanh địa chỉ có thông tin cá nhân.
- Nếu chụp mobile, dùng 390×844.

**Lưu ý môi trường:** máy phát triển hiện tại không có Chrome/Chromium để dùng Chrome DevTools MCP. Cần chụp thủ công bằng trình duyệt có sẵn, hoặc cài Chromium trước khi chụp.

---

## 7. Phân bổ thời gian

| Thời lượng | Nội dung |
|---|---|
| 0:00–0:45 | Mở đầu, phạm vi, nguyên tắc |
| 0:45–2:00 | Case 1: một hành vi |
| 2:00–3:15 | Case 2: hỏi lại loại xe |
| 3:15–4:00 | Case 3: biên tốc độ |
| 4:00–6:30 | Case 4: multi-violation |
| 6:30–7:15 | Case 5: hai vi phạm |
| 7:15–8:30 | Case 6–7: thủ tục, khiếu nại |
| 8:30–9:30 | Case 8–9: từ chối |
| 9:30–10:30 | Giới hạn, kiểm chứng, Q&A |

---

## 8. Khi có lỗi

### Web không tải

1. Kiểm tra `http://127.0.0.1:8000/health`.
2. Kiểm tra terminal Next.js có lỗi build.
3. Nếu vẫn lỗi, chuyển sang Swagger `http://127.0.0.1:8000/docs` hoặc dùng `curl`.

### API 503

- Kiểm tra `data/build/catalog.db` tồn tại.
- Chạy `python3 scripts/build_db.py` nếu cần.
- Không xóa/tạo DB rỗng trong lúc demo.

### Câu trả lời không đúng kỳ vọng

- Kiểm tra commit đang chạy: `git log -1 --oneline`.
- Kiểm tra API có phải bản mới: `curl http://127.0.0.1:8000/openapi.json`.
- Không sửa code trong lúc demo; ghi lại câu hỏi và chuyển sang case khác.

### Không có ảnh

- Dùng kết quả `curl` trong phụ lục báo cáo.
- Chụp lại sau, ghi rõ ngày/commit.

---

## 9. Câu hỏi thường gặp khi demo

**“Số tiền có đúng 100% không?”**

> Catalog đã audit tự động 276/276 khớp với điều/khoản/điểm. Tuy nhiên catalog vẫn `draft`, chờ hai người rà soát độc lập. Đây là thông tin tham khảo, không thay thế tư vấn pháp lý.

**“Sao không dùng ChatGPT/LLM?”**

> Số tiền và căn cứ phải truy vết được. LLM có thể bịa. Hiện hệ thống deterministic; nếu sau này dùng LLM, chỉ dùng để trích xuất cấu trúc, không sinh số tiền.

**“Tổng tiền có phải mức phạt chính thức?”**

> Không. Đây là cộng các khung để tham khảo. Cơ quan có thẩm quyền quyết định theo hồ sơ và tình tiết cụ thể.

**“Có xử lý xe tải/xe khách không?”**

> Có, với các hành vi giao thông chung đã có trong catalog. Các quy định riêng về kinh doanh vận tải (Điều 20–24) chưa nằm trong phạm vi.

**“Câu hỏi tự do có trả lời được hết không?”**

> Không. Hệ thống ưu tiên đúng và truy vết được; câu thiếu dữ kiện sẽ hỏi lại, câu ngoài phạm vi/chưa có nguồn sẽ từ chối.

---

## 10. Sau demo

- [ ] Dừng API/web nếu không dùng tiếp.
- [ ] Không commit `tmp/demo/question-log.db`.
- [ ] Lưu ảnh vào thư mục báo cáo, ghi ngày/commit.
- [ ] Ghi lại câu hỏi nào bị hỏi lại/từ chối ngoài dự kiến để cải thiện alias.
- [ ] Nếu có thay đổi code, chạy lại `pytest` và `evaluate_dataset.py`.
