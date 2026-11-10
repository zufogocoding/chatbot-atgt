# Phiếu rà soát catalog

Thư mục này chứa phiếu xuất từ catalog và các bản ghi phục vụ quá trình kiểm chứng hai người.

| Tệp | Nội dung |
|---|---|
| `review-2026-11-09.csv` | Phiếu đầy đủ 271 bản ghi, sinh tự động |
| `review-2026-11-09-fine.csv` | Phiếu 259 bản ghi có phạt tiền |
| `nguoi-ra-soat-1.csv` | Phiếu trống cho người rà soát 1 (259 bản ghi có phạt tiền) |
| `nguoi-ra-soat-2.csv` | Phiếu trống cho người rà soát 2 (259 bản ghi có phạt tiền) |
| `fine-audit-2026-11-10.csv` | Kết quả đối chiếu tự động mức tiền với đoạn luật |
| `spotcheck-2026-11-10.csv` | Mẫu 30 bản ghi rủi ro cao cho một người spot-check, **không phải phiếu xác minh hai người** |
| `ai-precheck-2026-11-10.csv` | Bản AI điền thử, **không phải phiếu của người rà soát** |
| `ai-precheck-2026-11-10.catalog-diff.csv` | Các ô dữ liệu catalog bị bản AI sửa |

## Quy tắc điền phiếu

1. Mỗi người mở một phiếu riêng, không xem phiếu của người kia trước khi điền xong.
2. Chỉ điền 8 cột: `expected_fine_min`, `expected_fine_max`, `fine_ok`, `citation_ok`, `text_ok`, `reviewer`, `reviewed_at`, `note`.
3. Không sửa các cột dữ liệu catalog (`behavior_text`, `fine_min`, `fine_max`, `additional_penalties`, `remedial_measures`, `source_quote`, `verification_status`...). Nếu thấy sai, đánh `SAI` và ghi lý do vào `note`.
4. Giá trị hợp lệ cho `*_ok`: `OK`, `SAI`, `NA`.
5. Hai phiếu phải có tên người rà soát khác nhau.

`scripts/merge_reviews.py` kiểm tra lại các cột catalog so với catalog hiện tại. Nếu phiếu bị sửa cột dữ liệu, script từ chối gộp và yêu cầu xuất lại phiếu.

## Mẫu spot-check 30 bản ghi rủi ro cao

`spotcheck-2026-11-10.csv` được sinh bằng `python3 scripts/export_spotcheck.py`. Đây là mẫu **một người** rà soát nhanh, không thay thế quy trình hai người và không thể gộp thành snapshot `verified`.

Mẫu chọn tự động, chia đều qua các nhóm rủi ro:

- 4 bản ghi người được chở (Điều 12);
- bản ghi sửa đổi bởi 238/2026/NĐ-CP;
- bản ghi có phạt tổ chức;
- bản ghi có điều kiện trừ điểm GPLX;
- bản ghi có hình phạt bổ sung;
- bản ghi có biện pháp khắc phục.

Cột `risk_reason` ghi lý do bản ghi nằm trong mẫu. Người rà soát điền các cột còn lại như phiếu thường (`expected_fine_min`, `expected_fine_max`, `fine_ok`, `citation_ok`, `text_ok`, `reviewer`, `reviewed_at`, `note`). Kết quả chỉ dùng để báo cáo độ tin cậy và phát hiện lỗi hệ thống, không dùng để đổi `verification_status`.

## Bản AI precheck ngày 10/11/2026

Tệp `ai-precheck-2026-11-10.csv` do AI điền, không đáp ứng quy trình hai người rà soát độc lập:

- Cột `reviewer` có hai nhãn AI trong cùng một phiếu: `Claude` (170 dòng) và `GPT-6 (đối chiếu tệp Công báo)` (89 dòng).
- Các cột `*_ok` dùng `TRUE`/`FALSE` thay vì `OK`/`SAI`/`NA`.
- Bản AI đổi `verification_status` của cả 259 dòng thành `reviewed`, dù chưa có người xác nhận.
- Bản AI sửa 31 ô `remedial_measures` và 25 ô `additional_penalties`; danh sách đầy đủ ở `ai-precheck-2026-11-10.catalog-diff.csv`.

### Kết quả duyệt 56 ô

- **37 ô** có điều kiện đúng theo luật đã được áp dụng qua `data/overrides/penalty-conditions.json`: điều kiện thùng xe của `32.18.c`/`32.19.đ`, điều kiện có phù hiệu của `32.18.đ`, và điều kiện gây hư hại cầu, đường của `32.19.e`.
- **14 ô** chỉ đề xuất thêm từ “giấy” vào “chứng nhận kiểm định” đã bị bác, vì Nghị định 238/2026 Điều 11 khoản 11 thay thế cụm từ này tại `32.18.c`, `32.18.d`, `32.19.đ`, `32.19.g` và `32.20`.
- **1 ô** đề xuất thêm tước phù hiệu cho `32.7.g` đã bị bác, vì 238/2026 Điều 11 khoản 12 bỏ “điểm e, điểm g khoản 7” khỏi `32.18.đ`.
- **4 ô** ghi chú về cách hiểu `32.18.a` (“tịch thu biển số; tịch thu biển số, thiết bị thay đổi biển số”) được giữ thành ghi chú trong `data/catalog/README.md`, không đưa vào dữ liệu hình phạt.

Trong 37 ô được áp dụng, một số ô còn kèm đề xuất thêm “giấy” hoặc mở rộng nhãn câu chữ; các phần đó không được áp dụng, chỉ phần điều kiện được giữ. Hai chỉnh sửa câu chữ được giữ thêm: “Buộc khôi phục lại tình trạng ban đầu…” (thay vì “Buộc tình trạng ban đầu…”) và nhãn “chứng nhận kiểm định và tem kiểm định” (thay vì “giấy chứng nhận/tem kiểm định”) cho khớp Nghị định 238/2026.

Kết quả đối chiếu nội dung:

- 259/259 mức tiền `expected_fine_min/max` khớp catalog.
- 19 dòng bị đánh `text_ok=FALSE`, nhưng cả 19 đều là dương tính giả vì người/AI chấm chỉ so với Nghị định 168/2024 mà bỏ qua Nghị định 238/2026.
- Các thay đổi tương ứng của 238/2026: Điều 2 khoản 2 (6.3.m); Điều 3 (13.8.b); Điều 4 (14.3.b); Điều 6 (18.4.a); Điều 11 khoản 11 (13.3.d, 13.4.b, 18.3.c, 32.1.b, 32.11.d, 32.14.h); Điều 11 khoản 12 (32.7.b); Điều 19 khoản 1 (6.3.h), khoản 2 (6.2.a, 6.5.g, 7.1.e), khoản 3 (6.5.i, 7.6.b), khoản 4 (6.7.c), khoản 10 (6.5.p).
- Riêng `nd168-d32-k1-b`: Điều 11 khoản 11 của 238/2026 ghi rõ thay thế cụm từ tại “điểm b khoản 1 … Điều 32”, nên catalog dùng “chứng nhận kiểm định khí thải” là đúng. Không cần sửa catalog.

Vì vậy bản AI precheck chỉ có giá trị tham khảo, không được dùng làm phiếu của người rà soát 1 hoặc 2 và không được gộp thành snapshot `verified`.
