# Kết quả kiểm thử và đánh giá

**Ngày chạy:** 11/11/2026  
**Commit:** `d857ca6`  
**Snapshot dữ liệu:** 09/11/2026  
**Môi trường đo:** Python 3.14.10, pytest 9.1.1, Node.js 22.23.1 (máy cục bộ)

Tài liệu này ghi lại kết quả có thể tái lập để dùng trong báo cáo. Khi trích dẫn, luôn ghi kèm ngày và commit.

---

## 1. Phạm vi đánh giá

Đánh giá gồm bốn lớp:

1. **Tính toàn vẹn catalog:** validate schema, alias, căn cứ và khung tiền.
2. **Đối chiếu khung tiền:** audit tự động 276 bản ghi với điều/khoản/điểm được dẫn.
3. **Kiểm thử chức năng:** pytest cho API, router, guardrail, multi-violation và frontend contract.
4. **Golden set:** chấm 265 câu qua HTTP API.

Không nằm trong phạm vi:

- Đánh giá người dùng thật.
- Đánh giá ngữ nghĩa câu trả lời thủ tục bằng người đọc.
- So sánh với LLM/RAG thuần.
- Kiểm thử tải hoặc production.
- Kiểm thử E2E trình duyệt tự động.

---

## 2. Kết quả tổng hợp

| Lớp đánh giá | Kết quả |
|---|---:|
| `validate_catalog.py` | 0 lỗi, 1 warning |
| `audit_fines.py` | 276/276 khớp, 0 mismatch |
| `pytest` | 123/123 pass |
| Golden set — đúng bản ghi mức phạt | 192/192 (100%) |
| Golden set — đúng cả min/max | 192/192 (100%) |
| Golden set — đúng căn cứ mức phạt | 192/192 (100%) |
| Golden set — đúng đoạn và căn cứ thủ tục | 46/46 (100%) |
| Golden set — hỏi lại đúng loại | 19/19 (100%) |
| Golden set — từ chối đúng loại | 8/8 (100%) |
| Golden set — câu trả lời thiếu nguồn | 0 |
| Độ trễ HTTP p95 | 2,0 ms (không log); 12–15 ms (có log) |

**Lưu ý:** đây là kết quả trên bộ golden set do nhóm biên soạn, không phải đánh giá trên người dùng thật.

---

## 3. Lệnh chạy và output

### 3.1. Validate catalog

```bash
python3 scripts/validate_catalog.py
```

Output rút gọn:

```text
records: 276
penalty rules: 59
fine records checked: 264
source quotes checked: 276
errors: 0
warnings: 1
  WARNING 152 records have no citizen alias
```

Warning không chặn build. Đây là nợ dữ liệu: 152 bản ghi chưa có cách nói công dân, nên một số câu hỏi tự nhiên có thể không khớp alias.

### 3.2. Audit khung tiền

```bash
python3 scripts/audit_fines.py
```

Output:

```text
Audited 276 records against cited provisions. Mismatches: 0
```

### 3.3. Kiểm thử chức năng

```bash
python3 -m pytest -q
```

Output:

```text
123 passed
```

Trong lần rà soát tài liệu ngày 11/11/2026, golden set phát hiện ca `gs-012` (“Người lớn ngồi sau xe máy không cài quai mũ thì người chở bị phạt mức nào?”) trả 2 vi phạm thay vì 1. Nguyên nhân là mặc định “không đội mũ” cho người lái được cộng thêm dù câu hỏi đã nêu rõ người ngồi sau và hỏi về người chở. Đã sửa tại commit `d857ca6` và thêm test `test_passenger_helmet_question_about_driver_returns_one_violation`; test tăng từ 122 lên 123. Đây là ví dụ golden set bắt được regression ngoài các ca multi-violation.

### 3.4. Golden set qua API

Chạy API tạm ở cổng 8100 để không ảnh hưởng demo:

```bash
python3 -m uvicorn src.api.main:app \
  --host 127.0.0.1 --port 8100 --no-access-log &

python3 scripts/evaluate_dataset.py \
  --api-url http://127.0.0.1:8100/chat
```

Output:

```text
Dataset checks passed: 276 records, 23 chunks, 265 cases
Đúng bản ghi mức phạt: 192/192 (100.0%)
Đúng cả min/max: 192/192 (100.0%)
Đúng căn cứ mức phạt: 192/192 (100.0%)
Đúng đoạn và căn cứ thủ tục: 46/46 (100.0%)
Hỏi lại: 19/19 (100.0%)
Từ chối: 8/8 (100.0%)
Thủ tục — số liệu khớp: 46/46
Thủ tục — độ phủ từ khóa trung bình: 87.4%
Thủ tục — ca dưới 60% từ khóa: 0/46
Thủ tục — trích dẫn hợp lệ: 46/46
Câu trả lời thiếu nguồn: 0
Độ trễ HTTP p95: 2.0 ms
```

Lần chạy trên dùng API tạm cổng 8100, không bật log câu hỏi. Khi chạy API demo cổng 8000 có `ATGT_QUESTION_LOG_PATH`, hai lần đo cho p95 12,5 ms và 14,9 ms; phần tăng chủ yếu đến từ ghi log SQLite. Đây là đo cục bộ, không phải cam kết hiệu năng production.

