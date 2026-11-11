# Golden set và baseline

[golden.jsonl](golden.jsonl) chứa 265 câu hỏi biên soạn cho snapshot 09/11/2026. Các nhãn được lưu cố định để phát hiện thay đổi khi chạy lại, với khung tiền lấy từ kết quả đối chiếu theo điều, khoản, điểm.

| Nhóm | Số câu |
|---|---:|
| Tra mức phạt xe máy | 79 |
| Tra mức phạt ô tô | 82 |
| Thủ tục nộp phạt và khiếu nại | 46 |
| Thiếu thông tin và ngoài phạm vi | 27 |
| Không dấu và teencode | 31 |

- `expected_answer_type` nhận `penalty`, `procedure`, `clarify` hoặc `refuse`.
- Ca mức phạt có `expected_violation_id`, `expected_legal_basis`, `expected_fine` và đối tượng áp dụng khung tiền. Cảnh cáo có cặp 0/0. Bản ghi chỉ có hình thức xử phạt khác có cặp null/null.
- Ca phạt theo người (Điều 32 khoản 5–6) có thêm `expected_fine_unit = "per_person"` và `expected_fine_cap`; ca có khung tổ chức có thể thêm `expected_fine_org_cap`.
- Ca thủ tục có ID đoạn nguồn, căn cứ và các ý cần có trong câu trả lời.
- Ca hỏi lại hoặc từ chối ghi thông tin cần làm rõ hoặc lý do từ chối trong `expected_reason`.

Chạy từ thư mục gốc dự án.

```bash
python3 scripts/validate_catalog.py
python3 scripts/audit_fines.py
python3 scripts/build_db.py
python3 scripts/evaluate_dataset.py
python3 scripts/evaluate_dataset.py --failures
```

## Kết quả baseline ngày 11/11/2026

| Chỉ số | Kết quả |
|---|---:|
| Tra mức phạt, tìm đúng bản ghi trong 5 ứng viên đầu | 96/192 |
| Tra mức phạt, trả đúng bản ghi | 47/192 |
| Tra mức phạt, đúng cả min/max | 47/192 |
| Tra mức phạt, đúng căn cứ | 47/192 |
| Hỏi lại khi thiếu thông tin | 19/19 |
| Từ chối ngoài phạm vi hoặc thiếu nguồn | 0/8 |
| Thủ tục, tìm đúng đoạn trong 5 kết quả BM25 đầu | 46/46 |
| Thủ tục, số liệu trong key point xuất hiện trong câu trả lời | 46/46 |
| Thủ tục, độ phủ từ khóa trung bình | 87,4% |
| Thủ tục, ca dưới 60% từ khóa | 0/46 |
| Thủ tục, trích dẫn hợp lệ | 46/46 |

Nhánh tra mức phạt chấm theo CLI hiện có. Các câu mà CLI chưa trả lời được vẫn nằm trong mẫu số. Chỉ số hỏi lại đo loại phản hồi, còn `expected_reason` ghi chi tiết thông tin thiếu để dùng khi đánh giá router. Nhánh thủ tục đo truy xuất đoạn nguồn trên corpus 23 đoạn. Độ phủ từ khóa là heuristic từ vựng trên `expected_key_points`, dùng để bắt câu trả lời thiếu số liệu hoặc ý chính; nó không thay thế đánh giá ngữ nghĩa của người đọc.

## Chấm FastAPI qua HTTP

Khởi động backend theo [README](../../README.md), sau đó chạy từ thư mục gốc.

```bash
python scripts/evaluate_dataset.py --api-url http://127.0.0.1:8000/chat --failures
```

Bộ chấm kiểm tra bản ghi, khung tiền, căn cứ, đoạn thủ tục, loại phản hồi hỏi lại hoặc từ chối và độ trễ HTTP p95. Golden set này được dùng trong lúc phát triển API. Các số đo phản ánh mức độ bao phủ của bộ câu hỏi hiện có.

| Chỉ số qua HTTP cục bộ | Kết quả |
|---|---:|
| Đúng bản ghi, khung tiền, mức trần và căn cứ mức phạt | 192/192 |
| Đúng đoạn và căn cứ thủ tục | 46/46 |
| Thủ tục, số liệu trong key point xuất hiện trong câu trả lời | 46/46 |
| Thủ tục, độ phủ từ khóa trung bình | 87,4% |
| Thủ tục, ca dưới 60% từ khóa | 0/46 |
| Thủ tục, trích dẫn hợp lệ | 46/46 |
| Hỏi lại đúng loại phản hồi | 19/19 |
| Từ chối đúng loại phản hồi | 8/8 |
| Câu trả lời thiếu nguồn | 0 |
| Độ trễ HTTP p95 trong lần chạy kiểm thử | 2,0 ms |

Định tuyến mới coi xe khách, xe tải, xe đầu kéo như ô tô cho các hành vi có trong catalog: hai ca trước đây nhãn `refuse` ("Xe tải vượt đèn đỏ", "Xe khách 45 chỗ vượt đèn đỏ") được đổi thành Điều 6 khoản 9 điểm b, cùng bốn ca mới cho xe khách/xe tải/đầu kéo và một ca hỏi lại chọn khung chủ xe chở quá số người. Xe buýt, xe máy chuyên dùng vẫn ngoài phạm vi.

Ba câu về dùng tay cầm điện thoại khi lái ô tô được sửa nhãn thành Điều 6 khoản 5 điểm h theo catalog và Công báo. Bảy ca bổ sung phủ Điều 12 (người được chở), cách nói số lượng hành khách và trường hợp thiếu loại đường khi hỏi ngược chiều. Mười một ca tiếp theo phủ nhóm thiết bị/điều kiện xe: kính chắn gió, đèn lắp thêm, lốp, phanh, còi, giảm thanh, logo cơ quan và đèn sau.

Năm ca mới phủ phần Điều 32 bổ sung: khoản 5, khoản 6 (phạt theo người, có mức trần), điểm a khoản 9a, điểm e khoản 11 và điểm e khoản 13. Hai ca hỏi lại mới kiểm tra nhánh chọn khung khi câu hỏi chưa phân biệt được xe thường/tuyến trên 300 km hoặc cứu hộ/đầu kéo.
