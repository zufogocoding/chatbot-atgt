# Nhật ký quyết định thiết kế

**Mục đích:** ghi lại các quyết định đã chốt, lý do và hệ quả, để người viết báo cáo dùng cho chương “Phương pháp”, “Thảo luận” và “Hướng phát triển”.

**Ngày tổng hợp:** 11/11/2026  
**Commit tham chiếu:** `d857ca6`  
**Trạng thái catalog:** `draft`

---

## Cách đọc

Mỗi quyết định có:

- **Bối cảnh:** vấn đề cần giải quyết.
- **Quyết định:** lựa chọn đã chốt.
- **Lý do:** vì sao chọn.
- **Hệ quả:** điều phải chấp nhận.
- **Bằng chứng:** nơi kiểm tra trong repo.

Mã `D-xxx` dùng để trích dẫn trong báo cáo.

---

## D-001 — JSONL là nguồn sự thật, SQLite là bản chiếu

**Bối cảnh:** cần lưu catalog có thể review, diff và rebuild.

**Quyết định:** dữ liệu gốc nằm trong `data/catalog/consolidated/*.jsonl` và `data/catalog/aliases.json`; `data/build/catalog.db` chỉ là bản build lại.

**Lý do:**

- JSONL dễ diff khi văn bản luật thay đổi.
- SQLite phù hợp truy vấn/FTS5 nhưng không nên là nơi sửa tay.
- Có thể tái lập cùng một DB từ cùng một commit.

**Hệ quả:**

- Mọi sửa dữ liệu phải sửa JSONL rồi chạy `scripts/build_db.py`.
- Không sửa trực tiếp `catalog.db`.

**Bằng chứng:** `data/catalog/README.md` mục 5; `scripts/build_db.py`.

---

## D-002 — Số tiền và căn cứ chỉ lấy từ catalog

**Bối cảnh:** câu trả lời pháp lý cần đúng số tiền và truy vết được; LLM có thể bịa.

**Quyết định:** phần mức phạt dùng tra cứu có cấu trúc; template soạn câu trả lời từ bản ghi; LLM không được sinh số tiền hoặc điều luật.

**Lý do:**

- Đúng số tiền là yêu cầu sống còn.
- Mỗi con số phải gắn với `source_quote` và `legal_basis`.
- Có thể chạy offline, không phụ thuộc provider.

**Hệ quả:**

- Câu trả lời chỉ tốt trong phạm vi catalog.
- Hành vi chưa có bản ghi sẽ bị hỏi lại/từ chối, không suy đoán.

**Bằng chứng:** `src/api/service.py` (`penalty_response`, `make_penalty`); `src/api/routing.py`.

---

## D-003 — Phạm vi: xe máy và ô tô cá nhân

**Bối cảnh:** đề tài hướng đến người dân, không phải nghiệp vụ CSGT.

**Quyết định:**

- Trong phạm vi: xe máy (mô tô, xe gắn máy), ô tô.
- Xe khách, xe tải, xe đầu kéo được xử lý như ô tô **cho các hành vi đã có trong catalog**.
- Ngoài phạm vi: xe buýt, xe đạp, xe thô sơ, xe máy chuyên dùng, người đi bộ, vận tải kinh doanh (Điều 20–24), tra phạt nguội theo biển số.

**Lý do:**

- Giữ catalog và guardrail trong phạm vi kiểm chứng được.
- Tránh trả lời sai cho nhóm phương tiện có quy định riêng.

**Hệ quả:**

- Câu hỏi xe buýt/xe máy chuyên dùng bị từ chối.
- Câu hỏi thuần vận tải kinh doanh bị từ chối dù xe tải/xe khách vẫn tra được hành vi giao thông chung.

**Bằng chứng:** `docs/project-brief.md` mục 3; `tests/test_api.py` (`test_commercial_vehicle_questions_route_like_cars`).

---

## D-004 — Runtime deterministic, chưa dùng LLM

**Bối cảnh:** P0 cần demo ổn định, không phụ thuộc API key/chi phí/mạng.

**Quyết định:** router, alias, speed/alcohol bands, guardrail và multi-violation đều deterministic; chưa gọi LLM.

**Lý do:**

- Kết quả lặp lại được, dễ test.
- Không có nguy cơ LLM bịa căn cứ.
- Chạy được offline.

**Hệ quả:**

