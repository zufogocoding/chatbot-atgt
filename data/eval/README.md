# Golden set và baseline

[golden.jsonl](golden.jsonl) chứa 243 câu hỏi biên soạn cho snapshot 09/11/2026. Các nhãn được lưu cố định để phát hiện thay đổi khi chạy lại, với khung tiền lấy từ kết quả đối chiếu theo điều, khoản, điểm.

| Nhóm | Số câu |
|---|---:|
| Tra mức phạt xe máy | 75 |
| Tra mức phạt ô tô | 71 |
| Thủ tục nộp phạt và khiếu nại | 46 |
| Thiếu thông tin và ngoài phạm vi | 26 |
| Không dấu và teencode | 25 |

- `expected_answer_type` nhận `penalty`, `procedure`, `clarify` hoặc `refuse`.
- Ca mức phạt có `expected_violation_id`, `expected_legal_basis`, `expected_fine` và đối tượng áp dụng khung tiền. Cảnh cáo có cặp 0/0. Bản ghi chỉ có hình thức xử phạt khác có cặp null/null.
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

## Kết quả baseline ngày 10/11/2026

| Chỉ số | Kết quả |
|---|---:|
| Tra mức phạt, tìm đúng bản ghi trong 5 ứng viên đầu | 73/171 |
| Tra mức phạt, trả đúng bản ghi | 30/171 |
| Tra mức phạt, đúng cả min/max | 25/171 |
| Tra mức phạt, đúng căn cứ | 25/171 |
| Hỏi lại khi thiếu thông tin | 16/16 |
| Từ chối ngoài phạm vi hoặc thiếu nguồn | 0/10 |
| Thủ tục, tìm đúng đoạn trong 5 kết quả BM25 đầu | 46/46 |

Nhánh tra mức phạt chấm theo CLI hiện có. Các câu mà CLI chưa trả lời được vẫn nằm trong mẫu số. Chỉ số hỏi lại đo loại phản hồi, còn `expected_reason` ghi chi tiết thông tin thiếu để dùng khi đánh giá router. Nhánh thủ tục đo truy xuất đoạn nguồn trên corpus 23 đoạn. Chất lượng nội dung trả lời, độ chính xác trích dẫn do RAG sinh và mục tiêu đầy đủ của MVP cần được đo sau khi tích hợp.

## Chấm FastAPI qua HTTP

Khởi động backend theo [README](../../README.md), sau đó chạy từ thư mục gốc.

```bash
python scripts/evaluate_dataset.py --api-url http://127.0.0.1:8000/chat --failures
```

Bộ chấm kiểm tra bản ghi, khung tiền, căn cứ, đoạn thủ tục, loại phản hồi hỏi lại hoặc từ chối và độ trễ HTTP p95. Golden set này được dùng trong lúc phát triển API. Các số đo phản ánh mức độ bao phủ của bộ câu hỏi hiện có.

| Chỉ số qua HTTP cục bộ | Kết quả |
|---|---:|
| Đúng bản ghi, khung tiền và căn cứ mức phạt | 171/171 |
| Đúng đoạn và căn cứ thủ tục | 46/46 |
| Hỏi lại đúng loại phản hồi | 16/16 |
| Từ chối đúng loại phản hồi | 10/10 |
| Câu trả lời thiếu nguồn | 0 |
| Độ trễ HTTP p95 trong lần chạy kiểm thử | 1,5 ms |

Ba câu về dùng tay cầm điện thoại khi lái ô tô được sửa nhãn thành Điều 6 khoản 5 điểm h theo catalog và Công báo. Bảy ca mới bổ sung phủ Điều 12 (người được chở), cách nói số lượng hành khách và trường hợp thiếu loại đường khi hỏi ngược chiều.