Sau khi đo, dừng API tạm:

```bash
kill %1
```

---

## 4. Ý nghĩa metric

| Metric | Cách hiểu | Không nên suy diễn |
|---|---|---|
| Đúng bản ghi | `record_id` trả về trùng `expected_violation_id` | Không đo mức độ tự nhiên của câu trả lời |
| Đúng min/max | Cả khung tiền và trần (nếu có) trùng nhãn | Không đo hình phạt bổ sung/khắc phục |
| Đúng căn cứ | Điều/khoản/điểm trùng nhãn | Không thay thế kiểm tra văn bản gốc |
| Hỏi lại đúng loại | `answer_type = clarify` đúng ca | Không đo nội dung câu hỏi lại có dễ hiểu không |
| Từ chối đúng loại | `answer_type = refuse` đúng ca | Không đo mức độ hữu ích của lời từ chối |
| Thủ tục recall@5 | Đoạn đúng nằm trong 5 kết quả BM25 đầu | Không đo chất lượng câu trả lời cuối |
| Độ phủ từ khóa | Tỷ lệ từ khóa/số liệu kỳ vọng xuất hiện trong câu trả lời | Heuristic từ vựng, không phải đánh giá ngữ nghĩa |
| Trích dẫn hợp lệ | Mọi trích dẫn trong câu trả lời trỏ tới nguồn có thật | Không bảo đảm nguồn được diễn giải đúng |
| p95 | 95% request có độ trễ ≤ giá trị | Đo cục bộ, không phải tải production |

---

## 5. Kiểm thử chức năng theo nhóm

`tests/test_api.py` có 123 test. Các nhóm chính:

| Nhóm | Test tiêu biểu | Điều được chứng minh |
|---|---|---|
| Health/OpenAPI | `test_health_and_openapi` | API khởi động, `/chat` có trong OpenAPI |
| Log câu hỏi | `test_question_log_records_resolved_answer_and_masks_identifiers` | Log đúng kết quả, che email/số điện thoại/biển số |
| Biên mức phạt | `test_penalty_boundaries_and_sources` | Đúng bản ghi, đúng min/max, có nguồn |
| Phạt tổ chức | `test_organization_fine` | Trả cả khung cá nhân và tổ chức |
| Phạt theo người/trừ điểm | `test_per_person_fine_and_licence_point_tiers` | `per_person`, trần, nhiều mức điểm |
| Đoạn luật | `test_penalty_includes_legal_quote` | `source_quote` có trong kết quả |
| Hướng dẫn nộp phạt | `test_penalty_includes_payment_and_complaint_guidance` | Có hạn nộp, nơi nộp, thời hiệu khiếu nại |
| So sánh loại xe | `test_related_vehicle_and_option_selection` | `related` và chọn `record_id` hoạt động |
| Chọn phương án | `test_option_selection_requires_valid_record_and_vehicle` | Chặn record không tồn tại/sai loại xe |
| Xem trước mức phạt | `test_vehicle_question_previews_both_fines_before_asking` | Hỏi loại xe kèm 2 mức tiền |
| Câu phổ biến | `test_common_phrasings`, `test_common_vehicle_unspecified_questions_show_amounts` | Alias và câu hỏi thiếu loại xe |
| Số người | `test_passenger_count_question_offers_both_bands` | Phân biệt 2 người/3 người |
| Đổi chủ xe | `test_owner_change_questions_answer_directly` | Điều 32 trả lời trực tiếp |
| Xe gắn máy | `test_motorcycle_class_clarification_offers_engine_choices` | Hỏi dung tích trước khi chọn khung |
| Người được chở | `test_passenger_is_a_separate_subject` | Điều 12 tách khỏi người lái |
| Mũ bảo hiểm theo vai trò | `test_passenger_helmet_question_about_driver_returns_one_violation` | Câu hỏi về người chở chỉ trả một vi phạm `7.2.i` |
| Guardrail | `test_guardrails_do_not_return_amount` | Không trả tiền khi thiếu căn cứ/ngoài phạm vi |
| Multi-violation | `test_two_independent_violations_return_both_penalties` | 2 vi phạm, tổng tiền/điểm |
| Multi-violation | `test_decimal_speed_in_compound_question_is_not_split_at_comma` | Không tách `20,5 km/h` |
| Multi-violation | `test_helmet_in_compound_question_defaults_to_driver` | Câu ghép mặc định người lái |
| Multi-violation | `test_compound_passenger_helmet_and_weaving_question` | Câu 4 vi phạm mẫu |
| Multi-violation | `test_multi_violation_does_not_mistake_dong_thoi_con_for_alcohol` | Không nhầm “đồng thời còn” với “thổi cồn” |
| Tai nạn | `test_accident_question_remains_one_aggravated_violation` | Không tách tai nạn thành 2 vi phạm |
| Xe thương mại | `test_commercial_vehicle_questions_route_like_cars` | Xe khách/tải/đầu kéo đi theo nhánh ô tô |
| Điều 32 mới | `test_new_article_32_routes` | Các điểm 238/2026 đã có route |
| Catalog thiếu | `test_missing_catalog_returns_503_without_creating_a_file` | API trả 503, không tạo DB rỗng |

