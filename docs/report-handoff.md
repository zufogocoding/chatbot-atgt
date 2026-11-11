# Bàn giao viết báo cáo

**Mục đích:** tài liệu định hướng cho người viết báo cáo chi tiết. Đây **không phải** báo cáo và không thay thế báo cáo.

| Hạng mục | Giá trị |
|---|---|
| Ngày cập nhật | 11/11/2026 |
| Commit tham chiếu | `d857ca6` |
| Nhánh | `main` |
| Snapshot dữ liệu | 09/11/2026 |
| Catalog | `draft` — chưa có snapshot `verified` |
| Runtime | Deterministic, chưa dùng LLM |

> Quy tắc quan trọng: mọi số liệu trong báo cáo phải ghi kèm **ngày chạy + commit**. Không trích số liệu từ tài liệu cũ mà chưa đối chiếu lại.

---

## 1. Trạng thái hiện tại

### 1.1. Dữ liệu

| Hạng mục | Giá trị |
|---|---:|
| Bản ghi vi phạm | 276 |
| Bản ghi có phạt tiền | 264 |
| Bản ghi cảnh cáo | 2 |
| Bản ghi chỉ có hình phạt bổ sung | 10 |
| Quy tắc hình phạt bổ sung/trừ điểm | 59 |
| Nhóm alias | 56 |
| Alias phrase đã nạp SQLite | 293 |
| Đoạn thủ tục | 23 |
| Nguồn thủ tục | 6 |
| Trích dẫn thủ tục | 31 |
| Bản ghi có trừ điểm GPLX | 112 |
| Bản ghi có hình phạt bổ sung | 69 |
| Bản ghi có biện pháp khắc phục | 69 |
| Bản ghi chưa có alias công dân | 152 (warning) |

Phân bố theo điều: Điều 6 (75), Điều 7 (65), Điều 12 (4), Điều 13 (23), Điều 14 (13), Điều 18 (24), Điều 32 (72).

Phân bố theo loại xe: xe máy 108, ô tô 165, dùng chung 3.

### 1.2. Kiểm chứng và đánh giá

| Hạng mục | Kết quả |
|---|---:|
| `validate_catalog.py` | 0 lỗi, 1 warning |
| `audit_fines.py` | 276/276 khớp, 0 mismatch |
| `pytest` | 123/123 pass |
| Golden set | 265 câu |
| API — đúng bản ghi/khung tiền/căn cứ | 192/192 |
| API — đúng đoạn và căn cứ thủ tục | 46/46 |
| API — hỏi lại | 19/19 |
| API — từ chối | 8/8 |
| API — câu trả lời thiếu nguồn | 0 |
| API — p95 | 2,0 ms (không log); 12–15 ms (có log) |

Chi tiết lệnh chạy và định nghĩa metric: [`docs/eval-results.md`](eval-results.md).

### 1.3. Kiểm chứng con người

- Hai phiếu `data/catalog/review/nguoi-ra-soat-1.csv` và `nguoi-ra-soat-2.csv` đều có 264 dòng, hiện **0 dòng đã điền**.
- `data/catalog/verified/` đang trống.
- Catalog chỉ được chuyển `verified` sau khi hai người thật rà soát độc lập và `scripts/merge_reviews.py --fine-only` chạy thành công.
- Kết quả AI precheck/spot-check **không thay thế** phiếu người.

---

## 2. Hiện trạng triển khai (as-built)

### 2.1. Backend

- FastAPI tại `src/api/main.py`:
  - `GET /health` kiểm tra catalog.
  - `POST /chat` nhận `question`, `vehicle_type`, `record_id`.
- Router và guardrail tại `src/api/routing.py`.
- Tra cứu, soạn câu trả lời và hướng dẫn nộp phạt tại `src/api/service.py`.
- Hợp đồng API tại `src/api/schemas.py`.
- Catalog đọc từ `data/build/catalog.db` ở chế độ chỉ đọc.
- Câu trả lời mức phạt lấy số tiền và căn cứ từ catalog, không do LLM sinh.
- Nhánh thủ tục dùng BM25/FTS5 trên SQLite, không dùng dense embedding/Chroma.
- Có thể ghi log câu hỏi vào SQLite cục bộ khi đặt `ATGT_QUESTION_LOG_PATH`.

### 2.2. Dữ liệu