- Chưa xử lý tốt câu tự do phức tạp ngoài mẫu.
- Chưa có so sánh định lượng với LLM/RAG.
- Trong báo cáo phải mô tả đây là hệ deterministic, không phải “AI chatbot dùng LLM”.

**Bằng chứng:** `src/api/routing.py`; `src/api/service.py`; `README.md`.

---

## D-005 — LLM chỉ dùng làm parser có kiểm soát (chưa triển khai)

**Bối cảnh:** câu hỏi tự do có thể phức tạp hơn rule hiện tại.

**Quyết định:** nếu bổ sung LLM, chỉ dùng để trích xuất cấu trúc (hành vi, loại xe, số người, tốc độ, nồng độ cồn) thành JSON; sau đó đối chiếu catalog; nếu không chắc thì fallback deterministic hoặc hỏi lại.

**Lý do:**

- Giữ nguyên nguyên tắc “số tiền/căn cứ từ catalog”.
- Dễ validate output bằng schema.
- Có thể tắt LLM mà hệ vẫn chạy.

**Hệ quả:**

- Cần API key, test prompt, eval riêng trước khi bật.
- Chưa có trong bản hiện tại.

**Bằng chứng:** `docs/project-brief.md` mục 4.3 (thiết kế); `src/api/routing.py` (hiện trạng).

---

## D-006 — Thiếu dữ kiện thì hỏi lại, không đoán

**Bối cảnh:** cùng một hành vi có nhiều khung phạt theo loại xe, dung tích, mức vượt, vai trò.

**Quyết định:** trả `clarify` khi thiếu loại xe, dung tích, mức vượt, nồng độ cồn, vai trò người ngồi trên xe. Nếu có thể, kèm nút chọn khung phạt có số tiền thật.

**Lý do:**

- Đoán sai gây hậu quả pháp lý.
- Nút chọn giúp người dân không phải tự mô tả lại.

**Hệ quả:**

- Một số câu phổ biến cần thêm một bước bấm.
- API trả `options`/`related`; client gửi `record_id` để tra thẳng.

**Bằng chứng:** `src/api/service.py` (`clarify`, `vehicle_penalty_choices`, `clarification_options`); `tests/test_api.py`.

---

## D-007 — “Xe gắn máy” không tự động map sang khung mô tô ≤125 cm³

**Bối cảnh:** “xe gắn máy” thường là xe ≤50 cm³; khung GPLX hạng A1 chỉ áp dụng cho mô tô ≤125 cm³.

**Quyết định:** giữ `clarification` `motorcycle_class` với các lựa chọn dung tích; không map thẳng “xe gắn máy” sang `18.5.a`.

**Lý do:**

- Tránh áp sai khung phạt.
- Người dùng có thể nói “xe gắn máy” nhưng thực tế đi mô tô.

**Hệ quả:**

- Câu “Xe gắn máy 50cc không có bằng lái” hỏi lại dung tích/thông tin trước khi trả.
- Cần bổ sung alias rõ hơn nếu muốn giảm số lần hỏi lại.

**Bằng chứng:** `src/api/routing.py` (`motorcycle_class`); `tests/test_api.py` (`test_motorcycle_class_clarification_offers_engine_choices`).

---

## D-008 — Tai nạn là tình tiết tăng nặng, không tách thành hai vi phạm

**Bối cảnh:** câu “vượt đèn đỏ gây tai nạn” có thể bị hiểu là vượt đèn đỏ + gây tai nạn.

**Quyết định:** dùng bản ghi tăng nặng (`10.a`/`10.b`); `violation_paths()` trả `[]` khi câu có “tai nạn”.

**Lý do:**

- Tránh cộng trùng khung gốc và khung tăng nặng.
- Phản ánh cách điều luật gộp hành vi và hậu quả.

**Hệ quả:**

- Câu tai nạn chỉ trả một bản ghi.
- Nếu người dùng muốn tách hành vi gốc, cần hỏi rõ.

**Bằng chứng:** `src/api/routing.py` (`violation_paths`); `tests/test_api.py` (`test_accident_question_remains_one_aggravated_violation`).

---

## D-009 — “Tống 3” là tổng 3 người; “chở 3 người” là 3 người được chở

**Bối cảnh:** tiếng Việt thường nói “tống 3” để chỉ tổng số người trên xe, nhưng “chở 3 người” có thể hiểu là 3 hành khách.