---

## 6. Case study: câu hỏi nhiều vi phạm

Câu hỏi:

> Nếu xe gắn máy tống 3 và không đội mũ bảo hiểm cả 3 người, đồng thời còn lạng lách đánh võng thì phải làm như thế nào?

Kết quả API:

| Hành vi | Record | Khung tiền | Điểm | Hình phạt bổ sung |
|---|---|---:|---:|---|
| Chở 02 người | `nd168-d7-k2-g` | 400.000–600.000 | 0 | — |
| Người lái không đội mũ | `nd168-d7-k2-h` | 400.000–600.000 | 0 | — |
| Chở người không đội mũ | `nd168-d7-k2-i` | 400.000–600.000 | 0 | — |
| Lạng lách, đánh võng | `nd168-d7-k9-a` | 8.000.000–10.000.000 | 0 | Tước GPLX 10–12 tháng |

Tổng hợp:

- Tổng mức phạt tiền: **9.200.000–11.800.000 đồng**.
- Tổng trừ điểm GPLX: **0 điểm**.
- Hình phạt bổ sung: tước quyền sử dụng GPLX **10–12 tháng**.

Test tương ứng: `test_compound_passenger_helmet_and_weaving_question`.

Điểm cần nói trong báo cáo:

- Đây là tách vi phạm deterministic, không phải LLM sinh câu trả lời.
- Tổng tiền là **cộng các khung**, chỉ hiển thị khi tất cả khung là khoảng cố định, không có `per_person`/trần.
- Mỗi hành vi vẫn giữ căn cứ riêng.

---

## 7. API và CLI baseline

Có hai đường chấm khác nhau, không được trộn số:

| Đường chấm | Cách chạy | Kết quả chính |
|---|---|---|
| API | `evaluate_dataset.py --api-url ...` | 192/192 bản ghi, 192/192 min/max, 192/192 căn cứ |
| CLI baseline | `evaluate_dataset.py` (không có `--api-url`) | recall@5 96/192, trả lời đúng 47/192, từ chối 0/8 |

Giải thích:

- CLI dùng `scripts/query_catalog.py`, không đi qua router/guardrail/clarification của API.
- Vì vậy CLI thấp hơn không có nghĩa là API thấp.
- Trong báo cáo, nếu chỉ chọn một con số sản phẩm, dùng **API 192/192** và ghi rõ là golden set nội bộ.
- Nếu muốn mô tả CLI, gọi đúng là “baseline tham chiếu”, không gọi là kết quả cuối.

---

## 8. Những gì chưa đo

1. **Chất lượng ngữ nghĩa của câu trả lời thủ tục:** mới đo độ phủ từ khóa và trích dẫn, chưa có người đọc chấm.
2. **Độ hiểu của người dân:** chưa có khảo sát người dùng.
3. **Câu hỏi tự do ngoài golden set:** chưa đo tỷ lệ hỏi lại/từ chối trên dữ liệu thật.
4. **Multi-violation ngoài các mẫu đã test:** chưa có bộ sinh câu tự động.
5. **Tải và độ ổn định:** p95 2,0 ms khi không log và 12–15 ms khi bật log là đo cục bộ, chưa phải production.
6. **Trình duyệt:** chưa có E2E; giao diện mới được typecheck và kiểm tra qua API/proxy.
7. **Kiểm chứng pháp lý:** audit tự động 276/276 không thay thế hai người rà soát.

---

## 9. Cách trích số liệu vào báo cáo

Nên viết:

> Trên golden set 265 câu, tại commit `d857ca6` ngày 11/11/2026, API đạt 192/192 ca mức phạt đúng bản ghi, khung tiền và căn cứ; 46/46 ca thủ tục đúng đoạn và căn cứ; 19/19 ca hỏi lại và 8/8 ca từ chối. Độ trễ p95 cục bộ là 2,0 ms khi chấm golden set không bật log, và 12–15 ms khi API demo bật log câu hỏi.

Không nên viết:

> Hệ thống chính xác 100% mọi câu hỏi của người dân.

hoặc:

> Chatbot đã được kiểm chứng pháp lý.

Lý do: golden set là nội bộ, catalog vẫn `draft`, chưa có hai người rà soát và chưa có đánh giá người dùng thật.

---

## 10. Tái lập nhanh

```bash
cd /home/trongzufo/pj/chatbot-atgt

python3 scripts/validate_catalog.py
python3 scripts/audit_fines.py
python3 -m pytest -q

python3 -m uvicorn src.api.main:app \
  --host 127.0.0.1 --port 8100 --no-access-log &
python3 scripts/evaluate_dataset.py \
  --api-url http://127.0.0.1:8100/chat
```

Nếu kết quả khác, ghi lại commit, ngày, phiên bản Python và output thực tế; không sửa số trong báo cáo cho khớp tài liệu cũ.