- Nguồn sự thật là các file JSONL/JSON trong `data/catalog/`.
- `data/build/catalog.db` là bản chiếu rebuild được, không sửa tay.
- Pipeline: parse → trích xuất → hợp nhất 238/2026 → validate → audit → build SQLite.
- Catalog hiện là ảnh chụp tại 09/11/2026.

### 2.3. Frontend

- Next.js tại `src/web`, chuyển tiếp `/api/chat` và `/api/health` sang FastAPI.
- Thẻ mức phạt đơn: tiền, điểm GPLX, hình phạt bổ sung, biện pháp khắc phục, hướng dẫn nộp phạt/khiếu nại, nguồn, đoạn luật áp dụng.
- Thẻ nhiều vi phạm: danh sách từng hành vi, tổng tiền, tổng điểm, hình phạt bổ sung, hướng dẫn.
- Nút chọn loại xe/phương án hỏi lại gửi lại `record_id` để tra thẳng bản ghi.

### 2.4. Câu hỏi nhiều vi phạm

Đã triển khai tách câu hỏi deterministic:

- Tách theo `và`, `đồng thời`, dấu phẩy/chấm phẩy.
- Không tách dấu phẩy thập phân (`20,5 km/h`).
- Không tách cụm `va chạm`/`va quẹt`.
- Không tách câu có `tai nạn`, vì tai nạn là tình tiết tăng nặng gắn với một hành vi gốc.
- Trả về `violations[]`; `penalty` vẫn là phần tử đầu để tương thích client cũ.
- Mỗi hành vi có `legal_basis` đầy đủ.

Ví dụ đã kiểm chứng:

> Nếu xe gắn máy tống 3 và không đội mũ bảo hiểm cả 3 người, đồng thời còn lạng lách đánh võng thì phải làm như thế nào?

Kết quả: 4 vi phạm `7.2.g`, `7.2.h`, `7.2.i`, `7.9.a`; tổng 9.200.000–11.800.000 đồng; 0 điểm GPLX; tước GPLX 10–12 tháng.

---

## 3. Những gì **chưa** triển khai

Không được mô tả các mục sau như đã làm trong báo cáo:

| Hạng mục | Trạng thái |
|---|---|
| LLM trích xuất slot | Chưa triển khai |
| LLM chọn bản ghi | Chưa triển khai |
| LLM diễn giải câu trả lời | Chưa triển khai |
| Gemini/Groq/Ollama | Chưa cấu hình |
| ChromaDB/dense embedding/RRF | Chưa triển khai |
| So sánh RAG thuần vs structured vs hybrid | Chưa có kết quả |
| Ablation BM25/dense/reranker | Chưa có kết quả |
| Đánh giá người dùng thật | Chưa có |
| Hai người kiểm chứng catalog | Chưa có |
| Thanh toán/nộp phạt trực tuyến | Ngoài phạm vi |
| Ứng dụng mobile native | Chưa có; chỉ có web responsive |
| Kiểm thử E2E bằng trình duyệt tự động | Chưa có |

`docs/project-brief.md` là **bản thiết kế ban đầu**, có phần mô tả LLM/Chroma. Khi viết báo cáo, phải đối chiếu với mục “Hiện trạng triển khai” ở trên, không trích nguyên văn phần thiết kế như thể đã hiện thực.

---

## 4. Bản đồ chương báo cáo → nguồn

| Chương gợi ý | Nội dung | Nguồn chính |
|---|---|---|
| 1. Mở đầu | Bối cảnh, mục tiêu, phạm vi, người dùng | `docs/project-brief.md` mục 1–3; `README.md` |
| 2. Cơ sở pháp lý | Văn bản áp dụng, hiệu lực, sửa đổi 238/2026 | `docs/project-brief.md` mục 5; `data/catalog/README.md` mục 3, 6 |
| 3. Phân tích và thiết kế | Kiến trúc, luồng trả lời, mô hình dữ liệu | `docs/project-brief.md` mục 4, 6, 7; mục 2 tài liệu này |
| 4. Dữ liệu | Catalog, alias, pipeline, kiểm chứng | `docs/project-brief.md` mục 5, 8; `data/catalog/README.md` |
| 5. Triển khai | API, router, service, frontend | `src/api/*`; `src/web/*`; `README.md` |
| 6. Đánh giá | Test, golden set, metric, kết quả | `docs/eval-results.md`; `data/eval/README.md` |
| 7. Demo | Kịch bản, ảnh, câu hỏi mẫu | `docs/demo-script.md` |
| 8. Thảo luận | Quyết định thiết kế, giới hạn, hướng phát triển | `docs/decision-log.md`; mục 3 và 8 tài liệu này |
| 9. Kết luận | Tóm tắt, đóng góp, việc tiếp theo | `docs/project-brief.md` mục 10, 13; `docs/decision-log.md` |