**Quyết định:**

- “Tống 3” / “3 người trên xe” → `7.2.g` (chở 02 người, tức tài xế + 2).
- “Chở 3 người” → `7.3.b` (chở 3 người, tức tài xế + 3).
- Trường hợp mơ hồ → hỏi lại số người.

**Lý do:**

- Hai cách nói dẫn đến hai khung khác nhau.
- Không nên tự suy diễn theo hướng tăng nặng.

**Hệ quả:**

- Cần giải thích trong báo cáo và trong demo.
- Nếu người dùng nói “tống 3” nhưng thực tế chở 3 khách, họ cần cung cấp lại.

**Bằng chứng:** `src/api/routing.py` (`_part_violation_paths`); `tests/test_api.py` (`test_passenger_count_question_offers_both_bands`).

---

## D-010 — Xử lý “không đội mũ bảo hiểm” theo vai trò

**Bối cảnh:** cùng câu “không đội mũ” có thể là người lái, người được chở hoặc cả hai.

**Quyết định:**

- Câu đơn, không rõ vai trò → `clarify` `helmet_role`.
- Câu có “cả 3 người” → `7.2.h` (người lái) + `7.2.i` (người được chở).
- Trong câu nhiều vi phạm, “không đội mũ” không nói rõ ai → mặc định người lái `7.2.h`; không tự quy kết thêm cho người được chở.
- Có cue “người ngồi sau/người được chở” → `12.5.b` hoặc `7.2.i` theo catalog.
- Nếu câu hỏi nói rõ vai trò (ví dụ “người lớn ngồi sau… thì người chở bị phạt”), giữ đúng một bản ghi theo vai trò; không cộng thêm mặc định người lái.

**Lý do:**

- Tránh bỏ sót hành vi trong câu ghép.
- Tránh tự buộc tội người được chở khi câu không nói.

**Hệ quả:**

- Câu “chở 3 người, không đội mũ, lạng lách” trả 3 vi phạm, trong đó mũ chỉ tính người lái.
- Nếu người dùng muốn tính cả người được chở, cần nói “cả 3 người” hoặc “người ngồi sau”.

**Bằng chứng:** `src/api/routing.py` (`HELMET`, `_part_violation_paths`); `tests/test_api.py` (`test_helmet_in_compound_question_defaults_to_driver`, `test_compound_passenger_helmet_and_weaving_question`, `test_passenger_helmet_question_about_driver_returns_one_violation`).

---

## D-011 — Tách câu nhiều vi phạm bằng rule deterministic

**Bối cảnh:** người dùng có thể hỏi một câu chứa nhiều hành vi.

**Quyết định:**

- Tách theo `và`, `đồng thời`, dấu phẩy/chấm phẩy.
- Không tách dấu phẩy thập phân (`20,5 km/h`).
- Không tách `va chạm`/`va quẹt`.
- Không tách câu có “tai nạn”.
- Dedupe theo `record_id`; chỉ trả multi khi có ≥2 bản ghi.
- Tổng tiền chỉ hiển thị khi mọi khung là khoảng cố định, không có `per_person`/trần.

**Lý do:**

- Không phụ thuộc LLM.
- Dễ test, dễ giải thích.
- Tránh các lỗi tách số thập phân và tai nạn.

**Hệ quả:**

- Câu quá phức tạp hoặc dùng từ nối khác có thể không tách hết.
- Cần bổ sung test khi thêm mẫu câu mới.

**Bằng chứng:** `src/api/routing.py` (`MULTI_SPLIT`, `violation_paths`); `src/api/service.py` (`multi_penalty_response`).

---

## D-012 — Hợp đồng multi-violation

**Bối cảnh:** client cũ chỉ đọc `penalty`; cần thêm nhiều vi phạm mà không phá vỡ.

**Quyết định:**

- Thêm `violations: list[Penalty]`.
- Giữ `penalty` là phần tử đầu tiên.
- Thêm `legal_basis` cho từng `Penalty`.
- `sources` là hợp của các bản ghi; hướng dẫn nộp phạt/khiếu nại chỉ gọi một lần.

**Lý do:**

- Tương thích ngược.
- Client mới có thể render danh sách; client cũ vẫn có dữ liệu.
- Tránh lặp nguồn và lặp hướng dẫn.

**Hệ quả:**