---

## 5. Số liệu được phép trích dẫn

Chỉ trích các số sau khi ghi rõ **ngày 11/11/2026, commit `d857ca6`, snapshot 09/11/2026**:

- 276 bản ghi vi phạm; 264 bản ghi có phạt tiền; 59 quy tắc.
- 56 nhóm alias; 293 alias phrase trong SQLite.
- 23 đoạn thủ tục; 6 nguồn; 31 trích dẫn.
- 265 câu golden set.
- 123 test pass.
- API: 192/192 mức phạt; 46/46 thủ tục; 19/19 hỏi lại; 8/8 từ chối.
- p95 2,0 ms khi chấm golden set không bật log; 12–15 ms khi API demo bật log câu hỏi.

**Không dùng** các số sau như kết quả sản phẩm:

- `47/192` và `96/192` là baseline CLI, không phải API.
- `94/94` trong `docs/ban-giao.md` là snapshot lịch sử tại commit `5de91b1`, không phải hiện tại.
- Các số trong `docs/project-brief.md` phần kế hoạch là mục tiêu, không phải kết quả.

---

## 6. Hình và bảng cần chuẩn bị

| Hình/bảng | Nội dung | Cách tạo |
|---|---|---|
| Hình 1 | Kiến trúc as-built: Web → FastAPI → router → SQLite/FTS5 → composer | Vẽ lại từ mục 2, không dùng sơ đồ Chroma/LLM trong project brief |
| Hình 2 | Pipeline dữ liệu: raw → parsed → amendments → JSONL → SQLite | Dựa trên project brief mục 8 và catalog README |
| Hình 3 | Luồng xử lý `/chat`: chuẩn hóa → detect vehicle → route → penalty/procedure/clarify/refuse | Dựa trên `src/api/service.py` |
| Hình 4 | Sơ đồ trạng thái `answer_type` | 4 trạng thái: penalty, procedure, clarify, refuse |
| Hình 5 | Luồng multi-violation: split → path → record → union sources → tổng hợp | Dựa trên `violation_paths()` và `multi_penalty_response()` |
| Bảng 1 | Thống kê catalog | Mục 1.1 |
| Bảng 2 | Kết quả đánh giá | Mục 1.2, chi tiết ở `eval-results.md` |
| Bảng 3 | So sánh API và CLI baseline | `eval-results.md` mục 7 |
| Ảnh 1–6 | Giao diện đơn, hỏi lại, multi, tổng hợp, thủ tục, từ chối | `demo-script.md` |

---

## 7. Tài liệu cũ cần lưu ý

| Tài liệu | Vấn đề | Cách dùng |
|---|---|---|
| `docs/ban-giao.md` | Số test `94/94`, commit `5de91b1` là snapshot lịch sử | Chỉ dùng cho quy trình kiểm chứng catalog; không trích làm trạng thái hiện tại |
| `docs/project-brief.md` | Mục 4.1–4.3 mô tả LLM/Chroma theo thiết kế | Dùng cho “thiết kế dự kiến”; hiện trạng dùng mục 2 tài liệu này |
| `README.md` | Bảng trạng thái đã có multi-violation nhưng chỉ ở mức tổng quan | Dùng cho giới thiệu; số liệu chi tiết lấy từ tài liệu này |
| `data/eval/README.md` | Có kết quả API; test multi-violation nằm ở `tests/test_api.py` | Dùng làm nguồn phụ; số hiện tại lấy từ `eval-results.md` |

---

## 8. Giới hạn phải nêu trong báo cáo

1. Catalog `draft`, chưa có hai người kiểm chứng.
2. Số tiền đã audit tự động 276/276 nhưng chưa thay thế rà soát pháp lý thủ công.
3. Hệ thống deterministic, chưa dùng LLM; chưa có so sánh với RAG/LLM.
4. Multi-violation dựa trên mẫu câu và guardrail, không phải NLU tổng quát.
5. Câu quá tự do, thiếu dữ kiện hoặc ngoài phạm vi sẽ hỏi lại/từ chối.
6. 152 bản ghi chưa có alias công dân; một số cách nói tự nhiên có thể không khớp.
7. Chưa có đánh giá người dùng thật; golden set do nhóm biên soạn nên có nguy cơ overfit.
8. Chưa có kiểm thử E2E trình duyệt tự động; giao diện mới được typecheck và kiểm tra qua API/proxy.
9. Chưa hỗ trợ Điều 17 và các điều vận tải 20–24; xe buýt/xe máy chuyên dùng ngoài phạm vi.
10. Điểm b khoản 9a Điều 32 hoãn đến 01/01/2028, chưa có trong catalog.