- Frontend phải kiểm tra `violations.length > 1` trước khi render thẻ đơn.
- Các trường `penalty` và `violations[0]` trùng nhau.

**Bằng chứng:** `src/api/schemas.py`; `src/web/app/answer.tsx` (`MultiPenaltyDetails`); `src/web/lib/contracts.ts`.

---

## D-013 — Catalog chỉ `verified` khi có hai người thật

**Bối cảnh:** số tiền pháp lý cần kiểm chứng độc lập.

**Quyết định:** catalog giữ `draft` cho đến khi hai người rà soát khác nhau điền đủ phiếu và `merge_reviews.py --fine-only` chạy thành công.

**Lý do:**

- AI precheck/spot-check có thể bỏ sót.
- Hai người độc lập giảm lỗi hệ thống.
- Có snapshot/report/tag để truy vết.

**Hệ quả:**

- Báo cáo hiện tại không được nói “đã kiểm chứng pháp lý”.
- `data/catalog/verified/` đang trống; hai phiếu đang 0 dòng điền.

**Bằng chứng:** `docs/ban-giao.md`; `data/catalog/review/README.md`; `scripts/merge_reviews.py`.

---

## D-014 — Log câu hỏi là tùy chọn, cục bộ, có che dữ liệu nhạy cảm

**Bối cảnh:** cần quan sát câu hỏi thực tế nhưng không muốn thu thập dữ liệu cá nhân.

**Quyết định:** chỉ ghi khi đặt `ATGT_QUESTION_LOG_PATH`; lưu `question`, `answer_type`, `record_id`, `reason`, `timestamp`; che email, số điện thoại, chuỗi số dài và biển số theo mẫu; không lưu IP/tài khoản/thiết bị.

**Lý do:**

- Đủ để cải thiện alias/guardrail.
- Giảm rủi ro riêng tư.
- Không ảnh hưởng nếu không bật.

**Hệ quả:**

- Tên/địa chỉ viết tự do vẫn có thể lọt vào câu hỏi.
- Không dùng log thật trong báo cáo nếu chưa ẩn danh.

**Bằng chứng:** `src/api/question_log.py`; `README.md` mục demo; `tests/test_api.py` (`test_question_log_records_resolved_answer_and_masks_identifiers`).

---

## D-015 — Tài liệu phải phân biệt “thiết kế” và “as-built”

**Bối cảnh:** project brief mô tả LLM/Chroma; runtime thực tế deterministic.

**Quyết định:** mọi tài liệu bàn giao báo cáo phải có mục “hiện trạng triển khai” riêng; không trích thiết kế như kết quả.

**Lý do:**

- Tránh báo cáo mô tả sai hệ thống.
- Tránh hứa hẹn tính năng chưa có.
- Giúp người phản biện đánh giá đúng.

**Hệ quả:**

- `docs/report-handoff.md` là điểm vào bắt buộc.
- `docs/project-brief.md` chỉ dùng cho phần thiết kế.

**Bằng chứng:** `docs/report-handoff.md` mục 2–3; `docs/project-brief.md`.

---

## Các quyết định còn mở

| Mã | Vấn đề | Điều kiện để chốt |
|---|---|---|
| O-001 | Có bật LLM parser không? | Có API key, prompt eval, fallback deterministic |
| O-002 | Mở rộng Điều 17/20–24? | Có nguồn, có người kiểm chứng, có golden case |
| O-003 | Thêm dense retrieval/Chroma? | Có thực nghiệm so sánh với BM25/FTS5 |
| O-004 | Thêm E2E trình duyệt? | Có Chrome/Playwright trong CI |
| O-005 | Chuyển catalog sang `verified`? | Hai phiếu người điền đủ, merge thành công |
| O-006 | Có khảo sát người dùng? | Có kế hoạch và người tham gia |

---

## Cách dùng trong báo cáo

- **Chương Phương pháp:** D-001, D-002, D-004, D-006, D-011.
- **Chương Thiết kế:** D-003, D-007, D-008, D-009, D-010, D-012.
- **Chương Đánh giá:** D-013, D-014.
- **Chương Thảo luận:** D-004, D-005, D-015, các quyết định còn mở.
- **Chương Hướng phát triển:** O-001 đến O-006.

Khi trích, ghi mã quyết định (ví dụ “theo D-011”) để người đọc tra lại.