---

## 9. Checklist bàn giao

### Bắt buộc

- [ ] Repo và quyền truy cập.
- [ ] Commit `d857ca6` hoặc commit mới hơn đã ghi rõ.
- [ ] Đề cương/format báo cáo của môn học hoặc đơn vị.
- [ ] Deadline, giới hạn trang, ngôn ngữ, định dạng trích dẫn.
- [ ] Danh sách chương bắt buộc.
- [ ] Ảnh giao diện (xem `demo-script.md`).
- [ ] Xác nhận có được dùng log/dữ liệu demo hay không.

### Khi có kết quả kiểm chứng

- [ ] Hai phiếu rà soát đã điền.
- [ ] Snapshot `data/catalog/verified/`.
- [ ] Báo cáo merge review.
- [ ] DB build từ snapshot `verified`.
- [ ] Kết quả eval/test sau khi chuyển `verified`.

### Trước khi nộp

- [ ] Mọi số liệu có ngày + commit.
- [ ] Không có câu nào mô tả LLM/RAG như đã triển khai.
- [ ] Có mục giới hạn.
- [ ] Có disclaimer “không thay thế tư vấn pháp lý”.
- [ ] Hình/bảng có nguồn hoặc caption.
- [ ] Tài liệu tham khảo trích đúng văn bản pháp luật.

---

## 10. Câu hỏi cần chốt với chủ dự án

1. Báo cáo phục vụ môn học, demo, hay nghiệm thu sản phẩm?
2. Có yêu cầu chương “so sánh kiến trúc/RAG vs LLM” không? Nếu có, phải chạy thêm thực nghiệm trước.
3. Có cần phụ lục bảng 276 bản ghi hoặc 265 câu golden set không?
4. Có được dùng ảnh chụp giao diện và log demo không?
5. Có yêu cầu về định dạng trích dẫn pháp lý (APA, IEEE, số hiệu văn bản)?
6. Có cần mô tả phần kiểm chứng con người không, hay chỉ mô tả kiểm chứng tự động?
7. Thời gian nộp và thời gian demo?
8. Ai trả lời các câu hỏi pháp lý phát sinh khi viết?

---

## 11. Gợi ý dàn ý báo cáo

1. **Mở đầu:** lý do chọn đề tài, mục tiêu, đối tượng, phạm vi.
2. **Cơ sở lý thuyết và pháp lý:** chatbot tra cứu, grounded answering, văn bản 168/2024 + 238/2026, trừ điểm GPLX.
3. **Phân tích yêu cầu:** câu hỏi điển hình, yêu cầu đúng số tiền/đúng căn cứ/không bịa, yêu cầu phi chức năng.
4. **Thiết kế hệ thống:** kiến trúc as-built, mô hình dữ liệu, luồng xử lý, guardrail.
5. **Xây dựng dữ liệu:** pipeline, catalog, alias, kiểm chứng.
6. **Triển khai:** backend, frontend, multi-violation, logging.
7. **Đánh giá:** golden set, metric, kết quả, phân tích lỗi.
8. **Demo:** kịch bản, ảnh, câu hỏi mẫu.
9. **Thảo luận:** quyết định, giới hạn, so sánh với hướng LLM/RAG (nếu có).
10. **Kết luận và hướng phát triển:** kiểm chứng người, mở rộng catalog, LLM parser, E2E.

---

## 12. Quy tắc trích dẫn nội bộ

- Tham chiếu code: `đường/dẫn/tệp.py`, tên hàm, không chỉ nói “module xử lý”.
- Tham chiếu dữ liệu: `data/...`, kèm ngày snapshot.
- Tham chiếu kết quả: `docs/eval-results.md`, kèm commit.
- Tham chiếu quyết định: `docs/decision-log.md`, mã `D-xxx`.
- Không trích số liệu từ chat/trí nhớ; phải chạy lại hoặc lấy từ tài liệu có ngày.
